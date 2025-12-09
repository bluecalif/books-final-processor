"""
엔티티 추출 서비스

페이지 단위 엔티티 추출 및 챕터 단위 구조화를 수행합니다.
"""
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from sqlalchemy.orm import Session
from backend.api.models.book import Book, BookStatus, PageSummary, ChapterSummary, Chapter
from backend.parsers.pdf_parser import PDFParser
from backend.summarizers.page_extractor import PageExtractor
from backend.summarizers.chapter_structurer import ChapterStructurer
from backend.summarizers.schemas import get_domain_from_category, get_page_schema_class, get_chapter_schema_class
from backend.utils.token_counter import TokenCounter
from backend.config.settings import settings

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
        self.token_counter = TokenCounter(model="gpt-4.1-mini")
        # 토큰 통계 저장용
        self.token_stats = {
            "book_id": None,
            "pages": {
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "total_cost": 0.0,
                "page_count": 0,
            },
            "chapters": {
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "total_cost": 0.0,
                "chapter_count": 0,
            },
        }
        logger.info("[INFO] ExtractionService initialized")

    def extract_pages(self, book_id: int, limit_pages: Optional[int] = None) -> Book:
        """
        페이지 엔티티 추출

        Args:
            book_id: 책 ID
            limit_pages: 페이지 제한 (테스트용, None이면 전체 처리)

        Returns:
            업데이트된 Book 객체
        """
        logger.info(f"[INFO] Starting page extraction for book_id={book_id}, limit_pages={limit_pages}")

        try:
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

            # 3. 구조 데이터 확인 및 검증
            logger.info(f"[INPUT_VALIDATION] Checking structure_data for book_id={book_id}")
            if not book.structure_data:
                logger.error(f"[INPUT_VALIDATION] Book {book_id} has no structure_data")
                raise ValueError(f"Book {book_id} has no structure_data. Please run structure analysis first.")

            # 구조 데이터 형식 확인 및 로깅
            structure_keys = list(book.structure_data.keys())
            logger.info(f"[INPUT_VALIDATION] structure_data keys: {structure_keys}")

            # 구조 데이터 형식 확인 및 main_pages 생성
            # 형식 1: {"main": {"pages": [87, 88, ...]}}
            # 형식 2: {"main_start_page": 87, "main_end_page": 474, "chapters": [...]}
            main_pages = None
            structure_format = None

            if "main" in book.structure_data and "pages" in book.structure_data["main"]:
                # 형식 1: main.pages 직접 사용
                structure_format = "format_1_main_pages"
                main_pages = book.structure_data["main"]["pages"]
                logger.info(f"[INPUT_VALIDATION] Using format 1: main.pages (count: {len(main_pages)})")
            elif "main_start_page" in book.structure_data and "main_end_page" in book.structure_data:
                # 형식 2: main_start_page ~ main_end_page 범위로 생성
                structure_format = "format_2_range"
                main_start_page = book.structure_data["main_start_page"]
                main_end_page = book.structure_data["main_end_page"]
                main_pages = list(range(main_start_page, main_end_page + 1))
                logger.info(
                    f"[INPUT_VALIDATION] Using format 2: main_start_page={main_start_page}, "
                    f"main_end_page={main_end_page}, generated pages count: {len(main_pages)}"
                )
            else:
                logger.error(
                    f"[INPUT_VALIDATION] Book {book_id} structure_data format not recognized. "
                    f"Available keys: {structure_keys}. "
                    f"Expected: 'main.pages' or 'main_start_page'/'main_end_page'"
                )
                logger.warning(f"[WARNING] Book {book_id} has no main pages, skipping extraction")
                return book

            if not main_pages:
                logger.error(f"[INPUT_VALIDATION] Book {book_id} main_pages is empty after processing")
                logger.warning(f"[WARNING] Book {book_id} has no main pages, skipping extraction")
                return book

            logger.info(f"[INPUT_VALIDATION] Main pages range: {main_pages[0]}~{main_pages[-1]} (total: {len(main_pages)})")

            # 4. PDF 파싱 (캐시 사용)
            logger.info(f"[INPUT_VALIDATION] Checking PDF file: {book.source_file_path}")
            if not Path(book.source_file_path).exists():
                logger.error(f"[INPUT_VALIDATION] PDF file not found: {book.source_file_path}")
                raise FileNotFoundError(f"PDF file not found: {book.source_file_path}")

            logger.info(f"[INPUT_VALIDATION] Parsing PDF: {book.source_file_path}")
            parsed_data = self.pdf_parser.parse_pdf(book.source_file_path, use_cache=True)
            pages_data = parsed_data.get("pages", [])

            if not pages_data:
                logger.error(f"[INPUT_VALIDATION] Parsed data has no pages")
                raise ValueError(f"Parsed data has no pages for book_id={book_id}")

            # 페이지 번호를 키로 하는 딕셔너리 생성
            pages_dict = {page.get("page_number"): page for page in pages_data}
            parsed_page_numbers = sorted(pages_dict.keys())
            logger.info(
                f"[INPUT_VALIDATION] Parsed pages range: {parsed_page_numbers[0]}~{parsed_page_numbers[-1]} "
                f"(total: {len(parsed_page_numbers)})"
            )

            # main_pages와 parsed_data 매칭 검증
            missing_pages = [p for p in main_pages if p not in pages_dict]
            if missing_pages:
                logger.warning(
                    f"[INPUT_VALIDATION] {len(missing_pages)} pages from main_pages not found in parsed_data: "
                    f"{missing_pages[:10]}{'...' if len(missing_pages) > 10 else ''}"
                )
            else:
                logger.info(f"[INPUT_VALIDATION] All main_pages found in parsed_data (perfect match)")

            # 실제 처리할 페이지 수 계산
            available_main_pages = [p for p in main_pages if p in pages_dict]
            logger.info(
                f"[INPUT_VALIDATION] Available pages for extraction: {len(available_main_pages)}/{len(main_pages)}"
            )

            if not available_main_pages:
                logger.error(f"[INPUT_VALIDATION] No available pages for extraction after matching")
                raise ValueError(f"No available pages for extraction: main_pages={len(main_pages)}, matched={len(available_main_pages)}")

            # 페이지 제한 적용 (테스트용)
            if limit_pages is not None and limit_pages > 0:
                original_count = len(available_main_pages)
                available_main_pages = available_main_pages[:limit_pages]
                logger.info(
                    f"[INPUT_VALIDATION] Page limit applied: {original_count} → {len(available_main_pages)} pages "
                    f"(limit_pages={limit_pages})"
                )

            # 챕터 정보를 미리 조회하여 딕셔너리로 생성 (병렬 처리 중 DB 접근 방지)
            chapters = self.db.query(Chapter).filter(Chapter.book_id == book_id).order_by(Chapter.order_index).all()
            chapter_info_map = {}  # {page_number: {"title": ..., "number": ...}}
            for chapter in chapters:
                for page_num in range(chapter.start_page, chapter.end_page + 1):
                    chapter_info_map[page_num] = {
                        "title": chapter.title,
                        "number": chapter.order_index + 1,  # 1-based
                    }
            logger.info(f"[INFO] Chapter info map created: {len(chapter_info_map)} pages mapped to {len(chapters)} chapters")

            # 5. PageExtractor 초기화 (책 제목 전달하여 캐시 폴더 분리)
            # 책 제목이 없으면 경고 출력 (폴더명으로 사용)
            if not book.title:
                logger.warning(f"[WARNING] 책제목 없음 - book_id={book_id}, book_title=None, safe_title=book_{book_id}")
                book_title = f"book_{book_id}"
            else:
                book_title = book.title
            page_extractor = PageExtractor(domain, enable_cache=True, book_title=book_title)

            # 토큰 통계 초기화
            self.token_stats["book_id"] = book_id
            self.token_stats["pages"] = {
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "total_cost": 0.0,
                "page_count": 0,
            }

            # 스키마 클래스 가져오기 (출력 토큰 예상치 계산용)
            page_schema_class = get_page_schema_class(domain)

            # 6. 각 본문 페이지 엔티티 추출 (병렬 처리)
            def extract_single_page(page_number: int) -> Tuple[int, Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
                """
                단일 페이지 엔티티 추출 (병렬 처리용)

                주의: DB 저장은 메인 스레드에서 처리하므로 여기서는 DB 접근 없이 엔티티 추출만 수행

                Returns:
                    (page_number, structured_data, token_info) 또는 (page_number, None, None) (실패 시)
                """
                page_data = pages_dict.get(page_number)
                if not page_data:
                    logger.warning(f"[WARNING] Page {page_number} not found in parsed data")
                    return (page_number, None, None)

                page_text = page_data.get("raw_text", "")
                if not page_text:
                    logger.warning(f"[WARNING] Page {page_number} has no raw_text")
                    return (page_number, None, None)

                # 빈 페이지 또는 너무 짧은 페이지 필터링
                if len(page_text.strip()) < 50:
                    logger.warning(
                        f"[WARNING] Page {page_number} text too short: {len(page_text)} chars, skipping"
                    )
                    return (page_number, None, None)

                # 긴 페이지 로깅 (4000자 초과 시 LLM에서 절단됨)
                if len(page_text) > 4000:
                    logger.warning(
                        f"[WARNING] Page {page_number} text will be truncated: "
                        f"{len(page_text)} chars → 4000 chars"
                    )

                # 책 컨텍스트 생성 (DB 접근 없이 미리 조회한 chapter_info_map 사용)
                chapter_info = chapter_info_map.get(page_number, {"title": "Unknown", "number": "Unknown"})
                book_context = {
                    "book_title": book.title or "Unknown",
                    "chapter_title": chapter_info.get("title", "Unknown"),
                    "chapter_number": chapter_info.get("number", "Unknown"),
                }

                try:
                    # 페이지 엔티티 추출 (DB 접근 없음)
                    structured_data, usage = page_extractor.extract_page_entities(
                        page_text, book_context, use_cache=True
                    )

                    # 실제 API 응답의 usage 정보 사용 (있으면), 없으면 예상치 계산
                    if usage:
                        input_tokens = usage["prompt_tokens"]
                        output_tokens = usage["completion_tokens"]
                        cost = self.token_counter.calculate_cost(input_tokens, output_tokens)
                        logger.info(
                            f"[TOKEN] Page {page_number}: input={input_tokens}, "
                            f"output={output_tokens}, cost=${cost:.6f} (actual)"
                        )
                    else:
                        # 캐시 히트 시 예상치 계산 (또는 0으로 처리)
                        prompt = self._build_page_prompt(page_text, book_context, domain)
                        input_tokens = self.token_counter.calculate_prompt_tokens(
                            prompt["system"], prompt["user"]
                        )
                        output_tokens = self.token_counter.estimate_output_tokens(
                            page_schema_class
                        )
                        cost = 0.0  # 캐시 히트 시 비용 0
                        logger.debug(
                            f"[TOKEN] Page {page_number}: cache hit, estimated "
                            f"input={input_tokens}, output={output_tokens}, cost=$0.0"
                        )

                    token_info = {
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "cost": cost,
                    }

                    return (page_number, structured_data, token_info)

                except Exception as e:
                    error_type = type(e).__name__
                    logger.error(
                        f"[ERROR] Failed to extract page {page_number}: "
                        f"{error_type}: {str(e)[:200]}"
                    )
                    return (page_number, None, None)

            # 병렬 처리로 페이지 엔티티 추출
            import time as time_module
            extraction_start_time = time_module.time()
            extracted_count = 0
            failed_count = 0
            total_pages = len(available_main_pages)

            # 챕터별 진행률 추적
            chapter_progress = {}  # {chapter_id: {"extracted": 0, "total": 0}}
            chapters = self.db.query(Chapter).filter(Chapter.book_id == book_id).order_by(Chapter.order_index).all()
            for chapter in chapters:
                chapter_pages = [p for p in available_main_pages if chapter.start_page <= p <= chapter.end_page]
                chapter_progress[chapter.id] = {
                    "chapter_number": chapter.order_index + 1,
                    "title": chapter.title,
                    "extracted": 0,
                    "total": len(chapter_pages),
                    "start_page": chapter.start_page,
                    "end_page": chapter.end_page,
                }

            logger.info(
                f"[EXTRACTION_START] Starting page extraction: "
                f"total_pages={total_pages}, domain={domain}, "
                f"parallel_workers=5, chapters={len(chapters)}"
            )

            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = {
                    executor.submit(extract_single_page, page_number): page_number
                    for page_number in available_main_pages
                }

                for future in as_completed(futures):
                    # futures 딕셔너리에서 페이지 번호 가져오기
                    page_number = futures.get(future, "unknown")
                    try:
                        page_number, structured_data, token_info = future.result()
                    except Exception as e:
                        # future.result()에서 예외 발생 시 처리 (페이지 번호 포함)
                        error_type = type(e).__name__
                        logger.error(
                            f"[ERROR] Future result failed for page {page_number}: "
                            f"{error_type}: {str(e)[:200]}"
                        )
                        failed_count += 1
                        continue

                    if structured_data is None:
                        failed_count += 1
                        logger.warning(f"[WARNING] Page {page_number} extraction failed")
                        continue

                    # 챕터별 진행률 업데이트
                    for chapter_id, progress in chapter_progress.items():
                        if progress["start_page"] <= page_number <= progress["end_page"]:
                            progress["extracted"] += 1
                            break

                    # 토큰 통계 누적
                    if token_info:
                        self.token_stats["pages"]["total_input_tokens"] += token_info["input_tokens"]
                        self.token_stats["pages"]["total_output_tokens"] += token_info["output_tokens"]
                        self.token_stats["pages"]["total_cost"] += token_info["cost"]
                        self.token_stats["pages"]["page_count"] += 1

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
                    processed_count = extracted_count + failed_count

                    # 10페이지당 진행 상황 출력 (페이지 기준)
                    if processed_count % 10 == 0:
                        elapsed_time = time_module.time() - extraction_start_time
                        avg_time_per_page = elapsed_time / processed_count
                        remaining_pages = total_pages - processed_count
                        estimated_remaining_time = avg_time_per_page * remaining_pages

                        logger.info(
                            f"[PROGRESS] Pages: {extracted_count} success, {failed_count} failed, "
                            f"{processed_count}/{total_pages} total "
                            f"({processed_count * 100 // total_pages}%) | "
                            f"Elapsed: {elapsed_time:.1f}s | "
                            f"Avg: {avg_time_per_page:.2f}s/page | "
                            f"Est. remaining: {estimated_remaining_time:.1f}s"
                        )

                    # 챕터별 진행률 출력 (챕터 완료 시)
                    for chapter_id, progress in chapter_progress.items():
                        if progress["start_page"] <= page_number <= progress["end_page"]:
                            if progress["extracted"] == progress["total"] and progress["total"] > 0:
                                logger.info(
                                    f"[PROGRESS] Chapter {progress['chapter_number']} completed: "
                                    f"{progress['title']} "
                                    f"({progress['extracted']}/{progress['total']} pages)"
                                )
                            break

                    # 중간 커밋 제거 (세션 상태 문제 방지)
                    # 병렬 처리는 빠르게 완료되므로 최종 커밋만 수행

            # 7. 상태 업데이트
            book.status = BookStatus.PAGE_SUMMARIZED
            self.db.commit()

            # 토큰 통계 로깅 및 저장
            pages_stats = self.token_stats["pages"]
            logger.info(
                f"[TOKEN] Page extraction summary: "
                f"input={pages_stats['total_input_tokens']}, "
                f"output={pages_stats['total_output_tokens']}, "
                f"cost=${pages_stats['total_cost']:.4f}, "
                f"pages={pages_stats['page_count']}"
            )
            self._save_token_stats()

            # 최종 검증 로그
            total_time = time_module.time() - extraction_start_time
            logger.info(
                f"[EXTRACTION_COMPLETE] Page extraction completed: "
                f"success={extracted_count}, failed={failed_count}, total={total_pages} pages, "
                f"time={total_time:.1f}s, "
                f"avg={total_time/max(extracted_count + failed_count, 1):.2f}s/page"
            )

            # 챕터별 완료 통계
            for chapter_id, progress in chapter_progress.items():
                logger.info(
                    f"[CHAPTER_STATS] Chapter {progress['chapter_number']} ({progress['title']}): "
                    f"{progress['extracted']}/{progress['total']} pages extracted"
                )

            # DB 저장 검증
            saved_count = self.db.query(PageSummary).filter(PageSummary.book_id == book_id).count()
            logger.info(f"[OUTPUT_VALIDATION] PageSummaries saved to DB: {saved_count} records")

            if saved_count != extracted_count:
                logger.warning(
                    f"[OUTPUT_VALIDATION] Mismatch: extracted={extracted_count}, saved={saved_count}"
                )

            if failed_count > 0:
                logger.warning(
                    f"[OUTPUT_VALIDATION] {failed_count} pages failed extraction "
                    f"({failed_count * 100 // total_pages}% failure rate)"
                )

            return book

        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            logger.error(
                f"[ERROR] extract_pages failed for book_id={{book_id}}, "
                f"error={{type(e).__name__}}: {{str(e)}}\n"
                f"Traceback:\n{{error_trace}}"
            )
            # 에러 상태로 업데이트
            book.status = BookStatus.ERROR_SUMMARIZING
            self.db.commit()
            logger.error(f"[ERROR] Book {{book_id}} status updated to ERROR_SUMMARIZING")
            raise


    def extract_chapters(self, book_id: int) -> Book:
        """
        챕터 구조화 (병렬 처리)

        Args:
            book_id: 책 ID

        Returns:
            업데이트된 Book 객체
        """
        logger.info(f"[INFO] Starting chapter structuring for book_id={book_id}")

        try:
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

            # 4. ChapterStructurer 초기화 (책 제목 전달하여 캐시 폴더 분리)
            # 책 제목이 없으면 경고 출력 (폴더명으로 사용)
            if not book.title:
                logger.warning(f"[WARNING] 책제목 없음 - book_id={book_id}, book_title=None, safe_title=book_{book_id}")
                book_title = f"book_{book_id}"
            else:
                book_title = book.title
            chapter_structurer = ChapterStructurer(domain, enable_cache=True, book_title=book_title)

            # 토큰 통계 초기화 (book_id 설정 중요!)
            if self.token_stats["book_id"] != book_id:
                # extract_pages가 실행되지 않은 경우 또는 다른 책인 경우
                self.token_stats["book_id"] = book_id
                # 페이지 통계가 이미 있으면 유지, 없으면 초기화
                if "pages" not in self.token_stats or self.token_stats["pages"]["page_count"] == 0:
                    self.token_stats["pages"] = {
                        "total_input_tokens": 0,
                        "total_output_tokens": 0,
                        "total_cost": 0.0,
                        "page_count": 0,
                    }

            # 챕터 통계만 초기화 (페이지 통계는 유지)
            self.token_stats["chapters"] = {
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "total_cost": 0.0,
                "chapter_count": 0,
            }

            # 스키마 클래스 가져오기 (출력 토큰 예상치 계산용)
            chapter_schema_class = get_chapter_schema_class(domain)

            # 5. 각 챕터 구조화 (병렬 처리)
            import time as time_module
            structuring_start_time = time_module.time()
            structured_count = 0
            failed_count = 0
            total_chapters = len(chapters)

            def extract_single_chapter(chapter: Chapter) -> Tuple[Chapter, Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
                """
                단일 챕터 구조화 (병렬 처리용)

                Returns:
                    (chapter, structured_data, token_info) 또는 (chapter, None, None) (실패 시)
                """
                # 각 스레드는 자신만의 DB 세션을 사용해야 함
                from backend.api.database import SessionLocal
                thread_db = SessionLocal()

                try:
                    # 챕터의 페이지 범위 확인
                    chapter_pages = list(range(chapter.start_page, chapter.end_page + 1))

                    # 해당 페이지들의 엔티티 가져오기
                    page_entities_list = []
                    for page_number in chapter_pages:
                        page_summary = (
                            thread_db.query(PageSummary)
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
                        return (chapter, None, None)

                    # 책 컨텍스트 생성
                    book_context = {
                        "book_title": book.title or "Unknown",
                        "chapter_title": chapter.title,
                        "chapter_number": chapter.order_index + 1,  # 1-based
                        "book_summary": "",  # TODO: Book 모델에 book_summary 필드 추가 시 사용
                    }

                    # 챕터 구조화
                    structured_data, usage = chapter_structurer.structure_chapter(
                        page_entities_list, book_context, use_cache=True
                    )

                    # 실제 API 응답의 usage 정보 사용 (있으면), 없으면 예상치 계산
                    if usage:
                        input_tokens = usage["prompt_tokens"]
                        output_tokens = usage["completion_tokens"]
                        cost = self.token_counter.calculate_cost(input_tokens, output_tokens)
                        logger.info(
                            f"[TOKEN] Chapter {chapter.order_index + 1}: input={input_tokens}, "
                            f"output={output_tokens}, cost=${cost:.6f} (actual)"
                        )
                    else:
                        # 캐시 히트 시 예상치 계산 (비용은 0)
                        compressed_pages = self._compress_page_entities(page_entities_list, domain)
                        prompt = self._build_chapter_prompt(compressed_pages, book_context, domain)
                        input_tokens = self.token_counter.calculate_prompt_tokens(
                            prompt["system"], prompt["user"]
                        )
                        output_tokens = self.token_counter.estimate_output_tokens(
                            chapter_schema_class
                        )
                        cost = 0.0  # 캐시 히트 시 비용 0
                        logger.debug(
                            f"[TOKEN] Chapter {chapter.order_index + 1}: cache hit, estimated "
                            f"input={input_tokens}, output={output_tokens}, cost=$0.0"
                        )

                    token_info = {
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "cost": cost,
                    }

                    return (chapter, structured_data, token_info)

                except Exception as e:
                    error_type = type(e).__name__
                    logger.error(
                        f"[ERROR] Failed to structure chapter {chapter.id}: "
                        f"{error_type}: {str(e)[:200]}"
                    )
                    return (chapter, None, None)
                finally:
                    thread_db.close()

            # 병렬 처리로 챕터 구조화
            logger.info(
                f"[EXTRACTION_START] Starting chapter structuring: "
                f"total_chapters={total_chapters}, domain={domain}, parallel_workers=5"
            )

            skipped_count = 0  # 2페이지 이하 챕터 스킵 카운트

            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = {
                    executor.submit(extract_single_chapter, chapter): chapter
                    for chapter in chapters
                }

                for future in as_completed(futures):
                    try:
                        chapter, structured_data, token_info = future.result()
                    except Exception as e:
                        # future.result()에서 예외 발생 시 처리
                        error_type = type(e).__name__
                        logger.error(f"[ERROR] Future result failed: {error_type}: {str(e)[:200]}")
                        failed_count += 1
                        continue

                    if structured_data is None:
                        # 2페이지 이하 챕터는 스킵 (의도된 동작)
                        chapter_pages = list(range(chapter.start_page, chapter.end_page + 1))
                        if len(chapter_pages) <= 2:
                            skipped_count += 1
                            logger.info(
                                f"[SKIP] Chapter {chapter.order_index + 1} ({chapter.title}): "
                                f"Skipped (2 pages or less: {len(chapter_pages)} pages)"
                            )
                        else:
                            failed_count += 1
                            logger.warning(f"[WARNING] Chapter {chapter.id} structuring failed")
                        continue

                    # 토큰 통계 누적
                    if token_info:
                        self.token_stats["chapters"]["total_input_tokens"] += token_info["input_tokens"]
                        self.token_stats["chapters"]["total_output_tokens"] += token_info["output_tokens"]
                        self.token_stats["chapters"]["total_cost"] += token_info["cost"]
                        self.token_stats["chapters"]["chapter_count"] += 1

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

                    # 각 챕터 완료 시 진행 상황 출력
                    processed_count = structured_count + failed_count + skipped_count
                    elapsed_time = time_module.time() - structuring_start_time
                    avg_time_per_chapter = elapsed_time / processed_count if processed_count > 0 else 0
                    remaining_chapters = total_chapters - processed_count
                    estimated_remaining_time = avg_time_per_chapter * remaining_chapters

                    logger.info(
                        f"[PROGRESS] Chapters: {structured_count} success, "
                        f"{failed_count} failed, {skipped_count} skipped, "
                        f"{processed_count}/{total_chapters} total "
                        f"({processed_count * 100 // total_chapters}%) | "
                        f"Elapsed: {elapsed_time:.1f}s | "
                        f"Avg: {avg_time_per_chapter:.2f}s/chapter | "
                        f"Est. remaining: {estimated_remaining_time:.1f}s | "
                        f"Chapter: {chapter.title}"
                    )

            # 6. 상태 업데이트
            book.status = BookStatus.SUMMARIZED
            self.db.commit()

            # 토큰 통계 로깅 및 저장
            chapters_stats = self.token_stats["chapters"]
            logger.info(
                f"[TOKEN] Chapter structuring summary: "
                f"input={chapters_stats['total_input_tokens']}, "
                f"output={chapters_stats['total_output_tokens']}, "
                f"cost=${chapters_stats['total_cost']:.4f}, "
                f"chapters={chapters_stats['chapter_count']}"
            )
            self._save_token_stats()

            # 최종 검증 로그
            total_time = time_module.time() - structuring_start_time
            logger.info(
                f"[EXTRACTION_COMPLETE] Chapter structuring completed: "
                f"success={structured_count}, failed={failed_count}, skipped={skipped_count}, "
                f"total={total_chapters} chapters, "
                f"time={total_time:.1f}s, "
                f"avg={total_time/max(structured_count + failed_count, 1):.2f}s/chapter"
            )

            # DB 저장 검증
            saved_count = self.db.query(ChapterSummary).filter(ChapterSummary.book_id == book_id).count()
            logger.info(f"[OUTPUT_VALIDATION] ChapterSummaries saved to DB: {saved_count} records")

            if saved_count != structured_count:
                logger.warning(
                    f"[OUTPUT_VALIDATION] Mismatch: structured={structured_count}, saved={saved_count}"
                )

            if failed_count > 0:
                logger.warning(
                    f"[OUTPUT_VALIDATION] {failed_count} chapters failed structuring "
                    f"({failed_count * 100 // total_chapters}% failure rate)"
                )

            return book

        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            logger.error(
                f"[ERROR] extract_chapters failed for book_id={{book_id}}, "
                f"error={{type(e).__name__}}: {{str(e)}}\n"
                f"Traceback:\n{{error_trace}}"
            )
            # 에러 상태로 업데이트
            book.status = BookStatus.ERROR_SUMMARIZING
            self.db.commit()
            logger.error(f"[ERROR] Book {{book_id}} status updated to ERROR_SUMMARIZING")
            raise


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

    def _build_page_prompt(
        self, page_text: str, book_context: Dict[str, Any], domain: str
    ) -> Dict[str, str]:
        """
        페이지 엔티티 추출 프롬프트 생성 (토큰 계산용)

        Args:
            page_text: 페이지 원문 텍스트
            book_context: 책 컨텍스트
            domain: 도메인 코드

        Returns:
            {"system": "...", "user": "..."}
        """
        book_title = book_context.get("book_title", "Unknown")
        chapter_title = book_context.get("chapter_title", "Unknown")
        chapter_number = book_context.get("chapter_number", "Unknown")
        
        domain_names = {
            "history": "역사/사회",
            "economy": "경제/경영",
            "humanities": "인문/자기계발",
            "science": "과학/기술",
        }
        domain_name = domain_names.get(domain, "인문/자기계발")

        # 텍스트 길이 제한 (토큰 제한 고려)
        max_chars = 4000
        if len(page_text) > max_chars:
            page_text = page_text[:max_chars] + "..."

        system = f"""You are an expert content analyst specializing in {domain_name} domain.
Your task is to extract structured entities from a single page of text.

**CRITICAL RULES**:
1. **NO HALLUCINATION**: Only extract information that is explicitly mentioned in the text.
   - If a person/event/concept is not mentioned, use empty list [] or null.
   - Do NOT invent names, dates, or facts.
2. **Be Specific**: Extract concrete, actionable information.
3. **Be Accurate**: Ensure all extracted information matches the original text.

**Output Format**:
You must return a JSON object that strictly follows the {domain_name} page schema.
All fields must be present and valid according to the schema."""

        user = f"""# BOOK CONTEXT
- Book Title: {book_title}
- Chapter: {chapter_number}. {chapter_title}
- Domain: {domain_name}

# PAGE TEXT
{page_text}

# TASK
Extract structured entities from this page following the {domain_name} page schema:
- page_summary: 2-4 sentences summarizing this page's role in the chapter
- page_function_tag: The function of this page (e.g., "problem_statement", "example_story", "data_explanation")
- persons: List of people mentioned
- concepts: List of key concepts
- events: List of events or historical occurrences
- examples: List of examples or case studies
- references: List of references or citations
- key_sentences: List of most important sentences (3-5 sentences)
- tone_tag: Tone of the page (e.g., "analytical", "narrative", "instructional")
- topic_tags: List of topic tags
- complexity: Complexity level (e.g., "simple", "moderate", "complex")

Remember: Only extract what is explicitly mentioned in the text. Do NOT invent or infer."""

        return {"system": system, "user": user}

    def _build_chapter_prompt(
        self,
        compressed_page_entities: List[Dict[str, Any]],
        book_context: Dict[str, Any],
        domain: str,
    ) -> Dict[str, str]:
        """
        챕터 구조화 프롬프트 생성 (토큰 계산용)

        Args:
            compressed_page_entities: 압축된 페이지 엔티티 목록
            book_context: 책 컨텍스트
            domain: 도메인 코드

        Returns:
            {"system": "...", "user": "..."}
        """
        book_title = book_context.get("book_title", "Unknown")
        chapter_title = book_context.get("chapter_title", "Unknown")
        chapter_number = book_context.get("chapter_number", "Unknown")
        book_summary = book_context.get("book_summary", "")
        
        domain_names = {
            "history": "역사/사회",
            "economy": "경제/경영",
            "humanities": "인문/자기계발",
            "science": "과학/기술",
        }
        domain_name = domain_names.get(domain, "인문/자기계발")

        # 페이지 엔티티를 JSON 문자열로 변환
        pages_json = json.dumps(compressed_page_entities, ensure_ascii=False, indent=2)

        system = f"""You are an expert content analyst specializing in {domain_name} domain.
Your task is to synthesize chapter-level structure from page-level entities.

**CRITICAL RULES**:
1. **NO HALLUCINATION**: Only synthesize information from the provided page entities.
   - Do NOT invent new events, people, or concepts.
   - Use only what is present in the page entities.
2. **Synthesize, Don't Summarize**: Create new insights by connecting page-level information.
3. **Maintain Evidence Links**: When creating insights, reference supporting evidence from pages.

**Output Format**:
You must return a JSON object that strictly follows the {domain_name} chapter schema.
All fields must be present and valid according to the schema."""

        user = f"""# BOOK CONTEXT
- Book Title: {book_title}
- Chapter: {chapter_number}. {chapter_title}
- Domain: {domain_name}
- Book Summary: {book_summary if book_summary else "Not provided"}

# COMPRESSED PAGE ENTITIES
{pages_json}

# TASK
Synthesize chapter-level structure from the page entities above:
- core_message: One-line core message of this chapter
- summary_3_5_sentences: 3-5 sentence summary
- argument_flow: Problem, background, main claims, evidence, counterpoints, conclusion
- key_events, key_examples, key_persons, key_concepts: Integrated from page entities
- insights: New insights connecting page-level information
- chapter_level_synthesis: Comprehensive synthesis

Remember: Only synthesize from the provided page entities. Do NOT invent."""

        return {"system": system, "user": user}

    def _compress_page_entities(
        self, page_entities_list: List[Dict[str, Any]], domain: str
    ) -> List[Dict[str, Any]]:
        """
        페이지 엔티티 압축 (상위 N개만 추려서 LLM에 전달)
        ChapterStructurer의 _compress_page_entities와 동일한 로직

        Args:
            page_entities_list: 페이지 엔티티 목록
            domain: 도메인 코드

        Returns:
            압축된 페이지 엔티티 목록
        """
        compressed = []
        
        for page_entity in page_entities_list:
            # 각 페이지에서 핵심 정보만 추출
            compressed_page = {
                "page_number": page_entity.get("page_number"),
                "page_summary": page_entity.get("page_summary", ""),
                "page_function_tag": page_entity.get("page_function_tag"),
                # 주요 엔티티만 상위 N개 추려서 포함
                "key_concepts": page_entity.get("concepts", [])[:5],  # 상위 5개
                "key_events": page_entity.get("events", [])[:3],  # 상위 3개
                "key_examples": page_entity.get("examples", [])[:3],  # 상위 3개
                "key_persons": page_entity.get("persons", [])[:3],  # 상위 3개
                "key_sentences": page_entity.get("key_sentences", [])[:3],  # 상위 3개
            }
            
            # 도메인별 추가 필드 (있는 경우만)
            if domain == "history":
                compressed_page["locations"] = page_entity.get("locations", [])[:3]
                compressed_page["time_periods"] = page_entity.get("time_periods", [])[:2]
            elif domain == "economy":
                compressed_page["indicators"] = page_entity.get("indicators", [])[:3]
                compressed_page["strategies"] = page_entity.get("strategies", [])[:2]
            elif domain == "humanities":
                compressed_page["practices"] = page_entity.get("practices", [])[:3]
                compressed_page["life_situations"] = page_entity.get("life_situations", [])[:2]
            elif domain == "science":
                compressed_page["technologies"] = page_entity.get("technologies", [])[:3]
                compressed_page["applications"] = page_entity.get("applications", [])[:2]
            
            compressed.append(compressed_page)
        
        return compressed

    def _save_token_stats(self) -> None:
        """토큰 통계를 JSON 파일로 저장 (기존 파일과 병합)"""
        try:
            stats_dir = settings.output_dir / "token_stats"
            stats_dir.mkdir(parents=True, exist_ok=True)
            
            stats_file = stats_dir / f"book_{self.token_stats['book_id']}_tokens.json"
            
            # 기존 파일이 있으면 로드하여 병합
            existing_stats = None
            if stats_file.exists():
                try:
                    with open(stats_file, "r", encoding="utf-8") as f:
                        existing_stats = json.load(f)
                except Exception as e:
                    logger.warning(f"[WARNING] Failed to load existing token stats: {e}")
            
            # 병합: 페이지 통계와 챕터 통계를 각각 유지
            if existing_stats:
                # 페이지 통계: 현재 값이 0이면 기존 값 사용
                if self.token_stats["pages"]["page_count"] == 0 and existing_stats.get("pages"):
                    self.token_stats["pages"] = existing_stats["pages"]
                # 챕터 통계: 현재 값이 0이면 기존 값 사용
                if self.token_stats["chapters"]["chapter_count"] == 0 and existing_stats.get("chapters"):
                    self.token_stats["chapters"] = existing_stats["chapters"]
            
            with open(stats_file, "w", encoding="utf-8") as f:
                json.dump(self.token_stats, f, ensure_ascii=False, indent=2)
            
            logger.info(f"[TOKEN] Token stats saved to {stats_file}")
        except Exception as e:
            logger.warning(f"[WARNING] Failed to save token stats: {e}")

