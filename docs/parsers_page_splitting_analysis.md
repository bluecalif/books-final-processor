# parsers/ 디렉토리 양면 분리 로직 분석

## 현재 구현 상태

### 파일 구조
```
backend/parsers/
├── __init__.py
├── upstage_api_client.py    # Upstage API 클라이언트
├── pdf_parser.py            # PDF 파서 (현재 구현)
└── cache_manager.py         # 캐시 매니저
```

### 현재 데이터 흐름

#### 1. UpstageAPIClient (`upstage_api_client.py`)

**역할**: Upstage API 호출 및 100페이지 분할 파싱

**메서드**:
- `parse_pdf(pdf_path, retries=3)`: 메인 파싱 메서드
- `_split_pdf(pdf_path, start_page, end_page, output_path)`: **PDF 파일 분할** (100페이지 초과 시 사용)
  - ⚠️ **주의**: 이것은 "양면 분리"가 아니라 "100페이지 분할 파싱"을 위한 것
  - PDF 파일 자체를 페이지 범위로 분할하여 API 호출
- `_parse_pdf_in_chunks()`: 100페이지씩 분할하여 파싱

**반환 형식**:
```python
{
    "api": "2.0",
    "model": "document-parse-250618",
    "usage": {"pages": total_pages},
    "elements": [
        {
            "id": 0,
            "page": 1,  # 원본 PDF 페이지 번호
            "category": "paragraph",
            "coordinates": [{"x": 0.1, "y": 0.2}, ...],
            "content": {"html": "<p>...</p>", ...}
        },
        ...
    ],
    "metadata": {
        "split_parsing": True/False,  # 100페이지 분할 여부
        "total_chunks": N
    }
}
```

#### 2. PDFParser (`pdf_parser.py`)

**역할**: API 응답을 구조화하고 페이지별로 그룹화

**현재 플로우**:
```
1. 캐시 확인
   ↓
2. API 호출 (캐시 미스 시)
   ↓
3. _structure_elements() → 구조화된 elements
   ↓
4. _group_by_page() → 페이지별 그룹화
   ↓
5. 반환
```

**현재 메서드**:
- `parse_pdf(file_path, use_cache=True)`: 메인 파싱 메서드
- `_structure_elements(api_response)`: API 응답 elements 구조화
  - HTML에서 텍스트 추출
  - Font size 추출
  - Bbox 계산
- `_group_by_page(elements)`: Elements를 페이지별로 그룹화
  - ⚠️ **양면 분리 없음**: 원본 페이지 번호 그대로 그룹화
  - 각 페이지의 `raw_text` 추출

**현재 반환 형식**:
```python
{
    "pages": [
        {
            "page_number": 1,  # 원본 PDF 페이지 번호 (양면 분리 없음)
            "elements": [...],
            "raw_text": "..."  # 전체 페이지 텍스트
        }
    ],
    "total_pages": N,
    "total_elements": N,
    "metadata": {...}
}
```

### 양면 분리 로직 상태

**현재 구현**: ❌ **없음**

**참고 파일에 있는 로직**:
- `_split_pages_by_side(elements, force_split)`: 양면 분리 로직
- `_clean_pages(pages)`: 불필요한 필드 제거

## 참고 파일의 데이터 흐름

### pdf_parser_REF.py 플로우

```
1. 캐시 확인
   ↓
2. API 호출 (캐시 미스 시)
   ↓
3. _structure_elements() → 구조화된 elements
   ↓
4. _split_pages_by_side() → 양면 분리
   - 원본 페이지를 좌/우로 분리
   - 상대좌표 기준 0.5 고정 중앙선
   - x < 0.5: 좌측, x >= 0.5: 우측
   ↓
5. _clean_pages() → 불필요한 필드 제거 (clean_output=True일 때)
   - original_page 제거
   - side 제거
   - element의 page 필드 제거
   ↓
6. 반환
```

**참고 파일 반환 형식** (clean_output=True일 때):
```python
{
    "success": True,
    "pages": [
        {
            "page_number": 1,  # 분리 후 페이지 번호 (1, 2, 3, ...)
            "elements": [...],  # 좌측 또는 우측 elements만
            "raw_text": "..."   # 좌측 또는 우측 텍스트만
            # original_page, side는 제거됨
        }
    ],
    "total_pages": 4,  # 분리 후 페이지 수 (원본 2페이지 → 4페이지)
    "original_pages": 2,  # 원본 페이지 수
    "split_applied": True,
    "metadata": {...}
}
```

## 현재 vs 참고 파일 비교

### 차이점

| 항목 | 현재 구현 | 참고 파일 |
|------|----------|----------|
| 양면 분리 | ❌ 없음 | ✅ 있음 (`_split_pages_by_side()`) |
| clean_output | ❌ 없음 | ✅ 있음 (`_clean_pages()`) |
| 반환 형식 | 단순 (pages, total_pages) | 상세 (original_pages, split_applied 등) |
| 페이지 번호 | 원본 페이지 번호 그대로 | 분리 후 새로 매김 (1, 2, 3, ...) |

### 데이터 전달 경로

**현재**:
```
UpstageAPIClient.parse_pdf()
  → api_response (elements 포함)
  → PDFParser._structure_elements()
  → structured_elements (bbox 포함)
  → PDFParser._group_by_page()
  → pages (양면 분리 없음)
  → 반환
```

**참고 파일**:
```
UpstageAPIClient.parse_pdf()
  → api_response (elements 포함)
  → PDFParser._structure_elements()
  → structured_elements (bbox 포함)
  → PDFParser._split_pages_by_side()  ← 양면 분리 추가
  → pages (좌/우 분리됨)
  → PDFParser._clean_pages()  ← clean_output 처리
  → pages (필드 정리됨)
  → 반환
```

## 구현 필요 사항

### 1. 양면 분리 로직 추가 (`_split_pages_by_side()`)

**위치**: `backend/parsers/pdf_parser.py`

**입력**: `structured_elements` (bbox 포함)
**출력**: 분리된 pages (좌/우 각각)

**로직**:
- 상대좌표 기준 0.5 고정 중앙선
- `bbox["x0"] < 0.5`: 좌측
- `bbox["x0"] >= 0.5`: 우측
- 각 페이지에 `raw_text` 추가 (좌/우별로)

### 2. clean_output 로직 추가 (`_clean_pages()`)

**위치**: `backend/parsers/pdf_parser.py`

**입력**: 분리된 pages
**출력**: 정리된 pages

**처리**:
- `original_page` 제거
- `side` 제거
- element의 `page` 필드 제거

### 3. 플로우 수정

**현재**:
```python
structured_elements = self._structure_elements(api_response)
pages = self._group_by_page(structured_elements)  # 양면 분리 없음
```

**변경 후**:
```python
structured_elements = self._structure_elements(api_response)
pages = self._split_pages_by_side(structured_elements, force_split=True)  # 양면 분리
if self.clean_output:
    pages = self._clean_pages(pages)  # 필드 정리
```

## 호환성 고려사항

### ParsingService 호환성

**ParsingService에서 사용하는 필드**:
- `page_data.get("page_number")` - ✅ 필요
- `page_data.get("raw_text")` - ✅ 필요
- `page_data.get("elements")` - ✅ 필요

**양면 분리 후**:
- `page_number`: 분리 후 새로 매김 (1, 2, 3, ...) ✅
- `raw_text`: 좌/우별로 분리된 텍스트 ✅
- `elements`: 좌/우별로 분리된 elements ✅

**결론**: `clean_output=True` (기본값)일 때 호환성 유지됨

## 참고 파일의 _split_pages_by_side() 분석

**참고 파일의 반환 형식**:
```python
{
    "page_number": 1,
    "original_page": 1,
    "side": "left",
    "elements": [...],
    "metadata": {...}
    # raw_text 없음
}
```

**현재 프로젝트 요구사항**:
- ParsingService가 `raw_text` 필드를 필요로 함
- 따라서 `_split_pages_by_side()`에서 `raw_text`를 추가해야 함

**수정 필요**:
- 참고 파일의 `_split_pages_by_side()`를 기반으로 하되, `raw_text` 추가 필요
- 각 좌/우 페이지의 elements에서 텍스트를 추출하여 `raw_text` 생성

## 최종 구현 계획

### 데이터 흐름 (수정 후)

```
1. 캐시 확인
   ↓
2. API 호출 (캐시 미스 시)
   ↓
3. _structure_elements() → structured_elements (bbox 포함)
   ↓
4. _split_pages_by_side() → 양면 분리
   - 원본 페이지를 좌/우로 분리
   - 각 좌/우 페이지에 raw_text 추가 (현재 프로젝트 요구사항)
   ↓
5. _clean_pages() → 불필요한 필드 제거 (clean_output=True일 때)
   - original_page 제거
   - side 제거
   - element의 page 필드 제거
   ↓
6. 반환
```

### _split_pages_by_side() 수정 사항

**참고 파일 기반 + raw_text 추가**:
```python
# 좌측 페이지
if left_elements:
    result_pages.append({
        "page_number": page_counter,
        "original_page": original_page,
        "side": "left",
        "elements": sorted(left_elements, ...),
        "raw_text": " ".join([e.get("text", "") for e in left_elements]),  # 추가
        "metadata": {...}
    })

# 우측 페이지
if right_elements:
    result_pages.append({
        "page_number": page_counter,
        "original_page": original_page,
        "side": "right",
        "elements": sorted(right_elements, ...),
        "raw_text": " ".join([e.get("text", "") for e in right_elements]),  # 추가
        "metadata": {...}
    })
```

## 요약

1. **현재 상태**: 양면 분리 로직 없음
2. **필요 작업**: 
   - `_split_pages_by_side()` 추가 (참고 파일 기반 + raw_text 추가)
   - `_clean_pages()` 추가 (참고 파일 기반)
3. **데이터 흐름**: 구조화 → 양면 분리 → clean_output → 반환
4. **호환성**: `clean_output=True` 기본값으로 유지, `raw_text` 추가로 ParsingService 호환
5. **기본 동작**: `force_split=True` 기본값으로 항상 양면 분리 실행

