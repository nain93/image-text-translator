from localization.contracts import LocalizationConstraints, SourceReview, TextConstraint
from localization.prompts import build_localization_prompt


def test_localization_prompt_contains_source_and_layout_contract() -> None:
    source = SourceReview(review_text_ko="끈적이지 않고 촉촉했어요.")
    constraint = TextConstraint(max_lines=7, max_chars_per_line=24, required=True)
    optional = TextConstraint(max_lines=2, max_chars_per_line=20, required=False)
    constraints = LocalizationConstraints(
        review_body=constraint,
        headline=optional,
        pull_quote=optional,
    )

    prompt = build_localization_prompt(source, constraints)

    assert "끈적이지 않고 촉촉했어요" in prompt
    assert '"max_lines": 7' in prompt
    assert "ja-review-localizer-v1" in prompt
