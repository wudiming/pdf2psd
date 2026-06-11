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
    compression: int = 0,
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

    scale = dpi / 72.0
    matrix = fitz.Matrix(scale, scale)

    images: List[Image.Image] = []
    layer_names: List[str] = []

    for i, page in enumerate(doc):
        report(i, num_pages, f"渲染第 {i + 1} / {num_pages} 页…")

        # alpha=True：保留 PDF 的透明通道，让图层背景透明而非白底
        # 对于有白色页面背景的 PDF，白色区域仍会保留；
        # 对于设计类 PDF（Illustrator/InDesign 导出），背景将透明
        pix = page.get_pixmap(matrix=matrix, alpha=True)
        img = Image.frombytes("RGBA", [pix.width, pix.height], pix.samples)
        images.append(img)
        layer_names.append(f"第 {i + 1} 页")

    doc.close()

    comp_names = {0: "RAW（无压缩）", 1: "RLE"}
    report(num_pages, num_pages,
           f"正在写入 PSD 文件（{comp_names.get(compression, '')} 压缩）…")

    write_psd(output_path, images, layer_names=layer_names,
              dpi=dpi, compression=compression)

    report(num_pages, num_pages, "转换完成！")
