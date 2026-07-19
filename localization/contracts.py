"""LLM 입출력과 애플리케이션 경계에서 사용하는 데이터 계약."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TextConstraint(StrictModel):
    max_lines: int = Field(ge=1, le=12)
    max_chars_per_line: int = Field(ge=4, le=80)
    required: bool


class LocalizationConstraints(StrictModel):
    review_body: TextConstraint
    headline: TextConstraint
    pull_quote: TextConstraint


class SourceReview(StrictModel):
    review_text_ko: str = Field(min_length=1, max_length=2_000)
    headline_ko: str = Field(default="", max_length=300)
    pull_quote_ko: str = Field(default="", max_length=300)
    audience: str = Field(default="20~30대 일본 여성", max_length=200)
    brand_tone: str = Field(default="자연스럽고 구체적인 실제 사용자 후기", max_length=300)


class LocalizedCopy(StrictModel):
    review_lines: list[str] = Field(min_length=1, max_length=12)
    headline_lines: list[str] = Field(max_length=4)
    pull_quote_lines: list[str] = Field(max_length=4)
    preserved_claims: list[str] = Field(max_length=12)
    tone_notes: list[str] = Field(max_length=8)
    warnings: list[str] = Field(max_length=8)

    def review_text(self) -> str:
        return "\n".join(self.review_lines)

    def headline(self) -> str:
        return "\n".join(self.headline_lines)

    def pull_quote(self) -> str:
        return "\n".join(self.pull_quote_lines)


class ReviewIssue(StrictModel):
    severity: Literal["low", "medium", "high"]
    field: Literal["review_body", "headline", "pull_quote", "claim", "tone"]
    problem: str = Field(min_length=1, max_length=500)
    instruction: str = Field(min_length=1, max_length=500)


class LocalizationReview(StrictModel):
    verdict: Literal["pass", "revise"]
    score: int = Field(ge=0, le=100)
    source_fidelity: bool
    naturalness: bool
    constraint_fit: bool
    passed_checks: list[str] = Field(max_length=10)
    issues: list[ReviewIssue] = Field(max_length=10)
