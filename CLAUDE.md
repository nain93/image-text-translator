# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 개요

이 저장소는 두 도구로 이뤄져 있다:

1. **리뷰 카드 생성기 (메인, 진행 중)** — 고정 디자인 템플릿(`image_plate/`)에 일본어 리뷰 텍스트·메타데이터(@아이디/피부타입/연령)·비포/애프터 사진을 채워 인스타용 화장품 리뷰 카드를 대량 생산한다. ChatGPT 이미지생성의 불안정함(글자 깨짐·줄바꿈 흔들림)을 **결정론적 합성**으로 대체하고 **일본어 QA**를 더한다. 진입점 [review_card.py](review_card.py).
2. **원본 글자 번역기** — 이미지 속 글자만 한→일로 바꾸는 4단계 파이프라인 [translate_image.py](translate_image.py). 카드 생성기가 이 모듈의 색 매칭·폰트 헬퍼를 재사용한다.

전체 설계 문서: `~/.claude/plans/joyful-sniffing-marble.md`.

## 명령어

테스트·린트·빌드 설정 없음. git 저장소 아님. venv는 **Python 3.11**(구축·의존성 설치 완료).

```bash
source venv/bin/activate

# 리뷰 카드: 기계 QA → 생성
python qa.py --csv reviews.csv                       # 슬롯 적합성(폰트축소·줄수·오버플로우) 검수
python review_card.py --csv reviews.csv --out out/   # 카드 생성

# 원본 번역기 (네이버 키 필요, iopaint를 PATH에서 subprocess로 찾으므로 activate 필수)
python translate_image.py input.png output.png --src ko --tgt ja
```

의존성 재설치: `pip install requests numpy pillow iopaint python-dotenv` (3.11 venv).

**리뷰 카드 생성·QA는 API 키가 필요 없다**(순수 Pillow + 로컬, 언어 검수는 Claude Code 대화형). 네이버 키 4개(`CLOVA_OCR_URL`, `CLOVA_OCR_SECRET`, `PAPAGO_CLIENT_ID`, `PAPAGO_CLIENT_SECRET`)는 `translate_image.py`와 OCR 슬롯 캘리브레이션에만 필요. `.env`에 넣으면 자동 로드(`.env.example` 템플릿, `.env`는 `.gitignore` 처리). 직접 export한 값이 `.env`보다 우선.

## 아키텍처

### 리뷰 카드 생성기
CSV 행(리뷰+메타) → 템플릿 변수 영역 갈아끼우기 → 카드 PNG.

- [review_card.py](review_card.py) — CSV를 읽어 행마다 `slots/<template>.json`을 로드. 텍스트 슬롯은 `erase_fill`(원본 배경색으로 박스를 채워 기존 글자 제거) → `ti.sample_colors`로 원본 글자색을 매칭해 `jp_layout`으로 렌더. 사진 슬롯은 `paste_photo`(cover-crop)로 합성.
- [jp_layout.py](jp_layout.py) — 일본어 다행 레이아웃. **작성자 줄바꿈(`\n`) 보존이 핵심** — 각 작성자 줄이 통째로 폭에 맞도록 폰트를 줄인다(고아줄 방지). 최소 크기에도 안 맞을 때만 금칙(禁則) 재줄바꿈으로 폴백.
- [qa.py](qa.py) — 기계적 QA. 슬롯에 깨끗이 들어가는지(폰트 축소량·줄수·오버플로우·자동 재줄바꿈)만 경고. **언어 품질(2030 여성 말투·자연스러움·구매전환) 검수는 Claude Code가 대화형으로** 한다(Anthropic API 안 씀 — 사용자 결정).
- `slots/<template>.json` — 템플릿별 변수 영역 좌표+스타일. 좌표는 `clova_ocr`로 1회 캘리브레이션(한국어 OCR 도메인이라 일본어는 깨져 읽혀도 **박스 좌표는 정확**).
- **재사용 헬퍼(translate_image.py)**: `sample_colors`(전경/배경 분리 글자색 추정), `weighted_font_path`. (LaMa erase를 연결하면 `build_mask`/`inpaint_lama`도 재사용)

### 원본 번역기 (translate_image.py)
`TextBox`가 4단계를 관통: `clova_ocr`(CLOVA, 단어 박스) → `group_into_lines` → `papago_translate`(줄 단위 한→일) → `build_mask`+`inpaint_lama`(LaMa CLI를 subprocess로 실행해 글자 제거) → `render_text`(색·굵기·네온 글로우 매칭 재렌더). 번역기를 바꾸려면 `papago_translate()`만 교체.

## 주의할 점 (gotchas)

- **Python은 반드시 3.11.** iopaint가 `Pillow==9.5.0`을 하드 핀 → cp311까지만 휠. 3.12+(머신 기본 3.14)에선 소스빌드 실패로 iopaint 설치 자체가 안 됨. venv를 3.12+로 다시 만들지 말 것.
- **카드 생성기의 erase는 현재 `fill`만**(단색 카드엔 충분). 텍스처 위 글자는 `inpaint_lama` 폴백이 필요하지만 아직 미연결.
- **교체 텍스트 폰트는 `~/Library/Fonts/NotoSansCJKjp-Regular.otf`**(brew `font-noto-sans-cjk-jp`). 굵기 변형(Regular~Black)을 `weighted_font_path`로 선택. translate_image의 `FONT_PATHS`도 동일 폰트.
- **`iopaint`은 외부 CLI**(`translate_image`에서만 사용). venv를 activate해야 PATH에서 찾음. 첫 실행 시 LaMa 모델 자동 다운로드. MPS(Apple GPU) 가능 → `inpaint_lama()`에서 `--device=mps`.
- **`image_plate/`는 현재 "완성본" 템플릿** — 변수 영역을 갈아끼우는 bridge 방식. 추후 빈 프레임 제공 시 erase 스킵으로 전환(슬롯 좌표는 동일 재사용).

## 진행 상태
- ✅ 텍스트 슬롯 합성 + `customer_review` 1종 + jp_layout + 기계 QA — E2E 동작 확인
- 🚧 비포/애프터 사진·풀쿼트(코드 준비, 슬롯 정의·테스트 예정), 나머지 템플릿 슬롯, 빈 프레임 모드
