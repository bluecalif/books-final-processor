# parsers/ 디렉토리 캐싱 시스템 분석

## 개요

parsers/ 디렉토리 내에서 Upstage API 파싱 결과를 캐싱하여 비용을 절감하고 성능을 향상시킵니다.

## 파일 구조

```
backend/parsers/
├── __init__.py              # 모듈 export
├── cache_manager.py         # 캐싱 로직 (캐시 저장/조회)
├── pdf_parser.py            # PDF 파서 (캐싱 통합)
└── upstage_api_client.py    # Upstage API 클라이언트 (캐싱 없음)
```

## 캐싱 관련 파일

### 1. CacheManager (`cache_manager.py`)

**역할**: Upstage API 응답의 캐시 저장 및 조회

**주요 메서드**:
- `get_file_hash(pdf_path)`: PDF 파일 내용 MD5 해시 생성
- `get_cache_key(pdf_path)`: 캐시 키 생성 (파일 해시)
- `get_cache_path(cache_key)`: 캐시 파일 경로 생성
- `get_cached_result(pdf_path)`: 캐시된 결과 조회
- `save_cache(pdf_path, result)`: 결과를 캐시에 저장

**캐시 디렉토리**:
- 기본 경로: `settings.cache_dir / "upstage"`
- 예시: `data/cache/upstage/`
- 파일명 형식: `{md5_hash}.json`

### 2. PDFParser (`pdf_parser.py`)

**역할**: PDF 파싱 및 캐싱 통합

**캐싱 통합**:
- `__init__()`: `CacheManager()` 초기화
- `parse_pdf()`: 캐시 확인 → API 호출 → 캐시 저장

### 3. UpstageAPIClient (`upstage_api_client.py`)

**역할**: Upstage API 직접 호출

**캐싱**: ❌ **캐싱 없음** (API 호출만 담당)

## 캐싱 플로우

### 전체 플로우 다이어그램

```
[ParsingService]
    ↓
[PDFParser.parse_pdf(file_path, use_cache=True)]
    ↓
┌─────────────────────────────────────────┐
│ 1. 캐시 확인                            │
│    cache_manager.get_cached_result()    │
└─────────────────────────────────────────┘
    ↓
    ├─ 캐시 히트 ──────────────────────────┐
    │                                       │
    │  [CacheManager.get_cached_result()]  │
    │    ↓                                  │
    │  [파일 해시 생성]                      │
    │    get_file_hash(pdf_path)           │
    │    → MD5 해시                         │
    │    ↓                                  │
    │  [캐시 키 생성]                        │
    │    get_cache_key(pdf_path)           │
    │    → {hash}.json 경로                 │
    │    ↓                                  │
    │  [캐시 파일 확인]                      │
    │    is_cache_valid()                  │
    │    → cache_file.exists()             │
    │    ↓                                  │
    │  [캐시 파일 로드]                      │
    │    json.load(cache_file)              │
    │    → Upstage API 원본 응답            │
    │    ↓                                  │
    │  [메타데이터 제거]                     │
    │    cached_data.pop("_cache_meta")    │
    │    ↓                                  │
    │  [원본 API 응답 반환]                  │
    │    return cached_data                 │
    │                                       │
    └───────────────────────────────────────┘
    ↓
    [캐시된 API 응답]
    ↓
    [PDFParser._structure_elements()]
    → 구조화된 elements
    ↓
    [PDFParser._group_by_page()]
    → 페이지별 그룹화
    ↓
    [반환]

    ├─ 캐시 미스 ──────────────────────────┐
    │                                       │
    │  [UpstageAPIClient.parse_pdf()]      │
    │    ↓                                  │
    │  [Upstage API 호출]                   │
    │    → 원본 API 응답                    │
    │    ↓                                  │
    │  [PDFParser._structure_elements()]    │
    │    → 구조화된 elements                │
    │    ↓                                  │
    │  [PDFParser._group_by_page()]         │
    │    → 페이지별 그룹화                   │
    │    ↓                                  │
    │  [결과 반환 준비]                      │
    │    ↓                                  │
    │  [캐시 저장]                          │
    │    cache_manager.save_cache()         │
    │    ↓                                  │
    │  [API 응답 검증]                       │
    │    → elements 또는 api 필드 확인       │
    │    ↓                                  │
    │  [캐시 메타데이터 추가]                │
    │    _cache_meta = {                   │
    │      "file_hash": ...,                │
    │      "file_size": ...,                │
    │      "file_mtime": ...,               │
    │      "cached_at": ...,                │
    │      "pdf_path": ...                  │
    │    }                                  │
    │    ↓                                  │
    │  [임시 파일로 저장]                   │
    │    temp_file = {hash}.json.tmp       │
    │    json.dump(result_to_cache, ...)   │
    │    ↓                                  │
    │  [원자적 이동]                         │
    │    temp_file.replace(cache_file)      │
    │    → {hash}.json                      │
    │    ↓                                  │
    │  [캐시 저장 완료]                      │
    │                                       │
    └───────────────────────────────────────┘
    ↓
    [반환]
```

## 데이터 전달 경로

### 1. 캐시 히트 시

```
PDFParser.parse_pdf(file_path, use_cache=True)
  ↓
CacheManager.get_cached_result(file_path)
  ↓
CacheManager.get_cache_key(file_path)
  ↓
CacheManager.get_file_hash(file_path)
  → MD5 해시 (예: "a1b2c3d4e5f6...")
  ↓
CacheManager.get_cache_path(cache_key)
  → Path("data/cache/upstage/a1b2c3d4e5f6....json")
  ↓
CacheManager.is_cache_valid()
  → cache_file.exists() 확인
  ↓
json.load(cache_file)
  → {
      "api": "2.0",
      "model": "document-parse-250618",
      "usage": {"pages": 100},
      "elements": [...],
      "metadata": {...},
      "_cache_meta": {...}  # 제거됨
    }
  ↓
cached_data.pop("_cache_meta", None)
  → 원본 API 응답만 반환
  ↓
PDFParser._structure_elements(cached_result)
  → 구조화된 elements
  ↓
PDFParser._group_by_page(structured_elements)
  → 페이지별 그룹화
  ↓
반환
```

### 2. 캐시 미스 시

```
PDFParser.parse_pdf(file_path, use_cache=True)
  ↓
UpstageAPIClient.parse_pdf(file_path)
  ↓
Upstage API 호출
  → {
      "api": "2.0",
      "model": "document-parse-250618",
      "usage": {"pages": 100},
      "elements": [...],
      "metadata": {...}
    }
  ↓
PDFParser._structure_elements(api_response)
  → 구조화된 elements
  ↓
PDFParser._group_by_page(structured_elements)
  → 페이지별 그룹화
  ↓
CacheManager.save_cache(file_path, api_response)
  ↓
CacheManager.get_cache_key(file_path)
  → MD5 해시
  ↓
CacheManager.get_cache_path(cache_key)
  → Path("data/cache/upstage/{hash}.json")
  ↓
캐시 메타데이터 추가
  result_to_cache = {
    ...api_response,
    "_cache_meta": {
      "file_hash": "...",
      "file_size": ...,
      "file_mtime": ...,
      "cached_at": ...,
      "pdf_path": "..."
    }
  }
  ↓
임시 파일로 저장
  temp_file = "{hash}.json.tmp"
  json.dump(result_to_cache, temp_file)
  ↓
원자적 이동
  temp_file.replace(cache_file)
  → "{hash}.json"
  ↓
반환
```

## 캐시 저장 형식

### 저장되는 데이터

**파일 경로**: `data/cache/upstage/{md5_hash}.json`

**저장 형식**:
```json
{
  "api": "2.0",
  "model": "document-parse-250618",
  "usage": {
    "pages": 100
  },
  "elements": [
    {
      "id": 0,
      "page": 1,
      "category": "paragraph",
      "coordinates": [{"x": 0.1, "y": 0.2}, ...],
      "content": {
        "html": "<p>...</p>",
        "markdown": "",
        "text": ""
      }
    },
    ...
  ],
  "metadata": {
    "split_parsing": false,
    "total_chunks": 1
  },
  "_cache_meta": {
    "file_hash": "a1b2c3d4e5f6...",
    "file_size": 1234567,
    "file_mtime": 1234567890.123,
    "cached_at": 1234567890.456,
    "pdf_path": "/path/to/file.pdf"
  }
}
```

### 캐시 키 생성 방식

**방식**: 파일 내용 MD5 해시

**특징**:
- 파일 내용이 동일하면 경로가 달라도 같은 캐시 키
- 파일 내용이 변경되면 다른 캐시 키
- 파일명/경로 변경 시에도 캐시 재사용 가능

**예시**:
```python
# 같은 PDF 파일 (내용 동일)
file1 = "data/input/book1.pdf"
file2 = "data/input/book1_renamed.pdf"  # 이름만 변경

# 같은 캐시 키 생성
hash1 = CacheManager().get_file_hash(file1)  # "a1b2c3d4..."
hash2 = CacheManager().get_file_hash(file2)  # "a1b2c3d4..." (동일)

# 같은 캐시 파일 사용
cache_file = "data/cache/upstage/a1b2c3d4....json"
```

## 캐시 저장 프로세스

### 1. 검증 단계

```python
# CacheManager.save_cache() 내부
has_elements = result.get("elements") is not None
has_api = bool(result.get("api"))

if not (has_elements or has_api):
    # Upstage API 응답이 아님 → 저장하지 않음
    return
```

### 2. 메타데이터 생성

```python
stat = os.stat(pdf_path)
file_hash = self.get_file_hash(pdf_path)
cache_meta = {
    "file_hash": file_hash,
    "file_size": stat.st_size,
    "file_mtime": stat.st_mtime,
    "cached_at": time.time(),
    "pdf_path": str(pdf_path)
}
```

### 3. 임시 파일 저장

```python
result_to_cache = result.copy()
result_to_cache["_cache_meta"] = cache_meta

temp_file = cache_file.with_suffix('.tmp')
with open(temp_file, 'w', encoding='utf-8') as f:
    json.dump(result_to_cache, f, ensure_ascii=False, indent=2)
```

### 4. 원자적 이동

```python
# 임시 파일을 최종 파일로 원자적 이동
temp_file.replace(cache_file)
```

**이유**: 파일 쓰기 중 오류 발생 시 기존 캐시 파일 손상 방지

## 캐시 조회 프로세스

### 1. 캐시 키 생성

```python
cache_key = self.get_cache_key(pdf_path)
# → MD5 해시
```

### 2. 캐시 파일 확인

```python
cache_file = self.get_cache_path(cache_key)
# → Path("data/cache/upstage/{hash}.json")

if not cache_file.exists():
    return None  # 캐시 미스
```

### 3. 캐시 파일 로드

```python
with open(cache_file, 'r', encoding='utf-8') as f:
    cached_data = json.load(f)
```

### 4. 메타데이터 제거

```python
cached_data.pop("_cache_meta", None)
# → 원본 API 응답만 반환
```

## 파일 간 상호작용

### PDFParser → CacheManager

**호출 위치**: `PDFParser.parse_pdf()`

**호출 메서드**:
1. `cache_manager.get_cached_result(file_path)`
   - 캐시 확인 및 조회
   - 반환: `Optional[Dict[str, Any]]` (Upstage API 원본 응답)

2. `cache_manager.save_cache(file_path, api_response)`
   - 캐시 저장
   - 입력: `api_response` (Upstage API 원본 응답)

### CacheManager → 파일 시스템

**작업**:
1. 캐시 파일 읽기: `json.load(cache_file)`
2. 캐시 파일 쓰기: `json.dump(result_to_cache, temp_file)`
3. 원자적 이동: `temp_file.replace(cache_file)`

### UpstageAPIClient → PDFParser

**호출 위치**: `PDFParser.parse_pdf()` (캐시 미스 시)

**호출 메서드**:
- `api_client.parse_pdf(file_path)`
- 반환: Upstage API 원본 응답

**캐싱**: ❌ UpstageAPIClient는 캐싱과 무관 (API 호출만 담당)

## 캐시 저장 위치

### 디렉토리 구조

```
data/
└── cache/
    └── upstage/
        ├── a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6.json
        ├── b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7.json
        └── ...
```

### 설정

**기본 경로**: `settings.cache_dir / "upstage"`

**설정 파일**: `backend/config/settings.py`
```python
cache_dir: Path = Path("data/cache")
```

**실제 경로**: `data/cache/upstage/`

## 캐시 재사용 로직

### 파일 내용 기반 캐시 키

**핵심**: 파일 내용이 동일하면 경로가 달라도 같은 캐시 키

**예시 시나리오**:
1. 사용자가 `book.pdf` 업로드
   - 파일 해시: `abc123...`
   - 캐시 저장: `data/cache/upstage/abc123....json`

2. 사용자가 같은 파일을 `book_renamed.pdf`로 다시 업로드
   - 파일 해시: `abc123...` (동일)
   - 캐시 조회: `data/cache/upstage/abc123....json` (재사용)

3. 사용자가 수정된 파일을 업로드
   - 파일 해시: `def456...` (다름)
   - 캐시 미스: 새로 API 호출

## 에러 처리

### 캐시 저장 실패

**위치**: `CacheManager.save_cache()`

**처리**:
```python
try:
    # 캐시 저장 로직
    ...
except Exception as e:
    logger.error(f"[ERROR] Failed to cache result: {e}")
    logger.warning(f"[WARNING] Cache save failed, but parsing will continue")
    # 예외를 다시 발생시키지 않음
    # 캐시 저장 실패가 전체 파싱을 막지 않도록
```

**이유**: 캐시는 비용 절감을 위한 최적화이므로, 실패해도 파싱은 계속 진행

### 캐시 조회 실패

**위치**: `CacheManager.get_cached_result()`

**처리**:
```python
try:
    # 캐시 조회 로직
    ...
except Exception as e:
    logger.warning(f"[WARNING] Failed to retrieve cache: {e}")
    return None  # 캐시 미스로 처리
```

**이유**: 손상된 캐시 파일이 있더라도 파싱은 계속 진행 (API 재호출)

## 요약

### 캐싱 플로우

1. **PDFParser.parse_pdf()** 호출
2. **CacheManager.get_cached_result()** → 캐시 확인
3. **캐시 히트**: 캐시된 API 응답 반환 → 구조화 → 반환
4. **캐시 미스**: UpstageAPIClient 호출 → API 응답 → 구조화 → **CacheManager.save_cache()** → 반환

### 저장되는 데이터

- **저장 위치**: `data/cache/upstage/{md5_hash}.json`
- **저장 내용**: Upstage API 원본 응답 + 캐시 메타데이터
- **캐시 키**: 파일 내용 MD5 해시 (경로 무관)

### 파일 간 관계

- **PDFParser**: 캐싱 통합 (CacheManager 사용)
- **CacheManager**: 캐시 저장/조회 담당
- **UpstageAPIClient**: 캐싱 없음 (API 호출만)

### 특징

- 파일 내용 기반 캐시 키 (경로 변경 시에도 재사용)
- 원자적 저장 (임시 파일 → 최종 파일 이동)
- 에러 견고성 (캐시 실패해도 파싱 계속 진행)

