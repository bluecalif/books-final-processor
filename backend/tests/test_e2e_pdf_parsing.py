"""PDF 파싱 E2E 테스트 (실제 데이터만 사용, Mock 사용 금지, 실제 서버 실행)"""
import pytest
import time
from pathlib import Path
import httpx
from backend.api.models.book import Book, Page, BookStatus

# 실제 PDF 파일 경로
TEST_PDF_PATH = Path(__file__).parent.parent.parent / "data" / "input" / "1등의 통찰.pdf"


@pytest.mark.e2e
def test_e2e_pdf_parsing_full_flow(e2e_client: httpx.Client, db_session):
    """
    전체 PDF 파싱 플로우 E2E 테스트
    
    ⚠️ 실제 데이터만 사용: 실제 PDF 파일, 실제 Upstage API, 실제 DB
    ⚠️ 실제 서버 실행: 프로덕션 플로우와 동일하게 검증
    Mock 사용 절대 금지
    """
    # 1. PDF 파일 존재 확인
    assert TEST_PDF_PATH.exists(), f"Test PDF file not found: {TEST_PDF_PATH}"
    
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
    
    # 3. 업로드된 책 상태 확인
    book_response = e2e_client.get(f"/api/books/{book_id}")
    assert book_response.status_code == 200
    book_data = book_response.json()
    assert book_data["status"] == "uploaded"
    assert book_data["title"] == "1등의 통찰"
    
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
    
    # 5. 파싱 결과 검증 (HTTP 응답으로)
    book_response = e2e_client.get(f"/api/books/{book_id}")
    assert book_response.status_code == 200
    book_data = book_response.json()
    assert book_data["status"] == "parsed"
    assert book_data["page_count"] is not None
    assert book_data["page_count"] > 0
    
    # DB에서도 검증
    book = db_session.query(Book).filter(Book.id == book_id).first()
    assert book is not None
    assert book.status == BookStatus.PARSED
    assert book.page_count == book_data["page_count"]
    
    # 6. Pages 테이블 데이터 검증
    pages = db_session.query(Page).filter(Page.book_id == book_id).all()
    assert len(pages) == book.page_count
    
    # 각 페이지 검증
    for page in pages:
        assert page.book_id == book_id
        assert page.page_number >= 1
        assert page.raw_text is not None or page.raw_text == ""  # 빈 페이지도 가능
    
    # 페이지 번호 순서 확인
    page_numbers = [p.page_number for p in pages]
    assert page_numbers == sorted(page_numbers), "페이지 번호가 정렬되지 않음"
    assert page_numbers == list(range(1, len(pages) + 1)), "페이지 번호가 1부터 연속적이지 않음"
    
    # 7. 최종 검증: API 응답과 DB 데이터 일치 확인
    assert book_data["page_count"] == len(pages)


@pytest.mark.e2e
def test_e2e_pdf_parsing_status_transition(e2e_client: httpx.Client, db_session):
    """
    상태 변경 검증 E2E 테스트 (uploaded → parsed)
    
    ⚠️ 실제 데이터만 사용
    ⚠️ 실제 서버 실행: 프로덕션 플로우와 동일하게 검증
    """
    # 1. PDF 파일 업로드
    assert TEST_PDF_PATH.exists(), f"Test PDF file not found: {TEST_PDF_PATH}"
    
    with open(TEST_PDF_PATH, "rb") as f:
        files = {"file": (TEST_PDF_PATH.name, f, "application/pdf")}
        response = e2e_client.post(
            "/api/books/upload",
            files=files
        )
    
    assert response.status_code == 200
    book_id = response.json()["book_id"]
    
    # 2. 초기 상태 확인 (uploaded) - HTTP 요청으로
    response = e2e_client.get(f"/api/books/{book_id}")
    assert response.status_code == 200
    assert response.json()["status"] == "uploaded"
    
    # 3. 백그라운드 작업 검증 (프로덕션 플로우와 동일)
    # 실제 HTTP 요청으로 상태를 폴링하여 백그라운드 작업 완료 확인
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
    
    # 4. 상태 변경 확인 (parsed) - HTTP 응답으로
    final_response = e2e_client.get(f"/api/books/{book_id}")
    assert final_response.status_code == 200
    final_data = final_response.json()
    assert final_data["status"] == "parsed"
    assert final_data["page_count"] is not None
    assert final_data["page_count"] > 0
    
    # 5. DB에서도 검증
    book = db_session.query(Book).filter(Book.id == book_id).first()
    assert book.status == BookStatus.PARSED
    assert book.page_count == final_data["page_count"]
