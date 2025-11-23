"""책 서비스"""
import logging
from pathlib import Path
from typing import Optional, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import inspect
from backend.api.models.book import Book, BookStatus
from backend.config.settings import settings

logger = logging.getLogger(__name__)


class BookService:
    """책 서비스 클래스"""

    def __init__(self, db: Session):
        logger.info("=" * 80)
        logger.info("[FUNCTION] BookService.__init__ 호출됨")
        db_id = id(db)
        logger.info(f"[PARAM] db 파라미터: session_id={db_id}")
        logger.info(f"[STATE] db의 bind: {id(db.bind)}")
        self.db = db
        logger.info(f"[STATE] self.db 설정 완료: session_id={db_id}")
        logger.info("=" * 80)

    def create_book(
        self, file_path: Path, title: Optional[str] = None, author: Optional[str] = None
    ) -> Book:
        """
        책 생성 (파일 저장 및 DB 레코드 생성)

        Args:
            file_path: 업로드된 파일 경로
            title: 책 제목 (선택)
            author: 저자 (선택)

        Returns:
            생성된 Book 객체
        """
        logger.info("=" * 80)
        logger.info("[FUNCTION] BookService.create_book 호출됨")
        db_id = id(self.db)
        logger.info(f"[PARAM] file_path={file_path}")
        logger.info(f"[PARAM] title={title}")
        logger.info(f"[PARAM] author={author}")
        logger.info(f"[STATE] self.db: session_id={db_id}")
        logger.info(f"[STATE] self.db의 bind: {id(self.db.bind)}")
        
        # 세션의 connection 확인
        logger.info("[CALL] self.db.connection() 호출 시작")
        logger.info(f"[PARAM] self.db.connection() 파라미터: session_id={db_id}")
        service_connection = self.db.connection()
        service_connection_id = id(service_connection)
        logger.info(f"[RETURN] self.db.connection() 반환값: connection_id={service_connection_id}")
        logger.info(f"[STATE] service_connection의 engine: {id(service_connection.engine)}")
        
        # 세션의 connection으로 테이블 확인
        logger.info("[CALL] inspect(service_connection) 호출 시작")
        logger.info(f"[PARAM] inspect() 파라미터: connection_id={service_connection_id}")
        service_inspector = inspect(service_connection)
        logger.info(f"[CALL] inspector.get_table_names() 호출 시작")
        service_tables = service_inspector.get_table_names()
        logger.info(f"[RETURN] get_table_names() 반환값: {service_tables}")
        expected_tables = ['books', 'chapter_summaries', 'chapters', 'page_summaries', 'pages']
        logger.info(f"[EXPECTED] Service connection 테이블 예상값: {expected_tables}")
        logger.info(f"[ACTUAL] Service connection 테이블 실제값: {service_tables}")
        logger.info(f"[COMPARE] 'books' in service_tables: {'books' in service_tables}")
        
        # 파일을 upload_dir로 이동
        logger.info("[CALL] saved_path 계산 시작")
        logger.info(f"[PARAM] settings.upload_dir={settings.upload_dir}, file_path.name={file_path.name}")
        saved_path = settings.upload_dir / file_path.name
        saved_path_str = str(saved_path)
        logger.info(f"[RETURN] saved_path 계산 완료: saved_path={saved_path_str}")
        
        logger.info("[CALL] if file_path != saved_path 조건 확인 시작")
        logger.info(f"[PARAM] file_path={file_path}, saved_path={saved_path_str}")
        logger.info(f"[COMPARE] file_path != saved_path: {file_path != saved_path}")
        if file_path != saved_path:
            logger.info("[COMPARE] 조건 True: 파일 이동 필요")
            import shutil
            logger.info(f"[CALL] shutil.move() 호출 시작")
            logger.info(f"[PARAM] src={file_path}, dst={saved_path}")
            shutil.move(str(file_path), str(saved_path))
            logger.info(f"[RETURN] shutil.move() 완료")
            logger.info(f"[INFO] File moved to {saved_path}")
        else:
            logger.info("[COMPARE] 조건 False: 파일 이동 불필요 (이미 올바른 위치)")

        # DB 레코드 생성
        logger.info("[CALL] Book() 생성자 호출 시작")
        logger.info(f"[PARAM] title={title}, author={author}, source_file_path={saved_path}, status=UPLOADED")
        book = Book(
            title=title,
            author=author,
            source_file_path=str(saved_path),
            status=BookStatus.UPLOADED,
        )
        book_id_before = getattr(book, 'id', None)
        logger.info(f"[RETURN] Book() 반환값: book_id={book_id_before}")
        
        logger.info("[CALL] self.db.add(book) 호출 시작")
        logger.info(f"[PARAM] book={book}")
        self.db.add(book)
        logger.info("[RETURN] self.db.add() 완료")
        
        logger.info("[CALL] self.db.commit() 호출 시작")
        logger.info(f"[PARAM] commit() 파라미터 없음")
        self.db.commit()
        logger.info("[RETURN] self.db.commit() 완료")
        
        logger.info("[CALL] self.db.refresh(book) 호출 시작")
        logger.info(f"[PARAM] book={book}")
        self.db.refresh(book)
        book_id_after = book.id
        logger.info(f"[RETURN] self.db.refresh() 완료, book.id={book_id_after}")
        logger.info(f"[COMPARE] book_id 변경: {book_id_before} -> {book_id_after}")

        logger.info(f"[INFO] Book created: id={book.id}, status={book.status}")
        logger.info("=" * 80)
        return book

    def get_book(self, book_id: int) -> Optional[Book]:
        """책 조회"""
        logger.info("=" * 80)
        logger.info("[FUNCTION] BookService.get_book 호출됨")
        db_id = id(self.db)
        logger.info(f"[PARAM] book_id={book_id}")
        logger.info(f"[STATE] self.db: session_id={db_id}")
        
        logger.info("[CALL] self.db.query(Book) 호출 시작")
        query = self.db.query(Book)
        logger.info(f"[RETURN] query 객체: {query}")
        
        logger.info("[CALL] query.filter(Book.id == book_id) 호출 시작")
        logger.info(f"[PARAM] filter 조건: Book.id == {book_id}")
        filtered_query = query.filter(Book.id == book_id)
        logger.info(f"[RETURN] filtered_query 객체: {filtered_query}")
        
        logger.info("[CALL] filtered_query.first() 호출 시작")
        book = filtered_query.first()
        logger.info(f"[RETURN] first() 반환값: book={book}, book_id={book.id if book else None}")
        logger.info("=" * 80)
        return book

    def get_books(
        self, skip: int = 0, limit: int = 100, status: Optional[BookStatus] = None
    ) -> Tuple[List[Book], int]:
        """
        책 리스트 조회

        Args:
            skip: 건너뛸 개수
            limit: 가져올 개수
            status: 상태 필터 (선택)

        Returns:
            (책 리스트, 전체 개수)
        """
        logger.info("=" * 80)
        logger.info("[FUNCTION] BookService.get_books 호출됨")
        db_id = id(self.db)
        logger.info(f"[PARAM] skip={skip}, limit={limit}, status={status}")
        logger.info(f"[STATE] self.db: session_id={db_id}")
        
        logger.info("[CALL] self.db.query(Book) 호출 시작")
        query = self.db.query(Book)
        logger.info(f"[RETURN] query 객체: {query}")
        
        logger.info("[CALL] if status 조건 확인 시작")
        logger.info(f"[PARAM] status={status}")
        logger.info(f"[COMPARE] status is not None: {status is not None}")
        if status:
            logger.info("[COMPARE] 조건 True: status 필터 적용")
            logger.info("[CALL] query.filter(Book.status == status) 호출 시작")
            logger.info(f"[PARAM] filter 조건: Book.status == {status}")
            query = query.filter(Book.status == status)
            logger.info(f"[RETURN] filtered_query 객체: {query}")
        else:
            logger.info("[COMPARE] 조건 False: status 필터 미적용 (전체 조회)")
        
        logger.info("[CALL] query.count() 호출 시작")
        total = query.count()
        logger.info(f"[RETURN] count() 반환값: total={total}")
        
        logger.info("[CALL] query.order_by().offset().limit().all() 호출 시작")
        logger.info(f"[PARAM] order_by=Book.created_at.desc(), offset={skip}, limit={limit}")
        books = query.order_by(Book.created_at.desc()).offset(skip).limit(limit).all()
        logger.info(f"[RETURN] all() 반환값: books 개수={len(books)}")
        
        logger.info("=" * 80)
        return books, total
