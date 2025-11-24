# 도서 PDF 구조 분석 및 서머리 서비스 개발 계획

> PRD: `docs/PRD_books-processor.md`  
> 핵심 로직 참고: `docs/core_logics.md`  
> 선행 서비스 참고: `docs/book-assistant_repomix_backend.md`

## 프로젝트 개요

도서 PDF 파일을 업로드하면 자동으로 책의 구조(본문 시작, 챕터 경계 등)를 파악하고, 페이지별 및 챕터별 서머리를 생성하는 웹 서비스입니다.

**핵심 파이프라인**: `PDF 업로드 → Upstage API 파싱 → 구조 분석(휴리스틱 + LLM) → 페이지/챕터 요약 → SQLite 저장`

## 프로젝트 현재 상황

> 상세 상황: `PROJECT_STATUS.md` 참고

### 전체 진행률: 약 50% (Phase 1, Phase 2 완료)

| Phase | 제목 | 진행률 | 상태 |
|-------|------|-------|------|
| Phase 1 | 프로젝트 기초 및 환경 설정 | 100% | 완료 |
| Phase 2 | PDF 파싱 모듈 (Upstage API 연동) | 100% | **완료** (참고 파일 기반 재구현, E2E 테스트 통과) |
| Phase 3 | 구조 분석 모듈 | 0% | **대기** (Phase 2 완료 후 시작) |
| Phase 4 | 요약 모듈 | 0% | 미시작 |
| Phase 5 | 프론트엔드 (Next.js) | 0% | 미시작 |
| Phase 6 | 통합 및 테스트 | 0% | 미시작 |

### 현재 상태 요약
- **백엔드**: 
  - Phase 1 완료: 기본 구조, DB 설정, FastAPI 기본 구조, 테스트 환경 설정
  - Phase 2 재구현 필요 (0%):
    - **작업 방식 변경**: 참고 파일 기반으로 재구현
    - 기존 프로젝트의 PDF 파싱 관련 파일을 `_REF` 접미사로 참고 파일 추가
    - 참고 파일을 기반으로 현재 프로젝트 구조에 맞게 재구현
    - 변수명/함수명/클래스명을 현재 프로젝트 규칙에 맞게 Align
    - 캐싱 시스템 통합 필수 (`CacheManager` 사용)
    - E2E 테스트 환경 설정 완료: `conftest_e2e.py` (실제 서버 실행), `test_e2e_pdf_parsing.py` 생성
  - Phase 3 대기: Phase 2 완료 후 시작 예정
- **프론트엔드**: 미구현 (frontend/ 디렉토리 없음)
- **Git 저장소**: 초기화 완료 (변경사항 커밋 대기 중)
- **문서**: 완료 (TODOs.md, PRD, core_logics.md, AGENTS.md, Cursor rules)
- **테스트**: E2E 테스트 환경 설정 완료 (실제 서버 실행 방식, `conftest_e2e.py`, `httpx.Client` 사용)

## Git 저장소 정보

**GitHub 저장소**: https://github.com/bluecalif/books-final-processor.git

**⚠️ 중요**: Git 업데이트 및 실행을 안하는 경우가 있으니, 반드시 주의할 것

### Git 워크플로우 (필수)

**⚠️ 중요: 작은 단위로 커밋하여 문제 발생 시 원복 가능하도록**

**Phase 작업 전**: `git status` → `git pull origin main`  
**Phase 작업 중**: 각 단계 완료 후 즉시 커밋 (작은 단위로 커밋)
**Phase 작업 완료 후**: `git add .` → `git commit -m "[Phase X] 작업 내용"` → `git push origin main`

**커밋 메시지 규칙**: `[Phase X] 작업 단계: 상세 설명` (예: `[Phase 2] 참고 파일 추가: UpstageAPIClient_REF.py`)

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
- [x] 테스트 디렉토리 생성 (`backend/tests/`, `conftest_e2e.py`, 실제 서버 실행 fixture) ✅ 완료
- [x] E2E 테스트 환경 설정 (실제 서버 실행, `httpx.Client` 사용) ✅ 완료

**검증**: FastAPI 서버 실행 확인, DB 연결 테스트, E2E 테스트 환경 확인

---

### Phase 2: PDF 파싱 모듈 (Upstage API 연동)

**✅ 현재 상태**: **완료** (참고 파일 기반 재구현 완료, E2E 테스트 통과, 캐싱 시스템 정상 작동)

**목표**: Upstage API를 사용한 PDF 파싱 기능 구현

**⚠️ 작업 방식**: **참고 파일 기반 구현**
- 기존 프로젝트의 PDF 파싱 관련 파일을 `_REF` 접미사를 붙여 참고 파일로 추가
- 참고 파일을 기반으로 현재 프로젝트 구조에 맞게 재구현
- 변수명/함수명/클래스명을 현재 프로젝트 규칙에 맞게 Align
- 캐싱 시스템 통합 필수 (`CacheManager` 사용)

**⚠️ Git 주의사항**: 
- **작업 전**: `git status` → `git pull origin main` 확인
- **작업 중**: 각 단계 완료 후 즉시 커밋 (작은 단위로 커밋하여 문제 발생 시 원복 가능하도록)
- **작업 후**: `git add .` → `git commit -m "[Phase 2] 작업 내용"` → `git push origin main`
- **커밋 메시지 규칙**: `[Phase 2] 작업 단계: 상세 설명` (예: `[Phase 2] 참고 파일 추가: UpstageAPIClient_REF.py`)
- **원복 가능하도록**: 각 단계별로 커밋하여 문제 발생 시 이전 단계로 쉽게 원복 가능

**⚠️ 참고 파일 방식 주의사항**:
1. **참고 파일 위치**: `docs/reference_code/parsers/` 디렉토리에 `_REF` 접미사 파일 추가
2. **변수명/함수명 Align**: 현재 프로젝트 규칙에 맞게 통일 (snake_case, 의미 있는 이름)
3. **캐싱 시스템 통합**: 모든 파싱 로직에 `CacheManager` 통합 필수
4. **설정 관리**: `backend/config/settings.py`의 `Settings` 클래스 사용
5. **로깅 형식**: `[INFO]`, `[ERROR]` 형식 사용 (이모지 사용 금지)
6. **단계별 검증**: 각 단계 완료 후 E2E 테스트 실행 및 캐시 저장 검증

#### 2.0 PDF 입력 파일 디렉토리 설정
- [x] `data/input/` 디렉토리 생성 (사용자가 직접 넣는 테스트용 PDF 파일) ✅ 완료
- [x] `.gitignore`에 `data/input/*.pdf` 추가 (실제 PDF 파일은 커밋 제외) ✅ 완료
- [x] `data/input/.gitkeep` 파일 생성 (빈 디렉토리 유지) ✅ 완료
- [x] `backend/config/settings.py`에 `input_dir` 경로 추가 ✅ 완료

#### 2.1 참고 파일 추가 및 분석
- [x] **Git 작업 전**: `git status` → `git pull origin main` 확인 ✅
- [x] `docs/reference_code/parsers/` 디렉토리 생성 ✅
- [x] 기존 프로젝트의 PDF 파싱 관련 파일 확인 및 목록 작성 ✅
- [x] 참고 파일 추가 (`_REF` 접미사 사용): ✅
  - `upstage_api_client_REF.py`: Upstage API 클라이언트 참고 파일 ✅
  - `pdf_parser_REF.py`: PDF 파서 참고 파일 ✅
  - `cache_manager_REF.py`: 캐시 매니저 참고 파일 (캐싱 로직 참고) ✅
- [x] 참고 파일 상단에 주석 추가: ✅
  - 출처 (기존 프로젝트명/경로) ✅
  - 참고 목적 ✅
  - 주요 차이점 예상 사항 ✅
- [x] 기능 분석 및 현재 프로젝트 구조 매핑: ✅
  - 클래스명, 함수명, 변수명 매핑 테이블 작성 (`ALIGN_PLAN.md`) ✅
  - 현재 프로젝트 규칙과의 차이점 정리 ✅
  - Align 계획 수립 ✅
  - 캐싱 로직 분석 및 통합 계획 수립 ✅
- [x] **Git 커밋**: `git add .` → `git commit -m "[Phase 2] 참고 파일 추가 및 분석 완료"` → `git push origin main` ✅

#### 2.2 UpstageAPIClient 재구현 (참고 파일 기반)
- [x] **Git 작업 전**: `git status` → `git pull origin main` 확인 ✅
- [x] `backend/parsers/upstage_api_client.py` 재구현 (참고 파일 기반) ✅
  - 참고 파일 분석 및 기능 이해 ✅
  - 변수명/함수명을 현재 프로젝트 규칙에 맞게 Align ✅
  - `UpstageAPIClient` 클래스 구현 ✅
  - `parse_pdf()`: 100페이지 이하 단일 요청, 100페이지 초과 분할 파싱, 재시도 로직 (기본 3회), Rate limit 처리 (429 에러 시 지수 백오프) ✅
  - `_get_pdf_page_count()`: pypdf로 PDF 페이지 수 확인 ✅
  - `_split_pdf()`: PDF를 특정 페이지 범위로 분할 ✅
  - `_parse_pdf_in_chunks()`: 100페이지씩 분할하여 파싱, Elements 병합, 페이지 번호 조정 ✅
  - `_parse_single_pdf()`: 단일 PDF 파싱, 재시도 로직, Rate limit 처리 ✅
  - **핵심**: 100페이지 분할 로직, 재시도 로직 (지수 백오프) ✅
  - **설정 관리**: `backend/config/settings.py`의 `Settings` 클래스 사용 ✅
  - **로깅**: `[INFO]`, `[ERROR]` 형식 사용 (이모지 사용 금지) ✅
- [x] 단계별 검증: 기본 기능 동작 확인 (코드 검토 완료) ✅
- [x] **Git 커밋**: `git add .` → `git commit -m "[Phase 2] UpstageAPIClient 재구현 완료"` → `git push origin main` ✅

#### 2.3 CacheManager 재구현 (참고 파일 기반, 캐싱 시스템 핵심)
- [x] **Git 작업 전**: `git status` → `git pull origin main` 확인 ✅
- [x] `backend/parsers/cache_manager.py` 재구현 (참고 파일 기반) ✅
  - 참고 파일 분석 및 기능 이해 ✅
  - 변수명/함수명을 현재 프로젝트 규칙에 맞게 Align ✅
  - `CacheManager` 클래스 구현 ✅
  - `get_file_hash()`: PDF 파일의 MD5 해시 생성 (청크 단위로 읽어서 메모리 효율적 처리) ✅
  - `get_cache_key()`: 파일 내용 기반 캐시 키 생성 (파일 해시 기반) ✅
  - `get_cache_path()`: 캐시 파일 경로 생성 ✅
  - `is_cache_valid()`: 캐시 유효성 확인 ✅
  - `get_cached_result()`: 캐시된 결과 조회 ✅
  - `save_cache()`: 결과를 캐시에 저장 (임시 파일로 안전하게 저장 후 원자적 이동) ✅
  - `invalidate_cache()`: 특정 캐시 무효화 ✅
  - `invalidate_cache_for_file()`: 특정 파일의 캐시 무효화 ✅
  - `cleanup_old_cache()`: 오래된 캐시 파일 정리 ✅
  - `get_cache_stats()`: 캐시 통계 정보 ✅
  - **핵심**: 파일 해시 기반 캐시 키 (같은 파일이면 경로 무관하게 재사용) ✅
  - **캐시 저장 위치**: `data/cache/upstage/` (설정: `settings.cache_dir / "upstage"`) ✅
  - **설정 관리**: `backend/config/settings.py`의 `Settings` 클래스 사용 ✅
  - **로깅**: `[INFO]`, `[ERROR]`, `[CACHE_SAVE]` 형식 사용 (이모지 사용 금지) ✅
  - **안전한 저장**: 임시 파일로 저장 후 원자적 이동 (파일 손상 방지) ✅
  - **예외 처리**: 캐시 저장 실패해도 파싱 계속 진행 ✅
- [x] 단계별 검증: 캐시 저장/로드 동작 확인 (코드 검토 및 Sequential Thinking 분석 완료) ✅
- [x] **Git 커밋**: `git add .` → `git commit -m "[Phase 2] CacheManager 재구현 완료"` → `git push origin main` ✅

#### 2.4 PDFParser 재구현 (참고 파일 기반, 캐싱 통합 필수)
- [x] **Git 작업 전**: `git status` → `git pull origin main` 확인 ✅
- [x] `backend/parsers/pdf_parser.py` 재구현 (참고 파일 기반) ✅
  - 참고 파일 분석 및 기능 이해 ✅
  - 변수명/함수명을 현재 프로젝트 규칙에 맞게 Align ✅
  - `PDFParser` 클래스 구현 ✅
  - `__init__()`: `CacheManager` 초기화 (캐시 매니저 통합) ✅
  - `parse_pdf(file_path, use_cache=True, force_split=True)`: **캐시 확인 → API 호출 → Elements 구조화 → 양면 분리 → 캐시 저장** (순서 필수) ✅
  - `_structure_elements()`: API 응답 elements를 표준 형식으로 변환 ✅
  - `_extract_text_from_html()`: BeautifulSoup로 HTML에서 텍스트 추출 ✅
  - `_extract_font_size()`: regex로 HTML에서 font-size 추출 ✅
  - `_calculate_bbox()`: 좌표 배열에서 bbox 계산 (x0, y0, x1, y1, width, height) ✅
  - `_split_pages_by_side()`: 양면 분리 로직 (참고 파일과 동일하게 구현) ✅
  - `_clean_pages()`: clean_output 로직 (참고 파일과 동일하게 구현) ✅
  - **핵심**: BeautifulSoup로 HTML 파싱, regex로 font_size 추출, bbox 계산 ✅
  - **캐싱 시스템 통합 필수**: `CacheManager` 사용, 캐시 확인 → API 호출 → 캐시 저장 플로우 구현 ✅
    - 캐시 히트 시: 캐시된 API 응답을 구조화하여 반환 ✅
    - 캐시 미스 시: API 호출 → 구조화 → 양면 분리 → 캐시 저장 ✅
  - **양면 분리**: `force_split=True` 기본값으로 항상 실행 ✅
  - **clean_output**: `clean_output=True` 기본값으로 불필요한 필드 제거 ✅
  - **설정 관리**: `backend/config/settings.py`의 `Settings` 클래스 사용 ✅
  - **로깅**: `[INFO]`, `[ERROR]` 형식 사용 (이모지 사용 금지) ✅
- [x] 단계별 검증: 캐시 저장 동작 확인 (코드 검토 완료, E2E 테스트에서 최종 검증 예정) ✅
- [x] **Git 커밋**: `git add .` → `git commit -m "[Phase 2] PDFParser 재구현 완료 (캐싱 통합)"` → `git push origin main` ✅

#### 2.5 업로드 API 구현
- [x] `backend/api/schemas/book.py` 생성
  - `BookCreate`: 업로드 요청 스키마 ✅ 완료
  - `BookResponse`: 책 응답 스키마 ✅ 완료
  - `BookListResponse`: 책 리스트 응답 스키마 ✅ 완료
- [x] `backend/api/routers/books.py` 생성
  - `POST /api/books/upload`: 파일 업로드 받기 → 저장 → DB 레코드 생성 (status: `uploaded`) → `book_id` 반환 ✅ 완료
  - `GET /api/books`: 책 리스트 조회 (페이지네이션, 상태 필터) ✅ 완료
  - `GET /api/books/{book_id}`: 책 상세 조회 ✅ 완료
- [x] `backend/api/services/book_service.py` 생성
  - `create_book()`: 파일 저장, DB 레코드 생성 ✅ 완료
  - `get_book()`: 책 조회 ✅ 완료
  - `get_books()`: 책 리스트 조회 ✅ 완료
- [x] `backend/api/main.py`에 books 라우터 등록 ✅ 완료
- [x] 백그라운드 작업 구현: `backend/api/services/parsing_service.py` 생성, `BackgroundTasks`로 자동 파싱 ✅ 완료

#### 2.6 PDF 파싱 모듈 테스트
- [x] **E2E 테스트 환경 설정**:
  - `backend/tests/conftest.py` 생성 (실제 서버 실행 fixture) ✅ 완료
  - `backend/tests/test_e2e_pdf_parsing.py` 생성 (실제 서버 실행, `httpx.Client` 사용) ✅ 완료
- [x] **Git 작업 전**: `git status` → `git pull origin main` 확인 ✅ 완료
- [x] **E2E 테스트 실행 및 검증** (⚠️ 실제 서버 실행, 실제 데이터만): ✅ 완료
  - 실제 Upstage API 연동, PDF 업로드 → 파싱 → DB 저장 전체 플로우, 상태 변경 검증 (`uploaded` → `parsed`) ✅ 완료
  - API 응답만 검증 (DB 직접 조회 제거, 서버와 다른 DB 문제 해결) ✅ 완료
  - **캐시 저장 검증 필수**: 파싱 후 `data/cache/upstage/`에 캐시 파일이 생성되는지 확인 ✅ 완료
    - 캐시 파일 존재 확인 ✅ 완료
    - 캐시 파일 내용 검증 (JSON 형식, 필수 필드 존재) ✅ 완료
    - 캐시 파일 크기 확인 (0 bytes가 아닌지) ✅ 완료
  - **캐시 재사용 검증 필수**: 두 번째 파싱 시 캐시 히트 확인 (API 호출 없이 캐시 사용) ✅ 완료
    - 동일 PDF 파일로 두 번째 파싱 시도 ✅ 완료
    - 로그에서 "Cache hit" 메시지 확인 ✅ 완료
    - API 호출 없이 캐시에서 결과 반환 확인 ✅ 완료
  - **양면 분리 검증**: 원본 페이지 수 → 분리 후 페이지 수 확인 (10페이지 → 20페이지, 142페이지 → 284페이지) ✅ 완료
  - **변수명/함수명 Align 검증**: 현재 프로젝트 규칙 준수 확인 ✅ 완료
  - **로깅 형식 검증**: `[INFO]`, `[ERROR]` 형식 사용 확인 (이모지 없음) ✅ 완료
  - 100페이지 초과 PDF: 분할 파싱 동작, 페이지 번호 조정, Elements 병합 검증 (추후 추가 가능)
  - 에러 케이스: Upstage API 실패, 네트워크 에러, 파일 읽기 실패, 잘못된 파일 형식 (추후 추가 가능)
  - `backend/tests/fixtures/` 디렉토리 생성 (테스트용 샘플 PDF, 선택)
- [x] **Git 커밋**: `git add .` → `git commit -m "[Phase 2] E2E 테스트 및 검증 완료"` → `git push origin main` ✅ 완료

**⚠️ 검증 기준**:
- ✅ E2E 테스트 통과 (실제 서버 실행, 실제 데이터 사용)
- ✅ 캐시 저장 검증 통과 (파싱 후 캐시 파일 생성 확인)
- ✅ 캐시 재사용 검증 통과 (두 번째 파싱 시 캐시 히트 확인)
- ✅ 변수명/함수명 Align 완료 (현재 프로젝트 규칙 준수)
- ✅ 로깅 형식 준수 (`[INFO]`, `[ERROR]` 형식, 이모지 없음)

**⚠️ 참고사항**: 
- 참고 파일 방식으로 재구현하여 캐싱 문제를 근본적으로 해결
- 참고 파일은 `docs/reference_code/parsers/`에 보관 (버전 관리 포함)
- 각 단계 완료 후 검증하여 문제 조기 발견

**⚠️ Git 커밋 전략**:
- 각 단계(2.1, 2.2, 2.3, 2.4) 완료 후 즉시 커밋
- 작은 단위로 커밋하여 문제 발생 시 원복 가능하도록
- 커밋 메시지 형식: `[Phase 2] 작업 단계: 상세 설명`
- Phase 2 전체 완료 후 최종 커밋: `git commit -m "[Phase 2] PDF 파싱 모듈 재구현 완료 (참고 파일 기반, 캐싱 통합)"`

---

### Phase 3: 구조 분석 모듈

**⚠️ 현재 상태**: **중단됨** - Phase 2 캐싱 문제로 인해 중단, Phase 2 완료 후 재개 예정

**중단 사유**: 
- Phase 3를 진행하다가 Phase 2에서 파싱한 결과를 캐싱해야 하는데 제대로 되지 않는 문제 발견
- 구조 분석 시 `pdf_parser.parse_pdf(use_cache=True)`로 캐시된 파싱 결과를 재사용해야 하는데, 캐시가 제대로 저장되지 않아 문제 발생
- Phase 2의 캐싱 문제를 해결한 후 재개 예정

**목표**: 책의 구조(본문 시작, 챕터 경계)를 자동으로 파악하는 모듈 구현

**⚠️ Git 주의사항**: 작업 전 `git status`, `git pull origin main` 확인 / 작업 후 `git add .`, `git commit`, `git push origin main` 실행

#### 3.1 StructureBuilder 구현 (휴리스틱 기반)
- [ ] `backend/structure/content_boundary_detector.py` 생성
  - `ContentBoundaryDetector` 클래스
  - `detect_boundaries()`: 키워드 기반 경계 탐지
    - START_KEYWORDS: ["차례", "contents", "목차", "서문"]
    - END_KEYWORDS: ["참고문헌", "references", "부록", "index"]
    - 앞쪽 20페이지에서 시작 키워드 검색
    - 뒤쪽 30페이지에서 끝 키워드 검색
    - 반환: `{"start": {...}, "main": {...}, "end": {...}}`
- [ ] `backend/structure/chapter_detector.py` 생성
  - `ChapterDetector` 클래스
  - `detect_chapters()`: 챕터 탐지
    - 페이지 상단 요소 분석 (y0 작음, font_size 큼)
    - CHAPTER_PATTERNS 정규식 매칭: `r"^제\s*\d+\s*장"`, `r"^CHAPTER\s+\d+"`, `r"^\d+\.\s*[^.]+\s*$"`
    - 챕터 시작/끝 페이지 계산
    - 반환: 챕터 리스트
- [ ] `backend/structure/structure_builder.py` 생성
  - `StructureBuilder` 클래스
  - `build_structure(parsed_data)`: 최종 구조 생성
    - 경계 탐지 → 챕터 탐지 → 최종 구조 JSON 생성
    - 반환: `{"start": {...}, "main": {...}, "end": {...}, "metadata": {...}}`
  - 참고: `docs/book-assistant_repomix_backend.md` (Line 5448-5538)

#### 3.2 LLMStructureRefiner 구현 (core_logics.md)
- [ ] `backend/structure/llm_structure_refiner.py` 생성
  - `LLMStructureRefiner` 클래스
  - Pydantic 모델: `LLMChapterSuggestion`, `LLMStructureSuggestion`
  - `_build_page_toplines_chain()`: 각 페이지 상단 50글자 추출
    - 형식: "p{page_number}: {text}"
    - y0가 가장 작은 요소 선택 (페이지 상단)
    - 참고: `docs/core_logics.md` Line 244-268
  - `_build_context_for_llm()`: LLM 컨텍스트 구축
    - 글로벌 정보 (total_pages, original_pages 등)
    - 샘플 페이지 (head, tail, around_main_start)
    - 챕터 후보
    - page_toplines_chain
    - 참고: `docs/core_logics.md` Line 280-328
  - `_build_prompt()`: 시스템 프롬프트 생성
    - JSON 스키마 명시
    - page_toplines_chain 사용법 지시
    - 참고: `docs/core_logics.md` Line 344-417
  - `refine_structure()`: LLM 호출 및 응답 파싱
    - OpenAI API 호출 (gpt-4o-mini, temperature=0.3, response_format="json_object")
    - Pydantic 검증
    - 실패 시 휴리스틱 구조로 fallback

#### 3.3 구조 분석 API 구현
- [ ] `backend/api/schemas/structure.py` 생성
  - `LLMChapterSuggestion`: `number`, `title`, `start_page`, `end_page`
  - `LLMStructureSuggestion`: `main_start_page`, `main_end_page`, `chapters`, `notes_pages`, `issues`
  - `FinalChapterInput`: `title`, `start_page`, `end_page`, `order_index` (선택)
  - `FinalStructureInput`: `main_start_page`, `main_end_page`, `chapters`, `notes_pages`, `start_pages`, `end_pages`
  - `StructureCandidatesResponse`: `meta`, `auto_candidates`, `chapter_title_candidates`, `samples`
- [ ] `backend/api/services/structure_service.py` 생성
  - `StructureService` 클래스
  - `get_structure_candidates(book_id)`: 휴리스틱 + LLM 보정 구조 생성
    - **PDF 파싱 데이터 가져오기 (캐시 사용)**: `pdf_parser.parse_pdf(use_cache=True)` - 캐시된 파싱 결과 재사용
    - StructureBuilder로 휴리스틱 구조 생성
    - LLMStructureRefiner로 LLM 보정 구조 생성
    - 샘플 페이지, 챕터 제목 후보 추출
    - 반환: `StructureCandidatesResponse`
  - `apply_final_structure(book_id, final_structure)`: 최종 구조 DB 저장
    - `Book.structure_data`에 JSON 저장
    - 기존 Chapter 레코드 삭제 후 재생성
    - 상태 변경: `parsed` → `structured`
    - 참고: `docs/core_logics.md` Line 501-711
- [ ] `backend/api/routers/structure.py` 생성
  - `GET /api/books/{id}/structure/candidates`: 구조 후보 반환
    - 휴리스틱 구조 + LLM 보정 구조
    - 샘플 페이지, 챕터 제목 후보 포함
    - 참고: `docs/core_logics.md` Line 447-498
  - `POST /api/books/{id}/structure/final`: 최종 구조 확정
    - `FinalStructureInput` 받아서 DB 저장
    - Chapter 테이블 재생성
    - 상태 변경: `parsed` → `structured`
- [ ] `backend/api/main.py`에 structure 라우터 등록

#### 3.4 구조 분석 모듈 테스트
- [ ] **E2E 테스트** (⚠️ 실제 서버 실행, 실제 데이터만):
  - `backend/tests/test_e2e_structure_analysis.py` 생성
  - 전체 플로우: PDF 업로드 → 파싱 → 구조 분석
    - 휴리스틱 구조 생성 검증
    - LLM 보정 구조 생성 검증 (실제 OpenAI API)
    - 최종 구조 확정 및 DB 저장 검증
    - **캐시 재사용 검증**: 구조 분석 시 캐시된 파싱 결과 사용 확인 (API 호출 없음)
  - 구조 분석 API 검증:
    - `GET /api/books/{id}/structure/candidates` (휴리스틱/LLM 보정 구조, 샘플 페이지)
    - `POST /api/books/{id}/structure/final` (DB 저장, Chapter 재생성, 상태 변경)
  - 다양한 PDF 형식: 한국어/영어 책, 다양한 챕터 구조

**검증**: E2E 테스트 통과 (⚠️ 실제 서버 실행, 실제 PDF, 실제 Upstage API, 실제 LLM 사용, Mock 사용 금지)

**⚠️ Git 커밋**: Phase 3 완료 후 `git add .`, `git commit -m "[Phase 3] 구조 분석 모듈 구현"`, `git push origin main`

---

### Phase 4: 요약 모듈

**목표**: 페이지별 및 챕터별 서머리 생성 기능 구현

#### 4.1 PageSummarizer 구현
- [ ] `backend/summarizers/page_summarizer.py` 생성
  - `PageSummarizer`: `summarize_page(page_text, book_context=None, use_cache=True)` - LLM에 전달, 2~4문장 또는 bullet 형태, 토큰 제한 고려
  - **캐시 통합**: SummaryCacheManager 사용, 캐시 확인 → LLM 호출 → 캐시 저장
- [ ] `backend/summarizers/llm_chains.py` 생성 (LLM 호출 공통 로직, 프롬프트 템플릿, 모델/온도/토큰 설정)
- [x] `backend/summarizers/summary_cache_manager.py` 생성 ✅ 완료
  - `SummaryCacheManager` 클래스: OpenAI 요약 결과 캐싱
  - 콘텐츠 해시 기반 캐시 키 생성 (MD5)
  - 캐시 저장/로드 (`data/cache/summaries/`)
  - 페이지/챕터 요약 모두 캐시 지원

#### 4.2 ChapterSummarizer 구현
- [ ] `backend/summarizers/chapter_summarizer.py` 생성
  - `ChapterSummarizer`: `summarize_chapter(chapter_pages, page_summaries, use_cache=True)` - 옵션 A: 챕터 원문 직접 요약 / 옵션 B: 페이지 요약 집계 (권장), 1~3단락
  - **캐시 통합**: SummaryCacheManager 사용, 캐시 확인 → LLM 호출 → 캐시 저장

#### 4.3 요약 API 구현
- [ ] `backend/api/routers/summary.py` 생성
  - `GET /api/books/{id}/pages`: 페이지별 요약 리스트
  - `GET /api/books/{id}/chapters`: 챕터별 요약 리스트
  - `GET /api/books/{id}/chapters/{chapter_id}`: 챕터 상세 (요약 + 페이지 리스트)
- [ ] `backend/api/services/summary_service.py` 생성 (요약 생성 비즈니스 로직, 백그라운드 작업, 상태 업데이트)
  - **캐시 사용**: `PageSummarizer.summarize_page(use_cache=True)`, `ChapterSummarizer.summarize_chapter(use_cache=True)`
  - **PDF 파싱 캐시 사용**: `pdf_parser.parse_pdf(use_cache=True)` - 캐시된 파싱 결과 재사용

#### 4.4 요약 모듈 테스트
- [ ] **E2E 테스트** (⚠️ 실제 서버 실행, 실제 데이터만):
  - 전체 요약 생성 플로우: 구조 확정된 책 → 페이지 요약 (실제 OpenAI API) → 챕터 요약, DB 저장 검증, 상태 변경 검증
  - **캐시 저장 검증**: 요약 생성 후 `data/cache/summaries/`에 캐시 파일 생성 확인
  - **캐시 재사용 검증**: 두 번째 요약 시 캐시 히트 확인 (LLM 호출 없이 캐시 사용)
  - 요약 API: `GET /api/books/{id}/pages`, `GET /api/books/{id}/chapters`, `GET /api/books/{id}/chapters/{chapter_id}`, 백그라운드 작업
  - 실제 LLM 연동: OpenAI API 호출 검증, 요약 품질 검증, API 에러 처리 검증
  - 성능 테스트 (선택): 여러 페이지 병렬 요약, 대용량 챕터 요약

**검증**: E2E 테스트 통과 (⚠️ 실제 서버 실행, 실제 LLM 연동, 실제 요약 생성, Mock 사용 금지)

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

**⚠️ 중요: 모든 E2E 테스트는 실제 서버 실행, Mock 사용 금지, 실제 데이터만 사용** (실제 PDF, 실제 Upstage API, 실제 OpenAI LLM, 실제 DB)

- [ ] **전체 플로우 E2E 테스트** (`tests/test_e2e.py`, 실제 서버 실행):
  - 1. `POST /api/books/upload` → 책 생성 (`uploaded`)
  - 2. 실제 Upstage API로 PDF 파싱 → `parsed` 상태 확인 → **캐시 저장 확인** (`data/cache/upstage/`)
  - 3. `GET /api/books/{id}/structure/candidates` → 실제 LLM으로 구조 후보 생성 → **캐시된 파싱 결과 재사용 확인**
  - 4. `POST /api/books/{id}/structure/final` → 구조 확정 (`structured`)
  - 5. `POST /api/books/{id}/summarize/pages` → 실제 LLM으로 페이지 요약 (`page_summarized`) → **캐시 저장 확인** (`data/cache/summaries/`)
  - 6. `POST /api/books/{id}/summarize/chapters` → 실제 LLM으로 챕터 요약 (`summarized`) → **캐시 저장 확인**
  - 7-9. 최종 결과 조회 검증 (`GET /api/books/{id}`, `/pages`, `/chapters`)
  - 각 단계별 데이터 정합성 검증 (DB 레코드, 관계, 상태 변경 순서)
  - **캐시 재사용 검증**: 동일 PDF/텍스트 재요청 시 캐시 히트 확인 (API 호출 없음)
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
- [x] **캐싱 전략 구현 완료**: ✅ 완료
  - Upstage API 파싱 결과 캐싱 (`data/cache/upstage/`) ✅ 완료
  - OpenAI 요약 결과 캐싱 (`data/cache/summaries/`) ✅ 완료
  - 파일 해시 기반 캐시 키 (같은 내용이면 경로 무관하게 재사용) ✅ 완료
  - 구조 분석기에서 캐시된 파싱 결과 재사용 ✅ 완료
- [ ] 캐시 정리 기능 (오래된 캐시 자동 삭제, 캐시 통계 조회)
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

**⚠️ E2E 테스트 필수 원칙**: 실제 서버 실행, Mock 사용 절대 금지, 실제 외부 API 연동, 실제 PDF 파일 사용, 실제 DB 데이터 검증

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
8. **⚠️ in-memory SQLite 테스트 시 Connection Lifecycle 관리 필수**:
   - **문제**: `sqlite3.OperationalError: no such table: books` 발생
   - **원인**: in-memory SQLite의 connection lifecycle 문제로 session이 다른 connection을 사용하거나 connection이 닫혀 테이블이 보이지 않음
   - **해결 방법**: 
     - `db_connection` fixture 추가하여 connection을 명시적으로 유지
     - `db_session` fixture에서 `Session(bind=db_connection)`로 동일 connection 사용
     - Connection을 fixture에서 명시적으로 관리하여 lifecycle 보장
   - **검증 방법**: 로그를 통해 모든 단계에서 동일 connection ID와 테이블 상태 확인 (총 374개 로그 문 추가)
   - **Lesson**: in-memory SQLite는 connection에 종속적이므로, 테스트 fixture에서 connection을 명시적으로 유지하고 session이 동일 connection을 사용하도록 해야 함
