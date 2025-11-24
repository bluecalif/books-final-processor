# 테스트 파일 정리 계획 (Phase 2 기준)

## Phase 2에 필요한 파일

### ✅ 유지할 파일
1. **`test_e2e_pdf_parsing.py`** - PDF 파싱 E2E 테스트 (Phase 2 핵심)
2. **`conftest_e2e.py`** - E2E 테스트 fixture (실제 서버 실행)
3. **`conftest.py`** - 일반 fixture (확인 필요, E2E 테스트에서 사용 안 함)

## 삭제할 파일

### Phase 3 관련 (구조 분석)
1. **`test_e2e_structure_analysis.py`** - 구조 분석 E2E 테스트 (Phase 3)
2. **`test_e2e_structure_analysis_with_output.py`** - 구조 분석 E2E 테스트 (결과 저장, Phase 3)

### 단위 테스트 (E2E 테스트만 사용하므로 불필요)
3. **`test_pdf_parser.py`** - PDFParser 단위 테스트
4. **`test_upstage_api_client.py`** - UpstageAPIClient 단위 테스트
5. **`test_books_router.py`** - Books API 통합 테스트
6. **`test_models.py`** - 데이터 모델 테스트
7. **`test_main.py`** - FastAPI 앱 기본 테스트

## conftest.py 확인

`test_e2e_pdf_parsing.py`는 `e2e_client` fixture만 사용하며, 이는 `conftest_e2e.py`에서 제공됩니다.
`conftest.py`는 `TestClient` 기반 fixture를 제공하지만, E2E 테스트에서는 사용하지 않습니다.

**결론**: `conftest.py`도 삭제 가능 (E2E 테스트만 사용하므로)

## 최종 정리 후 파일 목록

```
backend/tests/
├── __init__.py
├── conftest_e2e.py          # E2E 테스트 fixture
└── test_e2e_pdf_parsing.py  # PDF 파싱 E2E 테스트
```

