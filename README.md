# 일본 리뷰 카드 생성기 (Japanese Review Card Generator)

고정 디자인 템플릿(`image_plate/`)에 **일본어 리뷰 텍스트 · 메타데이터(@아이디/피부타입/연령) · 비포·애프터 사진**을 채워, 인스타용 화장품 리뷰 카드를 대량 생산합니다. ChatGPT 이미지생성의 불안정함(글자 깨짐·줄바꿈 어색·레이아웃 흔들림)을 **결정론적 합성**으로 대체하고 **일본어 검수(QA)** 를 더했습니다.

```
CSV(리뷰+메타) ─▶ ① 일본어 QA ─▶ ② 템플릿 변수영역 갈아끼우기 ─▶ 리뷰 카드 PNG
                  (기계검수 +        (기존 글자 지움 → 색 매칭 렌더,
                   Claude 대화형)     비포/애프터 사진 합성)
```

> 같은 저장소의 `translate_image.py`는 원래 만든 **이미지 속 글자 번역기(한→일)** 입니다. 카드 생성기가 그 색 매칭·폰트 로직을 재사용합니다. (맨 아래 "원본 번역 도구" 참고)

## 1. 환경
- `venv/`는 **Python 3.11**로 구축돼 있고 의존성 설치 완료. 실행 전 `source venv/bin/activate`.
- 폰트: **Noto Sans CJK JP** (`brew install --cask font-noto-sans-cjk-jp` → `~/Library/Fonts/`).
- **리뷰 카드 생성·QA는 외부 API 키가 필요 없습니다** (순수 Pillow + 로컬). 언어 검수는 Claude Code가 대화형으로 합니다.
  - 네이버 키는 새 템플릿 슬롯 좌표를 OCR로 뽑을 때(선택)와 `translate_image.py`에만 필요 — `.env` 참고.

## 2. 리뷰 카드 만들기
```bash
# 1) 기계 검수 — 슬롯에 깨끗이 들어가는지(폰트축소·줄수·오버플로우·고아줄) 경고
venv/bin/python qa.py --csv reviews.csv
#    + 언어 검수(2030 여성 말투·줄바꿈·구매전환)는 Claude Code에게 텍스트를 주고 받습니다.

# 2) 카드 생성
venv/bin/python review_card.py --csv reviews.csv --out out/
```

## 3. CSV 스키마
| 열 | 필수 | 설명 |
|---|---|---|
| `template` | ✓ | `slots/<template>.json`의 템플릿 키 (예: `customer_review`) |
| `review_text` | ✓ | 리뷰 본문. 줄바꿈은 리터럴 `\n`으로. 작성자 줄바꿈은 그대로 보존됨 |
| `handle` | | `@아이디` 또는 이름 |
| `skin_type` | | 피부타입 (乾燥肌/混合肌/脂性肌…) |
| `age` | | 연령 (20代/30代…) |
| `pull_quote` | | 강조 문장 (해당 슬롯이 있는 템플릿) |
| `before_image` / `after_image` | | 비포/애프터 사진 경로 (해당 슬롯이 있는 템플릿) |
| `output_name` | | 출력 파일명 |

`handle / skin_type / age`는 `@아이디 / 피부타입 / 연령` 한 줄로 합쳐집니다. 예시는 `sample_reviews.csv` 참고.

## 4. 템플릿 슬롯 스펙 (`slots/<template>.json`)
템플릿마다 변수 영역의 좌표·스타일을 **한 번** 정의합니다.
```json
{
  "image": "image_plate/....png",
  "slots": {
    "review_body": {"box": [x0,y0,x1,y1], "align": "left", "valign": "top", "font_size": 38, "leading": 1.75},
    "id_line":     {"box": [x0,y0,x1,y1], "align": "left", "valign": "middle", "font_size": 27},
    "pull_quote":  {"box": [x0,y0,x1,y1], "color": [255,150,0], "weight": "Bold"},
    "before_image":{"box": [x0,y0,x1,y1]}, "after_image": {"box": [x0,y0,x1,y1]}
  }
}
```
**좌표 측정 팁**: `translate_image.py`의 `clova_ocr()`로 템플릿을 OCR하면 기존 글자의 박스 좌표가 나옵니다 (한국어 OCR 도메인이라 일본어 글자는 깨져 읽혀도 **박스 좌표는 정확**). 추후 빈 프레임이 와도 같은 좌표를 그대로 씁니다.

## 5. 구성 파일
- `review_card.py` — CSV → 카드 생성 (진입점)
- `jp_layout.py` — 일본어 다행 레이아웃 (줄바꿈 + 금칙처리 + 박스 폰트맞춤)
- `qa.py` — 기계적 QA (레이아웃 적합성)
- `slots/*.json` — 템플릿별 슬롯 스펙
- `image_plate/` — 디자인 템플릿 (현재는 완성본; 추후 빈 프레임으로 교체 예정)
- `sample_reviews.csv` — 샘플 입력
- `translate_image.py` — 원본 글자 번역기 (재사용 헬퍼 제공)

## 6. 진행 상태
- ✅ 텍스트 슬롯 합성(`review_body` / `id_line`) + 1종 템플릿(`customer_review`)
- ✅ 일본어 레이아웃(작성자 줄바꿈 보존) + 기계 QA + Claude 대화형 언어검수
- 🚧 비포/애프터 사진·풀쿼트 (코드 준비됨, 템플릿 슬롯 정의·테스트 예정)
- 🚧 나머지 템플릿 슬롯 정의
- 🚧 빈 프레임 모드 (디자이너 블랭크 틀 제공 시 erase 스킵)

---

## 원본 번역 도구 — `translate_image.py`
이미지 배경은 두고 **글자만** 다른 언어로 바꿉니다 (한→일 기본): CLOVA OCR → Papago 번역 → IOPaint(LaMa) 텍스트 제거 → Pillow 재렌더링.
```bash
venv/bin/python translate_image.py input.png output.png --src ko --tgt ja
```
네이버 키 4개 필요(`.env` 또는 export): `CLOVA_OCR_URL`, `CLOVA_OCR_SECRET`, `PAPAGO_CLIENT_ID`, `PAPAGO_CLIENT_SECRET`. CLOVA OCR URL은 `https://...apigw.ntruss.com/.../general` 형태(도메인의 APIGW Invoke URL). 첫 실행 시 LaMa 모델 자동 다운로드. GPU(MPS) 쓰려면 `inpaint_lama()`의 `--device=cpu`→`mps`.
