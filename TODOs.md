# 도서 PDF 구조 분석 및 서머리 서비스 개발 계획

> PRD: `docs/PRD_books-processor.md`  
> 핵심 로직 참고: `docs/core_logics.md`  
> 선행 서비스 참고: `docs/book-assistant_repomix_backend.md`

## 프로젝트 개요

도서 PDF 파일을 업로드하면 자동으로 책의 구조(본문 시작, 챕터 경계 등)를 파악하고, 페이지별 및 챕터별 서머리를 생성하는 웹 서비스입니다.

**핵심 파이프라인**: `PDF 업로드 → Upstage API 파싱 → 구조 분석(휴리스틱 + LLM) → 페이지/챕터 요약 → SQLite 저장`

## 프로젝트 현재 상황

> 상세 상황: `PROJECT_STATUS.md` 참고

### 전체 진행률: 0% (Phase 1 시작 전)

| Phase | 제목 | 진행률 | 상태 |
|-------|------|-------|------|
| Phase 1 | 프로젝트 기초 및 환경 설정 | 0% | 미시작 |
| Phase 2 | PDF 파싱 모듈 (Upstage API 연동) | 0% | 미시작 |
| Phase 3 | 구조 분석 모듈 | 0% | 미시작 |
| Phase 4 | 요약 모듈 | 0% | 미시작 |
| Phase 5 | 프론트엔드 (Next.js) | 0% | 미시작 |
| Phase 6 | 통합 및 테스트 | 0% | 미시작 |

### 현재 상태 요약
- **백엔드**: 미구현 (backend/ 디렉토리 없음)
- **프론트엔드**: 미구현 (frontend/ 디렉토리 없음)
- **Git 저장소**: 미초기화 (`.git` 디렉토리 없음)
- **문서**: 완료 (TODOs.md, PRD, core_logics.md, AGENTS.md, Cursor rules)

## Git 저장소 정보

**GitHub 저장소**: https://github.com/bluecalif/books-final-processor.git

**⚠️ 중요**: Git 업데이트 및 실행을 안하는 경우가 있으니, 반드시 주의할 것

### Git 워크플로우 (필수)

**Phase 작업 전**: `git status` → `git pull origin main`  
**Phase 작업 완료 후**: `git add .` → `git commit -m "[Phase X] 작업 내용"` → `git push origin main`

## 기술 스택

### 백엔드
- Python 3.10+, FastAPI, SQLAlchemy, SQLite, Poetry, Pydantic

### 프론트엔드
- Next.js 14+ (App Router), TypeScript, Tailwind CSS, shadcn/ui

### 외부 API
- Upstage Document Digitization API, OpenAI API

---

## 프로젝트 구조

```
backend/
├── api/ (models, routers, schemas, services, database.py, main.py)
├── parsers/ (upstage_api_client.py, pdf_parser.py, cache_manager.py)
├── structure/ (structure_builder.py, llm_structure_refiner.py, content_boundary_detector.py, chapter_detector.py)
├── summarizers/ (page_summarizer.py, chapter_summarizer.py, llm_chains.py)
└── config/ (settings.py, constants.py)

frontend/
├── app/ (page.tsx, books/[id]/page.tsx)
├── components/ (BookList.tsx, BookUpload.tsx, StructureViewer.tsx, SummaryViewer.tsx)
├── hooks/ (useBooks.ts, useStructure.ts, useSummary.ts)
└── types/ (api.ts)
```

---

## 데이터 모델 (SQLite)

### books
- `id`, `title`, `author`, `source_file_path`, `page_count`, `status` (enum), `structure_data` (JSON), `created_at`, `updated_at`

### pages
- `id`, `book_id` (FK), `page_number`, `raw_text`, `metadata` (JSON)

### chapters
- `id`, `book_id` (FK), `title`, `order_index`, `start_page`, `end_page`, `section_type`, `created_at`

### page_summaries
- `id`, `book_id` (FK), `page_id` (FK), `page_number`, `summary_text`, `lang`, `created_at`

### chapter_summaries
- `id`, `book_id` (FK), `chapter_id` (FK), `summary_text`, `lang`, `created_at`

---

## 구현 단계

### Phase 1: 프로젝트 기초 및 환경 설정

**목표**: 프로젝트 기본 구조 설정 및 개발 환경 준비

**⚠️ Git 주의사항**: 작업 전 `git status`, `git pull origin main` 확인 / 작업 후 `git add .`, `git commit`, `git push origin main` 실행

#### 1.1 Poetry 프로젝트 초기화
- [ ] `pyproject.toml` 생성 (Python 3.10+)
- [ ] Poetry 버전 확인 (1.8.5 이상 필수)

#### 1.2 필수 패키지 설치
- [ ] 백엔드: `fastapi`, `uvicorn[standard]`, `sqlalchemy`, `pydantic`, `pydantic-settings`, `requests`, `openai`, `python-dotenv`, `python-multipart`, `pypdf`, `beautifulsoup4`
- [ ] 테스트: `pytest`, `pytest-asyncio`, `httpx`, `pytest-cov` (선택)

#### 1.3 SQLite DB 설정
- [ ] `backend/api/database.py` 생성 (SQLAlchemy 엔진/세션, Base 클래스)
- [ ] `backend/api/models/base.py` 생성
- [ ] `backend/api/models/book.py` 생성 (Book, Chapter, PageSummary, ChapterSummary 모델, BookStatus enum)
- [ ] DB 초기화 스크립트 작성

#### 1.4 FastAPI 기본 구조 생성
- [ ] `backend/api/main.py` 생성 (FastAPI 앱, CORS 설정, 라우터 등록)
- [ ] `backend/api/dependencies.py` 생성 (DB 세션 의존성)
- [ ] 기본 헬스체크 엔드포인트 작성

#### 1.5 환경변수 설정
- [ ] `.env` 파일 생성 (`UPSTAGE_API_KEY`, `OPENAI_API_KEY`, `DATABASE_URL`)
- [ ] `backend/config/settings.py` 생성 (Pydantic Settings)

#### 1.6 Git 저장소 설정 (우선순위: 최상)
- [ ] **Git 저장소 초기화** (`git init`)
- [ ] **원격 저장소 연결** (`git remote add origin https://github.com/bluecalif/books-final-processor.git`)
- [ ] `.gitignore` 확인 (`.env`, `*.db`, `*.sqlite`, `poetry.lock`, `node_modules/`)
- [ ] **초기 커밋** (문서 파일들: `git add .`, `git commit -m "docs: 프로젝트 초기 문서 및 계획"`)
- [ ] **원격 저장소 푸시** (`git push -u origin main`)

#### 1.7 테스트 환경 설정
- [ ] 테스트 디렉토리 생성 (`backend/tests/`, `conftest.py`, 테스트 DB 설정)
- [ ] 단위 테스트: DB 모델 (`test_models.py`), Pydantic 스키마 (`test_schemas.py`)
- [ ] 통합 테스트: FastAPI 앱 (`test_main.py` - 헬스체크, CORS)
- [ ] E2E 테스트 준비 (테스트 클라이언트, DB 픽스처)

**검증**: FastAPI 서버 실행 확인, DB 연결 테스트, 모든 단위 테스트 통과

---

### Phase 2: PDF 파싱 모듈 (Upstage API 연동)

**목표**: Upstage API를 사용한 PDF 파싱 기능 구현

#### 2.1 UpstageAPIClient 구현
- [ ] `backend/parsers/upstage_api_client.py` 생성
  - `UpstageAPIClient` 클래스
  - `parse_pdf()`: 100페이지 이하 단일 요청, 100페이지 초과 분할 파싱, 재시도 로직 (기본 3회), Rate limit 처리 (429 에러 시 지수 백오프)
  - **핵심**: 100페이지 분할 로직, 재시도 로직 (지수 백오프)
  - 참고: `docs/book-assistant_repomix_backend.md` (Line 3484-3683)

#### 2.2 PDFParser 구현
- [ ] `backend/parsers/pdf_parser.py` 생성
  - `PDFParser` 클래스
  - `parse_pdf(file_path, use_cache=True)`: 캐시 확인 → API 호출 → Elements 구조화 → 페이지/요소 정규화
  - **핵심**: `_structure_elements()` - BeautifulSoup로 HTML 파싱, regex로 font_size 추출, bbox 계산
- [ ] `backend/parsers/cache_manager.py` 생성 (선택)

#### 2.3 업로드 API 구현
- [ ] `backend/api/routers/books.py` 생성
  - `POST /api/books/upload`: 파일 업로드 받기 → 저장 → DB 레코드 생성 (status: `uploaded`) → `book_id` 반환
- [ ] `backend/api/services/book_service.py` 생성 (파일 저장, DB 레코드 생성)
- [ ] 백그라운드 작업 큐 설정 (선택: Celery 또는 FastAPI BackgroundTasks)

#### 2.4 PDF 파싱 모듈 테스트
- [ ] **단위 테스트** (모킹 허용):
  - UpstageAPIClient: `_get_pdf_page_count()`, `_parse_single_pdf()` 모킹, 100페이지 분기, 재시도 로직, Rate limit
  - PDFParser: `_structure_elements()`, `_extract_text_from_html()`, `_extract_font_size()`, `_calculate_bbox()`, 캐시
- [ ] **통합 테스트**:
  - PDFParser + UpstageAPIClient: 실제 PDF 파일 사용, API 응답 구조/Elements 구조화/페이지 그룹화 검증
  - 업로드 API: 파일 업로드, DB 레코드 생성, 파일 저장, 에러 처리
- [ ] **E2E 테스트** (⚠️ 실제 데이터만):
  - 실제 Upstage API 연동: PDF 업로드 → 파싱 → DB 저장 전체 플로우, 상태 변경 검증, Pages 테이블 데이터 검증
  - 100페이지 초과 PDF: 분할 파싱 동작, 페이지 번호 조정, Elements 병합 검증
- [ ] 에러 케이스: Upstage API 실패, 네트워크 에러, 파일 읽기 실패

**검증**: 단위/통합/E2E 테스트 통과 (⚠️ E2E는 실제 Upstage API 연동, Mock 사용 금지)

**⚠️ Git 커밋**: Phase 2 완료 후 `git add .`, `git commit -m "[Phase 2] PDF 파싱 모듈 구현"`, `git push origin main`

---

### Phase 3: 구조 분석 모듈

**목표**: 책의 구조(본문 시작, 챕터 경계)를 자동으로 파악하는 모듈 구현

#### 3.1 StructureBuilder 구현 (휴리스틱 기반)
- [ ] `backend/structure/content_boundary_detector.py` 생성
  - `ContentBoundaryDetector`: `detect_boundaries()` - 키워드 기반 경계 탐지 ("차례", "contents", "참고문헌", "index", "부록" 등), `start/main/end` 반환
- [ ] `backend/structure/chapter_detector.py` 생성
  - `ChapterDetector`: `detect_chapters()` - 페이지 상단 요소 분석 (y0, font_size), 챕터 패턴 인식 ("제1장", "CHAPTER 1" 등), 챕터 시작/끝 페이지 계산
- [ ] `backend/structure/structure_builder.py` 생성
  - `StructureBuilder`: `build_structure(parsed_data)` - 경계 탐지 → 챕터 탐지 → 최종 구조 JSON 생성
  - 참고: `docs/book-assistant_repomix_backend.md` (Line 5448-5538)

#### 3.2 LLMStructureRefiner 구현 (core_logics.md)
- [ ] `backend/structure/llm_structure_refiner.py` 생성
  - `LLMStructureRefiner` 클래스
  - Pydantic 모델: `LLMChapterSuggestion`, `LLMStructureSuggestion`
  - `_build_page_toplines_chain()`: 각 페이지 상단 50글자 추출, "p{page_number}: {text}" 형식 (참고: `core_logics.md` Line 244-268)
  - `_build_context_for_llm()`: 글로벌 정보, 샘플 페이지, 챕터 후보, page_toplines_chain (참고: Line 280-328)
  - `_build_prompt()`: 시스템 프롬프트, JSON 스키마 명시 (참고: Line 344-417)
  - `refine_structure()`: LLM 호출 (OpenAI API), 응답 파싱 및 Pydantic 검증

#### 3.3 구조 분석 API 구현
- [ ] `backend/api/routers/structure.py` 생성
  - `GET /api/books/{id}/structure/candidates`: 휴리스틱 구조 + LLM 보정 구조 반환 (참고: `core_logics.md` Line 447-498)
  - `POST /api/books/{id}/structure/final`: `FinalStructureInput` 받아서 최종 구조 DB 저장, Chapter 테이블 재생성 (참고: Line 501-711)
- [ ] `backend/api/schemas/structure.py` 생성 (`FinalStructureInput`, `FinalChapterInput`)
- [ ] `backend/api/services/structure_service.py` 생성 (`apply_final_structure()`)

#### 3.4 구조 분석 모듈 테스트
- [ ] **단위 테스트** (모킹 허용):
  - ContentBoundaryDetector: `detect_boundaries()`, START/END_KEYWORDS 매칭, 경계 탐지
  - ChapterDetector: `detect_chapters()`, CHAPTER_PATTERNS 매칭, 페이지 상단 요소 분석
  - StructureBuilder: `build_structure()` 파이프라인, 경계/챕터 탐지 연계
  - LLMStructureRefiner: `_build_page_toplines_chain()`, `_build_context_for_llm()`, `refine_structure()` (OpenAI API 모킹)
- [ ] **통합 테스트**:
  - StructureBuilder + PDFParser: 실제 파싱 데이터로 구조 분석, 정합성 검증
  - 구조 분석 API: `GET /api/books/{id}/structure/candidates` (휴리스틱/LLM 보정 구조), `POST /api/books/{id}/structure/final` (DB 저장, Chapter 재생성, 상태 변경)
- [ ] **E2E 테스트** (⚠️ 실제 데이터만):
  - 전체 구조 분석 플로우: PDF 업로드 → 파싱 → 구조 분석, 휴리스틱/LLM 보정 구조 생성, 최종 구조 확정 및 DB 저장
  - 다양한 PDF 형식: 한국어/영어 책, 다양한 챕터 구조

**검증**: 단위/통합/E2E 테스트 통과 (⚠️ E2E는 실제 PDF, 실제 Upstage API, 실제 LLM 사용, Mock 사용 금지)

**⚠️ Git 커밋**: Phase 3 완료 후 `git add .`, `git commit -m "[Phase 3] 구조 분석 모듈 구현"`, `git push origin main`

---

### Phase 4: 요약 모듈

**목표**: 페이지별 및 챕터별 서머리 생성 기능 구현

#### 4.1 PageSummarizer 구현
- [ ] `backend/summarizers/page_summarizer.py` 생성
  - `PageSummarizer`: `summarize_page(page_text, book_context=None)` - LLM에 전달, 2~4문장 또는 bullet 형태, 토큰 제한 고려
- [ ] `backend/summarizers/llm_chains.py` 생성 (LLM 호출 공통 로직, 프롬프트 템플릿, 모델/온도/토큰 설정)

#### 4.2 ChapterSummarizer 구현
- [ ] `backend/summarizers/chapter_summarizer.py` 생성
  - `ChapterSummarizer`: `summarize_chapter(chapter_pages, page_summaries)` - 옵션 A: 챕터 원문 직접 요약 / 옵션 B: 페이지 요약 집계 (권장), 1~3단락

#### 4.3 요약 API 구현
- [ ] `backend/api/routers/summary.py` 생성
  - `GET /api/books/{id}/pages`: 페이지별 요약 리스트
  - `GET /api/books/{id}/chapters`: 챕터별 요약 리스트
  - `GET /api/books/{id}/chapters/{chapter_id}`: 챕터 상세 (요약 + 페이지 리스트)
- [ ] `backend/api/services/summary_service.py` 생성 (요약 생성 비즈니스 로직, 백그라운드 작업, 상태 업데이트)

#### 4.4 요약 모듈 테스트
- [ ] **단위 테스트** (모킹 허용):
  - PageSummarizer: `summarize_page()` (LLM 모킹), 긴 텍스트 자르기, 요약 형식 검증
  - ChapterSummarizer: `summarize_chapter()` (페이지 요약 집계), 옵션 A/B 테스트
  - LLM Chains: 프롬프트 템플릿, 모델/온도/토큰 설정, 에러 처리
- [ ] **통합 테스트**:
  - SummaryService: `summarize_pages()` (본문 페이지만 필터링, DB 저장, 상태 변경), `summarize_chapters()` (페이지 요약 조회, DB 저장, 상태 변경)
  - 요약 API: `GET /api/books/{id}/pages`, `GET /api/books/{id}/chapters`, `GET /api/books/{id}/chapters/{chapter_id}`, 백그라운드 작업
- [ ] **E2E 테스트** (⚠️ 실제 데이터만):
  - 전체 요약 생성 플로우: 구조 확정된 책 → 페이지 요약 (실제 OpenAI API) → 챕터 요약, DB 저장 검증, 상태 변경 검증
  - 실제 LLM 연동: OpenAI API 호출 검증, 요약 품질 검증, API 에러 처리 검증
- [ ] 성능 테스트 (선택): 여러 페이지 병렬 요약, 대용량 챕터 요약

**검증**: 단위/통합/E2E 테스트 통과 (⚠️ E2E는 실제 LLM 연동, 실제 요약 생성, Mock 사용 금지)

**⚠️ Git 커밋**: Phase 4 완료 후 `git add .`, `git commit -m "[Phase 4] 요약 모듈 구현"`, `git push origin main`

---

### Phase 5: 프론트엔드 (Next.js)

**목표**: 사용자 인터페이스 구현

#### 5.1 Next.js 프로젝트 설정
- [ ] Next.js 14+ 초기화 (TypeScript, App Router, Tailwind CSS)
- [ ] shadcn/ui 설치 및 기본 컴포넌트 추가 (Button, Card, Input, Progress, Tabs)
- [ ] API 타입 정의 (`frontend/types/api.ts` - 백엔드 API 응답 타입)

#### 5.2 책 목록 페이지
- [ ] `frontend/app/page.tsx` 구현 (책 리스트, 업로드 버튼)
- [ ] `frontend/components/BookList.tsx` 구현 (책 카드, 제목/상태/업로드일)
- [ ] `frontend/hooks/useBooks.ts` 구현 (`GET /api/books`, React Query 또는 SWR)

#### 5.3 책 업로드 기능
- [ ] `frontend/components/BookUpload.tsx` 구현 (파일 선택, 업로드 진행률, 드래그 앤 드롭)
- [ ] `POST /api/books/upload` 연동 (업로드 완료 후 상세 페이지 이동, 처리 상태 폴링)

#### 5.4 책 상세 페이지
- [ ] `frontend/app/books/[id]/page.tsx` 구현 (책 메타정보)
- [ ] `frontend/components/StructureViewer.tsx` 구현 (좌측: 챕터 구조 트리, 우측: 요약 표시)
- [ ] `frontend/components/SummaryViewer.tsx` 구현 (챕터 요약, 페이지별 요약 리스트)
- [ ] `frontend/components/PageViewer.tsx` 구현 (선택: 페이지 원문 표시)

#### 5.5 인터랙티브 구조 분석 UI (core_logics.md)
- [ ] 구조 후보 선택 UI (휴리스틱 vs LLM 보정 구조 탭, `GET /api/books/{id}/structure/candidates`)
- [ ] 페이지 뷰어 통합 (페이지 좌우 넘기기, "본문 시작" 버튼 → `mainStartPage` 기록, "챕터 시작" 버튼 → `chapterStartPages` 토글, 참고: `core_logics.md` Line 508-552)
- [ ] 최종 구조 확정 (`StructureSelectionState` 관리, "구조 확정" 버튼 → `POST /api/books/{id}/structure/final`, 구조 트리 업데이트)

**검증**: 전체 UI 플로우 테스트 (업로드 → 구조 분석 → 요약 조회)

---

### Phase 6: 통합 및 테스트

**목표**: 전체 파이프라인 통합 및 품질 향상

#### 6.1 백엔드 전체 파이프라인 E2E 테스트 (필수 완료)

**⚠️ 중요: 모든 E2E 테스트는 Mock 사용 금지, 실제 데이터만 사용** (실제 PDF, 실제 Upstage API, 실제 OpenAI LLM, 실제 DB)

- [ ] **Phase 1-4 단계별 테스트 검증** (모든 단위/통합 테스트 통과 확인)
- [ ] **전체 플로우 E2E 테스트** (`tests/test_e2e.py`):
  - 1. `POST /api/books/upload` → 책 생성 (`uploaded`)
  - 2. 실제 Upstage API로 PDF 파싱 → `parsed` 상태 확인
  - 3. `GET /api/books/{id}/structure/candidates` → 실제 LLM으로 구조 후보 생성
  - 4. `POST /api/books/{id}/structure/final` → 구조 확정 (`structured`)
  - 5. `POST /api/books/{id}/summarize/pages` → 실제 LLM으로 페이지 요약 (`page_summarized`)
  - 6. `POST /api/books/{id}/summarize/chapters` → 실제 LLM으로 챕터 요약 (`summarized`)
  - 7-9. 최종 결과 조회 검증 (`GET /api/books/{id}`, `/pages`, `/chapters`)
  - 각 단계별 데이터 정합성 검증 (DB 레코드, 관계, 상태 변경 순서)
- [ ] **다양한 시나리오 E2E 테스트** (실제 PDF 파일 및 실제 API 사용):
  - 다양한 형식의 실제 PDF (단면/양면 스캔, 한국어/영어, 다양한 챕터 구조)
  - 엣지 케이스 (작은 PDF, 큰 PDF 100페이지 초과, 챕터 없는 책, 구조 불명확한 책)
- [ ] **API 계약 검증** (`tests/test_api_contract.py`): 모든 API 엔드포인트 응답 스키마, Pydantic 스키마와 실제 응답 일치, Enum 값 정합성, 필드명/타입 일치
- [ ] **에러 플로우 E2E 테스트**: 실제 Upstage API/LLM 실패 시나리오, 파일 형식 에러 처리

#### 6.2 에러 처리 강화
- [ ] Upstage API 실패 처리 (네트워크 에러, Rate limit, `error_parsing` 상태 업데이트, 에러 로그 저장)
- [ ] LLM 요약 실패 처리 (`error_summarizing` 상태, 부분 실패 처리)
- [ ] 재시도 로직 개선 (지수 백오프, 최대 재시도 횟수 제한)

#### 6.3 성능 최적화
- [ ] 페이지 요약 병렬 처리 (asyncio 또는 멀티프로세싱, 배치 처리)
- [ ] 캐싱 전략 개선 (파싱 결과 캐싱, 요약 결과 캐싱)
- [ ] DB 쿼리 최적화 (인덱스 추가, N+1 쿼리 방지)

#### 6.4 문서화
- [ ] API 문서 작성 (FastAPI 자동 생성)
- [ ] README.md 작성 (프로젝트 소개, 설치/실행 방법, 환경변수 설정, 테스트 실행 방법)
- [ ] 코드 주석 보완
- [ ] 테스트 문서 작성 (테스트 구조, E2E 테스트 실행 방법, 테스트 데이터 준비)

#### 6.5 백엔드 테스트 완료 검증 (프론트엔드 연동 전 필수)
- [ ] **테스트 커버리지 확인**: 전체 80% 이상 (핵심 로직 100%), 핵심 모듈 90% 이상 (UpstageAPIClient 100%, PDFParser/StructureBuilder/SummaryService 90%+)
- [ ] **모든 테스트 통과 확인**: 단위/통합/E2E 테스트 모두 통과, `pytest --cov=backend tests/` 실행 결과 확인
- [ ] **API 계약 문서화**: OpenAPI 스키마 생성 (`/openapi.json`), 프론트엔드 참고용 API 문서, 요청/응답 예시
- [ ] **테스트 리포트 생성**: 테스트 실행 결과 리포트, 커버리지 리포트, 실패 테스트 확인

**백엔드 E2E 테스트 완료 기준**:
- ✅ Phase 1-4 모든 단계별 테스트 통과
- ✅ 전체 플로우 E2E 테스트 통과 (최소 3가지 시나리오, ⚠️ 실제 데이터 사용 필수: 실제 PDF, 실제 Upstage API, 실제 OpenAI LLM, Mock 사용 금지)
- ✅ API 계약 검증 통과
- ✅ 테스트 커버리지 목표 달성
- ✅ 에러 플로우 테스트 통과

**⚠️ E2E 테스트 필수 원칙**: Mock 사용 절대 금지, 실제 외부 API 연동, 실제 PDF 파일 사용, 실제 DB 데이터 검증

**검증**: 백엔드 단독으로 모든 기능이 실제 데이터로 정상 작동함을 E2E 테스트로 확인, 프론트엔드 연동 전 백엔드 완성도 검증 완료

**⚠️ Git 커밋**: Phase 6 완료 후 `git add .`, `git commit -m "[Phase 6] 백엔드 E2E 테스트 완료 및 통합 검증"`, `git push origin main`

---

## 주요 참고 문서

- `docs/PRD_books-processor.md`: 제품 요구사항 문서
- `docs/core_logics.md`: 구조 분석 로직 상세 설계 (LLMStructureRefiner, Human-in-the-loop)
- `docs/book-assistant_repomix_backend.md`: 선행 서비스 코드 참고 (UpstageAPIClient, PDFParser, StructureBuilder)

## 주의사항

1. **상태 관리**: `uploaded → parsed → structured → page_summarized → summarized` 순서로 진행
2. **SQLite → Supabase 전환 고려**: DB 추상화 레이어를 두어 추후 전환 용이하도록 설계
3. **⚠️ 실제 데이터 테스트 필수 (E2E 테스트)**: Mock 사용 절대 금지, 실제 PDF 파일, 실제 Upstage API, 실제 OpenAI LLM, 실제 DB 데이터 검증 (단위/통합은 모킹 허용, E2E는 반드시 실제 데이터)
4. **⚠️ Git 버전 관리 필수**: Git 업데이트 및 실행을 안하는 경우가 있으니 반드시 주의, 각 Phase 완료 후 커밋 및 푸시, 작업 전 `git status`, `git pull origin main` 확인, 커밋 메시지: `[Phase X] 작업 내용: 상세 설명`, GitHub 저장소: https://github.com/bluecalif/books-final-processor.git
5. **이모지 사용 금지**: PowerShell 환경 고려
6. **Poetry 1.8.5 이상 필수**: 메타데이터 버전 2.4 지원
7. **AGENTS.md 규칙 준수**: PowerShell 명령어, 환경변수 관리, 프로젝트 실행 규칙 등
