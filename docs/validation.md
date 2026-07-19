# Validation Record

## 2026-07-19 OpenAI API smoke test

한국어 리뷰 1건을 실제 OpenAI Responses API로 현지화하고 별도 Reviewer 검수 후 PNG로 렌더했다. API 키와 원본 응답 ID는 저장소에 기록하지 않았다.

```bash
localize-reviews \
  --csv sample_reviews_ko.csv \
  --limit 1 \
  --render \
  --out <temporary-directory>
```

### Result

- Model: `gpt-5.6-sol`
- Rows: 1
- Review pass: 1
- Human review required: 0
- Average review score: 98
- Revision count: 0
- API calls: 2
- Total tokens: 3,111
- API latency: 21,924ms
- Rendered image: 1 PNG, 1122×1402
- Visual inspection: Japanese text present, no clipping or slot overflow

이 수치는 단일 스모크 입력의 결과이며 전체 데이터셋 품질을 의미하지 않는다. 모델·프롬프트 변경 시 다건 평가로 다시 측정해야 한다.

## Automated validation

```bash
pytest -q
ruff check .
python review_card.py --csv sample_reviews.csv --validate-only
```

- Unit/integration tests: 9 passed
- Ruff: passed
- Existing template asset preflight: 10 rows passed
- Existing deterministic batch render: 10 PNGs completed
