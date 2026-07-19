#!/usr/bin/env python3
"""일본 리뷰 카드 QA — 기계적 검수.

언어 품질과 원문 충실도는 LLM Reviewer가 검수한다.
이 모듈은 객관적으로 잴 수 있는 레이아웃만 점검한다:
슬롯에 텍스트가 깨끗이 들어가는가 — 폰트 축소량 / 줄 수 / 오버플로우 / 자동 재줄바꿈(고아줄 위험).

사용법:
  python qa.py --csv reviews.csv
"""

import argparse
import csv
import json
import os

from PIL import Image, ImageDraw

import jp_layout
import translate_image as ti

HERE = os.path.dirname(os.path.abspath(__file__))


def _dummy_draw():
    return ImageDraw.Draw(Image.new("RGB", (10, 10)))


def check_slot(draw, text: str, slot: dict) -> dict:
    """슬롯에 text를 넣을 때의 레이아웃 결과(축소·줄수·오버플로우)를 계산."""
    x0, y0, x1, y1 = slot["box"]
    bw, bh = x1 - x0, y1 - y0
    target = slot.get("font_size", 36)
    leading = slot.get("leading", 1.5)
    font_path = ti.weighted_font_path("ja", slot.get("weight", "Regular"))
    font, lines, line_h = jp_layout.fit(draw, text, bw, bh, font_path, target, leading)
    return {
        "target": target,
        "final": font.size,
        "lines": len(lines),
        "author_lines": len(text.split("\n")),
        "rewrapped": len(lines) > len(text.split("\n")),
        "overflow": line_h * len(lines) > bh,
    }


def warnings_for(name: str, r: dict):
    out = []
    if r["overflow"]:
        out.append(f"  ⛔ {name}: 박스에 안 들어감(최소 크기에도 초과). 문장을 줄이세요.")
    if r["rewrapped"]:
        out.append(f"  ⚠ {name}: 폭 초과로 자동 재줄바꿈 발생(고아줄 위험). 작성자 줄을 더 짧게.")
    if r["final"] < r["target"] * 0.85 and not r["overflow"]:
        message = (
            f"  ⚠ {name}: 글자가 {r['final']}px로 축소됨"
            f"(디자인 {r['target']}px). 줄을 짧게/적게 하면 커집니다."
        )
        out.append(message)
    return out


def run_qa(csv_path: str, slots_dir: str):
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    draw = _dummy_draw()
    flagged = 0
    for i, row in enumerate(rows):
        template = (row.get("template") or "").strip()
        spec_path = os.path.join(slots_dir, template + ".json")
        if not template or not os.path.exists(spec_path):
            print(f"[{i}] 템플릿 스펙 없음: {template!r}")
            continue
        slots = json.load(open(spec_path, encoding="utf-8"))["slots"]
        print(f"\n[{i}] {template}  ({row.get('output_name', '')})")
        texts = {
            "review_body": (row.get("review_text") or "").replace("\\n", "\n"),
            "headline": (row.get("headline") or "").replace("\\n", "\n"),
            "pull_quote": (row.get("pull_quote") or "").replace("\\n", "\n"),
        }
        warned = False
        for name, text in texts.items():
            if name in slots and text.strip():
                r = check_slot(draw, text, slots[name])
                print(f"  {name}: {r['final']}px / {r['lines']}줄 (작성자 {r['author_lines']}줄)")
                for w in warnings_for(name, r):
                    print(w)
                    warned = True
        body = texts["review_body"]
        if body.strip():
            print("  ── 본문(줄별, 언어검수용) ──")
            for ln in body.split("\n"):
                print(f"    | {ln}")
        if warned:
            flagged += 1
        else:
            print("  ✓ 기계적 검수 통과")
    print(f"\n총 {len(rows)}건 중 기계적 경고 {flagged}건.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--slots", default=os.path.join(HERE, "slots"))
    args = ap.parse_args()
    run_qa(args.csv, args.slots)
