import csv
import json
from pathlib import Path

import pytest

import review_card

ROOT = Path(__file__).resolve().parents[1]


def read_rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def test_all_sample_assets_are_renderable() -> None:
    rows = read_rows(ROOT / "sample_reviews.csv")

    specs = review_card.validate_rows(rows, str(ROOT / "slots"))

    assert len(specs) == 10
    assert all(spec.get("image") for spec in specs)


def test_missing_template_image_is_reported_before_render(tmp_path: Path) -> None:
    slots_dir = tmp_path / "slots"
    slots_dir.mkdir()
    (slots_dir / "broken.json").write_text(
        json.dumps({"image": "missing.png", "slots": {}}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="템플릿 원본 이미지가 없습니다"):
        review_card.validate_rows([{"template": "broken"}], str(slots_dir))
