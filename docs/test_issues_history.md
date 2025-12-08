# 테스트 가이드 및 문제 히스토리

## 개요

이 문서는 E2E 테스트 실행 방법, 테스트 파일 구조, 그리고 테스트 중 발생한 문제들과 해결 과정을 기록합니다.

---

## 테스트 파일 구조

### 핵심 테스트 파일

#### `test_e2e_full_pipeline_unified.py` (통합 E2E 테스트)

**목적**: 전체 파이프라인을 일관된 방식으로 테스트

**기능**:
- **4권 검증**: 이미 처리된 책들의 캐시 활용 검증
- **1권 테스트**: 새로 업로드한 책의 전체 파이프라인 테스트
- **7.5단계 대량 처리**: 챕터 6개 이상 책들의 일괄 처리

**파이프라인**:
```
PDF 업로드 → 파싱 → 구조분석 → 페이지엔티티 → 챕터서머리 → 북서머리
```

**캐시 활용 원칙**:
- Upstage API 캐시: `data/cache/upstage/` (파일 해시 기반)
- 구조 분석 결과: `data/output/structure/` (PDF 해시 기반)
- 요약 캐시: `data/cache/summaries/{book_title}/` (책 제목 폴더)

**실행 방법**:
```powershell
# 전체 파이프라인 테스트 (새 책 1권)
poetry run pytest backend/tests/test_e2e_full_pipeline_unified.py::test_e2e_new_book_full_pipeline -v -m e2e -s

# 이미 처리된 책 검증 (4권)
poetry run pytest backend/tests/test_e2e_full_pipeline_unified.py::test_e2e_full_pipeline_validation -v -m e2e -s
```

---

#### `test_api_contract.py` (API 계약 검증)

**목적**: 모든 API 엔드포인트의 응답이 정의된 Pydantic 스키마와 일치하는지 검증

**검증 항목**:
- 응답 구조 일치
- 데이터 타입 일치
- Enum 값 일치
- 필수 필드 존재

**실행 방법**:
```powershell
poetry run pytest backend/tests/test_api_contract.py -v -m e2e -s
```

---

#### `test_e2e_extraction.py` (엔티티 추출 테스트)

**목적**: 페이지/챕터 엔티티 추출 기능 단독 테스트

**검증 항목**:
- 페이지 엔티티 추출
- 챕터 구조화
- 캐시 저장/재사용

**실행 방법**:
```powershell
poetry run pytest backend/tests/test_e2e_extraction.py -v -m e2e -s
```

---

#### `test_e2e_pdf_parsing.py` (PDF 파싱 테스트)

**목적**: Upstage API를 통한 PDF 파싱 기능 테스트

**검증 항목**:
- PDF 업로드
- 파싱 완료 대기
- 캐시 저장/재사용

**실행 방법**:
```powershell
poetry run pytest backend/tests/test_e2e_pdf_parsing.py -v -m e2e -s
```

---

#### `test_e2e_structure_analysis.py` (구조 분석 테스트)

**목적**: Footer 기반 휴리스틱 구조 분석 기능 테스트

**검증 항목**:
- 본문 시작/끝 경계 탐지
- 챕터 경계 탐지
- Ground Truth와 비교

**실행 방법**:
```powershell
poetry run pytest backend/tests/test_e2e_structure_analysis.py -v -m e2e -s
```

---

#### `test_e2e_text_organizer.py` (텍스트 정리 테스트)

**목적**: 구조 분석 결과를 바탕으로 본문 텍스트 정리 기능 테스트

**검증 항목**:
- JSON 파일 생성
- 챕터별 페이지 텍스트 구조화

**실행 방법**:
```powershell
poetry run pytest backend/tests/test_e2e_text_organizer.py -v -m e2e -s
```

---

### 유틸리티 파일

#### `test_utils.py` (테스트 유틸리티)

**목적**: E2E 테스트 공통 유틸리티 함수 제공

**주요 함수**:
- `wait_for_status_with_progress()`: 상태 변경 대기 (진행률 출력)
- `wait_for_extraction_with_progress()`: 엔티티 추출 완료 대기 (진행률 출력)
- `find_cache_files()`: 캐시 파일 찾기
- `get_cache_file_count()`: 캐시 파일 개수 조회
- `find_latest_server_log()`: 최신 서버 로그 파일 찾기
- `parse_progress_from_log()`: 서버 로그에서 진행률 파싱

**특징**:
- 서버 로그 실시간 파싱으로 진행률 표시
- 경과 시간, 평균 시간, 예상 남은 시간 계산
- 한글 출력 인코딩 설정 포함

---

#### `conftest.py` (테스트 픽스처)

**목적**: E2E 테스트용 실제 서버 실행 픽스처 제공

**주요 픽스처**:
- `test_server`: 실제 uvicorn 서버 실행 (포트 8001)
- `e2e_client`: httpx.Client 인스턴스

**특징**:
- 테스트 시작 시 서버 자동 시작
- 테스트 종료 시 서버 자동 종료
- 포트 충돌 시 자동 정리
- 한글 출력 인코딩 설정 포함

---

## 테스트 실행 방법

### 전체 테스트 실행

```powershell
# 모든 E2E 테스트 실행
poetry run pytest backend/tests/ -v -m e2e -s

# 특정 테스트 파일만 실행
poetry run pytest backend/tests/test_e2e_full_pipeline_unified.py -v -m e2e -s

# 특정 테스트 함수만 실행
poetry run pytest backend/tests/test_e2e_full_pipeline_unified.py::test_e2e_new_book_full_pipeline -v -m e2e -s
```

### 테스트 옵션

- `-v`: 상세 출력 (verbose)
- `-m e2e`: E2E 테스트만 실행
- `-s`: 표준 출력 표시 (print 문 출력)
- `--tb=short`: 짧은 트레이스백 출력

---

## 진행률 표시

### 실시간 진행률 출력

테스트 실행 중 다음 정보가 실시간으로 표시됩니다:

**페이지 엔티티 추출**:
```
[TEST] Pages: 188/210 (89%) | Time: 00:03 | Avg: 0.0s/item | Est: 00:00
```

**챕터 구조화**:
```
[TEST] Chapters: 7/7 (100%) | Time: 00:03 | Avg: 0.4s/item | Est: 00:00
```

**북 서머리 생성**:
```
[TEST] Book summary: 4/5 steps (80%) | Time: 00:02
```

### 진행률 데이터 소스

1. **서버 로그 파싱** (우선): `data/test_results/server_*.log` 파일에서 `[PROGRESS]` 메시지 파싱
2. **DB 조회** (Fallback): API를 통해 DB에서 현재 상태 조회

---

## 캐시 활용

### 캐시 위치

- **Upstage API 캐시**: `data/cache/upstage/{hash}.json`
- **구조 분석 결과**: `data/output/structure/{hash}_{title}_structure.json`
- **요약 캐시**: `data/cache/summaries/{book_title}/page_{hash}.json`, `chapter_{hash}.json`

### 캐시 검증

테스트는 각 단계에서 다음을 검증합니다:

1. **캐시 존재 확인**: 처리 전 캐시 파일 존재 여부 확인
2. **캐시 재사용**: 캐시가 있으면 API 호출 없이 재사용
3. **캐시 저장 확인**: 처리 후 캐시 파일 생성 확인

---

## 해결된 문제들

### ✅ 문제 1: 이모지 인코딩 오류 (해결 완료)

**발생 시점**: 2025-12-08

**증상**:
```
UnicodeEncodeError: 'cp949' codec can't encode character '\u2705'
```

**원인**: PowerShell 환경에서 이모지(✅, ❌) 출력 시 cp949 인코딩 오류

**해결**: 모든 이모지를 텍스트로 변경 (`✅` → `[OK]`, `❌` → `[FAIL]`)

**수정된 파일**:
- `backend/tests/test_e2e_full_pipeline_unified.py`
- `backend/tests/test_utils.py`
- `backend/tests/test_api_contract.py`
- `backend/tests/test_e2e_extraction.py`

---

### ✅ 문제 2: Query import 누락 (해결 완료)

**발생 시점**: 2025-12-08

**증상**:
```
NameError: name 'Query' is not defined
```

**원인**: `backend/api/routers/books.py`에서 `Query` 사용하지만 import 누락

**해결**: `from fastapi import Query` 추가

**수정된 파일**:
- `backend/api/routers/books.py`

---

### ✅ 문제 3: 한글 출력 깨짐 (해결 완료)

**발생 시점**: 2025-12-08

**증상**:
```
[TEST] Full Pipeline Processing
Book ID: NEW, Title: 1
Category:/濵, Chapters: 7
```

**원인**: PowerShell의 기본 인코딩이 cp949인데, UTF-8로 인코딩된 한글 출력 시 깨짐

**해결**: Windows 환경에서 UTF-8 인코딩 설정 추가

**수정된 파일**:
- `backend/tests/conftest.py`
- `backend/tests/test_utils.py`
- `backend/tests/test_e2e_full_pipeline_unified.py`

**적용된 코드**:
```python
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
```

---

### ✅ 문제 4: 챕터 구조화 미실행 (해결 완료)

**발생 시점**: 2025-12-08

**증상**: 페이지 엔티티 추출 완료 후 챕터 구조화 단계로 진행되지 않음

**원인**: 이모지 인코딩 오류로 테스트가 중단되어 STEP 6 미실행

**해결**: 이모지 제거 완료로 테스트 정상 진행

---

### ✅ 문제 5: 북 서머리 생성 에러 (해결 완료)

**발생 시점**: 2025-12-08

**증상**:
```
NameError: name 'total_steps' is not defined
```

**원인**: `book_report_service.py`에서 `total_steps` 변수가 정의되기 전에 사용됨

**해결**: `total_steps` 계산을 함수 시작 부분으로 이동

**수정된 파일**:
- `backend/api/services/book_report_service.py`

---

### ✅ 문제 6: 진행률 출력 문제 (해결 완료)

**발생 시점**: 2025-12-08

**증상**:
1. 경과시간 및 남은 시간이 모두 0초로 출력
2. 서버 로그는 계속 찍히는데 터미널에는 모두 완료된 후 한번에 출력

**원인**:
- DB 조회 방식의 한계: 백그라운드 작업이 완료될 때까지 DB에 저장되지 않음
- 서버 로그 파싱 미사용: 서버 로그에 실시간 진행률이 있지만 테스트 코드에서 활용하지 않음
- 출력 버퍼링: Python의 stdout 버퍼링으로 인해 즉시 출력되지 않음

**해결**:
1. 서버 로그 파일 실시간 파싱 구현 (`find_latest_server_log`, `parse_progress_from_log`)
2. 출력 버퍼링 해제 (`print(..., flush=True)` 사용)
3. `check_interval` 단축 (10초 → 2초)

**수정된 파일**:
- `backend/tests/test_utils.py`

---

### ✅ 문제 7: 북 서머리 파일 검색 실패 (해결 완료)

**발생 시점**: 2025-12-08

**증상**: 북 서머리 파일이 생성되었지만 테스트에서 찾지 못함

**원인**: 파일명이 `1등의_통찰_report.json`인데, 테스트 코드가 `*1등의 통찰*.json` 패턴으로 검색

**해결**: `safe_title` 생성 로직 추가하여 공백을 언더스코어로 변환한 패턴도 검색

**수정된 파일**:
- `backend/tests/test_e2e_full_pipeline_unified.py`

---

## 테스트 환경 설정

### 필수 환경변수

`.env` 파일에 다음 환경변수가 설정되어 있어야 합니다:

```env
OPENAI_API_KEY=your_openai_api_key
UPSTAGE_API_KEY=your_upstage_api_key
```

### PowerShell 인코딩 설정

테스트 실행 전 다음 명령어로 인코딩을 설정할 수 있습니다:

```powershell
$env:PYTHONIOENCODING = "utf-8"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
```

---

## 서버 로그 확인

### 로그 파일 위치

- `data/test_results/server_{timestamp}.log`

### 로그 확인 방법

```powershell
# 최신 로그 파일 확인
Get-ChildItem "data\test_results\server_*.log" | Sort-Object LastWriteTime -Descending | Select-Object -First 1

# 로그에서 진행률 확인
Select-String -Path "data\test_results\server_*.log" -Pattern "\[PROGRESS\]"

# 로그에서 에러 확인
Select-String -Path "data\test_results\server_*.log" -Pattern "ERROR|Exception|Traceback"
```

---

## 테스트 결과 확인

### 캐시 파일 확인

```powershell
# Upstage API 캐시
Get-ChildItem "data\cache\upstage" | Measure-Object | Select-Object Count

# 구조 분석 결과
Get-ChildItem "data\output\structure" | Measure-Object | Select-Object Count

# 요약 캐시
Get-ChildItem "data\cache\summaries" -Recurse | Measure-Object | Select-Object Count
```

### 북 서머리 파일 확인

```powershell
# 북 서머리 파일 목록
Get-ChildItem "data\output\book_summaries" | Select-Object Name, LastWriteTime
```

---

## 참고 문서

- **README.md**: 프로젝트 전체 개요 및 사용법
- **TODOs.md**: Phase별 상세 구현 계획
- **AGENTS.md**: AI 에이전트 운영 가이드 (PowerShell 규칙 등)
- **API 문서**: `http://localhost:8000/docs` (서버 실행 시)

---

## 다음 단계

### Phase 7.3: 에러 처리 강화
- Upstage API 실패 처리
- LLM 요약 실패 처리
- 재시도 로직 개선

### Phase 7.4: 성능 최적화
- DB 쿼리 최적화 (인덱싱, N+1 쿼리 방지)
- 필요 시에만 진행

### Phase 7.5: 대량 처리 스크립트
- 챕터 6개 이상 책들의 일괄 처리
- 진행률, 경과 시간, 예상 남은 시간 표시

---

### ✅ 문제 8: 테스트 완료 후 프로세스 종료 문제 (미해결)

**발생 시점**: 2025-12-08

**증상**:
- 테스트가 완료되었지만 터미널 출력이 멈추고 프로세스가 종료되지 않음
- 서버 로그에는 모든 작업이 정상적으로 완료됨:
  - 북서머리 생성 완료: `[INFO] Book report generated successfully for book_id=263`
  - 백그라운드 작업 완료: `[INFO] Background book summary generation completed: book_id=263`
  - 최종 API 호출 완료: `GET /api/books/263`, `GET /api/books/263/pages`, `GET /api/books/263/chapters`

**원인 분석**:
- 테스트 함수는 정상적으로 완료되었지만 프로세스가 종료되지 않음
- 가능한 원인:
  1. 서버 프로세스가 자동으로 종료되지 않음
  2. 백그라운드 작업 스레드가 종료되지 않음
  3. 테스트 픽스처의 cleanup 로직 문제

**해결 방안** (다음 작업):
1. `conftest.py`의 `test_server` 픽스처에서 서버 종료 로직 확인
2. 백그라운드 작업 스레드 종료 확인
3. 테스트 완료 후 명시적으로 프로세스 종료 로직 추가

**임시 해결책**:
- 테스트 완료 후 수동으로 프로세스 종료 (Ctrl+C 또는 taskkill)

---

**최종 업데이트**: 2025-12-08
