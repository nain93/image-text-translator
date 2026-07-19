"""현지화 → 독립 검수 → 제한된 수정 루프."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Protocol

from localization.contracts import (
    LocalizationConstraints,
    LocalizationReview,
    LocalizedCopy,
    SourceReview,
)
from localization.openai_gateway import CallMetadata, CallResult


class LocalizationGateway(Protocol):
    def localize(
        self,
        source: SourceReview,
        constraints: LocalizationConstraints,
    ) -> CallResult[LocalizedCopy]: ...

    def review(
        self,
        source: SourceReview,
        constraints: LocalizationConstraints,
        localized: LocalizedCopy,
    ) -> CallResult[LocalizationReview]: ...

    def revise(
        self,
        source: SourceReview,
        constraints: LocalizationConstraints,
        localized: LocalizedCopy,
        review: LocalizationReview,
    ) -> CallResult[LocalizedCopy]: ...


@dataclass(frozen=True)
class LocalizationOutcome:
    localized: LocalizedCopy
    review: LocalizationReview
    status: str
    revision_count: int
    calls: list[CallMetadata]

    def metadata(self) -> dict:
        return {
            "status": self.status,
            "revision_count": self.revision_count,
            "api_calls": len(self.calls),
            "token_usage": {
                "input": sum(call.input_tokens for call in self.calls),
                "output": sum(call.output_tokens for call in self.calls),
                "total": sum(call.total_tokens for call in self.calls),
            },
            "latency_ms": sum(call.latency_ms for call in self.calls),
            "calls": [asdict(call) for call in self.calls],
        }


class LocalizationPipeline:
    def __init__(self, gateway: LocalizationGateway, pass_score: int = 85) -> None:
        self.gateway = gateway
        self.pass_score = pass_score

    def run(
        self,
        source: SourceReview,
        constraints: LocalizationConstraints,
    ) -> LocalizationOutcome:
        calls: list[CallMetadata] = []
        localized_call = self.gateway.localize(source, constraints)
        calls.append(localized_call.metadata)
        localized = localized_call.data

        review_call = self.gateway.review(source, constraints, localized)
        calls.append(review_call.metadata)
        review = review_call.data
        revision_count = 0

        if review.verdict == "revise" or review.score < self.pass_score:
            revision_call = self.gateway.revise(source, constraints, localized, review)
            calls.append(revision_call.metadata)
            localized = revision_call.data
            revision_count = 1

            review_call = self.gateway.review(source, constraints, localized)
            calls.append(review_call.metadata)
            review = review_call.data

        status = (
            "pass"
            if review.verdict == "pass" and review.score >= self.pass_score
            else "human_review_required"
        )
        return LocalizationOutcome(
            localized=localized,
            review=review,
            status=status,
            revision_count=revision_count,
            calls=calls,
        )
