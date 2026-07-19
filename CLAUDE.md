# CLAUDE.md

## 프로젝트 개요

한국어 화장품 리뷰를 일본 소비자용 카피로 현지화하고 고정 이미지 템플릿에 합성한다.

- LLM: 의미 보존, 일본어 문체, 레이아웃 제약을 반영한 현지화와 독립 검수
- 결정론적 코드: 자산 검증, 좌표, 금칙처리, 폰트 맞춤, 이미지 합성
- 기존 Papago 경로: 비교 기준선이므로 제거하지 않는다

## 주요 명령

```bash
source venv/bin/activate
pip install -e '.[dev]'

pytest -q
ruff check .
python review_card.py --csv sample_reviews.csv --validate-only
localize-reviews --csv sample_reviews_ko.csv --limit 1 --render
```

## 구현 규칙

- Python 3.11만 지원한다. IOPaint가 Pillow 9.5.0에 고정되어 있다.
- 프롬프트를 변경하면 `localization/prompts.py`의 버전도 올린다.
- 원문에 없는 효능, 기간, 수치, 추천 표현을 추가하지 않는다.
- 자동 수정은 한 번만 허용하고 최종 실패는 `human_review_required`로 남긴다.
- LLM 결과를 직접 이미지에 넘기지 않고 Pydantic 계약과 Reviewer를 통과시킨다.
- 렌더 전 `review_card.validate_rows()`로 전체 배치 자산을 먼저 검증한다.
- `.env`, `venv/`, `artifacts/`는 커밋하지 않는다.

## 주요 파일

- `localization/` — API 계약, 프롬프트, OpenAI 게이트웨이, 수정 루프
- `localize_reviews.py` — 한국어 CSV에서 결과 번들까지 연결
- `review_card.py` — 템플릿 렌더러와 배치 사전검증
- `jp_layout.py` — 일본어 줄바꿈과 금칙처리
- `translate_image.py` — CLOVA/Papago 기준선과 이미지 헬퍼
- `evals/evaluate_run.py` — 품질·토큰·지연시간 요약
