"""책 관련 API 라우터"""
import logging
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Optional

from backend.api.database import get_db
from backend.api.services.book_service import BookService
from backend.api.services.parsing_service import ParsingService
from backend.api.schemas.book import BookResponse, BookListResponse, BookCreate
from backend.api.models.book import BookStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/books", tags=["books"])


def _parse_book_background(book_id: int):
    """
    백그라운드에서 책 파싱 실행
    
    Args:
        book_id: 책 ID
    """
    logger.info("=" * 80)
    logger.info("[FUNCTION] _parse_book_background 호출됨")
    logger.info(f"[PARAM] book_id={book_id}")
    
    # 새로운 DB 세션 생성 (백그라운드 작업용)
    logger.info("[CALL] get_db() 호출 시작 (새 세션 생성)")
    db = next(get_db())
    db_id = id(db)
    logger.info(f"[RETURN] get_db() 반환값: session_id={db_id}")
    logger.info(f"[STATE] db의 bind: {id(db.bind)}")
    
    try:
        # 파싱 서비스 생성 및 실행
        logger.info("[CALL] ParsingService(db) 생성 시작")
        logger.info(f"[PARAM] db 파라미터: session_id={db_id}")
        parsing_service = ParsingService(db)
        service_id = id(parsing_service)
        logger.info(f"[RETURN] ParsingService() 반환값: service_id={service_id}")
        
        logger.info("[CALL] parsing_service.parse_book() 호출 시작")
        logger.info(f"[PARAM] book_id={book_id}")
        book = parsing_service.parse_book(book_id)
        logger.info(f"[RETURN] parse_book() 반환값: book_id={book.id}, status={book.status}, page_count={book.page_count}")
        logger.info(f"[INFO] Background parsing completed successfully: book_id={book_id}, status={book.status}")
    except Exception as e:
        logger.error(f"[ERROR] Background parsing failed: {e}")
        logger.info(f"[ERROR] Exception 타입: {type(e).__name__}")
        logger.info(f"[ERROR] Exception 메시지: {str(e)}")
        
        # 에러 상태로 업데이트
        try:
            logger.info("[CALL] 에러 상태 업데이트 시작")
            from backend.api.models.book import Book
            book = db.query(Book).filter(Book.id == book_id).first()
            if book:
                logger.info(f"[PARAM] book_id={book_id}, status=ERROR_PARSING")
                book.status = BookStatus.ERROR_PARSING
                db.commit()
                logger.info(f"[RETURN] 에러 상태 업데이트 완료: status={book.status}")
            else:
                logger.info("[ERROR] 책을 찾을 수 없음 (에러 상태 업데이트 실패)")
        except Exception as update_error:
            logger.error(f"[ERROR] Failed to update error status: {update_error}")
    finally:
        logger.info("[CALL] db.close() 호출 시작")
        db.close()
        logger.info("[RETURN] db.close() 완료")
        logger.info("=" * 80)


@router.post("/upload", response_model=dict)
async def upload_book(
    file: UploadFile = File(...),
    title: Optional[str] = Query(None, description="책 제목"),
    author: Optional[str] = Query(None, description="저자"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
):
    """
    PDF 파일 업로드

    파일을 업로드하고 DB 레코드를 생성합니다.
    """
    logger.info("=" * 80)
    logger.info("[FUNCTION] upload_book 호출됨")
    db_id = id(db)
    logger.info(f"[PARAM] file 파라미터: filename={file.filename}, content_type={file.content_type}, size={file.size if hasattr(file, 'size') else 'unknown'}")
    logger.info(f"[PARAM] title={title}")
    logger.info(f"[PARAM] author={author}")
    logger.info(f"[PARAM] db 파라미터: session_id={db_id}")
    logger.info(f"[STATE] db의 bind: {id(db.bind)}")
    
    # 파일 형식 검증
    logger.info("[CALL] file.filename.endswith('.pdf') 호출 시작")
    logger.info(f"[PARAM] endswith() 파라미터: '.pdf'")
    logger.info(f"[PARAM] file.filename={file.filename}")
    is_pdf = file.filename.endswith(".pdf")
    logger.info(f"[RETURN] endswith() 반환값: {is_pdf}")
    logger.info(f"[EXPECTED] 파일 형식 예상값: True (PDF 파일)")
    logger.info(f"[ACTUAL] 파일 형식 실제값: {is_pdf}")
    logger.info(f"[COMPARE] is_pdf == True: {is_pdf == True}")
    
    if not is_pdf:
        logger.info("[ERROR] 파일 형식 검증 실패 - PDF가 아님")
        logger.info("[CALL] HTTPException() 생성 시작")
        logger.info(f"[PARAM] status_code=400, detail='Only PDF files are allowed'")
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    
    # 임시 파일로 저장
    logger.info("[CALL] import tempfile 실행")
    import tempfile
    logger.info("[RETURN] import tempfile 완료")
    
    logger.info("[CALL] tempfile.NamedTemporaryFile() 호출 시작")
    logger.info(f"[PARAM] delete=False, suffix='.pdf'")
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        tmp_file_id = id(tmp_file)
        logger.info(f"[RETURN] NamedTemporaryFile() 반환값: tmp_file_id={tmp_file_id}")
        logger.info(f"[STATE] tmp_file.name={tmp_file.name}")
        
        logger.info("[CALL] Path(tmp_file.name) 생성 시작")
        logger.info(f"[PARAM] tmp_file.name={tmp_file.name}")
        tmp_path = Path(tmp_file.name)
        tmp_path_str = str(tmp_path)
        logger.info(f"[RETURN] Path() 반환값: tmp_path={tmp_path_str}")
        
        logger.info("[CALL] file.read() 호출 시작")
        logger.info(f"[PARAM] file.read() 파라미터 없음")
        content = await file.read()
        content_size = len(content)
        logger.info(f"[RETURN] file.read() 반환값: content_size={content_size} bytes")
        
        logger.info("[CALL] tmp_file.write(content) 호출 시작")
        logger.info(f"[PARAM] content_size={content_size} bytes")
        tmp_file.write(content)
        logger.info("[RETURN] tmp_file.write() 완료")
        logger.info(f"[INFO] 임시 파일 저장 완료: {tmp_path_str}")
        logger.info("[CALL] with tempfile.NamedTemporaryFile() 컨텍스트 매니저 종료")
        logger.info(f"[RETURN] with 블록 종료, tmp_file 닫힘")

    logger.info("[CALL] try 블록 시작")
    try:
        # 서비스를 통해 책 생성
        logger.info("[CALL] BookService(db) 생성 시작")
        logger.info(f"[PARAM] db 파라미터: session_id={db_id}")
        service = BookService(db)
        service_id = id(service)
        logger.info(f"[RETURN] BookService() 반환값: service_id={service_id}")
        
        logger.info("[CALL] service.create_book() 호출 시작")
        logger.info(f"[PARAM] tmp_path={tmp_path_str}, title={title}, author={author}")
        book = service.create_book(tmp_path, title=title, author=author)
        book_id = book.id
        book_status = book.status
        logger.info(f"[RETURN] create_book() 반환값: book_id={book_id}, status={book_status}")

        # 백그라운드 작업 추가: PDF 파싱
        logger.info("[CALL] background_tasks.add_task() 호출 시작")
        logger.info(f"[PARAM] task=_parse_book_background, book_id={book_id}")
        background_tasks.add_task(_parse_book_background, book_id)
        logger.info("[RETURN] background_tasks.add_task() 완료")
        logger.info(f"[INFO] Background parsing task added: book_id={book_id}")

        logger.info("[CALL] return dict 생성 시작")
        result = {
            "book_id": book_id,
            "status": book_status,
            "message": "File uploaded successfully. Parsing started in background.",
        }
        logger.info(f"[RETURN] upload_book() 반환값: {result}")
        logger.info("=" * 80)
        return result
    except Exception as e:
        logger.error(f"[ERROR] Failed to upload book: {e}")
        logger.info(f"[ERROR] Exception 타입: {type(e).__name__}")
        logger.info(f"[ERROR] Exception 메시지: {str(e)}")
        
        # 임시 파일 삭제
        logger.info("[CALL] tmp_path.unlink(missing_ok=True) 호출 시작")
        logger.info(f"[PARAM] tmp_path={tmp_path_str}, missing_ok=True")
        tmp_path.unlink(missing_ok=True)
        logger.info("[RETURN] tmp_path.unlink() 완료")
        
        logger.info("[CALL] HTTPException() 생성 시작")
        logger.info(f"[PARAM] status_code=500, detail='Failed to upload book: {str(e)}'")
        logger.info("=" * 80)
        raise HTTPException(status_code=500, detail=f"Failed to upload book: {str(e)}")


@router.get("", response_model=BookListResponse)
def get_books(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status: Optional[BookStatus] = Query(None, description="상태 필터"),
    db: Session = Depends(get_db),
):
    """책 리스트 조회"""
    logger.info("=" * 80)
    logger.info("[FUNCTION] get_books 호출됨")
    db_id = id(db)
    logger.info(f"[PARAM] skip={skip}")
    logger.info(f"[PARAM] limit={limit}")
    logger.info(f"[PARAM] status={status}")
    logger.info(f"[PARAM] db 파라미터: session_id={db_id}")
    logger.info(f"[STATE] db의 bind: {id(db.bind)}")
    
    logger.info("[CALL] BookService(db) 생성 시작")
    logger.info(f"[PARAM] db 파라미터: session_id={db_id}")
    service = BookService(db)
    service_id = id(service)
    logger.info(f"[RETURN] BookService() 반환값: service_id={service_id}")
    
    logger.info("[CALL] service.get_books() 호출 시작")
    logger.info(f"[PARAM] skip={skip}, limit={limit}, status={status}")
    books, total = service.get_books(skip=skip, limit=limit, status=status)
    logger.info(f"[RETURN] get_books() 반환값: books 개수={len(books)}, total={total}")
    
    logger.info("[CALL] BookResponse.model_validate() 호출 시작 (리스트 변환)")
    logger.info(f"[PARAM] books 개수={len(books)}")
    logger.info("[CALL] validated_books = [] 리스트 초기화 시작")
    validated_books = []
    logger.info(f"[RETURN] validated_books 초기화 완료: 빈 리스트")
    logger.info("[CALL] for idx, book in enumerate(books) 루프 시작")
    for idx, book in enumerate(books):
        logger.info(f"[CALL] BookResponse.model_validate(book) 호출 시작 (인덱스 {idx})")
        logger.info(f"[PARAM] book={book}, book_id={book.id if book else None}")
        validated_book = BookResponse.model_validate(book)
        logger.info(f"[RETURN] model_validate() 반환값: book_id={validated_book.id}")
        logger.info("[CALL] validated_books.append(validated_book) 호출 시작")
        logger.info(f"[PARAM] validated_book={validated_book}, book_id={validated_book.id}")
        validated_books.append(validated_book)
        logger.info(f"[RETURN] append() 완료, validated_books 개수={len(validated_books)}")
    logger.info(f"[RETURN] 모든 model_validate() 완료: validated_books 개수={len(validated_books)}")
    
    logger.info("[CALL] BookListResponse() 생성 시작")
    logger.info(f"[PARAM] books 개수={len(validated_books)}, total={total}")
    result = BookListResponse(
        books=validated_books,
        total=total,
    )
    logger.info(f"[RETURN] BookListResponse() 반환값: books 개수={len(result.books)}, total={result.total}")
    logger.info("=" * 80)
    return result


@router.get("/{book_id}", response_model=BookResponse)
def get_book(book_id: int, db: Session = Depends(get_db)):
    """책 상세 조회"""
    logger.info("=" * 80)
    logger.info("[FUNCTION] get_book 호출됨")
    db_id = id(db)
    logger.info(f"[PARAM] book_id={book_id}")
    logger.info(f"[PARAM] db 파라미터: session_id={db_id}")
    logger.info(f"[STATE] db의 bind: {id(db.bind)}")
    
    logger.info("[CALL] BookService(db) 생성 시작")
    logger.info(f"[PARAM] db 파라미터: session_id={db_id}")
    service = BookService(db)
    service_id = id(service)
    logger.info(f"[RETURN] BookService() 반환값: service_id={service_id}")
    
    logger.info("[CALL] service.get_book() 호출 시작")
    logger.info(f"[PARAM] book_id={book_id}")
    book = service.get_book(book_id)
    logger.info(f"[RETURN] get_book() 반환값: book={book}, book_id={book.id if book else None}")
    
    logger.info("[CALL] if not book 조건 확인 시작")
    logger.info(f"[PARAM] book={book}")
    logger.info(f"[COMPARE] book is None: {book is None}")
    if not book:
        logger.info("[ERROR] 책을 찾을 수 없음")
        logger.info("[CALL] HTTPException() 생성 시작")
        logger.info(f"[PARAM] status_code=404, detail='Book not found'")
        logger.info("=" * 80)
        raise HTTPException(status_code=404, detail="Book not found")
    
    logger.info("[CALL] BookResponse.model_validate(book) 호출 시작")
    logger.info(f"[PARAM] book={book}, book_id={book.id}")
    result = BookResponse.model_validate(book)
    logger.info(f"[RETURN] model_validate() 반환값: book_id={result.id}")
    logger.info("=" * 80)
    return result
