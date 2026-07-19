"""OpenAI Responses API를 사용하는 현지화 게이트웨이."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Generic, Literal, TypeVar

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel

from localization.contracts import (
    LocalizationConstraints,
    LocalizationReview,
    LocalizedCopy,
    SourceReview,
)
from localization.prompts import (
    LOCALIZER_INSTRUCTIONS,
    LOCALIZER_PROMPT_VERSION,
    REVIEWER_INSTRUCTIONS,
    REVIEWER_PROMPT_VERSION,
    REVISION_PROMPT_VERSION,
    build_localization_prompt,
    build_review_prompt,
    build_revision_prompt,
)

load_dotenv()

T = TypeVar("T", bound=BaseModel)
ReasoningEffort = Literal["none", "low", "medium", "high", "xhigh", "max"]


@dataclass(frozen=True)
class CallMetadata:
    response_id: str
    model: str
    prompt_version: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    latency_ms: int


@dataclass(frozen=True)
class CallResult(Generic[T]):
    data: T
    metadata: CallMetadata


class OpenAILocalizationGateway:
    def __init__(
        self,
        client: OpenAI | None = None,
        model: str | None = None,
        reasoning_effort: ReasoningEffort | None = None,
    ) -> None:
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if client is None and not api_key:
            raise ValueError("OPENAI_API_KEY가 설정되지 않았습니다.")
        self.client = client or OpenAI(api_key=api_key)
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-5.6-sol")
        self.reasoning_effort = reasoning_effort or self._reasoning_effort_from_env()

    @staticmethod
    def _reasoning_effort_from_env() -> ReasoningEffort:
        value = os.getenv("OPENAI_REASONING_EFFORT", "medium").strip().lower()
        allowed = {"none", "low", "medium", "high", "xhigh", "max"}
        if value not in allowed:
            raise ValueError(f"지원하지 않는 OPENAI_REASONING_EFFORT입니다: {value}")
        return value  # type: ignore[return-value]

    def _parse(
        self,
        *,
        schema: type[T],
        instructions: str,
        prompt: str,
        prompt_version: str,
    ) -> CallResult[T]:
        started_at = time.perf_counter()
        response = self.client.responses.parse(
            model=self.model,
            instructions=instructions,
            input=prompt,
            text_format=schema,
            reasoning={"effort": self.reasoning_effort},
            store=False,
            metadata={"prompt_version": prompt_version},
        )
        parsed = response.output_parsed
        if parsed is None:
            raise RuntimeError(f"{prompt_version} 응답을 데이터 계약으로 파싱하지 못했습니다.")
        usage = response.usage
        return CallResult(
            data=parsed,
            metadata=CallMetadata(
                response_id=response.id,
                model=response.model,
                prompt_version=prompt_version,
                input_tokens=usage.input_tokens if usage else 0,
                output_tokens=usage.output_tokens if usage else 0,
                total_tokens=usage.total_tokens if usage else 0,
                latency_ms=round((time.perf_counter() - started_at) * 1_000),
            ),
        )

    def localize(
        self,
        source: SourceReview,
        constraints: LocalizationConstraints,
    ) -> CallResult[LocalizedCopy]:
        return self._parse(
            schema=LocalizedCopy,
            instructions=LOCALIZER_INSTRUCTIONS,
            prompt=build_localization_prompt(source, constraints),
            prompt_version=LOCALIZER_PROMPT_VERSION,
        )

    def review(
        self,
        source: SourceReview,
        constraints: LocalizationConstraints,
        localized: LocalizedCopy,
    ) -> CallResult[LocalizationReview]:
        return self._parse(
            schema=LocalizationReview,
            instructions=REVIEWER_INSTRUCTIONS,
            prompt=build_review_prompt(source, constraints, localized),
            prompt_version=REVIEWER_PROMPT_VERSION,
        )

    def revise(
        self,
        source: SourceReview,
        constraints: LocalizationConstraints,
        localized: LocalizedCopy,
        review: LocalizationReview,
    ) -> CallResult[LocalizedCopy]:
        return self._parse(
            schema=LocalizedCopy,
            instructions=LOCALIZER_INSTRUCTIONS,
            prompt=build_revision_prompt(source, constraints, localized, review),
            prompt_version=REVISION_PROMPT_VERSION,
        )
