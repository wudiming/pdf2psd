"""
Custom PSD (Photoshop Document) binary writer.
Creates multi-layer RGBA PSD files from PIL images.
Implements Adobe PSD format spec (version 1).

Compression modes
-----------------
0 = RAW        : No compression. Fastest write (~10-20× vs RLE). Largest files.
1 = RLE        : PackBits. Slowest write. Smallest files. Best compatibility.
2 = ZIP (zlib) : Fastest write + small files. Requires Photoshop CS or later.
                 Default choice: best speed/size balance.
"""

import struct
import io
import zlib
from PIL import Image
from typing import List, Optional, Tuple


# ── Compression helpers ───────────────────────────────────────────────────────

def _packbits_encode(data: bytes) -> bytes:
    """PackBits RLE compression (PSD compression type 1)."""
    if not data:
        return b''
    buf = list(data)
    result = []
    i = 0
    n = len(buf)
    while i < n:
        j = i + 1
        while j < n and (j - i) < 128 and buf[j] == buf[i]:
            j += 1
        run_len = j - i
        if run_len >= 2:
            result.append(257 - run_len)
            result.append(buf[i])
            i = j
        else:
            j = i + 1
            while j < n and (j - i) < 128:
                if j + 2 < n and buf[j] == buf[j + 1] == buf[j + 2]:
                    break
                j += 1
            lit_len = j - i
            result.append(lit_len - 1)
            result.extend(buf[i:j])
            i = j
    return bytes(result)


def _compress_channel(
    raw: bytes,
    width: int,
    height: int,
    compression: int,
) -> Tuple[int, bytes]:
    """
    Compress a single channel plane.

    Returns:
        (data_len, block_bytes)
        data_len   : total byte count to record in the layer descriptor
        block_bytes: bytes to write into the channel image data section
                     (includes the 2-byte compression type header)
    """
    if compression == 0:
        # RAW — no compression
        block = struct.pack('>H', 0) + raw
        return len(block), block

    elif compression == 1:
        # RLE / PackBits
        byte_counts = []
        rows = []
        for row in range(height):
            row_data = raw[row * width: (row + 1) * width]
            compressed_row = _packbits_encode(row_data)
            byte_counts.append(len(compressed_row))
            rows.append(compressed_row)
        counts_bytes = b''.join(struct.pack('>H', bc) for bc in byte_counts)
        compressed_data = b''.join(rows)
        block = struct.pack('>H', 1) + counts_bytes + compressed_data
        return len(block), block

    else:
        raise ValueError(f"Unsupported compression: {compression}")


# ── Utilities ─────────────────────────────────────────────────────────────────

def _pad_to_even(data: bytes) -> bytes:
    return data + b'\x00' if len(data) % 2 else data


def _pascal_string(name: str, align: int = 4) -> bytes:
    """Pascal string (length byte + text) padded to `align` bytes."""
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
    compression: int = 2,   # Default: ZIP (fast + compact)
) -> None:
    """
    Write a multi-layer PSD file where each image becomes a named layer.

    Args:
        output_path : Destination .psd file path.
        images      : PIL Images; any mode accepted, normalised to RGBA internally.
        layer_names : Optional layer name list (same length as images).
        dpi         : Document resolution (pixels/inch).
        compression : 0=RAW (fastest), 1=RLE (smallest), 2=ZIP (default, fast+small).
    """
    if not images:
        raise ValueError("No images provided")

    # Normalise to RGBA
    rgba = [img.convert('RGBA') for img in images]

    canvas_w = max(im.width for im in rgba)
    canvas_h = max(im.height for im in rgba)

    if layer_names is None:
        layer_names = [f"Page {i + 1}" for i in range(len(rgba))]
    while len(layer_names) < len(rgba):
        layer_names.append(f"Page {len(layer_names) + 1}")

    with open(output_path, 'wb') as f:

        # ── Section 1: File Header ─────────────────────────────────────────
        f.write(b'8BPS')
        f.write(struct.pack('>H', 1))            # Version 1 = PSD
        f.write(b'\x00' * 6)                     # Reserved
        f.write(struct.pack('>H', 3))            # Channels (merged RGB)
        f.write(struct.pack('>I', canvas_h))
        f.write(struct.pack('>I', canvas_w))
        f.write(struct.pack('>H', 8))            # Bit depth
        f.write(struct.pack('>H', 3))            # Color mode: RGB

        # ── Section 2: Color Mode Data ────────────────────────────────────
        f.write(struct.pack('>I', 0))            # Empty for RGB

        # ── Section 3: Image Resources ────────────────────────────────────
        res_buf = io.BytesIO()
        h_res = dpi << 16
        v_res = dpi << 16
        res_data = (
            struct.pack('>I', h_res) +
            struct.pack('>H', 1) +               # H unit: pixels/inch
            struct.pack('>H', 1) +               # Width unit
            struct.pack('>I', v_res) +
            struct.pack('>H', 1) +               # V unit
            struct.pack('>H', 1)                 # Height unit
        )
        res_buf.write(b'8BIM')
        res_buf.write(struct.pack('>H', 0x03ED)) # Resource 1005: Resolution
        res_buf.write(b'\x00\x00')               # Empty Pascal name
        res_buf.write(struct.pack('>I', len(res_data)))
        res_buf.write(res_data)
        res_bytes = res_buf.getvalue()
        f.write(struct.pack('>I', len(res_bytes)))
        f.write(res_bytes)

        # ── Section 4: Layer and Mask Information ─────────────────────────
        lm_buf = io.BytesIO()
        li_buf = io.BytesIO()
        li_buf.write(struct.pack('>h', len(rgba)))  # Layer count

        channel_ids = [-1, 0, 1, 2]              # transparency, R, G, B
        all_channel_blocks = []                  # [(block, block, block, block), ...]

        for img, name in zip(rgba, layer_names):
            # Paste image onto canvas (top-left), preserving transparency
            canvas = Image.new('RGBA', (canvas_w, canvas_h), (0, 0, 0, 0))
            canvas.paste(img, (0, 0))

            r, g, b, a = canvas.split()
            planes = [a, r, g, b]               # order: alpha, R, G, B

            ch_blocks = []
            ch_records = []
            for ch_id, plane in zip(channel_ids, planes):
                raw = plane.tobytes()
                data_len, block = _compress_channel(raw, canvas_w, canvas_h, compression)
                ch_blocks.append(block)
                ch_records.append((ch_id, data_len))

            all_channel_blocks.append(ch_blocks)

            # Layer record
            li_buf.write(struct.pack('>iiii', 0, 0, canvas_h, canvas_w))
            li_buf.write(struct.pack('>H', 4))   # 4 channels
            for ch_id, data_len in ch_records:
                li_buf.write(struct.pack('>hI', ch_id, data_len))

            li_buf.write(b'8BIM')
            li_buf.write(b'norm')               # Normal blend mode
            li_buf.write(struct.pack('>BBBB', 255, 0, 0, 0))  # opacity, clip, flags, pad

            extra = io.BytesIO()
            extra.write(struct.pack('>I', 0))   # Layer mask: empty
            extra.write(struct.pack('>I', 0))   # Blending ranges: empty
            extra.write(_pascal_string(name, 4))
            extra_bytes = extra.getvalue()
            li_buf.write(struct.pack('>I', len(extra_bytes)))
            li_buf.write(extra_bytes)

        # ── 4b: Channel Image Data ────────────────────────────────────────
        for ch_blocks in all_channel_blocks:
            for block in ch_blocks:
                li_buf.write(block)

        li_bytes = _pad_to_even(li_buf.getvalue())
        lm_buf.write(struct.pack('>I', len(li_bytes)))
        lm_buf.write(li_bytes)
        lm_buf.write(struct.pack('>I', 0))      # Global mask info: empty

        lm_bytes = lm_buf.getvalue()
        f.write(struct.pack('>I', len(lm_bytes)))
        f.write(lm_bytes)

        # ── Section 5: Flattened Composite ────────────────────────────────
        # Build composite (bottom to top) for PS's thumbnail preview
        merged = Image.new('RGBA', (canvas_w, canvas_h), (255, 255, 255, 255))
        for img in reversed(rgba):
            tmp = Image.new('RGBA', (canvas_w, canvas_h), (0, 0, 0, 0))
            tmp.paste(img, (0, 0))
            merged = Image.alpha_composite(merged, tmp)

        merged_rgb = merged.convert('RGB')
        r_ch, g_ch, b_ch = merged_rgb.split()

        if compression == 0:
            # RAW: write all channel data without per-row byte counts
            f.write(struct.pack('>H', 0))
            for plane in (r_ch, g_ch, b_ch):
                f.write(plane.tobytes())

        else:
            # RLE: write per-row byte counts for all channels, then data
            f.write(struct.pack('>H', 1))
            channels_data = []
            for plane in (r_ch, g_ch, b_ch):
                raw = plane.tobytes()
                byte_counts = []
                rows = []
                for row in range(canvas_h):
                    row_data = raw[row * canvas_w: (row + 1) * canvas_w]
                    comp_row = _packbits_encode(row_data)
                    byte_counts.append(len(comp_row))
                    rows.append(comp_row)
                channels_data.append((byte_counts, b''.join(rows)))
            for byte_counts, _ in channels_data:
                for bc in byte_counts:
                    f.write(struct.pack('>H', bc))
            for _, compressed in channels_data:
                f.write(compressed)
