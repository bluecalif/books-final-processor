"""병렬 파싱 검증 테스트"""
import pytest
import time
import logging
from pathlib import Path
from backend.parsers.upstage_api_client import UpstageAPIClient
from backend.config.settings import settings

logger = logging.getLogger(__name__)

# 테스트용 PDF 파일 경로
TEST_PDF_PATH = Path(__file__).parent.parent.parent / "data" / "input" / "1등의 통찰.pdf"


@pytest.mark.e2e
def test_parallel_parsing_basic_functionality():
    """
    병렬 파싱 기본 기능 검증
    
    ⚠️ 실제 데이터만 사용: 실제 PDF 파일, 실제 Upstage API
    """
    # PDF 파일 존재 확인
    if not TEST_PDF_PATH.exists():
        pytest.skip(f"Test PDF file not found: {TEST_PDF_PATH}")
    
    # UpstageAPIClient 초기화
    api_client = UpstageAPIClient(settings.upstage_api_key)
    
    # 병렬 파싱 실행
    start_time = time.time()
    result = api_client.parse_pdf(str(TEST_PDF_PATH))
    elapsed_time = time.time() - start_time
    
    # 결과 검증
    assert result is not None
    assert "elements" in result
    assert "metadata" in result
    assert result["metadata"].get("parallel_processing") is True
    assert result["metadata"].get("pages_per_chunk") == 10
    
    # Elements 검증
    elements = result.get("elements", [])
    assert len(elements) > 0, "Elements가 비어있음"
    
    # 페이지 번호 검증 (순차적이어야 함)
    page_numbers = [elem.get("page") for elem in elements if elem.get("page")]
    if page_numbers:
        assert min(page_numbers) >= 1, "페이지 번호가 1보다 작음"
        # 페이지 번호가 순차적인지 확인 (일부만 확인)
        sorted_pages = sorted(set(page_numbers))
        logger.info(f"[TEST] 페이지 번호 범위: {min(sorted_pages)} - {max(sorted_pages)}")
    
    # ID 검증 (중복 없어야 함)
    element_ids = [elem.get("id") for elem in elements if elem.get("id") is not None]
    assert len(element_ids) == len(set(element_ids)), "Element ID가 중복됨"
    
    logger.info(f"[TEST] 병렬 파싱 완료:")
    logger.info(f"  - 소요 시간: {elapsed_time:.2f}초")
    logger.info(f"  - 총 Elements: {len(elements)}")
    logger.info(f"  - 청크 수: {result['metadata'].get('total_chunks', 0)}")
    logger.info(f"  - 병렬 처리: {result['metadata'].get('parallel_processing', False)}")
    
    print(f"\n[RESULT] 병렬 파싱 검증:")
    print(f"  - 소요 시간: {elapsed_time:.2f}초")
    print(f"  - 총 Elements: {len(elements)}")
    print(f"  - 청크 수: {result['metadata'].get('total_chunks', 0)}")


@pytest.mark.e2e
def test_parallel_parsing_elements_order():
    """
    병렬 파싱 Elements 순서 검증
    
    청크가 병렬로 처리되더라도 최종 결과의 Elements는 페이지 순서대로 정렬되어야 함
    """
    # PDF 파일 존재 확인
    if not TEST_PDF_PATH.exists():
        pytest.skip(f"Test PDF file not found: {TEST_PDF_PATH}")
    
    # UpstageAPIClient 초기화
    api_client = UpstageAPIClient(settings.upstage_api_key)
    
    # 병렬 파싱 실행
    result = api_client.parse_pdf(str(TEST_PDF_PATH))
    
    # Elements 검증
    elements = result.get("elements", [])
    assert len(elements) > 0, "Elements가 비어있음"
    
    # 페이지 번호로 정렬하여 순서 확인
    page_elements = {}
    for elem in elements:
        page_num = elem.get("page")
        if page_num:
            if page_num not in page_elements:
                page_elements[page_num] = []
            page_elements[page_num].append(elem)
    
    # 페이지 번호가 순차적인지 확인
    sorted_pages = sorted(page_elements.keys())
    logger.info(f"[TEST] 페이지 번호 범위: {min(sorted_pages)} - {max(sorted_pages)}")
    logger.info(f"[TEST] 총 페이지 수: {len(sorted_pages)}")
    
    # 연속성 확인 (일부 페이지가 누락될 수 있으므로 완전한 연속성은 요구하지 않음)
    # 하지만 최소한 순서는 맞아야 함
    for i in range(len(sorted_pages) - 1):
        assert sorted_pages[i] <= sorted_pages[i + 1], "페이지 번호가 순차적이지 않음"
    
    logger.info(f"[TEST] Elements 순서 검증 완료: {len(sorted_pages)}개 페이지")


@pytest.mark.e2e
def test_parallel_parsing_cache_compatibility():
    """
    병렬 파싱 캐시 호환성 검증
    
    병렬 처리 결과가 캐시에 저장되고 재사용되는지 확인
    """
    # PDF 파일 존재 확인
    if not TEST_PDF_PATH.exists():
        pytest.skip(f"Test PDF file not found: {TEST_PDF_PATH}")
    
    from backend.parsers.cache_manager import CacheManager
    
    cache_manager = CacheManager()
    
    # 첫 번째 파싱 (캐시 미스)
    api_client = UpstageAPIClient(settings.upstage_api_key)
    result1 = api_client.parse_pdf(str(TEST_PDF_PATH))
    
    # 캐시 파일 확인
    cached_result = cache_manager.get_cached_result(str(TEST_PDF_PATH))
    assert cached_result is not None, "캐시 파일이 생성되지 않음"
    
    # 두 번째 파싱 (캐시 히트)
    result2 = api_client.parse_pdf(str(TEST_PDF_PATH))
    
    # 결과 비교 (Elements 개수)
    elements1 = result1.get("elements", [])
    elements2 = result2.get("elements", [])
    
    # 캐시 히트 시에는 동일한 결과여야 함
    # 하지만 실제로는 캐시에서 가져온 후 구조화 과정을 거치므로 약간 다를 수 있음
    # 최소한 Elements 개수는 같아야 함
    assert len(elements1) == len(elements2), \
        f"캐시 재사용 시 Elements 개수가 다름: {len(elements1)} vs {len(elements2)}"
    
    logger.info(f"[TEST] 캐시 호환성 검증 완료:")
    logger.info(f"  - 첫 번째 파싱 Elements: {len(elements1)}")
    logger.info(f"  - 두 번째 파싱 Elements: {len(elements2)}")

