# 도서 PDF 구조 분석 및 엔티티 추출 시스템

## 📖 프로젝트 개요

도서 PDF 파일을 업로드하면 자동으로 책의 구조(본문 시작, 챕터 경계)를 파악하고, 페이지별 및 챕터별 구조화된 엔티티를 추출하는 백엔드 시스템입니다.

**핵심 파이프라인**: `PDF 업로드 → 파싱 → 구조분석 → 페이지엔티티 → 챕터서머리 → 북서머리`

**프로젝트 범위**: 백엔드 API 서버 (프론트엔드 제외)

**프로젝트 상태**: ✅ Phase 7.5 완료 (2025-12-10)
- 전체 도서: 87권
- 챕터 6개 이상 완료: 36권 (100%)
- 배치 처리 스크립트 완료
- 도서 상세 리스트 문서화 완료

---

## 🏗️ 전체 아키텍처

### 데이터 파이프라인

```
┌─────────────────────┐
│    PDF 파일         │
│ (data/input/)       │
└──────────┬──────────┘
           ↓
┌──────────────────────────────────────────┐
│ Phase 1: PDF 파싱                        │
│ - Upstage Document API 호출              │
│ - 레이아웃 분석 (elements, HTML)         │
│ - 100페이지 자동 분할                    │
│ - 병렬 처리 (10페이지 단위)              │
│ - 양면 분리 (좌/우 페이지)               │
└──────────┬───────────────────────────────┘
           ↓
┌──────────────────────────────────────────┐
│ 캐시 저장 (비용 절감)                    │
│ data/cache/upstage/{md5_hash}.json       │
│ - API 원본 응답 저장                     │
│ - 파일 해시 기반 (같은 파일 재사용)      │
└──────────┬───────────────────────────────┘
           ↓
┌──────────────────────────────────────────┐
│ Phase 2: 구조 분석                       │
│ - Footer 기반 본문/서문/종문 탐지        │
│ - Footer 기반 챕터 경계 탐지             │
│ - 휴리스틱 알고리즘만 사용 (LLM 없음)    │
└──────────┬───────────────────────────────┘
           ↓
┌──────────────────────────────────────────┐
│ DB 저장 (Book.structure_data)            │
│ {                                         │
│   "main_start_page": 87,                 │
│   "main_end_page": 474,                  │
│   "chapters": [                          │
│     {"title": "...", "start_page": ...}  │
│   ]                                       │
│ }                                         │
└──────────┬───────────────────────────────┘
           ↓
┌──────────────────────────────────────────┐
│ Phase 3: 엔티티 추출                     │
│ Step 1: 페이지 엔티티 추출               │
│ - 캐시에서 raw_text 생성                 │
│ - OpenAI LLM (Structured Output)         │
│ - 도메인별 스키마 (4가지)                │
│ - 병렬 처리 (workers=3)                  │
│                                           │
│ Step 2: 챕터 구조화                      │
│ - 페이지 엔티티 집계                     │
│ - 챕터 수준 통합 및 인사이트 생성        │
└──────────┬───────────────────────────────┘
           ↓
┌──────────────────────────────────────────┐
│ DB 저장                                   │
│ - PageSummary.structured_data (JSON)     │
│ - ChapterSummary.structured_data (JSON)  │
│                                           │
│ 엔티티 캐시 저장 (재사용)                │
│ data/cache/summaries/{book_title}/      │
│ - page_{content_hash}.json               │
│ - chapter_{content_hash}.json            │
└──────────┬───────────────────────────────┘
           ↓
┌──────────────────────────────────────────┐
│ Phase 4: 북 서머리 생성                  │
│ - 챕터별 요약 집계                       │
│ - 책 전체 요약 생성 (LLM)                │
│ - 엔티티 통합 (insights, events, etc.)   │
│ - 도메인별 엔티티 집계                   │
└──────────┬───────────────────────────────┘
           ↓
┌──────────────────────────────────────────┐
│ 로컬 파일 저장                            │
│ data/output/book_summaries/              │
│ - {book_title}_report.json               │
└──────────────────────────────────────────┘
```

### 상태 전이

```
uploaded → parsed → structured → page_summarized → summarized → (북 서머리 생성)
```

**참고**: 북 서머리 생성은 별도 API 엔드포인트로 호출 (`POST /api/books/{id}/extract/book_summary`)

---

## 📦 주요 컴포넌트

### 1. PDF 파싱 (`backend/parsers/`)

#### UpstageAPIClient
- **기능**: Upstage Document Digitization API 연동
- **특징**:
  - 100페이지 자동 분할 처리
  - 병렬 처리 (10페이지 단위 기본 모드)
  - 재시도 로직 (지수 백오프)
  - Rate limit (429) 처리

#### PDFParser
- **기능**: Elements 구조화 및 양면 분리
- **특징**:
  - HTML → 텍스트 추출 (BeautifulSoup)
  - 좌/우 페이지 분리 (중앙선 0.5 기준)
  - raw_text 생성 (elements의 text를 공백 연결)
  - 캐시 통합 (자동 저장/로드)

#### CacheManager
- **기능**: 파일 해시 기반 캐싱
- **특징**:
  - MD5 해시 키 생성 (파일 내용 기반)
  - 안전한 저장 (임시 파일 → 원자적 이동)
  - 메타데이터 포함 (pdf_path, category, cached_at)

### 2. 구조 분석 (`backend/structure/`)

#### ContentBoundaryDetector
- **기능**: 본문/서문/종문 경계 탐지
- **특징**:
  - Footer 기반 판단 (좌측 페이지 우선)
  - 키워드 패턴 매칭
  - 휴리스틱만 사용 (LLM 없음)

#### ChapterDetector
- **기능**: 챕터 경계 탐지
- **특징**:
  - Footer 기반 숫자 추출
  - 숫자만 사용하여 챕터 구분
  - 챕터 범위 계산 (start_page, end_page)

#### StructureBuilder
- **기능**: 최종 구조 생성
- **특징**:
  - BoundaryDetector + ChapterDetector 통합
  - 구조 후보 생성 (자동 분석)
  - 사용자 확정 지원

### 3. 엔티티 추출 (`backend/summarizers/`)

#### PageExtractor
- **기능**: 페이지별 엔티티 추출
- **특징**:
  - 도메인별 스키마 (History/Economy/Humanities/Science)
  - OpenAI Structured Output
  - 캐시 저장 (콘텐츠 해시 기반)
  - 4000자 초과 시 자동 절단

#### ChapterStructurer
- **기능**: 챕터별 구조화
- **특징**:
  - 페이지 엔티티 집계 및 압축
  - 챕터 수준 인사이트 생성
  - 증거 기반 통합

#### LLMChains
- **기능**: OpenAI API 연동
- **설정**:
  - 모델: gpt-4.1-mini
  - 온도: 0.3
  - 타임아웃: 60초
  - 재시도: 최대 3회 (지수 백오프)

---

## 🗄️ 데이터 저장

### 캐시 (data/cache/)

```
cache/
├── upstage/                    # PDF 파싱 캐시
│   └── {md5_hash}.json         # Upstage API 원본 응답
│       └── _cache_meta.json    # 메타데이터 (pdf_path, category, cached_at)
└── summaries/                  # 엔티티 추출 캐시
    ├── page_{content_hash}.json      # 페이지 엔티티
    └── chapter_{content_hash}.json   # 챕터 구조화 결과
```

### 데이터베이스 (SQLite: data/books.db)

#### books 테이블
- `id`, `title`, `author`, `category` (분야)
- `source_file_path`, `page_count`, `status` (enum)
- `structure_data` (JSON): 구조 분석 결과
- `created_at`, `updated_at`

#### chapters 테이블
- `id`, `book_id` (FK)
- `title`, `order_index` (0-based)
- `start_page`, `end_page`, `section_type`

#### page_summaries 테이블
- `id`, `book_id` (FK), `page_number`
- `summary_text`: 하위 호환성 (2-4문장 요약)
- `structured_data` (JSON): 구조화된 엔티티
- `lang`: 언어 코드

#### chapter_summaries 테이블
- `id`, `book_id` (FK), `chapter_id` (FK)
- `summary_text`: 하위 호환성 (3-5문장 요약)
- `structured_data` (JSON): 구조화된 결과
- `lang`: 언어 코드

### 산출물 (data/output/)

```
output/
├── text/                       # 텍스트 정리 (API 전용)
│   └── {hash}_{title}_text.json
├── structure/                  # 구조 분석 (레거시, 삭제 예정)
│   └── {hash}_{title}_structure.json
├── book_summaries/             # 북 서머리 (최종 보고서)
│   └── {book_title}_report.json
├── token_stats/                # 토큰 통계
│   └── book_{id}_tokens.json
└── test_samples/               # 테스트 샘플
    └── selected_samples.json
```

**참고**: 
- `data/output/text/` 파일은 API 엔드포인트 `GET /api/books/{id}/text` 용도로만 사용
- Phase 5 엔티티 추출은 이 파일을 사용하지 않고, 캐시에서 직접 raw_text 생성
- `data/output/book_summaries/` 파일은 북 서머리 생성 시 자동 생성

---

## 🚀 설치 및 실행

### 환경 요구사항

- **OS**: Windows 10+ (PowerShell 5.1)
- **Python**: 3.10 이상
- **Poetry**: 1.8.5 이상 (필수)
- **외부 API**:
  - Upstage Document Digitization API 키
  - OpenAI API 키

### 설치

```powershell
# 1. Poetry 버전 확인
poetry --version  # 1.8.5 이상 필수

# 2. 의존성 설치
poetry install

# 3. 환경변수 설정
# .env 파일 생성 및 API 키 입력
```

### 환경변수 설정 (.env)

```env
# Upstage API
UPSTAGE_API_KEY=your_upstage_api_key_here

# OpenAI API
OPENAI_API_KEY=your_openai_api_key_here

# 데이터베이스 (선택, 기본값: data/books.db)
DATABASE_DIR=data

# 캐시 디렉토리 (선택, 기본값: data/cache)
CACHE_DIR=data/cache

# 출력 디렉토리 (선택, 기본값: data/output)
OUTPUT_DIR=data/output
```

### 데이터베이스 초기화

```powershell
# DB 테이블 생성
poetry run python -c "from backend.api.database import init_db; init_db()"
```

### 서버 실행

```powershell
# 개발 모드 (자동 재시작)
poetry run uvicorn backend.api.main:app --reload --port 8000

# API 문서 확인
# 브라우저에서: http://localhost:8000/docs
```

---

## 📚 API 엔드포인트

### 기본

- `GET /health` - 헬스체크
- `GET /api/books` - 책 리스트 조회

### PDF 파싱

- `POST /api/books/upload` - PDF 업로드 및 파싱 시작 (백그라운드)
  - 파라미터: `file` (PDF 파일), `title`, `author`, `category` (선택)
  - 응답: `{"book_id": 123, "status": "uploaded"}`
- `GET /api/books/{id}` - 책 상태 및 메타데이터 조회
  - 응답: `{"id": 123, "title": "...", "status": "parsed", ...}`

### 구조 분석

- `GET /api/books/{id}/structure/candidates` - 구조 후보 조회
  - 응답: 휴리스틱 기반 자동 구조 후보 + 샘플 페이지
- `POST /api/books/{id}/structure/final` - 구조 확정
  - 요청 본문: `{"main_start_page": 87, "chapters": [...]}`
  - 응답: `{"status": "structured"}`

### 엔티티 추출

- `POST /api/books/{id}/extract/pages` - 페이지 엔티티 추출 시작 (백그라운드)
  - 응답: `{"status": "processing"}`
  - 전제 조건: `status == "structured"`
- `POST /api/books/{id}/extract/chapters` - 챕터 구조화 시작 (백그라운드)
  - 응답: `{"status": "processing"}`
  - 전제 조건: `status == "page_summarized"`
- `POST /api/books/{id}/extract/book_summary` - 북 서머리 생성 시작 (백그라운드)
  - 응답: `{"status": "processing"}`
  - 전제 조건: `status == "summarized"`
  - 결과: `data/output/book_summaries/{book_title}_report.json` 파일 생성
- `GET /api/books/{id}/pages` - 페이지 엔티티 리스트
  - 응답: `[{"page_number": 1, "structured_data": {...}}, ...]`
- `GET /api/books/{id}/pages/{page_number}` - 페이지 엔티티 상세
- `GET /api/books/{id}/chapters` - 챕터 구조화 리스트
  - 응답: `[{"chapter_id": 1, "structured_data": {...}}, ...]`
- `GET /api/books/{id}/chapters/{chapter_id}` - 챕터 구조화 상세

### 텍스트 정리 (선택적, API 전용)

- `GET /api/books/{id}/text` - 정리된 텍스트 조회
  - 응답: JSON 파일 내용 (챕터별/페이지별 텍스트)
- `POST /api/books/{id}/organize` - 텍스트 정리 실행

---

## 🧪 테스트

### 테스트 파일 구조 및 목적

**⚠️ 중요**: 본 프로젝트는 E2E 테스트만 사용합니다. 실제 서버 실행, 실제 데이터만 사용, Mock 사용 절대 금지.

#### 통합 테스트 파일

**`test_e2e_full_pipeline_unified.py`** (권장 사용)
- **목적**: 전체 파이프라인을 일관된 방식으로 테스트
- **특징**: 
  - 입력 책 리스트만 다르고 처리 과정은 완전히 동일
  - 4권 검증, 1권 테스트, 7.5단계 대량 처리 모두 동일한 함수 사용
  - 캐시 활용 검증 포함
  - 진행률, 소요 시간, 남은 시간 표시
- **테스트 함수**:
  - `test_e2e_full_pipeline_validation`: 이미 완료된 책 검증
  - `test_e2e_new_book_full_pipeline`: 새 책 1권 전체 파이프라인
  - `test_e2e_multiple_books_validation`: 여러 책 검증 (파라미터화)
  - `test_e2e_error_flow_*`: 에러 처리 검증

#### 단계별 테스트 파일

**`test_e2e_pdf_parsing.py`**
- **목적**: PDF 파싱 모듈 단독 테스트
- **검증 항목**: Upstage API 연동, 캐시 저장/재사용, 100페이지 분할 처리

**`test_e2e_structure_analysis.py`**
- **목적**: 구조 분석 모듈 단독 테스트
- **검증 항목**: Footer 기반 경계 탐지, 챕터 탐지, 구조 파일 캐시 재사용

**`test_e2e_extraction.py`**
- **목적**: 엔티티 추출 모듈 단독 테스트
- **검증 항목**: 페이지/챕터 엔티티 추출, 도메인별 스키마, 캐시 재사용

**`test_e2e_text_organizer.py`**
- **목적**: 텍스트 정리 모듈 단독 테스트
- **검증 항목**: 본문 텍스트 추출, JSON 파일 생성

**`test_api_contract.py`**
- **목적**: API 계약 검증
- **검증 항목**: Pydantic 스키마 일치, Enum 값 검증, 필드명/타입 일치

#### 레거시 테스트 파일 (통합 예정)

**`test_e2e_full_pipeline.py`**
- **상태**: `test_e2e_full_pipeline_unified.py`로 통합 예정
- **용도**: 기존 4권 검증 테스트 (통합 후 삭제 예정)

**`test_e2e_new_book_pipeline.py`**
- **상태**: `test_e2e_full_pipeline_unified.py`로 통합 예정
- **용도**: 새 책 1권 테스트 (통합 후 삭제 예정)

### E2E 테스트 실행

```powershell
# 통합 테스트 (권장)
poetry run pytest backend/tests/test_e2e_full_pipeline_unified.py -v -m e2e

# 단계별 테스트
poetry run pytest backend/tests/test_e2e_pdf_parsing.py -v -m e2e
poetry run pytest backend/tests/test_e2e_structure_analysis.py -v -m e2e
poetry run pytest backend/tests/test_e2e_extraction.py -v -m e2e

# API 계약 검증
poetry run pytest backend/tests/test_api_contract.py -v -m e2e

# 전체 E2E 테스트
poetry run pytest backend/tests/ -m e2e -v
```

### 테스트 원칙

⚠️ **중요**: 본 프로젝트는 E2E 테스트만 사용합니다.

- ✅ **실제 서버 실행**: uvicorn 서버를 실제로 띄워서 테스트 (`conftest.py`의 `test_server` fixture)
- ✅ **실제 데이터만 사용**: 실제 PDF, 실제 Upstage API, 실제 OpenAI LLM
- ✅ **Mock 사용 절대 금지**: 프로덕션 플로우와 동일하게 검증
- ✅ **백그라운드 작업 검증**: 실제 서버에서 백그라운드 작업이 실행되는지 확인
- ✅ **캐시 활용 검증**: 각 단계에서 캐시 저장/재사용 확인
- ✅ **진행률 표시**: 페이지/챕터 추출 시 진행률, 소요 시간, 남은 시간 표시
- ❌ **TestClient 사용 금지**: 백그라운드 작업이 제대로 실행되지 않음
- ❌ **DB 직접 조회 금지**: 서버와 테스트가 다른 DB 사용, API 응답만 검증
- ❌ **서비스 직접 호출 금지**: 프로덕션 플로우와 다르므로 금지

### 테스트 샘플 선정

```powershell
# 테스트 샘플 자동 선정 (분야별 1권씩, 챕터 6개 이상)
poetry run python backend/scripts/select_test_samples.py
```

---

## 📊 도메인별 스키마

### 페이지 엔티티 (공통 필드)

- `page_summary`: 2-4문장 요약
- `page_function_tag`: 페이지 기능 (예: "problem_statement", "example_story")
- `persons`: 인물 목록
- `concepts`: 개념 목록
- `events`: 사건 목록
- `examples`: 예시 목록
- `references`: 참고자료 목록
- `key_sentences`: 핵심 문장 (3-5개)
- `tone_tag`: 톤 태그
- `topic_tags`: 주제 태그
- `complexity`: 복잡도

### 도메인별 추가 필드

#### 역사/사회 (history)
- `locations`: 도시, 국가, 지역, 강 등
- `time_periods`: 연대, 세기, 시대
- `polities`: 왕조, 제국, 문명

#### 경제/경영 (economy)
- `indicators`: 경제 지표, 통계, 그래프 요약
- `actors`: 이해관계자 (정부, 기업, 투자자)
- `strategies`: 전략, 원칙, 규칙
- `cases`: 회사, 도시, 산업 사례

#### 인문/자기계발 (humanities)
- `psychological_states`: 정서/심리 상태
- `life_situations`: 구체적 상황 (직장, 가족, 관계)
- `practices`: 추천 습관/행동
- `inner_conflicts`: 내적 갈등/딜레마

#### 과학/기술 (science)
- `technologies`: 핵심 기술
- `systems`: 시스템/프로세스 구조
- `applications`: 적용 영역/사례
- `risks_ethics`: 위험/윤리/정책 이슈

### 챕터 구조화 (공통 필드)

- `core_message`: 한 줄 핵심 메시지
- `summary_3_5_sentences`: 3-5문장 요약
- `argument_flow`: 논증 흐름 (문제, 배경, 주장, 증거, 반론, 결론)
- `key_events`, `key_examples`, `key_persons`, `key_concepts`: 통합된 핵심 요소
- `insights`: 인사이트 (유형, 텍스트, 증거 ID)
- `chapter_level_synthesis`: 챕터 수준 종합
- `references`: 참고자료

---

## 🔧 주요 설정

### 병렬 처리

- **PDF 파싱**: 기본 모드 (10페이지 단위 병렬)
- **엔티티 추출**: ThreadPoolExecutor (workers=3)

### 타임아웃

- **Upstage API**: 120초
- **OpenAI API**: 60초
- **E2E 테스트**: 1800초 (30분)

### 재시도

- **Upstage API**: 최대 3회 (지수 백오프)
- **OpenAI API**: 최대 3회 (지수 백오프)

### 캐시

- **자동 사용**: `use_cache=True` (기본값)
- **파일 해시**: MD5 (PDF), 콘텐츠 해시 (엔티티)
- **안전한 저장**: 임시 파일 → 원자적 이동

### 중간 커밋

- **엔티티 추출**: 10페이지마다 DB 커밋
- **챕터 구조화**: 각 챕터마다 커밋

---

## 📝 프로젝트 구조

```
books-final-processor/
├── backend/
│   ├── api/                    # FastAPI 애플리케이션
│   │   ├── models/             # SQLAlchemy ORM 모델
│   │   │   └── book.py         # Book, Chapter, Page, PageSummary, ChapterSummary
│   │   ├── routers/            # API 라우터
│   │   │   ├── books.py        # 책 관리 API
│   │   │   ├── structure.py    # 구조 분석 API
│   │   │   ├── extraction.py   # 엔티티 추출 API
│   │   │   └── text.py         # 텍스트 정리 API
│   │   ├── schemas/            # Pydantic 스키마
│   │   │   └── book.py         # API 요청/응답 스키마
│   │   ├── services/           # 비즈니스 로직
│   │   │   ├── book_service.py
│   │   │   ├── parsing_service.py
│   │   │   ├── structure_service.py
│   │   │   └── extraction_service.py
│   │   ├── database.py         # DB 설정
│   │   └── main.py             # FastAPI 앱
│   ├── parsers/                # PDF 파싱 모듈
│   │   ├── upstage_api_client.py
│   │   ├── pdf_parser.py
│   │   └── cache_manager.py
│   ├── structure/              # 구조 분석 모듈
│   │   ├── content_boundary_detector.py
│   │   ├── chapter_detector.py
│   │   ├── structure_builder.py
│   │   └── text_organizer.py
│   ├── summarizers/            # 엔티티 추출 모듈
│   │   ├── schemas.py          # 도메인별 Pydantic 스키마
│   │   ├── llm_chains.py       # OpenAI LLM Chains
│   │   ├── page_extractor.py
│   │   ├── chapter_structurer.py
│   │   └── summary_cache_manager.py
│   ├── utils/                  # 유틸리티
│   │   ├── token_counter.py
│   │   ├── csv_parser.py
│   │   └── processed_books_checker.py
│   ├── config/                 # 설정
│   │   └── settings.py
│   ├── scripts/                # 배치 처리 스크립트
│   │   ├── batch_process_books_step_by_step.py
│   │   ├── select_test_samples.py
│   │   └── ...
│   └── tests/                  # E2E 테스트
│       ├── conftest.py         # 테스트 픽스처
│       ├── test_e2e_pdf_parsing.py
│       ├── test_e2e_structure_analysis.py
│       └── test_e2e_extraction.py
├── data/
│   ├── cache/                  # 캐시
│   ├── input/                  # 입력 PDF
│   ├── output/                 # 산출물
│   └── test_results/           # 테스트 로그
├── docs/                       # 문서
│   ├── PRD_books-processor.md  # 제품 요구사항
│   ├── core_logics.md          # 구조 분석 로직 상세 설계
│   └── entity_extraction_guideline.md  # 엔티티 추출 가이드
├── .cursor/rules/              # Cursor 룰
│   ├── backend-api-design.mdc
│   ├── backend-caching.mdc
│   └── ...
├── .env                        # 환경변수 (숨김)
├── .gitignore
├── pyproject.toml              # Poetry 설정
├── AGENTS.md                   # AI 에이전트 운영 가이드
├── TODOs.md                    # 프로젝트 계획
└── README.md                   # 이 파일
```

---

## 🎯 사용 예시

### 1. PDF 업로드 및 파싱

```bash
curl -X POST "http://localhost:8000/api/books/upload" \
  -F "file=@data/input/sample.pdf" \
  -F "title=샘플 도서" \
  -F "author=저자명" \
  -F "category=역사/사회"
```

**응답**:
```json
{
  "book_id": 123,
  "status": "uploaded",
  "message": "PDF parsing started in background"
}
```

### 2. 파싱 완료 확인

```bash
curl "http://localhost:8000/api/books/123"
```

**응답** (파싱 완료 후):
```json
{
  "id": 123,
  "title": "샘플 도서",
  "status": "parsed",
  "page_count": 200
}
```

### 3. 구조 분석

```bash
# 구조 후보 조회
curl "http://localhost:8000/api/books/123/structure/candidates"

# 구조 확정
curl -X POST "http://localhost:8000/api/books/123/structure/final" \
  -H "Content-Type: application/json" \
  -d '{
    "main_start_page": 15,
    "main_end_page": 180,
    "chapters": [
      {"title": "1장", "start_page": 15, "end_page": 50},
      {"title": "2장", "start_page": 51, "end_page": 100}
    ]
  }'
```

### 4. 엔티티 추출

```bash
# 페이지 엔티티 추출 시작
curl -X POST "http://localhost:8000/api/books/123/extract/pages"

# 추출 완료 확인 (status: page_summarized)
curl "http://localhost:8000/api/books/123"

# 챕터 구조화 시작
curl -X POST "http://localhost:8000/api/books/123/extract/chapters"

# 완료 확인 (status: summarized)
curl "http://localhost:8000/api/books/123"

# 결과 조회
curl "http://localhost:8000/api/books/123/pages"
curl "http://localhost:8000/api/books/123/chapters"
```

---

## 🔬 배치 처리

### 대량 도서 처리 (Phase 4)

```powershell
# CSV 파일 기반 대량 처리 (파싱 + 구조 분석 + 텍스트 생성)
poetry run python backend/scripts/batch_process_books_step_by_step.py
```

**처리 대상**: `docs/100권 노션 원본_수정.csv` (87권)

**처리 플로우**:
1. CSV 파일 읽기
2. 이미 처리된 도서 제외
3. PDF 파싱 (캐시 재사용)
4. 구조 분석 (병렬 처리)
5. 텍스트 정리 (병렬 처리)
6. 결과 리포트 생성

---

## 🔍 모니터링 및 진단

### 진행 상황 로깅

엔티티 추출 시 자동으로 다음 정보를 로깅:

**페이지 기준 진행률**:
```
[PROGRESS] Pages: 100 success, 5 failed, 105/388 total (27%) | 
Elapsed: 150.2s | Avg: 1.43s/page | Est. remaining: 404.5s
```

**챕터 기준 진행률**:
```
[PROGRESS] Chapter 3 completed: 챕터 제목 (50/50 pages)
```

**최종 통계**:
```
[EXTRACTION_COMPLETE] Page extraction completed: 
success=383, failed=5, total=388 pages, time=555.3s, avg=1.43s/page

[CHAPTER_STATS] Chapter 1 (제목): 30/30 pages extracted
[CHAPTER_STATS] Chapter 2 (제목): 45/45 pages extracted
...
```

### 진단 스크립트

```powershell
# 배치 처리 결과 검증
poetry run python backend/scripts/verify_batch_processing.py

# 문제 진단 (파싱, 구조, 텍스트)
poetry run python backend/scripts/diagnose_processing_issues.py
```

### 토큰 통계

```powershell
# 전체 책의 토큰 통계 수집
poetry run python backend/scripts/calculate_extraction_tokens.py
```

**출력**:
- `data/output/token_stats/book_{id}_tokens.json`: 책별 통계
- `data/output/reports/`: 전체 통계 리포트

---

## 🔗 참고 문서

- **[PRD](docs/PRD_books-processor.md)**: 제품 요구사항 문서
- **[구조 분석 로직](docs/core_logics.md)**: Footer 기반 휴리스틱 상세 설계
- **[엔티티 추출 가이드](docs/entity_extraction_guideline.md)**: 도메인별 엔티티 추출 작업 지침
- **[선행 서비스](docs/book-assistant_repomix_backend.md)**: 이전 프로젝트 코드 참고
- **[TODOs](TODOs.md)**: Phase별 상세 구현 계획
- **[AGENTS](AGENTS.md)**: AI 에이전트 운영 가이드 (PowerShell 규칙 등)

---

## ⚠️ 주의사항

### PowerShell 환경

- **이모지 사용 금지**: `[OK]`, `[PASS]`, `[FAIL]` 같은 태그 사용
- **명령어 연결**: 세미콜론(`;`) 사용 (Bash `&&` 금지)
- **환경변수**: `$env:VAR_NAME = "value"` 형식
- **파일 확인**: `Get-Content .env` (숨김 파일 확인 시 `-Force` 옵션)

### Git 워크플로우

- **작업 시작 전**: `git status` → `git pull origin main`
- **작업 완료 후**: `git add .` → `git commit -m "[Phase X] 작업 내용"` → `git push origin main`
- **작은 단위로 커밋**: 문제 발생 시 원복 가능하도록

### 데이터베이스

- **프로덕션 DB**: `data/books.db` (실제 파일)
- **테스트 DB**: 서버는 프로덕션 DB 사용
- **DB 직접 조회 금지**: E2E 테스트에서는 API 응답만 검증

### 캐시

- **자동 저장**: API 호출 시 자동으로 캐시 저장
- **재사용**: 같은 파일/콘텐츠는 캐시에서 로드 (API 호출 없음)
- **비용 절감**: Upstage API, OpenAI API 중복 호출 방지

---

## 📈 성능 지표

### Phase 2 (PDF 파싱)
- **병렬 처리**: 기본 모드 (10페이지 단위)
- **성능 향상**: 순차 대비 3-5배 빠름
- **캐시 효과**: 재처리 시 API 호출 0회

### Phase 3 (구조 분석)
- **처리 속도**: 평균 1-2초/권 (캐시 사용 시)
- **정확도**: Ground Truth 기준 90% 이상 (10권 테스트)

### Phase 5 (엔티티 추출)
- **처리 속도**: 평균 1.4초/페이지 (병렬 workers=3)
- **토큰 사용**: 페이지당 약 1074 입력, 2187 출력 (history 도메인)
- **예상 비용**: 페이지당 약 $0.004

---

## 📄 라이선스

MIT License

---

## 👥 기여자

- 개발: [Your Name]
- 문서: [Your Name]

---

## 🆘 문제 해결

### Poetry 설치 오류

```powershell
# Poetry 1.8.5 이상 필수
pip install --upgrade poetry>=1.8.5
```

### 포트 충돌

```powershell
# 포트 8000이 사용 중인 경우
netstat -ano | findstr :8000
taskkill /F /PID [PID번호]
```

### 환경변수 확인

```powershell
# .env 파일 확인 (숨김 파일)
Get-Content .env

# 환경변수 확인
echo $env:OPENAI_API_KEY
Get-ChildItem Env:
```

### 캐시 정리

```powershell
# 캐시 디렉토리 삭제 (재생성 필요 시)
Remove-Item -Recurse -Force data\cache
```

---

## 📚 프로젝트 완료 현황

### Phase 완료 현황 (2025-12-10 기준)

| Phase | 제목 | 상태 |
|-------|------|------|
| Phase 1 | 프로젝트 기초 및 환경 설정 | ✅ 완료 |
| Phase 2 | PDF 파싱 모듈 (Upstage API 연동) | ✅ 완료 |
| Phase 3 | 구조 분석 모듈 | ✅ 완료 |
| Phase 4 | 대량 도서 처리 프레임 단계 | ✅ 완료 |
| Phase 5 | 내용 추출 및 요약 모듈 | ✅ 완료 |
| Phase 6 | Summary 캐시 시각화 및 변환 정교화 | ✅ 완료 |
| Phase 7 | 통합 및 테스트 | ✅ 진행 중 (7.5 완료, 7.6 진행 중) |

### 도서 처리 현황

- **전체 도서**: 87권
- **챕터 6개 이상 완료**: 36권 (100%)
- **부분 완료**: 50권 (챕터 6개 미만 또는 구조 분석만 완료)
- **처리 제외**: 1권 (노이즈 - 이중구조 문제)

**상세 현황**: `docs/books_detailed_list.md` 참고

## 🚧 향후 계획

### Phase 7.6 (진행 중)
- [ ] API 문서 작성 (`docs/API.md`)
- [ ] 코드 주석 보완
- [ ] 테스트 문서 작성 (`docs/TESTING.md`)
- [ ] 프로젝트 완료 검증

### 향후 개선 사항
- [ ] 구조 분석 강화 (챕터 1-2개 세분화)
- [ ] 에러 처리 강화 (부분 실패 허용)
- [ ] 성능 최적화 (비동기 처리 전환)
- [ ] 캐시 정리 기능 (오래된 캐시 자동 삭제)
- [ ] 배포 준비 (Docker, 환경별 설정)

---

**GitHub 저장소**: https://github.com/bluecalif/books-final-processor.git

