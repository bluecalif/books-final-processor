"""
책 전체 보고서 생성 서비스 (Phase 6.3)

챕터별 요약을 집계하여 책 전체 보고서를 생성합니다.
"""
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from backend.api.models.book import Book, ChapterSummary, Chapter
from backend.summarizers.llm_chains import BookSummaryChain, EntitySynthesisChain
from backend.config.settings import settings

logger = logging.getLogger(__name__)


class BookReportService:
    """책 전체 보고서 생성 서비스"""
    
    def __init__(self, db: Session, book_title: Optional[str] = None):
        """
        Args:
            db: SQLAlchemy 세션
            book_title: 책 제목 (캐시 폴더 분리용)
        """
        self.db = db
        self.book_title = book_title
        self.book_summary_chain = BookSummaryChain(enable_cache=True, book_title=book_title)
        self.output_dir = settings.output_dir / "book_summaries"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        logger.info("[INFO] BookReportService initialized")
    
    def generate_report(self, book_id: int) -> Dict[str, Any]:
        """
        책 전체 보고서 생성 (Phase 1: 필수 항목)
        
        챕터별 요약을 집계하여 책 전체 보고서를 생성하고 JSON 파일로 저장합니다.
        LLM을 사용하여 책 전체 요약 및 엔티티 집계를 수행합니다.
        
        **처리 플로우**:
        1. 책 및 챕터별 요약 조회
        2. 책 전체 요약 생성 (LLM)
        3. 엔티티 집계 (insights, events, examples, persons, concepts)
        4. 도메인별 엔티티 집계 (Phase 2)
        5. JSON 파일 저장 (`data/output/book_summaries/{book_title}_report.json`)
        
        **에러 처리**:
        - LLM 호출 실패 시 예외 발생
        - 파일 저장 실패 시 예외 발생
        - 부분 실패는 허용하지 않음 (전체 실패로 처리)
        
        **캐시 활용**:
        - BookSummaryChain과 EntitySynthesisChain이 자동으로 캐시 확인 및 저장
        - 같은 입력은 재사용하여 LLM 호출 없음
        
        Args:
            book_id: 책 ID
        
        Returns:
            보고서 데이터 (Dict)
            
        Raises:
            ValueError: 책을 찾을 수 없거나 챕터 요약이 없는 경우
            Exception: LLM 호출 또는 파일 저장 실패
        """
        logger.info(f"[INFO] Generating book report for book_id={book_id}")

        try:
            # 1. 책 조회
            book = self.db.query(Book).filter(Book.id == book_id).first()
            if not book:
                raise ValueError(f"Book {book_id} not found")

            # 책 제목 업데이트 (캐시 폴더 분리용)
            if not self.book_title:
                self.book_title = book.title
                # BookSummaryChain과 EntitySynthesisChain의 캐시 매니저 업데이트
                from backend.summarizers.summary_cache_manager import SummaryCacheManager
                cache_manager = SummaryCacheManager(book_title=self.book_title)
                self.book_summary_chain.cache_manager = cache_manager

            # 2. 챕터별 요약 조회 (order_index 순서대로)
            chapter_summaries = (
                self.db.query(ChapterSummary)
                .filter(ChapterSummary.book_id == book_id)
                .join(Chapter, ChapterSummary.chapter_id == Chapter.id)
                .order_by(Chapter.order_index)
                .all()
            )

            if not chapter_summaries:
                raise ValueError(f"No chapter summaries found for book {book_id}")

            logger.info(
                f"[INFO] Found {len(chapter_summaries)} chapter summaries for book {book_id}"
            )

            # 3. 챕터별 요약 데이터 준비
            chapter_data_list = []
            for cs in chapter_summaries:
                chapter = cs.chapter
                structured_data = cs.structured_data or {}

                chapter_data = {
                    "chapter_number": chapter.order_index + 1,  # 1-based
                    "chapter_title": chapter.title,
                    "page_range": f"{chapter.start_page}-{chapter.end_page}",
                    "page_count": chapter.end_page - chapter.start_page + 1,
                    "core_message": structured_data.get("core_message", ""),
                    "summary_3_5_sentences": structured_data.get("summary_3_5_sentences", ""),
                    "argument_flow": structured_data.get("argument_flow", {}),  # Phase 2: argument_flow 추가
                }
                chapter_data_list.append(chapter_data)

            # 4. 책 전체 요약 생성 (LLM)
            book_context = {
                "book_title": book.title or "Unknown",
                "author": book.author or "Unknown",
                "category": book.category or "Unknown",
            }

            # 전체 단계 수 계산 (나중에 사용하기 위해 미리 계산)
            from backend.summarizers.schemas import get_domain_from_category
            domain = get_domain_from_category(book.category or "인문/자기계발")

            domain_entity_map = {
                "history": ["timeline", "geo_map", "structure_layer"],
                "economy": ["frameworks", "scenarios", "playbooks"],
                "humanities": ["life_themes", "practice_recipes", "dilemmas", "identity_shifts"],
                "science": ["technologies", "systems", "applications", "risks_ethics"],
            }
            domain_entities = domain_entity_map.get(domain, [])
            entity_types = ["insights", "key_events", "key_examples", "key_persons", "key_concepts"]
            # book_summary(1) + entity_types(5) + main_arguments(1) + domain_entities(N)
            total_steps = 1 + len(entity_types) + 1 + len(domain_entities)

            logger.info("[INFO] Generating book-level summary...")
            import time as time_module
            report_start_time = time_module.time()
            current_step = 0
            progress_pct = int((current_step / total_steps) * 100) if total_steps > 0 else 0
            logger.info(f"[PROGRESS] Book report: {current_step}/{total_steps} steps ({progress_pct}%) | Step: book_summary")
            book_summary, book_usage = self.book_summary_chain.summarize_book(
                chapter_data_list, book_context
            )
            current_step = 1
            progress_pct = int((current_step / total_steps) * 100) if total_steps > 0 else 0
            elapsed_time = time_module.time() - report_start_time
            logger.info(f"[PROGRESS] Book report: {current_step}/{total_steps} steps ({progress_pct}%) | Elapsed: {elapsed_time:.1f}s | Step: book_summary completed")

            if book_usage:
                logger.info(
                    f"[TOKEN_USAGE] Book summary: "
                    f"prompt={book_usage['prompt_tokens']}, "
                    f"completion={book_usage['completion_tokens']}, "
                    f"total={book_usage['total_tokens']}"
                )

            # 5. 엔티티 집계 (LLM) - Phase 1 필수 항목
            entity_synthesis = {}
            total_entity_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

            total_entity_steps = len(entity_types)
            completed_entity_steps = 0

            for idx, entity_type in enumerate(entity_types):
                completed_entity_steps = idx
                progress_pct = int((completed_entity_steps / total_entity_steps) * 100) if total_entity_steps > 0 else 0
                logger.info(f"[PROGRESS] Entity synthesis: {completed_entity_steps}/{total_entity_steps} steps ({progress_pct}%) | Step: {entity_type}")
                logger.info(f"[INFO] Synthesizing {entity_type}...")

                # 챕터별 엔티티 수집
                chapter_entities = []
                for cs in chapter_summaries:
                    structured_data = cs.structured_data or {}
                    entities = structured_data.get(entity_type, [])
                    if entities:
                        chapter_entities.append(entities)

                if chapter_entities:
                    chain = EntitySynthesisChain(entity_type, enable_cache=True, book_title=self.book_title)
                    synthesized, usage = chain.synthesize_entities(chapter_entities, book_context, use_cache=True)
                    entity_synthesis[entity_type] = synthesized

                    if usage:
                        total_entity_usage["prompt_tokens"] += usage["prompt_tokens"]
                        total_entity_usage["completion_tokens"] += usage["completion_tokens"]
                        total_entity_usage["total_tokens"] += usage["total_tokens"]
                        logger.info(
                            f"[TOKEN_USAGE] {entity_type}: "
                            f"prompt={usage['prompt_tokens']}, "
                            f"completion={usage['completion_tokens']}, "
                            f"total={usage['total_tokens']}"
                        )
                else:
                    entity_synthesis[entity_type] = []
                    logger.warning(f"[WARNING] No {entity_type} found in chapter summaries")

            # Phase 2: main_arguments 엔티티 집계 (챕터별 argument_flow.main_claims 집계)
            # total_steps는 이미 위에서 계산됨
            current_step = 1 + len(entity_types)
            progress_pct = int((current_step / total_steps) * 100) if total_steps > 0 else 0
            elapsed_time = time_module.time() - report_start_time
            logger.info(f"[PROGRESS] Book report: {current_step}/{total_steps} steps ({progress_pct}%) | Elapsed: {elapsed_time:.1f}s | Step: main_arguments")
            logger.info("[INFO] Synthesizing main_arguments...")
            chapter_main_claims = []
            for cs in chapter_summaries:
                structured_data = cs.structured_data or {}
                argument_flow = structured_data.get("argument_flow", {})
                main_claims = argument_flow.get("main_claims", [])
                if main_claims:
                    chapter_main_claims.append(main_claims)

            if chapter_main_claims:
                # main_arguments는 key_arguments와 유사하지만 더 포괄적
                chain = EntitySynthesisChain("main_arguments", enable_cache=True, book_title=self.book_title)
                # max_items를 더 크게 설정
                chain.max_items = 18
                synthesized, usage = chain.synthesize_entities(chapter_main_claims, book_context, use_cache=True)
                entity_synthesis["main_arguments"] = synthesized

                if usage:
                    total_entity_usage["prompt_tokens"] += usage["prompt_tokens"]
                    total_entity_usage["completion_tokens"] += usage["completion_tokens"]
                    total_entity_usage["total_tokens"] += usage["total_tokens"]
                    logger.info(
                        f"[TOKEN_USAGE] main_arguments: "
                        f"prompt={usage['prompt_tokens']}, "
                        f"completion={usage['completion_tokens']}, "
                        f"total={usage['total_tokens']}"
                    )
            else:
                entity_synthesis["main_arguments"] = []
                logger.warning("[WARNING] No main_arguments found in chapter summaries")

            # Phase 2: 도메인별 엔티티 집계
            # domain과 domain_entity_map, domain_entities는 이미 위에서 계산됨
            for idx, entity_type in enumerate(domain_entities):
                current_step = 1 + len(entity_types) + 1 + idx
                progress_pct = int((current_step / total_steps) * 100) if total_steps > 0 else 0
                elapsed_time = time_module.time() - report_start_time
                logger.info(f"[PROGRESS] Book report: {current_step}/{total_steps} steps ({progress_pct}%) | Elapsed: {elapsed_time:.1f}s | Step: {entity_type} (domain: {domain})")
                logger.info(f"[INFO] Synthesizing {entity_type} (domain: {domain})...")

                # 챕터별 도메인 엔티티 수집
                chapter_entities = []
                for cs in chapter_summaries:
                    structured_data = cs.structured_data or {}
                    entities = structured_data.get(entity_type)
                    if entities:
                        # timeline, geo_map, structure_layer는 문자열일 수 있음
                        if isinstance(entities, list):
                            chapter_entities.append(entities)
                        elif isinstance(entities, str) and entities:
                            # 문자열인 경우 리스트로 변환 (각 줄을 항목으로)
                            chapter_entities.append([entities])

                if chapter_entities:
                    chain = EntitySynthesisChain(entity_type, enable_cache=True, book_title=self.book_title)
                    # 도메인별 엔티티 타입에 맞는 max_items 설정
                    domain_max_items = {
                        "timeline": 20,
                        "geo_map": 1,  # 문자열 하나
                        "structure_layer": 1,  # 문자열 하나
                        "frameworks": 12,
                        "scenarios": 8,
                        "playbooks": 12,
                        "life_themes": 12,
                        "practice_recipes": 15,
                        "dilemmas": 12,
                        "identity_shifts": 8,
                        "technologies": 15,
                        "systems": 12,
                        "applications": 12,
                        "risks_ethics": 10,
                    }
                    chain.max_items = domain_max_items.get(entity_type, 15)

                    synthesized, usage = chain.synthesize_entities(chapter_entities, book_context, use_cache=True)
                    entity_synthesis[entity_type] = synthesized

                    if usage:
                        total_entity_usage["prompt_tokens"] += usage["prompt_tokens"]
                        total_entity_usage["completion_tokens"] += usage["completion_tokens"]
                        total_entity_usage["total_tokens"] += usage["total_tokens"]
                        logger.info(
                            f"[TOKEN_USAGE] {entity_type}: "
                            f"prompt={usage['prompt_tokens']}, "
                            f"completion={usage['completion_tokens']}, "
                            f"total={usage['total_tokens']}"
                        )
                else:
                    entity_synthesis[entity_type] = [] if entity_type not in ["geo_map", "structure_layer"] else ""
                    logger.warning(f"[WARNING] No {entity_type} found in chapter summaries")

            logger.info(
                f"[TOKEN_USAGE] Total entity synthesis: "
                f"prompt={total_entity_usage['prompt_tokens']}, "
                f"completion={total_entity_usage['completion_tokens']}, "
                f"total={total_entity_usage['total_tokens']}"
            )

            # 6. 메타데이터 집계 (단순 집계)
            chapters = (
                self.db.query(Chapter)
                .filter(Chapter.book_id == book_id)
                .order_by(Chapter.order_index)
                .all()
            )

            processed_chapters = len([ch for ch in chapters if any(cs.chapter_id == ch.id for cs in chapter_summaries)])
            skipped_chapters = len(chapters) - processed_chapters

            metadata = {
                "book_id": book.id,
                "title": book.title,
                "author": book.author,
                "category": book.category,
                "page_count": book.page_count,
                "chapter_count": len(chapters),
                "processed_chapters": processed_chapters,
                "skipped_chapters": skipped_chapters,
                "generated_at": datetime.utcnow().isoformat() + "Z",
                "status": book.status.value,
            }

            # 7. 통계 정보 집계 (단순 집계)
            total_insights = len(entity_synthesis.get("insights", []))
            total_events = len(entity_synthesis.get("key_events", []))
            total_examples = len(entity_synthesis.get("key_examples", []))
            total_persons = len(entity_synthesis.get("key_persons", []))
            total_concepts = len(entity_synthesis.get("key_concepts", []))

            statistics = {
                "total_pages": book.page_count or 0,
                "total_chapters": len(chapters),
                "total_insights": total_insights,
                "total_key_events": total_events,
                "total_key_examples": total_examples,
                "total_key_persons": total_persons,
                "total_key_concepts": total_concepts,
            }

            # 8. references 집계 (단순 집계, 중복 제거)
            all_references = []
            for cs in chapter_summaries:
                structured_data = cs.structured_data or {}
                references = structured_data.get("references", [])
                if references:
                    all_references.extend(references)

            # 중복 제거 (순서 유지)
            seen = set()
            unique_references = []
            for ref in all_references:
                if ref not in seen:
                    seen.add(ref)
                    unique_references.append(ref)

            entity_synthesis["references"] = unique_references

            # 9. 최종 보고서 구성
            report = {
                "metadata": metadata,
                "book_summary": book_summary,
                "chapters": chapter_data_list,
                "entity_synthesis": entity_synthesis,
                "statistics": statistics,
            }

            # 10. 로컬 파일 저장
            self._save_report_to_file(book, report)

            logger.info(f"[INFO] Book report generated successfully for book_id={book_id}")
            return report

        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            logger.error(
                f"[ERROR] generate_report failed for book_id={{book_id}}, "
                f"error={{type(e).__name__}}: {{str(e)}}\n"
                f"Traceback:\n{{error_trace}}"
            )
            # 에러 상태로 업데이트
            book.status = BookStatus.ERROR_SUMMARIZING
            self.db.commit()
            logger.error(f"[ERROR] Book {{book_id}} status updated to ERROR_SUMMARIZING")
            raise

        
    def _save_report_to_file(self, book: Book, report: Dict[str, Any]) -> None:
        """보고서를 로컬 파일로 저장"""
        # 파일명 생성 (책 제목 기반)
        safe_title = "".join(
            c for c in (book.title or f"book_{book.id}") 
            if c.isalnum() or c in (' ', '-', '_')
        ).strip().replace(' ', '_')[:100]
        
        file_path = self.output_dir / f"{safe_title}_report.json"
        
        # JSON 파일로 저장
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        logger.info(f"[INFO] Book report saved to {file_path}")

