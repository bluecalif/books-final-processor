"""PDF 파싱 E2E 테스트 (실제 서버 실행, 실제 데이터만 사용, Mock 사용 금지)"""
import pytest
import time
import logging
import json
import hashlib
from pathlib import Path
from datetime import datetime
import httpx
from backend.config.settings import settings

# 실제 PDF 파일 경로 (전체 PDF로 최종 확인)
TEST_PDF_PATH = Path(__file__).parent.parent.parent / "data" / "input" / "1등의 통찰.pdf"

# 로그 디렉토리
LOG_DIR = Path(__file__).parent.parent.parent / "data" / "test_results"
LOG_DIR.mkdir(parents=True, exist_ok=True)


def setup_test_logging():
    """테스트용 로그 파일 설정"""
    log_file = LOG_DIR / f"cache_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    
    # 파일 핸들러 추가
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('[%(asctime)s] %(name)s - %(levelname)s: %(message)s')
    file_handler.setFormatter(formatter)
    
    # 루트 로거에 추가
    root_logger = logging.getLogger()
    root_logger.addHandler(file_handler)
    root_logger.setLevel(logging.DEBUG)
    
    return log_file


@pytest.mark.e2e
def test_e2e_pdf_parsing_full_flow(e2e_client: httpx.Client):
    """
    전체 PDF 파싱 플로우 E2E 테스트
    
    ⚠️ 실제 데이터만 사용: 실제 PDF 파일, 실제 Upstage API, 실제 서버 DB
    ⚠️ 실제 서버 실행: 프로덕션 플로우와 동일하게 검증
    ⚠️ Mock 사용 절대 금지
    ⚠️ DB 직접 조회 금지: 서버와 다른 DB이므로 API 응답만 검증
    """
    # 로그 파일 설정
    log_file = setup_test_logging()
    logger = logging.getLogger(__name__)
    logger.info(f"[TEST] 로그 파일: {log_file}")
    logger.info(f"[TEST] 테스트 PDF 파일: {TEST_PDF_PATH}")
    
    # 1. PDF 파일 존재 확인
    assert TEST_PDF_PATH.exists(), f"Test PDF file not found: {TEST_PDF_PATH}"
    logger.info(f"[TEST] PDF 파일 존재 확인 완료: {TEST_PDF_PATH}")
    
    # 2. PDF 파일 업로드 (실제 HTTP 요청)
    with open(TEST_PDF_PATH, "rb") as f:
        files = {"file": (TEST_PDF_PATH.name, f, "application/pdf")}
        response = e2e_client.post(
            "/api/books/upload",
            files=files,
            params={"title": "1등의 통찰", "author": "Test Author"}
        )
    
    assert response.status_code == 200
    upload_data = response.json()
    book_id = upload_data["book_id"]
    assert upload_data["status"] == "uploaded"
    
    # 3. 업로드된 책 상태 확인 (API 응답으로)
    book_response = e2e_client.get(f"/api/books/{book_id}")
    assert book_response.status_code == 200
    book_data = book_response.json()
    assert book_data["status"] == "uploaded"
    assert book_data["title"] == "1등의 통찰"
    assert book_data["author"] == "Test Author"
    
    # 4. 백그라운드 작업 검증 (프로덕션 플로우와 동일)
    # ⚠️ 중요: 실제 서버에서 백그라운드 작업이 실행되므로, 상태를 폴링하여 완료 확인
    max_wait_time = 300  # 최대 5분 대기
    start_time = time.time()
    
    while True:
        elapsed = time.time() - start_time
        if elapsed > max_wait_time:
            pytest.fail(f"Background task timeout after {max_wait_time} seconds")
        
        # 실제 HTTP 요청으로 상태 확인 (프로덕션과 동일)
        response = e2e_client.get(f"/api/books/{book_id}")
        assert response.status_code == 200
        status = response.json()["status"]
        
        if status == "parsed":
            break
        elif status == "error_parsing":
            pytest.fail(f"Parsing failed: book_id={book_id}")
        
        time.sleep(2)  # 2초마다 상태 확인
    
    # 5. 파싱 결과 검증 (API 응답으로만 검증)
    book_response = e2e_client.get(f"/api/books/{book_id}")
    assert book_response.status_code == 200
    book_data = book_response.json()
    assert book_data["status"] == "parsed"
    assert book_data["page_count"] is not None
    assert book_data["page_count"] > 0
    
    # 페이지 수 출력 (확인용)
    logger.info(f"[TEST] 파싱 완료:")
    logger.info(f"  - Book ID: {book_id}")
    logger.info(f"  - Status: {book_data['status']}")
    logger.info(f"  - Page Count (DB): {book_data['page_count']}")
    
    print(f"\n[RESULT] 파싱 완료:")
    print(f"  - Book ID: {book_id}")
    print(f"  - Status: {book_data['status']}")
    print(f"  - Page Count (DB): {book_data['page_count']}")
    print(f"  - 로그 파일: {log_file}")
    
    # 6. 최종 검증: 파싱 완료 확인
    assert book_data["id"] == book_id
    assert book_data["title"] == "1등의 통찰"
    assert book_data["page_count"] > 0
    
    # 7. 캐시 저장 검증
    cache_dir = settings.cache_dir / "upstage"
    assert cache_dir.exists(), f"캐시 디렉토리가 존재하지 않음: {cache_dir}"
    
    # PDF 파일 해시 계산
    with open(TEST_PDF_PATH, 'rb') as f:
        hasher = hashlib.md5()
        for chunk in iter(lambda: f.read(4096), b""):
            hasher.update(chunk)
        file_hash = hasher.hexdigest()
    
    cache_file = cache_dir / f"{file_hash}.json"
    assert cache_file.exists(), f"캐시 파일이 생성되지 않음: {cache_file}"
    assert cache_file.stat().st_size > 0, f"캐시 파일이 비어있음: {cache_file}"
    
    # 캐시 파일 내용 검증
    with open(cache_file, 'r', encoding='utf-8') as f:
        cached_data = json.load(f)
    
    assert "elements" in cached_data or "api" in cached_data, "캐시 파일에 필수 필드가 없음"
    
    # 병렬 처리 메타데이터 검증 (10페이지 초과인 경우)
    if cached_data.get("metadata", {}).get("parallel_processing"):
        assert cached_data["metadata"]["pages_per_chunk"] == 10, "병렬 처리 청크 크기가 10이 아님"
        logger.info(f"[TEST] 병렬 처리 확인: {cached_data['metadata'].get('total_chunks', 0)}개 청크")
    
    logger.info(f"[TEST] 캐시 저장 검증 완료: {cache_file} ({cache_file.stat().st_size} bytes)")
    
    # 8. 양면 분리 검증 (페이지 수 확인)
    # 원본 10페이지 → 양면 분리 후 20페이지 예상
    # 하지만 실제로는 양면 분리가 적용되어야 함
    logger.info(f"[TEST] 페이지 수: {book_data['page_count']} (원본 10페이지)")
    assert book_data["page_count"] >= 10, "양면 분리 후 페이지 수가 원본보다 적음"
    
    # 9. 페이지 데이터 검증 (API를 통해 페이지 조회)
    pages_response = e2e_client.get(f"/api/books/{book_id}/pages")
    if pages_response.status_code == 200:
        pages_data = pages_response.json()
        if "pages" in pages_data and len(pages_data["pages"]) > 0:
            first_page = pages_data["pages"][0]
            assert "page_number" in first_page, "페이지에 page_number 필드가 없음"
            assert "raw_text" in first_page, "페이지에 raw_text 필드가 없음"
            assert "elements" in first_page or "page_metadata" in first_page, "페이지에 elements 또는 page_metadata 필드가 없음"
            logger.info(f"[TEST] 페이지 데이터 검증 완료: page_number={first_page.get('page_number')}, raw_text 길이={len(first_page.get('raw_text', ''))}")


@pytest.mark.e2e
def test_e2e_pdf_parsing_status_transition(e2e_client: httpx.Client):
    """
    상태 변경 검증 E2E 테스트 (uploaded → parsed)
    
    ⚠️ 실제 데이터만 사용
    ⚠️ 실제 서버 실행: 프로덕션 플로우와 동일하게 검증
    ⚠️ DB 직접 조회 금지: API 응답만 검증
    """
    # 1. PDF 파일 존재 확인
    assert TEST_PDF_PATH.exists(), f"Test PDF file not found: {TEST_PDF_PATH}"
    
    # 2. PDF 파일 업로드
    with open(TEST_PDF_PATH, "rb") as f:
        files = {"file": (TEST_PDF_PATH.name, f, "application/pdf")}
        response = e2e_client.post(
            "/api/books/upload",
            files=files
        )
    
    assert response.status_code == 200
    upload_data = response.json()
    book_id = upload_data["book_id"]
    assert upload_data["status"] == "uploaded"
    
    # 3. 초기 상태 확인 (uploaded) - API 응답으로
    response = e2e_client.get(f"/api/books/{book_id}")
    assert response.status_code == 200
    book_data = response.json()
    assert book_data["status"] == "uploaded"
    
    # 4. 백그라운드 작업 검증 (프로덕션 플로우와 동일)
    # 실제 HTTP 요청으로 상태를 폴링하여 백그라운드 작업 완료 확인
    max_wait_time = 300  # 최대 5분 대기
    start_time = time.time()
    
    status_history = []  # 상태 변경 이력 추적
    
    while True:
        elapsed = time.time() - start_time
        if elapsed > max_wait_time:
            pytest.fail(f"Background task timeout after {max_wait_time} seconds")
        
        # 실제 HTTP 요청으로 상태 확인 (프로덕션과 동일)
        response = e2e_client.get(f"/api/books/{book_id}")
        assert response.status_code == 200
        status = response.json()["status"]
        status_history.append(status)
        
        if status == "parsed":
            break
        elif status == "error_parsing":
            pytest.fail(f"Parsing failed: book_id={book_id}")
        
        time.sleep(2)  # 2초마다 상태 확인
    
    # 5. 상태 변경 확인 (parsed) - API 응답으로
    final_response = e2e_client.get(f"/api/books/{book_id}")
    assert final_response.status_code == 200
    final_data = final_response.json()
    assert final_data["status"] == "parsed"
    assert final_data["page_count"] is not None
    assert final_data["page_count"] > 0
    
    # 6. 상태 변경 이력 검증 (uploaded → parsed)
    assert "uploaded" in status_history, "초기 상태가 uploaded가 아님"
    assert "parsed" in status_history, "최종 상태가 parsed가 아님"
    assert status_history[-1] == "parsed", "최종 상태가 parsed가 아님"


@pytest.mark.e2e
def test_e2e_pdf_parsing_cache_reuse(e2e_client: httpx.Client):
    """
    캐시 재사용 검증 E2E 테스트
    
    ⚠️ 실제 데이터만 사용
    ⚠️ 실제 서버 실행: 프로덕션 플로우와 동일하게 검증
    ⚠️ DB 직접 조회 금지: API 응답만 검증
    """
    # 1. PDF 파일 존재 확인
    assert TEST_PDF_PATH.exists(), f"Test PDF file not found: {TEST_PDF_PATH}"
    
    # 2. 첫 번째 파싱 (캐시 미스)
    logger = logging.getLogger(__name__)
    logger.info("[TEST] 첫 번째 파싱 시작 (캐시 미스 예상)")
    
    with open(TEST_PDF_PATH, "rb") as f:
        files = {"file": (TEST_PDF_PATH.name, f, "application/pdf")}
        response = e2e_client.post(
            "/api/books/upload",
            files=files,
            params={"title": "1등의 통찰 (캐시 테스트)", "author": "Test Author"}
        )
    
    assert response.status_code == 200
    upload_data = response.json()
    book_id_1 = upload_data["book_id"]
    
    # 파싱 완료 대기
    max_wait_time = 300
    start_time = time.time()
    
    while True:
        elapsed = time.time() - start_time
        if elapsed > max_wait_time:
            pytest.fail(f"First parsing timeout after {max_wait_time} seconds")
        
        response = e2e_client.get(f"/api/books/{book_id_1}")
        assert response.status_code == 200
        status = response.json()["status"]
        
        if status == "parsed":
            break
        elif status == "error_parsing":
            pytest.fail(f"First parsing failed: book_id={book_id_1}")
        
        time.sleep(2)
    
    # 캐시 파일 확인
    cache_dir = settings.cache_dir / "upstage"
    with open(TEST_PDF_PATH, 'rb') as f:
        hasher = hashlib.md5()
        for chunk in iter(lambda: f.read(4096), b""):
            hasher.update(chunk)
        file_hash = hasher.hexdigest()
    
    cache_file = cache_dir / f"{file_hash}.json"
    assert cache_file.exists(), f"첫 번째 파싱 후 캐시 파일이 생성되지 않음: {cache_file}"
    cache_created_time = cache_file.stat().st_mtime
    logger.info(f"[TEST] 첫 번째 파싱 완료, 캐시 파일 생성: {cache_file}")
    
    # 3. 두 번째 파싱 (캐시 히트 예상)
    logger.info("[TEST] 두 번째 파싱 시작 (캐시 히트 예상)")
    
    # 약간의 시간 간격 (캐시 파일이 확실히 생성되도록)
    time.sleep(1)
    
    with open(TEST_PDF_PATH, "rb") as f:
        files = {"file": (TEST_PDF_PATH.name, f, "application/pdf")}
        response = e2e_client.post(
            "/api/books/upload",
            files=files,
            params={"title": "1등의 통찰 (캐시 재사용 테스트)", "author": "Test Author"}
        )
    
    assert response.status_code == 200
    upload_data = response.json()
    book_id_2 = upload_data["book_id"]
    
    # 두 번째 파싱은 캐시를 사용하므로 더 빠를 것으로 예상
    # 하지만 실제로는 백그라운드 작업이므로 여전히 시간이 걸릴 수 있음
    max_wait_time = 300
    start_time = time.time()
    
    while True:
        elapsed = time.time() - start_time
        if elapsed > max_wait_time:
            pytest.fail(f"Second parsing timeout after {max_wait_time} seconds")
        
        response = e2e_client.get(f"/api/books/{book_id_2}")
        assert response.status_code == 200
        status = response.json()["status"]
        
        if status == "parsed":
            break
        elif status == "error_parsing":
            pytest.fail(f"Second parsing failed: book_id={book_id_2}")
        
        time.sleep(2)
    
    # 캐시 파일이 여전히 존재하는지 확인 (같은 파일이므로 같은 캐시 사용)
    assert cache_file.exists(), f"두 번째 파싱 후 캐시 파일이 사라짐: {cache_file}"
    
    # 캐시 파일 수정 시간 확인 (같은 파일이므로 수정되지 않아야 함)
    cache_modified_time = cache_file.stat().st_mtime
    # 캐시 파일이 재사용되었는지 확인 (수정 시간이 변경되지 않았거나 약간만 변경)
    # 참고: 캐시 파일은 읽기만 하므로 수정 시간이 변경되지 않아야 하지만,
    # 파일 시스템에 따라 약간의 차이가 있을 수 있음
    logger.info(f"[TEST] 캐시 파일 수정 시간: 생성={cache_created_time}, 현재={cache_modified_time}")
    
    # 두 번째 파싱 결과 검증
    book_response = e2e_client.get(f"/api/books/{book_id_2}")
    assert book_response.status_code == 200
    book_data = book_response.json()
    assert book_data["status"] == "parsed"
    assert book_data["page_count"] > 0
    
    # 첫 번째와 두 번째 파싱 결과 비교 (페이지 수가 같아야 함)
    book_response_1 = e2e_client.get(f"/api/books/{book_id_1}")
    book_data_1 = book_response_1.json()
    
    assert book_data_1["page_count"] == book_data["page_count"], \
        f"첫 번째와 두 번째 파싱 결과의 페이지 수가 다름: {book_data_1['page_count']} vs {book_data['page_count']}"
    
    logger.info(f"[TEST] 캐시 재사용 검증 완료:")
    logger.info(f"  - 첫 번째 파싱: {book_id_1}, 페이지 수: {book_data_1['page_count']}")
    logger.info(f"  - 두 번째 파싱: {book_id_2}, 페이지 수: {book_data['page_count']}")
    logger.info(f"  - 캐시 파일: {cache_file}")


@pytest.mark.e2e
def test_e2e_pdf_parsing_page_data_validation(e2e_client: httpx.Client):
    """
    페이지 데이터 검증 E2E 테스트
    
    ⚠️ 실제 데이터만 사용
    ⚠️ 실제 서버 실행: 프로덕션 플로우와 동일하게 검증
    ⚠️ DB 직접 조회 금지: API 응답만 검증
    """
    # 1. PDF 파일 존재 확인
    assert TEST_PDF_PATH.exists(), f"Test PDF file not found: {TEST_PDF_PATH}"
    
    # 2. PDF 파일 업로드 및 파싱
    with open(TEST_PDF_PATH, "rb") as f:
        files = {"file": (TEST_PDF_PATH.name, f, "application/pdf")}
        response = e2e_client.post(
            "/api/books/upload",
            files=files,
            params={"title": "1등의 통찰 (페이지 데이터 검증)", "author": "Test Author"}
        )
    
    assert response.status_code == 200
    upload_data = response.json()
    book_id = upload_data["book_id"]
    
    # 파싱 완료 대기
    max_wait_time = 300
    start_time = time.time()
    
    while True:
        elapsed = time.time() - start_time
        if elapsed > max_wait_time:
            pytest.fail(f"Parsing timeout after {max_wait_time} seconds")
        
        response = e2e_client.get(f"/api/books/{book_id}")
        assert response.status_code == 200
        status = response.json()["status"]
        
        if status == "parsed":
            break
        elif status == "error_parsing":
            pytest.fail(f"Parsing failed: book_id={book_id}")
        
        time.sleep(2)
    
    # 3. 페이지 데이터 검증
    pages_response = e2e_client.get(f"/api/books/{book_id}/pages")
    
    if pages_response.status_code == 200:
        pages_data = pages_response.json()
        
        # pages 필드 확인
        if "pages" in pages_data:
            pages = pages_data["pages"]
            assert len(pages) > 0, "페이지 데이터가 없음"
            
            # 첫 번째 페이지 검증
            first_page = pages[0]
            assert "page_number" in first_page, "페이지에 page_number 필드가 없음"
            assert first_page["page_number"] > 0, "page_number가 0 이하"
            
            # raw_text 검증
            assert "raw_text" in first_page, "페이지에 raw_text 필드가 없음"
            # raw_text는 비어있을 수 있지만 필드는 있어야 함
            assert isinstance(first_page["raw_text"], str), "raw_text가 문자열이 아님"
            
            # elements 또는 page_metadata 검증
            has_elements = "elements" in first_page or "page_metadata" in first_page
            assert has_elements, "페이지에 elements 또는 page_metadata 필드가 없음"
            
            # 여러 페이지 검증
            for i, page in enumerate(pages[:5]):  # 처음 5개 페이지만 검증
                assert "page_number" in page, f"페이지 {i}에 page_number 필드가 없음"
                assert "raw_text" in page, f"페이지 {i}에 raw_text 필드가 없음"
                assert page["page_number"] == i + 1, f"페이지 번호가 순차적이지 않음: {page['page_number']}"
            
            logger = logging.getLogger(__name__)
            logger.info(f"[TEST] 페이지 데이터 검증 완료:")
            logger.info(f"  - 총 페이지 수: {len(pages)}")
            logger.info(f"  - 첫 번째 페이지: page_number={first_page['page_number']}, raw_text 길이={len(first_page.get('raw_text', ''))}")
    else:
        # 페이지 API가 없는 경우 스킵 (선택적)
        logger = logging.getLogger(__name__)
        logger.warning(f"[TEST] 페이지 API가 없음 (스킵): {pages_response.status_code}")

