"""
API 계약 검증 테스트 (Phase 7.2)

모든 API 엔드포인트의 응답 스키마를 검증합니다:
- Pydantic 스키마와 실제 응답 일치
- Enum 값 정합성 (BookStatus 등)
- 필드명/타입 일치
- 필수 필드 존재
"""
import pytest
import httpx
from typing import Dict, Any, List
from backend.api.models.book import BookStatus
from backend.api.schemas.book import (
    BookResponse,
    BookListResponse,
    PageSummaryResponse,
    ChapterSummaryResponse,
)

pytestmark = pytest.mark.e2e


def validate_book_status(status: str) -> bool:
    """BookStatus Enum 값 검증"""
    valid_statuses = {s.value for s in BookStatus}
    return status in valid_statuses


def validate_book_response(data: Dict[str, Any]) -> bool:
    """
    BookResponse 스키마 검증
    
    Args:
        data: API 응답 데이터
        
    Returns:
        검증 성공 여부
    """
    try:
        # Pydantic 모델로 검증
        book = BookResponse.model_validate(data)
        
        # Enum 값 검증
        assert validate_book_status(book.status.value), f"Invalid BookStatus: {book.status.value}"
        
        # 필수 필드 확인
        assert book.id is not None
        assert book.source_file_path is not None
        assert book.status is not None
        assert book.created_at is not None
        assert book.updated_at is not None
        
        return True
    except Exception as e:
        pytest.fail(f"BookResponse validation failed: {e}")


def validate_book_list_response(data: Dict[str, Any]) -> bool:
    """BookListResponse 스키마 검증"""
    try:
        response = BookListResponse.model_validate(data)
        
        # books 리스트 검증
        assert isinstance(response.books, list)
        for book in response.books:
            validate_book_response(book.model_dump())
        
        # total 필드 검증
        assert isinstance(response.total, int)
        assert response.total >= 0
        assert response.total == len(response.books)
        
        return True
    except Exception as e:
        pytest.fail(f"BookListResponse validation failed: {e}")


def validate_page_summary_response(data: Dict[str, Any]) -> bool:
    """PageSummaryResponse 스키마 검증"""
    try:
        page = PageSummaryResponse.model_validate(data)
        
        # 필수 필드 확인
        assert page.id is not None
        assert page.book_id is not None
        assert page.page_number is not None
        assert page.summary_text is not None
        assert page.created_at is not None
        
        return True
    except Exception as e:
        pytest.fail(f"PageSummaryResponse validation failed: {e}")


def validate_chapter_summary_response(data: Dict[str, Any]) -> bool:
    """ChapterSummaryResponse 스키마 검증"""
    try:
        chapter = ChapterSummaryResponse.model_validate(data)
        
        # 필수 필드 확인
        assert chapter.id is not None
        assert chapter.book_id is not None
        assert chapter.chapter_id is not None
        assert chapter.summary_text is not None
        assert chapter.created_at is not None
        
        return True
    except Exception as e:
        pytest.fail(f"ChapterSummaryResponse validation failed: {e}")


@pytest.mark.e2e
def test_health_endpoint(e2e_client: httpx.Client):
    """헬스체크 엔드포인트 검증"""
    response = e2e_client.get("/health")
    assert response.status_code == 200
    
    data = response.json()
    assert isinstance(data, dict)
    # 헬스체크 응답 형식은 프로젝트에 따라 다를 수 있음


@pytest.mark.e2e
def test_get_books_list(e2e_client: httpx.Client):
    """GET /api/books - 책 리스트 조회"""
    response = e2e_client.get("/api/books")
    assert response.status_code == 200
    
    data = response.json()
    validate_book_list_response(data)


@pytest.mark.e2e
def test_get_book_by_id(e2e_client: httpx.Client):
    """GET /api/books/{id} - 책 상세 조회"""
    # 먼저 책 리스트에서 첫 번째 책 ID 가져오기
    list_response = e2e_client.get("/api/books")
    assert list_response.status_code == 200
    books_data = list_response.json()
    
    if not books_data.get("books"):
        pytest.skip("No books available for testing")
    
    book_id = books_data["books"][0]["id"]
    
    # 책 상세 조회
    response = e2e_client.get(f"/api/books/{book_id}")
    assert response.status_code == 200
    
    data = response.json()
    validate_book_response(data)


@pytest.mark.e2e
def test_get_book_not_found(e2e_client: httpx.Client):
    """GET /api/books/{id} - 존재하지 않는 책 조회 (404)"""
    response = e2e_client.get("/api/books/999999")
    assert response.status_code == 404
    
    data = response.json()
    assert "detail" in data


@pytest.mark.e2e
def test_get_structure_candidates(e2e_client: httpx.Client):
    """GET /api/books/{id}/structure/candidates - 구조 후보 조회"""
    # parsed 상태인 책 찾기
    list_response = e2e_client.get("/api/books")
    assert list_response.status_code == 200
    books_data = list_response.json()
    
    parsed_book = None
    for book in books_data.get("books", []):
        if book.get("status") in ["parsed", "structured"]:
            parsed_book = book
            break
    
    if not parsed_book:
        pytest.skip("No parsed/structured books available for testing")
    
    book_id = parsed_book["id"]
    
    response = e2e_client.get(f"/api/books/{book_id}/structure/candidates")
    assert response.status_code == 200
    
    data = response.json()
    assert isinstance(data, dict)
    assert "auto_candidates" in data
    assert isinstance(data["auto_candidates"], list)


@pytest.mark.e2e
def test_get_page_entities(e2e_client: httpx.Client):
    """GET /api/books/{id}/pages - 페이지 엔티티 리스트 조회"""
    # page_summarized 상태인 책 찾기
    list_response = e2e_client.get("/api/books")
    assert list_response.status_code == 200
    books_data = list_response.json()
    
    summarized_book = None
    for book in books_data.get("books", []):
        if book.get("status") in ["page_summarized", "summarized"]:
            summarized_book = book
            break
    
    if not summarized_book:
        pytest.skip("No page_summarized/summarized books available for testing")
    
    book_id = summarized_book["id"]
    
    response = e2e_client.get(f"/api/books/{book_id}/pages")
    assert response.status_code == 200
    
    data = response.json()
    assert isinstance(data, list)
    
    # 각 페이지 엔티티 검증
    for page_data in data:
        validate_page_summary_response(page_data)


@pytest.mark.e2e
def test_get_page_entity(e2e_client: httpx.Client):
    """GET /api/books/{id}/pages/{page_number} - 페이지 엔티티 상세 조회"""
    # page_summarized 상태인 책 찾기
    list_response = e2e_client.get("/api/books")
    assert list_response.status_code == 200
    books_data = list_response.json()
    
    summarized_book = None
    for book in books_data.get("books", []):
        if book.get("status") in ["page_summarized", "summarized"]:
            summarized_book = book
            break
    
    if not summarized_book:
        pytest.skip("No page_summarized/summarized books available for testing")
    
    book_id = summarized_book["id"]
    
    # 페이지 리스트에서 첫 번째 페이지 번호 가져오기
    pages_response = e2e_client.get(f"/api/books/{book_id}/pages")
    assert pages_response.status_code == 200
    pages_data = pages_response.json()
    
    if not pages_data:
        pytest.skip("No page entities available for testing")
    
    page_number = pages_data[0]["page_number"]
    
    # 페이지 상세 조회
    response = e2e_client.get(f"/api/books/{book_id}/pages/{page_number}")
    assert response.status_code == 200
    
    data = response.json()
    validate_page_summary_response(data)


@pytest.mark.e2e
def test_get_chapter_entities(e2e_client: httpx.Client):
    """GET /api/books/{id}/chapters - 챕터 엔티티 리스트 조회"""
    # summarized 상태인 책 찾기
    list_response = e2e_client.get("/api/books")
    assert list_response.status_code == 200
    books_data = list_response.json()
    
    summarized_book = None
    for book in books_data.get("books", []):
        if book.get("status") == "summarized":
            summarized_book = book
            break
    
    if not summarized_book:
        pytest.skip("No summarized books available for testing")
    
    book_id = summarized_book["id"]
    
    response = e2e_client.get(f"/api/books/{book_id}/chapters")
    assert response.status_code == 200
    
    data = response.json()
    assert isinstance(data, list)
    
    # 각 챕터 엔티티 검증
    for chapter_data in data:
        validate_chapter_summary_response(chapter_data)


@pytest.mark.e2e
def test_get_chapter_entity(e2e_client: httpx.Client):
    """GET /api/books/{id}/chapters/{chapter_id} - 챕터 엔티티 상세 조회"""
    # summarized 상태인 책 찾기
    list_response = e2e_client.get("/api/books")
    assert list_response.status_code == 200
    books_data = list_response.json()
    
    summarized_book = None
    for book in books_data.get("books", []):
        if book.get("status") == "summarized":
            summarized_book = book
            break
    
    if not summarized_book:
        pytest.skip("No summarized books available for testing")
    
    book_id = summarized_book["id"]
    
    # 챕터 리스트에서 첫 번째 챕터 ID 가져오기
    chapters_response = e2e_client.get(f"/api/books/{book_id}/chapters")
    assert chapters_response.status_code == 200
    chapters_data = chapters_response.json()
    
    if not chapters_data:
        pytest.skip("No chapter entities available for testing")
    
    chapter_id = chapters_data[0]["chapter_id"]
    
    # 챕터 상세 조회
    response = e2e_client.get(f"/api/books/{book_id}/chapters/{chapter_id}")
    assert response.status_code == 200
    
    data = response.json()
    validate_chapter_summary_response(data)


@pytest.mark.e2e
def test_book_status_enum_values(e2e_client: httpx.Client):
    """BookStatus Enum 값 정합성 검증"""
    response = e2e_client.get("/api/books")
    assert response.status_code == 200
    
    books_data = response.json()
    valid_statuses = {s.value for s in BookStatus}
    
    for book in books_data.get("books", []):
        status = book.get("status")
        assert status in valid_statuses, f"Invalid BookStatus: {status} (book_id={book.get('id')})"
    
    print(f"[TEST] ✅ BookStatus Enum 값 정합성 검증 완료: {len(books_data.get('books', []))}개 책 검증")


@pytest.mark.e2e
def test_response_field_names(e2e_client: httpx.Client):
    """응답 필드명 검증 (snake_case 유지)"""
    response = e2e_client.get("/api/books")
    assert response.status_code == 200
    
    books_data = response.json()
    
    if not books_data.get("books"):
        pytest.skip("No books available for testing")
    
    book = books_data["books"][0]
    
    # 필드명이 snake_case인지 확인 (camelCase가 아닌지)
    expected_fields = {
        "id", "title", "author", "category", "source_file_path",
        "page_count", "status", "structure_data", "created_at", "updated_at"
    }
    
    actual_fields = set(book.keys())
    
    # 예상 필드가 모두 있는지 확인
    for field in expected_fields:
        assert field in actual_fields, f"Missing field: {field}"
    
    # camelCase 필드가 없는지 확인
    camel_case_fields = [f for f in actual_fields if any(c.isupper() for c in f if c.isalpha())]
    assert len(camel_case_fields) == 0, f"Found camelCase fields: {camel_case_fields}"
    
    print(f"[TEST] ✅ 응답 필드명 검증 완료: snake_case 유지 확인")


@pytest.mark.e2e
def test_response_field_types(e2e_client: httpx.Client):
    """응답 필드 타입 검증"""
    response = e2e_client.get("/api/books")
    assert response.status_code == 200
    
    books_data = response.json()
    
    if not books_data.get("books"):
        pytest.skip("No books available for testing")
    
    book = books_data["books"][0]
    
    # 타입 검증
    assert isinstance(book["id"], int)
    assert book["title"] is None or isinstance(book["title"], str)
    assert book["author"] is None or isinstance(book["author"], str)
    assert book["category"] is None or isinstance(book["category"], str)
    assert isinstance(book["source_file_path"], str)
    assert book["page_count"] is None or isinstance(book["page_count"], int)
    assert isinstance(book["status"], str)
    assert book["structure_data"] is None or isinstance(book["structure_data"], dict)
    assert isinstance(book["created_at"], str)  # ISO 8601 문자열
    assert isinstance(book["updated_at"], str)  # ISO 8601 문자열
    
    print(f"[TEST] ✅ 응답 필드 타입 검증 완료")

