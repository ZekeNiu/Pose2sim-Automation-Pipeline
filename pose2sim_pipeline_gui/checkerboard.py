from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from .paths import GENERATED_CHECKERBOARD_DIR

A4_MM = (210.0, 297.0)


def generate_checkerboard(
    inner_corners: tuple[int, int] = (4, 7),
    square_size_mm: float = 35.0,
    output_dir: Path = GENERATED_CHECKERBOARD_DIR,
    dpi: int = 300,
) -> tuple[Path, Path]:
    """Generate an A4 checkerboard PNG and PDF.

    Pose2Sim's corner count is the number of inner corners. A 4x7 inner-corner
    board therefore has 5x8 squares.
    """

    output_dir.mkdir(parents=True, exist_ok=True)
    rows = inner_corners[0] + 1
    cols = inner_corners[1] + 1
    px_per_mm = dpi / 25.4
    page_w = int(A4_MM[0] * px_per_mm)
    page_h = int(A4_MM[1] * px_per_mm)
    square_px = int(square_size_mm * px_per_mm)
    board_w = cols * square_px
    board_h = rows * square_px
    if board_w > page_w - 80 or board_h > page_h - 160:
        page_w, page_h = page_h, page_w
    if board_w > page_w - 80 or board_h > page_h - 160:
        raise ValueError("棋盘格尺寸超过 A4 页面，请减小方格尺寸或角点数量。")

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

    label = f"Pose2Sim checkerboard | inner corners {inner_corners[0]}x{inner_corners[1]} | square {square_size_mm:g} mm"
    draw.text((80, 60), label, fill="black")
    draw.text((80, page_h - 100), "Print at 100% scale. Measure one square after printing.", fill="black")

    stem = f"checkerboard_{inner_corners[0]}x{inner_corners[1]}_{square_size_mm:g}mm".replace(".", "p")
    png_path = output_dir / f"{stem}.png"
    pdf_path = output_dir / f"{stem}.pdf"
    image.save(png_path, dpi=(dpi, dpi))
    image.save(pdf_path, "PDF", resolution=float(dpi))
    return png_path, pdf_path
