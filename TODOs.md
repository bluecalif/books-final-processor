# 도서 PDF 구조 분석 및 서머리 서비스 개발 계획

> PRD: `docs/PRD_books-processor.md`  
> 핵심 로직 참고: `docs/core_logics.md`  
> 선행 서비스 참고: `docs/book-assistant_repomix_backend.md`  
> 이전 계획: `TODOs_archive_20241215.md` 참고

## 프로젝트 개요

도서 PDF 파일을 업로드하면 자동으로 책의 구조(본문 시작, 챕터 경계 등)를 파악하고, 페이지별 및 챕터별 서머리를 생성하는 웹 서비스입니다.

**핵심 파이프라인**: `PDF 업로드 → Upstage API 파싱 → 구조 분석(휴리스틱) → 페이지/챕터 요약 → SQLite 저장`

**프로젝트 범위**: 프론트엔드 없이 백엔드에서 종료

## 프로젝트 현재 상황

### 전체 진행률: 약 85% (Phase 1, Phase 2, Phase 3, Phase 4 완료, Phase 5 진행 예정)

| Phase | 제목 | 진행률 | 상태 |
|-------|------|-------|------|
| Phase 1 | 프로젝트 기초 및 환경 설정 | 100% | 완료 |
| Phase 2 | PDF 파싱 모듈 (Upstage API 연동) | 100% | 완료 |
| Phase 3 | 구조 분석 모듈 | 100% | 완료 |
| Phase 4 | 대량 도서 처리 프레임 단계 | 100% | 완료 |
| Phase 5 | 내용 추출 및 요약 모듈 | 0% | 미시작 |
| Phase 6 | 통합 및 테스트 | 0% | 미시작 |

## Git 저장소 정보

**GitHub 저장소**: https://github.com/bluecalif/books-final-processor.git

**⚠️ 중요**: Git 업데이트 및 실행을 안하는 경우가 있으니, 반드시 주의할 것

### Git 워크플로우 (필수)

**⚠️ 중요: 작은 단위로 커밋하여 문제 발생 시 원복 가능하도록**

**Phase 작업 전**: `git status` → `git pull origin main`  
**Phase 작업 중**: 각 단계 완료 후 즉시 커밋 (작은 단위로 커밋)  
**Phase 작업 완료 후**: `git add .` → `git commit -m "[Phase X] 작업 내용"` → `git push origin main`

**커밋 메시지 규칙**: `[Phase X] 작업 단계: 상세 설명`

## 기술 스택

### 백엔드
- Python 3.10+, FastAPI, SQLAlchemy, SQLite, Poetry, Pydantic

### 외부 API
- Upstage Document Digitization API, OpenAI API

---

## Phase 1-3 핵심 요약

### Phase 1: 프로젝트 기초 및 환경 설정 (100% 완료)

**완료된 주요 작업**:
- Poetry 프로젝트 초기화 (Python 3.10+, Poetry 1.8.5+)
- FastAPI 기본 구조 생성 (CORS, 라우터 등록, 헬스체크)
- SQLite DB 설정 (SQLAlchemy ORM, Book/Chapter/Page 모델)
- 환경변수 설정 (Pydantic Settings)
- Git 저장소 초기화 및 원격 연결
- E2E 테스트 환경 설정 (`conftest_e2e.py`, 실제 서버 실행)

**검증 완료**: FastAPI 서버 실행, DB 연결, E2E 테스트 환경 동작 확인

### Phase 2: PDF 파싱 모듈 (100% 완료)

**완료된 주요 작업**:
- UpstageAPIClient: 100페이지 분할 파싱, 병렬 처리 (10페이지 기본 모드), 재시도 로직, Rate limit 처리
- CacheManager: 파일 해시 기반 캐싱, 안전한 저장 (`data/cache/upstage/`)
- PDFParser: 캐싱 통합, 양면 분리, Elements 구조화 (BeautifulSoup, regex)
- 업로드 API: 파일 업로드, 백그라운드 파싱, DB 저장
- E2E 테스트: 실제 서버 실행, 캐시 저장/재사용 검증

**핵심 성과**:
- 병렬 처리 구현으로 성능 3-5배 향상
- 캐싱 시스템으로 Upstage API 호출 비용 절감
- E2E 테스트 통과율 100% (실제 서버, 실제 데이터)

### Phase 3: 구조 분석 모듈 (98% 완료)

**완료된 주요 작업**:
- ContentBoundaryDetector: Footer 기반 본문/서문/종문 경계 탐지
- ChapterDetector: Footer 기반 챕터 탐지 (숫자 기반)
- StructureBuilder: Footer 기반 휴리스틱 구조 생성
- 구조 분석 API: 후보 조회, 최종 구조 확정
- 텍스트 정리 모듈: 본문 텍스트만 정리하여 JSON 파일 생성

**핵심 원칙**:
- Footer 기반 판단 (좌측 페이지 우선)
- 숫자 기반 챕터 구분 (특별한 식별자 무시)
- LLM 보정 제외 (휴리스틱만 사용)

**검증 완료**:
- E2E 테스트 통과율 100% (10개 도서)
- Ground Truth 기반 정확도 평가 통과
- 캐시 재사용 검증 통과 (Upstage API 호출 없음)

**완료**: 3.8 도서 텍스트 파일 정리 테스트 ✅

---

## Phase 4: 대량 도서 처리 프레임 단계

**목표**: CSV 파일에 있는 87권의 책을 파싱 및 구조 분석까지 일괄 처리

**처리 대상**: `docs/100권 노션 원본_수정.csv` 파일의 87권 (이미 처리된 도서 제외)

**⚠️ Git 주의사항**: 작업 전 `git status`, `git pull origin main` 확인 / 작업 후 `git add .`, `git commit`, `git push origin main` 실행

### 4.1 분야 태그 시스템 구현

**목표**: Book 모델에 분야(category) 필드 추가, 캐시에도 분야 정보 저장

#### 4.1.1 Book 모델 확장
- [x] `backend/api/models/book.py` 수정 ✅ 완료
  - `category` 필드 추가 (String, nullable=True)
  - DB 마이그레이션: 기존 DB에 ALTER TABLE로 category 컬럼 추가 (`backend/scripts/add_category_column.py`)
- [x] `backend/api/schemas/book.py` 수정 ✅ 완료
  - `BookResponse`, `BookCreate`에 `category` 필드 추가
- [x] `backend/api/services/book_service.py` 수정 ✅ 완료
  - `create_book()`에서 category 필드 처리 추가

#### 4.1.2 캐시 메타데이터 확장
- [x] `backend/parsers/cache_manager.py` 수정 ✅ 완료
  - `save_cache()` 메서드에 `category` 파라미터 추가 (Optional)
  - `_cache_meta`에 `category` 필드 저장
- [x] `backend/scripts/migrate_cache_category.py` 생성 ✅ 완료
  - 기존 캐시 파일에 분야 정보 추가 (마이그레이션 스크립트)
  - DB의 Book 레코드와 캐시 파일의 pdf_path 매칭하여 분야 정보 추가

**Git 커밋**: `git add .` → `git commit -m "[Phase 4] 분야 태그 시스템 구현 (Book 모델 확장, 캐시 메타데이터 확장)"` → `git push origin main`

### 4.2 CSV 파일 파서 구현

**목표**: CSV 파일에서 도서 리스트 및 분야 정보 추출

- [x] `backend/utils/csv_parser.py` 생성 ✅ 완료
  - `BookCSVParser` 클래스: CSV 파일 파싱
  - `parse_book_list(csv_path)`: CSV 파일 파싱 함수
  - 컬럼 매핑: `일련번호`, `Title`, `연도`, `저자`, `분야`, `Topic`, `요약`
  - 반환 형식: `List[Dict[str, Any]]` (각 도서 정보)
  - 분야 정보 검증 및 정규화 (빈 값 → "미분류", 길이 제한)
  - 테스트 결과: 87개 도서 파싱 성공 (경제/경영 28개, 과학/기술 23개, 역사/사회 18개, 인문/자기계발 18개)

**Git 커밋**: `git add .` → `git commit -m "[Phase 4] CSV 파일 파서 구현"` → `git push origin main`

### 4.3 이미 처리된 도서 확인

**목표**: DB에서 이미 구조 분석이 완료된 도서를 제외

- [x] `backend/utils/processed_books_checker.py` 생성 ✅ 완료
  - `ProcessedBooksChecker` 클래스: 이미 처리된 도서 확인
  - `get_processed_books(db_session)`: DB에서 `status >= 'structured'`인 도서 조회
  - `get_processed_titles(db_session)`: 정규화된 제목 리스트 반환
  - `is_book_processed(csv_title, db_session)`: CSV 제목이 이미 처리되었는지 확인
  - `find_matching_processed_book()`: CSV 제목과 매칭되는 처리된 도서 찾기
  - CSV의 `Title`과 DB의 `title` 매칭 로직 (제목 정규화 포함)
  - 테스트 결과: 10개 처리 완료, CSV에서 9개 매칭 (처리 대기: 78개)

**Git 커밋**: `git add .` → `git commit -m "[Phase 4] 이미 처리된 도서 확인 로직 구현"` → `git push origin main`

### 4.4 대량 도서 처리 스크립트 구현

**목표**: CSV 파일의 87권을 일괄 처리 (파싱 + 구조 분석 + 텍스트 생성)

- [x] `backend/scripts/batch_process_books_step_by_step.py` 생성 ✅ 완료
  - CSV 파일 읽기 (`docs/100권 노션 원본_수정.csv`)
  - 이미 처리된 도서 제외 (4.3 로직 사용)
  - 단계별 배치 처리 (모든 책 파싱 → 모든 책 구조 분석 → 모든 책 텍스트 생성)
  - 각 도서별 처리 플로우:
    1. PDF 파일 경로 확인 (`data/input/`)
    2. Book 레코드 생성 또는 조회 (제목, 저자, 분야 정보 포함)
    3. PDF 파싱 실행 (`use_cache=True` - 캐시 재사용 필수)
       - 캐시 히트 확인 (Upstage API 호출 횟수 = 0)
       - 로그에서 "Cache hit" 메시지 확인
    4. 구조 분석 실행 (캐시된 파싱 결과 재사용)
       - 캐시 재사용 검증 (Upstage API 호출 없음)
    5. 텍스트 파일 생성 (구조 분석 완료 후)
    6. 진행 상황 로깅 (도서별, 전체 진행률, 소요시간)
  - 병렬 처리: Phase 3(구조 분석), Phase 4(텍스트 생성)에 ThreadPoolExecutor 적용
  - 에러 처리: 개별 도서 실패 시에도 나머지 도서 계속 처리
  - 결과 리포트 생성 (성공/실패 도서 수, 분야별 통계)

**캐시 검증**:
- 파싱 시 캐시 히트 확인 (Upstage API 호출 횟수 = 0)
- 로그에서 "Cache hit" 메시지 확인
- 캐시 파일 존재 확인 (`data/cache/upstage/{hash}.json`)

**Git 커밋**: `git add .` → `git commit -m "[Phase 4] 대량 도서 처리 스크립트 구현"` → `git push origin main`

### 4.5 분야별 통계 및 리포트

**목표**: 처리 결과를 분야별로 집계하여 리포트 생성

- [x] `backend/scripts/verify_batch_processing.py` 생성 ✅ 완료
  - 배치 처리 로그 파싱 및 검증
  - 출력 파일 존재 여부 확인 (캐시, 구조, 텍스트)
  - DB 상태 검증
- [x] 진단 스크립트 (`backend/scripts/diagnose_processing_issues.py`) 생성 ✅ 완료
  - 파싱 문제 진단 (페이지 완전성 검증 포함)
  - 구조 분석 문제 진단
  - 텍스트 생성 문제 진단

**Git 커밋**: `git add .` → `git commit -m "[Phase 4] 분야별 통계 및 리포트 생성"` → `git push origin main`

### 4.6 대량 도서 처리 실행 및 검증

**목표**: 실제로 87권의 책을 처리하고 결과 검증

- [x] 배치 처리 스크립트 실행 ✅ 완료
  - CSV 파일 기준 87권 처리 완료
  - 이미 처리된 도서는 제외 (DB 조회)
  - 각 도서별 파싱, 구조 분석, 텍스트 생성 완료
- [x] 캐시 재사용 검증 ✅ 완료
  - 모든 처리에서 캐시 히트 확인 (Upstage API 호출 = 0)
  - 캐시 파일에 분야 정보 포함 확인
- [x] 결과 검증 ✅ 완료
  - DB에 모든 도서 저장 확인 (87권)
  - 구조 분석 완료 상태 (`status = 'structured'`) 확인
  - 텍스트 파일 생성 완료 확인 (87개)
  - 분야 정보가 DB에 저장되었는지 확인

**검증 기준**:
- [x] 87권 모두 처리 완료 ✅
- [x] 모든 처리에서 캐시 재사용 (Upstage API 호출 없음) ✅
- [x] 모든 도서의 분야 정보가 DB에 저장됨 ✅
- [x] 텍스트 파일 87개 모두 생성 완료 ✅

**Git 커밋**: `git add .` → `git commit -m "[Phase 4] 대량 도서 처리 완료 및 검증"` → `git push origin main`


---

## Phase 5: 내용 추출 및 요약 모듈

**목표**: `docs/entity_extraction_guideline.md`를 바탕으로 페이지 단위 엔티티 추출 및 챕터 단위 구조화 파이프라인 구현

> **참고**: 단순 요약이 아닌 **구조화된 엔티티 추출**을 통해 사건·예시·개념·인사이트·참고자료를 입체적으로 재사용 가능하게 만듦

**핵심 원칙**:
- 2단계 파이프라인: 페이지 구조화 → 챕터 구조화
- 도메인별 스키마 지원 (역사/사회, 경제/경영, 인문/자기계발, 과학/기술)
- Book.category 기반 도메인 자동 선택
- 구조화된 JSON 데이터 저장 (단순 텍스트가 아님)

**참고 문서**: `docs/entity_extraction_guideline.md` (작업 지침)

#### 5.1 데이터 모델 확장
- [x] `backend/api/models/book.py` 수정 ✅ 완료
  - `PageSummary` 모델에 `structured_data` 필드 추가 (JSON, nullable=True)
    - 공통 필드: `page_summary`, `persons`, `concepts`, `events`, `examples`, `references`, `key_sentences`
    - 도메인별 확장 필드 (JSON 내부에 저장)
  - `ChapterSummary` 모델에 `structured_data` 필드 추가 (JSON, nullable=True)
    - 공통 필드: `core_message`, `summary_3_5_sentences`, `argument_flow`, `key_*`, `insights`, `chapter_level_synthesis`
    - 도메인별 확장 필드 (JSON 내부에 저장)
- [x] `backend/scripts/add_structured_data_columns.py` 생성 ✅ 완료
  - DB 마이그레이션 스크립트: ALTER TABLE로 `structured_data` 컬럼 추가
- [x] `backend/api/schemas/book.py` 수정 ✅ 완료
  - `PageSummaryResponse`, `ChapterSummaryResponse`에 `structured_data` 필드 추가

#### 5.2 도메인 스키마 정의
- [x] `backend/summarizers/schemas.py` 생성 ✅ 완료
  - `BasePageSchema` (Pydantic): 공통 필드 정의
    - `page_summary: str` (2~4문장)
    - `page_function_tag: Optional[str]` (예: "problem_statement", "example_story", "data_explanation")
    - `persons: List[str]`
    - `concepts: List[str]`
    - `events: List[str]`
    - `examples: List[str]`
    - `references: List[str]`
    - `key_sentences: List[str]`
    - `tone_tag: Optional[str]`, `topic_tags: List[str]`, `complexity: Optional[str]`
  - `BaseChapterSchema` (Pydantic): 공통 필드 정의
    - `core_message: str` (한 줄)
    - `summary_3_5_sentences: str`
    - `argument_flow: Dict[str, Any]` (problem, background, main_claims, evidence_overview, counterpoints_or_limits, conclusion_or_action)
    - `key_events: List[str]`, `key_examples: List[str]`, `key_persons: List[str]`, `key_concepts: List[str]`
    - `insights: List[Dict[str, Any]]` (type, text, supporting_evidence_ids)
    - `chapter_level_synthesis: str`
    - `references: List[str]`
  - 도메인별 스키마 (상속):
    - `HistoryPage`, `EconomyPage`, `HumanitiesPage`, `SciencePage` (BasePageSchema 상속)
    - `HistoryChapter`, `EconomyChapter`, `HumanitiesChapter`, `ScienceChapter` (BaseChapterSchema 상속)
  - 도메인 매핑 함수: `get_domain_from_category(category: str) -> str`
    - "역사/사회" → "history"
    - "경제/경영" → "economy"
    - "인문/자기계발" → "humanities"
    - "과학/기술" → "science"
  - 스키마 클래스 반환 함수: `get_page_schema_class()`, `get_chapter_schema_class()`

#### 5.3 LLM Chains 구현
- [x] `backend/summarizers/llm_chains.py` 생성 ✅ 완료
  - `PageExtractionChain`: 페이지 엔티티 추출 (도메인별 스키마 사용)
    - OpenAI API 클라이언트 초기화
    - Structured Output 사용 (Pydantic 스키마 기반)
    - 도메인별 프롬프트 템플릿
    - 모델: `gpt-4o-mini` (권장), 온도: 0.3
    - 텍스트 길이 제한 (4000자)
  - `ChapterStructuringChain`: 챕터 구조화 (페이지 결과 집계)
    - 페이지 엔티티 압축/집계 후 LLM 호출
    - 도메인별 프롬프트 템플릿
    - Structured Output 사용
  - 프롬프트 템플릿 설계 원칙:
    - 입력 컨텍스트: `book_title`, `chapter_title`, `domain`, `raw_page_text` (또는 압축된 페이지 엔티티)
    - 출력 포맷: 도메인별 `*Page`/`*Chapter` 스키마 (JSON)
    - 할루시네이션 방지: 원문에 없는 내용 생성 금지
    - 도메인별 추가 필드 지침 포함

#### 5.4 Page Extractor 구현
- [ ] `backend/summarizers/page_extractor.py` 생성
  - `PageExtractor` 클래스
  - `extract_page_entities(page_text, book_context, domain, use_cache=True)` 메서드
    - 입력: `page_text`, `book_context` (book_title, chapter_title, chapter_number), `domain`
    - SummaryCacheManager 통합 (캐시 확인 → LLM 호출 → 캐시 저장)
    - 도메인별 스키마 선택 및 LLM 호출
    - 결과를 JSON으로 변환하여 반환
  - **캐시 통합**: SummaryCacheManager 사용, 콘텐츠 해시 기반 캐시 키

#### 5.5 Chapter Structurer 구현
- [ ] `backend/summarizers/chapter_structurer.py` 생성
  - `ChapterStructurer` 클래스
  - `structure_chapter(page_entities_list, book_context, domain, use_cache=True)` 메서드
    - 입력: `page_entities_list` (페이지 엔티티 목록), `book_context`, `domain`
    - 페이지 엔티티 집계/압축 (상위 N개만 추려서 LLM에 전달)
    - SummaryCacheManager 통합
    - 결과를 JSON으로 변환하여 반환
  - **캐시 통합**: SummaryCacheManager 사용, 압축된 페이지 엔티티 해시 기반 캐시 키

#### 5.6 Extraction Service 구현
- [ ] `backend/api/services/extraction_service.py` 생성
  - 요약 생성 비즈니스 로직
  - **PDF 파싱 캐시 사용**: `pdf_parser.parse_pdf(use_cache=True)` - 캐시된 파싱 결과 재사용
  - 페이지 엔티티 추출:
    - 본문 페이지만 처리 (structure_data.main.pages 기준)
    - 각 페이지별로 `PageExtractor.extract_page_entities()` 호출
    - 결과를 `PageSummary.structured_data`에 JSON으로 저장
    - `summary_text`는 `page_summary` 필드에서 추출하여 저장 (하위 호환성)
  - 챕터 구조화:
    - 각 챕터별로 해당 페이지 엔티티들을 집계
    - `ChapterStructurer.structure_chapter()` 호출
    - 결과를 `ChapterSummary.structured_data`에 JSON으로 저장
    - `summary_text`는 `summary_3_5_sentences` 필드에서 추출하여 저장 (하위 호환성)
  - DB 저장 및 상태 업데이트:
    - `page_summarized` 상태로 업데이트 (페이지 엔티티 추출 완료 시)
    - `summarized` 상태로 업데이트 (챕터 구조화 완료 시)
  - **⚠️ 챕터 1-2개인 책 제외**: 챕터가 1개 또는 2개인 책은 요약 생성에서 제외 (Phase 6.1에서 구조 분석 강화 후 처리)
  - 백그라운드 작업 지원

#### 5.7 Extraction API 구현
- [ ] `backend/api/routers/extraction.py` 생성
  - `GET /api/books/{id}/pages`: 페이지별 엔티티 리스트 (structured_data 포함)
  - `GET /api/books/{id}/pages/{page_number}`: 페이지 엔티티 상세
  - `GET /api/books/{id}/chapters`: 챕터별 구조화 결과 리스트 (structured_data 포함)
  - `GET /api/books/{id}/chapters/{chapter_id}`: 챕터 구조화 결과 상세
  - `POST /api/books/{id}/extract/pages`: 페이지 엔티티 추출 시작 (백그라운드 작업)
  - `POST /api/books/{id}/extract/chapters`: 챕터 구조화 시작 (백그라운드 작업)
- [ ] `backend/api/main.py`에 라우터 등록

#### 5.8 Extraction 모듈 테스트
- [ ] **E2E 테스트** (⚠️ 실제 서버 실행, 실제 데이터만):
  - 전체 엔티티 추출 플로우: 구조 확정된 책 (챕터 3개 이상) → 페이지 엔티티 추출 (실제 OpenAI API) → 챕터 구조화, DB 저장 검증, 상태 변경 검증
  - **도메인별 스키마 검증**: 각 도메인(역사/사회, 경제/경영, 인문/자기계발, 과학/기술)별로 올바른 스키마가 생성되는지 확인
  - **구조화된 JSON 데이터 검증**: `structured_data` 필드에 올바른 JSON 구조가 저장되는지 확인
  - **캐시 저장 검증**: 엔티티 추출 후 `data/cache/summaries/`에 캐시 파일 생성 확인
  - **캐시 재사용 검증**: 두 번째 추출 시 캐시 히트 확인 (LLM 호출 없이 캐시 사용)
  - Extraction API: `GET /api/books/{id}/pages`, `GET /api/books/{id}/chapters`, `GET /api/books/{id}/chapters/{chapter_id}`, 백그라운드 작업
  - 실제 LLM 연동: OpenAI API 호출 검증, Structured Output 검증, API 에러 처리 검증
  - **챕터 1-2개 제외 검증**: 챕터가 1개 또는 2개인 책은 엔티티 추출에서 제외되는지 확인

**검증**: E2E 테스트 통과 (⚠️ 실제 서버 실행, 실제 LLM 연동, 실제 엔티티 추출, Mock 사용 금지)

**⚠️ Git 커밋**: Phase 5 완료 후 `git add .`, `git commit -m "[Phase 5] 내용 추출 및 요약 모듈 구현"`, `git push origin main`

---

## Phase 6: 통합 및 테스트

**목표**: 전체 파이프라인 통합 및 품질 향상

> **참고**: 프론트엔드는 백엔드에서 종료하므로 프론트엔드 관련 항목은 제외

#### 6.1 구조 분석 강화 (챕터 1-2개 세분화)

**목표**: 챕터가 1개 또는 2개인 책의 구조 분석을 더 세분화하여 개선

**현재 상황**:
- 챕터 1개: 2권 (ID 188: MIT 스타트업 바이블, ID 242: 뉴스의 시대)
- 챕터 2개: 3권 (ID 193: 강남되는 강북부동산은 정해져 있다, ID 230: 냉정한 이타주의자, ID 244: 다크 데이터)

**보강 계획**:
- [ ] 챕터 1-2개인 책의 구조 분석 개선 로직 추가
  - Footer 기반 세부 섹션 탐지
  - 페이지 내용 분석을 통한 논리적 구분점 탐지
  - 수동 보정 인터페이스 (필요시)
- [ ] 개선된 구조 분석 적용 및 재처리
  - 챕터 1-2개인 5권에 대해 구조 분석 재실행
  - 텍스트 파일 재생성
- [ ] 재처리 후 요약 모듈 적용
  - 챕터 세분화 완료된 책들에 대해 Phase 5 요약 모듈 적용

**참고**: Phase 5 요약 모듈에서는 챕터 1-2개인 책은 제외하고 진행 (Phase 6.1 완료 후 적용)

#### 6.2 백엔드 전체 파이프라인 E2E 테스트 (필수 완료)

**⚠️ 중요: 모든 E2E 테스트는 실제 서버 실행, Mock 사용 금지, 실제 데이터만 사용** (실제 PDF, 실제 Upstage API, 실제 OpenAI LLM, 실제 DB)

- [ ] **전체 플로우 E2E 테스트** (`tests/test_e2e.py`, 실제 서버 실행):
  - 1. `POST /api/books/upload` → 책 생성 (`uploaded`)
  - 2. 실제 Upstage API로 PDF 파싱 → `parsed` 상태 확인 → **캐시 저장 확인** (`data/cache/upstage/`)
  - 3. `GET /api/books/{id}/structure/candidates` → 구조 후보 생성 → **캐시된 파싱 결과 재사용 확인**
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

#### 6.3 에러 처리 강화
- [ ] Upstage API 실패 처리 (네트워크 에러, Rate limit, `error_parsing` 상태 업데이트, 에러 로그 저장)
- [ ] LLM 요약 실패 처리 (`error_summarizing` 상태, 부분 실패 처리)
- [ ] 재시도 로직 개선 (지수 백오프, 최대 재시도 횟수 제한)

#### 6.4 성능 최적화
- [ ] 페이지 요약 병렬 처리 (asyncio 또는 멀티프로세싱, 배치 처리)
- [x] **캐싱 전략 구현 완료**: ✅ 완료
  - Upstage API 파싱 결과 캐싱 (`data/cache/upstage/`) ✅ 완료
  - OpenAI 요약 결과 캐싱 (`data/cache/summaries/`) ✅ 완료
  - 파일 해시 기반 캐시 키 (같은 내용이면 경로 무관하게 재사용) ✅ 완료
  - 구조 분석기에서 캐시된 파싱 결과 재사용 ✅ 완료
- [ ] 캐시 정리 기능 (오래된 캐시 자동 삭제, 캐시 통계 조회)
- [ ] DB 쿼리 최적화 (인덱스 추가, N+1 쿼리 방지)

#### 6.5 문서화
- [ ] API 문서 작성 (FastAPI 자동 생성)
- [ ] README.md 작성 (프로젝트 소개, 설치/실행 방법, 환경변수 설정, 테스트 실행 방법)
- [ ] 코드 주석 보완
- [ ] 테스트 문서 작성 (테스트 구조, E2E 테스트 실행 방법, 테스트 데이터 준비)

#### 6.6 백엔드 테스트 완료 검증 (프론트엔드 연동 전 필수)
- [ ] **테스트 커버리지 확인**: 전체 80% 이상 (핵심 로직 100%), 핵심 모듈 90% 이상 (UpstageAPIClient 100%, PDFParser/StructureBuilder/SummaryService 90%+)
- [ ] **모든 테스트 통과 확인**: 단위/통합/E2E 테스트 모두 통과, `pytest --cov=backend tests/` 실행 결과 확인
- [ ] **API 계약 문서화**: OpenAPI 스키마 생성 (`/openapi.json`), API 문서, 요청/응답 예시
- [ ] **테스트 리포트 생성**: 테스트 실행 결과 리포트, 커버리지 리포트, 실패 테스트 확인

**백엔드 E2E 테스트 완료 기준**:
- ✅ Phase 1-5 모든 단계별 테스트 통과
- ✅ 전체 플로우 E2E 테스트 통과 (최소 3가지 시나리오, ⚠️ 실제 데이터 사용 필수: 실제 PDF, 실제 Upstage API, 실제 OpenAI LLM, Mock 사용 금지)
- ✅ API 계약 검증 통과
- ✅ 테스트 커버리지 목표 달성
- ✅ 에러 플로우 테스트 통과

**⚠️ E2E 테스트 필수 원칙**: 실제 서버 실행, Mock 사용 절대 금지, 실제 외부 API 연동, 실제 PDF 파일 사용, 실제 DB 데이터 검증

**검증**: 백엔드 단독으로 모든 기능이 실제 데이터로 정상 작동함을 E2E 테스트로 확인

**⚠️ Git 커밋**: Phase 6 완료 후 `git add .`, `git commit -m "[Phase 6] 백엔드 E2E 테스트 완료 및 통합 검증"`, `git push origin main`

---

## 데이터 모델 (SQLite)

### books
- `id`, `title`, `author`, `category` (분야), `source_file_path`, `page_count`, `status` (enum), `structure_data` (JSON), `created_at`, `updated_at`

### pages
- `id`, `book_id` (FK), `page_number`, `raw_text`, `metadata` (JSON)

### chapters
- `id`, `book_id` (FK), `title`, `order_index`, `start_page`, `end_page`, `section_type`, `created_at`

### page_summaries
- `id`, `book_id` (FK), `page_id` (FK), `page_number`, `summary_text`, `lang`, `created_at`

### chapter_summaries
- `id`, `book_id` (FK), `chapter_id` (FK), `summary_text`, `lang`, `created_at`

---

## 주요 참고 문서

- `docs/PRD_books-processor.md`: 제품 요구사항 문서
- `docs/core_logics.md`: 구조 분석 로직 상세 설계
- `docs/book-assistant_repomix_backend.md`: 선행 서비스 코드 참고
- `TODOs_archive_20241215.md`: 이전 계획 문서 (참고용)

## 주의사항

1. **상태 관리**: `uploaded → parsed → structured → page_summarized → summarized` 순서로 진행
2. **SQLite → Supabase 전환 고려**: DB 추상화 레이어를 두어 추후 전환 용이하도록 설계
3. **⚠️ 실제 데이터 테스트 필수 (E2E 테스트)**: Mock 사용 절대 금지, 실제 PDF 파일, 실제 Upstage API, 실제 OpenAI LLM, 실제 DB 데이터 검증
4. **⚠️ Git 버전 관리 필수**: Git 업데이트 및 실행을 안하는 경우가 있으니 반드시 주의, 각 Phase 완료 후 커밋 및 푸시, 작업 전 `git status`, `git pull origin main` 확인
5. **이모지 사용 금지**: PowerShell 환경 고려
6. **Poetry 1.8.5 이상 필수**: 메타데이터 버전 2.4 지원
7. **AGENTS.md 규칙 준수**: PowerShell 명령어, 환경변수 관리, 프로젝트 실행 규칙 등
8. **프론트엔드 제외**: 백엔드에서 프로젝트 종료, 프론트엔드 구현 제외
