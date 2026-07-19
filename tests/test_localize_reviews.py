from localization.contracts import LocalizedCopy
from localize_reviews import constraints_from_spec, localized_row


def test_constraints_are_derived_from_template_geometry() -> None:
    spec = {
        "slots": {
            "review_body": {
                "box": [0, 0, 600, 420],
                "font_size": 40,
                "leading": 1.5,
            },
            "headline": {
                "box": [0, 0, 400, 120],
                "font_size": 60,
                "leading": 1.0,
            },
        }
    }
    row = {"headline_ko": "제목", "pull_quote_ko": ""}

    constraints = constraints_from_spec(spec, row)

    assert constraints.review_body.max_lines == 7
    assert constraints.review_body.max_chars_per_line == 15
    assert constraints.headline.required is True
    assert constraints.pull_quote.required is False


def test_localized_copy_is_mapped_to_renderer_columns() -> None:
    copy = LocalizedCopy(
        review_lines=["朝の肌が", "変わりました。"],
        headline_lines=["朝の変化"],
        pull_quote_lines=[],
        preserved_claims=[],
        tone_notes=[],
        warnings=[],
    )

    row = localized_row({"template": "customer_review"}, copy)

    assert row["review_text"] == "朝の肌が\\n変わりました。"
    assert row["headline"] == "朝の変化"
