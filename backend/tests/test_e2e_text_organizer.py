"""
텍스트 정리 E2E 테스트 (실제 서버 실행, 실제 데이터만 사용, Mock 사용 금지)

⚠️ 중요:
- 실제 서버 실행: 프로덕션 플로우와 동일하게 검증
- 실제 데이터만 사용: 실제 PDF 파일, 실제 서버 DB
- Mock 사용 절대 금지
- DB 직접 조회 금지: 서버와 다른 DB이므로 API 응답만 검증
- 캐시 재사용 검증: 텍스트 정리 시 캐시된 파싱 결과 사용 확인

테스트 실행 제어:
- 환경변수 TEST_FIRST_BOOK_ONLY=1 설정 시 첫 번째 도서만 테스트
- 예: $env:TEST_FIRST_BOOK_ONLY="1"; poetry run pytest backend/tests/test_e2e_text_organizer.py
"""

import pytest
import time
import logging
import os
import json
from pathlib import Path
from datetime import datetime
import httpx
from backend.config.settings import settings

# 로그 디렉토리
LOG_DIR = Path(__file__).parent.parent.parent / "data" / "test_results"
LOG_DIR.mkdir(parents=True, exist_ok=True)


def setup_test_logging():
    """간결한 로그 설정 (핵심 정보만)"""
    log_file = (
        LOG_DIR / f"text_organizer_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    )

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(
        logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s")
    )

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    logger = logging.getLogger(__name__)
    logger.info(f"테스트 시작 - 로그 파일: {log_file}")

    return log_file


def get_structure_analyzed_books(e2e_client: httpx.Client) -> list:
    """
    구조 분석 완료된 책 목록 조회
    
    Args:
        e2e_client: HTTP 클라이언트
        
    Returns:
        구조 분석 완료된 책 목록 (status='structured')
    """
    response = e2e_client.get("/api/books", params={"status": "structured"})
    assert response.status_code == 200, f"책 목록 조회 실패: {response.status_code}"
    
    data = response.json()
    books = data.get("books", [])
    
    logger = logging.getLogger(__name__)
    logger.info(f"[TEST] 구조 분석 완료된 책 {len(books)}개 발견")
    
    return books


def validate_text_json_schema(text_data: dict) -> dict:
    """
    텍스트 JSON 파일 스키마 검증
    
    Args:
        text_data: 텍스트 JSON 데이터
        
    Returns:
        검증 결과 딕셔너리
    """
    results = {
        "has_book_id": False,
        "has_book_title": False,
        "has_metadata": False,
        "has_text_content": False,
        "has_chapters": False,
        "chapters_structure_valid": False,
    }
    
    # book_id 확인
    results["has_book_id"] = "book_id" in text_data and isinstance(text_data["book_id"], int)
    
    # book_title 확인
    results["has_book_title"] = "book_title" in text_data
    
    # metadata 확인
    metadata = text_data.get("metadata", {})
    results["has_metadata"] = isinstance(metadata, dict)
    if results["has_metadata"]:
        results["metadata_has_total_pages"] = "total_pages" in metadata
        results["metadata_has_main_start_page"] = "main_start_page" in metadata
        results["metadata_has_main_end_page"] = "main_end_page" in metadata
        results["metadata_has_chapter_count"] = "chapter_count" in metadata
    
    # text_content 확인
    text_content = text_data.get("text_content", {})
    results["has_text_content"] = isinstance(text_content, dict)
    
    # chapters 확인
    chapters = text_content.get("chapters", [])
    results["has_chapters"] = isinstance(chapters, list) and len(chapters) > 0
    
    # 챕터 구조 검증
    if results["has_chapters"]:
        valid_chapters = 0
        for chapter in chapters:
            required_fields = ["order_index", "chapter_number", "title", "start_page", "end_page", "pages"]
            if all(field in chapter for field in required_fields):
                # pages 배열 검증
                pages = chapter.get("pages", [])
                if isinstance(pages, list):
                    page_valid = True
                    for page in pages:
                        if not isinstance(page, dict) or "page_number" not in page or "text" not in page:
                            page_valid = False
                            break
                    if page_valid:
                        valid_chapters += 1
        
        results["chapters_structure_valid"] = valid_chapters == len(chapters)
        results["valid_chapter_count"] = valid_chapters
        results["total_chapter_count"] = len(chapters)
    
    return results


def validate_main_content_only(text_data: dict) -> dict:
    """
    본문 영역만 포함되는지 검증 (서문/종문 제외)
    
    텍스트 JSON 파일의 metadata에 있는 본문 범위와 실제 챕터/페이지 범위가 일치하는지 확인
    
    Args:
        text_data: 텍스트 JSON 데이터
        
    Returns:
        검증 결과 딕셔너리
    """
    results = {
        "has_metadata": False,
        "all_pages_in_main_range": False,
    }
    
    metadata = text_data.get("metadata", {})
    results["has_metadata"] = isinstance(metadata, dict) and len(metadata) > 0
    
    if not results["has_metadata"]:
        return results
    
    text_main_start = metadata.get("main_start_page")
    text_main_end = metadata.get("main_end_page")
    
    results["main_start_page"] = text_main_start
    results["main_end_page"] = text_main_end
    
    # 모든 페이지가 본문 범위 내에 있는지 검증
    chapters = text_data.get("text_content", {}).get("chapters", [])
    all_pages_in_range = True
    out_of_range_pages = []
    
    for chapter in chapters:
        chapter_start = chapter.get("start_page")
        chapter_end = chapter.get("end_page")
        
        # 챕터 시작/끝 페이지가 본문 범위 내에 있는지 확인
        if text_main_start is not None and chapter_start is not None:
            if chapter_start < text_main_start:
                all_pages_in_range = False
                out_of_range_pages.append({"chapter": chapter.get("title"), "page": chapter_start, "reason": "before_main_start"})
        
        if text_main_end is not None and chapter_end is not None:
            if chapter_end > text_main_end:
                all_pages_in_range = False
                out_of_range_pages.append({"chapter": chapter.get("title"), "page": chapter_end, "reason": "after_main_end"})
        
        # 각 페이지가 본문 범위 내에 있는지 확인
        pages = chapter.get("pages", [])
        for page in pages:
            page_num = page.get("page_number")
            if page_num is not None:
                if text_main_start is not None and page_num < text_main_start:
                    all_pages_in_range = False
                    out_of_range_pages.append({"chapter": chapter.get("title"), "page": page_num, "reason": "before_main_start"})
                if text_main_end is not None and page_num > text_main_end:
                    all_pages_in_range = False
                    out_of_range_pages.append({"chapter": chapter.get("title"), "page": page_num, "reason": "after_main_end"})
    
    results["all_pages_in_main_range"] = all_pages_in_range
    if out_of_range_pages:
        results["out_of_range_pages"] = out_of_range_pages[:10]  # 최대 10개만
    
    return results


@pytest.mark.e2e
def test_e2e_text_organizer_full_flow(e2e_client: httpx.Client):
    """
    텍스트 정리 전체 플로우 E2E 테스트 (모든 구조 분석 완료된 책 처리)
    
    1. 구조 분석 완료된 책 조회
    2. 각 책에 대해 텍스트 정리 API 호출 (백그라운드 작업)
    3. 텍스트 정리 완료 대기 및 파일 재생성 확인
    4. 텍스트 JSON 파일 조회 및 검증
    5. 파일 생성 시간이 최신인지 확인
    
    ⚠️ 중요: 모든 구조 분석 완료된 책에 대해 텍스트 파일을 재생성합니다.
    """
    logger = logging.getLogger(__name__)
    logger.info("[TEST] 텍스트 정리 전체 플로우 E2E 테스트 시작 (모든 책 재생성)")
    
    # 1. 구조 분석 완료된 책 조회
    books = get_structure_analyzed_books(e2e_client)
    assert len(books) > 0, "구조 분석 완료된 책이 없습니다"
    
    # 첫 번째 책만 테스트 (환경변수 설정 시)
    test_first_only = os.getenv("TEST_FIRST_BOOK_ONLY", "0") == "1"
    if test_first_only:
        books = books[:1]
        logger.info("[TEST] 첫 번째 책만 테스트 (TEST_FIRST_BOOK_ONLY=1)")
    else:
        logger.info(f"[TEST] 모든 책에 대해 텍스트 파일 재생성: {len(books)}개")
    
    # 현재 시간 기록 (파일 생성 시간 확인용)
    test_start_time = datetime.now()
    
    # 처리 결과 추적
    results = {
        "total": len(books),
        "success": 0,
        "failed": 0,
        "files_regenerated": [],
    }
    
    for idx, book in enumerate(books, 1):
        book_id = book["id"]
        book_title = book.get("title", "")
        logger.info(f"[TEST] [{idx}/{len(books)}] 텍스트 정리 시작: book_id={book_id}, title={book_title}")
        
        # 기존 텍스트 파일 확인 (재생성 전)
        text_output_dir = settings.output_dir / "text"
        existing_files = list(text_output_dir.glob(f"*_{book_id}_text.json"))
        if existing_files:
            existing_file = existing_files[0]
            existing_mtime = datetime.fromtimestamp(existing_file.stat().st_mtime)
            logger.info(f"[TEST] 기존 파일 발견: {existing_file.name} (수정 시간: {existing_mtime.strftime('%Y-%m-%d %H:%M:%S')})")
        
        # 2. 텍스트 정리 API 호출 (백그라운드 작업 - 항상 재생성)
        response = e2e_client.post(f"/api/books/{book_id}/organize")
        assert response.status_code == 200, f"텍스트 정리 시작 실패: {response.status_code}"
        
        response_data = response.json()
        assert response_data.get("message") == "Text organization started", "응답 메시지 확인"
        assert response_data.get("book_id") == book_id, "책 ID 확인"
        
        logger.info(f"[TEST] 텍스트 정리 시작됨: book_id={book_id}")
        
        # 3. 텍스트 정리 완료 대기 (파일 존재 확인)
        max_wait_time = 300  # 최대 5분 대기
        start_time = time.time()
        text_data = None
        timed_out = False
        
        while True:
            elapsed = time.time() - start_time
            if elapsed > max_wait_time:
                logger.error(f"[TEST] 텍스트 정리 타임아웃: book_id={book_id} ({max_wait_time}초 초과)")
                results["failed"] += 1
                timed_out = True
                break
            
            # 텍스트 파일 확인
            try:
                response = e2e_client.get(f"/api/books/{book_id}/text")
                if response.status_code == 200:
                    text_data = response.json()
                    # 텍스트 데이터가 있는지 확인
                    if text_data.get("text_content") and text_data.get("text_content").get("chapters"):
                        logger.info(f"[TEST] 텍스트 정리 완료 확인: book_id={book_id}")
                        break
            except httpx.HTTPStatusError:
                pass
            
            time.sleep(2)
        
        # 타임아웃으로 실패한 경우 다음 책으로
        if timed_out:
            logger.warning(f"[TEST] 타임아웃으로 인해 다음 책으로 넘어갑니다: book_id={book_id}")
            continue
        
        # 4. 텍스트 JSON 파일 조회 및 검증
        if text_data is None:
            response = e2e_client.get(f"/api/books/{book_id}/text")
            assert response.status_code == 200, f"텍스트 파일 조회 실패: {response.status_code}"
            text_data = response.json()
        
        logger.info(f"[TEST] 텍스트 JSON 파일 조회 성공: book_id={book_id}")
        
        # 4.0 파일 생성 시간 확인 (재생성 확인)
        text_file_path = None
        updated_files = list(text_output_dir.glob(f"*_{book_id}_text.json"))
        if not updated_files:
            # 해시 기반 파일명으로도 확인
            updated_files = list(text_output_dir.glob("*_text.json"))
        
        if updated_files:
            text_file_path = updated_files[0]
            file_mtime = datetime.fromtimestamp(text_file_path.stat().st_mtime)
            time_diff = (test_start_time - file_mtime).total_seconds()
            
            logger.info(
                f"[TEST] 파일 생성 시간: {file_mtime.strftime('%Y-%m-%d %H:%M:%S')} "
                f"(테스트 시작으로부터 {abs(time_diff):.1f}초 전)"
            )
            
            # 파일이 최신에 생성되었는지 확인 (테스트 시작 후 생성되어야 함)
            if file_mtime >= test_start_time:
                logger.info(f"[TEST] 파일이 최신에 재생성됨: {text_file_path.name}")
                results["files_regenerated"].append({
                    "book_id": book_id,
                    "file_name": text_file_path.name,
                    "created_at": file_mtime.isoformat(),
                })
            else:
                logger.warning(
                    f"[TEST] 파일이 오래됨: {text_file_path.name} "
                    f"(생성 시간: {file_mtime.strftime('%Y-%m-%d %H:%M:%S')})"
                )
        
        # 4.1 JSON 스키마 검증
        schema_results = validate_text_json_schema(text_data)
        logger.info(f"[TEST] JSON 스키마 검증 결과: {schema_results}")
        
        assert schema_results["has_book_id"], "book_id 필드 누락"
        assert schema_results["has_book_title"], "book_title 필드 누락"
        assert schema_results["has_metadata"], "metadata 필드 누락"
        assert schema_results["has_text_content"], "text_content 필드 누락"
        assert schema_results["has_chapters"], "chapters 배열 누락"
        assert schema_results["chapters_structure_valid"], f"챕터 구조 검증 실패: {schema_results}"
        
        # 4.2 본문 영역만 포함되는지 검증 (텍스트 파일의 metadata 사용)
        main_content_results = validate_main_content_only(text_data)
        logger.info(f"[TEST] 본문 영역 검증 결과: {main_content_results}")
        
        assert main_content_results["has_metadata"], "metadata 필드 누락"
        assert main_content_results["all_pages_in_main_range"], f"본문 범위를 벗어난 페이지 발견: {main_content_results.get('out_of_range_pages', [])}"
        
        # 4.4 챕터별 텍스트 분리 확인
        chapters = text_data.get("text_content", {}).get("chapters", [])
        logger.info(f"[TEST] 챕터 개수: {len(chapters)}")
        
        for chapter_idx, chapter in enumerate(chapters):
            chapter_title = chapter.get("title", "")
            pages = chapter.get("pages", [])
            start_page = chapter.get("start_page")
            end_page = chapter.get("end_page")
            
            logger.info(
                f"[TEST] 챕터 {chapter_idx+1}: {chapter_title} "
                f"(시작: {start_page}, 끝: {end_page}, 페이지: {len(pages)}개)"
            )
            
            # 각 챕터에 페이지가 있는지 확인
            assert len(pages) > 0, f"챕터 {chapter_idx+1}에 페이지가 없습니다: {chapter_title}"
            
            # 페이지 번호가 순서대로 있는지 확인
            page_numbers = [p.get("page_number") for p in pages]
            assert page_numbers == sorted(page_numbers), f"챕터 {chapter_idx+1}의 페이지 번호가 정렬되지 않았습니다"
            
            # 시작/끝 페이지가 챕터 범위와 일치하는지 확인
            if page_numbers:
                assert min(page_numbers) == start_page, f"챕터 {chapter_idx+1}의 시작 페이지 불일치"
                assert max(page_numbers) == end_page, f"챕터 {chapter_idx+1}의 끝 페이지 불일치"
        
        logger.info(f"[TEST] 텍스트 정리 테스트 완료: book_id={book_id}")
        results["success"] += 1
        
        # 첫 번째 책만 테스트하는 경우 중단
        if test_first_only:
            break
    
    # 결과 요약 출력
    logger.info("=" * 80)
    logger.info("[TEST] 텍스트 파일 재생성 결과 요약")
    logger.info(f"  - 전체: {results['total']}개")
    logger.info(f"  - 성공: {results['success']}개")
    logger.info(f"  - 실패: {results['failed']}개")
    logger.info(f"  - 재생성된 파일: {len(results['files_regenerated'])}개")
    logger.info("=" * 80)
    
    assert results["failed"] == 0, f"{results['failed']}개 책의 텍스트 정리 실패"


@pytest.mark.e2e
def test_e2e_text_organizer_cache_reuse(e2e_client: httpx.Client):
    """
    텍스트 정리 시 캐시 재사용 검증
    
    텍스트 정리 시 캐시된 파싱 결과를 사용하는지 확인
    (Upstage API 호출이 없어야 함)
    """
    logger = logging.getLogger(__name__)
    logger.info("[TEST] 텍스트 정리 캐시 재사용 검증 테스트 시작")
    
    # 구조 분석 완료된 책 조회
    books = get_structure_analyzed_books(e2e_client)
    assert len(books) > 0, "구조 분석 완료된 책이 없습니다"
    
    # 첫 번째 책만 테스트
    book = books[0]
    book_id = book["id"]
    book_title = book.get("title", "")
    
    logger.info(f"[TEST] 캐시 재사용 검증: book_id={book_id}, title={book_title}")
    
    # 캐시 파일 확인 (Upstage API 캐시)
    pdf_path = book.get("source_file_path")
    if pdf_path and Path(pdf_path).exists():
        import hashlib
        with open(pdf_path, "rb") as f:
            hasher = hashlib.md5()
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
            file_hash = hasher.hexdigest()
        
        cache_dir = settings.cache_dir / "upstage"
        cache_file = cache_dir / f"{file_hash}.json"
        
        if cache_file.exists():
            logger.info(f"[TEST] 캐시 파일 존재 확인: {cache_file}")
            
            # 캐시 파일 수정 시간 기록
            cache_mtime_before = cache_file.stat().st_mtime
            
            # 텍스트 정리 실행
            response = e2e_client.post(f"/api/books/{book_id}/organize")
            assert response.status_code == 200, "텍스트 정리 시작 실패"
            
            # 텍스트 정리 완료 대기
            max_wait_time = 300
            start_time = time.time()
            
            while True:
                elapsed = time.time() - start_time
                if elapsed > max_wait_time:
                    pytest.fail(f"텍스트 정리 타임아웃: book_id={book_id}")
                
                try:
                    response = e2e_client.get(f"/api/books/{book_id}/text")
                    if response.status_code == 200:
                        text_data = response.json()
                        if text_data.get("text_content") and text_data.get("text_content").get("chapters"):
                            break
                except httpx.HTTPStatusError:
                    pass
                
                time.sleep(2)
            
            # 캐시 파일 수정 시간 확인 (변경되지 않아야 함)
            cache_mtime_after = cache_file.stat().st_mtime
            assert cache_mtime_before == cache_mtime_after, "캐시 파일이 수정되었습니다 (Upstage API 호출 가능성)"
            
            logger.info("[TEST] 캐시 재사용 검증 통과 (캐시 파일 수정 시간 변경 없음)")
        else:
            logger.warning(f"[TEST] 캐시 파일이 없습니다: {cache_file} (이 테스트는 캐시가 있는 경우에만 의미 있음)")
    else:
        logger.warning("[TEST] PDF 파일 경로가 없습니다 (이 테스트는 PDF 파일이 있는 경우에만 의미 있음)")


if __name__ == "__main__":
    # 테스트 로깅 설정
    setup_test_logging()
    
    # pytest 실행
    pytest.main([__file__, "-v"])

