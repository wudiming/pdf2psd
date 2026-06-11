"""
生成应用图标 - 输出 icon.png 和 icon.ico
运行: python assets/make_icon.py
"""
from PIL import Image, ImageDraw
import os

def make_icon(size=512):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    s = size

    # 深色圆形背景
    d.ellipse([s*0.02, s*0.02, s*0.98, s*0.98], fill=(18, 22, 38, 255))

    # 蓝色外环
    for i in range(6):
        r = int(s * (0.06 + i * 0.003))
        d.ellipse([r, r, s-r, s-r], outline=(74, 158, 255, 255))

    # === 左侧：PDF 文档图形 ===
    # 文档主体
    doc_x, doc_y = int(s*0.14), int(s*0.18)
    doc_w, doc_h = int(s*0.28), int(s*0.36)
    d.rounded_rectangle(
        [doc_x, doc_y, doc_x+doc_w, doc_y+doc_h],
        radius=int(s*0.025), fill=(255, 255, 255, 220)
    )
    # 折角
    corner = int(s*0.07)
    d.polygon([
        (doc_x+doc_w-corner, doc_y),
        (doc_x+doc_w, doc_y+corner),
        (doc_x+doc_w-corner, doc_y+corner),
    ], fill=(200, 210, 230, 200))
    # PDF 文字横线模拟
    line_color = (74, 158, 255, 255)
    for li, lw in enumerate([0.55, 0.65, 0.73, 0.81]):
        ly = int(doc_y + doc_h * lw)
        lx1 = doc_x + int(doc_w * 0.15)
        lx2 = doc_x + int(doc_w * (0.85 if li % 2 == 0 else 0.65))
        d.rectangle([lx1, ly, lx2, ly + max(2, int(s*0.012))], fill=line_color)
    # "PDF" label
    label_y = int(doc_y + doc_h * 0.28)
    label_x = doc_x + int(doc_w * 0.15)
    lw2 = int(doc_w * 0.55)
    d.rounded_rectangle(
        [label_x, label_y, label_x+lw2, label_y+int(s*0.065)],
        radius=int(s*0.012), fill=(74, 158, 255, 255)
    )

    # === 中间：箭头 ===
    cx = s // 2
    cy = s // 2
    aw = int(s * 0.09)
    ah = int(s * 0.05)
    ap = int(s * 0.04)
    d.polygon([
        (cx - aw, cy - ah//2),
        (cx,      cy - ah//2),
        (cx,      cy - ah//2 - ap),
        (cx + aw, cy),
        (cx,      cy + ah//2 + ap),
        (cx,      cy + ah//2),
        (cx - aw, cy + ah//2),
    ], fill=(74, 158, 255, 255))

    # === 右侧：PSD 图层图形 ===
    psd_x = int(s * 0.58)
    psd_y = int(s * 0.18)
    psd_w = int(s * 0.28)
    psd_h = int(s * 0.36)
    # 三层叠加效果
    for li, (alpha, offset) in enumerate([(120, 12), (180, 6), (255, 0)]):
        ox = int(s * 0.015) * (2 - li)
        oy = int(s * 0.015) * (2 - li)
        d.rounded_rectangle(
            [psd_x + ox, psd_y + oy, psd_x + psd_w - ox, psd_y + psd_h - oy],
            radius=int(s*0.025),
            fill=(74, 158, 255, alpha)
        )
    # "PSD" 白色横条
    for li, lw_r in enumerate([0.55, 0.65, 0.73, 0.81]):
        ly = int(psd_y + psd_h * lw_r)
        lx1 = psd_x + int(psd_w * 0.15)
        lx2 = psd_x + int(psd_w * (0.85 if li % 2 == 0 else 0.65))
        d.rectangle([lx1, ly, lx2, ly + max(2, int(s*0.012))],
                    fill=(255, 255, 255, 200))
    label_y2 = int(psd_y + psd_h * 0.28)
    label_x2 = psd_x + int(psd_w * 0.15)
    d.rounded_rectangle(
        [label_x2, label_y2, label_x2+int(psd_w*0.55), label_y2+int(s*0.065)],
        radius=int(s*0.012), fill=(255, 255, 255, 220)
    )

    return img


if __name__ == "__main__":
    os.makedirs("assets", exist_ok=True)
    icon = make_icon(512)

    # PNG
    icon.save("assets/icon.png")
    print("OK assets/icon.png")

    # ICO (multi-size for Windows)
    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    ico_imgs = [icon.resize(s, Image.LANCZOS) for s in sizes]
    ico_imgs[0].save(
        "assets/icon.ico",
        format="ICO",
        sizes=sizes,
        append_images=ico_imgs[1:],
    )
    print("OK assets/icon.ico")
