# 테스트 문제 히스토리

## 개요
E2E 테스트 실행 중 발생한 문제들과 해결 과정을 기록합니다.

---

## 2025-12-08: Phase 7.2 E2E 테스트 문제

### 문제 1: 이모지 인코딩 오류 (해결 완료)

**발생 시점**: 2025-12-08 22:22

**증상**:
```
UnicodeEncodeError: 'cp949' codec can't encode character '\u2705' in position 8: illegal multibyte sequence
```

**원인**:
- PowerShell 환경에서 이모지(✅, ❌) 출력 시 cp949 인코딩 오류
- `test_e2e_full_pipeline_unified.py`와 `test_utils.py`에서 이모지 사용

**해결**:
- 모든 이모지를 텍스트로 변경: `✅` → `[OK]`, `❌` → `[FAIL]`
- `test_utils.py`의 `wait_for_extraction_with_progress` 함수 수정
- `test_e2e_full_pipeline_unified.py`의 모든 출력 메시지 수정
- `test_api_contract.py`의 출력 메시지 수정
- `test_e2e_extraction.py`의 출력 메시지 수정

**수정된 파일**:
- `backend/tests/test_e2e_full_pipeline_unified.py`
- `backend/tests/test_utils.py`
- `backend/tests/test_api_contract.py`
- `backend/tests/test_e2e_extraction.py`

**확인 방법**:
```bash
grep -r "print.*✅\|print.*❌" backend/tests/
# 결과: 없음 (모두 [OK], [FAIL]로 변경됨)
```

---

### 문제 2: Query import 누락 (해결 완료)

**발생 시점**: 2025-12-08 22:22

**증상**:
```
NameError: name 'Query' is not defined
```

**원인**:
- `backend/api/routers/books.py`에서 `Query` 사용하지만 import 누락

**해결**:
- `from fastapi import Query` 추가

**수정된 파일**:
- `backend/api/routers/books.py`

---

### 문제 3: 터미널 진행률 출력 문제 (미해결)

**발생 시점**: 2025-12-08 22:23

**증상**:
1. **경과시간 및 남은 시간이 모두 0초로 출력**
   ```
   [TEST] Pages: 0/210 (0%) | Time: 00:00 | Avg: 0.0s/item | Est: 00:00
   ```
2. **서버 로그는 계속 찍히는데 터미널에는 모두 완료된 후 한번에 출력**

**원인 분석**:

#### 3.1 경과시간 0초 문제

**근본 원인**:
- `test_utils.py`의 `wait_for_extraction_with_progress` 함수에서:
  ```python
  if current_count > 0:
      avg_time = elapsed / current_count
      ...
  else:
      avg_time = 0.0
      est_min = 0
      est_sec = 0
  ```
- `get_page_count()` 함수가 API를 호출하여 DB에서 페이지 수를 조회
- **백그라운드 작업이 진행 중일 때는 아직 DB에 저장되지 않아서 `current_count = 0` 반환**
- 따라서 `current_count > 0` 조건이 false가 되어 `avg_time = 0.0` 설정

**서버 로그 vs 테스트 출력 불일치**:
- 서버 로그: `extraction_service.py`에서 `logger.info("[PROGRESS] ...")`로 **실시간 파일 기록**
- 테스트 출력: `test_utils.py`에서 `print()`로 **stdout 버퍼링** + `check_interval=10` (10초마다만 확인)

**문제점**:
1. **DB 조회 방식의 한계**: 백그라운드 작업이 완료될 때까지 DB에 저장되지 않음
2. **서버 로그 파싱 미사용**: 서버 로그에 실시간 진행률이 있지만 테스트 코드에서 활용하지 않음
3. **출력 버퍼링**: Python의 stdout 버퍼링으로 인해 즉시 출력되지 않음

**개선 방안**:
1. **서버 로그 파일 실시간 파싱**: `data/test_results/server_*.log` 파일을 tail하여 `[PROGRESS]` 메시지 파싱
2. **진행률 API 엔드포인트 추가**: 백그라운드 작업 진행률을 메모리에 저장하고 API로 조회
3. **출력 버퍼링 해제**: `print(..., flush=True)` 사용 또는 `sys.stdout.flush()` 호출
4. **check_interval 단축**: 10초 → 2-3초로 단축하여 더 자주 확인

---

### 문제 4: 한글 출력 깨짐 (미해결)

**발생 시점**: 2025-12-08 22:23

**증상**:
```
[TEST] Full Pipeline Processing
Book ID: NEW, Title: 1
Category:/濵, Chapters: 7
```

**원인 분석**:
- PowerShell의 기본 인코딩이 cp949인데, UTF-8로 인코딩된 한글 출력 시 깨짐
- Python의 `print()` 함수가 시스템 기본 인코딩 사용

**개선 방안**:
1. **PowerShell 인코딩 설정**: 테스트 시작 전 `[Console]::OutputEncoding = [System.Text.Encoding]::UTF8` 실행
2. **환경변수 설정**: `$env:PYTHONIOENCODING = "utf-8"` 설정
3. **로그 파일로 우회**: 터미널 출력 대신 로그 파일에 기록 후 확인

---

### 문제 5: 챕터 구조화 미실행 (원인 분석 완료)

**발생 시점**: 2025-12-08 22:27

**증상**:
- 페이지 엔티티 추출 완료 후 챕터 구조화 단계로 진행되지 않음
- Book ID 259 상태: `page_summarized` (챕터 구조화 대기 중)

**원인 분석**:

#### 5.1 서버 로그 확인 결과

**확인 사항**:
- 서버 로그에서 `POST /api/books/259/extract/chapters` 호출 **없음**
- 마지막 요청: `GET /api/books/259/pages` (22:27:13)
- 페이지 엔티티 추출 완료: 22:27:11 (`status=BookStatus.PAGE_SUMMARIZED`)

#### 5.2 테스트 코드 흐름 분석

`test_e2e_full_pipeline_unified.py`의 `process_book_full_pipeline` 함수:
```python
# STEP 5: 페이지 엔티티 추출
book_data = wait_for_extraction_with_progress(
    ...
    target_status="page_summarized",
    ...
)

# STEP 6: 챕터 구조화 (실행되지 않음)
response = e2e_client.post(f"/api/books/{book_id}/extract/chapters")
```

#### 5.3 근본 원인

**이모지 인코딩 오류로 테스트 중단**:
- `wait_for_extraction_with_progress` 함수에서 완료 메시지 출력 시:
  ```python
  # test_utils.py (수정 전)
  if status == target_status:
      print(f"[TEST] ✅ {extraction_type.capitalize()} extraction completed...")
      # ↑ 여기서 UnicodeEncodeError 발생
      return response.json()
  ```
- STEP 5 완료 후 `status == "page_summarized"` 확인
- 완료 메시지 출력 시 이모지(✅) 인코딩 오류 발생
- 테스트 중단 → STEP 6 미실행

**해결 상태**:
- ✅ 이모지 제거 완료: `✅` → `[OK]`로 변경
- ✅ 테스트 재실행 시 STEP 6 정상 진행 예상

**확인 필요 사항** (재실행 후):
1. 서버 로그에서 챕터 구조화 API 호출 여부 확인
2. `extraction.py`의 `start_chapter_extraction` 함수에서 상태 체크 로직 확인
3. 백그라운드 작업 실행 여부 확인

**개선 방안**:
1. **에러 처리 강화**: 각 단계에서 예외 발생 시 상세 로그 출력
2. **상태 확인 로직 명확화**: `page_summarized` → `summarized` 상태 전이 확인
3. **백그라운드 작업 실행 확인**: API 호출 후 실제 백그라운드 작업 시작 여부 확인

---

## 다음 단계

### 우선순위 1: 진행률 출력 문제 해결
- 서버 로그 파일 실시간 파싱 구현
- 또는 진행률 API 엔드포인트 추가

### 우선순위 2: 한글 출력 문제 해결
- PowerShell 인코딩 설정 추가
- 또는 로그 파일 기반 확인으로 전환

### 우선순위 3: 챕터 구조화 미실행 원인 파악 (완료)
- ✅ 원인 확인: 이모지 인코딩 오류로 테스트 중단
- ✅ 해결: 이모지 제거 완료
- ⏳ 재실행 후 최종 확인 필요

---

## 해결 완료 요약

1. ✅ **이모지 인코딩 오류**: 모든 `print()` 문에서 이모지 제거 완료
2. ✅ **Query import 누락**: `backend/api/routers/books.py`에 import 추가 완료
3. ✅ **챕터 구조화 미실행 원인 파악**: 이모지 오류로 테스트 중단 확인

## 미해결 문제

1. ⏳ **터미널 진행률 출력 문제**: 해결책 제시 완료, 구현 대기
2. ⏳ **한글 출력 깨짐**: 해결책 제시 완료, 구현 대기

---

## 참고

- 서버 로그 위치: `data/test_results/server_*.log`
- 테스트 코드 위치: `backend/tests/`
- API 라우터 위치: `backend/api/routers/`

