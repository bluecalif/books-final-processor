# 캐시 미스 문제 분석 (2025-12-03)

## 문제 요약

**핵심 의문**: 페이지 캐시가 100% 히트했는데, 왜 챕터 캐시는 3/8개만 히트했는가?

**논리적 기대**:
- 페이지 캐시 100% 히트 → 페이지 엔티티 동일
- 페이지 엔티티 동일 → 챕터 입력 동일
- 챕터 입력 동일 → **챕터 캐시도 100% 히트해야 함**

**실제 결과**: 8개 챕터 중 3개만 캐시 히트, 5개는 OpenAI API 재호출

---

## 시간대별 상세 이력

### 테스트 1: 21:19 ~ 21:22 (첫 번째 테스트)
**로그 파일**: `server_20251203_212101.log`

**컨텍스트**: 
- 병렬 처리 개선 직후 첫 테스트
- 캐시 폴더 분리 **이전** (루트 `summaries/`에 저장)

**결과**:
- 페이지 추출: 성공 (캐시는 Upstage API만, OpenAI는 신규 호출)
- 챕터 구조화: **8/8 성공** (52.5초, 평균 6.57초/챕터)
- 캐시 저장 위치: `data/cache/summaries/` (루트)

**로그 증거**:
```
[2025-12-03 21:21:27] backend.api.services.extraction_service - INFO: [TOKEN] Chapter 1: input=17142, output=3304, cost=$0.012143
[2025-12-03 21:22:17] backend.summarizers.llm_chains - INFO: [INFO] Chapter structuring completed
[2025-12-03 21:22:19] backend.api.services.extraction_service - INFO: [EXTRACTION_COMPLETE] Chapter structuring completed: success=8, failed=0, total=8 chapters, time=52.5s, avg=6.57s/chapter
```

---

### 테스트 2: 21:55 ~ 22:14 (캐시 폴더 분리 후)
**로그 파일**: `server_20251203_215458.log`

**컨텍스트**:
- Book 176 reset 후 재실행
- 캐시 폴더 분리 **이후** (`summaries/1000년/`에 저장)
- 타임아웃 60초 적용

**결과**:
- 페이지 추출: 385/388 성공 (612.4초, 평균 1.58초/페이지)
  - **OpenAI API 신규 호출** (캐시 폴더 변경으로 기존 캐시 못 찾음)
- 챕터 구조화: **7/8 성공, 1개 실패** (548초, 평균 68.5초/챕터)
  - **실패한 챕터**: Chapter 984 (order_index=0, "1000년의세계", pages 87-116)
  - **실패 원인**: APITimeoutError (60초 × 3회 재시도 = 180초 소요 후 실패)

**캐시 생성**:
- `data/cache/summaries/1000년/` 폴더 생성
- 페이지 캐시: 385개
- 챕터 캐시: **7개** (Chapter 2-8만 성공, Chapter 1 실패로 캐시 없음)

**로그 증거**:
```
[2025-12-03 22:05:23] backend.api.services.extraction_service - INFO: [EXTRACTION_COMPLETE] Page extraction completed: success=385, failed=3, total=388 pages, time=612.4s, avg=1.58s/page

[2025-12-03 22:08:34] backend.summarizers.llm_chains - WARNING: [WARNING] Chapter structuring attempt 1/3 failed: APITimeoutError: Request timed out., retrying in 1s...
[2025-12-03 22:11:36] backend.summarizers.llm_chains - WARNING: [WARNING] Chapter structuring attempt 2/3 failed: APITimeoutError: Request timed out., retrying in 2s...
[2025-12-03 22:14:40] backend.api.services.extraction_service - ERROR: [ERROR] Failed to structure chapter 984: APITimeoutError: Request timed out.
[2025-12-03 22:14:40] backend.api.services.extraction_service - INFO: [EXTRACTION_COMPLETE] Chapter structuring completed: success=7, failed=1, total=8 chapters, time=548.0s, avg=68.50s/chapter
```

**생성된 챕터 캐시 (7개)**:
```
data/cache/summaries/1000년/
├── chapter_760f8927e15ab00a3f05b3c76ba91570.json  # Chapter ?
├── chapter_a314ac0c7b7fa23ed919ad451a9c2b50.json  # Chapter ?
├── chapter_a6c07f91a2ed92d47305e5c6204f0a29.json  # Chapter ?
├── chapter_aa63106690f414f3461fdfc41bd503da.json  # Chapter ?
├── chapter_d39e0aeaf1a71b9cfb0625b2d0ea83dd.json  # Chapter ?
├── chapter_ed596fe4349ebe0b02398941ea382459.json  # Chapter ?
├── chapter_45386e4f91e010d3b65af267ff278311.json  # Chapter ?
```

---

### 테스트 3: 22:27 ~ 22:29 (타임아웃 120s 적용)
**로그 파일**: `server_20251203_222743.log`

**컨텍스트**:
- Book 176 reset 후 재실행
- 타임아웃 120초로 증가
- 토큰 통계 병합 저장 로직 적용

**결과**:
- 페이지 추출: 373/388 성공 (2.9초, 평균 0.01초/페이지)
  - **페이지 캐시 100% 히트** ✅
- 챕터 구조화: **8/8 성공** (76.2초, 평균 9.52초/챕터)
  - **캐시 히트**: 3개 (760f8927, a6c07f91, a314ac0c)
  - **OpenAI API 호출**: 5개

**로그 증거**:
```
[2025-12-03 22:28:10] backend.api.services.extraction_service - INFO: [EXTRACTION_COMPLETE] Page extraction completed: success=373, failed=15, total=388 pages, time=2.9s, avg=0.01s/page

[2025-12-03 22:28:21] backend.summarizers.chapter_structurer - INFO: [INFO] Cache hit for chapter structuring (hash: 760f8927...)
[2025-12-03 22:29:08] backend.summarizers.chapter_structurer - INFO: [INFO] Cache hit for chapter structuring (hash: a6c07f91...)
[2025-12-03 22:29:08] backend.summarizers.chapter_structurer - INFO: [INFO] Cache hit for chapter structuring (hash: a314ac0c...)

[2025-12-03 22:29:08] backend.summarizers.llm_chains - INFO: [INFO] Chapter structuring completed  (5개 OpenAI 호출)
[2025-12-03 22:29:37] backend.api.services.extraction_service - INFO: [EXTRACTION_COMPLETE] Chapter structuring completed: success=8, failed=0, total=8 chapters, time=76.2s, avg=9.52s/chapter
```

---

## 문제 분석

### 페이지 캐시 확인

**캐시 폴더**: `data/cache/summaries/1000년/`
- 페이지 캐시: ~385개 파일
- 생성 시간: 21:55 ~ 22:05 (테스트 2)

**22:27 테스트 페이지 추출**:
- 총 시간: 2.9초
- 평균: 0.01초/페이지
- **결론**: 페이지 캐시 100% 히트 확실 ✅

### 챕터 캐시 확인

**캐시 파일**: `data/cache/summaries/1000년/` 에 7개 chapter 캐시
- 생성 시간: 22:06 ~ 22:14 (테스트 2)
- Chapter 1(984) 캐시 없음 (타임아웃 실패)

**22:27 테스트 챕터 구조화**:
- 캐시 히트: 3개
- OpenAI API 호출: 5개
- **의문**: 페이지 엔티티가 동일하다면 챕터 입력도 동일해야 하는데?

---

## 가설

### 가설 1: 페이지 캐시가 실제로는 100% 히트가 아니었을 가능성
- 일부 페이지만 캐시 미스 → 해당 페이지가 포함된 챕터의 캐시 키 변경

### 가설 2: 챕터 캐시 키 생성 로직에 추가 변수가 있을 가능성
- `book_context`의 다른 필드가 변경되었을 가능성
- 예: `book_summary` 필드 등

### 가설 3: 캐시 파일 자체의 문제
- 7개 캐시 파일 중 일부가 손상되었거나 읽기 실패

### 가설 4: 페이지 순서 또는 필터링 차이
- 테스트 2: 385 페이지 성공
- 테스트 3: 373 페이지 성공
- **차이**: 12페이지 차이 발생 → 일부 챕터의 입력이 달라짐

---

## 검증 필요 사항

1. **페이지 추출 상세 로그 분석**:
   - 테스트 2와 테스트 3에서 추출된 페이지 번호가 동일한지
   - `success=385` vs `success=373` 차이 원인

2. **챕터별 캐시 히트/미스 매핑**:
   - 캐시 히트 3개 챕터가 어떤 챕터인지 (order_index)
   - API 호출 5개 챕터가 어떤 챕터인지

3. **캐시 키 생성 로직 재확인**:
   - `_compress_page_entities()` 결과가 페이지 순서에 영향을 받는지
   - `book_context`의 모든 필드 확인

4. **캐시 파일 내용 확인**:
   - 7개 캐시 파일이 정상적으로 저장되었는지
   - cached_at 타임스탬프 확인

---

## 다음 세션 작업

1. **가설 4 검증**: 페이지 수 차이(385 vs 373) 원인 파악
2. **챕터별 매핑**: 어떤 챕터가 캐시 히트/미스인지 로그에서 추출
3. **캐시 키 디버깅**: 캐시 키 생성 과정을 상세 로깅하여 차이점 파악
4. **해결 방안 수립**: 문제 원인에 따른 해결 방법 적용

---

## 참고 정보

### Book 176 정보
- **ID**: 176
- **제목**: 1000년
- **분야**: 역사/사회
- **챕터 수**: 8개
- **페이지 범위**: 87-474 (본문)

### 챕터 목록
```
Chapter 984: order=0, "1000년의세계", pages 87-116 (30 pages)
Chapter 985: order=1, "가자서쪽으로젊은바이킹들이여", pages 117-168
Chapter 986: order=2, "유럽의노예들", pages 169-226
Chapter 987: order=3, "세계최고의자", pages 227-284
Chapter 988: order=4, "1000년의팬아메리칸하이웨이", pages 285-340
Chapter 989: order=5, "둘로갈라진중앙아시아", pages 341-396
Chapter 990: order=6, "놀라운항해", pages 397-424
Chapter 991: order=7, "지상에서가세계화된지역", pages 425-474
```

### 캐시 시스템 구조

#### 페이지 캐시
- **캐시 키**: `hash(page_text)` (원문 텍스트의 MD5)
- **캐시 값**: 추출된 페이지 엔티티 (JSON)
- **위치**: `data/cache/summaries/1000년/page_{hash}.json`

#### 챕터 캐시
- **캐시 키**: `hash(compressed_page_entities + book_context)`
- **캐시 값**: 구조화된 챕터 데이터 (JSON)
- **위치**: `data/cache/summaries/1000년/chapter_{hash}.json`
- **book_context 구조**:
  ```python
  {
    "book_title": "1000년",
    "chapter_title": "...",
    "chapter_number": 1,
    "book_summary": ""  # 현재 빈 문자열
  }
  ```

### 로그 파일 위치
- `data/test_results/server_20251203_212101.log` (테스트 1)
- `data/test_results/server_20251203_215458.log` (테스트 2)
- `data/test_results/server_20251203_222743.log` (테스트 3)

### 캐시 파일 위치
- **페이지**: `data/cache/summaries/1000년/page_*.json` (385개)
- **챕터**: `data/cache/summaries/1000년/chapter_*.json` (7개)

### 코드 참조
- 페이지 추출: `backend/summarizers/page_extractor.py`
- 챕터 구조화: `backend/summarizers/chapter_structurer.py`
- 캐시 매니저: `backend/summarizers/summary_cache_manager.py`
- 추출 서비스: `backend/api/services/extraction_service.py`

---

## 추가 조사 필요

1. **테스트 2와 테스트 3의 페이지 성공 개수 차이**:
   - 테스트 2: 385/388 성공
   - 테스트 3: 373/388 성공
   - **12페이지 차이** 발생 원인?

2. **캐시 히트 3개 챕터 식별**:
   - 760f8927, a6c07f91, a314ac0c가 어떤 챕터인지
   - 캐시 파일 내용 확인으로 chapter_number 추출

3. **캐시 키 재현**:
   - 동일한 입력으로 캐시 키를 재생성하여 일치 여부 확인
   - `_compress_page_entities()` 결과의 deterministic 여부 검증

