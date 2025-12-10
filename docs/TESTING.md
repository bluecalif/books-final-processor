# 테스트 문서

이 문서는 도서 PDF 구조 분석 및 엔티티 추출 시스템의 테스트 구조와 실행 방법을 설명합니다.

---

## 목차

1. [테스트 원칙](#테스트-원칙)
2. [테스트 구조](#테스트-구조)
3. [테스트 실행 방법](#테스트-실행-방법)
4. [테스트 데이터 준비](#테스트-데이터-준비)
5. [테스트 커버리지](#테스트-커버리지)
6. [문제 해결 가이드](#문제-해결-가이드)

---

## 테스트 원칙

### ⚠️ 핵심 원칙: E2E 테스트만 사용

본 프로젝트는 **E2E 테스트만** 사용합니다. 실제 서버를 실행하여 프로덕션 플로우와 동일하게 검증합니다.

### 필수 원칙

✅ **해야 할 것**:
- 실제 서버 실행 (`uvicorn` 서버를 실제로 띄워서 테스트)
- 실제 데이터만 사용 (실제 PDF, 실제 Upstage API, 실제 OpenAI LLM)
- Mock 사용 절대 금지 (프로덕션 플로우와 동일하게 검증)
- 백그라운드 작업 검증 (실제 서버에서 백그라운드 작업이 실행되는지 확인)
- 캐시 활용 검증 (각 단계에서 캐시 저장/재사용 확인)
- 진행률 표시 (페이지/챕터 추출 시 진행률, 소요 시간, 남은 시간 표시)
- API 응답만 검증 (서버와 테스트가 다른 DB 사용)

❌ **금지 사항**:
- TestClient 사용 (백그라운드 작업이 제대로 실행되지 않음)
- DB 직접 조회 (서버와 테스트가 다른 DB 사용)
- 서비스 직접 호출 (프로덕션 플로우와 다르므로 금지)
- Mock 사용 (프로덕션 플로우와 다르므로 금지)

---

## 테스트 구조

### 테스트 파일 위치

```
backend/tests/
├── conftest.py                    # 테스트 픽스처 (test_server 등)
├── conftest_e2e.py               # E2E 테스트 픽스처 (실제 서버 실행)
├── test_e2e_full_pipeline_unified.py  # 통합 E2E 테스트 (권장)
├── test_e2e_pdf_parsing.py       # PDF 파싱 단독 테스트
├── test_e2e_structure_analysis.py  # 구조 분석 단독 테스트
├── test_e2e_extraction.py        # 엔티티 추출 단독 테스트
├── test_e2e_text_organizer.py    # 텍스트 정리 단독 테스트
└── test_api_contract.py          # API 계약 검증
```

### 테스트 파일 설명

#### `test_e2e_full_pipeline_unified.py` (권장)

**목적**: 전체 파이프라인을 일관된 방식으로 테스트

**특징**:
- 입력 책 리스트만 다르고 처리 과정은 완전히 동일
- 4권 검증, 1권 테스트, 7.5단계 대량 처리 모두 동일한 함수 사용
- 캐시 활용 검증 포함
- 진행률, 소요 시간, 남은 시간 표시

**테스트 함수**:
- `test_e2e_full_pipeline_validation`: 이미 완료된 책 검증 (4권)
- `test_e2e_new_book_full_pipeline`: 새 책 1권 전체 파이프라인
- `test_e2e_multiple_books_validation`: 여러 책 검증 (파라미터화)
- `test_e2e_error_flow_*`: 에러 처리 검증

#### 단계별 테스트 파일

**`test_e2e_pdf_parsing.py`**:
- **목적**: PDF 파싱 모듈 단독 테스트
- **검증 항목**: Upstage API 연동, 캐시 저장/재사용, 100페이지 분할 처리

**`test_e2e_structure_analysis.py`**:
- **목적**: 구조 분석 모듈 단독 테스트
- **검증 항목**: Footer 기반 경계 탐지, 챕터 탐지, 구조 파일 캐시 재사용

**`test_e2e_extraction.py`**:
- **목적**: 엔티티 추출 모듈 단독 테스트
- **검증 항목**: 페이지/챕터 엔티티 추출, 도메인별 스키마, 캐시 재사용

**`test_e2e_text_organizer.py`**:
- **목적**: 텍스트 정리 모듈 단독 테스트
- **검증 항목**: 본문 텍스트 추출, JSON 파일 생성

**`test_api_contract.py`**:
- **목적**: API 계약 검증
- **검증 항목**: Pydantic 스키마 일치, Enum 값 검증, 필드명/타입 일치

---

## 테스트 실행 방법

### 환경 설정

```powershell
# 1. 의존성 설치
poetry install

# 2. 환경변수 설정 (.env 파일 확인)
Get-Content .env -Force

# 3. DB 초기화 (필요 시)
poetry run python -c "from backend.api.database import init_db; init_db()"
```

### 기본 실행

```powershell
# 통합 테스트 (권장)
poetry run pytest backend/tests/test_e2e_full_pipeline_unified.py -v -m e2e

# 단계별 테스트
poetry run pytest backend/tests/test_e2e_pdf_parsing.py -v -m e2e
poetry run pytest backend/tests/test_e2e_structure_analysis.py -v -m e2e
poetry run pytest backend/tests/test_e2e_extraction.py -v -m e2e
poetry run pytest backend/tests/test_e2e_text_organizer.py -v -m e2e

# API 계약 검증
poetry run pytest backend/tests/test_api_contract.py -v -m e2e

# 전체 E2E 테스트
poetry run pytest backend/tests/ -m e2e -v
```

### 특정 테스트만 실행

```powershell
# 특정 테스트 함수만 실행
poetry run pytest backend/tests/test_e2e_full_pipeline_unified.py::test_e2e_new_book_full_pipeline -v -m e2e

# 특정 파일의 특정 테스트만 실행
poetry run pytest backend/tests/test_e2e_pdf_parsing.py::test_e2e_pdf_parsing_simple -v -m e2e
```

### 옵션

```powershell
# 상세 출력
poetry run pytest backend/tests/ -m e2e -v -s

# 실패 시 즉시 중단
poetry run pytest backend/tests/ -m e2e -v -x

# 실패한 테스트만 재실행
poetry run pytest backend/tests/ -m e2e -v --lf

# 병렬 실행 (선택적)
poetry run pytest backend/tests/ -m e2e -v -n auto
```

---

## 테스트 데이터 준비

### PDF 파일 준비

테스트용 PDF 파일은 `data/input/` 디렉토리에 위치합니다.

**요구사항**:
- 실제 PDF 파일 (테스트 파일이 아님)
- 최소 1권 이상 준비 (새 책 테스트용)
- 권장: 10-100페이지 범위 (처리 시간 고려)

### Ground Truth 데이터

구조 분석 테스트를 위한 Ground Truth 데이터는 `backend/tests/fixtures/` 디렉토리에 위치합니다.

**파일 형식**: `ground_truth_{book_title}.py`

**예시**:
```python
# backend/tests/fixtures/ground_truth_1등의통찰.py
GROUND_TRUTH = {
    "main_start_page": 15,
    "main_end_page": 180,
    "chapters": [
        {"title": "1장", "start_page": 15, "end_page": 50},
        ...
    ]
}
```

### 캐시 데이터

**참고**: 테스트는 기존 캐시를 재사용할 수 있습니다.
- PDF 파싱 캐시: `data/cache/upstage/{hash_6}.json`
- 엔티티 추출 캐시: `data/cache/summaries/`

**캐시 사용 여부**: 테스트 환경에서는 캐시를 사용하여 비용을 절감합니다.

---

## 테스트 커버리지

### 커버리지 확인

```powershell
# 커버리지 포함 실행
poetry run pytest backend/tests/ -m e2e --cov=backend --cov-report=html

# 커버리지 리포트 확인
# 브라우저에서: htmlcov/index.html
```

### 커버리지 목표

- **전체 코드 커버리지**: 80% 이상
- **핵심 모듈 커버리지**: 90% 이상
  - UpstageAPIClient: 100%
  - PDFParser: 90% 이상
  - StructureBuilder: 90% 이상
  - ExtractionService: 90% 이상
  - BookReportService: 90% 이상

### 커버리지 리포트 위치

- HTML 리포트: `htmlcov/index.html`
- 터미널 출력: `--cov-report=term`

---

## 문제 해결 가이드

### 1. 서버 시작 실패

**증상**: `test_server` fixture에서 서버 시작 실패

**원인**:
- 포트 8000이 이미 사용 중
- 환경변수 누락 (API 키 등)

**해결 방법**:
```powershell
# 포트 확인
netstat -ano | findstr :8000

# 포트 사용 중인 프로세스 종료
taskkill /F /PID [PID번호]

# 환경변수 확인
Get-Content .env -Force
echo $env:UPSTAGE_API_KEY
echo $env:OPENAI_API_KEY
```

---

### 2. API 호출 실패

**증상**: Upstage API 또는 OpenAI API 호출 실패

**원인**:
- API 키 잘못됨 또는 만료
- Rate limit 초과
- 네트워크 오류

**해결 방법**:
```powershell
# API 키 확인
echo $env:UPSTAGE_API_KEY
echo $env:OPENAI_API_KEY

# .env 파일 확인
Get-Content .env -Force

# 로그 확인
# 테스트 로그는 터미널에 출력됨
```

**참고**: Rate limit 발생 시 자동 재시도 (지수 백오프)가 적용됩니다.

---

### 3. DB 관련 오류

**증상**: `ModuleNotFoundError`, 테이블 없음 오류

**원인**:
- DB 파일 없음
- 테이블 미생성

**해결 방법**:
```powershell
# DB 초기화
poetry run python -c "from backend.api.database import init_db; init_db()"

# DB 파일 확인
Test-Path data/books.db
```

**⚠️ 주의**: E2E 테스트에서는 DB 직접 조회를 하지 않습니다. API 응답만 검증합니다.

---

### 4. 캐시 관련 문제

**증상**: 캐시가 재사용되지 않음

**원인**:
- 파일 해시 불일치
- 캐시 파일 손상

**해결 방법**:
```powershell
# 캐시 디렉토리 확인
Get-ChildItem data/cache/upstage/ -Force
Get-ChildItem data/cache/summaries/ -Force

# 캐시 파일 삭제 (재생성됨)
Remove-Item data/cache/upstage/*.json -Force
Remove-Item data/cache/summaries/*.json -Force
```

---

### 5. 테스트 타임아웃

**증상**: 테스트가 타임아웃으로 실패

**원인**:
- 대형 PDF 처리 시간 초과
- 네트워크 지연
- API 응답 지연

**해결 방법**:
```powershell
# 타임아웃 시간 증가 (pytest.ini 또는 conftest.py)
# 또는 개별 테스트에서 타임아웃 설정

# 테스트 실행 시 타임아웃 옵션
poetry run pytest backend/tests/ -m e2e -v --timeout=3600
```

**참고**: 기본 타임아웃은 1800초 (30분)입니다.

---

### 6. 백그라운드 작업 미완료

**증상**: 백그라운드 작업이 완료되지 않음

**원인**:
- TestClient 사용 (백그라운드 작업이 실행되지 않음)
- 실제 서버 미실행

**해결 방법**:
- `conftest_e2e.py`의 `test_server` fixture 사용 확인
- `httpx.Client` 사용 확인 (TestClient 사용 금지)
- 서버 로그 확인: 테스트 실행 중 서버 로그가 출력되는지 확인

---

### 7. 테스트 실패 로그 확인

**로그 위치**:
- 터미널 출력 (기본)
- `data/logs/test_results/` (서버 로그)
- `data/logs/batch_processing/` (배치 처리 로그)

**로그 확인**:
```powershell
# 최신 테스트 로그 확인
Get-ChildItem data/logs/test_results/ | Sort-Object LastWriteTime -Descending | Select-Object -First 1 | Get-Content -Tail 100

# 특정 키워드 검색
Get-Content data/logs/test_results/*.log | Select-String "ERROR|WARNING" | Select-Object -Last 50
```

---

## 테스트 실행 예시

### 전체 플로우 테스트

```powershell
# 1. 통합 테스트 실행
poetry run pytest backend/tests/test_e2e_full_pipeline_unified.py -v -m e2e

# 출력 예시:
# [INFO] Starting server...
# [INFO] Server started at http://127.0.0.1:8000
# [INFO] Starting page extraction for book_id=123
# [PROGRESS] Pages: 100/200 (50%) | Elapsed: 150s | Est. remaining: 150s
# [INFO] Page extraction completed: success=200, failed=0
# ...
```

### 단계별 테스트

```powershell
# PDF 파싱 테스트
poetry run pytest backend/tests/test_e2e_pdf_parsing.py::test_e2e_pdf_parsing_simple -v -m e2e

# 구조 분석 테스트
poetry run pytest backend/tests/test_e2e_structure_analysis.py::test_e2e_structure_candidates -v -m e2e

# 엔티티 추출 테스트
poetry run pytest backend/tests/test_e2e_extraction.py::test_e2e_page_extraction -v -m e2e
```

---

## 테스트 모범 사례

### 1. 테스트 격리

- 각 테스트는 독립적으로 실행 가능해야 함
- 테스트 간 상태 공유 금지
- DB 상태는 테스트 시작 전/후로 복원 (필요 시)

### 2. 테스트 데이터 관리

- 실제 데이터만 사용 (Mock 금지)
- 테스트용 PDF는 `data/input/`에 저장
- 캐시는 재사용 가능하도록 관리

### 3. 에러 처리 테스트

- 정상 플로우뿐만 아니라 에러 플로우도 테스트
- 예: 존재하지 않는 책 조회, 잘못된 요청 등

### 4. 성능 고려

- 대형 PDF 테스트는 타임아웃 시간 충분히 설정
- 진행률 표시로 처리 시간 모니터링
- 캐시 활용으로 불필요한 API 호출 방지

---

## 참고 문서

- [README.md](../README.md): 프로젝트 개요 및 설치 방법
- [API.md](./API.md): API 엔드포인트 문서
- [TODOs.md](../TODOs.md): Phase별 상세 구현 계획
- FastAPI 자동 생성 문서: `http://localhost:8000/docs` (서버 실행 시)

---

**최종 업데이트**: 2025-12-10

