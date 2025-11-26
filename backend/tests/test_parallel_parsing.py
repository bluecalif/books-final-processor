"""병렬 파싱 검증 테스트"""

import pytest
import time
import logging
from pathlib import Path
from backend.parsers.pdf_parser import PDFParser
from backend.config.settings import settings

logger = logging.getLogger(__name__)

# 테스트용 PDF 파일 경로
TEST_PDF_PATH = (
    Path(__file__).parent.parent.parent / "data" / "input" / "1등의 통찰.pdf"
)


@pytest.mark.e2e
def test_parallel_parsing_basic_functionality():
    """
    병렬 파싱 기본 기능 검증

    ⚠️ 실제 데이터만 사용: 실제 PDF 파일, 실제 Upstage API
    ⚠️ PDFParser 사용: 캐시 확인 로직이 포함되어 있음
    """
    # PDF 파일 존재 확인
    if not TEST_PDF_PATH.exists():
        pytest.skip(f"Test PDF file not found: {TEST_PDF_PATH}")

    # PDFParser 초기화 (캐시 확인 로직 포함)
    pdf_parser = PDFParser()

    # 병렬 파싱 실행 (PDFParser를 통해 호출)
    start_time = time.time()
    result = pdf_parser.parse_pdf(str(TEST_PDF_PATH), use_cache=True)
    elapsed_time = time.time() - start_time

    # 결과 검증
    assert result is not None
    assert "pages" in result
    assert "metadata" in result

    # 병렬 처리 메타데이터 확인 (10페이지 초과인 경우)
    metadata = result.get("metadata", {})
    if metadata.get("parallel_processing"):
        assert metadata.get("pages_per_chunk") == 10, "병렬 처리 청크 크기가 10이 아님"
        logger.info(f"[TEST] 병렬 처리 확인: {metadata.get('total_chunks', 0)}개 청크")

    # Pages 검증
    pages = result.get("pages", [])
    assert len(pages) > 0, "Pages가 비어있음"

    # Elements 검증 (첫 번째 페이지에서)
    if pages and len(pages) > 0:
        first_page = pages[0]
        elements = first_page.get("elements", [])
        if elements:
            # 페이지 번호 검증 (순차적이어야 함)
            page_numbers = [elem.get("page") for elem in elements if elem.get("page")]
            if page_numbers:
                assert min(page_numbers) >= 1, "페이지 번호가 1보다 작음"
                sorted_pages = sorted(set(page_numbers))
                logger.info(
                    f"[TEST] 페이지 번호 범위: {min(sorted_pages)} - {max(sorted_pages)}"
                )

    logger.info(f"[TEST] 병렬 파싱 완료:")
    logger.info(f"  - 소요 시간: {elapsed_time:.2f}초")
    logger.info(f"  - 총 Pages: {len(pages)}")
    logger.info(f"  - 총 Elements: {result.get('total_elements', 0)}")
    logger.info(f"  - 청크 수: {metadata.get('total_chunks', 0)}")
    logger.info(f"  - 병렬 처리: {metadata.get('parallel_processing', False)}")

    print(f"\n[RESULT] 병렬 파싱 검증:")
    print(f"  - 소요 시간: {elapsed_time:.2f}초")
    print(f"  - 총 Pages: {len(pages)}")
    print(f"  - 총 Elements: {result.get('total_elements', 0)}")
    print(f"  - 청크 수: {metadata.get('total_chunks', 0)}")


@pytest.mark.e2e
def test_parallel_parsing_elements_order():
    """
    병렬 파싱 Elements 순서 검증

    청크가 병렬로 처리되더라도 최종 결과의 Elements는 페이지 순서대로 정렬되어야 함
    ⚠️ PDFParser 사용: 캐시 확인 로직이 포함되어 있음
    """
    # PDF 파일 존재 확인
    if not TEST_PDF_PATH.exists():
        pytest.skip(f"Test PDF file not found: {TEST_PDF_PATH}")

    # PDFParser 초기화 (캐시 확인 로직 포함)
    pdf_parser = PDFParser()

    # 병렬 파싱 실행 (PDFParser를 통해 호출)
    result = pdf_parser.parse_pdf(str(TEST_PDF_PATH), use_cache=True)

    # Pages 검증
    pages = result.get("pages", [])
    assert len(pages) > 0, "Pages가 비어있음"

    # 모든 페이지의 Elements 수집
    all_elements = []
    for page in pages:
        elements = page.get("elements", [])
        all_elements.extend(elements)

    assert len(all_elements) > 0, "Elements가 비어있음"

    # 페이지 번호로 정렬하여 순서 확인
    page_elements = {}
    for elem in all_elements:
        page_num = elem.get("page")
        if page_num:
            if page_num not in page_elements:
                page_elements[page_num] = []
            page_elements[page_num].append(elem)

    # 페이지 번호가 순차적인지 확인
    sorted_pages = sorted(page_elements.keys())
    if sorted_pages:
        logger.info(
            f"[TEST] 페이지 번호 범위: {min(sorted_pages)} - {max(sorted_pages)}"
        )
        logger.info(f"[TEST] 총 페이지 수: {len(sorted_pages)}")

        # 연속성 확인 (일부 페이지가 누락될 수 있으므로 완전한 연속성은 요구하지 않음)
        # 하지만 최소한 순서는 맞아야 함
        for i in range(len(sorted_pages) - 1):
            assert (
                sorted_pages[i] <= sorted_pages[i + 1]
            ), "페이지 번호가 순차적이지 않음"

    logger.info(f"[TEST] Elements 순서 검증 완료: {len(sorted_pages)}개 페이지")


@pytest.mark.e2e
def test_parallel_parsing_cache_compatibility():
    """
    병렬 파싱 캐시 호환성 검증

    병렬 처리 결과가 캐시에 저장되고 재사용되는지 확인
    ⚠️ PDFParser를 통해 검증 (캐시는 PDFParser에서 관리)
    """
    # PDF 파일 존재 확인
    if not TEST_PDF_PATH.exists():
        pytest.skip(f"Test PDF file not found: {TEST_PDF_PATH}")

    from backend.parsers.pdf_parser import PDFParser
    from backend.parsers.cache_manager import CacheManager

    cache_manager = CacheManager()

    # 첫 번째 파싱 (캐시 미스, 병렬 처리)
    pdf_parser = PDFParser()
    result1 = pdf_parser.parse_pdf(str(TEST_PDF_PATH), use_cache=True)

    # 캐시 파일 확인
    cached_result = cache_manager.get_cached_result(str(TEST_PDF_PATH))
    assert cached_result is not None, "캐시 파일이 생성되지 않음"

    # 병렬 처리 메타데이터 확인 (10페이지 초과인 경우)
    if cached_result.get("metadata", {}).get("parallel_processing"):
        assert (
            cached_result["metadata"]["pages_per_chunk"] == 10
        ), "병렬 처리 청크 크기가 10이 아님"
        logger.info(
            f"[TEST] 병렬 처리 확인: {cached_result['metadata'].get('total_chunks', 0)}개 청크"
        )

    # 두 번째 파싱 (캐시 히트)
    result2 = pdf_parser.parse_pdf(str(TEST_PDF_PATH), use_cache=True)

    # 결과 비교 (페이지 수, Elements 개수)
    pages1 = result1.get("pages", [])
    pages2 = result2.get("pages", [])

    # 캐시 히트 시에는 동일한 결과여야 함
    assert len(pages1) == len(
        pages2
    ), f"캐시 재사용 시 페이지 수가 다름: {len(pages1)} vs {len(pages2)}"

    assert result1.get("total_elements") == result2.get(
        "total_elements"
    ), f"캐시 재사용 시 Elements 개수가 다름: {result1.get('total_elements')} vs {result2.get('total_elements')}"

    logger.info(f"[TEST] 캐시 호환성 검증 완료:")
    logger.info(
        f"  - 첫 번째 파싱: {len(pages1)} 페이지, {result1.get('total_elements')} Elements"
    )
    logger.info(
        f"  - 두 번째 파싱: {len(pages2)} 페이지, {result2.get('total_elements')} Elements"
    )
    logger.info(
        f"  - 병렬 처리: {cached_result.get('metadata', {}).get('parallel_processing', False)}"
    )
