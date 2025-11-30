# 대량 도서 처리 스크립트 사용 가이드

## 개요

CSV 파일에 있는 도서를 일괄 처리하는 스크립트입니다.
- PDF 파싱 (Upstage API, 캐시 재사용)
- 구조 분석 (Footer 기반 휴리스틱)
- 텍스트 파일 생성

## 1. 배치 처리 실행

### 기본 사용법

```bash
poetry run python -m backend.scripts.batch_process_books
```

### 주요 특징

- **상세 로그**: `data/logs/batch_processing/batch_process_YYYYMMDD_HHMMSS.log` 파일에 저장
  - 각 도서별 처리 단계 (파싱/구조/텍스트) 상태
  - 파일 생성 여부
  - 에러 메시지
  
- **콘솔 출력**: 진행률과 소요시간만 표시
  ```
  [진행률: 45.2%] (23/51) 현재: 1등의 통찰... | 경과: 12.5분 | 예상 남은 시간: 15.3분
  ```

### 처리 플로우

1. CSV 파일 읽기 (`docs/100권 노션 원본_수정.csv`)
2. 이미 처리된 도서 자동 제외 (DB에서 `status >= 'structured'` 확인)
3. 각 도서별 처리:
   - PDF 파일 찾기 (`data/input/` 디렉토리)
   - Book 레코드 생성/조회
   - PDF 파싱 실행 (캐시 사용)
   - 구조 분석 실행 및 자동 적용
   - 텍스트 파일 생성
4. 에러 처리: 개별 도서 실패 시에도 나머지 도서 계속 처리

### 로그 파일 위치

```
data/logs/batch_processing/batch_process_YYYYMMDD_HHMMSS.log
```

## 2. 결과 검증

### 기본 사용법 (가장 최근 로그 파일 자동 사용)

```bash
poetry run python -m backend.scripts.verify_batch_processing
```

또는

```bash
poetry run python -m backend.scripts.verify_batch_processing --latest
```

### 특정 로그 파일 검증

```bash
poetry run python -m backend.scripts.verify_batch_processing data/logs/batch_processing/batch_process_20241215_123456.log
```

### 리포트 파일 저장

```bash
poetry run python -m backend.scripts.verify_batch_processing --output verification_report.json
```

### 검증 항목

1. **로그 파싱**: 각 도서별 처리 단계 추출
   - PDF 파일 찾기
   - Book 레코드 생성
   - 파싱 성공/실패
   - 구조 분석 성공/실패
   - 텍스트 파일 생성 성공/실패

2. **파일 존재 여부**: 실제 디렉토리에서 확인
   - 캐시 파일 (`data/cache/upstage/`)
   - 구조 파일 (`data/output/structure/`)
   - 텍스트 파일 (`data/output/text/`)

3. **DB 레코드 확인**: DB 상태 확인
   - Book 레코드 존재 여부
   - 상태 (status)
   - 페이지 수, 분야 등

### 리포트 출력 예시

```
================================================================================
대량 도서 처리 검증 리포트
================================================================================

[전체 통계]
  전체 도서: 87개
  성공: 75개
  실패: 3개
  상태 불명: 9개

[단계별 통계]
  PDF 파일 찾기: 78개
  Book 레코드 생성: 65개
  파싱 - 성공: 75개, 실패: 0개, 스킵: 12개
  구조 분석 - 성공: 75개, 실패: 0개, 스킵: 12개
  텍스트 파일 - 성공: 75개, 실패: 0개, 스킵: 12개

[파일 존재 여부]
  캐시 파일: 75개
  구조 파일: 75개
  텍스트 파일: 75개

[이슈] (3개 도서)
  - 도서명1 (ID: 123)
    * PDF 파일 없음
  - 도서명2 (ID: 124)
    * 파싱 실패
```

### 리포트 파일 형식 (JSON)

```json
{
  "log_file": "data/logs/batch_processing/batch_process_20241215_123456.log",
  "verification_time": "2024-12-15T12:34:56",
  "statistics": {
    "total_books": 87,
    "success": 75,
    "failed": 3,
    ...
  },
  "issues": [...],
  "books": {
    "도서명": {
      "title": "도서명",
      "book_id": 123,
      "status": "success",
      "steps": {
        "pdf_found": true,
        "parsing": "success",
        "structure": "success",
        "text_file": "success"
      },
      "output_files": {
        "cache_file": "...",
        "structure_file": "...",
        "text_file": "...",
        "cache_file_exists": true,
        "structure_file_exists": true,
        "text_file_exists": true
      },
      "db_record": {...}
    }
  }
}
```

## 3. 주의사항

1. **PDF 파일 위치**: CSV에 있는 도서의 PDF 파일이 `data/input/` 디렉토리에 있어야 합니다.
2. **캐시 재사용**: 이미 캐시된 PDF는 Upstage API를 호출하지 않으므로 비용이 발생하지 않습니다.
3. **에러 처리**: 개별 도서 처리 실패 시에도 나머지 도서는 계속 처리됩니다.
4. **로그 파일**: 상세한 처리 내역은 로그 파일에서 확인할 수 있습니다.

## 4. 문제 해결

### PDF 파일을 찾을 수 없음

- `data/input/` 디렉토리에 PDF 파일이 있는지 확인
- 파일명이 CSV의 Title과 일치하는지 확인
- 로그 파일에서 실제 검색된 파일명 확인

### 파싱 실패

- 로그 파일에서 상세 에러 메시지 확인
- Upstage API 키가 올바르게 설정되어 있는지 확인 (`.env` 파일)

### 텍스트 파일 생성 실패

- 구조 분석이 성공적으로 완료되었는지 확인
- DB의 Book 레코드 상태 확인 (`status == 'structured'`)
- 로그 파일에서 상세 에러 메시지 확인

