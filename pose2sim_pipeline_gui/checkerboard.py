from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from .paths import GENERATED_CHECKERBOARD_DIR

PAGE_SIZES_MM = {
    "A4": (210.0, 297.0),
    "A3": (297.0, 420.0),
}


def generate_checkerboard(
    inner_corners: tuple[int, int] = (4, 7),
    square_size_mm: float = 35.0,
    output_dir: Path = GENERATED_CHECKERBOARD_DIR,
    dpi: int = 300,
    page_size: str = "A4",
    purpose: str = "checkerboard",
) -> tuple[Path, Path]:
    """Generate a checkerboard PNG and PDF.

    Pose2Sim's corner count is the number of inner corners. A 4x7 inner-corner
    board therefore has 5x8 squares.
    """

    output_dir.mkdir(parents=True, exist_ok=True)
    page_key = page_size.upper()
    if page_key not in PAGE_SIZES_MM:
        raise ValueError(f"不支持的纸张尺寸: {page_size}")
    rows = inner_corners[0] + 1
    cols = inner_corners[1] + 1
    px_per_mm = dpi / 25.4
    page_w = int(PAGE_SIZES_MM[page_key][0] * px_per_mm)
    page_h = int(PAGE_SIZES_MM[page_key][1] * px_per_mm)
    square_px = int(square_size_mm * px_per_mm)
    board_w = cols * square_px
    board_h = rows * square_px
    if board_w > page_w - 80 or board_h > page_h - 160:
        page_w, page_h = page_h, page_w
    if board_w > page_w - 80 or board_h > page_h - 160:
        raise ValueError(f"棋盘格尺寸超过 {page_key} 页面，请减小方格尺寸或角点数量。")

    image = Image.new("RGB", (page_w, page_h), "white")
    draw = ImageDraw.Draw(image)
    x0 = (page_w - board_w) // 2
    y0 = (page_h - board_h) // 2
    for row in range(rows):
        for col in range(cols):
            color = "black" if (row + col) % 2 == 0 else "white"
            x1 = x0 + col * square_px
            y1 = y0 + row * square_px
            draw.rectangle([x1, y1, x1 + square_px, y1 + square_px], fill=color)

    label = (
        f"Pose2Sim {purpose} | {page_key} | inner corners {inner_corners[0]}x{inner_corners[1]} "
        f"| square {square_size_mm:g} mm"
    )
    draw.text((80, 60), label, fill="black")
    draw.text((80, page_h - 100), "Print at 100% scale. Measure one square after printing.", fill="black")
    scale_len = int(100 * px_per_mm)
    scale_y = page_h - 55
    scale_x = 80
    draw.line([(scale_x, scale_y), (scale_x + scale_len, scale_y)], fill="black", width=max(3, int(px_per_mm)))
    draw.line([(scale_x, scale_y - 18), (scale_x, scale_y + 18)], fill="black", width=max(2, int(px_per_mm / 2)))
    draw.line(
        [(scale_x + scale_len, scale_y - 18), (scale_x + scale_len, scale_y + 18)],
        fill="black",
        width=max(2, int(px_per_mm / 2)),
    )
    draw.text((scale_x, scale_y + 24), "100 mm check ruler", fill="black")

    safe_purpose = "".join(ch if ch.isalnum() else "_" for ch in purpose).strip("_") or "checkerboard"
    stem = f"{safe_purpose}_{page_key}_{inner_corners[0]}x{inner_corners[1]}_{square_size_mm:g}mm".replace(".", "p")
    png_path = output_dir / f"{stem}.png"
    pdf_path = output_dir / f"{stem}.pdf"
    image.save(png_path, dpi=(dpi, dpi))
    image.save(pdf_path, "PDF", resolution=float(dpi))
    return png_path, pdf_path
