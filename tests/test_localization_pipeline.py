from localization.contracts import (
    LocalizationConstraints,
    LocalizationReview,
    LocalizedCopy,
    ReviewIssue,
    SourceReview,
    TextConstraint,
)
from localization.openai_gateway import CallMetadata, CallResult
from localization.pipeline import LocalizationPipeline


def metadata(version: str) -> CallMetadata:
    return CallMetadata(
        response_id=f"response-{version}",
        model="test-model",
        prompt_version=version,
        input_tokens=10,
        output_tokens=5,
        total_tokens=15,
        latency_ms=100,
    )


def localized(text: str) -> LocalizedCopy:
    return LocalizedCopy(
        review_lines=[text],
        headline_lines=[],
        pull_quote_lines=[],
        preserved_claims=["보습감"],
        tone_notes=["자연스러운 후기체"],
        warnings=[],
    )


def review(verdict: str, score: int) -> LocalizationReview:
    issues = []
    if verdict == "revise":
        issues = [
            ReviewIssue(
                severity="medium",
                field="claim",
                problem="원문보다 효과가 강합니다.",
                instruction="효과 표현을 원문 수준으로 낮추세요.",
            )
        ]
    return LocalizationReview(
        verdict=verdict,
        score=score,
        source_fidelity=verdict == "pass",
        naturalness=True,
        constraint_fit=True,
        passed_checks=["레이아웃 제한"],
        issues=issues,
    )


class FakeGateway:
    def __init__(self, reviews: list[LocalizationReview]) -> None:
        self.reviews = reviews
        self.review_index = 0

    def localize(self, source, constraints):
        return CallResult(localized("保湿感がありました。"), metadata("localize"))

    def review(self, source, constraints, copy):
        result = self.reviews[self.review_index]
        self.review_index += 1
        return CallResult(result, metadata(f"review-{self.review_index}"))

    def revise(self, source, constraints, copy, result):
        return CallResult(localized("しっとり感じました。"), metadata("revise"))


def inputs() -> tuple[SourceReview, LocalizationConstraints]:
    source = SourceReview(review_text_ko="사용 후 촉촉하게 느껴졌어요.")
    constraint = TextConstraint(max_lines=7, max_chars_per_line=24, required=True)
    optional = TextConstraint(max_lines=2, max_chars_per_line=20, required=False)
    constraints = LocalizationConstraints(
        review_body=constraint,
        headline=optional,
        pull_quote=optional,
    )
    return source, constraints


def test_passes_without_revision() -> None:
    source, constraints = inputs()
    pipeline = LocalizationPipeline(FakeGateway([review("pass", 92)]))

    outcome = pipeline.run(source, constraints)

    assert outcome.status == "pass"
    assert outcome.revision_count == 0
    assert outcome.metadata()["api_calls"] == 2
    assert outcome.metadata()["token_usage"]["total"] == 30


def test_revises_once_and_reviews_again() -> None:
    source, constraints = inputs()
    pipeline = LocalizationPipeline(FakeGateway([review("revise", 70), review("pass", 90)]))

    outcome = pipeline.run(source, constraints)

    assert outcome.status == "pass"
    assert outcome.revision_count == 1
    assert outcome.localized.review_text() == "しっとり感じました。"
    assert outcome.metadata()["api_calls"] == 4
