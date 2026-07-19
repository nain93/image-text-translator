# LLM Japanese Review Card Pipeline

한국어 화장품 리뷰를 일본 소비자용 카피로 현지화하고, 고정 디자인 템플릿에 합성해 SNS 리뷰 카드로 만드는 Python 프로젝트입니다.

단순 번역 API 호출이 아니라 **원문 의미 보존**, **일본어 후기 말투**, **이미지 슬롯의 줄 수·글자 수 제한**을 함께 다룹니다. 의미와 문체는 LLM이 판단하고, 좌표·폰트·줄바꿈·이미지 합성은 결정론적 코드가 책임집니다.

## 해결하려는 문제

이미지 속 문구를 다른 내용이나 언어로 바꾸기 위해 단순히 LLM 이미지 모델을 사용하면 결과가 일정하지 않았습니다.

- 텍스트가 원래 위치에서 벗어납니다.
- 기존 이미지 폼과 배경이 함께 변형됩니다.
- 일본어 글자가 깨지거나 알아보기 어렵게 생성됩니다.
- 이미지마다 위치와 글자 스타일이 달라져 다시 수정해야 합니다.

이 프로젝트는 이미지 전체를 LLM으로 다시 생성하지 않는 방식으로 이 문제를 해결했습니다. LLM은 한글 문구를 자연스러운 일본어로 번역하고, 코드는 기존 이미지 위에 번역문을 직접 합성합니다.

- 텍스트 위치와 영역을 JSON 좌표로 지정합니다.
- 글자 크기, 굵기, 줄 간격, 색상, 정렬도 JSON에 함께 저장합니다.
- 번역문을 지정된 위치와 폰트 설정에 맞춰 렌더링합니다.
- 문장이 영역을 벗어나지 않도록 길이와 줄바꿈을 조절합니다.
- 기존 이미지 폼과 배경은 그대로 유지한 채 텍스트만 교체합니다.

한 번 만든 JSON 설정은 같은 이미지 폼에 계속 재사용할 수 있습니다. 따라서 문구나 언어가 바뀌어도 텍스트 위치와 디자인을 매번 다시 맞추는 반복 작업을 줄일 수 있습니다.

## 파이프라인

```text
한국어 리뷰 CSV
  → 템플릿 좌표로 줄 수·줄당 글자 수 계산
  → OpenAI Responses API Localizer
  → Pydantic 응답 계약 검증
  → 독립 Reviewer 프롬프트
      ├─ pass: 렌더링
      └─ revise: 지적 기반 1회 수정 → 재검수
  → Pillow 일본어 금칙처리·폰트 맞춤·이미지 합성
  → localized.csv + PNG + API/검수 메타데이터
```

### LLM이 담당하는 부분

- 한국어 리뷰의 주장과 경험을 보존한 일본어 현지화
- 타깃 독자와 브랜드 톤 반영
- 원문에 없는 효과·수치·추천 표현 추가 여부 검수
- 레이아웃 제한을 넘는 문장 축약

### 코드가 담당하는 부분

- 템플릿과 참조 이미지 사전검증
- 슬롯 좌표 기반 길이 제한 계산
- 일본어 금칙처리와 폰트 크기 조절
- 비포·애프터 사진 cover-crop 및 PNG 합성
- 프롬프트 버전, 토큰, 지연시간, 리뷰 점수 기록

## 실행

Python 3.11이 필요합니다. LaMa의 Pillow 제약 때문에 3.12 이상은 지원하지 않습니다.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
# .env에 OPENAI_API_KEY 입력
```

## 실제 사용 예시

2026-07-19 실제 API 스모크에 사용한 첫 번째 입력입니다. `review_text_ko`의 `\n`은 카드에 유지할 줄바꿈입니다.

### 실제 실행 이미지

왼쪽은 한국어 원문을 고정 템플릿에 렌더링한 변환 전 카드이고, 오른쪽은 같은 원문을 `gpt-5.6-sol`로 현지화·검수한 실제 출력입니다. 두 PNG는 리뷰 본문 슬롯을 제외한 모든 픽셀이 동일합니다.

| Input — 한국어 원문 카드 | Output — 일본어 현지화 카드 |
| --- | --- |
| ![동일 템플릿에 렌더링한 한국어 원문 카드](docs/examples/actual-run/before-korean-customer-review.png) | ![OpenAI API 현지화 후 동일 템플릿에 렌더링한 일본어 리뷰 카드](docs/examples/actual-run/after-japanese-customer-review.png) |

### 생성 파일

```text
artifacts/<UTC timestamp>/
├── localized.csv
├── localization.meta.json
└── images/
    └── llm_customer_review.png  # 1122×1402, 잘림·오버플로우 없음
```

실행 결과의 검수·비용 지표를 요약할 수 있습니다.

```bash
python evals/evaluate_run.py artifacts/<run>/localization.meta.json
```

## 검증

```bash
pytest -q
ruff check .
python review_card.py --csv sample_reviews.csv --validate-only
```

2026-07-19 실제 API 스모크에서는 1건이 Reviewer 98점으로 통과했고, 2회 API 호출 후 PNG까지 생성됐습니다. 상세 수치는 [검증 기록](docs/validation.md)에 남겼습니다.

## Papago 기준선

[translate_image.py](translate_image.py)는 기존 CLOVA OCR → Papago → LaMa → Pillow 경로입니다. 삭제하지 않고 LLM 현지화와 비교할 기준선으로 유지합니다. 좌표 추출과 렌더링 헬퍼도 새 파이프라인에서 재사용합니다.

## 구조

- `localization/contracts.py` — Pydantic 입출력 계약
- `localization/prompts.py` — 버전이 지정된 Localizer·Reviewer·Revision 프롬프트
- `localization/openai_gateway.py` — Responses API 호출과 사용량 수집
- `localization/pipeline.py` — 현지화·검수·1회 수정 오케스트레이션
- `localize_reviews.py` — CSV 배치 진입점과 결과 번들 생성
- `review_card.py`, `jp_layout.py` — 결정론적 이미지 렌더링
- `evals/` — 실행 결과 품질·토큰·지연시간 요약
- `tests/` — API 없이 실행되는 계약·파이프라인·렌더 사전검증 테스트

## 현재 한계

- LLM Reviewer 점수는 일본어 원어민 평가를 대체하지 않습니다.
- 효능 표현 경고는 법률·광고 심의 판단이 아니며 최종 검토가 필요합니다.
- macOS Noto Sans CJK JP 폰트 경로를 기본값으로 사용합니다.
- 기존 템플릿 2종은 원본 빈 프레임이 없어 과거 출력 이미지를 브리지 자산으로 사용합니다.
