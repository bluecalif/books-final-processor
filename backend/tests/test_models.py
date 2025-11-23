"""데이터 모델 테스트"""
from datetime import datetime
from backend.api.models.book import Book, Page, Chapter, BookStatus
from backend.api.database import Base, engine, SessionLocal


def test_book_creation():
    """Book 모델 생성 테스트"""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    try:
        book = Book(
            title="테스트 책",
            author="테스트 저자",
            source_file_path="/path/to/test.pdf",
            page_count=100,
            status=BookStatus.UPLOADED,
        )
        db.add(book)
        db.commit()
        db.refresh(book)
        
        assert book.id is not None
        assert book.title == "테스트 책"
        assert book.status == BookStatus.UPLOADED
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)

