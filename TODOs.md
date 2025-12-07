# 도서 PDF 구조 분석 및 서머리 서비스 개발 계획

> PRD: `docs/PRD_books-processor.md`  
> 핵심 로직 참고: `docs/core_logics.md`  
> 선행 서비스 참고: `docs/book-assistant_repomix_backend.md`  
> 이전 계획: `TODOs_archive_20241215.md`, `TODOs_archive_20251207_122200.md` 참고

## 프로젝트 개요

도서 PDF 파일을 업로드하면 자동으로 책의 구조(본문 시작, 챕터 경계 등)를 파악하고, 페이지별 및 챕터별 서머리를 생성하는 웹 서비스입니다.

**핵심 파이프라인**: `PDF 업로드 → Upstage API 파싱 → 구조 분석(휴리스틱) → 페이지/챕터 요약 → SQLite 저장`

**프로젝트 범위**: 프론트엔드 없이 백엔드에서 종료

## 프로젝트 현재 상황

### 전체 진행률: 약 83% (Phase 1-5 완료, Phase 6 미시작)

| Phase | 제목 | 진행률 | 상태 |
|-------|------|-------|------|
| Phase 1 | 프로젝트 기초 및 환경 설정 | 100% | 완료 |
| Phase 2 | PDF 파싱 모듈 (Upstage API 연동) | 100% | 완료 |
| Phase 3 | 구조 분석 모듈 | 100% | 완료 |
| Phase 4 | 대량 도서 처리 프레임 단계 | 100% | 완료 |
| Phase 5 | 내용 추출 및 요약 모듈 | 100% | 완료 |
| Phase 6 | Summary 캐시 시각화 및 변환 정교화 | 85% | 진행 중 (6.1, 6.2 완료, 6.3 미시작) |
| Phase 7 | 통합 및 테스트 | 0% | 미시작 |

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

## Phase 1-5 핵심 요약

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

### Phase 3: 구조 분석 모듈 (100% 완료)

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

**⚠️ 참고 (파이프라인 정합성)**:
- 이 단계는 **메인 파이프라인의 일부가 아님**
- Phase 5 엔티티 추출은 `data/output/text/` 파일을 사용하지 않음
- 대신 **캐시에서 직접 raw_text를 재생성**하여 사용
- `data/output/text/` 파일은 **API 엔드포인트** `GET /api/books/{id}/text` **용도로만 제공**
- 프론트엔드가 없으므로 실제 사용 빈도는 낮음

### Phase 4: 대량 도서 처리 프레임 단계 (100% 완료)

**완료된 주요 작업**:
- 분야 태그 시스템 구현: Book 모델에 category 필드 추가, 캐시 메타데이터 확장
- CSV 파일 파서 구현: 87개 도서 파싱 성공 (경제/경영 28개, 과학/기술 23개, 역사/사회 18개, 인문/자기계발 18개)
- 이미 처리된 도서 확인 로직: DB에서 `status >= 'structured'`인 도서 제외
- 대량 도서 처리 스크립트: 87권 일괄 처리 (파싱 + 구조 분석 + 텍스트 생성)
- 분야별 통계 및 리포트: 배치 처리 로그 파싱, 진단 스크립트

**핵심 성과**:
- 87권 모두 처리 완료
- 모든 처리에서 캐시 재사용 (Upstage API 호출 없음)
- 모든 도서의 분야 정보가 DB에 저장됨
- 텍스트 파일 87개 모두 생성 완료

### Phase 5: 내용 추출 및 요약 모듈 (100% 완료)

**완료된 주요 작업**:
- 데이터 모델 확장: `PageSummary.structured_data`, `ChapterSummary.structured_data` 필드 추가
- 도메인 스키마 정의: BasePageSchema, BaseChapterSchema 및 도메인별 스키마 (History, Economy, Humanities, Science)
- LLM Chains 구현: PageExtractionChain, ChapterStructuringChain (Structured Output 사용, gpt-4o-mini)
- Page Extractor 구현: SummaryCacheManager 통합, 콘텐츠 해시 기반 캐시 키
- Chapter Structurer 구현: 페이지 엔티티 집계/압축, 캐시 통합
- Extraction Service 구현: 병렬 처리 (worker=5), 토큰 계산 및 모니터링
- Extraction API 구현: 페이지/챕터 엔티티 조회, 백그라운드 작업 지원
- E2E 테스트: 4권 도서 검증 완료 (Book 176, 177, 184, 175)

**핵심 성과**:
- 도메인별 구조화된 엔티티 추출 (사건·예시·개념·인사이트·참고자료)
- 병렬 처리로 성능 개선 (챕터 구조화: 56초 → 9.52초/챕터, 83% 단축)
- 캐시 시스템으로 OpenAI API 호출 비용 절감
- 4권 E2E 테스트 통과 (총 1,806 페이지, 46/47 챕터 성공, 총 비용 약 $2.32)

**테스트 결과 (4권 도서)**:
- Book 176 (역사/사회, 8챕터): 385/385 페이지, 8/8 챕터 성공
- Book 177 (경제/경영, 19챕터): 473/473 페이지, 19/19 챕터 성공
- Book 184 (과학/기술, 8챕터): 325/350 페이지, 7/8 챕터 성공
- Book 175 (인문/자기계발, 12챕터): 623/646 페이지, 12/12 챕터 성공

**⚠️ 참고**:
- 챕터 1-2개인 책은 요약 생성에서 제외 (Phase 7.1에서 구조 분석 강화 후 처리)
- `data/output/text/` 파일은 사용하지 않음 (캐시에서 직접 raw_text 재생성)

---

## Phase 6: Summary 캐시 시각화 및 변환 정교화

**목표**: Summary 캐시를 시각화 가능한 구조로 변경하고, 페이지 엔티티 → 챕터 서머리 변환을 정교화하며, 챕터 서머리 → 도서 전체 서머리 생성 기능을 추가합니다.

**핵심 원칙**:
1. Summary 캐시 시각화: JSON 문자열 → 구조화된 필드 전개
2. 변환 정교화: 사용자 리뷰 기반 개선
3. 도서 전체 서머리 생성: 챕터 서머리 집계

### 6.1 Summary 캐시 시각화

**목표**: 현재 캐시의 `summary_text` 필드에 JSON 문자열로 저장된 구조를 각 필드를 별도 key로 전개하여 시각화 가능하게 변경합니다.

**현재 구조**:
```json
{
  "summary_text": "{\"page_summary\":\"...\",\"persons\":[...],...}",
  "summary_type": "page",
  "content_hash": "...",
  "cached_at": 1234567890
}
```

**변경 후 구조**:
```json
{
  "page_summary": "...",
  "persons": [...],
  "concepts": [...],
  "events": [...],
  "summary_type": "page",
  "content_hash": "...",
  "cached_at": 1234567890
}
```

#### 6.1.1 기존 캐시 변환 스크립트 작성
- [x] `backend/scripts/migrate_cache_to_visualizable.py` 생성 ✅ 완료
  - `data/cache/summaries/` 디렉토리 순회
  - **현재 summary가 생성된 캐시만 변환** (DB에서 `status >= 'page_summarized'`인 도서의 캐시만)
  - 각 캐시 파일의 `summary_text` JSON 문자열 파싱
  - 파싱된 필드를 루트 레벨로 전개
  - 기존 파일 백업 (`.backup` 확장자 추가)
  - 변환된 구조로 저장
  - 변환 통계 출력 (성공/실패 개수, 도서별 통계)
  - **참고**: 추후 생성되는 캐시는 자동으로 새 형식으로 저장됨
- [x] `backend/scripts/organize_cache_backups.py` 생성 ✅ 완료
  - 백업 파일들을 각 책별 `backup/` 폴더로 정리
  - 총 1,928개 백업 파일 정리 완료

#### 6.1.2 SummaryCacheManager 수정
- [x] `backend/summarizers/summary_cache_manager.py` 수정 ✅ 완료
  - `save_cache()` 메서드 수정
    - 입력: `structured_data: Dict[str, Any]` (이미 구조화된 딕셔너리)
    - `summary_text` 필드 제거, 각 필드를 루트 레벨로 저장
    - 메타데이터 필드 유지 (`summary_type`, `content_hash`, `cached_at`)
  - `get_cached_summary()` 메서드 수정
    - 반환 타입: `Optional[Dict[str, Any]]` (문자열이 아닌 딕셔너리)
    - 루트 레벨 필드들을 딕셔너리로 반환
    - 기존 형식 감지 시 경고 로그 출력
    - **주의**: 새로운 캐시 구조만 지원 (기존 형식 지원 제거, 변환 스크립트로 모두 변환)

#### 6.1.3 PageExtractor 및 ChapterStructurer 수정
- [x] `backend/summarizers/page_extractor.py` 수정 ✅ 완료
  - `extract_page_entities()` 메서드
    - 캐시 저장: `result_dict`를 직접 전달 (JSON 문자열 변환 제거)
    - 캐시 로드: 딕셔너리 반환 (JSON 파싱 제거)
- [x] `backend/summarizers/chapter_structurer.py` 수정 ✅ 완료
  - `structure_chapter()` 메서드
    - 캐시 저장: `result_dict`를 직접 전달
    - 캐시 로드: 딕셔너리 반환
    - **주의**: 새로운 시각화된 캐시 구조를 입력으로 받음

#### 6.1.4 변환 스크립트 실행 및 검증
- [x] 기존 캐시 변환 실행 ✅ 완료
  - 현재 summary가 생성된 모든 도서의 캐시 변환 (4권)
  - 변환 결과: 페이지 캐시 1,878개 성공, 챕터 캐시 50개 성공 (실패 0개)
  - 변환 후 캐시 파일 구조 검증 완료 (`summary_text` 필드 제거, 각 필드 루트 레벨 전개 확인)
  - 백업 파일 정리 완료 (1,928개 파일을 각 책별 `backup/` 폴더로 이동)
- [ ] E2E 테스트 실행 (선택사항)
  - 변환된 캐시로 엔티티 추출 재실행
  - 캐시 히트율 확인
  - 결과 일관성 검증

### 6.2 페이지 엔티티 → 챕터 서머리 변환 정교화

**목표**: 사용자 리뷰를 통해 페이지 엔티티와 챕터 서머리의 품질을 검증하고, 변환 로직을 개선합니다.

#### 6.2.1 시각화된 캐시 리뷰 도구 작성
- [x] `backend/scripts/review_cache.py` 생성 ✅ 완료
  - 페이지 엔티티 캐시 조회 및 표시
  - 챕터 서머리 캐시 조회 및 표시
  - **HTML 파일 생성** (브라우저에서 시각화)
  - 특정 도서/챕터/페이지 필터링 지원
  - 키워드 검색 기능
  - 페이지 엔티티 → 챕터 서머리 매핑 시각화

#### 6.2.2 사용자 리뷰 및 피드백 수집
- [x] 테스트 도서 4권의 페이지 엔티티 리뷰 ✅ 완료
  - Book 176 (1000년, 역사/사회, 8챕터)
  - Book 177 (100년 투자 가문의 비밀, 경제/경영, 19챕터)
  - Book 184 (AI지도책, 과학/기술, 8챕터)
  - Book 175 (12가지인생의법칙, 인문/자기계발, 12챕터)
  - 사용자 리뷰 결과: 페이지 엔티티 품질 OK
- [x] 테스트 도서 4권의 챕터 서머리 리뷰 ✅ 완료
  - 각 챕터별 구조화 결과 검토
  - 페이지 엔티티 통합 품질 검증
  - 사용자 리뷰 결과: 챕터 서머리 품질 OK

#### 6.2.3 변환 정합성 검토
- [x] 페이지 엔티티 → 챕터 서머리 변환 검증 ✅ 완료
  - 페이지 엔티티의 핵심 정보가 챕터 서머리에 반영되었는지 확인
  - 중복 제거 및 통합 로직 검증
  - 누락된 정보 확인
  - 사용자 리뷰 결과: 변환 정합성 OK
- [x] 정합성 리포트 생성 ✅ 완료
  - HTML 리뷰 파일을 통한 시각화 검증
  - 사용자 리뷰를 통한 품질 확인
  - 개선된 프롬프트로 재처리 완료

#### 6.2.4 변환 로직 개선
- [x] `backend/summarizers/llm_chains.py` 수정 ✅ 완료
  - `ChapterStructuringChain` 프롬프트 개선
    - key_events: 최대 8-10개, 중요도 기반 선별 지침 추가
    - key_examples: 최대 5-7개, 대표성 기반 선별 지침 추가
    - key_persons: 최대 8-10개, 중요도 기반 선별 지침 추가
    - key_concepts: 최대 10-12개, 중요도 기반 선별 지침 추가
    - 단순 병합 대신 중요도/대표성 기반 선별 지침 명시
- [x] `backend/summarizers/schemas.py` 수정 ✅ 완료
  - Field description에 최대 개수 및 선별 기준 명시
- [x] `backend/summarizers/chapter_structurer.py` 수정 ✅ 완료
  - **2페이지 이하 챕터 스킵**: 페이지 수가 2페이지 이하인 챕터는 서머리 생성하지 않음 (None 반환, 로그 기록)
  - **챕터 메타 정보 추가**: `chapter_number`, `chapter_title`, `page_count`를 캐시 메타데이터에 포함
  - **주의**: 새로운 시각화된 캐시 구조를 입력으로 받음
- [x] `backend/api/services/extraction_service.py` 수정 ✅ 완료
  - 2페이지 이하 챕터 스킵 로직 개선
    - `skipped_count` 추가하여 의도된 스킵과 실패 구분
    - 진행 상황 로그에 `skipped` 카운트 포함
    - 최종 리포트에 `skipped` 카운트 포함
- [x] 기존 캐시 보강 스크립트 작성 ✅ 완료
  - `backend/scripts/add_page_count_to_cache.py`: `page_count` 추가 (기존 캐시 보강)
  - `backend/scripts/add_chapter_metadata_to_cache.py`: `chapter_number`, `chapter_title` 추가 (기존 캐시 보강)

#### 6.2.5 개선된 로직으로 재처리
- [x] 챕터 서머리 재처리 스크립트 작성 ✅ 완료
  - `backend/scripts/delete_chapter_caches.py`: 챕터 서머리 캐시만 삭제 (페이지 엔티티 캐시 유지)
  - `backend/scripts/reprocess_chapter_summaries.py`: 개선된 프롬프트로 챕터 서머리 재생성
  - `backend/scripts/reprocess_all_test_books.py`: 테스트 도서 4권 일괄 재처리
- [x] 테스트 도서 4권 재처리 ✅ 완료
  - Book 176 (1000년): 8개 챕터 성공, 0개 실패, 0개 스킵
  - Book 177 (투자정신): 19개 챕터 성공, 0개 실패, 0개 스킵
  - Book 184 (AI지도책): 6개 챕터 성공, 0개 실패, 2개 스킵 (2페이지 이하)
  - Book 175 (12가지인생의법칙): 12개 챕터 성공, 0개 실패, 0개 스킵
  - 총 비용: $0.4379
  - 페이지 엔티티는 DB에서 읽어 재사용 (캐시 삭제 없음)
- [x] HTML 리뷰 파일 재생성 ✅ 완료
  - 4권 모두 HTML 리뷰 파일 생성 완료
  - 개선된 프롬프트로 생성된 챕터 서머리 확인 가능

### 6.3 챕터 서머리 → 도서 전체 서머리 생성

**목표**: 챕터 서머리를 집계하여 도서 전체 서머리를 생성하는 기능을 추가합니다.

#### 6.3.1 도서 서머리 항목 및 생성 로직 검토
- [ ] 도서 서머리 스키마 설계 제안
  - 공통 필드: `book_summary`, `core_themes`, `key_insights`, `main_arguments`
  - 도메인별 확장 필드 검토
  - **사용자 피드백 수렴 후 최종 결정**
- [ ] 생성 로직 설계
  - 챕터 서머리 집계 방식
  - LLM 프롬프트 설계
  - 캐시 전략 (도서 전체 서머리 캐시)

#### 6.3.2 도서 서머리 스키마 정의
- [ ] `backend/summarizers/schemas.py` 수정
  - `BaseBookSchema` 클래스 정의
    - 공통 필드: `book_summary`, `core_themes`, `key_insights`, `main_arguments`
  - 도메인별 스키마 정의
    - `HistoryBook`, `EconomyBook`, `HumanitiesBook`, `ScienceBook`
  - `get_book_schema_class()` 함수 추가

#### 6.3.3 도서 서머리 LLM Chain 구현
- [ ] `backend/summarizers/llm_chains.py` 수정
  - `BookSummarizationChain` 클래스 추가
    - 입력: 챕터 서머리 리스트, 책 컨텍스트
    - 출력: 도메인별 Book 스키마
    - Structured Output 사용
    - 프롬프트 템플릿 설계
    - **주의**: 새로운 시각화된 캐시 구조의 챕터 서머리를 입력으로 받음

#### 6.3.4 도서 서머리 서비스 구현
- [ ] `backend/api/services/book_summary_service.py` 생성
  - `BookSummaryService` 클래스
  - `summarize_book(book_id)` 메서드
    - 챕터 서머리 조회 (DB에서 `ChapterSummary.structured_data` 조회)
    - **챕터 서머리 압축/집계** (새로운 시각화된 캐시 구조 사용)
    - `BookSummarizationChain` 호출
    - 결과를 DB에 저장 (`Book.book_summary_data` 필드)
    - **로컬 파일 저장** (`data/output/book_summaries/{book_title}_summary.json`)
    - 캐시 저장 (SummaryCacheManager 사용, 새로운 시각화 구조)
  - 캐시 통합 (SummaryCacheManager)
  - **주의**: Book.status는 변경하지 않음 (기존 `SUMMARIZED` 상태 유지)

#### 6.3.5 도서 서머리 데이터 모델 확장
- [ ] `backend/api/models/book.py` 수정
  - `Book` 모델에 `book_summary_data` 필드 추가 (JSON, nullable=True)
- [ ] `backend/api/schemas/book.py` 수정
  - `BookSummaryResponse` 스키마 추가
- [ ] DB 마이그레이션 스크립트 작성
  - `backend/scripts/add_book_summary_column.py` 생성
- [ ] 로컬 파일 저장 기능 추가
  - `data/output/book_summaries/` 디렉토리 생성
  - 도서 서머리 생성 시 JSON 파일로 저장 (`{book_title}_summary.json`)
  - BookSummaryService에서 로컬 파일 저장 로직 추가

#### 6.3.6 도서 서머리 API 구현
- [ ] `backend/api/routers/book_summary.py` 생성
  - `GET /api/books/{id}/summary`: 도서 서머리 조회
  - `POST /api/books/{id}/summarize`: 도서 서머리 생성 시작 (백그라운드 작업)
- [ ] `backend/api/main.py`에 라우터 등록

#### 6.3.7 도서 서머리 실행 및 검증
- [ ] 테스트 도서 4권에 대해 도서 서머리 생성
  - Book 176 (1000년, 역사/사회)
  - Book 177 (100년 투자 가문의 비밀, 경제/경영)
  - Book 184 (AI지도책, 과학/기술)
  - Book 175 (12가지인생의법칙, 인문/자기계발)
- [ ] 생성 결과 검증
  - 도서 서머리 품질 검토
  - 챕터 서머리 통합 품질 확인
  - DB 및 로컬 파일 확인
  - Book.status는 `SUMMARIZED` 상태 유지 확인
  - 사용자 피드백 수렴

**⚠️ Git 커밋**: Phase 6 완료 후 `git add .`, `git commit -m "[Phase 6] Summary 캐시 시각화 및 변환 정교화 완료"`, `git push origin main`

---

## Phase 7: 통합 및 테스트

**목표**: 전체 파이프라인 통합 및 품질 향상

> **참고**: 프론트엔드는 백엔드에서 종료하므로 프론트엔드 관련 항목은 제외

#### 7.1 구조 분석 강화 (챕터 1-2개 세분화 및 경계 탐지 개선)

**목표**: 챕터가 1개 또는 2개인 책의 구조 분석을 더 세분화하고, 챕터 경계 탐지 오류를 개선합니다.

**현재 상황**:
- 챕터 1개: 2권 (ID 188: MIT 스타트업 바이블, ID 242: 뉴스의 시대)
- 챕터 2개: 3권 (ID 193: 강남되는 강북부동산은 정해져 있다, ID 230: 냉정한 이타주의자, ID 244: 다크 데이터)
- **구조 분석 오류 사례**: Book 184 (AI지도책)
  - order_index 중복 문제 (Order 2가 2개, Order 5가 2개)
  - 2페이지 이하 잘못된 챕터 탐지 (Chapter ID 1023, 1024)
  - 제목 추출 실패 (Title: "l")

**보강 계획**:
- [ ] 챕터 경계 탐지 개선 로직 추가
  - **최소 챕터 페이지 수 검증**: 2페이지 이하 챕터는 자동으로 이전 챕터에 병합
  - **챕터 제목 검증**: 제목이 1글자 이하인 경우 경고 및 수동 검토
  - **order_index 중복 검증**: 같은 order_index를 가진 챕터가 있으면 경고
  - Footer 기반 탐지 로직 개선 (일관성 검증)
- [ ] 챕터 1-2개인 책의 구조 분석 개선 로직 추가
  - Footer 기반 세부 섹션 탐지
  - 페이지 내용 분석을 통한 논리적 구분점 탐지
  - 수동 보정 인터페이스 (필요시)
- [ ] ExtractionService에서 2페이지 이하 챕터 필터링 로직 추가
  - `extract_chapters()` 메서드에서 챕터 페이지 수 확인
  - 2페이지 이하 챕터는 서머리 생성에서 제외 (ChapterStructurer에서도 처리하지만 이중 검증)
- [ ] 개선된 구조 분석 적용 및 재처리
  - Book 184 (AI지도책) 구조 분석 재실행
  - 챕터 1-2개인 5권에 대해 구조 분석 재실행
  - 텍스트 파일 재생성
- [ ] 재처리 후 요약 모듈 적용
  - 챕터 세분화 완료된 책들에 대해 Phase 5 요약 모듈 적용

**참고**: Phase 5 요약 모듈에서는 챕터 1-2개인 책은 제외하고 진행 (Phase 7.1 완료 후 적용)

#### 7.2 백엔드 전체 파이프라인 E2E 테스트 (필수 완료)

**⚠️ 중요: 모든 E2E 테스트는 실제 서버 실행, Mock 사용 금지, 실제 데이터만 사용** (실제 PDF, 실제 Upstage API, 실제 OpenAI LLM, 실제 DB)

- [ ] **전체 플로우 E2E 테스트** (`tests/test_e2e.py`, 실제 서버 실행):
  - 1. `POST /api/books/upload` → 책 생성 (`uploaded`)
  - 2. 실제 Upstage API로 PDF 파싱 → `parsed` 상태 확인 → **캐시 저장 확인** (`data/cache/upstage/`)
  - 3. `GET /api/books/{id}/structure/candidates` → 구조 후보 생성 → **캐시된 파싱 결과 재사용 확인**
  - 4. `POST /api/books/{id}/structure/final` → 구조 확정 (`structured`)
  - 5. `POST /api/books/{id}/extract/pages` → 실제 LLM으로 페이지 엔티티 추출 (`page_summarized`) → **캐시 저장 확인** (`data/cache/summaries/`)
  - 6. `POST /api/books/{id}/extract/chapters` → 실제 LLM으로 챕터 구조화 (`summarized`) → **캐시 저장 확인**
  - 7. `POST /api/books/{id}/summarize` → 실제 LLM으로 도서 서머리 생성 → **캐시 저장 확인**
  - 8-10. 최종 결과 조회 검증 (`GET /api/books/{id}`, `/pages`, `/chapters`, `/summary`)
  - 각 단계별 데이터 정합성 검증 (DB 레코드, 관계, 상태 변경 순서)
  - **캐시 재사용 검증**: 동일 PDF/텍스트 재요청 시 캐시 히트 확인 (API 호출 없음)
- [ ] **다양한 시나리오 E2E 테스트** (실제 PDF 파일 및 실제 API 사용):
  - 다양한 형식의 실제 PDF (단면/양면 스캔, 한국어/영어, 다양한 챕터 구조)
  - 엣지 케이스 (작은 PDF, 큰 PDF 100페이지 초과, 챕터 없는 책, 구조 불명확한 책)
- [ ] **API 계약 검증** (`tests/test_api_contract.py`): 모든 API 엔드포인트 응답 스키마, Pydantic 스키마와 실제 응답 일치, Enum 값 정합성, 필드명/타입 일치
- [ ] **에러 플로우 E2E 테스트**: 실제 Upstage API/LLM 실패 시나리오, 파일 형식 에러 처리

#### 7.3 에러 처리 강화
- [ ] Upstage API 실패 처리 (네트워크 에러, Rate limit, `error_parsing` 상태 업데이트, 에러 로그 저장)
- [ ] LLM 요약 실패 처리 (`error_summarizing` 상태, 부분 실패 처리)
- [ ] 재시도 로직 개선 (지수 백오프, 최대 재시도 횟수 제한)

#### 7.4 성능 최적화
- [ ] 페이지 요약 병렬 처리 (asyncio 또는 멀티프로세싱, 배치 처리)
- [x] **캐싱 전략 구현 완료**: ✅ 완료
  - Upstage API 파싱 결과 캐싱 (`data/cache/upstage/`) ✅ 완료
  - OpenAI 요약 결과 캐싱 (`data/cache/summaries/`) ✅ 완료
  - 파일 해시 기반 캐시 키 (같은 내용이면 경로 무관하게 재사용) ✅ 완료
  - 구조 분석기에서 캐시된 파싱 결과 재사용 ✅ 완료
- [x] 캐시 정리 기능 ✅ 완료
  - `backend/scripts/cleanup_cache.py`: 통합 캐시 정리 스크립트
    - `.backup` 파일들을 `backup/` 폴더로 이동
    - `.tmp` 파일 삭제
    - 각 챕터별로 최신 캐시만 유지하고 나머지는 `backup/`으로 이동
    - 정리 결과 리포트 출력
- [ ] DB 쿼리 최적화 (인덱스 추가, N+1 쿼리 방지)

#### 7.5 문서화
- [ ] API 문서 작성 (FastAPI 자동 생성)
- [ ] README.md 작성 (프로젝트 소개, 설치/실행 방법, 환경변수 설정, 테스트 실행 방법)
- [ ] 코드 주석 보완
- [ ] 테스트 문서 작성 (테스트 구조, E2E 테스트 실행 방법, 테스트 데이터 준비)

#### 7.6 백엔드 테스트 완료 검증 (프론트엔드 연동 전 필수)
- [ ] **테스트 커버리지 확인**: 전체 80% 이상 (핵심 로직 100%), 핵심 모듈 90% 이상 (UpstageAPIClient 100%, PDFParser/StructureBuilder/SummaryService 90%+)
- [ ] **모든 테스트 통과 확인**: 단위/통합/E2E 테스트 모두 통과, `pytest --cov=backend tests/` 실행 결과 확인
- [ ] **API 계약 문서화**: OpenAPI 스키마 생성 (`/openapi.json`), API 문서, 요청/응답 예시
- [ ] **테스트 리포트 생성**: 테스트 실행 결과 리포트, 커버리지 리포트, 실패 테스트 확인

**백엔드 E2E 테스트 완료 기준**:
- ✅ Phase 1-6 모든 단계별 테스트 통과
- ✅ 전체 플로우 E2E 테스트 통과 (최소 3가지 시나리오, ⚠️ 실제 데이터 사용 필수: 실제 PDF, 실제 Upstage API, 실제 OpenAI LLM, Mock 사용 금지)
- ✅ API 계약 검증 통과
- ✅ 테스트 커버리지 목표 달성
- ✅ 에러 플로우 테스트 통과

**⚠️ E2E 테스트 필수 원칙**: 실제 서버 실행, Mock 사용 절대 금지, 실제 외부 API 연동, 실제 PDF 파일 사용, 실제 DB 데이터 검증

**검증**: 백엔드 단독으로 모든 기능이 실제 데이터로 정상 작동함을 E2E 테스트로 확인

**⚠️ Git 커밋**: Phase 7 완료 후 `git add .`, `git commit -m "[Phase 7] 백엔드 E2E 테스트 완료 및 통합 검증"`, `git push origin main`

---

## 데이터 모델 (SQLite)

### books
- `id`, `title`, `author`, `category` (분야), `source_file_path`, `page_count`, `status` (enum), `structure_data` (JSON), `book_summary_data` (JSON, Phase 6 추가), `created_at`, `updated_at`

### pages
- `id`, `book_id` (FK), `page_number`, `raw_text`, `page_metadata` (JSON)

### chapters
- `id`, `book_id` (FK), `title`, `order_index`, `start_page`, `end_page`, `section_type`, `created_at`

### page_summaries
- `id`, `book_id` (FK), `page_id` (FK), `page_number`, `summary_text`, `structured_data` (JSON), `lang`, `created_at`

### chapter_summaries
- `id`, `book_id` (FK), `chapter_id` (FK), `summary_text`, `structured_data` (JSON), `lang`, `created_at`

---

## 주요 참고 문서

- `docs/PRD_books-processor.md`: 제품 요구사항 문서
- `docs/core_logics.md`: 구조 분석 로직 상세 설계
- `docs/book-assistant_repomix_backend.md`: 선행 서비스 코드 참고
- `docs/entity_extraction_guideline.md`: 엔티티 추출 작업 지침
- `TODOs_archive_20241215.md`: 이전 계획 문서 (참고용)
- `TODOs_archive_20251207_122200.md`: 이전 계획 문서 (참고용)

## 주의사항

1. **상태 관리**: `uploaded → parsed → structured → page_summarized → summarized` 순서로 진행
2. **SQLite → Supabase 전환 고려**: DB 추상화 레이어를 두어 추후 전환 용이하도록 설계
3. **⚠️ 실제 데이터 테스트 필수 (E2E 테스트)**: Mock 사용 절대 금지, 실제 PDF 파일, 실제 Upstage API, 실제 OpenAI LLM, 실제 DB 데이터 검증
4. **⚠️ Git 버전 관리 필수**: Git 업데이트 및 실행을 안하는 경우가 있으니 반드시 주의, 각 Phase 완료 후 커밋 및 푸시, 작업 전 `git status`, `git pull origin main` 확인
5. **이모지 사용 금지**: PowerShell 환경 고려
6. **Poetry 1.8.5 이상 필수**: 메타데이터 버전 2.4 지원
7. **AGENTS.md 규칙 준수**: PowerShell 명령어, 환경변수 관리, 프로젝트 실행 규칙 등
8. **프론트엔드 제외**: 백엔드에서 프로젝트 종료, 프론트엔드 구현 제외
