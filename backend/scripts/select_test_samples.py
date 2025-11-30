"""
E2E 테스트용 샘플 도서 선정 스크립트

챕터 수 6개 이상인 도서 중 분야별로 파일명 가나다순 상위 1개씩 선정
"""
import json
import logging
from pathlib import Path
from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.api.database import SessionLocal
from backend.api.models.book import Book, Chapter

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def select_test_samples() -> dict:
    """
    테스트 샘플 도서 선정

    Returns:
        선정된 샘플 도서 정보 딕셔너리
    """
    db: Session = SessionLocal()
    
    try:
        # 1. 챕터 수 6개 이상인 도서 조회
        logger.info("[INFO] Querying books with 6+ chapters...")
        
        # 챕터 수가 6개 이상인 book_id 조회
        books_with_6plus_chapters = (
            db.query(Chapter.book_id)
            .group_by(Chapter.book_id)
            .having(func.count(Chapter.id) >= 6)
            .all()
        )
        
        book_ids = [row[0] for row in books_with_6plus_chapters]
        logger.info(f"[INFO] Found {len(book_ids)} books with 6+ chapters")
        
        if not book_ids:
            logger.warning("[WARNING] No books found with 6+ chapters")
            return {"samples": [], "total_books": 0}
        
        # 2. 도서 정보 조회
        books = db.query(Book).filter(Book.id.in_(book_ids)).all()
        
        # 3. 분야별로 그룹화
        books_by_category = {}
        for book in books:
            category = book.category or "미분류"
            if category not in books_by_category:
                books_by_category[category] = []
            books_by_category[category].append(book)
        
        logger.info(f"[INFO] Books by category: {[(cat, len(books)) for cat, books in books_by_category.items()]}")
        
        # 4. 각 분야에서 파일명 가나다순 상위 1개 선정
        selected_samples = []
        target_categories = ["역사/사회", "경제/경영", "인문/자기계발", "과학/기술"]
        
        for category in target_categories:
            if category not in books_by_category:
                logger.warning(f"[WARNING] No books found in category: {category}")
                continue
            
            books_in_category = books_by_category[category]
            
            # 파일명 기준으로 정렬 (가나다순)
            books_sorted = sorted(
                books_in_category,
                key=lambda b: Path(b.source_file_path).stem if b.source_file_path else ""
            )
            
            selected_book = books_sorted[0]
            
            # 챕터 수 확인
            chapter_count = (
                db.query(Chapter)
                .filter(Chapter.book_id == selected_book.id)
                .count()
            )
            
            selected_samples.append({
                "book_id": selected_book.id,
                "title": selected_book.title,
                "author": selected_book.author,
                "category": selected_book.category,
                "source_file_path": selected_book.source_file_path,
                "chapter_count": chapter_count,
                "status": selected_book.status.value if selected_book.status else None,
            })
            
            logger.info(
                f"[INFO] Selected from {category}: "
                f"book_id={selected_book.id}, title={selected_book.title}, "
                f"chapters={chapter_count}, file={Path(selected_book.source_file_path).name if selected_book.source_file_path else 'N/A'}"
            )
        
        result = {
            "samples": selected_samples,
            "total_books_with_6plus_chapters": len(book_ids),
            "selected_count": len(selected_samples),
        }
        
        return result
        
    finally:
        db.close()


def main():
    """메인 함수"""
    logger.info("[INFO] Starting test sample selection...")
    
    # 샘플 선정
    result = select_test_samples()
    
    # 결과 저장
    from backend.config.settings import settings
    output_dir = settings.output_dir / "test_samples"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_file = output_dir / "selected_samples.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    logger.info(f"[INFO] Test samples saved to {output_file}")
    logger.info(f"[INFO] Selected {result['selected_count']} books for testing")
    
    # 콘솔 출력
    print("\n" + "=" * 80)
    print("Selected Test Samples")
    print("=" * 80)
    for sample in result["samples"]:
        print(f"\nBook ID: {sample['book_id']}")
        print(f"  Title: {sample['title']}")
        print(f"  Category: {sample['category']}")
        print(f"  Chapters: {sample['chapter_count']}")
        print(f"  File: {Path(sample['source_file_path']).name if sample['source_file_path'] else 'N/A'}")
        print(f"  Status: {sample['status']}")
    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()

