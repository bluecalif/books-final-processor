# PDFParser 반환 형식 검토 보고서

## 현재 상황

### 참고 파일의 반환 형식 (`pdf_parser_REF.py`)

```python
{
    "success": True,
    "pages": [
        {
            "page_number": 1,  # 분리 후 페이지 번호
            "original_page": 1,  # 원본 페이지 번호 (clean_output=False일 때만)
            "side": "left",     # 좌/우 구분 (clean_output=False일 때만)
            "elements": [...],
            "raw_text": "...",  # 좌/우별 텍스트
            "metadata": {...}   # (clean_output=False일 때만)
        }
    ],
    "total_pages": 4,           # 분리 후 페이지 수
    "original_pages": 2,        # 원본 페이지 수
    "split_applied": True,      # 양면 분리 적용 여부
    "force_split_applied": False,
    "pdf_path": str,
    "metadata": {
        "api_version": "2.0",
        "model": "document-parse-250618",
        "processing_applied": {
            "upstage_parsing": True,
            "element_structuring": True,
            "page_splitting": True
        }
    }
}
```

### 현재 프로젝트의 반환 형식 (`pdf_parser.py`)

```python
{
    "pages": [
        {
            "page_number": 1,  # 원본 페이지 번호
            "elements": [...],
            "raw_text": "..."  # 전체 페이지 텍스트
        }
    ],
    "total_pages": N,
    "total_elements": N,
    "metadata": {...}
}
```

## 사용처 분석

### 1. ParsingService (`backend/api/services/parsing_service.py`)

**사용 필드**:
- `parsed_data.get("pages", [])` - ✅ 필수
- `page_data.get("page_number")` - ✅ 필수
- `page_data.get("raw_text")` - ✅ 필수
- `page_data.get("elements", [])` - ✅ 필수 (metadata로 저장)
- `parsed_data.get("total_pages", 0)` - ✅ 필수 (book.page_count 설정)

**코드 위치**:
```python
# Line 66-67
parsed_data = self.pdf_parser.parse_pdf(book.source_file_path, use_cache=True)
logger.info(f"[RETURN] parse_pdf() 반환값: pages 개수={len(parsed_data.get('pages', []))}, total_pages={parsed_data.get('total_pages', 0)}")

# Line 71
pages_data = parsed_data.get("pages", [])

# Line 87-95
for idx, page_data in enumerate(pages_data):
    page = Page(
        book_id=book_id,
        page_number=page_data.get("page_number"),
        raw_text=page_data.get("raw_text"),
        page_metadata={"elements": page_data.get("elements", [])} if page_data.get("elements") else None,
    )

# Line 104-106
book.status = BookStatus.PARSED
book.page_count = parsed_data.get("total_pages", 0)
```

**호환성**: ✅ **호환됨**
- `pages`, `page_number`, `raw_text`, `elements`, `total_pages` 모두 사용
- 참고 파일 형식과 호환 (clean_output=True일 때)

### 2. StructureService (`backend/api/services/structure_service.py`)

**사용 필드**:
- `parsed_data.get("total_pages", 0)` - ✅ 필수
- `parsed_data.get("pages", [])` - ✅ 필수 (StructureBuilder에 전달)

**코드 위치**:
```python
# Line 60
parsed_data = self.pdf_parser.parse_pdf(book.source_file_path, use_cache=True)

# Line 64
heuristic_structure = self.structure_builder.build_structure(parsed_data)

# Line 80
"total_pages": parsed_data.get("total_pages", 0),
```

**호환성**: ✅ **호환됨**
- `total_pages`, `pages` 필드 사용
- 참고 파일 형식과 호환

### 3. StructureBuilder (`backend/structure/structure_builder.py`)

**사용 필드**:
- `parsed_data.get("total_pages", 0)` - ✅ 필수
- `parsed_data.get("pages", [])` - ✅ 필수 (ContentBoundaryDetector, ChapterDetector에 전달)

**코드 위치**:
```python
# Line 58
boundaries = self.boundary_detector.detect_boundaries(parsed_data)

# Line 62
chapters = self.chapter_detector.detect_chapters(parsed_data, main_pages)

# Line 80
"total_pages": parsed_data.get("total_pages", 0),
```

**호환성**: ✅ **호환됨**
- `total_pages`, `pages` 필드 사용
- 참고 파일 형식과 호환

### 4. ContentBoundaryDetector (`backend/structure/content_boundary_detector.py`)

**예상 사용 필드**:
- `parsed_data.get("pages", [])` - ✅ 필수
- 각 `page`의 `page_number`, `raw_text` 사용 예상

**호환성**: ✅ **호환됨** (구현 확인 필요하나, `pages` 배열만 사용하면 호환)

### 5. ChapterDetector (`backend/structure/chapter_detector.py`)

**예상 사용 필드**:
- `parsed_data.get("pages", [])` - ✅ 필수
- 각 `page`의 `page_number`, `elements` 사용 예상

**호환성**: ✅ **호환됨** (구현 확인 필요하나, `pages` 배열만 사용하면 호환)

## 반환 형식 제안

### 옵션 1: 참고 파일 형식 그대로 (권장)

**장점**:
- 참고 파일과 완전히 동일하여 구현 단순화
- 추가 메타데이터 제공 (`original_pages`, `split_applied` 등)
- 디버깅 및 로깅에 유용

**단점**:
- `success` 필드 추가 (현재 프로젝트에는 없음)
- `pdf_path` 필드 추가 (현재 프로젝트에는 없음)
- `force_split_applied` 필드 추가 (현재 프로젝트에는 없음)

**반환 형식**:
```python
{
    "success": True,
    "pages": [
        {
            "page_number": 1,  # 분리 후 페이지 번호
            "elements": [...],  # clean_output=True일 때 page 필드 제거됨
            "raw_text": "..."   # 좌/우별 텍스트
        }
    ],
    "total_pages": 4,           # 분리 후 페이지 수
    "total_elements": N,        # 현재 프로젝트 호환성 유지
    "original_pages": 2,        # 원본 페이지 수 (메타데이터)
    "split_applied": True,      # 양면 분리 적용 여부
    "metadata": {
        "api_version": "2.0",
        "model": "document-parse-250618",
        "processing_applied": {
            "upstage_parsing": True,
            "element_structuring": True,
            "page_splitting": True
        }
    }
}
```

### 옵션 2: 현재 프로젝트 형식 유지 + 최소 추가

**장점**:
- 현재 프로젝트와 완전히 호환
- 최소한의 변경만 필요

**단점**:
- 참고 파일과 차이가 있어 구현 시 주의 필요
- 메타데이터 부족 (디버깅 어려움)

**반환 형식**:
```python
{
    "pages": [
        {
            "page_number": 1,  # 분리 후 페이지 번호
            "elements": [...],  # clean_output=True일 때 page 필드 제거됨
            "raw_text": "..."   # 좌/우별 텍스트
        }
    ],
    "total_pages": 4,           # 분리 후 페이지 수
    "total_elements": N,        # 현재 프로젝트 호환성 유지
    "metadata": {
        "original_pages": 2,    # 원본 페이지 수 (메타데이터로 이동)
        "split_applied": True,  # 양면 분리 적용 여부
        "api_version": "2.0",
        "model": "document-parse-250618"
    }
}
```

### 옵션 3: 하이브리드 (권장)

**장점**:
- 참고 파일의 핵심 메타데이터 유지
- 현재 프로젝트 호환성 유지
- `total_elements` 필드 유지 (현재 프로젝트 사용)

**단점**:
- 약간의 커스터마이징 필요

**반환 형식**:
```python
{
    "pages": [
        {
            "page_number": 1,  # 분리 후 페이지 번호
            "elements": [...],  # clean_output=True일 때 page 필드 제거됨
            "raw_text": "..."   # 좌/우별 텍스트
        }
    ],
    "total_pages": 4,           # 분리 후 페이지 수
    "total_elements": N,        # 현재 프로젝트 호환성 유지
    "original_pages": 2,         # 원본 페이지 수 (메타데이터)
    "split_applied": True,       # 양면 분리 적용 여부
    "metadata": {
        "api_version": "2.0",
        "model": "document-parse-250618",
        "processing_applied": {
            "upstage_parsing": True,
            "element_structuring": True,
            "page_splitting": True
        }
    }
}
```

## 최종 권장 사항

### 옵션 3 (하이브리드) 권장

**이유**:
1. **호환성**: 현재 프로젝트의 모든 사용처와 호환
   - `pages`, `page_number`, `raw_text`, `elements`, `total_pages` 모두 유지
   - `total_elements` 필드 유지 (현재 프로젝트에 있음)
2. **메타데이터**: 참고 파일의 유용한 메타데이터 유지
   - `original_pages`: 원본 페이지 수 (디버깅 유용)
   - `split_applied`: 양면 분리 적용 여부 (로깅 유용)
3. **단순성**: `success`, `pdf_path`, `force_split_applied` 제거
   - 현재 프로젝트에서 사용하지 않는 필드 제거
   - 불필요한 복잡도 감소

### 구현 시 주의사항

1. **clean_output=True 기본값**:
   - `original_page`, `side`, element의 `page` 필드 제거
   - ParsingService 호환성 유지

2. **raw_text 필수**:
   - `_split_pages_by_side()`에서 각 좌/우 페이지에 `raw_text` 추가
   - 참고 파일에는 없지만 현재 프로젝트 필수

3. **total_elements 계산**:
   - `_structure_elements()` 후 elements 개수 계산
   - 양면 분리 전 elements 개수 유지 (분리 후가 아님)

4. **original_pages 계산**:
   - `api_response.get("usage", {}).get("pages", 0)` 사용
   - Upstage API 응답의 원본 페이지 수

## 검증 체크리스트

- [ ] `ParsingService` 호환성 확인
  - [ ] `parsed_data.get("pages", [])` 정상 작동
  - [ ] `page_data.get("page_number")` 정상 작동
  - [ ] `page_data.get("raw_text")` 정상 작동
  - [ ] `page_data.get("elements", [])` 정상 작동
  - [ ] `parsed_data.get("total_pages", 0)` 정상 작동
- [ ] `StructureService` 호환성 확인
  - [ ] `parsed_data.get("total_pages", 0)` 정상 작동
  - [ ] `parsed_data.get("pages", [])` 정상 작동
- [ ] `StructureBuilder` 호환성 확인
  - [ ] `parsed_data.get("total_pages", 0)` 정상 작동
  - [ ] `parsed_data.get("pages", [])` 정상 작동
- [ ] 양면 분리 후 페이지 번호 검증
  - [ ] 원본 2페이지 → 분리 후 4페이지 확인
  - [ ] `page_number`가 1, 2, 3, 4로 순차적으로 증가하는지 확인
- [ ] clean_output 검증
  - [ ] `original_page` 필드 제거 확인
  - [ ] `side` 필드 제거 확인
  - [ ] element의 `page` 필드 제거 확인

