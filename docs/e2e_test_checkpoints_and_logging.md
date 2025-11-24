# E2E 테스트 체크포인트 및 로깅 가이드

## 1. E2E 테스트 체크포인트

### 1.1 전체 플로우 테스트 (`test_e2e_pdf_parsing_full_flow`)

#### 체크포인트 1: PDF 파일 존재 확인
- **검증**: `TEST_PDF_PATH.exists()`
- **실패 시**: 테스트 PDF 파일이 없음
- **로그 위치**: 테스트 로그 파일

#### 체크포인트 2: PDF 파일 업로드
- **검증**: 
  - `response.status_code == 200`
  - `upload_data["status"] == "uploaded"`
  - `upload_data["book_id"]` 존재
- **실패 시**: 업로드 API 실패 또는 파일 형식 오류
- **로그 위치**: 서버 로그 파일, 테스트 로그 파일

#### 체크포인트 3: 업로드된 책 상태 확인
- **검증**:
  - `book_response.status_code == 200`
  - `book_data["status"] == "uploaded"`
  - `book_data["title"]`, `book_data["author"]` 일치
- **실패 시**: DB 저장 실패 또는 API 응답 오류
- **로그 위치**: 서버 로그 파일, 테스트 로그 파일

#### 체크포인트 4: 백그라운드 작업 완료 대기
- **검증**:
  - 상태 폴링: `uploaded` → `parsed` (최대 5분 대기)
  - 타임아웃: 300초 초과 시 실패
  - 에러 상태: `error_parsing` 시 실패
- **실패 시**: 
  - 타임아웃: 백그라운드 작업이 너무 오래 걸림
  - 에러 상태: 파싱 프로세스 실패
- **로그 위치**: 서버 로그 파일 (백그라운드 작업 로그), 테스트 로그 파일

#### 체크포인트 5: 파싱 결과 검증
- **검증**:
  - `book_data["status"] == "parsed"`
  - `book_data["page_count"] is not None`
  - `book_data["page_count"] > 0`
  - `book_data["id"] == book_id`
  - `book_data["title"]`, `book_data["author"]` 일치
- **실패 시**: 파싱 결과가 DB에 저장되지 않음
- **로그 위치**: 서버 로그 파일, 테스트 로그 파일

#### 체크포인트 6: 캐시 저장 검증
- **검증**:
  - 캐시 디렉토리 존재: `cache_dir.exists()`
  - 캐시 파일 생성: `cache_file.exists()`
  - 캐시 파일 크기: `cache_file.stat().st_size > 0`
  - 캐시 파일 내용: `"elements" in cached_data or "api" in cached_data`
- **실패 시**: 캐시 저장 실패 (파일 시스템 오류 또는 권한 문제)
- **로그 위치**: 서버 로그 파일 (`[CACHE_SAVE]` 로그), 테스트 로그 파일

#### 체크포인트 7: 양면 분리 검증
- **검증**:
  - `book_data["page_count"] >= 10` (원본 10페이지 기준)
- **실패 시**: 양면 분리 로직이 제대로 작동하지 않음
- **로그 위치**: 서버 로그 파일 (`[INFO] Parsing completed: ...`), 테스트 로그 파일

#### 체크포인트 8: 페이지 데이터 검증 (선택적)
- **검증**:
  - `pages_response.status_code == 200` (API 존재 시)
  - `"pages" in pages_data`
  - `len(pages_data["pages"]) > 0`
  - 첫 번째 페이지: `page_number`, `raw_text`, `elements` 또는 `page_metadata` 필드 존재
  - 페이지 번호 순차성: `page["page_number"] == i + 1`
- **실패 시**: 페이지 API 없음 또는 데이터 형식 오류
- **로그 위치**: 서버 로그 파일, 테스트 로그 파일

### 1.2 상태 변경 테스트 (`test_e2e_pdf_parsing_status_transition`)

#### 체크포인트 1-3: 업로드 및 초기 상태 확인
- **검증**: 위와 동일

#### 체크포인트 4: 상태 변경 이력 추적
- **검증**:
  - `"uploaded" in status_history`
  - `"parsed" in status_history`
  - `status_history[-1] == "parsed"`
- **실패 시**: 상태 변경 순서가 올바르지 않음
- **로그 위치**: 테스트 로그 파일 (상태 이력)

### 1.3 캐시 재사용 테스트 (`test_e2e_pdf_parsing_cache_reuse`)

#### 체크포인트 1: 첫 번째 파싱 (캐시 미스)
- **검증**: 위와 동일

#### 체크포인트 2: 캐시 파일 생성 확인
- **검증**:
  - `cache_file.exists()`
  - `cache_file.stat().st_mtime` 기록
- **실패 시**: 캐시 파일이 생성되지 않음
- **로그 위치**: 서버 로그 파일 (`[CACHE_SAVE]`), 테스트 로그 파일

#### 체크포인트 3: 두 번째 파싱 (캐시 히트)
- **검증**:
  - `cache_file.exists()` (캐시 파일 유지)
  - `book_data_1["page_count"] == book_data["page_count"]` (결과 일치)
- **실패 시**: 캐시 재사용 실패 또는 결과 불일치
- **로그 위치**: 서버 로그 파일 (`[INFO] Cache hit`), 테스트 로그 파일

### 1.4 페이지 데이터 검증 테스트 (`test_e2e_pdf_parsing_page_data_validation`)

#### 체크포인트 1-2: 업로드 및 파싱 완료
- **검증**: 위와 동일

#### 체크포인트 3: 페이지 데이터 구조 검증
- **검증**:
  - 페이지 리스트 존재 및 비어있지 않음
  - 각 페이지에 필수 필드 존재 (`page_number`, `raw_text`)
  - 페이지 번호 순차성
- **실패 시**: 페이지 데이터 구조 오류
- **로그 위치**: 서버 로그 파일, 테스트 로그 파일

## 2. 로깅 현황 분석

### 2.1 현재 로깅 구현 상태

#### ✅ 테스트 로그 (파일 저장)
- **위치**: `data/test_results/cache_analysis_{timestamp}.log`
- **설정**: `setup_test_logging()` 함수
- **범위**: 테스트 코드의 로그만 저장
- **문제점**: 
  - 일부 테스트 함수에서만 사용 (`test_e2e_pdf_parsing_full_flow`만)
  - 다른 테스트 함수에서는 로그 파일 저장 안 함

#### ✅ 서버 로그 (파일 저장)
- **위치**: `data/test_results/server_{timestamp}.log`
- **설정**: `conftest_e2e.py`의 `test_server` fixture
- **범위**: 서버 전체 로그 (stdout, stderr)
- **장점**: 서버 실행 중 모든 로그 저장

#### ⚠️ 백엔드 서비스 로그 (파일 저장 없음)
- **현재 상태**: 
  - `ParsingService`: `logger.info()` 사용 (콘솔 출력만)
  - `PDFParser`: `logger.info()` 사용 (콘솔 출력만)
  - `CacheManager`: `logger.info()`, `logger.error()` 사용 (콘솔 출력만)
  - `UpstageAPIClient`: `logger.info()`, `logger.warning()` 사용 (콘솔 출력만)
- **문제점**: 
  - 로그가 파일로 저장되지 않음
  - 서버 로그 파일에만 포함 (서버 실행 시)
  - 별도 로그 파일 없음

### 2.2 로깅 개선 필요 사항

#### ❌ 부족한 로깅 영역

1. **테스트 로그 파일 통합**
   - 모든 테스트 함수에서 로그 파일 저장 필요
   - 현재: `test_e2e_pdf_parsing_full_flow`만 로그 파일 저장

2. **백엔드 서비스 로그 파일 저장**
   - `ParsingService`, `PDFParser`, `CacheManager`, `UpstageAPIClient`의 로그를 별도 파일로 저장
   - 현재: 서버 로그 파일에만 포함 (서버 실행 시)

3. **로그 레벨 관리**
   - DEBUG 레벨 로그도 파일에 저장 필요
   - 현재: 일부 DEBUG 로그는 파일에 저장 안 됨

4. **로그 파일 명명 규칙**
   - 테스트별로 구분 가능한 파일명 필요
   - 현재: `cache_analysis_{timestamp}.log` (일부 테스트만)

## 3. 개선 방안

### 3.1 테스트 로그 파일 통합

**목표**: 모든 테스트 함수에서 로그 파일 저장

**방법**:
1. `conftest_e2e.py`에 `test_log_file` fixture 추가
2. 모든 테스트 함수에서 `test_log_file` fixture 사용
3. 로그 파일명: `test_e2e_{test_function_name}_{timestamp}.log`

### 3.2 백엔드 서비스 로그 파일 저장

**목표**: 백엔드 서비스의 로그를 별도 파일로 저장

**방법**:
1. `backend/api/main.py`에서 로깅 설정 추가
2. 로그 파일명: `backend_{timestamp}.log`
3. 로그 레벨: DEBUG 이상
4. 로그 위치: `data/test_results/` 또는 `data/logs/`

### 3.3 로그 파일 통합 관리

**목표**: 모든 로그를 한 곳에서 확인 가능

**방법**:
1. 테스트 실행 시 로그 디렉토리 생성: `data/test_results/{test_run_timestamp}/`
2. 하위 디렉토리 구조:
   ```
   data/test_results/{test_run_timestamp}/
   ├── server.log                    # 서버 로그
   ├── test_e2e_pdf_parsing_full_flow.log  # 테스트 로그
   ├── backend_parsing_service.log  # ParsingService 로그
   ├── backend_pdf_parser.log       # PDFParser 로그
   ├── backend_cache_manager.log    # CacheManager 로그
   └── backend_upstage_api.log      # UpstageAPIClient 로그
   ```

## 4. 체크포인트 실패 시 원인 파악 방법

### 4.1 체크포인트별 로그 확인 위치

| 체크포인트 | 실패 원인 파악 로그 위치 |
|-----------|----------------------|
| PDF 파일 존재 확인 | 테스트 로그 파일 |
| PDF 파일 업로드 | 서버 로그 파일 (`[FUNCTION] upload_book`) |
| 업로드된 책 상태 확인 | 서버 로그 파일 (`[FUNCTION] get_book`) |
| 백그라운드 작업 완료 대기 | 서버 로그 파일 (`[FUNCTION] _parse_book_background`, `[FUNCTION] ParsingService.parse_book`) |
| 파싱 결과 검증 | 서버 로그 파일 (`[RETURN] parse_pdf()`, `[RETURN] get_book()`) |
| 캐시 저장 검증 | 서버 로그 파일 (`[CACHE_SAVE]`) |
| 양면 분리 검증 | 서버 로그 파일 (`[INFO] Parsing completed: ...`) |
| 페이지 데이터 검증 | 서버 로그 파일, 테스트 로그 파일 |

### 4.2 실패 시 확인 순서

1. **테스트 로그 파일 확인**
   - `data/test_results/test_e2e_{test_function_name}_{timestamp}.log`
   - 테스트 실행 흐름 확인

2. **서버 로그 파일 확인**
   - `data/test_results/server_{timestamp}.log`
   - 백엔드 서비스 실행 흐름 확인

3. **백엔드 서비스 로그 파일 확인** (개선 후)
   - `data/test_results/{test_run_timestamp}/backend_*.log`
   - 각 서비스별 상세 로그 확인

4. **캐시 파일 확인**
   - `data/cache/upstage/{file_hash}.json`
   - 캐시 저장 여부 확인

5. **DB 상태 확인** (API를 통해)
   - `GET /api/books/{book_id}`
   - DB 저장 상태 확인

## 5. 요약

### 현재 상태
- ✅ 서버 로그 파일 저장 (서버 실행 시)
- ✅ 일부 테스트 로그 파일 저장 (`test_e2e_pdf_parsing_full_flow`)
- ⚠️ 백엔드 서비스 로그 파일 저장 없음 (서버 로그에만 포함)
- ⚠️ 모든 테스트 함수에서 로그 파일 저장 안 함

### 개선 필요
1. 모든 테스트 함수에서 로그 파일 저장
2. 백엔드 서비스 로그를 별도 파일로 저장
3. 로그 파일 통합 관리 (테스트 실행별 디렉토리)

### 체크포인트
- 총 8개 주요 체크포인트 (전체 플로우 테스트)
- 각 체크포인트별 실패 원인 파악 로그 위치 명확화 필요

