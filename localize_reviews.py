#!/usr/bin/env python3
"""한국어 리뷰 CSV → LLM 현지화 → 검수 메타데이터 → 일본어 리뷰 카드."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv

import review_card
from localization.contracts import (
    LocalizationConstraints,
    LocalizedCopy,
    SourceReview,
    TextConstraint,
)
from localization.openai_gateway import OpenAILocalizationGateway
from localization.pipeline import LocalizationOutcome, LocalizationPipeline

HERE = Path(__file__).resolve().parent


def text_constraint(slot: dict | None, required: bool) -> TextConstraint:
    if not slot:
        return TextConstraint(max_lines=1, max_chars_per_line=20, required=False)

    x0, y0, x1, y1 = slot["box"]
    width = x1 - x0
    height = y1 - y0
    font_size = int(slot.get("font_size", 36))
    leading = float(slot.get("leading", 1.5))
    max_lines = max(1, min(12, int(height / max(1, font_size * leading))))
    max_chars = max(4, min(80, int(width / max(1, font_size))))
    return TextConstraint(
        max_lines=max_lines,
        max_chars_per_line=max_chars,
        required=required,
    )


def constraints_from_spec(spec: dict, row: dict) -> LocalizationConstraints:
    slots = spec["slots"]
    return LocalizationConstraints(
        review_body=text_constraint(slots.get("review_body"), required=True),
        headline=text_constraint(
            slots.get("headline"),
            required=bool((row.get("headline_ko") or "").strip()),
        ),
        pull_quote=text_constraint(
            slots.get("pull_quote"),
            required=bool((row.get("pull_quote_ko") or "").strip()),
        ),
    )


def source_from_row(row: dict) -> SourceReview:
    return SourceReview(
        review_text_ko=(row.get("review_text_ko") or "").replace("\\n", "\n").strip(),
        headline_ko=(row.get("headline_ko") or "").replace("\\n", "\n").strip(),
        pull_quote_ko=(row.get("pull_quote_ko") or "").replace("\\n", "\n").strip(),
        audience=(row.get("audience") or "20~30대 일본 여성").strip(),
        brand_tone=(row.get("brand_tone") or "자연스럽고 구체적인 실제 사용자 후기").strip(),
    )


def localized_row(row: dict, copy: LocalizedCopy) -> dict:
    output = dict(row)
    output["review_text"] = copy.review_text().replace("\n", "\\n")
    output["headline"] = copy.headline().replace("\n", "\\n")
    output["pull_quote"] = copy.pull_quote().replace("\n", "\\n")
    return output


def source_hash(source: SourceReview) -> str:
    payload = source.model_dump_json().encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def write_csv(path: Path, rows: list[dict]) -> None:
    fields: list[str] = []
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def result_metadata(
    index: int,
    row: dict,
    source: SourceReview,
    constraints: LocalizationConstraints,
    outcome: LocalizationOutcome,
) -> dict:
    return {
        "index": index,
        "template": row["template"],
        "output_name": row.get("output_name", ""),
        "source_hash": source_hash(source),
        "constraints": constraints.model_dump(),
        "localized": outcome.localized.model_dump(),
        "review": outcome.review.model_dump(),
        "execution": outcome.metadata(),
    }


def default_output_dir() -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return HERE / "artifacts" / timestamp


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True, help="한국어 원문 CSV")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--slots", default=str(HERE / "slots"))
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--render", action="store_true")
    parser.add_argument("--env-file", type=Path, default=None)
    args = parser.parse_args()

    if args.env_file:
        load_dotenv(args.env_file, override=False)

    with open(args.csv, encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    if args.limit is not None:
        rows = rows[: args.limit]
    if not rows:
        print("처리할 CSV 행이 없습니다.")
        return 2

    specs = review_card.validate_rows(rows, args.slots)
    output_dir = args.out or default_output_dir()
    images_dir = output_dir / "images"
    output_dir.mkdir(parents=True, exist_ok=False)
    if args.render:
        images_dir.mkdir()

    pipeline = LocalizationPipeline(OpenAILocalizationGateway())
    localized_rows: list[dict] = []
    metadata_rows: list[dict] = []
    review_required = 0

    for index, (row, spec) in enumerate(zip(rows, specs)):
        source = source_from_row(row)
        constraints = constraints_from_spec(spec, row)
        print(f"[{index + 1}/{len(rows)}] {row['template']} 현지화·검수")
        outcome = pipeline.run(source, constraints)
        rendered_row = localized_row(row, outcome.localized)
        localized_rows.append(rendered_row)
        metadata_rows.append(result_metadata(index, row, source, constraints, outcome))

        if outcome.status != "pass":
            review_required += 1
            print(f"  검수 상태: {outcome.status} ({outcome.review.score}점)")
            continue

        if args.render:
            name = (row.get("output_name") or f"card_{index:03d}.png").strip()
            review_card.render_card(spec, rendered_row, str(images_dir / name))
            print(f"  렌더 완료: images/{name}")

    write_csv(output_dir / "localized.csv", localized_rows)
    summary = {
        "schema_version": "1.0",
        "pipeline": "openai-localize-review-render",
        "generated_at": datetime.now(UTC).isoformat(),
        "source_csv": Path(args.csv).name,
        "rows": len(rows),
        "pass": len(rows) - review_required,
        "human_review_required": review_required,
        "results": metadata_rows,
    }
    (output_dir / "localization.meta.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"완료: {output_dir}")
    return 3 if review_required else 0


if __name__ == "__main__":
    raise SystemExit(main())
