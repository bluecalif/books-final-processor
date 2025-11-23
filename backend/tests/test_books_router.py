"""Books API 통합 테스트"""
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from backend.api.models.book import BookStatus


def test_upload_book_success(client: TestClient, tmp_path: Path):
    """PDF 업로드 통합 테스트"""
    # 임시 PDF 파일 생성 (실제 PDF가 아니지만 테스트용)
    test_pdf = tmp_path / "test.pdf"
    test_pdf.write_bytes(b"%PDF-1.4\nfake pdf content")
    
    with open(test_pdf, "rb") as f:
        response = client.post(
            "/api/books/upload",
            files={"file": ("test.pdf", f, "application/pdf")},
            params={"title": "Test Book", "author": "Test Author"}
        )
    
    assert response.status_code == 200
    data = response.json()
    assert "book_id" in data
    assert data["status"] == "uploaded"
    
    # DB 검증
    book_response = client.get(f"/api/books/{data['book_id']}")
    assert book_response.status_code == 200
    book_data = book_response.json()
    assert book_data["title"] == "Test Book"
    assert book_data["author"] == "Test Author"
    assert book_data["status"] == "uploaded"


def test_upload_book_invalid_format(client: TestClient, tmp_path: Path):
    """잘못된 파일 형식 업로드 테스트"""
    test_file = tmp_path / "test.txt"
    test_file.write_text("not a pdf")
    
    with open(test_file, "rb") as f:
        response = client.post(
            "/api/books/upload",
            files={"file": ("test.txt", f, "text/plain")}
        )
    
    assert response.status_code == 400
    assert "PDF" in response.json()["detail"]


def test_get_books_list(client: TestClient, db_session):
    """책 리스트 조회 테스트"""
    from backend.api.models.book import Book
    
    # 테스트 데이터 생성
    book1 = Book(
        title="Book 1",
        source_file_path="/path/to/book1.pdf",
        status=BookStatus.UPLOADED
    )
    book2 = Book(
        title="Book 2",
        source_file_path="/path/to/book2.pdf",
        status=BookStatus.PARSED
    )
    db_session.add_all([book1, book2])
    db_session.commit()
    
    # 리스트 조회
    response = client.get("/api/books")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 2
    assert len(data["books"]) >= 2


def test_get_books_with_status_filter(client: TestClient, db_session):
    """상태 필터로 책 리스트 조회 테스트"""
    from backend.api.models.book import Book
    
    # 테스트 데이터 생성
    book = Book(
        title="Filtered Book",
        source_file_path="/path/to/book.pdf",
        status=BookStatus.PARSED
    )
    db_session.add(book)
    db_session.commit()
    
    # 상태 필터 적용
    response = client.get("/api/books", params={"status": "parsed"})
    assert response.status_code == 200
    data = response.json()
    assert all(b["status"] == "parsed" for b in data["books"])


def test_get_book_not_found(client: TestClient):
    """존재하지 않는 책 조회 테스트"""
    response = client.get("/api/books/99999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()

