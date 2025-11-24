"""구조 분석 서비스"""
import logging
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from backend.api.models.book import Book, Chapter, BookStatus
from backend.parsers.pdf_parser import PDFParser
from backend.structure.structure_builder import StructureBuilder
from backend.structure.llm_structure_refiner import LLMStructureRefiner
from backend.api.schemas.structure import FinalStructureInput
from backend.config.settings import settings

logger = logging.getLogger(__name__)


class StructureService:
    """구조 분석 서비스 클래스"""

    def __init__(self, db: Session):
        """
        Args:
            db: 데이터베이스 세션
        """
        self.db = db
        self.pdf_parser = PDFParser(api_key=settings.upstage_api_key)
        self.structure_builder = StructureBuilder()
        self.llm_refiner = LLMStructureRefiner(api_key=settings.openai_api_key)

    def get_structure_candidates(self, book_id: int) -> Dict[str, Any]:
        """
        구조 후보 생성 (휴리스틱 + LLM 보정)

        Args:
            book_id: 책 ID

        Returns:
            {
                "meta": {...},
                "auto_candidates": [
                    {"label": "heuristic_v1", "structure": {...}},
                    {"label": "llm_v2", "structure": {...}}
                ],
                "chapter_title_candidates": [...],
                "samples": {...}
            }
        """
        logger.info(f"[INFO] Getting structure candidates for book {book_id}")

        # 책 조회
        book = self.db.query(Book).filter(Book.id == book_id).first()
        if not book:
            raise ValueError(f"Book {book_id} not found")

        if book.status != BookStatus.PARSED:
            raise ValueError(
                f"Book {book_id} must be in 'parsed' status. Current status: {book.status}"
            )

        # PDF 파싱 (캐시 사용)
        logger.info(f"[INFO] Parsing PDF: {book.source_file_path}")
        parsed_data = self.pdf_parser.parse_pdf(book.source_file_path, use_cache=True)

        # 1. 휴리스틱 구조 생성
        logger.info("[INFO] Building heuristic structure...")
        heuristic_structure = self.structure_builder.build_structure(parsed_data)

        # 2. LLM 보정 구조 생성
        logger.info("[INFO] Refining structure with LLM...")
        llm_structure = self.llm_refiner.refine_structure(parsed_data, heuristic_structure)

        # 3. 샘플 페이지 추출
        samples = self._extract_samples(parsed_data, heuristic_structure)

        # 4. 챕터 제목 후보 추출
        chapter_title_candidates = self._extract_chapter_title_candidates(
            parsed_data, heuristic_structure
        )

        # 5. 메타데이터
        meta = {
            "total_pages": parsed_data.get("total_pages", 0),
            "book_id": book_id,
            "book_title": book.title,
        }

        result = {
            "meta": meta,
            "auto_candidates": [
                {"label": "heuristic_v1", "structure": heuristic_structure},
                {"label": "llm_v2", "structure": llm_structure},
            ],
            "chapter_title_candidates": chapter_title_candidates,
            "samples": samples,
        }

        logger.info("[INFO] Structure candidates generated successfully")
        return result

    def apply_final_structure(
        self, book_id: int, final_structure: FinalStructureInput
    ) -> Book:
        """
        최종 구조 확정 및 DB 저장

        Args:
            book_id: 책 ID
            final_structure: 최종 구조 입력

        Returns:
            업데이트된 Book 객체
        """
        logger.info(f"[INFO] Applying final structure for book {book_id}")

        # 책 조회
        book = self.db.query(Book).filter(Book.id == book_id).first()
        if not book:
            raise ValueError(f"Book {book_id} not found")

        if book.status != BookStatus.PARSED:
            raise ValueError(
                f"Book {book_id} must be in 'parsed' status. Current status: {book.status}"
            )

        # 1. structure_data에 JSON 저장
        structure_data = {
            "main_start_page": final_structure.main_start_page,
            "main_end_page": final_structure.main_end_page,
            "chapters": [
                {
                    "title": ch.title,
                    "start_page": ch.start_page,
                    "end_page": ch.end_page,
                    "order_index": ch.order_index or idx,
                }
                for idx, ch in enumerate(final_structure.chapters)
            ],
            "notes_pages": final_structure.notes_pages,
            "start_pages": final_structure.start_pages,
            "end_pages": final_structure.end_pages,
        }
        book.structure_data = structure_data

        # 2. 기존 Chapter 레코드 삭제 후 재생성
        logger.info("[INFO] Deleting existing chapters...")
        existing_chapters = self.db.query(Chapter).filter(Chapter.book_id == book_id).all()
        for chapter in existing_chapters:
            self.db.delete(chapter)

        logger.info("[INFO] Creating new chapters...")
        for idx, ch_input in enumerate(final_structure.chapters):
            chapter = Chapter(
                book_id=book_id,
                title=ch_input.title,
                order_index=ch_input.order_index or idx,
                start_page=ch_input.start_page,
                end_page=ch_input.end_page,
                section_type="main",  # 기본값
            )
            self.db.add(chapter)

        # 3. 상태 변경: parsed → structured
        book.status = BookStatus.STRUCTURED

        # 4. 커밋
        self.db.commit()
        self.db.refresh(book)

        logger.info(f"[INFO] Final structure applied. Status changed to: {book.status}")
        return book

    def _extract_samples(
        self, parsed_data: Dict[str, Any], heuristic_structure: Dict[str, Any]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        샘플 페이지 추출

        Args:
            parsed_data: PDF 파싱 결과
            heuristic_structure: 휴리스틱 구조

        Returns:
            {
                "head": [...],
                "tail": [...],
                "around_main_start": [...]
            }
        """
        pages = parsed_data.get("pages", [])
        total_pages = len(pages)

        # head: 앞 5페이지
        head = [
            {
                "page_number": p.get("page_number"),
                "snippet": p.get("raw_text", "")[:200],
            }
            for p in pages[:5]
        ]

        # tail: 뒤 5페이지
        tail = [
            {
                "page_number": p.get("page_number"),
                "snippet": p.get("raw_text", "")[:200],
            }
            for p in pages[-5:]
        ]

        # around_main_start: 본문 시작 주변
        main_pages = heuristic_structure.get("main", {}).get("pages", [])
        around_main_start = []
        if main_pages:
            main_start = main_pages[0]
            start_idx = max(0, main_start - 3)
            end_idx = min(len(pages), main_start + 3)
            for p in pages[start_idx:end_idx]:
                around_main_start.append(
                    {
                        "page_number": p.get("page_number"),
                        "snippet": p.get("raw_text", "")[:200],
                    }
                )

        return {
            "head": head,
            "tail": tail,
            "around_main_start": around_main_start,
        }

    def _extract_chapter_title_candidates(
        self, parsed_data: Dict[str, Any], heuristic_structure: Dict[str, Any]
    ) -> List[str]:
        """
        챕터 제목 후보 추출

        Args:
            parsed_data: PDF 파싱 결과
            heuristic_structure: 휴리스틱 구조

        Returns:
            챕터 제목 후보 리스트
        """
        chapters = heuristic_structure.get("main", {}).get("chapters", [])
        return [ch.get("title", "") for ch in chapters if ch.get("title")]

