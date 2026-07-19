from PIL import Image, ImageDraw, ImageFont

import jp_layout


def test_wrap_paragraph_does_not_start_line_with_closing_punctuation() -> None:
    draw = ImageDraw.Draw(Image.new("RGB", (100, 100)))
    font = ImageFont.load_default()
    max_width = draw.textbbox((0, 0), "abc", font=font)[2]

    lines = jp_layout.wrap_paragraph(draw, "abc)def", font, max_width)

    assert all(not line.startswith(")") for line in lines)
