# Phase 2 검증 체크리스트

## 완료 상태 확인

### 2.1 참고 파일 추가 및 분석
- [x] `docs/reference_code/parsers/` 디렉토리 생성 ✅
- [x] 참고 파일 추가 (`_REF` 접미사) ✅
  - `upstage_api_client_REF.py` ✅
  - `pdf_parser_REF.py` ✅
  - `cache_manager_REF.py` ✅
- [x] `ALIGN_PLAN.md` 작성 ✅
- [ ] **Git 커밋**: 확인 필요

### 2.2 UpstageAPIClient 재구현
- [x] `backend/parsers/upstage_api_client.py` 재구현 ✅
- [x] `pypdf` 사용 확인 ✅
- [x] 이모지 제거 확인 ✅
- [x] 로깅 형식 `[INFO]`, `[ERROR]` 확인 ✅
- [x] 설정 관리 `Settings` 클래스 사용 ✅
- [ ] **단계별 검증**: 기본 기능 동작 확인 필요
- [ ] **Git 커밋**: 확인 필요

### 2.3 CacheManager 재구현
- [x] `backend/parsers/cache_manager.py` 재구현 ✅
- [x] 로깅 형식 `[INFO]`, `[ERROR]`, `[CACHE_SAVE]` 확인 ✅
- [x] 캐시 디렉토리 `settings.cache_dir / "upstage"` 사용 ✅
- [x] 안전한 저장 (임시 파일 → 원자적 이동) ✅
- [x] 예외 처리 (캐시 저장 실패해도 파싱 계속 진행) ✅
- [ ] **단계별 검증**: 캐시 저장/로드 동작 확인 필요
- [ ] **Git 커밋**: 확인 필요

### 2.4 PDFParser 재구현
- [x] `backend/parsers/pdf_parser.py` 재구현 ✅
- [x] 양면 분리 로직 `_split_pages_by_side()` 구현 ✅
- [x] clean_output 로직 `_clean_pages()` 구현 ✅
- [x] 캐싱 시스템 통합 ✅
- [x] 이모지 제거 확인 ✅
- [x] 로깅 형식 `[INFO]`, `[ERROR]` 확인 ✅
- [x] 설정 관리 `Settings` 클래스 사용 ✅
- [ ] **단계별 검증**: 캐시 저장 동작 확인 필요
- [ ] **Git 커밋**: 완료 ✅

### 2.3 업로드 API 구현
- [x] 완료 ✅

## 호환성 확인

### ParsingService 호환성
- [x] `parse_pdf(use_cache=True)` 호출 확인 ✅
- [x] `force_split` 파라미터 미전달 → 기본값 `True` 사용 (문제 없음) ✅
- [x] 반환 형식 호환성 확인 필요:
  - `parsed_data.get("pages", [])` ✅
  - `parsed_data.get("total_pages", 0)` ✅
  - `page_data.get("page_number")` ✅
  - `page_data.get("raw_text")` ✅
  - `page_data.get("elements", [])` ✅
  - 새로운 필드 (`original_pages`, `split_applied`)는 사용하지 않으므로 호환 ✅

### StructureService 호환성
- [x] `parse_pdf(use_cache=True)` 호출 확인 ✅
- [x] `force_split` 파라미터 미전달 → 기본값 `True` 사용 (문제 없음) ✅
- [x] 반환 형식 호환성 확인 필요:
  - `parsed_data.get("total_pages", 0)` ✅
  - `parsed_data.get("pages", [])` ✅
  - 새로운 필드 (`original_pages`, `split_applied`)는 사용하지 않으므로 호환 ✅

## 검증 필요 작업

### 1. 단계별 검증 (E2E 테스트 전)
- [ ] UpstageAPIClient 기본 기능 동작 확인
- [ ] CacheManager 캐시 저장/로드 동작 확인
- [ ] PDFParser 캐시 저장 동작 확인
- [ ] 양면 분리 로직 동작 확인
- [ ] clean_output 로직 동작 확인

### 2. 통합 검증
- [ ] ParsingService → PDFParser 통합 확인
- [ ] StructureService → PDFParser 통합 확인
- [ ] 반환 형식 호환성 최종 확인

### 3. 코드 품질 검증
- [ ] 변수명/함수명 Align 확인
- [ ] 로깅 형식 확인 (이모지 없음)
- [ ] 설정 관리 확인 (`Settings` 클래스 사용)

