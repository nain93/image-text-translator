"""버전이 지정된 현지화·검수 프롬프트."""

from localization.contracts import (
    LocalizationConstraints,
    LocalizationReview,
    LocalizedCopy,
    SourceReview,
)

LOCALIZER_PROMPT_VERSION = "ja-review-localizer-v1"
REVIEWER_PROMPT_VERSION = "ja-review-reviewer-v1"
REVISION_PROMPT_VERSION = "ja-review-revision-v1"

LOCALIZER_INSTRUCTIONS = """
역할: 한국 화장품 리뷰를 일본 소비자용 카피로 현지화하는 전문 에디터다.

목표:
- 한국어 원문의 경험과 효능 주장을 그대로 보존한다.
- 일본 소비자가 실제로 작성한 후기처럼 자연스러운 일본어로 쓴다.
- 제공된 슬롯별 줄 수와 줄당 글자 수 제한을 지킨다.

제약:
- 원문에 없는 사용 기간, 효과, 수치, 제품명, 추천 표현을 추가하지 않는다.
- 의미를 강화하거나 광고 문구처럼 과장하지 않는다.
- 입력이 불명확하면 추측하지 말고 warnings에 남긴다.
- 줄바꿈은 각 *_lines 배열의 원소 경계로 표현한다.
- 입력에 없는 headline 또는 pull_quote가 필수가 아니면 빈 배열을 반환한다.

완료 기준:
- 모든 필수 슬롯이 채워져 있다.
- 각 줄이 해당 글자 수 제한 이내다.
- preserved_claims에는 원문에서 실제로 보존한 핵심 주장만 기록한다.
""".strip()

REVIEWER_INSTRUCTIONS = """
역할: 한일 화장품 리뷰 현지화 결과를 배포 전에 검수하는 독립 리뷰어다.

검수 기준:
- 한국어 원문에 없는 효과·기간·수치·추천 표현이 추가되지 않았는가
- 핵심 경험과 주장이 누락되거나 반대로 바뀌지 않았는가
- 일본어가 타깃 독자에게 자연스럽고 광고문처럼 과장되지 않았는가
- 모든 슬롯이 줄 수와 줄당 글자 수 제한을 지켰는가

high 또는 medium 문제가 하나라도 있으면 revise로 판정하고, 수정 가능한 instruction을 쓴다.
문체 취향만으로 revise하지 않는다. score 85 이상이고 세 기준이 모두 참일 때만 pass한다.
""".strip()


def build_localization_prompt(
    source: SourceReview,
    constraints: LocalizationConstraints,
) -> str:
    return "\n".join(
        [
            f"프롬프트 버전: {LOCALIZER_PROMPT_VERSION}",
            "아래 원문을 일본어 리뷰 카드 카피로 현지화하라.",
            "",
            "<source_review>",
            source.model_dump_json(indent=2),
            "</source_review>",
            "",
            "<layout_constraints>",
            constraints.model_dump_json(indent=2),
            "</layout_constraints>",
        ]
    )


def build_review_prompt(
    source: SourceReview,
    constraints: LocalizationConstraints,
    localized: LocalizedCopy,
) -> str:
    return "\n".join(
        [
            f"프롬프트 버전: {REVIEWER_PROMPT_VERSION}",
            "<source_review>",
            source.model_dump_json(indent=2),
            "</source_review>",
            "<layout_constraints>",
            constraints.model_dump_json(indent=2),
            "</layout_constraints>",
            "<localized_copy>",
            localized.model_dump_json(indent=2),
            "</localized_copy>",
        ]
    )


def build_revision_prompt(
    source: SourceReview,
    constraints: LocalizationConstraints,
    localized: LocalizedCopy,
    review: LocalizationReview,
) -> str:
    return "\n".join(
        [
            f"프롬프트 버전: {REVISION_PROMPT_VERSION}",
            "기존 현지화 결과를 리뷰 지적에 필요한 만큼만 수정하라.",
            "원문에 없는 내용을 새로 추가하지 말고 전체 결과를 다시 반환하라.",
            "",
            "<source_review>",
            source.model_dump_json(indent=2),
            "</source_review>",
            "<layout_constraints>",
            constraints.model_dump_json(indent=2),
            "</layout_constraints>",
            "<previous_copy>",
            localized.model_dump_json(indent=2),
            "</previous_copy>",
            "<review>",
            review.model_dump_json(indent=2),
            "</review>",
        ]
    )
