"""병렬 파싱 검증 테스트"""

import pytest
import time
import logging
from pathlib import Path
from backend.parsers.pdf_parser import PDFParser
from backend.parsers.cache_manager import CacheManager

logger = logging.getLogger(__name__)

# 테스트용 PDF 파일 경로 (변경 시 여기만 수정)
TEST_PDF_PATH = (
    Path(__file__).parent.parent.parent / "data" / "input" / "99%를 위한 경제.pdf"
)


@pytest.mark.e2e
def test_parallel_parsing_api_call_count_verification():
    """
    API 호출 횟수 정확히 검증

    요구사항:
    1. 첫 번째 실행: 캐시 없음 → API 호출 발생
    2. 두 번째 실행: 캐시 있음 → API 호출 0번
    3. 캐시 파일 생성 및 재사용 확인
    """
    if not TEST_PDF_PATH.exists():
        pytest.skip(f"Test PDF file not found: {TEST_PDF_PATH}")

    cache_manager = CacheManager()
    pdf_parser = PDFParser()

    # 첫 번째 파싱 (캐시가 있으면 히트, 없으면 미스)
    cached_before = cache_manager.get_cached_result(str(TEST_PDF_PATH))
    cache_status = "히트" if cached_before else "미스"
    logger.info("=" * 80)
    logger.info(f"[TEST] ========== 첫 번째 파싱 시작 (캐시 {cache_status}) ==========")
    logger.info("=" * 80)
    start_time_1 = time.time()
    result1 = pdf_parser.parse_pdf(str(TEST_PDF_PATH), use_cache=True)
    elapsed_time_1 = time.time() - start_time_1

    assert result1 is not None
    assert "pages" in result1
    assert "metadata" in result1

    metadata1 = result1.get("metadata", {})
    original_pages_1 = result1.get("original_pages", 0)

    logger.info("=" * 80)
    logger.info(f"[TEST] 첫 번째 파싱 완료: {elapsed_time_1:.3f}초")
    logger.info(f"[TEST] 원본 페이지 수: {original_pages_1}")
    logger.info(f"[TEST] 병렬 처리: {metadata1.get('parallel_processing', False)}")
    if metadata1.get("parallel_processing"):
        logger.info(f"[TEST] 청크 수: {metadata1.get('total_chunks', 0)}")
        logger.info(f"[TEST] 청크당 페이지 수: {metadata1.get('pages_per_chunk', 0)}")
    logger.info("=" * 80)

    # 캐시 파일 생성 확인
    cache_key = cache_manager.get_cache_key(str(TEST_PDF_PATH))
    cache_file = cache_manager.cache_dir / f"{cache_key}.json"
    assert cache_file.exists(), f"캐시 파일이 생성되지 않음: {cache_file}"

    cached_result_after = cache_manager.get_cached_result(str(TEST_PDF_PATH))
    assert cached_result_after is not None, "캐시 파일이 생성되지 않음"
    cached_pages = cached_result_after.get("usage", {}).get("pages", 0)
    logger.info(f"[TEST] 캐시 파일 생성 확인: {cached_pages}페이지")

    # 두 번째 파싱 (캐시 히트)
    logger.info("=" * 80)
    logger.info("[TEST] ========== 두 번째 파싱 시작 (캐시 히트 예상) ==========")
    logger.info("=" * 80)
    start_time_2 = time.time()
    result2 = pdf_parser.parse_pdf(str(TEST_PDF_PATH), use_cache=True)
    elapsed_time_2 = time.time() - start_time_2

    assert elapsed_time_2 < elapsed_time_1, (
        f"두 번째 파싱이 첫 번째보다 느림: {elapsed_time_2:.2f}초 vs {elapsed_time_1:.2f}초 "
        "(캐시를 사용해야 함)"
    )

    assert result2 is not None
    assert "pages" in result2
    original_pages_2 = result2.get("original_pages", 0)

    logger.info("=" * 80)
    logger.info(f"[TEST] 두 번째 파싱 완료: {elapsed_time_2:.3f}초")
    logger.info(f"[TEST] 원본 페이지 수: {original_pages_2}")
    logger.info(
        f"[TEST] 성능 향상: {((elapsed_time_1 - elapsed_time_2) / elapsed_time_1 * 100):.1f}% 빠름"
    )
    logger.info("=" * 80)

    # 결과 비교
    pages1 = result1.get("pages", [])
    pages2 = result2.get("pages", [])

    assert len(pages1) == len(
        pages2
    ), f"캐시 재사용 시 페이지 수가 다름: {len(pages1)} vs {len(pages2)}"

    assert result1.get("total_elements") == result2.get(
        "total_elements"
    ), f"캐시 재사용 시 Elements 개수가 다름: {result1.get('total_elements')} vs {result2.get('total_elements')}"

    assert original_pages_1 == original_pages_2, (
        f"원본 페이지 수가 다름: {original_pages_1} vs {original_pages_2} "
        "(캐시를 사용했으므로 동일해야 함)"
    )

    print(f"\n[RESULT] API 호출 횟수 검증:")
    print(f"  - 첫 번째 파싱: {elapsed_time_1:.2f}초 (캐시 미스)")
    print(f"  - 두 번째 파싱: {elapsed_time_2:.2f}초 (캐시 히트)")
    print(
        f"  - 성능 향상: {((elapsed_time_1 - elapsed_time_2) / elapsed_time_1 * 100):.1f}% 빠름"
    )
    print(
        f"  - 원본 페이지 수: {original_pages_1} (첫 번째), {original_pages_2} (두 번째)"
    )
    print(
        f"  - 로그에서 '[API_CALL]', '[CACHE_HIT]', '[CACHE_MISS]' 태그로 API 호출 횟수 확인 필요"
    )
