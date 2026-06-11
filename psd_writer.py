"""
Custom PSD (Photoshop Document) binary writer.
Creates multi-layer RGBA PSD files from PIL images.
Implements Adobe PSD format spec (version 1).

Compression
-----------
0 = RAW  : No compression. Fastest write. Largest files.
1 = RLE  : Adaptive PackBits. Samples 16 rows per plane to measure
           compressibility; if savings < 5% automatically falls back to RAW
           for that plane. This gives near-RAW speed for photo/complex images
           while still producing small files for typical text+white PDFs.
"""

import struct
import io
import numpy as np
from PIL import Image
from typing import List, Optional, Tuple


# ── PackBits encoder ──────────────────────────────────────────────────────────

def _packbits_row(row: np.ndarray) -> bytes:
    """Encode one row with PackBits RLE."""
    n = len(row)
    if n == 0:
        return b''

    # Find run-boundary positions using numpy (C-speed)
    ne = row[1:] != row[:-1]
    seg_starts = np.concatenate(([0], np.flatnonzero(ne) + 1))
    seg_ends   = np.empty(len(seg_starts), dtype=np.intp)
    seg_ends[:-1] = seg_starts[1:]
    seg_ends[-1]  = n
    seg_lens = seg_ends - seg_starts
    seg_vals = row[seg_starts]

    out = bytearray()
    lit  = bytearray()

    def flush():
        while lit:
            chunk = lit[:128]
            out.append(len(chunk) - 1)
            out.extend(chunk)
            del lit[:128]

    for ln, val in zip(seg_lens, seg_vals):
        ln = int(ln); val = int(val)
        if ln >= 3:
            flush()
            while ln >= 3:
                run = min(ln, 128)
                out.append(257 - run)
                out.append(val)
                ln -= run
            if ln:
                lit.extend([val] * ln)
        else:
            lit.extend([val] * ln)
            if len(lit) >= 128:
                flush()

    flush()
    return bytes(out)


def _compress_plane_adaptive(
    plane_bytes: bytes, width: int, height: int
) -> Tuple[int, bytes]:
    """
    Compress one channel plane with adaptive PackBits.

    Samples 16 evenly-spaced rows first.
    If estimated RLE size >= 95% of raw → returns RAW block (header 0).
    Otherwise → returns full RLE block (header 1).

    Returns (compression_type_used, block_bytes).
    """
    raw_size = len(plane_bytes)
    arr = np.frombuffer(plane_bytes, dtype=np.uint8).reshape(height, width)

    # ── Probe: sample 16 rows ─────────────────────────────────────────────────
    indices = np.linspace(0, height - 1, min(16, height), dtype=int)
    sample_raw = sample_enc = 0
    for idx in indices:
        enc = _packbits_row(arr[idx])
        sample_raw += width
        sample_enc += len(enc)

    if sample_enc >= sample_raw * 0.95:
        # RLE won't help for this plane — use RAW (instant write)
        return 0, struct.pack('>H', 0) + plane_bytes

    # ── Full RLE encode ───────────────────────────────────────────────────────
    byte_counts = []
    rows_enc    = []
    for row in arr:
        enc = _packbits_row(row)
        byte_counts.append(len(enc))
        rows_enc.append(enc)

    counts_block = np.array(byte_counts, dtype='>u2').tobytes()
    data_block   = b''.join(rows_enc)
    block = struct.pack('>H', 1) + counts_block + data_block
    return 1, block


# ── Utilities ─────────────────────────────────────────────────────────────────

def _pad_to_even(data: bytes) -> bytes:
    return data + b'\x00' if len(data) % 2 else data


def _pascal_string(name: str, align: int = 4) -> bytes:
    encoded = name.encode('ascii', errors='replace')[:255]
    result  = bytes([len(encoded)]) + encoded
    return result + b'\x00' * ((-len(result)) % align)


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
        compression : 0=RAW always, 1=Adaptive RLE (auto-selects per plane).
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

    channel_ids = [-1, 0, 1, 2]   # alpha, R, G, B — PSD channel order

    # ── Pre-compress all layer channels ───────────────────────────────────────
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
                block = struct.pack('>H', 0) + raw
            else:
                _, block = _compress_plane_adaptive(raw, canvas_w, canvas_h)
            ch_blocks.append(block)
            ch_records.append((ch_id, len(block)))

        all_ch_records.append(ch_records)
        all_ch_blocks.append(ch_blocks)

    # ── Write file ────────────────────────────────────────────────────────────
    with open(output_path, 'wb') as f:

        # Section 1: File Header
        f.write(b'8BPS')
        f.write(struct.pack('>H', 1))
        f.write(b'\x00' * 6)
        f.write(struct.pack('>H', 3))        # merged composite has 3 channels
        f.write(struct.pack('>I', canvas_h))
        f.write(struct.pack('>I', canvas_w))
        f.write(struct.pack('>H', 8))        # 8 bit depth
        f.write(struct.pack('>H', 3))        # RGB color mode

        # Section 2: Color Mode Data
        f.write(struct.pack('>I', 0))

        # Section 3: Image Resources (resolution info)
        res_buf = io.BytesIO()
        hv_res  = dpi << 16
        res_data = (
            struct.pack('>I', hv_res) + struct.pack('>HH', 1, 1) +
            struct.pack('>I', hv_res) + struct.pack('>HH', 1, 1)
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
        li_buf.write(struct.pack('>h', len(rgba)))  # signed layer count

        for ch_records, name in zip(all_ch_records, layer_names):
            li_buf.write(struct.pack('>iiii', 0, 0, canvas_h, canvas_w))
            li_buf.write(struct.pack('>H', 4))
            for ch_id, data_len in ch_records:
                li_buf.write(struct.pack('>hI', ch_id, data_len))
            li_buf.write(b'8BIM')
            li_buf.write(b'norm')
            li_buf.write(struct.pack('>BBBB', 255, 0, 0, 0))

            extra = io.BytesIO()
            extra.write(struct.pack('>I', 0))    # layer mask: empty
            extra.write(struct.pack('>I', 0))    # blending ranges: empty
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
        lm_buf.write(struct.pack('>I', 0))   # global mask: empty

        lm_bytes = lm_buf.getvalue()
        f.write(struct.pack('>I', len(lm_bytes)))
        f.write(lm_bytes)

        # Section 5: Flattened Composite (RAW — it's just PS's preview thumbnail)
        merged = Image.new('RGBA', (canvas_w, canvas_h), (255, 255, 255, 255))
        for img in reversed(rgba):
            tmp = Image.new('RGBA', (canvas_w, canvas_h), (0, 0, 0, 0))
            tmp.paste(img, (0, 0))
            merged = Image.alpha_composite(merged, tmp)
        merged_rgb = merged.convert('RGB')
        f.write(struct.pack('>H', 0))        # RAW compression for composite
        for plane in merged_rgb.split():
            f.write(plane.tobytes())
