#!/usr/bin/env python3
"""Publish a README-ready input/output pair from an actual pipeline run."""

from __future__ import annotations

import argparse
import csv
import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from translate_image import weighted_font_path

CANVAS_SIZE = (1122, 1402)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-csv", type=Path, required=True)
    parser.add_argument("--output-image", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    return parser.parse_args()


def load_first_row(path: Path) -> dict[str, str]:
    with path.open(encoding="utf-8", newline="") as csv_file:
        row = next(csv.DictReader(csv_file), None)
    if row is None:
        raise ValueError(f"No data rows found in {path}")
    return row


def font(weight: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(weighted_font_path("ko", weight), size)


def render_input_preview(row: dict[str, str], destination: Path) -> None:
    image = Image.new("RGB", CANVAS_SIZE, "#F4F1EA")
    draw = ImageDraw.Draw(image)

    draw.rounded_rectangle((72, 72, 354, 134), radius=31, fill="#171717")
    draw.text((102, 84), "ACTUAL INPUT", font=font("Bold", 30), fill="white")
    draw.text((72, 184), "한국어 리뷰 CSV", font=font("Bold", 62), fill="#171717")
    draw.text(
        (72, 266),
        "sample_reviews_ko.csv · 첫 번째 행",
        font=font("Regular", 30),
        fill="#66615A",
    )

    draw.rounded_rectangle((72, 340, 1050, 1070), radius=34, fill="white")
    draw.text((120, 392), "review_text_ko", font=font("Bold", 28), fill="#E35D2F")

    y = 462
    review = row["review_text_ko"].replace("\\n", "\n")
    for line in review.splitlines():
        draw.text((120, y), line, font=font("Medium", 43), fill="#24211E")
        y += 75

    draw.line((120, 1004, 1002, 1004), fill="#E4DED4", width=2)
    metadata = f'{row["handle"]}  ·  {row["skin_type"]}  ·  {row["age"]}'
    draw.text((120, 1020), metadata, font=font("Regular", 27), fill="#726C64")

    draw.text((72, 1146), "audience", font=font("Bold", 25), fill="#726C64")
    draw.text((72, 1190), row["audience"], font=font("Medium", 31), fill="#24211E")
    draw.text((72, 1260), "brand_tone", font=font("Bold", 25), fill="#726C64")
    draw.text((72, 1304), row["brand_tone"], font=font("Medium", 31), fill="#24211E")

    image.save(destination, optimize=True)


def publish_output(source: Path, destination: Path) -> None:
    with Image.open(source) as image:
        if image.size != CANVAS_SIZE:
            raise ValueError(f"Expected {CANVAS_SIZE}, got {image.size}: {source}")
    shutil.copyfile(source, destination)


def main() -> None:
    args = parse_args()
    args.destination.mkdir(parents=True, exist_ok=True)
    row = load_first_row(args.input_csv)
    render_input_preview(row, args.destination / "input-korean-review.png")
    publish_output(args.output_image, args.destination / "output-japanese-review.png")


if __name__ == "__main__":
    main()
