"""텍스트 정리 API 라우터"""
import logging
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pathlib import Path
from backend.api.database import get_db
from backend.api.services.text_organizer_service import TextOrganizerService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/books", tags=["text"])


@router.post("/{book_id}/organize")
def organize_text(
    book_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    텍스트 정리 실행 (백그라운드 작업)

    Args:
        book_id: 책 ID
        background_tasks: FastAPI BackgroundTasks
        db: 데이터베이스 세션

    Returns:
        {"message": "Text organization started", "book_id": book_id}
    """
    logger.info(f"[INFO] 텍스트 정리 요청: book_id={book_id}")

    service = TextOrganizerService(db)

    # 상태 확인
    from backend.api.models.book import Book, BookStatus

    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    if book.status != BookStatus.STRUCTURED:
        raise HTTPException(
            status_code=400,
            detail=f"Book must be in 'structured' status. Current status: {book.status}",
        )

    # 백그라운드 작업으로 텍스트 정리 실행
    def organize_task():
        try:
            service.organize_book_text(book_id)
            logger.info(f"[INFO] 텍스트 정리 완료: book_id={book_id}")
        except Exception as e:
            logger.error(f"[ERROR] 텍스트 정리 실패: book_id={book_id}, error={e}")

    background_tasks.add_task(organize_task)

    return {"message": "Text organization started", "book_id": book_id}


@router.get("/{book_id}")
def get_text_file(book_id: int, db: Session = Depends(get_db)):
    """
    정리된 텍스트 JSON 파일 반환

    Args:
        book_id: 책 ID
        db: 데이터베이스 세션

    Returns:
        텍스트 JSON 파일 내용
    """
    logger.info(f"[INFO] 텍스트 파일 조회: book_id={book_id}")

    from backend.api.models.book import Book
    from backend.config.settings import settings
    import json

    # 책 조회
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    # 텍스트 파일 찾기
    text_dir = settings.output_dir / "text"

    # 파일명 패턴으로 찾기
    import hashlib
    import re

    file_hash_6 = ""
    if book.source_file_path and Path(book.source_file_path).exists():
        with open(book.source_file_path, "rb") as f:
            hasher = hashlib.md5()
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
            file_hash = hasher.hexdigest()
            file_hash_6 = file_hash[:6]

    safe_title = ""
    if book.title:
        safe_title = re.sub(r'[\\/:*?"<>|]', "_", book.title)
        safe_title = safe_title.replace(" ", "_")[:10]

    text_file = None
    if file_hash_6 and safe_title:
        text_file = text_dir / f"{file_hash_6}_{safe_title}_text.json"
    elif file_hash_6:
        text_file = text_dir / f"{file_hash_6}_text.json"
    elif safe_title:
        text_file = text_dir / f"{safe_title}_text.json"
    else:
        text_file = text_dir / f"{book_id}_text.json"

    if not text_file.exists():
        raise HTTPException(
            status_code=404, detail=f"Text file not found: {text_file}"
        )

    # JSON 파일 읽기
    with open(text_file, "r", encoding="utf-8") as f:
        text_data = json.load(f)

    return text_data

