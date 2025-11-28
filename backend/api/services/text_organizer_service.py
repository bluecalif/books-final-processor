"""텍스트 정리 서비스"""
import logging
import json
from pathlib import Path
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from backend.api.models.book import Book, BookStatus
from backend.structure.text_organizer import TextOrganizer
from backend.config.settings import settings

logger = logging.getLogger(__name__)


class TextOrganizerService:
    """텍스트 정리 서비스 클래스"""

    def __init__(self, db: Session):
        """
        Args:
            db: 데이터베이스 세션
        """
        self.db = db
        self.text_organizer = TextOrganizer()

    def organize_book_text(self, book_id: int) -> Path:
        """
        책 텍스트 정리

        Args:
            book_id: 책 ID

        Returns:
            저장된 JSON 파일 경로
        """
        logger.info(f"[INFO] 텍스트 정리 시작: book_id={book_id}")

        # 1. 책 조회
        book = self.db.query(Book).filter(Book.id == book_id).first()
        if not book:
            raise ValueError(f"Book {book_id} not found")

        # 2. 구조 분석 완료 확인
        if book.status != BookStatus.STRUCTURED:
            raise ValueError(
                f"Book {book_id} must be in 'structured' status. "
                f"Current status: {book.status}"
            )

        # 3. 구조 분석 결과 가져오기
        structure_data = None
        if book.structure_data:
            # DB의 structure_data 사용
            structure_data = book.structure_data
            logger.info(f"[INFO] DB에서 구조 분석 결과 로드: book_id={book_id}")
        else:
            # JSON 파일에서 로드 시도
            structure_file = self._find_structure_json_file(book_id, book.title)
            if structure_file and structure_file.exists():
                with open(structure_file, "r", encoding="utf-8") as f:
                    structure_data = json.load(f)
                logger.info(
                    f"[INFO] JSON 파일에서 구조 분석 결과 로드: {structure_file}"
                )
            else:
                raise ValueError(
                    f"구조 분석 결과를 찾을 수 없습니다: book_id={book_id}"
                )

        # 4. 텍스트 정리 실행
        output_path = self.text_organizer.organize_text(
            book_id=book_id,
            structure_data=structure_data,
            pdf_path=book.source_file_path,
            book_title=book.title,
        )

        logger.info(f"[INFO] 텍스트 정리 완료: {output_path}")
        return output_path

    def _find_structure_json_file(
        self, book_id: int, book_title: Optional[str] = None
    ) -> Optional[Path]:
        """
        구조 분석 JSON 파일 찾기

        Args:
            book_id: 책 ID
            book_title: 책 제목 (선택)

        Returns:
            JSON 파일 경로 또는 None
        """
        structure_dir = settings.output_dir / "structure"

        # 1. book_id로 찾기
        pattern = f"*_{book_id}_structure.json"
        for file in structure_dir.glob(pattern):
            return file

        # 2. 책 제목으로 찾기 (해시 포함)
        if book_title:
            import re
            safe_title = re.sub(r'[\\/:*?"<>|]', "_", book_title)
            safe_title = safe_title.replace(" ", "_")[:10]
            pattern = f"*_{safe_title}_structure.json"
            for file in structure_dir.glob(pattern):
                return file

        # 3. book_id만으로 찾기 (fallback)
        pattern = f"{book_id}_structure.json"
        for file in structure_dir.glob(pattern):
            return file

        return None

