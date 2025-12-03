"""
테스트용 도서 샘플 선정 스크립트

챕터 6개 이상인 도서를 각 분야별로 가나다순 정렬하여 첫 번째 책을 선정합니다.
"""
import json
import logging
from pathlib import Path
from sqlalchemy import func
from backend.api.models.book import Book, Chapter
from backend.api.database import SessionLocal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def select_test_books():
    """
    테스트용 도서 샘플 선정
    
    조건:
    - 챕터 6개 이상
    - 각 분야별로 첫 번째 책 (가나다순)
    
    Returns:
        선정된 도서 정보 딕셔너리
    """
    # DB 연결
    db = SessionLocal()
    
    try:
        # 분야 목록
        categories = ["역사/사회", "경제/경영", "인문/자기계발", "과학/기술"]
        
        selected_books = {}
        
        for category in categories:
            logger.info(f"[INFO] Processing category: {category}")
            
            # 해당 분야의 챕터 6개 이상인 도서 조회 (가나다순)
            books_with_chapters = (
                db.query(
                    Book.id,
                    Book.title,
                    Book.category,
                    func.count(Chapter.id).label("chapter_count")
                )
                .join(Chapter, Book.id == Chapter.book_id)
                .filter(Book.category == category)
                .group_by(Book.id)
                .having(func.count(Chapter.id) >= 6)
                .order_by(Book.title)  # 가나다순 정렬
                .all()
            )
            
            if books_with_chapters:
                # 첫 번째 책 선정
                first_book = books_with_chapters[0]
                
                selected_books[category] = {
                    "book_id": first_book.id,
                    "title": first_book.title,
                    "chapter_count": first_book.chapter_count,
                }
                
                logger.info(
                    f"[INFO] Selected for {category}: "
                    f"ID={first_book.id}, Title={first_book.title}, "
                    f"Chapters={first_book.chapter_count}"
                )
                
                # 해당 분야의 전체 후보 출력 (참고용)
                logger.info(f"[INFO] Total candidates for {category}: {len(books_with_chapters)}")
                for idx, book in enumerate(books_with_chapters[:5], 1):
                    logger.info(
                        f"  {idx}. ID={book.id}, Title={book.title}, "
                        f"Chapters={book.chapter_count}"
                    )
            else:
                logger.warning(f"[WARNING] No books with 6+ chapters found for {category}")
        
        # 결과 저장
        output_dir = Path("data/output/test_samples")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / "test_books_list.json"
        
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(selected_books, f, ensure_ascii=False, indent=2)
        
        logger.info(f"[INFO] Test books list saved to {output_file}")
        
        # 요약 출력
        logger.info("\n[SUMMARY] Selected test books:")
        for category, book_info in selected_books.items():
            logger.info(
                f"  {category}: {book_info['title']} "
                f"(ID={book_info['book_id']}, Chapters={book_info['chapter_count']})"
            )
        
        return selected_books
    
    finally:
        db.close()


if __name__ == "__main__":
    logger.info("[INFO] Starting test book selection...")
    selected_books = select_test_books()
    logger.info(f"[INFO] Selected {len(selected_books)} books across {len(selected_books)} categories")

