"""
DB 정리: text 파일과 매칭되는 책만 남기고 나머지 삭제

data/output/text 디렉토리의 JSON 파일에서 book_id를 추출하여
해당 책들만 남기고 나머지는 삭제합니다.
"""
import json
import logging
from pathlib import Path
from sqlalchemy.orm import Session

from backend.api.database import SessionLocal
from backend.api.models.book import Book

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def cleanup_db_keep_only_text_books():
    """text 파일과 매칭되는 책만 남기고 나머지 삭제"""
    text_dir = Path("data/output/text")
    
    if not text_dir.exists():
        logger.error(f"[ERROR] 텍스트 디렉토리가 없습니다: {text_dir}")
        return
    
    # 1. text 파일에서 book_id 추출
    text_files = list(text_dir.glob("*.json"))
    logger.info(f"[INFO] 텍스트 파일 {len(text_files)}개 발견")
    
    book_ids_from_text = set()
    for text_file in text_files:
        try:
            with open(text_file, 'r', encoding='utf-8') as f:
                text_data = json.load(f)
                book_id = text_data.get('book_id')
                if book_id:
                    book_ids_from_text.add(book_id)
                    logger.debug(f"[DEBUG] {text_file.name}: book_id={book_id}")
        except Exception as e:
            logger.error(f"[ERROR] {text_file.name} 읽기 실패: {e}")
    
    logger.info(f"[INFO] 텍스트 파일에서 추출한 book_id: {sorted(book_ids_from_text)}")
    
    # 2. DB에서 모든 책 조회
    db: Session = SessionLocal()
    
    try:
        all_books = db.query(Book).all()
        logger.info(f"[INFO] DB에 총 {len(all_books)}개 책 존재")
        
        # 3. 유지할 책과 삭제할 책 분류
        books_to_keep = []
        books_to_delete = []
        
        for book in all_books:
            if book.id in book_ids_from_text:
                books_to_keep.append(book)
            else:
                books_to_delete.append(book)
        
        logger.info(f"[INFO] 유지할 책: {len(books_to_keep)}개")
        logger.info(f"[INFO] 삭제할 책: {len(books_to_delete)}개")
        
        # 4. 삭제할 책 목록 출력
        if books_to_delete:
            logger.info("\n[INFO] 삭제할 책 목록:")
            for book in books_to_delete:
                logger.info(f"  ID {book.id}: {book.title} (파일: {Path(book.source_file_path).name if book.source_file_path else 'N/A'})")
        
        # 5. 삭제 실행
        if books_to_delete:
            logger.info("\n[INFO] 삭제 시작...")
            for book in books_to_delete:
                logger.info(f"[INFO] 삭제 중: ID {book.id} - {book.title}")
                db.delete(book)
            
            db.commit()
            logger.info(f"[INFO] 삭제 완료: {len(books_to_delete)}개 책 삭제됨")
        else:
            logger.info("[INFO] 삭제할 책이 없습니다.")
        
        # 6. 최종 상태 확인
        remaining_books = db.query(Book).all()
        logger.info(f"\n[INFO] 최종 남은 책: {len(remaining_books)}개")
        for book in sorted(remaining_books, key=lambda b: b.id):
            logger.info(f"  ID {book.id}: {book.title}")
        
    except Exception as e:
        logger.error(f"[ERROR] DB 정리 실패: {e}")
        db.rollback()
        raise
    
    finally:
        db.close()


if __name__ == "__main__":
    cleanup_db_keep_only_text_books()

