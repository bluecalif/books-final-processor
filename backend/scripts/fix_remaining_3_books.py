"""
남은 3개 책 처리 스크립트

Phase 2, 3, 4를 단계별로 진행:
1. 파싱 (캐시 무시하고 재파싱)
2. 구조 분석
3. 텍스트 파일 생성
"""
import sys
import logging
from pathlib import Path
from typing import Dict, Any
from datetime import datetime
import time

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy.orm import Session

from backend.api.database import SessionLocal, init_db
from backend.api.models.book import Book, BookStatus
from backend.api.services.parsing_service import ParsingService
from backend.api.services.structure_service import StructureService
from backend.api.services.text_organizer_service import TextOrganizerService
from backend.parsers.cache_manager import CacheManager
from backend.parsers.pdf_parser import PDFParser
from backend.config.settings import settings
from backend.api.schemas.structure import FinalStructureInput, FinalChapterInput

# 로그 디렉토리 설정
LOG_DIR = project_root / "data" / "logs" / "batch_processing"
LOG_DIR.mkdir(parents=True, exist_ok=True)


def setup_logging() -> logging.Logger:
    """로깅 설정"""
    log_file = LOG_DIR / f"fix_remaining_3_books_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    
    logger = logging.getLogger("fix_remaining_3_books")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    
    # 콘솔 핸들러도 추가
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter("%(message)s")
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    return logger, log_file


def print_progress(message: str):
    """진행률 메시지를 콘솔에 출력"""
    print(f"\r{message}", end="", flush=True)


def delete_incomplete_cache(book: Book, logger: logging.Logger) -> bool:
    """불완전한 캐시 파일 삭제"""
    if not book.source_file_path:
        return False
    
    pdf_path = Path(book.source_file_path)
    if not pdf_path.exists():
        return False
    
    try:
        cache_manager = CacheManager()
        cache_key = cache_manager.get_file_hash(str(pdf_path))
        cache_file = cache_manager.get_cache_path(cache_key)
        
        if cache_file.exists():
            import json
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            elements_count = len(cache_data.get("elements", []))
            
            if elements_count == 0:
                logger.info(f"[CACHE] 불완전한 캐시 파일 삭제: {cache_file.name} (elements: 0개)")
                cache_file.unlink()
                return True
        return False
    except Exception as e:
        logger.warning(f"[CACHE] 캐시 파일 확인 실패: {e}")
        return False


def parse_book_without_cache(book_id: int, db: Session, logger: logging.Logger) -> bool:
    """캐시 무시하고 책 파싱"""
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        logger.error(f"[PHASE 2] Book 레코드 없음: ID {book_id}")
        return False
    
    if not book.source_file_path:
        logger.error(f"[PHASE 2] source_file_path 없음: ID {book_id}")
        return False
    
    pdf_path = Path(book.source_file_path)
    if not pdf_path.exists():
        logger.error(f"[PHASE 2] PDF 파일 없음: {book.source_file_path}")
        return False
    
    # 불완전한 캐시 삭제
    delete_incomplete_cache(book, logger)
    
    try:
        logger.info(f"[PHASE 2] 파싱 시작: ID {book_id}, {book.title} (캐시 무시)")
        parse_start = time.time()
        
        # 캐시 무시하고 재파싱
        pdf_parser = PDFParser(api_key=settings.upstage_api_key)
        parsed_data = pdf_parser.parse_pdf(str(pdf_path), use_cache=False)
        
        # Pages 테이블에 저장
        from backend.api.models.book import Page
        
        # 기존 페이지 삭제
        existing_pages = db.query(Page).filter(Page.book_id == book_id).all()
        for page in existing_pages:
            db.delete(page)
        
        # 새 페이지 저장
        pages_data = parsed_data.get("pages", [])
        for page_data in pages_data:
            page = Page(
                book_id=book_id,
                page_number=page_data.get("page_number", 1),
                raw_text=page_data.get("raw_text", ""),
                metadata=page_data.get("metadata", {})
            )
            db.add(page)
        
        # Book 상태 업데이트
        book.page_count = parsed_data.get("total_pages", 0)
        book.status = BookStatus.PARSED
        db.commit()
        db.refresh(book)
        
        parse_time = time.time() - parse_start
        logger.info(f"[PHASE 2] 파싱 완료: ID {book_id}, page_count={book.page_count}, 소요시간: {parse_time:.1f}초")
        print_progress(f"[Phase 2: 파싱] ID {book_id} - {book.title[:40]}... 완료 (소요시간: {parse_time:.1f}초)")
        return True
        
    except Exception as e:
        logger.error(f"[PHASE 2] 파싱 실패: ID {book_id}, {e}", exc_info=True)
        book.status = BookStatus.ERROR_PARSING
        db.commit()
        return False


def structure_book(book_id: int, db: Session, logger: logging.Logger) -> bool:
    """책 구조 분석"""
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        logger.error(f"[PHASE 3] Book 레코드 없음: ID {book_id}")
        return False
    
    if book.status != BookStatus.PARSED:
        logger.info(f"[PHASE 3] 파싱 완료 상태가 아님: ID {book_id}, Status: {book.status}")
        return False
    
    try:
        logger.info(f"[PHASE 3] 구조 분석 시작: ID {book_id}, {book.title}")
        structure_start = time.time()
        
        structure_service = StructureService(db)
        structure_candidates = structure_service.get_structure_candidates(book_id)
        
        if not structure_candidates or not structure_candidates.get("auto_candidates"):
            logger.error(f"[PHASE 3] 구조 후보 없음: ID {book_id}")
            return False
        
        # 첫 번째 후보 자동 적용
        first_candidate = structure_candidates["auto_candidates"][0]
        final_structure = convert_structure_to_final_input(first_candidate)
        
        structure_service.apply_final_structure(book_id, final_structure)
        
        structure_time = time.time() - structure_start
        logger.info(f"[PHASE 3] 구조 분석 완료: ID {book_id}, 소요시간: {structure_time:.1f}초")
        print_progress(f"[Phase 3: 구조 분석] ID {book_id} - {book.title[:40]}... 완료 (소요시간: {structure_time:.1f}초)")
        return True
        
    except Exception as e:
        logger.error(f"[PHASE 3] 구조 분석 실패: ID {book_id}, {e}", exc_info=True)
        book.status = BookStatus.ERROR_STRUCTURING
        db.commit()
        return False


def text_book(book_id: int, db: Session, logger: logging.Logger) -> bool:
    """책 텍스트 파일 생성"""
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        logger.error(f"[PHASE 4] Book 레코드 없음: ID {book_id}")
        return False
    
    if book.status != BookStatus.STRUCTURED:
        logger.info(f"[PHASE 4] 구조 분석 완료 상태가 아님: ID {book_id}, Status: {book.status}")
        return False
    
    try:
        logger.info(f"[PHASE 4] 텍스트 파일 생성 시작: ID {book_id}, {book.title}")
        text_start = time.time()
        
        text_organizer_service = TextOrganizerService(db)
        text_file_path = text_organizer_service.organize_book_text(book_id)
        
        text_time = time.time() - text_start
        logger.info(f"[PHASE 4] 텍스트 파일 생성 완료: ID {book_id}, 파일: {text_file_path}, 소요시간: {text_time:.1f}초")
        print_progress(f"[Phase 4: 텍스트 생성] ID {book_id} - {book.title[:40]}... 완료 (소요시간: {text_time:.1f}초)")
        return True
        
    except Exception as e:
        logger.error(f"[PHASE 4] 텍스트 파일 생성 실패: ID {book_id}, {e}", exc_info=True)
        return False


def convert_structure_to_final_input(structure_candidate: Dict[str, Any]) -> FinalStructureInput:
    """구조 후보를 FinalStructureInput으로 변환"""
    structure = structure_candidate.get("structure", {})
    main = structure.get("main", {})
    main_pages = main.get("pages", [])
    chapters = main.get("chapters", [])
    
    main_start_page = main_pages[0] if main_pages else 1
    main_end_page = main_pages[-1] if main_pages else None
    
    final_chapters = []
    for chapter in chapters:
        final_chapters.append(
            FinalChapterInput(
                start_page=chapter.get("start_page", 1),
                end_page=chapter.get("end_page", 1),
                title=chapter.get("title", ""),
            )
        )
    
    return FinalStructureInput(
        main_start_page=main_start_page,
        main_end_page=main_end_page,
        chapters=final_chapters,
        notes_pages=[],
        start_pages=[],
        end_pages=[],
    )


def main():
    """메인 함수"""
    # 남은 3개 책 ID
    book_ids = [209, 210, 211]
    
    logger, log_file = setup_logging()
    
    logger.info("=" * 100)
    logger.info("남은 3개 책 처리 시작")
    logger.info("=" * 100)
    logger.info(f"처리할 책 ID: {book_ids}")
    logger.info(f"로그 파일: {log_file}")
    
    init_db()
    db = SessionLocal()
    
    try:
        # Phase 2: 파싱
        print("\n[Phase 2: 파싱]")
        logger.info("=" * 100)
        logger.info("[PHASE 2] 파싱 시작 (캐시 무시하고 재파싱)")
        logger.info("=" * 100)
        
        phase2_start = time.time()
        for idx, book_id in enumerate(book_ids, start=1):
            print_progress(f"[Phase 2: 파싱] {idx}/{len(book_ids)} - 처리 중...")
            parse_book_without_cache(book_id, db, logger)
        
        print()  # 줄바꿈
        phase2_time = time.time() - phase2_start
        logger.info(f"[PHASE 2] 완료: 소요시간: {phase2_time:.1f}초")
        
        # Phase 3: 구조 분석
        print("\n[Phase 3: 구조 분석]")
        logger.info("=" * 100)
        logger.info("[PHASE 3] 구조 분석 시작")
        logger.info("=" * 100)
        
        phase3_start = time.time()
        for idx, book_id in enumerate(book_ids, start=1):
            print_progress(f"[Phase 3: 구조 분석] {idx}/{len(book_ids)} - 처리 중...")
            structure_book(book_id, db, logger)
        
        print()  # 줄바꿈
        phase3_time = time.time() - phase3_start
        logger.info(f"[PHASE 3] 완료: 소요시간: {phase3_time:.1f}초")
        
        # Phase 4: 텍스트 파일 생성
        print("\n[Phase 4: 텍스트 파일 생성]")
        logger.info("=" * 100)
        logger.info("[PHASE 4] 텍스트 파일 생성 시작")
        logger.info("=" * 100)
        
        phase4_start = time.time()
        for idx, book_id in enumerate(book_ids, start=1):
            print_progress(f"[Phase 4: 텍스트 생성] {idx}/{len(book_ids)} - 처리 중...")
            text_book(book_id, db, logger)
        
        print()  # 줄바꿈
        phase4_time = time.time() - phase4_start
        logger.info(f"[PHASE 4] 완료: 소요시간: {phase4_time:.1f}초")
        
        # 최종 상태 확인
        print("\n[최종 상태 확인]")
        logger.info("=" * 100)
        logger.info("[최종 상태 확인]")
        logger.info("=" * 100)
        
        for book_id in book_ids:
            book = db.query(Book).filter(Book.id == book_id).first()
            if book:
                logger.info(f"ID {book_id}: {book.title}")
                logger.info(f"  Status: {book.status.value}")
                logger.info(f"  page_count: {book.page_count}")
        
        total_time = time.time() - phase2_start
        print(f"\n[완료] 전체 소요시간: {total_time:.1f}초")
        logger.info(f"[완료] 전체 소요시간: {total_time:.1f}초")
        logger.info(f"로그 파일: {log_file}")
        
    finally:
        db.close()


if __name__ == "__main__":
    main()

