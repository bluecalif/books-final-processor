# 캐시 vs DB 저장 구조 설명

## 핵심 요약

**캐시 파일**: Upstage API **원본 응답**만 저장 (10페이지)  
**DB 저장**: **양면 분리 후 결과** 저장 (20페이지)

## 데이터 흐름

### 1. 캐시 저장 단계

```
UpstageAPIClient.parse_pdf()
  ↓
원본 API 응답 (10페이지)
  ↓
CacheManager.save_cache()
  ↓
data/cache/upstage/{hash}.json
  (원본 10페이지 그대로 저장)
```

**캐시 파일 내용**:
- `usage.pages`: 10 (원본 페이지 수)
- `elements`: 원본 10페이지의 elements 배열
- **양면 분리 전 원본 데이터**

### 2. 양면 분리 단계

```
PDFParser.parse_pdf()
  ↓
캐시에서 원본 응답 로드 (10페이지)
  ↓
_structure_elements() → 구조화
  ↓
_split_pages_by_side() → 양면 분리
  (10페이지 → 20페이지)
  ↓
_clean_pages() → 필드 정리
  ↓
반환: 20페이지
```

**분리 로직**:
- 원본 페이지 1개 → 좌측 1개 + 우측 1개
- 원본 10페이지 → 분리 후 20페이지

### 3. DB 저장 단계

```
ParsingService.parse_book()
  ↓
PDFParser.parse_pdf() → 20페이지 반환
  ↓
Pages 테이블에 저장
  ↓
book.page_count = 20
```

**DB 저장 내용**:
- `pages` 테이블: 20개 레코드
- `books.page_count`: 20
- 각 페이지는 분리된 좌/우 페이지

## 왜 이렇게 설계되었나?

### 캐시에 원본만 저장하는 이유

1. **재사용성**: 같은 파일을 다시 파싱할 때 원본 데이터 재사용
2. **유연성**: 양면 분리 로직을 변경해도 캐시 재사용 가능
3. **일관성**: 캐시는 외부 API 응답을 그대로 보존

### DB에 분리된 결과를 저장하는 이유

1. **실제 사용 데이터**: 애플리케이션은 분리된 페이지를 사용
2. **조회 성능**: 분리된 페이지를 바로 조회 가능
3. **상태 관리**: `page_count`는 실제 사용 가능한 페이지 수

## 검증 결과

### 캐시 파일 확인
- **파일**: `data/cache/upstage/b4821449e8376f7e8b41f800691141df.json`
- **원본 페이지 수**: 10페이지
- **Elements**: 원본 10페이지의 elements

### DB 확인
- **Book ID 10**:
  - `page_count`: 20
  - `status`: PARSED
- **Pages 테이블**: 20개 레코드 저장됨

## 결론

**정상 작동 중** ✅

- 캐시: 원본 10페이지 저장 (Upstage API 응답 그대로)
- DB: 분리된 20페이지 저장 (실제 사용 데이터)
- 양면 분리는 파싱 시점에 동적으로 수행되어 DB에 저장됨

