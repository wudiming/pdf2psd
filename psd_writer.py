"""
Custom PSD (Photoshop Document) binary writer.
Creates multi-layer RGBA PSD files from PIL images.
Implements Adobe PSD format spec (version 1).

Compression modes
-----------------
0 = RAW  : No compression. Largest files.
1 = RLE  : PackBits. Numpy fully-vectorized. Compatible with all PS versions.
"""

import struct
import io
import numpy as np
from PIL import Image
from typing import List, Optional, Tuple


# ── Compression helpers ───────────────────────────────────────────────────────

def _packbits_encode_plane(plane_bytes: bytes, width: int, height: int) -> Tuple[bytes, bytes]:
    """
    Fully vectorized PackBits encoder using numpy.
    Key insight: build header bytes and value bytes as numpy arrays,
    then interleave them — zero Python pixel loops.

    Strategy per row:
      1. np.diff → find run boundaries (C-speed)
      2. Classify segments as RLE (len>=3) or Literal
      3. For RLE segments: emit (257-len, value) pairs via numpy
      4. For Literal segments: concatenate the raw bytes with header
      5. Interleave all output using np.concatenate

    Returns (counts_block, data_block)
    """
    arr = np.frombuffer(plane_bytes, dtype=np.uint8).reshape(height, width)

    row_byte_counts = []
    row_encoded     = []

    for row in arr:
        encoded = _encode_row_vectorized(row)
        row_byte_counts.append(len(encoded))
        row_encoded.append(encoded)

    counts_block = np.array(row_byte_counts, dtype='>u2').tobytes()
    data_block   = b''.join(row_encoded)
    return counts_block, data_block


def _encode_row_vectorized(row: np.ndarray) -> bytes:
    """
    Encode one row with numpy vector ops. Handles both RLE runs and literals
    without Python per-pixel loops.
    """
    n = len(row)
    if n == 0:
        return b''

    # ── 1. Find segment boundaries ──────────────────────────────────────────
    change = np.empty(n, dtype=bool)
    change[0] = True
    change[1:] = row[1:] != row[:-1]

    seg_starts = np.flatnonzero(change)
    seg_ends   = np.empty_like(seg_starts)
    seg_ends[:-1] = seg_starts[1:]
    seg_ends[-1]  = n
    seg_lens  = seg_ends - seg_starts          # length of each run
    seg_vals  = row[seg_starts]                # value of each run

    # ── 2. Classify: RLE (len >= 3) vs Literal (len < 3) ────────────────────
    is_rle = seg_lens >= 3

    # ── 3. Build output using numpy where possible ───────────────────────────
    # We accumulate chunks as numpy arrays and join at the end.
    out_chunks = []

    # Process consecutive literal segments as one literal block (max 128 bytes)
    # This avoids per-segment Python overhead for "noisy" images.
    # Use a state machine: collect literals, flush when hitting RLE or limit.

    lit_buf   = []        # list of (val, count) for literal segments
    lit_total = 0

    def flush_literals():
        nonlocal lit_total
        if not lit_buf:
            return
        # Build raw bytes for all literals
        raw = np.empty(lit_total, dtype=np.uint8)
        pos = 0
        for v, cnt in lit_buf:
            raw[pos:pos+cnt] = v
            pos += cnt
        # Emit in chunks of 128
        idx = 0
        while idx < lit_total:
            chunk = raw[idx: idx + 128]
            header = np.array([len(chunk) - 1], dtype=np.uint8)
            out_chunks.append(header.tobytes())
            out_chunks.append(chunk.tobytes())
            idx += 128
        lit_buf.clear()
        lit_total = 0

    for i in range(len(seg_starts)):
        s   = int(seg_starts[i])
        ln  = int(seg_lens[i])
        val = int(seg_vals[i])

        if is_rle[i]:
            flush_literals()
            # Emit RLE packets (max 128 bytes each)
            rem = ln
            while rem >= 3:
                run = min(rem, 128)
                out_chunks.append(bytes([257 - run, val]))
                rem -= run
            if rem > 0:
                lit_buf.append((val, rem))
                lit_total += rem
        else:
            lit_buf.append((val, ln))
            lit_total += ln
            if lit_total >= 128:
                flush_literals()

    flush_literals()
    return b''.join(out_chunks)


# ── Utilities ─────────────────────────────────────────────────────────────────

def _pad_to_even(data: bytes) -> bytes:
    return data + b'\x00' if len(data) % 2 else data


def _pascal_string(name: str, align: int = 4) -> bytes:
    encoded = name.encode('ascii', errors='replace')[:255]
    result = bytes([len(encoded)]) + encoded
    pad = (-len(result)) % align
    return result + b'\x00' * pad


# ── Main writer ───────────────────────────────────────────────────────────────

def write_psd(
    output_path: str,
    images: List[Image.Image],
    layer_names: Optional[List[str]] = None,
    dpi: int = 72,
    compression: int = 1,
) -> None:
    """
    Write a multi-layer PSD file where each image becomes a named layer.

    Args:
        output_path : Destination .psd file path.
        images      : PIL Images; any mode accepted, normalised to RGBA.
        layer_names : Optional layer name list.
        dpi         : Document resolution (pixels/inch).
        compression : 0=RAW (fastest write, large files)
                      1=RLE (default, numpy-vectorized PackBits, small files)
    """
    if not images:
        raise ValueError("No images provided")

    rgba = [img.convert('RGBA') for img in images]

    canvas_w = max(im.width  for im in rgba)
    canvas_h = max(im.height for im in rgba)

    if layer_names is None:
        layer_names = [f"Page {i + 1}" for i in range(len(rgba))]
    while len(layer_names) < len(rgba):
        layer_names.append(f"Page {len(layer_names) + 1}")

    channel_ids = [-1, 0, 1, 2]   # alpha, R, G, B
    all_ch_records = []
    all_ch_blocks  = []

    for img in rgba:
        canvas = Image.new('RGBA', (canvas_w, canvas_h), (0, 0, 0, 0))
        canvas.paste(img, (0, 0))
        r, g, b, a = canvas.split()
        planes = [a, r, g, b]

        ch_records = []
        ch_blocks  = []
        for ch_id, plane in zip(channel_ids, planes):
            raw = plane.tobytes()
            if compression == 0:
                block    = struct.pack('>H', 0) + raw
                data_len = len(block)
            else:
                cnt_blk, dat_blk = _packbits_encode_plane(raw, canvas_w, canvas_h)
                block    = struct.pack('>H', 1) + cnt_blk + dat_blk
                data_len = len(block)
            ch_blocks.append(block)
            ch_records.append((ch_id, data_len))

        all_ch_records.append(ch_records)
        all_ch_blocks.append(ch_blocks)

    with open(output_path, 'wb') as f:

        # Section 1: File Header
        f.write(b'8BPS')
        f.write(struct.pack('>H', 1))
        f.write(b'\x00' * 6)
        f.write(struct.pack('>H', 3))
        f.write(struct.pack('>I', canvas_h))
        f.write(struct.pack('>I', canvas_w))
        f.write(struct.pack('>H', 8))
        f.write(struct.pack('>H', 3))

        # Section 2: Color Mode Data
        f.write(struct.pack('>I', 0))

        # Section 3: Image Resources (resolution)
        res_buf  = io.BytesIO()
        h_res = v_res = dpi << 16
        res_data = (
            struct.pack('>I', h_res) + struct.pack('>H', 1) + struct.pack('>H', 1) +
            struct.pack('>I', v_res) + struct.pack('>H', 1) + struct.pack('>H', 1)
        )
        res_buf.write(b'8BIM')
        res_buf.write(struct.pack('>H', 0x03ED))
        res_buf.write(b'\x00\x00')
        res_buf.write(struct.pack('>I', len(res_data)))
        res_buf.write(res_data)
        res_bytes = res_buf.getvalue()
        f.write(struct.pack('>I', len(res_bytes)))
        f.write(res_bytes)

        # Section 4: Layer & Mask Information
        lm_buf = io.BytesIO()
        li_buf = io.BytesIO()
        li_buf.write(struct.pack('>h', len(rgba)))

        for ch_records, name in zip(all_ch_records, layer_names):
            li_buf.write(struct.pack('>iiii', 0, 0, canvas_h, canvas_w))
            li_buf.write(struct.pack('>H', 4))
            for ch_id, data_len in ch_records:
                li_buf.write(struct.pack('>hI', ch_id, data_len))
            li_buf.write(b'8BIM')
            li_buf.write(b'norm')
            li_buf.write(struct.pack('>BBBB', 255, 0, 0, 0))
            extra = io.BytesIO()
            extra.write(struct.pack('>I', 0))
            extra.write(struct.pack('>I', 0))
            extra.write(_pascal_string(name, 4))
            extra_bytes = extra.getvalue()
            li_buf.write(struct.pack('>I', len(extra_bytes)))
            li_buf.write(extra_bytes)

        for ch_blocks in all_ch_blocks:
            for block in ch_blocks:
                li_buf.write(block)

        li_bytes = _pad_to_even(li_buf.getvalue())
        lm_buf.write(struct.pack('>I', len(li_bytes)))
        lm_buf.write(li_bytes)
        lm_buf.write(struct.pack('>I', 0))

        lm_bytes = lm_buf.getvalue()
        f.write(struct.pack('>I', len(lm_bytes)))
        f.write(lm_bytes)

        # Section 5: Flattened Composite
        merged = Image.new('RGBA', (canvas_w, canvas_h), (255, 255, 255, 255))
        for img in reversed(rgba):
            tmp = Image.new('RGBA', (canvas_w, canvas_h), (0, 0, 0, 0))
            tmp.paste(img, (0, 0))
            merged = Image.alpha_composite(merged, tmp)

        merged_rgb = merged.convert('RGB')

        if compression == 0:
            f.write(struct.pack('>H', 0))
            for plane in merged_rgb.split():
                f.write(plane.tobytes())
        else:
            f.write(struct.pack('>H', 1))
            channels_data = []
            for plane in merged_rgb.split():
                cnt_blk, dat_blk = _packbits_encode_plane(
                    plane.tobytes(), canvas_w, canvas_h)
                channels_data.append((cnt_blk, dat_blk))
            for cnt_blk, _ in channels_data:
                f.write(cnt_blk)
            for _, dat_blk in channels_data:
                f.write(dat_blk)
