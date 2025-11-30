"""
엔티티 추출 서비스

페이지 단위 엔티티 추출 및 챕터 단위 구조화를 수행합니다.
"""
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
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
        self.token_counter = TokenCounter(model="gpt-4o-mini")
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
                # 토큰 계산 (프롬프트 재생성)
                prompt = self._build_page_prompt(page_text, book_context, domain)
                input_tokens = self.token_counter.calculate_prompt_tokens(
                    prompt["system"], prompt["user"]
                )
                output_tokens = self.token_counter.estimate_output_tokens(
                    page_schema_class
                )
                cost = self.token_counter.calculate_cost(input_tokens, output_tokens)
                
                # 통계 누적
                self.token_stats["pages"]["total_input_tokens"] += input_tokens
                self.token_stats["pages"]["total_output_tokens"] += output_tokens
                self.token_stats["pages"]["total_cost"] += cost
                self.token_stats["pages"]["page_count"] += 1
                
                logger.info(
                    f"[TOKEN] Page {page_number}: input={input_tokens}, "
                    f"output={output_tokens}, cost=${cost:.6f}"
                )
                
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
        
        # 토큰 통계 초기화
        self.token_stats["chapters"] = {
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_cost": 0.0,
            "chapter_count": 0,
        }
        
        # 스키마 클래스 가져오기 (출력 토큰 예상치 계산용)
        chapter_schema_class = get_chapter_schema_class(domain)

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
                # 토큰 계산 (프롬프트 재생성)
                compressed_pages = self._compress_page_entities(page_entities_list, domain)
                prompt = self._build_chapter_prompt(compressed_pages, book_context, domain)
                input_tokens = self.token_counter.calculate_prompt_tokens(
                    prompt["system"], prompt["user"]
                )
                output_tokens = self.token_counter.estimate_output_tokens(
                    chapter_schema_class
                )
                cost = self.token_counter.calculate_cost(input_tokens, output_tokens)
                
                # 통계 누적
                self.token_stats["chapters"]["total_input_tokens"] += input_tokens
                self.token_stats["chapters"]["total_output_tokens"] += output_tokens
                self.token_stats["chapters"]["total_cost"] += cost
                self.token_stats["chapters"]["chapter_count"] += 1
                
                logger.info(
                    f"[TOKEN] Chapter {chapter.order_index + 1}: input={input_tokens}, "
                    f"output={output_tokens}, cost=${cost:.6f}"
                )
                
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
        """토큰 통계를 JSON 파일로 저장"""
        try:
            stats_dir = settings.output_dir / "token_stats"
            stats_dir.mkdir(parents=True, exist_ok=True)
            
            stats_file = stats_dir / f"book_{self.token_stats['book_id']}_tokens.json"
            
            with open(stats_file, "w", encoding="utf-8") as f:
                json.dump(self.token_stats, f, ensure_ascii=False, indent=2)
            
            logger.info(f"[TOKEN] Token stats saved to {stats_file}")
        except Exception as e:
            logger.warning(f"[WARNING] Failed to save token stats: {e}")

