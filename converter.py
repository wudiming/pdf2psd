"""
PDF → PSD conversion logic.
Uses PyMuPDF to render PDF pages and psd_writer to produce the PSD file.
"""

import os
import fitz  # PyMuPDF
from PIL import Image
from typing import Callable, List, Optional
from psd_writer import write_psd


def get_pdf_info(pdf_path: str) -> dict:
    """Return basic info about a PDF file."""
    doc = fitz.open(pdf_path)
    info = {
        'page_count': len(doc),
        'title': doc.metadata.get('title', ''),
        'author': doc.metadata.get('author', ''),
    }
    # Get first page size in points
    if len(doc) > 0:
        page = doc[0]
        info['width_pt'] = page.rect.width
        info['height_pt'] = page.rect.height
    doc.close()
    return info


def convert_pdf_to_psd(
    pdf_path: str,
    output_path: str,
    dpi: int = 150,
    compression: int = 1,
    total_pages: int | None = None,
    reverse_order: bool = True,
    add_white_layer: bool = True,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> None:
    """
    Convert a multi-page PDF into a single layered PSD file.

    Args:
        pdf_path         : Path to the input PDF.
        output_path      : Destination .psd file path.
        dpi              : Render resolution (72–300 recommended).
        compression      : 0=RAW (fastest write), 1=RLE (smallest file).
        progress_callback: Optional fn(current, total, message) for UI updates.
    """
    def report(current: int, total: int, msg: str) -> None:
        if progress_callback:
            progress_callback(current, total, msg)

    report(0, 1, "正在打开 PDF…")

    doc = fitz.open(pdf_path)
    num_pages = len(doc)

    if num_pages == 0:
        raise ValueError("PDF 文件没有页面")

    # Clamp to user-specified page count if provided
    if total_pages is not None and 0 < total_pages < num_pages:
        num_pages = total_pages

    scale = dpi / 72.0
    matrix = fitz.Matrix(scale, scale)

    page_indices = list(range(num_pages))  # 0-based
    if reverse_order:
        page_indices = list(reversed(page_indices))  # N-1 → 0，这样 PSD 中第 1 页在最上面

    images: List[Image.Image] = []
    layer_names: List[str] = []

    for order_idx, page_idx in enumerate(page_indices):
        report(order_idx, num_pages, f"渲染第 {page_idx + 1} / {len(doc)} 页…")

        # alpha=True：保留 PDF 的透明通道，让图层背景透明而非白底
        pix = doc[page_idx].get_pixmap(matrix=matrix, alpha=True)
        img = Image.frombytes("RGBA", [pix.width, pix.height], pix.samples)
        images.append(img)
        layer_names.append(f"第 {page_idx + 1} 页")

    doc.close()

    # 白色底层：与第一页大小相同，纯白 RGBA
    if add_white_layer and images:
        w, h = images[0].size
        white_img = Image.new("RGBA", (w, h), (255, 255, 255, 255))
        images.append(white_img)
        layer_names.append("第 0 页")

    comp_names = {0: "RAW（无压缩）", 1: "RLE"}
    report(num_pages, num_pages,
           f"正在写入 PSD 文件（{comp_names.get(compression, '')} 压缩）…")

    write_psd(output_path, images, layer_names=layer_names,
              dpi=dpi, compression=compression)

    report(num_pages, num_pages, "转换完成！")
