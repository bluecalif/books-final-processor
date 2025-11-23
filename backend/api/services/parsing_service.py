"""PDF 파싱 서비스"""
import logging
from pathlib import Path
from sqlalchemy.orm import Session
from backend.api.models.book import Book, Page, BookStatus
from backend.parsers.pdf_parser import PDFParser
from backend.config.settings import settings

logger = logging.getLogger(__name__)


class ParsingService:
    """PDF 파싱 서비스 클래스"""

    def __init__(self, db: Session):
        """
        Args:
            db: 데이터베이스 세션
        """
        logger.info("=" * 80)
        logger.info("[FUNCTION] ParsingService.__init__ 호출됨")
        db_id = id(db)
        logger.info(f"[PARAM] db 파라미터: session_id={db_id}")
        logger.info(f"[STATE] db의 bind: {id(db.bind)}")
        self.db = db
        self.pdf_parser = PDFParser(api_key=settings.upstage_api_key)
        logger.info(f"[STATE] self.db 설정 완료: session_id={db_id}")
        logger.info(f"[STATE] PDFParser 초기화 완료")
        logger.info("=" * 80)

    def parse_book(self, book_id: int) -> Book:
        """
        책의 PDF 파일을 파싱하고 DB에 저장

        Args:
            book_id: 책 ID

        Returns:
            업데이트된 Book 객체
        """
        logger.info("=" * 80)
        logger.info("[FUNCTION] ParsingService.parse_book 호출됨")
        db_id = id(self.db)
        logger.info(f"[PARAM] book_id={book_id}")
        logger.info(f"[STATE] self.db: session_id={db_id}")

        # 책 조회
        logger.info("[CALL] self.db.query(Book) 호출 시작")
        logger.info(f"[PARAM] filter 조건: Book.id == {book_id}")
        book = self.db.query(Book).filter(Book.id == book_id).first()
        logger.info(f"[RETURN] query.first() 반환값: book={book}, book_id={book.id if book else None}")

        if not book:
            logger.info("[ERROR] 책을 찾을 수 없음")
            logger.info("=" * 80)
            raise ValueError(f"Book {book_id} not found")

        if book.status != BookStatus.UPLOADED:
            logger.info(f"[WARNING] 책 상태가 uploaded가 아님: status={book.status}")
            logger.info("=" * 80)
            raise ValueError(f"Book {book_id} is not in uploaded status. Current status: {book.status}")

        # PDF 파싱
        logger.info("[CALL] self.pdf_parser.parse_pdf() 호출 시작")
        logger.info(f"[PARAM] file_path={book.source_file_path}")
        parsed_data = self.pdf_parser.parse_pdf(book.source_file_path, use_cache=False)
        logger.info(f"[RETURN] parse_pdf() 반환값: pages 개수={len(parsed_data.get('pages', []))}, total_pages={parsed_data.get('total_pages', 0)}")

        # Pages 테이블에 저장
        logger.info("[CALL] Pages 테이블에 저장 시작")
        pages_data = parsed_data.get("pages", [])
        logger.info(f"[PARAM] pages_data 개수={len(pages_data)}")

        # 기존 페이지 삭제 (재파싱 시)
        logger.info("[CALL] 기존 페이지 삭제 시작")
        logger.info(f"[PARAM] book_id={book_id}")
        existing_pages = self.db.query(Page).filter(Page.book_id == book_id).all()
        logger.info(f"[RETURN] 기존 페이지 개수={len(existing_pages)}")
        for page in existing_pages:
            logger.info(f"[CALL] self.db.delete(page) 호출 시작")
            logger.info(f"[PARAM] page_id={page.id}")
            self.db.delete(page)
        logger.info("[RETURN] 기존 페이지 삭제 완료")

        # 새 페이지 생성
        logger.info("[CALL] 새 페이지 생성 시작")
        for idx, page_data in enumerate(pages_data):
            logger.info(f"[CALL] Page() 생성자 호출 시작 (인덱스 {idx})")
            logger.info(f"[PARAM] book_id={book_id}, page_number={page_data.get('page_number')}, raw_text 길이={len(page_data.get('raw_text', ''))}")
            page = Page(
                book_id=book_id,
                page_number=page_data.get("page_number"),
                raw_text=page_data.get("raw_text"),
                page_metadata={"elements": page_data.get("elements", [])} if page_data.get("elements") else None,
            )
            logger.info(f"[RETURN] Page() 반환값: page_id={getattr(page, 'id', None)}")
            logger.info("[CALL] self.db.add(page) 호출 시작")
            self.db.add(page)
            logger.info("[RETURN] self.db.add() 완료")
        logger.info(f"[RETURN] 모든 페이지 생성 완료: 총 {len(pages_data)}개")

        # 책 상태 업데이트
        logger.info("[CALL] 책 상태 업데이트 시작")
        logger.info(f"[PARAM] book_id={book_id}, status=PARSED, page_count={parsed_data.get('total_pages', 0)}")
        book.status = BookStatus.PARSED
        book.page_count = parsed_data.get("total_pages", 0)
        logger.info(f"[RETURN] 상태 업데이트 완료: status={book.status}, page_count={book.page_count}")

        # 커밋
        logger.info("[CALL] self.db.commit() 호출 시작")
        logger.info(f"[PARAM] commit() 파라미터 없음")
        self.db.commit()
        logger.info("[RETURN] self.db.commit() 완료")

        logger.info(f"[INFO] Book parsed: id={book.id}, status={book.status}, page_count={book.page_count}")
        logger.info("=" * 80)
        return book

