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

### 전체 진행률: 약 95% (Phase 1-6 완료, Phase 7 진행 중)

| Phase | 제목 | 진행률 | 상태 |
|-------|------|-------|------|
| Phase 1 | 프로젝트 기초 및 환경 설정 | 100% | 완료 |
| Phase 2 | PDF 파싱 모듈 (Upstage API 연동) | 100% | 완료 |
| Phase 3 | 구조 분석 모듈 | 100% | 완료 |
| Phase 4 | 대량 도서 처리 프레임 단계 | 100% | 완료 |
| Phase 5 | 내용 추출 및 요약 모듈 | 100% | 완료 |
| Phase 6 | Summary 캐시 시각화 및 변환 정교화 | 100% | 완료 |
| Phase 7 | 통합 및 테스트 | 40% | 진행 중 |

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
- [x] 테스트 도서 4권에 대해 도서 서머리 생성 ✅ 완료
  - Book 176 (1000년, 역사/사회): 완료
  - Book 177 (100년 투자 가문의 비밀, 경제/경영): 완료
  - Book 184 (AI지도책, 과학/기술): 완료 (재처리: 챕터 서머리 DB/캐시 삭제 후 재생성, 2페이지 이하 챕터 스킵 적용)
  - Book 175 (12가지인생의법칙, 인문/자기계발): 완료
- [x] 생성 결과 검증 ✅ 완료
  - 도서 서머리 품질 검토: 완료
  - 챕터 서머리 통합 품질 확인: 완료 (AI지도책 재처리로 중복 챕터 문제 해결)
  - DB 및 로컬 파일 확인: 완료
  - Book.status는 `SUMMARIZED` 상태 유지 확인: 완료
  - 사용자 피드백 수렴: 완료

**⚠️ Git 커밋**: Phase 6 완료 후 `git add .`, `git commit -m "[Phase 6] Summary 캐시 시각화 및 변환 정교화 완료"`, `git push origin main`

---

## Phase 7: 통합 및 테스트

**목표**: 챕터 6개 이상 도서에 대한 전체 파이프라인 통합 및 품질 향상

> **참고**: 프론트엔드는 백엔드에서 종료하므로 프론트엔드 관련 항목은 제외  
> **범위**: 챕터 6개 이상 도서만 처리 (7.1 구조 분석 강화 스킵)

#### 7.1 구조 분석 강화 (스킵)

**결정**: 챕터 6개 이상 도서만 처리하므로 구조 분석 강화는 스킵합니다.
- 챕터 1-2개인 책은 처리 대상에서 제외
- 챕터 6개 이상 도서에 집중하여 전체 파이프라인 완성도 향상

#### 7.2 백엔드 전체 파이프라인 E2E 테스트 (필수 완료)

**목표**: 챕터 6개 이상 도서에 대한 전체 파이프라인을 실제 서버에서 E2E 테스트로 검증

**⚠️ 중요: 모든 E2E 테스트는 실제 서버 실행, Mock 사용 금지, 실제 데이터만 사용** (실제 PDF, 실제 Upstage API, 실제 OpenAI LLM, 실제 DB)

**⚠️ 구조 분석 캐시 재사용 원칙**:
- 모든 책은 구조 분석까지는 기존 캐시를 사용해야 합니다.
- `StructureService.get_structure_candidates()`는 PDF 해시 기반으로 `data/output/structure/{hash_6}_{title}_structure.json` 파일을 찾아 재사용합니다.
- 구조 파일이 있으면 구조 분석을 건너뛰고 캐시된 결과를 사용합니다.
- 구조 파일이 없을 때만 새로 구조 분석을 수행합니다.

- [x] **구조 분석 캐시 재사용 로직 구현** (`backend/api/services/structure_service.py`): ✅ 완료
  - [x] `_get_pdf_hash_6()`: PDF 해시 6글자 계산 메서드 추가 ✅ 완료
  - [x] `_find_structure_file_by_hash()`: PDF 해시 기반 구조 파일 찾기 메서드 추가 ✅ 완료
  - [x] `_convert_json_to_structure_format()`: JSON 형식을 StructureBuilder 출력 형식으로 변환 메서드 추가 ✅ 완료
  - [x] `get_structure_candidates()`: 구조 파일 캐시 확인 및 재사용 로직 추가 ✅ 완료
- [x] **전체 플로우 E2E 테스트** (`backend/tests/test_e2e_full_pipeline_unified.py`): ✅ 완료
  - [x] **1단계: 구조 분석 완료된 4권 캐시 검증 테스트** (완료된 책 검증): ✅ 완료
    - **⚠️ 완료된 책 (재처리 없음)**: Book ID 175, 176, 177, 184
      - Book 175 (12가지인생의법칙, 인문/자기계발, 12챕터): 완료
      - Book 176 (1000년, 역사/사회, 8챕터): 완료
      - Book 177 (100년 투자 가문의 비밀, 경제/경영, 19챕터): 완료
      - Book 184 (AI지도책, 과학/기술, 8챕터): 완료
      - **이 4권은 앞으로 다시 처리하지 않습니다.**
    - 이미 구조 분석이 완료된 4권에 대해 캐시 활용 검증
    - 구조 데이터, 페이지 엔티티, 챕터 엔티티, 도서 서머리 상태 확인
    - Upstage 캐시, 구조 파일, 요약 캐시 확인
    - **구조 분석 캐시 재사용 검증**: 구조 후보 생성 시 구조 파일을 재사용하는지 확인
  - [x] **2단계: 챕터 6개 이상 도서 리스트 생성 및 보고**: ✅ 완료
    - `select_test_samples.py` 실행하여 챕터 6개 이상 도서 리스트 생성
    - 총 몇 권인지 사용자에게 보고
  - [x] **3단계: 새 책 E2E 테스트** (전체 파이프라인): ✅ 완료
    - 리스트 중 이미 사용된 4권 제외한 맨 첫 번째 한 권 선택
    - 전체 플로우: 업로드 → 파싱 → 구조 분석 → 페이지 추출 → 챕터 구조화 → 도서 서머리 생성
    - 각 단계별 캐시 저장/재사용 검증
    - **구조 분석 단계**: 이미 구조 분석이 완료된 책의 경우 구조 파일 캐시를 재사용하는지 확인
    - **환경변수 지원**: `TEST_BOOK_ID` 환경변수로 특정 책 지정 가능
    - **자동 선택 기능**: 환경변수가 없으면 북서머리 미완료 책 중 첫 번째 자동 선택
    - Book ID 182 (2030 축의 전환, 8챕터) 테스트 완료 ✅
    - Book ID 178 (2018 인구절벽이 온다, 9챕터) 테스트 완료 ✅
    - 전체 파이프라인 정상 동작 확인
    - 북서머리 생성 완료 확인
    - 프로세스 정상 종료 확인
    - [x] **프로세스 종료 문제 해결** ✅ 완료
      - 북서머리 생성 후 서버 로그에서 백그라운드 작업 완료 메시지 확인 추가
      - 파일 생성 확인 후 추가 대기 시간 추가 (3초)
      - conftest.py에서 서버 종료 전 백그라운드 작업 완료 대기 추가 (5초)
- [x] **캐시 활용 검증 테스트** (`test_e2e_cache_verification`): 모든 챕터 6개 이상 도서에 대해 Upstage 캐시 및 구조 파일 확인
- [x] **API 계약 검증** (`backend/tests/test_api_contract.py` 생성 완료): 모든 API 엔드포인트 응답 스키마, Pydantic 스키마와 실제 응답 일치, Enum 값 정합성, 필드명/타입 일치
- [x] **에러 플로우 E2E 테스트** (일부 완료): 파일 형식 에러 처리, 존재하지 않는 책 조회, 파싱 전 구조 분석 시도
- [x] **구조 분석 문제 사례 분석** ✅ 완료
  - [x] 구조 파일 분석 스크립트 작성 (`backend/scripts/analyze_structure_files.py`) ✅ 완료
  - [x] 전체 구조 파일 분석 (88개 파일, 87개 성공) ✅ 완료
  - [x] 문제 사례 발견: 5권의 책에서 구조 분석 문제 발견 ✅ 완료
    - **AI지도책 (Book ID 184)**: 중복된 소량 페이지 챕터로 인해 이후 처리가 어려워진 대표 사례
      - 중복된 order_index: `order_index: 2` (2회), `order_index: 5` (2회)
      - 소량 페이지 챕터: "l" (189-190, 2페이지), "데이터" (191-192, 2페이지)
      - 중복된 챕터 제목: "데이터" (2회)
      - 영향: 페이지 엔티티 추출 시 챕터 매핑 혼란, 챕터 서머리 생성 시 중복 데이터 처리 문제
      - 완화: 2페이지 이하 챕터 스킵 로직으로 일부 완화됨
      - **처리 상태**: ✅ 이미 처리 완료 (완료된 6권에 포함)
    - **노이즈 (Book ID 235)**: 중복된 order_index 5건 (order_index 1, 2, 3, 4, 5 모두 중복)
      - **처리 방침**: 7.5 처리 대상에서 제외
      - **사유**: 1부 아래에 1, 2, 3장이 하부구조로 겹침
    - **뇌를 바꾼 공학 (Book ID 239)**: 중복된 order_index 1건, 소량 페이지 챕터 1개
      - **처리 방침**: 7.5 처리 예정
      - **해결 방법**: 중복 챕터는 페이지수 미달로 제외 예정 (2페이지 이하 챕터 스킵 로직 적용)
    - **MIT 스타트업 바이블 (Book ID 188)**: order_index 순서 문제 (23만 존재)
      - **처리 방침**: 챕터 수 6개 미만으로 대상 제외
    - **뉴스의 시대 (Book ID 242)**: order_index 순서 문제 (1만 존재)
      - **처리 방침**: 챕터 수 6개 미만으로 대상 제외
  - [x] 분석 보고서 생성 (`data/output/analysis/structure_analysis_report_*.md`) ✅ 완료
  - [x] 통계 요약:
    - 중복된 order_index: 8건
    - 중복된 챕터 제목: 1건
    - 소량 페이지 챕터 (2-3페이지 이하): 4개
    - order_index 순서 문제: 5건

#### 7.3 에러 처리 강화
- [x] Upstage API 실패 처리 (네트워크 에러, Rate limit, `error_parsing` 상태 업데이트, 에러 로그 저장) ✅ 완료
  - ParsingService.parse_book()에 try-except 추가
  - 에러 발생 시 BookStatus.ERROR_PARSING 상태로 업데이트
  - 상세한 에러 로그 및 트레이스백 저장
- [x] LLM 요약 실패 처리 (`error_summarizing` 상태, 부분 실패 처리) ✅ 완료
  - ExtractionService.extract_pages()에 try-except 추가
  - ExtractionService.extract_chapters()에 try-except 추가
  - BookReportService.generate_report()에 try-except 추가
  - 에러 발생 시 BookStatus.ERROR_SUMMARIZING 상태로 업데이트
  - 함수 레벨 try/except 블록으로 전체 함수 본문 감싸기
  - 함수 본문 레벨 코드(8칸)를 12칸으로 들여쓰기 증가 (try 블록 내부)
  - except 블록에서 상세한 에러 로깅 및 상태 업데이트
  - **⚠️ 구현 과정에서 발생한 문제**:
    - 초기 수동 편집 시 들여쓰기 문제 발생 (중첩 블록 처리 복잡)
    - Git 원복 후 스크립트 기반 자동 처리로 변경
    - 스크립트 실행 후 중복 코드 발생 (logger.info, return 문 중복)
    - 중복 코드 제거 후 최종 완료
    - **교훈**: 복잡한 들여쓰기 작업은 스크립트보다 수동 검토가 필요할 수 있음
- [x] 재시도 로직 개선 (지수 백오프, 최대 재시도 횟수 제한) ✅ 완료
  - UpstageAPIClient: 이미 지수 백오프 구현됨 (2^attempt)
  - LLM Chains: 이미 지수 백오프 구현됨 (2^attempt), max_retries=3

#### 7.4 성능 최적화 (필요한 부분만)

**목표**: 성능 병목 지점만 최적화

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
- [x] **DB 쿼리 최적화** (필요한 부분만): ✅ 완료
  - [x] 인덱스 추가 확인 및 보완 ✅ 완료
    - `books.status` 컬럼에 인덱스 추가 (get_books 필터 최적화)
    - 기존 인덱스 확인: `book_id`, `chapter_id`, `page_number` 등 필수 인덱스 존재 확인
  - [x] N+1 쿼리 방지 ✅ 완료
    - `BookReportService.generate_report()`: `joinedload(ChapterSummary.chapter)` 추가
    - `ExtractionService`: 챕터 정보 미리 조회하여 딕셔너리로 생성 (병렬 처리 중 DB 접근 방지)

#### 7.5 챕터 6개 이상 모두 처리 스크립트

**목표**: 챕터 6개 이상인 모든 도서에 대해 전체 파이프라인 처리 (파싱 → 구조 분석 → 엔티티 추출 → 도서 서머리 생성)

**⚠️ 참고**: 완료된 책을 제외한 나머지 챕터 6개 이상 도서를 일괄 처리
  - **완료된 책 (재처리 없음)**: Book ID 175, 176, 177, 184, 182, 178 (총 6권)
  - **처리 제외 대상**:
    - 구조 분석 문제로 인한 제외: Book ID 235 (노이즈) - 1부 아래 하부구조 겹침
    - 챕터 수 6개 미만: Book ID 188 (MIT 스타트업 바이블), Book ID 242 (뉴스의 시대)
  - **처리 예정**: 위를 제외한 나머지 챕터 6개 이상 도서 처리
    - **참고**: Book ID 239 (뇌를 바꾼 공학)은 처리 예정 (중복 챕터는 페이지수 미달로 자동 제외)

**⚠️ 스크립트 실행 방식**:
- 서버 1회 시작 → 모든 책 처리 → 종료
- E2E 테스트와 달리 각 책마다 서버를 시작/종료하지 않음
- 효율성 및 일관성을 위해 동일 서버 세션에서 모든 책 처리

**⚠️ 구조 분석 캐시 재사용 원칙**:
- 모든 책은 구조 분석까지는 기존 캐시를 사용해야 합니다.
- `StructureService.get_structure_candidates()`는 PDF 해시 기반으로 `data/output/structure/{hash_6}_{title}_structure.json` 파일을 찾아 재사용합니다.
- 구조 파일이 있으면 구조 분석을 건너뛰고 캐시된 결과를 사용합니다.
- 구조 파일이 없을 때만 새로 구조 분석을 수행합니다.
- **이미 구조 분석이 완료된 모든 책은 구조 파일 캐시를 재사용하여 불필요한 구조 분석을 방지합니다.**

**⚠️ 중요: 진행률 및 소요 시간 표시 필수**:
- 모든 파이프라인 테스트와 7.5 스크립트에서 진행률, 소요 시간, 남은 시간 표시 필수
- 진행률: `{current}/{total} ({progress_pct}%)`
- 소요 시간: `Time: {elapsed_min:02d}:{elapsed_sec:02d}`
- 평균 시간: `Avg: {avg_time:.1f}s/item`
- 예상 남은 시간: `Est: {est_min:02d}:{est_sec:02d}`
- 공통 유틸리티 함수 사용: `backend/tests/test_utils.py`의 `wait_for_extraction_with_progress()` 활용

- [ ] **대량 처리 스크립트 작성** (`backend/scripts/process_all_books_6plus_chapters.py` 생성):
  - **서버 관리**: 서버 1회 시작 → 모든 책 처리 → 종료
    - 서버 시작 (포트 8000)
    - 헬스체크 대기
    - 모든 처리 완료 후 종료
  - DB에서 챕터 6개 이상인 도서 조회
  - 완료된 6권 제외 (Book ID: 175, 176, 177, 184, 182, 178)
  - 북서머리 미완료 책만 필터링
  - 각 도서별 처리 상태 확인
  - 단계별 처리 (순차 처리 또는 제한된 병렬 처리):
    - 파싱 (`status < 'parsed'`): Upstage 캐시 재사용
    - 구조 분석 (`status < 'structured'`): **구조 파일 캐시 재사용** (`StructureService.get_structure_candidates()`가 자동으로 캐시 확인 및 재사용)
    - 페이지 엔티티 추출 (`status < 'page_summarized'`): 요약 캐시 재사용
    - 챕터 구조화 (`status < 'summarized'`): 요약 캐시 재사용
    - 도서 서머리 생성 (`BookReportService.generate_report()`)
  - `process_book_full_pipeline()` 함수 재사용 (테스트와 동일한 로직)
  - 진행 상황 로깅 (`data/logs/batch_processing/`)
  - 진행률 표시: `{current}/{total} ({progress_pct}%)`, 소요 시간, 예상 남은 시간
  - 최종 리포트 생성 (성공/실패 통계, 처리 시간, 비용 추정)
  - **캐시 재사용 통계**: 각 단계별 캐시 히트율 리포트 포함
  - **에러 처리**: 개별 책 실패 시에도 나머지 책 계속 처리, 로그 기록
- [ ] **스크립트 실행 및 검증**:
  - 모든 챕터 6개 이상 도서 처리 완료 확인
  - 각 단계별 상태 업데이트 확인
  - 도서 서머리 파일 생성 확인 (`data/output/book_summaries/`)
  - 에러 발생 시 로그 확인 및 재처리 가능 여부 확인

#### 7.6 문서 작성 및 완료

**목표**: 프로젝트 문서화 완료 및 최종 검증

- [ ] **API 문서 작성** (`docs/API.md` 생성 또는 README.md에 통합):
  - FastAPI 자동 생성 문서 링크 (`/docs`, `/openapi.json`)
  - 주요 API 엔드포인트 설명
  - 요청/응답 예시
  - 에러 코드 및 처리 방법
- [ ] **README.md 업데이트**:
  - 프로젝트 완료 상태 업데이트
  - Phase 7 완료 내용 반영
  - 챕터 6개 이상 도서 처리 방법 안내
  - 전체 파이프라인 실행 방법
- [ ] **코드 주석 보완**:
  - `backend/api/services/extraction_service.py`: 주요 메서드 docstring 보완
  - `backend/api/services/book_report_service.py`: 주요 메서드 docstring 보완
  - `backend/parsers/upstage_api_client.py`: 에러 처리 로직 주석 추가
  - `backend/summarizers/llm_chains.py`: 에러 처리 로직 주석 추가
- [ ] **테스트 문서 작성** (`docs/TESTING.md` 생성):
  - 테스트 구조 설명
  - E2E 테스트 실행 방법
  - 테스트 데이터 준비 방법
  - 테스트 커버리지 확인 방법
  - 문제 해결 가이드
- [ ] **프로젝트 완료 검증**:
  - [ ] 모든 E2E 테스트 통과
  - [ ] 챕터 6개 이상 도서 전체 처리 완료
  - [ ] API 문서 작성 완료
  - [ ] README.md 업데이트 완료
  - [ ] 코드 주석 보완 완료
  - [ ] 테스트 문서 작성 완료

**백엔드 E2E 테스트 완료 기준**:
- ✅ Phase 1-6 모든 단계별 테스트 통과
- ✅ 전체 플로우 E2E 테스트 통과 (최소 3가지 시나리오, ⚠️ 실제 데이터 사용 필수: 실제 PDF, 실제 Upstage API, 실제 OpenAI LLM, Mock 사용 금지)
- ✅ API 계약 검증 통과
- ✅ 테스트 커버리지 목표 달성
- ✅ 에러 플로우 테스트 통과

**⚠️ E2E 테스트 필수 원칙**: 실제 서버 실행, Mock 사용 절대 금지, 실제 외부 API 연동, 실제 PDF 파일 사용, 실제 DB 데이터 검증

**검증**: 백엔드 단독으로 모든 기능이 실제 데이터로 정상 작동함을 E2E 테스트로 확인

**⚠️ Git 커밋**: 각 sub phase 완료 후 즉시 커밋
- 7.2 완료: `git commit -m "[Phase 7.2] 전체 파이프라인 E2E 테스트 완료"`
- 7.3 완료: `git commit -m "[Phase 7.3] 에러 처리 강화 완료"`
- 7.4 완료: `git commit -m "[Phase 7.4] 성능 최적화 완료"`
- 7.5 완료: `git commit -m "[Phase 7.5] 챕터 6개 이상 도서 전체 처리 완료"`
- 7.6 완료: `git commit -m "[Phase 7.6] 문서 작성 및 프로젝트 완료"`
- Phase 7 전체 완료 후: `git commit -m "[Phase 7] 통합 및 테스트 완료 (챕터 6개 이상 도서 대상)"`

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
