"""
엔티티 추출 서비스

페이지 단위 엔티티 추출 및 챕터 단위 구조화를 수행합니다.
"""
import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from backend.api.models.book import Book, BookStatus, PageSummary, ChapterSummary, Chapter
from backend.parsers.pdf_parser import PDFParser
from backend.summarizers.page_extractor import PageExtractor
from backend.summarizers.chapter_structurer import ChapterStructurer
from backend.summarizers.schemas import get_domain_from_category

logger = logging.getLogger(__name__)


class ExtractionService:
    """엔티티 추출 서비스 클래스"""

    def __init__(self, db: Session):
        """
        Args:
            db: SQLAlchemy 세션
        """
        self.db = db
        self.pdf_parser = PDFParser(use_cache=True)
        logger.info("[INFO] ExtractionService initialized")

    def extract_pages(self, book_id: int) -> Book:
        """
        페이지 엔티티 추출

        Args:
            book_id: 책 ID

        Returns:
            업데이트된 Book 객체
        """
        logger.info(f"[INFO] Starting page extraction for book_id={book_id}")

        # 1. 책 조회
        book = self.db.query(Book).filter(Book.id == book_id).first()
        if not book:
            raise ValueError(f"Book {book_id} not found")

        # 2. 도메인 확인
        if not book.category:
            logger.warning(f"[WARNING] Book {book_id} has no category, using default 'humanities'")
            domain = "humanities"
        else:
            domain = get_domain_from_category(book.category)
        
        logger.info(f"[INFO] Domain: {domain} (category: {book.category})")

        # 3. 구조 데이터 확인
        if not book.structure_data:
            raise ValueError(f"Book {book_id} has no structure_data. Please run structure analysis first.")

        main_pages = book.structure_data.get("main", {}).get("pages", [])
        if not main_pages:
            logger.warning(f"[WARNING] Book {book_id} has no main pages, skipping extraction")
            return book

        logger.info(f"[INFO] Main pages: {main_pages[:10]}... (total: {len(main_pages)})")

        # 4. PDF 파싱 (캐시 사용)
        logger.info(f"[INFO] Parsing PDF: {book.source_file_path}")
        parsed_data = self.pdf_parser.parse_pdf(book.source_file_path, use_cache=True)
        pages_data = parsed_data.get("pages", [])

        # 페이지 번호를 키로 하는 딕셔너리 생성
        pages_dict = {page.get("page_number"): page for page in pages_data}

        # 5. PageExtractor 초기화
        page_extractor = PageExtractor(domain, enable_cache=True)

        # 6. 각 본문 페이지 엔티티 추출
        extracted_count = 0
        for page_number in main_pages:
            page_data = pages_dict.get(page_number)
            if not page_data:
                logger.warning(f"[WARNING] Page {page_number} not found in parsed data")
                continue

            page_text = page_data.get("raw_text", "")
            if not page_text:
                logger.warning(f"[WARNING] Page {page_number} has no raw_text")
                continue

            # 책 컨텍스트 생성
            chapter_info = self._get_chapter_info(book, page_number)
            book_context = {
                "book_title": book.title or "Unknown",
                "chapter_title": chapter_info.get("title", "Unknown"),
                "chapter_number": chapter_info.get("number", "Unknown"),
            }

            try:
                # 페이지 엔티티 추출
                structured_data = page_extractor.extract_page_entities(
                    page_text, book_context, use_cache=True
                )

                # PageSummary 저장 또는 업데이트
                page_summary = (
                    self.db.query(PageSummary)
                    .filter(
                        PageSummary.book_id == book_id,
                        PageSummary.page_number == page_number,
                    )
                    .first()
                )

                if page_summary:
                    # 기존 레코드 업데이트
                    page_summary.summary_text = structured_data.get("page_summary", "")
                    page_summary.structured_data = structured_data
                else:
                    # 새 레코드 생성
                    page_summary = PageSummary(
                        book_id=book_id,
                        page_number=page_number,
                        summary_text=structured_data.get("page_summary", ""),
                        structured_data=structured_data,
                        lang="ko",
                    )
                    self.db.add(page_summary)

                extracted_count += 1
                if extracted_count % 10 == 0:
                    logger.info(f"[INFO] Extracted {extracted_count} pages...")

            except Exception as e:
                logger.error(f"[ERROR] Failed to extract page {page_number}: {e}")
                continue

        # 7. 상태 업데이트
        book.status = BookStatus.PAGE_SUMMARIZED
        self.db.commit()

        logger.info(
            f"[INFO] Page extraction completed: {extracted_count}/{len(main_pages)} pages extracted"
        )
        return book

    def extract_chapters(self, book_id: int) -> Book:
        """
        챕터 구조화

        Args:
            book_id: 책 ID

        Returns:
            업데이트된 Book 객체
        """
        logger.info(f"[INFO] Starting chapter structuring for book_id={book_id}")

        # 1. 책 조회
        book = self.db.query(Book).filter(Book.id == book_id).first()
        if not book:
            raise ValueError(f"Book {book_id} not found")

        # 2. 챕터 개수 확인 (1-2개인 책 제외)
        chapters = (
            self.db.query(Chapter)
            .filter(Chapter.book_id == book_id)
            .order_by(Chapter.order_index)
            .all()
        )

        if len(chapters) <= 2:
            logger.warning(
                f"[WARNING] Book {book_id} has {len(chapters)} chapters, skipping chapter structuring "
                "(will be handled in Phase 6.1)"
            )
            return book

        # 3. 도메인 확인
        if not book.category:
            logger.warning(f"[WARNING] Book {book_id} has no category, using default 'humanities'")
            domain = "humanities"
        else:
            domain = get_domain_from_category(book.category)

        logger.info(f"[INFO] Domain: {domain} (category: {book.category})")

        # 4. ChapterStructurer 초기화
        chapter_structurer = ChapterStructurer(domain, enable_cache=True)

        # 5. 각 챕터 구조화
        structured_count = 0
        for chapter in chapters:
            # 챕터의 페이지 범위 확인
            chapter_pages = list(range(chapter.start_page, chapter.end_page + 1))

            # 해당 페이지들의 엔티티 가져오기
            page_entities_list = []
            for page_number in chapter_pages:
                page_summary = (
                    self.db.query(PageSummary)
                    .filter(
                        PageSummary.book_id == book_id,
                        PageSummary.page_number == page_number,
                    )
                    .first()
                )

                if page_summary and page_summary.structured_data:
                    # structured_data에 page_number 추가
                    entity = page_summary.structured_data.copy()
                    entity["page_number"] = page_number
                    page_entities_list.append(entity)

            if not page_entities_list:
                logger.warning(
                    f"[WARNING] Chapter {chapter.id} has no page entities, skipping"
                )
                continue

            # 책 컨텍스트 생성
            book_context = {
                "book_title": book.title or "Unknown",
                "chapter_title": chapter.title,
                "chapter_number": chapter.order_index + 1,  # 1-based
                "book_summary": "",  # TODO: Book 모델에 book_summary 필드 추가 시 사용
            }

            try:
                # 챕터 구조화
                structured_data = chapter_structurer.structure_chapter(
                    page_entities_list, book_context, use_cache=True
                )

                # ChapterSummary 저장 또는 업데이트
                chapter_summary = (
                    self.db.query(ChapterSummary)
                    .filter(ChapterSummary.chapter_id == chapter.id)
                    .first()
                )

                if chapter_summary:
                    # 기존 레코드 업데이트
                    chapter_summary.summary_text = structured_data.get(
                        "summary_3_5_sentences", ""
                    )
                    chapter_summary.structured_data = structured_data
                else:
                    # 새 레코드 생성
                    chapter_summary = ChapterSummary(
                        book_id=book_id,
                        chapter_id=chapter.id,
                        summary_text=structured_data.get("summary_3_5_sentences", ""),
                        structured_data=structured_data,
                        lang="ko",
                    )
                    self.db.add(chapter_summary)

                structured_count += 1
                logger.info(
                    f"[INFO] Structured chapter {chapter.order_index + 1}: {chapter.title}"
                )

            except Exception as e:
                logger.error(f"[ERROR] Failed to structure chapter {chapter.id}: {e}")
                continue

        # 6. 상태 업데이트
        book.status = BookStatus.SUMMARIZED
        self.db.commit()

        logger.info(
            f"[INFO] Chapter structuring completed: {structured_count}/{len(chapters)} chapters structured"
        )
        return book

    def _get_chapter_info(self, book: Book, page_number: int) -> Dict[str, Any]:
        """
        페이지 번호에 해당하는 챕터 정보 조회

        Args:
            book: Book 객체
            page_number: 페이지 번호

        Returns:
            챕터 정보 딕셔너리 (title, number)
        """
        chapter = (
            self.db.query(Chapter)
            .filter(
                Chapter.book_id == book.id,
                Chapter.start_page <= page_number,
                Chapter.end_page >= page_number,
            )
            .first()
        )

        if chapter:
            return {
                "title": chapter.title,
                "number": chapter.order_index + 1,  # 1-based
            }
        else:
            return {"title": "Unknown", "number": "Unknown"}

