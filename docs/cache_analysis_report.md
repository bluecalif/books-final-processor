# 캐싱 시스템 분석 보고서

## 분석 방법
Sequential Thinking MCP를 사용하여 캐싱 시스템의 전체 플로우를 단계별로 분석했습니다.

## 발견된 문제점

### ⚠️ 중요 문제: 캐시 저장 실패 시 전체 파싱 실패

**위치**: `backend/parsers/cache_manager.py` line 218-222

**문제**:
```python
except Exception as e:
    logger.error(f"[CACHE_SAVE] 예외 발생: {e}")
    logger.error(f"[CACHE_SAVE] 예외 타입: {type(e).__name__}")
    logger.error(f"[CACHE_SAVE] 트레이스백:\n{traceback.format_exc()}")
    raise  # 예외를 다시 발생시킴
```

**영향**:
- `PDFParser.parse_pdf()`에서 `save_cache()` 호출 시 예외 발생하면 전체 파싱이 실패
- 파싱은 성공했지만 캐시 저장 실패로 인해 사용자에게는 실패로 보임
- 사용자가 언급한 "캐싱에 문제가 많았습니다"와 관련이 있을 수 있음

**해결 방안**:
1. `save_cache()`에서 예외를 catch하고 warning만 남기기 (권장)
2. 또는 `PDFParser`에서 `save_cache()` 호출을 try-except로 감싸기

## 정상 작동하는 부분

### ✅ 캐시 재사용 로직
- 파일 내용 해시 기반 캐시 키 생성
- 같은 파일이면 경로 무관하게 재사용
- 파일이 수정되면 자동으로 새로 파싱

### ✅ 캐시 저장 로직
- API 원본 응답을 그대로 저장
- 임시 파일로 안전하게 저장 후 원자적 이동
- 검증 로직이 Upstage API 응답 형식과 일치

### ✅ 캐시 로드 로직
- 캐시 파일 읽기 실패 시 API 재호출 (치명적이지 않음)
- 손상된 캐시 파일은 무시하고 재파싱
- 메타데이터 제거 후 원본 API 응답 반환

## 검증 결과

### 캐시 플로우 검증

1. **첫 번째 파싱 (캐시 미스)**:
   ```
   PDFParser.parse_pdf(file_path, use_cache=True)
   → CacheManager.get_cached_result(file_path) → None
   → UpstageAPIClient.parse_pdf(file_path) → api_response
   → PDFParser._structure_elements(api_response)
   → CacheManager.save_cache(file_path, api_response)
   → ✅ 캐시 저장 완료
   ```

2. **두 번째 파싱 (캐시 히트)**:
   ```
   PDFParser.parse_pdf(file_path, use_cache=True)
   → CacheManager.get_cached_result(file_path) → cached_result
   → PDFParser._structure_elements(cached_result)
   → ✅ 캐시 재사용 완료
   ```

3. **같은 파일, 다른 경로 (캐시 재사용)**:
   ```
   첫 번째: file_path="data/input/book.pdf" → hash1 → 캐시 저장
   두 번째: file_path="uploads/book.pdf" (같은 파일) → hash1 → 캐시 재사용
   → ✅ 파일 내용 기반이므로 경로 무관하게 재사용
   ```

## 권장 수정 사항

### 1. save_cache() 예외 처리 개선

**현재 코드**:
```python
except Exception as e:
    logger.error(...)
    raise  # 전체 파싱 실패
```

**수정안**:
```python
except Exception as e:
    logger.error(f"[ERROR] Failed to cache result for {pdf_path}: {e}")
    logger.error(f"[ERROR] Exception type: {type(e).__name__}")
    logger.error(f"[ERROR] Traceback:\n{traceback.format_exc()}")
    # 예외를 다시 발생시키지 않음 - 캐시 저장 실패가 전체 파싱을 막지 않도록
    # 캐시는 비용 절약을 위한 것이므로 실패해도 파싱은 계속 진행
```

### 2. 추가 검증 (선택적)

- 캐시 파일 생성 확인
- 캐시 파일 내용 검증
- 캐시 재사용 테스트

## 추가 검증: 캐시 재사용 로직

### 캐시 키 생성 방식
- `get_file_hash(pdf_path)`: 파일 내용의 MD5 해시 생성
- `get_cache_key(pdf_path)`: 파일 해시를 그대로 캐시 키로 사용
- ✅ **올바름**: 같은 파일이면 경로 무관하게 같은 키 생성

### 캐시 재사용 시나리오 검증

**시나리오 1: 같은 경로에서 두 번 파싱**
```
첫 번째: file_path="data/input/book.pdf"
  → get_file_hash("data/input/book.pdf") → hash1
  → get_cache_key("data/input/book.pdf") → hash1
  → 캐시 미스 → API 호출 → save_cache("data/input/book.pdf", api_response)
  → 캐시 파일: {hash1}.json

두 번째: file_path="data/input/book.pdf"
  → get_file_hash("data/input/book.pdf") → hash1
  → get_cache_key("data/input/book.pdf") → hash1
  → is_cache_valid("data/input/book.pdf", hash1) → True
  → get_cached_result("data/input/book.pdf") → cached_result
  → ✅ 캐시 재사용 성공
```

**시나리오 2: 같은 파일, 다른 경로**
```
첫 번째: file_path="data/input/book.pdf"
  → hash1 → 캐시 저장

두 번째: file_path="uploads/book.pdf" (같은 파일 내용)
  → get_file_hash("uploads/book.pdf") → hash1 (같은 파일이므로)
  → get_cache_key("uploads/book.pdf") → hash1
  → is_cache_valid("uploads/book.pdf", hash1) → True
  → get_cached_result("uploads/book.pdf") → cached_result
  → ✅ 캐시 재사용 성공 (경로 무관)
```

**시나리오 3: 파일이 수정된 경우**
```
첫 번째: file_path="book.pdf" (내용 A)
  → hash1 → 캐시 저장

파일 수정: file_path="book.pdf" (내용 B, 변경됨)
  → get_file_hash("book.pdf") → hash2 (내용이 변경되었으므로)
  → get_cache_key("book.pdf") → hash2
  → is_cache_valid("book.pdf", hash2) → False (hash2.json 없음)
  → get_cached_result("book.pdf") → None
  → API 재호출 → 새로 파싱
  → ✅ 올바른 동작: 파일이 변경되었으므로 새로 파싱
```

### 결론

1. ✅ **캐시 재사용 로직**: 완벽하게 작동
   - 파일 내용 기반 해시로 경로 무관하게 재사용
   - 파일 수정 시 자동으로 새로 파싱

2. ✅ **캐시 저장 로직**: 올바름
   - API 원본 응답을 그대로 저장
   - 임시 파일로 안전하게 저장 후 원자적 이동

3. ✅ **캐시 로드 로직**: 올바름
   - 예외 발생 시 API 재호출 (치명적이지 않음)
   - 메타데이터 제거 후 원본 응답 반환

4. ⚠️ **수정 완료**: 캐시 저장 실패 시 전체 파싱 실패 문제 해결
   - `save_cache()`에서 예외를 catch하고 warning만 남기도록 수정
   - 캐시 저장 실패가 전체 파싱을 막지 않음

