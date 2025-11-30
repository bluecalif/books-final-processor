"""
대량 도서 처리 스크립트 (단계별 배치 처리)

CSV 파일에 있는 도서를 단계별로 일괄 처리합니다:
1. 모든 책에 대해 파싱 완료
2. 모든 책에 대해 구조 분석 완료
3. 모든 책에 대해 텍스트 파일 생성 완료

이미 처리된 도서는 자동으로 제외됩니다.
"""
import logging
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy.orm import Session

from backend.api.database import SessionLocal, init_db
from backend.api.models.book import Book, BookStatus
from backend.api.services.book_service import BookService
from backend.api.services.parsing_service import ParsingService
from backend.api.services.structure_service import StructureService
from backend.api.services.text_organizer_service import TextOrganizerService
from backend.utils.csv_parser import BookCSVParser
from backend.utils.processed_books_checker import ProcessedBooksChecker
from backend.api.schemas.structure import FinalStructureInput, FinalChapterInput

# 로그 디렉토리 설정
LOG_DIR = project_root / "data" / "logs" / "batch_processing"
LOG_DIR.mkdir(parents=True, exist_ok=True)


def setup_logging(log_file: Path) -> logging.Logger:
    """로깅 설정"""
    logger = logging.getLogger("batch_process")
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
    
    return logger


def print_progress(message: str):
    """진행률 메시지를 콘솔에 출력"""
    print(f"\r{message}", end="", flush=True)


# 진행률 추적을 위한 Lock
progress_lock = Lock()


def find_pdf_file(book_title: str, search_dirs: List[Path]) -> Optional[Path]:
    """PDF 파일 경로 찾기"""
    normalized_title = book_title.replace(" ", "").replace("　", "")
    
    for search_dir in search_dirs:
        if not search_dir.exists():
            continue
        
        pdf_file = search_dir / f"{book_title}.pdf"
        if pdf_file.exists():
            return pdf_file
        
        pdf_file = search_dir / f"{normalized_title}.pdf"
        if pdf_file.exists():
            return pdf_file
        
        for pdf_file in search_dir.glob("*.pdf"):
            if normalized_title in pdf_file.stem.replace(" ", "").replace("　", ""):
                return pdf_file
    
    return None


def convert_structure_to_final_input(structure_candidate: Dict[str, Any]) -> FinalStructureInput:
    """구조 후보를 FinalStructureInput으로 변환"""
    structure = structure_candidate.get("structure", {})
    main = structure.get("main", {})
    main_pages = main.get("pages", [])
    chapters = main.get("chapters", [])
    
    main_start_page = main_pages[0] if main_pages else 1
    main_end_page = main_pages[-1] if main_pages else None
    
    final_chapters = []
    for idx, chapter in enumerate(chapters):
        final_chapter = FinalChapterInput(
            title=chapter.get("title", f"제{idx+1}장"),
            start_page=chapter.get("start_page", 1),
            end_page=chapter.get("end_page", 1),
            order_index=chapter.get("number") - 1 if chapter.get("number") else idx,
        )
        final_chapters.append(final_chapter)
    
    return FinalStructureInput(
        main_start_page=main_start_page,
        main_end_page=main_end_page,
        chapters=final_chapters,
        notes_pages=[],
        start_pages=[],
        end_pages=[],
    )


def prepare_books(
    csv_books: List[Dict[str, Any]],
    db: Session,
    search_dirs: List[Path],
    logger: logging.Logger,
) -> Dict[str, Dict[str, Any]]:
    """
    단계 1: 모든 책에 대해 PDF 파일 찾기 및 Book 레코드 생성
    
    Returns:
        book_data 딕셔너리: {book_id: {...}, ...}
    """
    logger.info("=" * 100)
    logger.info("[PHASE 1] PDF 파일 찾기 및 Book 레코드 생성 시작")
    logger.info("=" * 100)
    
    book_service = BookService(db)
    books_data = {}
    
    for idx, csv_book in enumerate(csv_books, start=1):
        csv_title = csv_book.get("Title", "")
        csv_author = csv_book.get("저자", "")
        csv_category = csv_book.get("분야", "미분류")
        
        print_progress(
            f"[Phase 1: 준비] {idx}/{len(csv_books)} - {csv_title[:40]}..."
        )
        
        book_data = {
            "csv_book": csv_book,
            "csv_title": csv_title,
            "book_id": None,
            "pdf_file": None,
            "status": "pending",
        }
        
        try:
            # PDF 파일 찾기
            pdf_file = find_pdf_file(csv_title, search_dirs)
            if not pdf_file:
                book_data["status"] = "skipped"
                book_data["error"] = "PDF 파일을 찾을 수 없습니다"
                logger.warning(f"[PHASE 1] PDF 파일 없음: {csv_title}")
                continue
            
            book_data["pdf_file"] = pdf_file
            
            # 기존 Book 레코드 확인
            existing_book = db.query(Book).filter(Book.title == csv_title).first()
            
            if existing_book:
                book = existing_book
                book_data["book_id"] = book.id
                logger.info(f"[PHASE 1] 기존 Book 레코드: ID {book.id}, Status: {book.status}")
            else:
                # 새 Book 레코드 생성
                book = book_service.create_book(
                    file_path=pdf_file,
                    title=csv_title,
                    author=csv_author,
                    category=csv_category,
                )
                book_data["book_id"] = book.id
                logger.info(f"[PHASE 1] 새 Book 레코드 생성: ID {book.id}")
            
            books_data[book.id] = book_data
            
        except Exception as e:
            book_data["status"] = "failed"
            book_data["error"] = str(e)
            logger.error(f"[PHASE 1] 오류: {csv_title}, {e}", exc_info=True)
    
    print()  # 줄바꿈
    
    logger.info(f"[PHASE 1] 완료: {len(books_data)}개 Book 레코드 준비")
    logger.info("=" * 100)
    
    return books_data


def parse_all_books(
    books_data: Dict[int, Dict[str, Any]],
    db: Session,
    logger: logging.Logger,
) -> Dict[int, Dict[str, Any]]:
    """
    단계 2: 모든 책에 대해 파싱 완료
    
    Returns:
        업데이트된 books_data
    """
    logger.info("=" * 100)
    logger.info("[PHASE 2] PDF 파싱 시작 (모든 책)")
    logger.info("=" * 100)
    
    parsing_service = ParsingService(db)
    
    books_to_parse = [
        (book_id, book_data)
        for book_id, book_data in books_data.items()
        if book_data.get("status") != "skipped" and book_data.get("status") != "failed"
    ]
    
    for idx, (book_id, book_data) in enumerate(books_to_parse, start=1):
        csv_title = book_data.get("csv_title", "")
        
        print_progress(
            f"[Phase 2: 파싱] {idx}/{len(books_to_parse)} - {csv_title[:40]}..."
        )
        
        try:
            # DB에서 최신 상태 조회
            book = db.query(Book).filter(Book.id == book_id).first()
            if not book:
                book_data["status"] = "failed"
                book_data["error"] = "Book 레코드를 찾을 수 없습니다"
                logger.error(f"[PHASE 2] Book 레코드 없음: ID {book_id}")
                continue
            
            # 이미 파싱되었으면 스킵
            if book.status != BookStatus.UPLOADED:
                logger.info(f"[PHASE 2] 이미 파싱됨: ID {book_id}, Status: {book.status}")
                book_data["parsing"] = "skipped"
                print_progress(
                    f"[Phase 2: 파싱] {idx}/{len(books_to_parse)} - {csv_title[:40]}... 스킵 (이미 처리됨)"
                )
                continue
            
            logger.info(f"[PHASE 2] 파싱 시작: ID {book_id}, {csv_title}")
            parse_start = time.time()
            book = parsing_service.parse_book(book_id)
            parse_time = time.time() - parse_start
            
            book_data["parsing"] = "success"
            logger.info(f"[PHASE 2] 파싱 완료: ID {book_id}, 소요시간: {parse_time:.2f}초")
            
            # 콘솔에 파싱 완료 및 소요시간 출력
            print_progress(
                f"[Phase 2: 파싱] {idx}/{len(books_to_parse)} - {csv_title[:40]}... 완료 (소요시간: {parse_time:.1f}초)"
            )
            
        except Exception as e:
            book_data["parsing"] = "failed"
            book_data["error"] = str(e)
            logger.error(f"[PHASE 2] 파싱 실패: ID {book_id}, {e}", exc_info=True)
    
    print()  # 줄바꿈
    
    success_count = len([b for b in books_data.values() if b.get("parsing") == "success"])
    logger.info(f"[PHASE 2] 완료: {success_count}개 책 파싱 완료")
    logger.info("=" * 100)
    
    return books_data


def process_single_structure(
    book_id: int,
    book_data: Dict[str, Any],
    logger: logging.Logger,
    auto_apply: bool,
    total_books: int,
    completed_counter: Dict[str, int],
    phase_times: Dict[str, float],
) -> Dict[str, Any]:
    """단일 책 구조 분석 (병렬 처리용)"""
    csv_title = book_data.get("csv_title", "")
    
    # 각 작업마다 독립적인 DB 세션 생성
    db = SessionLocal()
    try:
        structure_service = StructureService(db)
        
        # DB에서 최신 상태 조회
        book = db.query(Book).filter(Book.id == book_id).first()
        if not book:
            book_data["status"] = "failed"
            book_data["error"] = "Book 레코드를 찾을 수 없습니다"
            logger.error(f"[PHASE 3] Book 레코드 없음: ID {book_id}")
            return book_data
        
        if book.status != BookStatus.PARSED:
            logger.info(f"[PHASE 3] 이미 구조 분석됨: ID {book_id}, Status: {book.status}")
            return book_data
        
        logger.info(f"[PHASE 3] 구조 분석 시작: ID {book_id}, {csv_title}")
        structure_start = time.time()
        
        # 구조 후보 생성
        candidates_result = structure_service.get_structure_candidates(book_id)
        auto_candidates = candidates_result.get("auto_candidates", [])
        
        if not auto_candidates:
            book_data["structure"] = "failed"
            book_data["error"] = "구조 후보를 생성할 수 없습니다"
            logger.error(f"[PHASE 3] 구조 후보 생성 실패: ID {book_id}")
            return book_data
        
        first_candidate = auto_candidates[0]
        
        if auto_apply:
            final_structure = convert_structure_to_final_input(first_candidate)
            book = structure_service.apply_final_structure(book_id, final_structure)
            structure_time = time.time() - structure_start
            
            book_data["structure"] = "success"
            logger.info(f"[PHASE 3] 구조 분석 완료: ID {book_id}, 소요시간: {structure_time:.2f}초")
        else:
            book_data["structure"] = "skipped"
            logger.info(f"[PHASE 3] 구조 후보 생성 완료 (적용 안 함): ID {book_id}")
        
    except Exception as e:
        book_data["structure"] = "failed"
        book_data["error"] = str(e)
        logger.error(f"[PHASE 3] 구조 분석 실패: ID {book_id}, {e}", exc_info=True)
    finally:
        db.close()
    
    # 진행률 업데이트 (스레드 안전)
    with progress_lock:
        completed_counter["count"] += 1
        completed = completed_counter["count"]
        progress = (completed / total_books) * 100 if total_books > 0 else 0
        
        # 경과 시간 및 예상 남은 시간 계산
        elapsed_time = time.time() - phase_times.get("start", time.time())
        avg_time_per_book = elapsed_time / completed if completed > 0 else 0
        remaining_books = total_books - completed
        estimated_remaining_time = avg_time_per_book * remaining_books
        
        print_progress(
            f"[Phase 3: 구조 분석] 진행률: {progress:.1f}% ({completed}/{total_books}) | "
            f"경과: {elapsed_time/60:.1f}분 | 예상 남은 시간: {estimated_remaining_time/60:.1f}분"
        )
    
    return book_data


def structure_all_books(
    books_data: Dict[int, Dict[str, Any]],
    db: Session,
    logger: logging.Logger,
    auto_apply: bool = True,
    max_workers: int = 3,
    phase_start_time: Optional[float] = None,
) -> Dict[int, Dict[str, Any]]:
    """
    단계 3: 모든 책에 대해 구조 분석 완료 (병렬 처리)
    
    Args:
        max_workers: 병렬 처리할 최대 스레드 수 (기본값: 3)
        phase_start_time: Phase 시작 시간 (진행률 계산용)
    
    Returns:
        업데이트된 books_data
    """
    logger.info("=" * 100)
    logger.info(f"[PHASE 3] 구조 분석 시작 (모든 책, 병렬 처리: {max_workers}개 스레드)")
    logger.info("=" * 100)
    
    phase_start = phase_start_time or time.time()
    
    books_to_structure = []
    for book_id, book_data in books_data.items():
        if book_data.get("status") in ["skipped", "failed"]:
            continue
        
        # DB에서 최신 상태 조회
        book = db.query(Book).filter(Book.id == book_id).first()
        if book and book.status == BookStatus.PARSED:
            books_to_structure.append((book_id, book_data))
    
    if not books_to_structure:
        logger.info("[PHASE 3] 처리할 책이 없습니다.")
        return books_data
    
    total_books = len(books_to_structure)
    completed_counter = {"count": 0}
    phase_times = {"start": phase_start}
    
    # ThreadPoolExecutor로 병렬 처리
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 모든 작업 제출
        future_to_book = {
            executor.submit(
                process_single_structure,
                book_id,
                book_data,
                logger,
                auto_apply,
                total_books,
                completed_counter,
                phase_times,
            ): (book_id, book_data)
            for book_id, book_data in books_to_structure
        }
        
        # 완료된 작업부터 처리
        for future in as_completed(future_to_book):
            book_id, book_data = future_to_book[future]
            try:
                result = future.result()
                books_data[book_id] = result
            except Exception as e:
                logger.error(f"[PHASE 3] 예외 발생: ID {book_id}, {e}", exc_info=True)
                book_data["structure"] = "failed"
                book_data["error"] = str(e)
    
    print()  # 줄바꿈
    
    success_count = len([b for b in books_data.values() if b.get("structure") == "success"])
    phase_time = time.time() - phase_start
    logger.info(f"[PHASE 3] 완료: {success_count}개 책 구조 분석 완료, 소요시간: {phase_time:.1f}초")
    logger.info("=" * 100)
    
    return books_data


def process_single_text(
    book_id: int,
    book_data: Dict[str, Any],
    logger: logging.Logger,
    total_books: int,
    completed_counter: Dict[str, int],
    phase_times: Dict[str, float],
) -> Dict[str, Any]:
    """단일 책 텍스트 파일 생성 (병렬 처리용)"""
    csv_title = book_data.get("csv_title", "")
    
    # 각 작업마다 독립적인 DB 세션 생성
    db = SessionLocal()
    try:
        text_organizer_service = TextOrganizerService(db)
        
        # DB에서 최신 상태 조회
        book = db.query(Book).filter(Book.id == book_id).first()
        if not book:
            book_data["status"] = "failed"
            book_data["error"] = "Book 레코드를 찾을 수 없습니다"
            logger.error(f"[PHASE 4] Book 레코드 없음: ID {book_id}")
            return book_data
        
        if book.status != BookStatus.STRUCTURED:
            logger.info(f"[PHASE 4] 이미 텍스트 파일 생성됨: ID {book_id}, Status: {book.status}")
            return book_data
        
        logger.info(f"[PHASE 4] 텍스트 정리 시작: ID {book_id}, {csv_title}")
        text_start = time.time()
        
        text_file_path = text_organizer_service.organize_book_text(book_id)
        text_time = time.time() - text_start
        
        book_data["text_file"] = "success"
        book_data["text_file_path"] = str(text_file_path)
        logger.info(f"[PHASE 4] 텍스트 정리 완료: ID {book_id}, 파일: {text_file_path}, 소요시간: {text_time:.2f}초")
        
    except Exception as e:
        book_data["text_file"] = "failed"
        book_data["error"] = str(e)
        logger.error(f"[PHASE 4] 텍스트 정리 실패: ID {book_id}, {e}", exc_info=True)
    finally:
        db.close()
    
    # 진행률 업데이트 (스레드 안전)
    with progress_lock:
        completed_counter["count"] += 1
        completed = completed_counter["count"]
        progress = (completed / total_books) * 100 if total_books > 0 else 0
        
        # 경과 시간 및 예상 남은 시간 계산
        elapsed_time = time.time() - phase_times.get("start", time.time())
        avg_time_per_book = elapsed_time / completed if completed > 0 else 0
        remaining_books = total_books - completed
        estimated_remaining_time = avg_time_per_book * remaining_books
        
        print_progress(
            f"[Phase 4: 텍스트 생성] 진행률: {progress:.1f}% ({completed}/{total_books}) | "
            f"경과: {elapsed_time/60:.1f}분 | 예상 남은 시간: {estimated_remaining_time/60:.1f}분"
        )
    
    return book_data


def text_all_books(
    books_data: Dict[int, Dict[str, Any]],
    db: Session,
    logger: logging.Logger,
    max_workers: int = 3,
    phase_start_time: Optional[float] = None,
) -> Dict[int, Dict[str, Any]]:
    """
    단계 4: 모든 책에 대해 텍스트 파일 생성 완료 (병렬 처리)
    
    Args:
        max_workers: 병렬 처리할 최대 스레드 수 (기본값: 3)
        phase_start_time: Phase 시작 시간 (진행률 계산용)
    
    Returns:
        업데이트된 books_data
    """
    logger.info("=" * 100)
    logger.info(f"[PHASE 4] 텍스트 파일 생성 시작 (모든 책, 병렬 처리: {max_workers}개 스레드)")
    logger.info("=" * 100)
    
    phase_start = phase_start_time or time.time()
    
    books_to_text = []
    for book_id, book_data in books_data.items():
        if book_data.get("status") in ["skipped", "failed"]:
            continue
        
        # DB에서 최신 상태 조회
        book = db.query(Book).filter(Book.id == book_id).first()
        if book and book.status == BookStatus.STRUCTURED:
            books_to_text.append((book_id, book_data))
    
    if not books_to_text:
        logger.info("[PHASE 4] 처리할 책이 없습니다.")
        return books_data
    
    total_books = len(books_to_text)
    completed_counter = {"count": 0}
    phase_times = {"start": phase_start}
    
    # ThreadPoolExecutor로 병렬 처리
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 모든 작업 제출
        future_to_book = {
            executor.submit(
                process_single_text,
                book_id,
                book_data,
                logger,
                total_books,
                completed_counter,
                phase_times,
            ): (book_id, book_data)
            for book_id, book_data in books_to_text
        }
        
        # 완료된 작업부터 처리
        for future in as_completed(future_to_book):
            book_id, book_data = future_to_book[future]
            try:
                result = future.result()
                books_data[book_id] = result
            except Exception as e:
                logger.error(f"[PHASE 4] 예외 발생: ID {book_id}, {e}", exc_info=True)
                book_data["text_file"] = "failed"
                book_data["error"] = str(e)
    
    print()  # 줄바꿈
    
    success_count = len([b for b in books_data.values() if b.get("text_file") == "success"])
    phase_time = time.time() - phase_start
    logger.info(f"[PHASE 4] 완료: {success_count}개 책 텍스트 파일 생성 완료, 소요시간: {phase_time:.1f}초")
    logger.info("=" * 100)
    
    return books_data


def batch_process_books_step_by_step(
    csv_path: Path,
    search_dirs: List[Path],
    log_file: Path,
    auto_apply_structure: bool = True,
    generate_text_files: bool = True,
    max_books: Optional[int] = None,
) -> Dict[str, Any]:
    """
    대량 도서 처리 (단계별 배치)
    
    1. 모든 책에 대해 파싱 완료
    2. 모든 책에 대해 구조 분석 완료
    3. 모든 책에 대해 텍스트 파일 생성 완료
    
    Args:
        csv_path: CSV 파일 경로
        search_dirs: PDF 파일 검색 디렉토리 리스트
        log_file: 로그 파일 경로
        auto_apply_structure: 구조 분석 결과를 자동으로 적용할지 여부
        generate_text_files: 텍스트 파일 생성 여부
        max_books: 처리할 최대 책 개수 (None이면 전체 처리, 테스트용으로 제한 가능)
    """
    logger = setup_logging(log_file)
    
    logger.info("=" * 100)
    logger.info("[BATCH PROCESS] 대량 도서 처리 시작 (단계별 배치)")
    logger.info(f"[BATCH PROCESS] CSV 파일: {csv_path}")
    logger.info(f"[BATCH PROCESS] 로그 파일: {log_file}")
    logger.info("=" * 100)
    
    batch_start_time = time.time()
    
    # CSV 파일 읽기
    logger.info("[INIT] CSV 파일 읽기")
    csv_parser = BookCSVParser()
    csv_books = csv_parser.parse_book_list(csv_path)
    logger.info(f"[INIT] CSV에서 {len(csv_books)}개 도서 발견")
    
    # 이미 처리된 도서 제외
    db = SessionLocal()
    try:
        logger.info("[INIT] 이미 처리된 도서 확인 중...")
        checker = ProcessedBooksChecker()
        
        pending_books = []
        skipped_books = []
        
        for csv_book in csv_books:
            csv_title = csv_book.get("Title", "")
            if checker.is_book_processed(csv_title, db):
                skipped_books.append(csv_book)
            else:
                pending_books.append(csv_book)
        
        logger.info(f"[INIT] 처리 대기: {len(pending_books)}개, 이미 처리됨: {len(skipped_books)}개")
        
        # max_books 제한 적용 (테스트용)
        if max_books is not None and max_books > 0:
            original_count = len(pending_books)
            pending_books = pending_books[:max_books]
            logger.info(f"[INIT] 처리 개수 제한: {original_count}개 중 {len(pending_books)}개만 처리 (max_books={max_books})")
            print(f"[INFO] 처리 개수 제한: {len(pending_books)}권만 처리합니다.")
        
        # Phase 1: PDF 파일 찾기 및 Book 레코드 생성
        print(f"\n[Phase 1/4] PDF 파일 찾기 및 Book 레코드 생성...")
        books_data = prepare_books(pending_books, db, search_dirs, logger)
        
        # Phase 2: 모든 책 파싱
        print(f"\n[Phase 2/4] PDF 파싱 (모든 책)...")
        books_data = parse_all_books(books_data, db, logger)
        
        # Phase 3: 모든 책 구조 분석 (병렬 처리)
        if auto_apply_structure:
            print(f"\n[Phase 3/4] 구조 분석 (모든 책, 병렬 처리)...")
            phase3_start = time.time()
            books_data = structure_all_books(
                books_data, db, logger, 
                auto_apply=True, 
                max_workers=3,  # 기본값
                phase_start_time=phase3_start
            )
        else:
            logger.info("[PHASE 3] 구조 분석 스킵 (auto_apply_structure=False)")
        
        # Phase 4: 모든 책 텍스트 파일 생성 (병렬 처리)
        if generate_text_files:
            print(f"\n[Phase 4/4] 텍스트 파일 생성 (모든 책, 병렬 처리)...")
            phase4_start = time.time()
            books_data = text_all_books(
                books_data, db, logger, 
                max_workers=3,  # 기본값
                phase_start_time=phase4_start
            )
        else:
            logger.info("[PHASE 4] 텍스트 파일 생성 스킵 (generate_text_files=False)")
        
        # 결과 집계
        total_count = len(csv_books)
        prepared_count = len(books_data)
        parsing_success = len([b for b in books_data.values() if b.get("parsing") == "success"])
        structure_success = len([b for b in books_data.values() if b.get("structure") == "success"])
        text_success = len([b for b in books_data.values() if b.get("text_file") == "success"])
        
        batch_time = time.time() - batch_start_time
        
        report = {
            "total": total_count,
            "prepared": prepared_count,
            "skipped": len(skipped_books),
            "parsing_success": parsing_success,
            "structure_success": structure_success,
            "text_success": text_success,
            "books_data": books_data,
            "log_file": str(log_file),
            "elapsed_time": batch_time,
        }
        
        logger.info("=" * 100)
        logger.info("[BATCH PROCESS] 대량 도서 처리 완료")
        logger.info(f"[BATCH PROCESS] 전체: {total_count}개")
        logger.info(f"[BATCH PROCESS] 준비 완료: {prepared_count}개")
        logger.info(f"[BATCH PROCESS] 이미 처리됨: {len(skipped_books)}개")
        logger.info(f"[BATCH PROCESS] 파싱 완료: {parsing_success}개")
        logger.info(f"[BATCH PROCESS] 구조 분석 완료: {structure_success}개")
        logger.info(f"[BATCH PROCESS] 텍스트 파일 생성 완료: {text_success}개")
        logger.info(f"[BATCH PROCESS] 총 소요시간: {batch_time/60:.1f}분 ({batch_time:.1f}초)")
        logger.info("=" * 100)
        
        return report
        
    finally:
        db.close()


if __name__ == "__main__":
    # 설정
    csv_file = project_root / "docs" / "100권 노션 원본_수정.csv"
    search_dirs = [
        project_root / "data" / "input",
    ]
    
    # 로그 파일 경로
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = LOG_DIR / f"batch_process_step_by_step_{timestamp}.log"
    
    # DB 초기화
    init_db()
    
    print(f"\n{'='*80}")
    print(f"대량 도서 처리 시작 (단계별 배치)")
    print(f"로그 파일: {log_file}")
    print(f"{'='*80}\n")
    
    # 대량 처리 실행
    # max_books: None이면 전체 처리, 숫자를 지정하면 그 개수만 처리 (테스트용)
    # 예: max_books=5 → 5권만 처리
    import os
    max_books_env = os.getenv("MAX_BOOKS")
    max_books = int(max_books_env) if max_books_env and max_books_env.isdigit() else None
    
    if max_books:
        print(f"[INFO] 처리 개수 제한: {max_books}권만 처리합니다.")
    
    report = batch_process_books_step_by_step(
        csv_path=csv_file,
        search_dirs=search_dirs,
        log_file=log_file,
        auto_apply_structure=True,
        generate_text_files=True,
        max_books=max_books,
    )
    
    # 결과 출력
    print(f"\n{'='*80}")
    print("처리 완료 리포트")
    print(f"{'='*80}")
    print(f"전체: {report['total']}개")
    print(f"준비 완료: {report['prepared']}개")
    print(f"이미 처리됨: {report['skipped']}개")
    print(f"파싱 완료: {report['parsing_success']}개")
    print(f"구조 분석 완료: {report['structure_success']}개")
    print(f"텍스트 파일 생성 완료: {report['text_success']}개")
    print(f"총 소요시간: {report['elapsed_time']/60:.1f}분")
    print(f"상세 로그: {report['log_file']}")
    print(f"{'='*80}\n")

