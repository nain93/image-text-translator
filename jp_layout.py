"""일본어 다행 텍스트 레이아웃 — 줄바꿈 + 금칙처리(禁則) + 박스 폰트맞춤.

review_card.py 가 텍스트 슬롯을 그릴 때 쓴다. 핵심 규칙:
- 작성자가 넣은 개행(\n)은 의도로 보고 우선 보존한다.
- 한 줄이 박스 폭을 넘으면 글자 단위로 다시 줄바꿈하되, 행두/행말 금칙을 지킨다.
- 글자 크기는 target_size에서 시작해, 전체가 박스 높이에 들어올 때까지 줄인다(오버플로우 방지).
"""

from PIL import ImageDraw, ImageFont

# 행두 금지: 줄 첫 글자로 올 수 없는 문자(앞 줄로 끌어올림)
KINSOKU_START = set(
    "、。，．,.・:：;；?？!！)）]］}｝」』】〉》〕ー…〜～々ぁぃぅぇぉっゃゅょゎ゛゜ヽヾゝゞ♡"
)
# 행말 금지: 줄 끝 글자로 올 수 없는 문자(다음 줄로 내림)
KINSOKU_END = set("(（[［{｛「『【〈《〔")


def _text_w(draw: ImageDraw.ImageDraw, s: str, font: ImageFont.FreeTypeFont) -> int:
    if not s:
        return 0
    left, _, right, _ = draw.textbbox((0, 0), s, font=font)
    return right - left


def wrap_paragraph(draw, text: str, font, max_w: int) -> list[str]:
    """한 단락(작성자 개행 단위)을 폭에 맞게 자르되 금칙처리."""
    lines: list[str] = []
    cur = ""
    for ch in text:
        if not cur or _text_w(draw, cur + ch, font) <= max_w:
            cur += ch
            continue
        # 줄을 바꿔야 하는 시점
        if ch in KINSOKU_START:
            cur += ch  # 행두 금지 문자는 현재 줄에 붙여 넘김(약간 초과 허용)
        elif cur[-1] in KINSOKU_END:
            lines.append(cur[:-1])  # 행말 금지 문자는 다음 줄로 내림
            cur = cur[-1] + ch
        else:
            lines.append(cur)
            cur = ch
    if cur:
        lines.append(cur)
    return lines


def wrap_text(draw, text: str, font, max_w: int) -> list[str]:
    """작성자 개행(\n) 보존 + 각 단락 폭 맞춤 줄바꿈."""
    out: list[str] = []
    for para in text.split("\n"):
        out.extend(wrap_paragraph(draw, para, font, max_w) if para else [""])
    return out


def fit(
    draw,
    text: str,
    box_w: int,
    box_h: int,
    font_path: str,
    target_size: int,
    leading: float,
    min_size: int = 10,
):
    """target_size부터 1px씩 줄여 박스에 들어오는 (font, lines, line_h)를 찾는다.

    작성자 줄바꿈(\n)을 우선 보존한다. 즉 각 작성자 줄이 통째로 폭에 맞도록 폰트를 줄인다
    (고아 줄/어색한 재줄바꿈 방지). 최소 크기에도 폭이 안 맞을 때만 금칙 재줄바꿈으로 폴백.
    """
    author_lines = text.split("\n")
    size = target_size
    while size >= min_size:
        font = ImageFont.truetype(font_path, size)
        line_h = int(round(size * leading))
        widest = max((_text_w(draw, ln, font) for ln in author_lines), default=0)
        if widest <= box_w and line_h * len(author_lines) <= box_h:
            return font, author_lines, line_h
        size -= 1
    # 폴백: 최소 크기에도 한 줄이 폭을 넘으면 폭 기준 재줄바꿈(금칙)
    font = ImageFont.truetype(font_path, min_size)
    return font, wrap_text(draw, text, font, box_w), int(round(min_size * leading))


def draw_block(
    draw,
    text: str,
    box: tuple[int, int, int, int],
    font_path: str,
    target_size: int,
    leading: float,
    fill,
    align: str = "left",
    valign: str = "top",
    stroke_width: int = 0,
    stroke_fill=None,
) -> dict:
    """박스 안에 다행 텍스트를 그린다. 실제 사용한 폰트크기/줄수를 반환(검증·로그용)."""
    x0, y0, x1, y1 = box
    box_w, box_h = x1 - x0, y1 - y0
    font, lines, line_h = fit(draw, text, box_w, box_h, font_path, target_size, leading)
    total_h = line_h * len(lines)
    if valign == "middle":
        cy = y0 + (box_h - total_h) // 2
    elif valign == "bottom":
        cy = y1 - total_h
    else:
        cy = y0
    for i, ln in enumerate(lines):
        ly = cy + i * line_h
        w = _text_w(draw, ln, font)
        if align == "center":
            lx = x0 + (box_w - w) // 2
        elif align == "right":
            lx = x1 - w
        else:
            lx = x0
        draw.text(
            (lx, ly),
            ln,
            font=font,
            fill=fill,
            stroke_width=stroke_width,
            stroke_fill=stroke_fill or fill,
        )
    return {"size": font.size, "lines": len(lines), "overflow": total_h > box_h}
