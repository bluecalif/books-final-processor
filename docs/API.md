# API 문서

이 문서는 도서 PDF 구조 분석 및 엔티티 추출 시스템의 API 엔드포인트를 설명합니다.

**FastAPI 자동 생성 문서**:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- OpenAPI JSON: `http://localhost:8000/openapi.json`

---

## 목차

1. [기본 엔드포인트](#기본-엔드포인트)
2. [PDF 파싱](#pdf-파싱)
3. [구조 분석](#구조-분석)
4. [엔티티 추출](#엔티티-추출)
5. [텍스트 정리](#텍스트-정리)
6. [에러 처리](#에러-처리)

---

## 기본 엔드포인트

### GET /health

서버 헬스체크.

**응답**:
```json
{
  "status": "ok"
}
```

**상태 코드**: `200 OK`

---

### GET /api/books

책 리스트 조회.

**쿼리 파라미터**:
- `skip` (int, 선택, 기본값: 0): 건너뛸 책 수
- `limit` (int, 선택, 기본값: 100): 반환할 최대 책 수
- `status` (string, 선택): 필터링할 상태 (예: "parsed", "structured", "summarized")

**응답**:
```json
{
  "books": [
    {
      "id": 123,
      "title": "도서 제목",
      "author": "저자명",
      "category": "역사/사회",
      "status": "parsed",
      "page_count": 200,
      "created_at": "2025-12-10T12:00:00",
      "updated_at": "2025-12-10T12:05:00"
    }
  ],
  "total": 87
}
```

**상태 코드**: `200 OK`

---

### GET /api/books/{book_id}

책 상세 정보 조회.

**경로 파라미터**:
- `book_id` (int, 필수): 책 ID

**응답**:
```json
{
  "id": 123,
  "title": "도서 제목",
  "author": "저자명",
  "category": "역사/사회",
  "status": "parsed",
  "page_count": 200,
  "source_file_path": "data/input/book.pdf",
  "structure_data": {
    "main_start_page": 15,
    "main_end_page": 180,
    "chapters": [...]
  },
  "created_at": "2025-12-10T12:00:00",
  "updated_at": "2025-12-10T12:05:00"
}
```

**상태 코드**: 
- `200 OK`: 성공
- `404 Not Found`: 책을 찾을 수 없음

---

## PDF 파싱

### POST /api/books/upload

PDF 파일 업로드 및 파싱 시작 (백그라운드 작업).

**요청 형식**: `multipart/form-data`

**파라미터**:
- `file` (file, 필수): PDF 파일
- `title` (string, 선택): 책 제목
- `author` (string, 선택): 저자명
- `category` (string, 선택): 분야 (예: "역사/사회", "경제/경영", "인문/자기계발", "과학/기술")

**응답**:
```json
{
  "book_id": 123,
  "status": "uploaded",
  "message": "PDF parsing started in background"
}
```

**상태 코드**: `200 OK`

**참고**:
- 파싱은 백그라운드에서 실행됩니다.
- 파싱 완료까지 시간이 걸릴 수 있습니다 (대형 PDF의 경우 수 분).
- 파싱 완료 여부는 `GET /api/books/{book_id}`로 `status` 필드를 확인하세요.
- `status`가 `"parsed"`가 되면 파싱 완료입니다.
- 캐시된 파싱 결과가 있으면 즉시 완료됩니다 (API 호출 없음).

---

## 구조 분석

### GET /api/books/{book_id}/structure/candidates

구조 분석 후보 조회.

**경로 파라미터**:
- `book_id` (int, 필수): 책 ID

**전제 조건**: `status == "parsed"` 또는 `"structured"` 이상

**응답**:
```json
{
  "meta": {
    "total_pages": 200,
    "has_structure_file": true
  },
  "auto_candidates": [
    {
      "label": "heuristic_v1",
      "structure": {
        "main_start_page": 15,
        "main_end_page": 180,
        "chapters": [
          {
            "title": "1장",
            "start_page": 15,
            "end_page": 50,
            "order_index": 0
          }
        ]
      }
    }
  ],
  "chapter_title_candidates": [...],
  "samples": {
    "head": [...],
    "tail": [...],
    "around_main_start": [...]
  }
}
```

**상태 코드**:
- `200 OK`: 성공
- `404 Not Found`: 책을 찾을 수 없음
- `400 Bad Request`: 파싱이 완료되지 않음

**참고**:
- 구조 파일 캐시(`data/output/structure/{hash_6}_{title}_structure.json`)가 있으면 재사용됩니다.
- 구조 파일이 없을 때만 새로 분석을 수행합니다.

---

### POST /api/books/{book_id}/structure/final

구조 확정 (DB 저장 및 Chapter 레코드 생성).

**경로 파라미터**:
- `book_id` (int, 필수): 책 ID

**전제 조건**: `status == "parsed"` 또는 `"structured"` 이상

**요청 본문**:
```json
{
  "main_start_page": 15,
  "main_end_page": 180,
  "chapters": [
    {
      "title": "1장 제목",
      "start_page": 15,
      "end_page": 50,
      "order_index": 0
    },
    {
      "title": "2장 제목",
      "start_page": 51,
      "end_page": 100,
      "order_index": 1
    }
  ],
  "notes_pages": [],
  "start_pages": [1, 2, 3, 4, 5],
  "end_pages": [181, 182, 183, 184, 185]
}
```

**응답**:
```json
{
  "book_id": 123,
  "status": "structured",
  "structure_data": {
    "main_start_page": 15,
    "main_end_page": 180,
    "chapters": [...]
  },
  "chapter_count": 2
}
```

**상태 코드**:
- `200 OK`: 성공
- `404 Not Found`: 책을 찾을 수 없음
- `400 Bad Request`: 요청 데이터가 유효하지 않음

**참고**:
- 구조 확정 시 기존 Chapter 레코드가 삭제되고 새로 생성됩니다.
- `status`가 `"structured"`로 변경됩니다.

---

## 엔티티 추출

### POST /api/books/{book_id}/extract/pages

페이지 엔티티 추출 시작 (백그라운드 작업).

**경로 파라미터**:
- `book_id` (int, 필수): 책 ID

**전제 조건**: `status == "structured"`

**응답**:
```json
{
  "book_id": 123,
  "status": "processing",
  "message": "Page extraction started in background"
}
```

**상태 코드**:
- `200 OK`: 성공
- `404 Not Found`: 책을 찾을 수 없음
- `400 Bad Request`: 구조 분석이 완료되지 않음

**참고**:
- 추출은 백그라운드에서 실행됩니다.
- 추출 완료 여부는 `GET /api/books/{book_id}`로 `status` 필드를 확인하세요.
- `status`가 `"page_summarized"`가 되면 추출 완료입니다.
- 캐시된 엔티티 결과가 있으면 재사용됩니다 (LLM 호출 없음).

---

### POST /api/books/{book_id}/extract/chapters

챕터 구조화 시작 (백그라운드 작업).

**경로 파라미터**:
- `book_id` (int, 필수): 책 ID

**전제 조건**: `status == "page_summarized"`

**응답**:
```json
{
  "book_id": 123,
  "status": "processing",
  "message": "Chapter structuring started in background"
}
```

**상태 코드**:
- `200 OK`: 성공
- `404 Not Found`: 책을 찾을 수 없음
- `400 Bad Request`: 페이지 추출이 완료되지 않음

**참고**:
- 구조화는 백그라운드에서 실행됩니다.
- 완료 여부는 `GET /api/books/{book_id}`로 `status` 필드를 확인하세요.
- `status`가 `"summarized"`가 되면 완료입니다.

---

### POST /api/books/{book_id}/extract/book_summary

북 서머리 생성 시작 (백그라운드 작업).

**경로 파라미터**:
- `book_id` (int, 필수): 책 ID

**전제 조건**: `status == "summarized"`

**응답**:
```json
{
  "book_id": 123,
  "status": "processing",
  "message": "Book summary generation started in background"
}
```

**상태 코드**:
- `200 OK`: 성공
- `404 Not Found`: 책을 찾을 수 없음
- `400 Bad Request`: 챕터 구조화가 완료되지 않음

**참고**:
- 북 서머리는 백그라운드에서 실행됩니다.
- 완료 시 `data/output/book_summaries/{book_title}_report.json` 파일이 생성됩니다.
- 파일 생성 여부는 파일 시스템을 확인하세요.

---

### GET /api/books/{book_id}/pages

페이지 엔티티 리스트 조회.

**경로 파라미터**:
- `book_id` (int, 필수): 책 ID

**쿼리 파라미터**:
- `page_number` (int, 선택): 특정 페이지 번호 조회

**응답**:
```json
{
  "pages": [
    {
      "id": 1,
      "book_id": 123,
      "page_number": 15,
      "summary_text": "페이지 요약 (2-4문장)",
      "structured_data": {
        "page_summary": "...",
        "persons": ["인물1", "인물2"],
        "concepts": ["개념1", "개념2"],
        "events": ["사건1"],
        "examples": ["예시1"],
        "key_sentences": ["핵심 문장1", "핵심 문장2"]
      },
      "lang": "ko"
    }
  ],
  "total": 200
}
```

**상태 코드**:
- `200 OK`: 성공
- `404 Not Found`: 책을 찾을 수 없음

---

### GET /api/books/{book_id}/pages/{page_number}

특정 페이지 엔티티 상세 조회.

**경로 파라미터**:
- `book_id` (int, 필수): 책 ID
- `page_number` (int, 필수): 페이지 번호 (1-based)

**응답**:
```json
{
  "id": 1,
  "book_id": 123,
  "page_number": 15,
  "summary_text": "페이지 요약",
  "structured_data": {...},
  "lang": "ko"
}
```

**상태 코드**:
- `200 OK`: 성공
- `404 Not Found`: 책 또는 페이지를 찾을 수 없음

---

### GET /api/books/{book_id}/chapters

챕터 구조화 리스트 조회.

**경로 파라미터**:
- `book_id` (int, 필수): 책 ID

**쿼리 파라미터**:
- `chapter_id` (int, 선택): 특정 챕터 ID 조회

**응답**:
```json
{
  "chapters": [
    {
      "id": 1,
      "book_id": 123,
      "chapter_id": 1,
      "summary_text": "챕터 요약 (3-5문장)",
      "structured_data": {
        "core_message": "핵심 메시지",
        "summary_3_5_sentences": "...",
        "argument_flow": {
          "problem": "...",
          "background": "...",
          "main_claims": [...],
          "evidence_overview": "...",
          "counterpoints_or_limits": "...",
          "conclusion_or_action": "..."
        },
        "key_events": [...],
        "key_examples": [...],
        "insights": [...]
      },
      "lang": "ko"
    }
  ],
  "total": 10
}
```

**상태 코드**:
- `200 OK`: 성공
- `404 Not Found`: 책을 찾을 수 없음

---

### GET /api/books/{book_id}/chapters/{chapter_id}

특정 챕터 구조화 상세 조회.

**경로 파라미터**:
- `book_id` (int, 필수): 책 ID
- `chapter_id` (int, 필수): 챕터 ID

**응답**:
```json
{
  "id": 1,
  "book_id": 123,
  "chapter_id": 1,
  "summary_text": "챕터 요약",
  "structured_data": {...},
  "lang": "ko"
}
```

**상태 코드**:
- `200 OK`: 성공
- `404 Not Found`: 책 또는 챕터를 찾을 수 없음

---

## 텍스트 정리

### GET /api/books/{book_id}/text

정리된 텍스트 조회 (챕터별/페이지별).

**경로 파라미터**:
- `book_id` (int, 필수): 책 ID

**응답**:
```json
{
  "book_id": 123,
  "book_title": "도서 제목",
  "metadata": {
    "total_pages": 200,
    "main_start_page": 15,
    "main_end_page": 180,
    "chapter_count": 10
  },
  "text_content": {
    "chapters": [
      {
        "order_index": 0,
        "chapter_number": 1,
        "title": "1장 제목",
        "start_page": 15,
        "end_page": 50,
        "pages": [
          {
            "page_number": 15,
            "text": "페이지 텍스트..."
          }
        ]
      }
    ]
  }
}
```

**상태 코드**:
- `200 OK`: 성공
- `404 Not Found`: 책을 찾을 수 없음
- `404 Not Found`: 텍스트 파일이 없음

**참고**:
- 텍스트 파일이 없으면 자동으로 생성됩니다 (`data/output/text/{hash_6}_{title}_text.json`).

---

### POST /api/books/{book_id}/organize

텍스트 정리 실행 (수동 트리거).

**경로 파라미터**:
- `book_id` (int, 필수): 책 ID

**전제 조건**: `status == "structured"` 이상

**응답**:
```json
{
  "book_id": 123,
  "message": "Text organization started",
  "output_file": "data/output/text/abc123_book_title_text.json"
}
```

**상태 코드**:
- `200 OK`: 성공
- `404 Not Found`: 책을 찾을 수 없음

---

## 에러 처리

### 에러 응답 형식

모든 에러는 다음 형식으로 반환됩니다:

```json
{
  "detail": "에러 메시지"
}
```

### 상태 코드

| 상태 코드 | 의미 | 설명 |
|-----------|------|------|
| `200 OK` | 성공 | 요청이 성공적으로 처리됨 |
| `201 Created` | 생성 성공 | 리소스가 생성됨 |
| `400 Bad Request` | 잘못된 요청 | 요청 데이터가 유효하지 않음 (전제 조건 불만족 등) |
| `404 Not Found` | 리소스 없음 | 요청한 리소스를 찾을 수 없음 |
| `500 Internal Server Error` | 서버 오류 | 서버 내부 오류 발생 |

### 일반적인 에러 케이스

#### 1. 책을 찾을 수 없음

```json
{
  "detail": "Book not found: book_id=999"
}
```

**상태 코드**: `404 Not Found`

**해결 방법**: 올바른 `book_id`를 사용하세요.

---

#### 2. 전제 조건 불만족

```json
{
  "detail": "Book status must be 'structured' for page extraction, but current status is 'parsed'"
}
```

**상태 코드**: `400 Bad Request`

**해결 방법**: 
- 파이프라인 순서를 확인하세요: `uploaded` → `parsed` → `structured` → `page_summarized` → `summarized`
- 각 단계를 순서대로 완료하세요.

---

#### 3. 백그라운드 작업 실패

백그라운드 작업(파싱, 엔티티 추출 등)이 실패하면 `status`가 에러 상태로 변경됩니다:

- `error_parsing`: PDF 파싱 실패
- `error_structuring`: 구조 분석 실패
- `error_summarizing`: 엔티티 추출 실패
- `failed`: 일반적인 실패

**확인 방법**: `GET /api/books/{book_id}`로 `status` 필드를 확인하세요.

**해결 방법**:
- 로그 확인: 서버 로그 또는 `data/logs/` 디렉토리
- PDF 파일 확인: 파일이 손상되었는지 확인
- API 키 확인: Upstage API 키, OpenAI API 키 확인
- 재시도: 문제 해결 후 다시 시도

---

## 상태 전이

책의 상태는 다음 순서로 진행됩니다:

```
uploaded → parsed → structured → page_summarized → summarized
```

각 상태의 의미:

| 상태 | 의미 | 다음 단계 |
|------|------|-----------|
| `uploaded` | PDF 업로드 완료 | `POST /api/books/upload` 후 자동으로 파싱 시작 |
| `parsed` | PDF 파싱 완료 | `GET /api/books/{id}/structure/candidates` → `POST /api/books/{id}/structure/final` |
| `structured` | 구조 분석 완료 | `POST /api/books/{id}/extract/pages` |
| `page_summarized` | 페이지 엔티티 추출 완료 | `POST /api/books/{id}/extract/chapters` |
| `summarized` | 챕터 구조화 완료 | `POST /api/books/{id}/extract/book_summary` |

**에러 상태**:
- `error_parsing`: 파싱 실패
- `error_structuring`: 구조 분석 실패
- `error_summarizing`: 엔티티 추출 실패
- `failed`: 일반적인 실패

---

## 예시 플로우

### 전체 파이프라인 실행 예시

```bash
# 1. PDF 업로드 및 파싱 시작
curl -X POST "http://localhost:8000/api/books/upload" \
  -F "file=@data/input/book.pdf" \
  -F "title=도서 제목" \
  -F "author=저자명" \
  -F "category=역사/사회"

# 응답: {"book_id": 123, "status": "uploaded"}

# 2. 파싱 완료 대기 (폴링)
curl "http://localhost:8000/api/books/123"
# status가 "parsed"가 될 때까지 반복 확인

# 3. 구조 후보 조회
curl "http://localhost:8000/api/books/123/structure/candidates"

# 4. 구조 확정
curl -X POST "http://localhost:8000/api/books/123/structure/final" \
  -H "Content-Type: application/json" \
  -d '{
    "main_start_page": 15,
    "main_end_page": 180,
    "chapters": [...]
  }'

# 5. 페이지 엔티티 추출 시작
curl -X POST "http://localhost:8000/api/books/123/extract/pages"

# 6. 추출 완료 대기 (status: "page_summarized")

# 7. 챕터 구조화 시작
curl -X POST "http://localhost:8000/api/books/123/extract/chapters"

# 8. 완료 대기 (status: "summarized")

# 9. 북 서머리 생성
curl -X POST "http://localhost:8000/api/books/123/extract/book_summary"

# 10. 결과 조회
curl "http://localhost:8000/api/books/123/pages"
curl "http://localhost:8000/api/books/123/chapters"
```

---

## 참고 문서

- [README.md](../README.md): 프로젝트 개요 및 설치 방법
- [TODOs.md](../TODOs.md): Phase별 상세 구현 계획
- FastAPI 자동 생성 문서: `http://localhost:8000/docs` (서버 실행 시)

