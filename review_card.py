#!/usr/bin/env python3
"""CSV → 일본 리뷰 카드 PNG 배치 생성.

완성본 템플릿(image_plate/)의 변수 영역(리뷰 본문·아이디줄·풀쿼트·비포/애프터)을
갈아끼운다. 슬롯 좌표/스타일은 slots/<template>.json 에 정의한다.

사용법:
  python review_card.py --csv reviews.csv --out out/

CSV 열: template, review_text, pull_quote(opt), handle, skin_type, age,
        before_image(opt), after_image(opt), output_name(opt)
  - review_text 안의 줄바꿈은 리터럴 "\\n" 으로 적으면 개행으로 변환된다.
"""
import os
import sys
import csv
import json
import argparse

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import translate_image as ti  # 재사용: sample_colors, weighted_font_path
import jp_layout


def load_spec(template: str, slots_dir: str) -> dict:
    path = os.path.join(slots_dir, template + ".json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _abs(path: str) -> str:
    return path if os.path.isabs(path) else os.path.join(HERE, path)


def slot_text(name: str, slot: dict, row: dict) -> str:
    """슬롯 이름에 해당하는 텍스트를 CSV 행에서 구성한다.

    - id_line: slot["format"](기본 "{handle} / {skin_type} / {age}")로 조립. 2줄 템플릿은
      format에 \\n을 넣으면 됨(예: "{handle}\\n{skin_type} / {age}").
    - review_body: review_text 열을 쓴다.
    - 그 외(headline, pull_quote 등): 슬롯명과 같은 이름의 열을 쓴다.
    """
    if name == "id_line":
        fmt = slot.get("format", "{handle} / {skin_type} / {age}")
        return fmt.format(
            handle=(row.get("handle") or "").strip(),
            skin_type=(row.get("skin_type") or "").strip(),
            age=(row.get("age") or "").strip(),
        ).strip()
    col = {"review_body": "review_text"}.get(name, name)
    return (row.get(col) or "").replace("\\n", "\n")


def erase_fill(canvas, orig, box):
    """박스를 원본 배경색으로 채워 텍스트를 지운다(단색 카드용). 원본 글자색을 반환."""
    fg, bg, _ = ti.sample_colors(orig, box)
    ImageDraw.Draw(canvas).rectangle(list(box), fill=tuple(bg))
    return fg


def paste_photo(canvas, box, photo_path):
    """사진을 박스에 cover-crop(꽉 채우고 넘치는 부분은 가운데 기준 크롭)으로 붙인다."""
    x0, y0, x1, y1 = box
    bw, bh = x1 - x0, y1 - y0
    img = Image.open(_abs(photo_path)).convert("RGB")
    scale = max(bw / img.width, bh / img.height)
    img = img.resize((max(1, round(img.width * scale)), max(1, round(img.height * scale))), Image.LANCZOS)
    left, top = (img.width - bw) // 2, (img.height - bh) // 2
    canvas.paste(img.crop((left, top, left + bw, top + bh)), (x0, y0))


def render_card(spec: dict, row: dict, out_path: str):
    orig = Image.open(_abs(spec["image"])).convert("RGB")
    canvas = orig.copy()
    draw = ImageDraw.Draw(canvas)
    notes = []

    # 텍스트 슬롯 (사진 슬롯 제외) — 슬롯명에 맞는 CSV 값을 구성해 렌더
    for name, slot in spec["slots"].items():
        if name in ("before_image", "after_image"):
            continue
        value = slot_text(name, slot, row)
        if not value.strip():
            continue
        box = tuple(slot["box"])
        fg = erase_fill(canvas, orig, box)  # 현재는 fill만(단색 카드). lama는 추후.
        info = jp_layout.draw_block(
            draw, value, box, ti.weighted_font_path("ja", slot.get("weight", "Regular")),
            target_size=slot.get("font_size", 36), leading=slot.get("leading", 1.5),
            fill=tuple(slot.get("color", fg)),
            align=slot.get("align", "left"), valign=slot.get("valign", "top"),
        )
        notes.append(f"  {name}: size={info['size']} lines={info['lines']}"
                     + ("  ! 오버플로우" if info["overflow"] else ""))

    # 사진 슬롯
    for name in ("before_image", "after_image"):
        slot = spec["slots"].get(name)
        if slot and (row.get(name) or "").strip():
            paste_photo(canvas, tuple(slot["box"]), row[name])
            notes.append(f"  {name}: pasted")

    canvas.save(out_path)
    return notes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--out", default="out")
    ap.add_argument("--slots", default=os.path.join(HERE, "slots"))
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    with open(args.csv, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    for i, row in enumerate(rows):
        template = row.get("template", "").strip()
        if not template:
            print(f"[{i}] template 비어있음 → 건너뜀", file=sys.stderr)
            continue
        spec = load_spec(template, args.slots)
        name = row.get("output_name", "").strip() or f"card_{i:03d}.png"
        out_path = os.path.join(args.out, name)
        print(f"[{i}] {template} → {out_path}")
        for note in render_card(spec, row, out_path):
            print(note)
    print(f"완료 → {args.out}/")


if __name__ == "__main__":
    main()
