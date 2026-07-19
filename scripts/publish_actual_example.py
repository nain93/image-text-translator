#!/usr/bin/env python3
"""Publish a README-ready input/output pair from an actual pipeline run."""

from __future__ import annotations

import argparse
import csv
import shutil
from pathlib import Path

from PIL import Image

import review_card

CANVAS_SIZE = (1122, 1402)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-csv", type=Path, required=True)
    parser.add_argument("--output-image", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--slots-dir", type=Path, default=Path("slots"))
    return parser.parse_args()


def load_first_row(path: Path) -> dict[str, str]:
    with path.open(encoding="utf-8", newline="") as csv_file:
        row = next(csv.DictReader(csv_file), None)
    if row is None:
        raise ValueError(f"No data rows found in {path}")
    return row


def render_input_preview(row: dict[str, str], slots_dir: Path, destination: Path) -> None:
    spec = review_card.load_spec(row["template"], str(slots_dir))
    rendered_row = dict(row)
    rendered_row["review_text"] = row["review_text_ko"]
    review_card.render_card(spec, rendered_row, str(destination))


def publish_output(source: Path, destination: Path) -> None:
    with Image.open(source) as image:
        if image.size != CANVAS_SIZE:
            raise ValueError(f"Expected {CANVAS_SIZE}, got {image.size}: {source}")
    shutil.copyfile(source, destination)


def main() -> None:
    args = parse_args()
    args.destination.mkdir(parents=True, exist_ok=True)
    row = load_first_row(args.input_csv)
    render_input_preview(
        row,
        args.slots_dir,
        args.destination / "input-korean-review.png",
    )
    publish_output(args.output_image, args.destination / "output-japanese-review.png")


if __name__ == "__main__":
    main()
