"""
Custom PSD (Photoshop Document) binary writer.
Creates multi-layer RGB PSD files from PIL images.
Implements Adobe PSD format spec (version 1).
"""

import struct
import io
from PIL import Image
from typing import List, Optional, Tuple


def packbits_encode(data: bytes) -> bytes:
    """PackBits RLE compression used by PSD format."""
    if not data:
        return b''

    buf = list(data)
    result = []
    i = 0
    n = len(buf)

    while i < n:
        # Try to find a run of same bytes
        j = i + 1
        while j < n and (j - i) < 128 and buf[j] == buf[i]:
            j += 1

        run_len = j - i
        if run_len >= 2:
            # Encode as repeat: control byte = -(run_len - 1) as unsigned
            result.append(257 - run_len)
            result.append(buf[i])
            i = j
        else:
            # Find end of literal run
            j = i + 1
            while j < n and (j - i) < 128:
                # Stop before a run of 3+ same bytes
                if j + 2 < n and buf[j] == buf[j + 1] == buf[j + 2]:
                    break
                j += 1
            lit_len = j - i
            result.append(lit_len - 1)
            result.extend(buf[i:j])
            i = j

    return bytes(result)


def compress_channel_rle(
    channel_data: bytes, width: int, height: int
) -> Tuple[List[int], bytes]:
    """
    Compress one channel plane row-by-row using RLE.

    Returns:
        (byte_counts, compressed_data)
        byte_counts: per-row compressed byte lengths (list of ints)
        compressed_data: all compressed rows concatenated
    """
    byte_counts = []
    rows_bytes = []

    for row in range(height):
        row_data = channel_data[row * width: (row + 1) * width]
        compressed = packbits_encode(row_data)
        byte_counts.append(len(compressed))
        rows_bytes.append(compressed)

    return byte_counts, b''.join(rows_bytes)


def _pad_to_even(data: bytes) -> bytes:
    return data + b'\x00' if len(data) % 2 else data


def _pascal_string(name: str, align: int = 4) -> bytes:
    """Pascal string (length byte + text) padded to `align` bytes."""
    encoded = name.encode('ascii', errors='replace')[:255]
    result = bytes([len(encoded)]) + encoded
    pad = (-len(result)) % align
    return result + b'\x00' * pad


def write_psd(
    output_path: str,
    images: List[Image.Image],
    layer_names: Optional[List[str]] = None,
    dpi: int = 72,
) -> None:
    """
    Write a multi-layer PSD file where each image becomes a named layer.

    Args:
        output_path : Destination .psd file path.
        images      : PIL Images; may be any mode, will be normalised to RGBA.
        layer_names : Optional list of layer names (same length as images).
        dpi         : Document resolution stored in image resources.
    """
    if not images:
        raise ValueError("No images provided")

    # Normalise to RGBA
    rgba = [img.convert('RGBA') for img in images]

    canvas_w = max(im.width for im in rgba)
    canvas_h = max(im.height for im in rgba)

    if layer_names is None:
        layer_names = [f"Page {i + 1}" for i in range(len(rgba))]
    # Ensure list is long enough
    while len(layer_names) < len(rgba):
        layer_names.append(f"Page {len(layer_names) + 1}")

    with open(output_path, 'wb') as f:

        # ── Section 1: File Header ─────────────────────────────────────────
        f.write(b'8BPS')                         # Signature
        f.write(struct.pack('>H', 1))            # Version 1 = PSD
        f.write(b'\x00' * 6)                     # Reserved
        f.write(struct.pack('>H', 3))            # Channels (merged image = RGB)
        f.write(struct.pack('>I', canvas_h))     # Height
        f.write(struct.pack('>I', canvas_w))     # Width
        f.write(struct.pack('>H', 8))            # Bit depth
        f.write(struct.pack('>H', 3))            # Color mode: RGB

        # ── Section 2: Color Mode Data ────────────────────────────────────
        f.write(struct.pack('>I', 0))            # Empty for RGB

        # ── Section 3: Image Resources ────────────────────────────────────
        res_buf = io.BytesIO()

        # Resource 0x03ED (1005): Resolution Info
        h_res = dpi << 16                        # Fixed-point 16.16
        v_res = dpi << 16
        res_data = (
            struct.pack('>I', h_res) +           # H resolution (fixed)
            struct.pack('>H', 1) +               # H res unit: 1 = pixels/inch
            struct.pack('>H', 1) +               # Width unit
            struct.pack('>I', v_res) +           # V resolution (fixed)
            struct.pack('>H', 1) +               # V res unit
            struct.pack('>H', 1)                 # Height unit
        )
        res_buf.write(b'8BIM')
        res_buf.write(struct.pack('>H', 0x03ED))
        res_buf.write(b'\x00\x00')               # Empty Pascal name
        res_buf.write(struct.pack('>I', len(res_data)))
        res_buf.write(res_data)

        res_bytes = res_buf.getvalue()
        f.write(struct.pack('>I', len(res_bytes)))
        f.write(res_bytes)

        # ── Section 4: Layer and Mask Information ─────────────────────────
        lm_buf = io.BytesIO()

        # ── 4a: Layer Info ────────────────────────────────────────────────
        li_buf = io.BytesIO()
        li_buf.write(struct.pack('>h', len(rgba)))  # Layer count

        channel_ids = [-1, 0, 1, 2]              # alpha(transparency), R, G, B
        all_layer_ch_data = []                   # store compressed data to write later

        for img, name in zip(rgba, layer_names):
            # Paste onto canvas (top-left aligned)
            canvas = Image.new('RGBA', (canvas_w, canvas_h), (255, 255, 255, 0))
            canvas.paste(img, (0, 0))
            a, r, g, b = canvas.split()[3], *canvas.split()[:3]
            planes = [a, r, g, b]                # order: transparency, R, G, B

            layer_ch_data = []
            for ch_id, plane in zip(channel_ids, planes):
                raw = plane.tobytes()
                bcounts, compressed = compress_channel_rle(raw, canvas_w, canvas_h)
                data_len = 2 + 2 * canvas_h + len(compressed)
                layer_ch_data.append({
                    'id': ch_id,
                    'data_len': data_len,
                    'bcounts': bcounts,
                    'compressed': compressed,
                })
            all_layer_ch_data.append(layer_ch_data)

            # Layer record
            li_buf.write(struct.pack('>iiii', 0, 0, canvas_h, canvas_w))
            li_buf.write(struct.pack('>H', 4))   # 4 channels: alpha, R, G, B
            for ch in layer_ch_data:
                li_buf.write(struct.pack('>hI', ch['id'], ch['data_len']))

            li_buf.write(b'8BIM')                # Blend mode signature
            li_buf.write(b'norm')                # Normal blend
            li_buf.write(struct.pack('>BBBB', 255, 0, 0, 0))  # opacity, clip, flags, pad

            # Extra data
            extra = io.BytesIO()
            extra.write(struct.pack('>I', 0))    # Layer mask: empty
            extra.write(struct.pack('>I', 0))    # Blending ranges: empty
            extra.write(_pascal_string(name, 4))
            extra_bytes = extra.getvalue()
            li_buf.write(struct.pack('>I', len(extra_bytes)))
            li_buf.write(extra_bytes)

        # ── 4b: Channel Image Data ────────────────────────────────────────
        for layer_ch_data in all_layer_ch_data:
            for ch in layer_ch_data:
                li_buf.write(struct.pack('>H', 1))          # Compression: RLE
                for bc in ch['bcounts']:
                    li_buf.write(struct.pack('>H', bc))     # Row byte counts
                li_buf.write(ch['compressed'])              # Compressed data

        li_bytes = _pad_to_even(li_buf.getvalue())
        lm_buf.write(struct.pack('>I', len(li_bytes)))
        lm_buf.write(li_bytes)
        lm_buf.write(struct.pack('>I', 0))       # Global mask info: empty

        lm_bytes = lm_buf.getvalue()
        f.write(struct.pack('>I', len(lm_bytes)))
        f.write(lm_bytes)

        # ── Section 5: Image Data (flattened composite) ───────────────────
        # Composite all layers for the merged preview Photoshop displays.
        merged = Image.new('RGBA', (canvas_w, canvas_h), (255, 255, 255, 255))
        for img in reversed(rgba):
            tmp = Image.new('RGBA', (canvas_w, canvas_h), (255, 255, 255, 0))
            tmp.paste(img, (0, 0))
            merged = Image.alpha_composite(merged, tmp)

        merged_rgb = merged.convert('RGB')
        r_ch, g_ch, b_ch = merged_rgb.split()

        f.write(struct.pack('>H', 1))            # Compression: RLE

        channels_data = []
        for plane in (r_ch, g_ch, b_ch):
            raw = plane.tobytes()
            bcounts, compressed = compress_channel_rle(raw, canvas_w, canvas_h)
            channels_data.append((bcounts, compressed))

        # Write all row byte counts first (all channels)
        for bcounts, _ in channels_data:
            for bc in bcounts:
                f.write(struct.pack('>H', bc))

        # Write all compressed channel data
        for _, compressed in channels_data:
            f.write(compressed)
