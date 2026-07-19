#!/usr/bin/env python3
"""
이미지 내 텍스트 언어 변경 파이프라인 (한국어 -> 일본어)
OCR (CLOVA) -> 번역 (Papago) -> 인페인팅 (IOPaint/LaMa) -> 텍스트 재렌더링 (Pillow)

사용법:
  # 키는 .env 파일에 넣어두면 자동 로드된다 (.env.example 복사해서 채우기). 또는 직접 export:
  export CLOVA_OCR_URL="https://..../general"
  export CLOVA_OCR_SECRET="xxxx"
  export PAPAGO_CLIENT_ID="xxxx"
  export PAPAGO_CLIENT_SECRET="xxxx"
  python translate_image.py input.png output.png --src ko --tgt ja
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass

import numpy as np
import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont

# ----------------------------------------------------------------------------
# 설정
# ----------------------------------------------------------------------------
# .env 파일을 자동 로드한다(스크립트와 같은 폴더). 이미 export된 환경변수가 우선한다.
# python-dotenv 미설치 시엔 조용히 건너뛰고 export된 값만 사용한다.
try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
except ImportError:
    pass

CLOVA_OCR_URL = os.environ.get("CLOVA_OCR_URL", "")
CLOVA_OCR_SECRET = os.environ.get("CLOVA_OCR_SECRET", "")
PAPAGO_CLIENT_ID = os.environ.get("PAPAGO_CLIENT_ID", "")
PAPAGO_CLIENT_SECRET = os.environ.get("PAPAGO_CLIENT_SECRET", "")

# 타깃 언어 폰트. 시스템에 맞게 경로 수정.
# Noto Sans CJK JP 는 일본어·한국어·라틴 글리프를 모두 포함하므로 ja/ko/en 공용으로 쓴다.
# 설치: brew install --cask font-noto-sans-cjk-jp  (-> ~/Library/Fonts/)
_NOTO_CJK = os.path.expanduser("~/Library/Fonts/NotoSansCJKjp-Regular.otf")
FONT_PATHS = {
    "ja": _NOTO_CJK,
    "ko": _NOTO_CJK,
    "en": _NOTO_CJK,
}

# 굵기별 폰트 (원본 글자 굵기에 맞춰 자동 선택). 파일 없으면 Regular로 폴백.
_FONT_DIR = os.path.expanduser("~/Library/Fonts")
_FONT_WEIGHTS = {
    "Thin": "NotoSansCJKjp-Thin.otf",
    "Light": "NotoSansCJKjp-Light.otf",
    "Regular": "NotoSansCJKjp-Regular.otf",
    "Medium": "NotoSansCJKjp-Medium.otf",
    "Bold": "NotoSansCJKjp-Bold.otf",
    "Black": "NotoSansCJKjp-Black.otf",
}


def weighted_font_path(tgt: str, weight: str) -> str:
    """굵기 이름에 해당하는 폰트 경로. 파일이 없으면 언어 기본(Regular)으로 폴백."""
    fn = _FONT_WEIGHTS.get(weight)
    if fn:
        p = os.path.join(_FONT_DIR, fn)
        if os.path.exists(p):
            return p
    return FONT_PATHS.get(tgt, FONT_PATHS["ja"])


@dataclass
class TextBox:
    text: str
    # 사각형 박스: (x0, y0, x1, y1)
    bbox: tuple[int, int, int, int]
    translated: str = ""


# ----------------------------------------------------------------------------
# 1. OCR — 네이버 CLOVA OCR
# ----------------------------------------------------------------------------
def clova_ocr(image_path: str) -> list[TextBox]:
    """CLOVA OCR로 텍스트와 박스 좌표를 추출한다."""
    with open(image_path, "rb") as f:
        img_bytes = f.read()
    ext = os.path.splitext(image_path)[1].lstrip(".").lower() or "png"

    payload = {
        "version": "V2",
        "requestId": str(uuid.uuid4()),
        "timestamp": int(time.time() * 1000),
        "images": [{"format": ext, "name": "demo"}],
    }
    files = [("file", img_bytes)]
    headers = {
        "X-OCR-SECRET": CLOVA_OCR_SECRET,
    }
    data = {"message": json.dumps(payload)}

    resp = requests.post(CLOVA_OCR_URL, headers=headers, data=data, files=files, timeout=30)
    resp.raise_for_status()
    result = resp.json()

    boxes: list[TextBox] = []
    for field_ in result["images"][0]["fields"]:
        text = field_["inferText"]
        pts = field_["boundingPoly"]["vertices"]
        xs = [p["x"] for p in pts]
        ys = [p["y"] for p in pts]
        bbox = (int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys)))
        boxes.append(TextBox(text=text, bbox=bbox))
    return boxes


def group_into_lines(boxes: list[TextBox], y_tol: int = 12) -> list[TextBox]:
    """가까운 단어 박스를 한 줄로 묶어 자연스러운 번역 단위로 만든다."""
    if not boxes:
        return []
    boxes = sorted(boxes, key=lambda b: (b.bbox[1], b.bbox[0]))
    lines: list[list[TextBox]] = []
    for b in boxes:
        placed = False
        cy = (b.bbox[1] + b.bbox[3]) / 2
        for line in lines:
            ly = (line[0].bbox[1] + line[0].bbox[3]) / 2
            if abs(cy - ly) <= y_tol:
                line.append(b)
                placed = True
                break
        if not placed:
            lines.append([b])

    merged: list[TextBox] = []
    for line in lines:
        line = sorted(line, key=lambda b: b.bbox[0])
        text = " ".join(b.text for b in line)
        x0 = min(b.bbox[0] for b in line)
        y0 = min(b.bbox[1] for b in line)
        x1 = max(b.bbox[2] for b in line)
        y1 = max(b.bbox[3] for b in line)
        merged.append(TextBox(text=text, bbox=(x0, y0, x1, y1)))
    return merged


# ----------------------------------------------------------------------------
# 2. 번역 — 네이버 Papago
# ----------------------------------------------------------------------------
def papago_translate(text: str, src: str = "ko", tgt: str = "ja") -> str:
    if not text.strip():
        return text
    url = "https://papago.apigw.ntruss.com/nmt/v1/translation"
    headers = {
        "X-NCP-APIGW-API-KEY-ID": PAPAGO_CLIENT_ID,
        "X-NCP-APIGW-API-KEY": PAPAGO_CLIENT_SECRET,
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {"source": src, "target": tgt, "text": text}
    resp = requests.post(url, headers=headers, data=data, timeout=15)
    resp.raise_for_status()
    return resp.json()["message"]["result"]["translatedText"]


# ----------------------------------------------------------------------------
# 3. 인페인팅 — IOPaint (LaMa)
# ----------------------------------------------------------------------------
def build_mask(size: tuple[int, int], boxes: list[TextBox], pad: int = 3) -> Image.Image:
    """텍스트 영역을 흰색으로 칠한 마스크 생성 (LaMa는 흰색=제거 영역)."""
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    for b in boxes:
        x0, y0, x1, y1 = b.bbox
        draw.rectangle([x0 - pad, y0 - pad, x1 + pad, y1 + pad], fill=255)
    return mask


def inpaint_lama(image_path: str, mask: Image.Image) -> Image.Image:
    """IOPaint(LaMa) 배치 실행으로 원본 텍스트를 지운 깨끗한 배경을 만든다."""
    with tempfile.TemporaryDirectory() as tmp:
        img_dir = os.path.join(tmp, "img")
        mask_dir = os.path.join(tmp, "mask")
        out_dir = os.path.join(tmp, "out")
        os.makedirs(img_dir)
        os.makedirs(mask_dir)
        os.makedirs(out_dir)

        name = "frame.png"
        Image.open(image_path).convert("RGB").save(os.path.join(img_dir, name))
        mask.save(os.path.join(mask_dir, name))

        cmd = [
            "iopaint",
            "run",
            "--model=lama",
            "--device=cpu",  # GPU 사용 시 cuda
            f"--image={img_dir}",
            f"--mask={mask_dir}",
            f"--output={out_dir}",
        ]
        subprocess.run(cmd, check=True)
        return Image.open(os.path.join(out_dir, name)).convert("RGB")


# ----------------------------------------------------------------------------
# 4. 텍스트 재렌더링 — Pillow
# ----------------------------------------------------------------------------
def sample_colors(orig: Image.Image, bbox: tuple[int, int, int, int]):
    """박스에서 (글자색, 배경색, 글자비율)을 추정한다.

    배경색 = 박스 테두리 픽셀의 중앙값(테두리는 대부분 배경).
    글자색 = 배경과 색 거리가 가장 먼 상위 픽셀의 중앙값.
    이렇게 하면 '밝은 배경+어두운 글자'와 '어두운 배경+밝은(네온) 글자' 모두 올바른 글자색을 얻는다.
    """
    x0, y0, x1, y1 = bbox
    crop = np.asarray(orig.convert("RGB").crop((x0, y0, x1, y1))).astype(np.float32)
    if crop.size == 0:
        return (0, 0, 0), (255, 255, 255), 0.0
    h, w = crop.shape[:2]
    border = np.concatenate([crop[0], crop[h - 1], crop[:, 0], crop[:, w - 1]], axis=0)
    bg = np.median(border, axis=0)
    flat = crop.reshape(-1, 3)
    dist = np.linalg.norm(flat - bg, axis=1)
    k = max(1, int(len(flat) * 0.12))
    fg = np.median(flat[np.argsort(dist)[-k:]], axis=0)
    # 글자 비율(볼드 추정용): 배경과 충분히 다른 픽셀 비율
    thr = max(40.0, float(dist.max()) * 0.35)
    fg_ratio = float((dist > thr).mean())
    return tuple(int(c) for c in fg), tuple(int(c) for c in bg), fg_ratio


def weight_for_ratio(r: float) -> str:
    """글자 비율로 폰트 굵기를 고른다 (두꺼운 글자일수록 무거운 weight)."""
    if r >= 0.28:
        return "Black"
    if r >= 0.20:
        return "Bold"
    if r >= 0.13:
        return "Medium"
    return "Regular"


def fit_font(text: str, box_w: int, box_h: int, font_path: str) -> ImageFont.FreeTypeFont:
    """박스에 맞는 최대 폰트 크기를 이진 탐색으로 찾는다."""
    lo, hi = 6, box_h + 4
    best = ImageFont.truetype(font_path, lo)
    dummy = Image.new("RGB", (10, 10))
    d = ImageDraw.Draw(dummy)
    while lo <= hi:
        mid = (lo + hi) // 2
        font = ImageFont.truetype(font_path, mid)
        left, top, right, bottom = d.textbbox((0, 0), text, font=font)
        if (right - left) <= box_w and (bottom - top) <= box_h:
            best = font
            lo = mid + 1
        else:
            hi = mid - 1
    return best


def render_text(
    canvas: Image.Image, orig: Image.Image, boxes: list[TextBox], tgt: str
) -> Image.Image:
    """번역문을 원본 글자색·굵기에 맞춰 다시 그린다.

    - 글자색/배경색을 추정해 대비가 유지되도록 칠한다.
    - 어두운 배경의 밝은 글자(네온풍)는 글로우(번진 후광)를 더해 원본 느낌을 살린다.
    - 모든 글자에 배경색 외곽선(stroke)을 둘러 복잡한 배경에서도 또렷하게 보이게 한다.
    """
    canvas = canvas.convert("RGB")
    glow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)

    plan = []
    has_glow = False
    for b in boxes:
        if not b.translated.strip():
            continue
        x0, y0, x1, y1 = b.bbox
        box_w, box_h = x1 - x0, y1 - y0
        if box_w <= 1 or box_h <= 1:
            continue
        fg, bg, ratio = sample_colors(orig, b.bbox)
        font = fit_font(
            b.translated, box_w, box_h, weighted_font_path(tgt, weight_for_ratio(ratio))
        )
        left, top, right, bottom = glow_draw.textbbox((0, 0), b.translated, font=font)
        tx = x0 + (box_w - (right - left)) // 2 - left
        ty = y0 + (box_h - (bottom - top)) // 2 - top
        # 어두운 배경 + 밝은 글자 = 네온풍 → 글로우 대상
        neon = (sum(bg) / 3 < 110) and (sum(fg) / 3 > 140)
        stroke_w = max(1, font.size // 22)
        plan.append((b.translated, font, fg, bg, tx, ty, stroke_w))
        if neon:
            has_glow = True
            glow_draw.text((tx, ty), b.translated, font=font, fill=fg + (255,))

    if has_glow:
        glow = glow.filter(ImageFilter.GaussianBlur(7))
        canvas = Image.alpha_composite(canvas.convert("RGBA"), glow).convert("RGB")

    draw = ImageDraw.Draw(canvas)
    for text, font, fg, bg, tx, ty, stroke_w in plan:
        draw.text((tx, ty), text, font=font, fill=fg, stroke_width=stroke_w, stroke_fill=bg)
    return canvas


# ----------------------------------------------------------------------------
# 메인 파이프라인
# ----------------------------------------------------------------------------
def run(input_path: str, output_path: str, src: str, tgt: str):
    print(f"[1/4] OCR: {input_path}")
    raw_boxes = clova_ocr(input_path)
    boxes = group_into_lines(raw_boxes)
    print(f"      {len(raw_boxes)}개 단어 -> {len(boxes)}개 줄")

    print("[2/4] 번역")
    for b in boxes:
        b.translated = papago_translate(b.text, src=src, tgt=tgt)
        print(f"      {b.text!r} -> {b.translated!r}")

    print("[3/4] 인페인팅 (LaMa)")
    orig = Image.open(input_path).convert("RGB")
    mask = build_mask(orig.size, boxes)
    clean = inpaint_lama(input_path, mask)

    print("[4/4] 텍스트 재렌더링")
    result = render_text(clean, orig, boxes, tgt)
    result.save(output_path)
    print(f"완료 -> {output_path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--src", default="ko")
    ap.add_argument("--tgt", default="ja")
    args = ap.parse_args()

    for key, val in {
        "CLOVA_OCR_URL": CLOVA_OCR_URL,
        "CLOVA_OCR_SECRET": CLOVA_OCR_SECRET,
        "PAPAGO_CLIENT_ID": PAPAGO_CLIENT_ID,
        "PAPAGO_CLIENT_SECRET": PAPAGO_CLIENT_SECRET,
    }.items():
        if not val:
            print(f"경고: 환경변수 {key} 가 비어 있습니다.", file=sys.stderr)

    run(args.input, args.output, args.src, args.tgt)
