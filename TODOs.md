# 도서 PDF 구조 분석 및 서머리 서비스 개발 계획

> PRD: `docs/PRD_books-processor.md`  
> 핵심 로직 참고: `docs/core_logics.md`  
> 선행 서비스 참고: `docs/book-assistant_repomix_backend.md`

## 프로젝트 개요

도서 PDF 파일을 업로드하면 자동으로 책의 구조(본문 시작, 챕터 경계 등)를 파악하고, 페이지별 및 챕터별 서머리를 생성하는 웹 서비스입니다.

**핵심 파이프라인**: `PDF 업로드 → Upstage API 파싱 → 구조 분석(휴리스틱 + LLM) → 페이지/챕터 요약 → SQLite 저장`

## 프로젝트 현재 상황

> 상세 상황: `PROJECT_STATUS.md` 참고

### 전체 진행률: 약 65% (Phase 1, Phase 2 완료, Phase 3 진행 중)

| Phase | 제목 | 진행률 | 상태 |
|-------|------|-------|------|
| Phase 1 | 프로젝트 기초 및 환경 설정 | 100% | 완료 |
| Phase 2 | PDF 파싱 모듈 (Upstage API 연동) | 100% | **완료** (핵심 기능 완료, 병렬 처리 구현 완료) |
| Phase 3 | 구조 분석 모듈 | 90% | **진행 중** (Footer 기반 휴리스틱 구조 분석 완료, LLM 보정 제외, 추가 도서 재현성 확인 진행 중 - 일부 문제 남음) |
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

**✅ 현재 상태**: **완료** (핵심 기능 완료, 병렬 처리 구현 완료)
- ✅ 참고 파일 기반 재구현 완료 (2.1 ~ 2.5)
- ✅ E2E 테스트 통과 (2.7)
- ✅ 캐싱 시스템 정상 작동
- ✅ **완료**: 2.6 PDF 파싱 병렬처리 구현 (10페이지 기본 모드, 성능 최적화 완료)

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

#### 2.6 PDF 파싱 병렬처리 구현 (10페이지 기본 모드) ✅ 완료 - **가장 중요**

**⚠️ 핵심 변경**: 순차 처리를 완전히 제거하고 병렬 처리(10페이지 기본 모드)만 사용

- [x] **Git 작업 전**: `git status` → `git pull origin main` 확인 ✅ 완료
- [x] **UpstageAPIClient 병렬 파싱 메서드 구현**: ✅ 완료
  - `backend/parsers/upstage_api_client.py` 수정 ✅ 완료
  - `PARALLEL_CHUNK_SIZE = 10` 상수 추가 (기본 청크 크기) ✅ 완료
  - `MAX_WORKERS = 5` 상수 추가 (동시 요청 수 제한, Rate limit 고려) ✅ 완료
  - `parse_pdf()` 메서드 수정: 기본적으로 10페이지 병렬 처리 사용 ✅ 완료
  - `_parse_pdf_parallel()` 메서드 추가: ✅ 완료
    - 10페이지 단위로 PDF 분할 ✅ 완료
    - `concurrent.futures.ThreadPoolExecutor` 사용 (I/O 바운드 작업) ✅ 완료
    - 각 청크를 병렬로 파싱 ✅ 완료
    - Elements 병합 시 페이지 번호 조정 (원본 페이지 번호 유지) ✅ 완료
    - 청크를 시작 페이지 기준으로 정렬 후 병합 (순서 보장) ✅ 완료
    - 에러 처리: 일부 청크 실패 시 재시도 로직 ✅ 완료
  - 기존 `_parse_pdf_in_chunks()` 제거 (순차 처리 로직 제거) ✅ 완료
- [x] **병렬 처리 로직 구현**: ✅ 완료
  - `_parse_chunk()`: 단일 청크 파싱 (ThreadPoolExecutor용) ✅ 완료
    - PDF 분할 → API 호출 → 결과 반환 ✅ 완료
    - 임시 파일 즉시 삭제 (finally 블록) ✅ 완료
  - `_merge_chunk_results()`: 병렬 파싱 결과 병합 ✅ 완료
    - 청크를 시작 페이지 기준으로 정렬 ✅ 완료
    - 페이지 번호 조정 (각 청크의 시작 페이지 기준) ✅ 완료
    - ID 재조정 (순차적으로 할당, len(all_elements) 사용) ✅ 완료
    - Elements 순서 보장 ✅ 완료
- [x] **Rate Limit 및 에러 처리**: ✅ 완료
  - `max_workers=5`로 동시 요청 수 제한 ✅ 완료
  - 429 에러 시 지수 백오프 재시도 (기존 로직 활용) ✅ 완료
  - 실패한 청크만 재시도, 부분 성공 허용 (로그 기록) ✅ 완료
- [x] **성능 테스트 및 검증**: ✅ 완료
  - `backend/tests/test_parallel_parsing.py` 생성 ✅ 완료
  - 병렬처리 전후 파싱 시간 비교 테스트 ✅ 완료
  - 여러 도서 동시 파싱 테스트 ✅ 완료 (7개 도서 테스트 완료: 3D프린터의 모든것, 4차산업혁명 전문직의 미래, 10년후 세계사, 12가지 인생의 법칙, 30개 도시로 읽는 세계사, 90년생이 온다, 99%를 위한 경제)
  - 메모리 사용량 모니터링 ✅ 완료
  - E2E 테스트 통합: 기존 `test_e2e_pdf_parsing.py`에 병렬 처리 검증 추가 ✅ 완료
  - **캐시 호환성 검증**: 병렬 처리 결과가 캐시에 저장되고 재사용되는지 확인 ✅ 완료 (모든 테스트에서 캐시 히트 확인, API 호출 0번 확인)
- [x] **기존 로직과의 호환성**: ✅ 완료
  - `parse_pdf()` 메서드 시그니처 유지 (하위 호환성) ✅ 완료
  - 캐싱 시스템과의 통합 확인 (병렬 처리 결과도 캐시 저장) ✅ 완료
  - `PDFParser.parse_pdf()`에서 변경 없이 사용 가능하도록 ✅ 완료
  - API 응답 형식 유지 (동일한 `elements` 배열 구조) ✅ 완료
- [ ] **Git 커밋**: `git add .` → `git commit -m "[Phase 2] PDF 파싱 병렬처리 구현 완료 (10페이지 기본 모드)"` → `git push origin main` (진행 예정)

**⚠️ 구현 시 필수 사항**:
1. Elements 순서 보장: 청크를 페이지 순서대로 정렬 후 병합
2. Page 번호 조정 정확성: 각 청크의 시작 페이지를 정확히 계산
3. ID 재조정 일관성: 순차 처리와 동일한 방식 (len(all_elements) 사용)
4. Rate Limit 고려: max_workers 제한, 429 에러 재시도
5. 에러 처리: 실패한 청크만 재시도, 부분 성공 허용

**⚠️ 예상 성능 향상**: 약 3-5배 (순차 처리 대비)

#### 2.7 PDF 파싱 모듈 테스트
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
  - [ ] 100페이지 초과 PDF: 분할 파싱 동작, 페이지 번호 조정, Elements 병합 검증 (추후 추가 가능, 선택)
  - [ ] 에러 케이스: Upstage API 실패, 네트워크 에러, 파일 읽기 실패, 잘못된 파일 형식 (추후 추가 가능, 선택)
  - [ ] `backend/tests/fixtures/` 디렉토리 생성 (테스트용 샘플 PDF, 선택)
- [x] **Git 커밋**: `git add .` → `git commit -m "[Phase 2] E2E 테스트 및 검증 완료"` → `git push origin main` ✅ 완료

**⚠️ 검증 기준**:
- ✅ E2E 테스트 통과 (실제 서버 실행, 실제 데이터 사용)
- ✅ 캐시 저장 검증 통과 (파싱 후 캐시 파일 생성 확인)
- ✅ 캐시 재사용 검증 통과 (두 번째 파싱 시 캐시 히트 확인)
- ✅ 변수명/함수명 Align 완료 (현재 프로젝트 규칙 준수)
- ✅ 로깅 형식 준수 (`[INFO]`, `[ERROR]` 형식, 이모지 없음)
- ✅ **병렬 처리 검증 통과**: 7개 도서 테스트 완료, 캐시 호환성 검증 완료, API 호출 횟수 정확성 확인
- ⚠️ **미완료 항목**:
  - [ ] 2.7 일부 선택적 테스트 항목 (100페이지 초과 PDF, 에러 케이스, fixtures 디렉토리)

**⚠️ 참고사항**: 
- 참고 파일 방식으로 재구현하여 캐싱 문제를 근본적으로 해결
- 참고 파일은 `docs/reference_code/parsers/`에 보관 (버전 관리 포함)
- 각 단계 완료 후 검증하여 문제 조기 발견

**⚠️ 완료된 핵심 기능**:
- ✅ 참고 파일 기반 재구현 (2.1 ~ 2.5)
- ✅ UpstageAPIClient: 100페이지 분할 파싱, 재시도 로직, Rate limit 처리
- ✅ CacheManager: 파일 해시 기반 캐싱, 안전한 저장
- ✅ PDFParser: 캐싱 통합, 양면 분리, Elements 구조화
- ✅ 업로드 API: 파일 업로드, 백그라운드 파싱, DB 저장
- ✅ E2E 테스트: 실제 서버 실행, 캐시 저장/재사용 검증
- ✅ **병렬 처리 구현**: 10페이지 단위 병렬 파싱, ThreadPoolExecutor 사용, 캐시 호환성 검증 완료

**⚠️ 미완료 항목 (추가 개선)**:
- [ ] 2.7 일부 선택적 테스트 항목 (100페이지 초과 PDF, 에러 케이스, fixtures 디렉토리)

**⚠️ Git 커밋 전략**:
- 각 단계(2.1, 2.2, 2.3, 2.4, 2.5, 2.7) 완료 후 즉시 커밋
- 작은 단위로 커밋하여 문제 발생 시 원복 가능하도록
- 커밋 메시지 형식: `[Phase 2] 작업 단계: 상세 설명`
- 핵심 기능 완료: `git commit -m "[Phase 2] PDF 파싱 모듈 재구현 완료 (참고 파일 기반, 캐싱 통합)"`

---

### Phase 3: 구조 분석 모듈

**✅ 현재 상태**: **진행 중 (90%)** - Footer 기반 구조 분석 구현 완료, E2E 테스트 통과 (1등의 통찰.pdf 기준), 추가 도서 재현성 확인 진행 중

**⚠️ 핵심 원칙** (참고: `docs/structure_analysis_logic_explanation_v2.md`):
1. **Footer 기반 판단**: 모든 구조 판단은 Footer의 구조 판별자를 기준으로 수행
2. **좌측 페이지 우선**: 홀수 페이지(좌측)에 항상 구조 판별자가 나타나므로 이를 기준으로 판단
3. **숫자 기반 챕터 구분**: "제", "장", "강", "part" 등의 특별한 식별자에 구애받지 않고, 숫자를 바탕으로 챕터 구분
4. **LLM 보정 제외**: 휴리스틱 기반 구조 분석만 사용 (LLM 보정 로직 미적용)

**목표**: Footer 기반 휴리스틱으로 책의 구조(본문 시작, 챕터 경계)를 자동으로 파악하는 모듈 구현

**⚠️ Git 주의사항**: 작업 전 `git status`, `git pull origin main` 확인 / 작업 후 `git add .`, `git commit`, `git push origin main` 실행

#### 3.1 참고 파일 추가 및 분석
- [x] **Git 작업 전**: `git status` → `git pull origin main` 확인 ✅ 완료
- [x] `docs/reference_code/structure/` 디렉토리 생성 ✅ 완료
- [x] 선행 서비스의 구조 분석 관련 파일 확인 및 목록 작성 ✅ 완료
- [x] 참고 파일 추가 (`_REF` 접미사 사용): ✅ 완료
  - `content_boundary_detector_REF.py` ✅ 완료
  - `chapter_detector_REF.py` ✅ 완료
  - `structure_builder_REF.py` ✅ 완료
  - `llm_structure_refiner_REF.py` (있는 경우) ✅ 완료
- [x] 참고 파일 상단에 주석 추가 (출처, 참고 목적, 주요 차이점) ✅ 완료
- [x] 기능 분석 및 현재 프로젝트 구조 매핑 (`ALIGN_PLAN.md` 작성) ✅ 완료
- [x] **Git 커밋**: `git add .` → `git commit -m "[Phase 3] 참고 파일 추가 및 분석 완료"` → `git push origin main` ✅ 완료

#### 3.2 ContentBoundaryDetector 및 ChapterDetector 구현 (Footer 기반 휴리스틱)
- [x] **Git 작업 전**: `git status` → `git pull origin main` 확인 ✅ 완료
- [x] `backend/structure/content_boundary_detector.py` 생성 ✅ 완료
  - `ContentBoundaryDetector` 클래스 ✅ 완료
  - `detect_boundaries()`: Footer 기반 경계 탐지 ✅ 완료
    - **Footer 구조 판별자 추출**: 홀수 페이지(좌측) Footer에서 구조 판별자 추출 ✅ 완료
    - **서문/본문/종문 구분**: Footer 구조 판별자의 숫자 포함 여부와 키워드로 구분 ✅ 완료
      - 숫자 포함 + 서문 키워드 없음 → 본문 영역 ✅ 완료
      - 숫자 미포함 + 서문 키워드 포함 → 서문 영역 ✅ 완료
      - 숫자 미포함 + 종문 키워드 포함 → 종문 영역 ✅ 완료
    - START_KEYWORDS: 서문 키워드 목록 (한글/영어) ✅ 완료
    - END_KEYWORDS: 종문 키워드 목록 (한글/영어) ✅ 완료
    - 반환: `{"start": {...}, "main": {...}, "end": {...}}` ✅ 완료
- [x] `backend/structure/chapter_detector.py` 생성 ✅ 완료
  - `ChapterDetector` 클래스 ✅ 완료
  - `detect_chapters()`: Footer 기반 챕터 탐지 ✅ 완료
    - **Footer 구조 판별자에서 숫자 추출**: 본문 영역의 홀수 페이지 Footer에서 숫자 추출 ✅ 완료
    - **숫자 기반 챕터 구분**: "제", "장", "강" 등 특별한 식별자 무시, 숫자만 사용 ✅ 완료
    - **챕터 범위 계산**: 각 챕터의 시작/끝 페이지 계산 (홀수 페이지 기준) ✅ 완료
    - **짝수 페이지 처리**: 인접한 홀수 페이지와 동일한 챕터로 간주 ✅ 완료
    - 반환: 챕터 리스트 ✅ 완료
- [x] **Git 커밋**: `git add .` → `git commit -m "[Phase 3] ContentBoundaryDetector 및 ChapterDetector 구현 완료 (Footer 기반)"` → `git push origin main` ✅ 완료

#### 3.3 StructureBuilder 구현 (Footer 기반 휴리스틱 통합)
- [x] **Git 작업 전**: `git status` → `git pull origin main` 확인 ✅ 완료
- [x] `backend/structure/structure_builder.py` 생성 ✅ 완료
  - `StructureBuilder` 클래스 ✅ 완료
  - `build_structure(parsed_data)`: Footer 기반 최종 구조 생성 ✅ 완료
    - ContentBoundaryDetector로 Footer 기반 경계 탐지 ✅ 완료
    - ChapterDetector로 Footer 기반 챕터 탐지 ✅ 완료
    - 최종 구조 JSON 생성 ✅ 완료
    - 반환: `{"start": {...}, "main": {...}, "end": {...}, "metadata": {...}}` ✅ 완료
  - 참고: `docs/structure_analysis_logic_explanation_v2.md` ✅ 완료
- [x] **Git 커밋**: `git add .` → `git commit -m "[Phase 3] StructureBuilder 구현 완료 (Footer 기반)"` → `git push origin main` ✅ 완료

#### 3.4 LLMStructureRefiner 구현 (참고용, 실제 미사용)
- [x] `backend/structure/llm_structure_refiner.py` 생성 ✅ 완료 (참고용으로 구현됨)
- [ ] **⚠️ 중요: LLM 보정 로직 미적용**
  - Footer 기반 휴리스틱 구조 분석만 사용 ✅ 완료
  - `LLMStructureRefiner.refine_structure()` 호출 제거 ✅ 완료
  - `StructureService.get_structure_candidates()`에서 LLM 보정 로직 제거 ✅ 완료
  - API 응답에서 LLM 보정 구조 제외 (Footer 기반 휴리스틱 구조만 반환) ✅ 완료

#### 3.5 구조 분석 API 스키마 및 서비스 구현 (Footer 기반)
- [x] **Git 작업 전**: `git status` → `git pull origin main` 확인 ✅ 완료
- [x] `backend/api/schemas/structure.py` 생성 ✅ 완료
  - `LLMChapterSuggestion`, `LLMStructureSuggestion`: 참고용 스키마 (실제 미사용) ✅ 완료
  - `FinalChapterInput`: `title`, `start_page`, `end_page`, `order_index` (선택) ✅ 완료
  - `FinalStructureInput`: `main_start_page`, `main_end_page`, `chapters`, `notes_pages`, `start_pages`, `end_pages` ✅ 완료
  - `StructureCandidatesResponse`: `meta`, `auto_candidates`, `chapter_title_candidates`, `samples` ✅ 완료
- [x] `backend/api/services/structure_service.py` 생성 ✅ 완료
  - `StructureService` 클래스 ✅ 완료
  - `get_structure_candidates(book_id)`: Footer 기반 휴리스틱 구조 생성 ✅ 완료
    - **PDF 파싱 데이터 가져오기 (캐시 사용)**: `pdf_parser.parse_pdf(use_cache=True)` - 캐시된 파싱 결과 재사용 ✅ 완료
    - StructureBuilder로 Footer 기반 휴리스틱 구조 생성 ✅ 완료
    - **LLM 보정 로직 제거**: `LLMStructureRefiner.refine_structure()` 호출 제거 ✅ 완료
    - 샘플 페이지, 챕터 제목 후보 추출 ✅ 완료
    - 반환: `StructureCandidatesResponse` (Footer 기반 휴리스틱 구조만 포함, `label: "footer_based_v1"`) ✅ 완료
  - `apply_final_structure(book_id, final_structure)`: 최종 구조 DB 저장 ✅ 완료
    - `Book.structure_data`에 JSON 저장 ✅ 완료
    - 기존 Chapter 레코드 삭제 후 재생성 ✅ 완료
    - 상태 변경: `parsed` → `structured` ✅ 완료
    - **구조 분석 결과 JSON 파일 저장** (⚠️ 이후 Phase에서 재사용): ✅ 완료
      - 저장 위치: `data/output/structure/{book_id}_structure.json` ✅ 완료
      - 저장 시점: 최종 구조 확정 시 (`apply_final_structure()` 메서드) ✅ 완료
      - JSON 형식: 깔끔하게 정리된 구조 분석 결과 (main_start_page, main_end_page, chapters 등) ✅ 완료
      - 파일명: `{book_id}_structure.json` (book_id 기반, 안전한 파일명) ✅ 완료
- [x] **Git 커밋**: `git add .` → `git commit -m "[Phase 3] 구조 분석 API 스키마 및 서비스 구현 완료 (Footer 기반)"` → `git push origin main` ✅ 완료

#### 3.6 구조 분석 API 라우터 구현 (Footer 기반)
- [x] **Git 작업 전**: `git status` → `git pull origin main` 확인 ✅ 완료
- [x] `backend/api/routers/structure.py` 생성 ✅ 완료
  - `GET /api/books/{id}/structure/candidates`: Footer 기반 구조 후보 반환 ✅ 완료
    - Footer 기반 휴리스틱 구조만 반환 (`label: "footer_based_v1"`) ✅ 완료
    - LLM 보정 구조 제외 ✅ 완료
    - 샘플 페이지, 챕터 제목 후보 포함 ✅ 완료
  - `POST /api/books/{id}/structure/final`: 최종 구조 확정 ✅ 완료
    - `FinalStructureInput` 받아서 DB 저장 ✅ 완료
    - Chapter 테이블 재생성 ✅ 완료
    - 상태 변경: `parsed` → `structured` ✅ 완료
- [x] `backend/api/main.py`에 structure 라우터 등록 ✅ 완료
- [x] **Git 커밋**: `git add .` → `git commit -m "[Phase 3] 구조 분석 API 라우터 구현 완료 (Footer 기반)"` → `git push origin main` ✅ 완료

#### 3.7 구조 분석 모듈 E2E 테스트
- [x] **Git 작업 전**: `git status` → `git pull origin main` 확인 ✅ 완료
- [x] **Ground Truth 파일 생성**: ✅ 완료
  - `backend/tests/fixtures/ground_truth_1등의통찰.py` 생성 (사용자 제공 페이지 정보 기반) ✅ 완료
  - ⚠️ 중요: 정확도 평가는 페이지 번호만 사용 (main_start_page, main_end_page, chapter start_page/end_page) ✅ 완료
  - 챕터 제목(title)은 참고용이며, 정확도 평가에 사용하지 않음 ✅ 완료
- [x] **E2E 테스트** (⚠️ 실제 서버 실행, 실제 데이터만): ✅ 완료
  - `backend/tests/test_e2e_structure_analysis.py` 생성 ✅ 완료
  - 전체 플로우: PDF 업로드 → 파싱 → 구조 분석 ✅ 완료
    - Footer 기반 휴리스틱 구조 생성 검증 ✅ 완료
    - 최종 구조 확정 및 DB 저장 검증 ✅ 완료
    - **캐시 재사용 검증**: 구조 분석 시 캐시된 파싱 결과 사용 확인 (Upstage API 호출 없음) ✅ 완료
  - **정확도 평가** (Ground Truth 기반, 1등의 통찰.pdf): ✅ 완료
    - 본문 시작 페이지 정확도: Footer 기반(±3페이지) ✅ 통과 (예측 37, GT 36, 오차 1페이지)
    - 챕터 개수 정확도: Footer 기반(±2개) ✅ 통과 (예측 7개, GT 7개, 오차 0개)
    - 챕터 시작 페이지 정확도: 각 챕터별 Footer 기반(±3페이지) ✅ 통과 (7/7개 챕터 통과)
    - 종문 탐지: ✅ 완료 (247페이지에서 "감사" 키워드 탐지)
    - ⚠️ 중요: 페이지 번호만 비교 (챕터 제목은 비교하지 않음) ✅ 완료
  - 구조 분석 API 검증: ✅ 완료
    - `GET /api/books/{id}/structure/candidates` (Footer 기반 구조, 샘플 페이지) ✅ 완료
    - `POST /api/books/{id}/structure/final` (DB 저장, Chapter 재생성, 상태 변경) ✅ 완료
  - **Phase 2 E2E 테스트와 연결성**: ✅ 완료
    - Phase 2에서 파싱된 book_id 재사용 또는 동일 PDF 파일 사용 ✅ 완료
    - Phase 2에서 생성된 캐시 파일(`data/cache/upstage/{hash}.json`) 재사용 확인 ✅ 완료
  - [x] **추가 도서로 재현성 확인** (총 9개 도서) - **진행 중**:
  - **⚠️ 캐시 재사용 규칙 준수** (Phase 2와 동일):
    - **캐시 삭제 금지**: 테스트 시작 전에 캐시를 삭제하면 안 됨
    - **캐시 재사용 필수**: PDF 파싱 결과는 캐시에 저장되고, 다시 호출 시 캐시를 사용해야 함
    - **병렬 모드 기본**: 병렬 모드가 기본으로 적용되어 있음
    - **캐시 상태 확인**: 캐시가 이미 있는 경우와 없는 경우를 구분하여 검증
    - **금지 사항**: 테스트 시작 전 캐시 삭제 (`cache_file.unlink()`, `cache_dir.rmdir()` 등), 캐시 무효화 (`invalidate_cache()` 호출), `use_cache=False`로 파싱 호출
  - [x] **3.7.1 Ground Truth 파일 생성** (사용자 제공 시작 페이지만, end_page는 계산): ✅ 완료
    1. `ground_truth_3D프린터의모든것.py`: 1장(27), 2장(99), 3장(151), 4장(241), 종문(359)
    2. `ground_truth_90년대생이온다.py`: 1장(35), 2장(167), 3장(289), 종문(401)
    3. `ground_truth_10년후세계사.py`: 1장(25), 2장(175), 3장(385), 종문(548)
    4. `ground_truth_4차산업혁명전문직의미래.py`: 1장(45), 2장(291), 3장(449), 종문(588)
    5. `ground_truth_12가지인생의법칙.py`: 1장(35), 2장(170), 3장(299), 4장(188), 5장(243), 6장(602), 7장(330), 8장(408), 9장(463), 10장(504), 11장(555), 12장(641), 종문(680)
    6. `ground_truth_30개도시로읽는세계사.py`: 1장(23), 11장(211), 21장(383), 30장(555), 종문(571)
    7. `ground_truth_10년후이곳은제2의판교.py`: 1장(17), 2장(85), 3장(123), 4장(163), 5장(345), 종문(518)
    8. `ground_truth_10년후이곳은제2의강남.py`: 1장(19), 2장(105), 3장(145), 4장(279), 종문(408)
    9. `ground_truth_99를위한경제.py`: 1장(41), 2장(69), 3장(125), 4장(145), 5장(177), 6장(257), 7장(321), 종문(349)
    - **⚠️ 중요**: 제공된 값은 각 챕터의 시작 페이지만 제공됨
      - `end_page` 계산: 다음 챕터 시작 페이지 - 1
      - 마지막 챕터의 `end_page`: 종문 시작 페이지 - 1
      - `main_start_page`: 첫 번째 챕터 시작 페이지
      - `main_end_page`: 종문 시작 페이지 - 1
    - **작업 방법**: 각 PDF 파일의 원본 페이지 수 확인 (pypdf 사용), `ground_truth_1등의통찰.py`를 템플릿으로 사용, 사용자 제공 시작 페이지 데이터로 각 파일 생성, `end_page` 자동 계산 로직 적용 ✅ 완료
  - [x] **3.7.2 E2E 테스트 확장 및 캐시 재사용 규칙 준수**: ✅ 완료
    - `backend/tests/test_e2e_structure_analysis.py` 수정
    - **캐시 상태 확인 로직 추가**:
      - 각 테스트 시작 시 캐시 파일 존재 여부 확인 (삭제하지 않음)
      - 캐시가 있는 경우: 캐시 재사용 검증 (수정 시간 확인, 'Cache hit' 로그 확인)
      - 캐시가 없는 경우: 캐시 생성 검증 (캐시 파일 생성 확인, 'Cache miss' 로그 확인)
    - **파라미터화된 테스트 함수 생성**:
      - `test_e2e_structure_analysis_for_book(book_name, pdf_file, ground_truth_module)`
      - `pytest.mark.parametrize` 사용하여 10개 도서 (1등의 통찰 + 추가 9개) 테스트
      - 각 도서별로 동일한 플로우 실행 (캐시 상태 확인 → PDF 업로드 및 파싱 → 구조 분석 → 정확도 평가)
    - **캐시 재사용 검증 강화**:
      - 캐시 파일 존재 확인: `data/cache/upstage/{hash}.json` 존재 여부
      - 캐시 파일 수정 시간 확인: 재사용 시 수정 시간이 변경되지 않아야 함
      - 서버 로그 확인: 'Cache hit' 또는 'Cache miss' 메시지 확인 (로그 파일 분석)
      - 구조 분석 시 캐시 재사용 확인: `StructureService.get_structure_candidates()`에서 `use_cache=True`로 호출되는지 확인
    - **정확도 평가 메트릭**:
      - 본문 시작 페이지: ±3페이지
      - 챕터 개수: ±2개
      - 챕터 시작 페이지: 각 챕터별 ±3페이지
      - 종문 탐지: 종문 시작 페이지 ±3페이지
    - **테스트 결과 리포트 생성**:
      - 각 도서별 정확도 결과 저장
      - 통과/실패 여부 기록
      - **캐시 상태 정보 포함** (캐시 히트/미스, 캐시 파일 경로)
      - 전체 통계 계산 (평균 정확도, 통과율 등) ✅ 완료
  - [x] **3.7.3 평가-수정 사이클** (진행 중):
    - 초기 테스트 실행: 9개 도서 모두에 대해 E2E 테스트 실행, 각 도서별 정확도 결과 수집, **캐시 상태 정보 수집** (캐시 히트/미스, 캐시 파일 경로)
    - 문제 분석: 실패한 도서 목록 확인, 실패 원인 분석 (본문 시작 페이지 오차, 챕터 개수 불일치, 챕터 시작 페이지 오차 등), 로그 파일 분석 (`data/test_results/structure_analysis_*.log`), **캐시 관련 문제 확인** (캐시 미사용, 캐시 파일 누락 등)
    - 사용자 보고: 실패한 도서 및 원인 보고, 수정 방안 제시 (필요 시)
    - 수정 및 재테스트: 구조 분석 로직 수정 (필요 시), 재테스트 실행, 정확도 재평가
    - 반복: 모든 메트릭 통과할 때까지 반복, 최대 3회 반복 (필요 시 사용자와 협의)
    - **✅ 완료된 수정 사항**:
      - 페이지 번호 일관성 문제 해결 (좌는 홀수, 우는 짝수로 일관되게 수정) ✅
      - 단일 문자 키워드 처리 개선 ("주" 키워드를 단독 단어로만 매칭) ✅
      - 챕터 패턴 확장 (`^\d+[_\-\s]+[가-힣]`, `^0?\d+[_\-\s]+[가-힣]`, `^\d+_\s*[가-힣A-Z0-9]` 추가) ✅
      - 구조 분석 로직 가이드라인 문서 작성 (`docs/structure_analysis_logic_guidelines.md`) ✅
    - **⚠️ 남은 문제**:
      - 3D프린터의모든것 챕터 4번 미탐지: `[c]4_실전!` 형식의 특수 접두사 처리 필요 (개선 방안 재검토 중)
      - 12가지인생의법칙: "법칙 N" 형식 미지원 (개선 방안 재검토 중)
  - [ ] **3.7.4 최종 리포트 생성** (남은 문제 해결 후 진행):
    - 전체 통계: 테스트 실행 도서 수 (10개), 통과한 도서 수, 통과율
    - 도서별 상세 결과: 각 도서별 정확도 메트릭, 통과/실패 여부, 오차 값, **캐시 상태 정보** (캐시 히트/미스, 캐시 파일 경로)
    - 평균 정확도: 본문 시작 페이지 평균 오차, 챕터 개수 평균 오차, 챕터 시작 페이지 평균 오차
    - **캐시 재사용 통계**: 캐시 히트율 (캐시 히트 횟수 / 전체 파싱 횟수), 캐시 미스 횟수, 캐시 파일 생성 횟수
    - 실패한 도서 목록 (있는 경우): 실패한 도서명, 실패 원인, 수정 방안
    - 리포트 형식: 마크다운 파일 (`data/test_results/structure_analysis_final_report.md`), 터미널 출력 (테스트 완료 시 요약 출력)
  - [x] **3.7.5 Git 커밋** (진행 중):
    - [x] 3.7.1 완료 후: `git add .` → `git commit -m "[Phase 3] Ground Truth 파일 9개 생성 완료"` → `git push origin main` ✅ 완료
    - [x] 3.7.2 완료 후: `git add .` → `git commit -m "[Phase 3] E2E 테스트 확장 완료 (9개 도서 추가, 캐시 재사용 규칙 준수)"` → `git push origin main` ✅ 완료
    - [x] 3.7.3 일부 완료 후: `git add .` → `git commit -m "[Phase 3] 구조 분석 로직 개선 (페이지 번호 일관성, 단일 문자 키워드 처리, 챕터 패턴 확장)"` → `git push origin main` (진행 예정)
    - [ ] 3.7.4 완료 후: `git add .` → `git commit -m "[Phase 3] 재현성 확인 완료 및 최종 리포트 생성"` → `git push origin main` (남은 문제 해결 후 진행)

**⚠️ 검증 기준**:
- ✅ E2E 테스트 통과 (실제 서버 실행, 실제 데이터 사용) - 1등의 통찰.pdf 기준
- ✅ 캐시 재사용 검증 통과 (구조 분석 시 캐시된 파싱 결과 사용 확인, Upstage API 호출 없음)
- ✅ Footer 기반 휴리스틱 구조 생성 검증 통과
- ✅ LLM 보정 로직 제외 확인 (Footer 기반 휴리스틱만 사용)
- ✅ 정확도 평가 통과 (Ground Truth 기반, 페이지 번호만 비교) - 1등의 통찰.pdf 기준
  - 본문 시작 페이지: Footer 기반(±3페이지) ✅ 통과 (예측 37, GT 36, 오차 1페이지)
  - 챕터 개수: Footer 기반(±2개) ✅ 통과 (예측 7개, GT 7개, 오차 0개)
  - 챕터 시작 페이지: 각 챕터별 Footer 기반(±3페이지) ✅ 통과 (7/7개 챕터 통과)
  - 종문 탐지: ✅ 완료 (247페이지에서 "감사" 키워드 탐지)
- ✅ Phase 2 E2E 테스트와 연결성 확인 (캐시 재사용)
- ✅ 변수명/함수명 Align 완료
- ✅ 로깅 형식 준수 (`[INFO]`, `[ERROR]`, 이모지 없음)
- [x] **추가 도서로 재현성 확인** (총 9개 도서, 진행 중): ✅ Ground Truth 파일 생성 완료, ✅ E2E 테스트 확장 완료, ⚠️ 일부 도서 실패 (3D프린터의모든것 챕터 4번, 12가지인생의법칙, 99를위한경제 챕터 7번), **캐시 재사용 규칙 준수 확인** (캐시 삭제 없음, 캐시 재사용 검증, 캐시 상태 정보 포함) ✅

**⚠️ 핵심 구현 내용** (참고: `docs/structure_analysis_logic_explanation_v2.md`):
- Footer 기반 본문 탐지: Footer 구조 판별자의 숫자 포함 여부와 서문/종문 키워드로 서문/본문/종문 구분
- Footer 기반 챕터 탐지: Footer 구조 판별자에 나타나는 숫자를 기준으로 챕터 구분 (특별한 식별자 무시)
- 좌측 페이지 우선: 홀수 페이지(좌측)의 Footer를 기준으로 판단하고, 짝수 페이지(우측)는 인접한 홀수 페이지와 동일하게 처리
- LLM 보정 제외: 휴리스틱 기반 구조 분석만 사용 (LLM 보정 로직 미적용)

**⚠️ Git 커밋 전략**:
- 각 단계(3.1, 3.2, 3.3, 3.5, 3.6) 완료 후 즉시 커밋
- 작은 단위로 커밋하여 문제 발생 시 원복 가능하도록
- 커밋 메시지 형식: `[Phase 3] 작업 단계: 상세 설명`

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
