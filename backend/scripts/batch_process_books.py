"""
대량 도서 처리 스크립트

CSV 파일에 있는 도서를 일괄 처리합니다 (파싱 + 구조 분석 + 텍스트 파일 생성).
이미 처리된 도서는 자동으로 제외됩니다.
"""
import logging
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import time

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
    """
    로깅 설정
    
    - 파일 핸들러: 상세 로그 (INFO 레벨)
    - 콘솔 핸들러: 간단한 진행률만 (WARNING 레벨, 사용자 정의 포맷)
    
    Args:
        log_file: 로그 파일 경로
        
    Returns:
        로거 객체
    """
    logger = logging.getLogger("batch_process")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()  # 기존 핸들러 제거
    
    # 파일 핸들러 (상세 로그)
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    
    # 콘솔 핸들러는 setup_console_logging에서 별도 설정
    
    return logger


def setup_console_logging():
    """콘솔에는 진행률과 소요시간만 출력"""
    console_logger = logging.getLogger("console")
    console_logger.setLevel(logging.INFO)
    console_logger.handlers.clear()
    
    class ProgressFormatter(logging.Formatter):
        """진행률 전용 포맷터"""
        def format(self, record):
            # 진행률 메시지만 포맷팅
            if hasattr(record, 'progress'):
                return f"{record.msg}"
            return ""
    
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(ProgressFormatter())
    console_logger.addHandler(console_handler)
    
    return console_logger


def print_progress(message: str):
    """진행률 메시지를 콘솔에 출력"""
    print(f"\r{message}", end="", flush=True)


def find_pdf_file(book_title: str, search_dirs: List[Path]) -> Optional[Path]:
    """
    PDF 파일 경로 찾기
    
    Args:
        book_title: 책 제목
        search_dirs: 검색할 디렉토리 리스트
        
    Returns:
        PDF 파일 경로 또는 None
    """
    # 제목 정규화 (파일명 매칭용)
    normalized_title = book_title.replace(" ", "").replace("　", "")
    
    for search_dir in search_dirs:
        if not search_dir.exists():
            continue
            
        # 직접 매칭 시도
        pdf_file = search_dir / f"{book_title}.pdf"
        if pdf_file.exists():
            return pdf_file
        
        # 정규화된 제목으로 매칭
        pdf_file = search_dir / f"{normalized_title}.pdf"
        if pdf_file.exists():
            return pdf_file
        
        # 부분 매칭 시도 (파일명에 제목이 포함된 경우)
        for pdf_file in search_dir.glob("*.pdf"):
            if normalized_title in pdf_file.stem.replace(" ", "").replace("　", ""):
                return pdf_file
    
    return None


def convert_structure_to_final_input(
    structure_candidate: Dict[str, Any]
) -> FinalStructureInput:
    """
    구조 후보를 FinalStructureInput으로 변환
    
    Args:
        structure_candidate: 구조 후보 딕셔너리
            {
                "label": "footer_based_v1",
                "structure": {
                    "start": {"pages": [...]},
                    "main": {
                        "pages": [...],
                        "chapters": [
                            {
                                "id": "ch1",
                                "number": 1,
                                "title": "제1장 ...",
                                "start_page": 4,
                                "end_page": 25
                            },
                            ...
                        ]
                    },
                    "end": {"pages": [...]}
                }
            }
        
    Returns:
        FinalStructureInput 객체
    """
    structure = structure_candidate.get("structure", {})
    main = structure.get("main", {})
    main_pages = main.get("pages", [])
    chapters = main.get("chapters", [])
    
    # main_start_page: main의 첫 번째 페이지
    main_start_page = main_pages[0] if main_pages else 1
    
    # main_end_page: main의 마지막 페이지
    main_end_page = main_pages[-1] if main_pages else None
    
    # FinalChapterInput 리스트 생성
    final_chapters = []
    for idx, chapter in enumerate(chapters):
        final_chapter = FinalChapterInput(
            title=chapter.get("title", f"제{idx+1}장"),
            start_page=chapter.get("start_page", 1),
            end_page=chapter.get("end_page", 1),
            order_index=chapter.get("number") - 1 if chapter.get("number") else idx,
        )
        final_chapters.append(final_chapter)
    
    # FinalStructureInput 생성
    final_structure = FinalStructureInput(
        main_start_page=main_start_page,
        main_end_page=main_end_page,
        chapters=final_chapters,
        notes_pages=[],
        start_pages=[],
        end_pages=[],
    )
    
    return final_structure


def process_single_book(
    csv_book: Dict[str, Any],
    db: Session,
    search_dirs: List[Path],
    logger: logging.Logger,
    auto_apply_structure: bool = True,
    generate_text_files: bool = True,
) -> Dict[str, Any]:
    """
    단일 도서 처리
    
    Args:
        csv_book: CSV에서 읽은 도서 정보
        db: 데이터베이스 세션
        search_dirs: PDF 파일 검색 디렉토리 리스트
        logger: 로거 객체
        auto_apply_structure: 구조 분석 결과를 자동으로 적용할지 여부
        generate_text_files: 텍스트 파일 생성 여부 (구조 분석 완료 후)
        
    Returns:
        처리 결과 딕셔너리
        {
            "csv_title": str,
            "status": "success" | "failed" | "skipped",
            "book_id": int | None,
            "error": str | None,
            "message": str,
            "steps": {
                "pdf_found": bool,
                "book_created": bool,
                "parsing": "success" | "failed" | "skipped",
                "structure": "success" | "failed" | "skipped",
                "text_file": "success" | "failed" | "skipped",
            },
            "output_files": {
                "cache_file": Optional[str],
                "structure_file": Optional[str],
                "text_file": Optional[str],
            }
        }
    """
    csv_title = csv_book.get("Title", "")
    csv_author = csv_book.get("저자", "")
    csv_category = csv_book.get("분야", "미분류")
    
    result = {
        "csv_title": csv_title,
        "status": "failed",
        "book_id": None,
        "error": None,
        "message": "",
        "steps": {
            "pdf_found": False,
            "book_created": False,
            "parsing": "skipped",
            "structure": "skipped",
            "text_file": "skipped",
        },
        "output_files": {
            "cache_file": None,
            "structure_file": None,
            "text_file": None,
        }
    }
    
    book_start_time = time.time()
    
    try:
        logger.info("=" * 80)
        logger.info(f"[BOOK] 처리 시작: {csv_title}")
        logger.info("=" * 80)
        
        # 1. PDF 파일 경로 확인
        logger.info(f"[STEP 1] PDF 파일 찾는 중: {csv_title}")
        pdf_file = find_pdf_file(csv_title, search_dirs)
        
        if not pdf_file:
            result["status"] = "skipped"
            result["message"] = f"PDF 파일을 찾을 수 없습니다: {csv_title}"
            result["error"] = "PDF file not found"
            logger.warning(f"[WARNING] {result['message']}")
            return result
        
        result["steps"]["pdf_found"] = True
        logger.info(f"[STEP 1] PDF 파일 발견: {pdf_file}")
        
        # 2. Book 레코드 생성 또는 조회
        logger.info(f"[STEP 2] Book 레코드 생성/조회 시작")
        book_service = BookService(db)
        
        # 기존 Book 레코드 확인
        existing_book = (
            db.query(Book)
            .filter(Book.title == csv_title)
            .first()
        )
        
        if existing_book:
            book = existing_book
            logger.info(f"[STEP 2] 기존 Book 레코드 사용: ID {book.id}, Status: {book.status}")
        else:
            # 새 Book 레코드 생성
            book = book_service.create_book(
                file_path=pdf_file,
                title=csv_title,
                author=csv_author,
                category=csv_category,
            )
            result["steps"]["book_created"] = True
            logger.info(f"[STEP 2] 새 Book 레코드 생성: ID {book.id}")
        
        result["book_id"] = book.id
        
        # 3. PDF 파싱 실행 (이미 파싱되었으면 스킵)
        if book.status == BookStatus.UPLOADED:
            logger.info(f"[STEP 3] PDF 파싱 시작: Book ID {book.id}")
            parsing_start = time.time()
            parsing_service = ParsingService(db)
            book = parsing_service.parse_book(book.id)
            parsing_time = time.time() - parsing_start
            result["steps"]["parsing"] = "success"
            logger.info(f"[STEP 3] PDF 파싱 완료: Book ID {book.id}, Status: {book.status}, 소요시간: {parsing_time:.2f}초")
        else:
            result["steps"]["parsing"] = "skipped"
            logger.info(f"[STEP 3] 이미 파싱됨: Book ID {book.id}, Status: {book.status}")
        
        # 캐시 파일 확인
        from backend.parsers.cache_manager import CacheManager
        cache_manager = CacheManager()
        cache_key = cache_manager.get_file_hash(str(pdf_file))
        cache_file = cache_manager.cache_dir / f"{cache_key}.json"
        if cache_file.exists():
            result["output_files"]["cache_file"] = str(cache_file)
            logger.info(f"[FILE] 캐시 파일: {cache_file}")
        
        # 4. 구조 분석 실행 (이미 구조 분석되었으면 스킵)
        if book.status == BookStatus.PARSED:
            logger.info(f"[STEP 4] 구조 분석 시작: Book ID {book.id}")
            structure_start = time.time()
            structure_service = StructureService(db)
            
            # 구조 후보 생성
            candidates_result = structure_service.get_structure_candidates(book.id)
            auto_candidates = candidates_result.get("auto_candidates", [])
            
            if not auto_candidates:
                result["status"] = "failed"
                result["error"] = "구조 후보를 생성할 수 없습니다"
                result["steps"]["structure"] = "failed"
                logger.error(f"[ERROR] {result['error']}")
                return result
            
            # 첫 번째 후보 선택
            first_candidate = auto_candidates[0]
            structure_data = first_candidate.get("structure", {})
            
            logger.info(f"[STEP 4] 구조 후보 생성 완료: {first_candidate.get('label', 'unknown')}")
            
            # 자동 적용
            if auto_apply_structure:
                final_structure = convert_structure_to_final_input(first_candidate)
                book = structure_service.apply_final_structure(book.id, final_structure)
                structure_time = time.time() - structure_start
                result["steps"]["structure"] = "success"
                logger.info(f"[STEP 4] 구조 분석 완료: Book ID {book.id}, Status: {book.status}, 소요시간: {structure_time:.2f}초")
            else:
                result["steps"]["structure"] = "skipped"
                logger.info(f"[STEP 4] 구조 후보 생성 완료 (자동 적용 안 함): Book ID {book.id}")
            
            # 구조 파일 확인
            from backend.config.settings import settings
            structure_dir = settings.output_dir / "structure"
            structure_pattern = f"*_{book.id}_structure.json"
            for structure_file in structure_dir.glob(structure_pattern):
                result["output_files"]["structure_file"] = str(structure_file)
                logger.info(f"[FILE] 구조 파일: {structure_file}")
                break
        else:
            result["steps"]["structure"] = "skipped"
            logger.info(f"[STEP 4] 이미 구조 분석됨: Book ID {book.id}, Status: {book.status}")
        
        # 5. 텍스트 정리 실행 (이미 텍스트 정리되었으면 스킵)
        if generate_text_files and book.status == BookStatus.STRUCTURED:
            logger.info(f"[STEP 5] 텍스트 정리 시작: Book ID {book.id}")
            text_start = time.time()
            text_organizer_service = TextOrganizerService(db)
            
            try:
                text_file_path = text_organizer_service.organize_book_text(book.id)
                text_time = time.time() - text_start
                result["steps"]["text_file"] = "success"
                result["output_files"]["text_file"] = str(text_file_path)
                logger.info(f"[STEP 5] 텍스트 정리 완료: Book ID {book.id}, 파일: {text_file_path}, 소요시간: {text_time:.2f}초")
            except Exception as e:
                result["steps"]["text_file"] = "failed"
                logger.error(f"[ERROR] 텍스트 정리 실패: Book ID {book.id}, 오류: {e}", exc_info=True)
                # 텍스트 정리 실패해도 전체 처리 실패로 간주하지 않음 (구조 분석은 완료됨)
        else:
            result["steps"]["text_file"] = "skipped"
            logger.info(f"[STEP 5] 텍스트 정리 스킵: Book ID {book.id}, Status: {book.status}")
        
        book_time = time.time() - book_start_time
        result["status"] = "success"
        result["message"] = f"처리 완료: Book ID {book.id}, Status: {book.status}"
        logger.info(f"[BOOK] 처리 완료: {csv_title}, 소요시간: {book_time:.2f}초")
        logger.info("=" * 80)
        
    except Exception as e:
        result["status"] = "failed"
        result["error"] = str(e)
        result["message"] = f"처리 실패: {e}"
        logger.error(f"[ERROR] {csv_title} 처리 중 오류 발생: {e}", exc_info=True)
        logger.info("=" * 80)
    
    return result


def batch_process_books(
    csv_path: Path,
    search_dirs: List[Path],
    log_file: Path,
    auto_apply_structure: bool = True,
    generate_text_files: bool = True,
) -> Dict[str, Any]:
    """
    대량 도서 처리
    
    Args:
        csv_path: CSV 파일 경로
        search_dirs: PDF 파일 검색 디렉토리 리스트
        log_file: 로그 파일 경로
        auto_apply_structure: 구조 분석 결과를 자동으로 적용할지 여부
        generate_text_files: 텍스트 파일 생성 여부 (구조 분석 완료 후)
        
    Returns:
        처리 결과 리포트
        {
            "total": int,
            "processed": int,
            "skipped": int,
            "failed": int,
            "results": List[Dict[str, Any]],
            "category_stats": Dict[str, int],
            "log_file": str,
        }
    """
    # 로깅 설정
    logger = setup_logging(log_file)
    
    logger.info("=" * 100)
    logger.info("[BATCH PROCESS] 대량 도서 처리 시작")
    logger.info(f"[BATCH PROCESS] CSV 파일: {csv_path}")
    logger.info(f"[BATCH PROCESS] 검색 디렉토리: {search_dirs}")
    logger.info(f"[BATCH PROCESS] 로그 파일: {log_file}")
    logger.info("=" * 100)
    
    batch_start_time = time.time()
    
    # 1. CSV 파일 읽기
    logger.info("[STEP 1] CSV 파일 읽기")
    csv_parser = BookCSVParser()
    csv_books = csv_parser.parse_book_list(csv_path)
    logger.info(f"[STEP 1] CSV에서 {len(csv_books)}개 도서 발견")
    
    # 2. 이미 처리된 도서 제외
    logger.info("[STEP 2] 이미 처리된 도서 확인 중...")
    db = SessionLocal()
    try:
        checker = ProcessedBooksChecker()
        processed_titles = checker.get_processed_titles(db)
        
        pending_books = []
        skipped_books = []
        
        for csv_book in csv_books:
            csv_title = csv_book.get("Title", "")
            if checker.is_book_processed(csv_title, db):
                skipped_books.append(csv_book)
            else:
                pending_books.append(csv_book)
        
        logger.info(f"[STEP 2] 처리 대기: {len(pending_books)}개, 이미 처리됨: {len(skipped_books)}개")
        
        # 3. 각 도서별 처리
        logger.info("[STEP 3] 도서 처리 시작...")
        results = []
        
        for idx, csv_book in enumerate(pending_books, start=1):
            csv_title = csv_book.get("Title", "")
            
            # 진행률 출력 (콘솔)
            progress = (idx / len(pending_books)) * 100
            elapsed_time = time.time() - batch_start_time
            avg_time_per_book = elapsed_time / idx if idx > 0 else 0
            remaining_books = len(pending_books) - idx
            estimated_remaining_time = avg_time_per_book * remaining_books
            
            print_progress(
                f"[진행률: {progress:.1f}%] ({idx}/{len(pending_books)}) "
                f"현재: {csv_title[:30]}... | "
                f"경과: {elapsed_time/60:.1f}분 | "
                f"예상 남은 시간: {estimated_remaining_time/60:.1f}분"
            )
            
            result = process_single_book(
                csv_book,
                db,
                search_dirs,
                logger,
                auto_apply_structure=auto_apply_structure,
                generate_text_files=generate_text_files,
            )
            results.append(result)
        
        print()  # 진행률 출력 후 줄바꿈
        
        # 4. 결과 집계
        total_count = len(csv_books)
        processed_count = len([r for r in results if r["status"] == "success"])
        skipped_count = len(skipped_books)
        failed_count = len([r for r in results if r["status"] == "failed"])
        
        # 분야별 통계
        category_stats = {}
        for result in results:
            if result["status"] == "success":
                # CSV에서 분야 찾기
                csv_book = next(
                    (b for b in csv_books if b.get("Title") == result["csv_title"]),
                    None
                )
                if csv_book:
                    category = csv_book.get("분야", "미분류")
                    category_stats[category] = category_stats.get(category, 0) + 1
        
        batch_time = time.time() - batch_start_time
        
        report = {
            "total": total_count,
            "processed": processed_count,
            "skipped": skipped_count,
            "failed": failed_count,
            "results": results,
            "category_stats": category_stats,
            "log_file": str(log_file),
            "elapsed_time": batch_time,
        }
        
        logger.info("=" * 100)
        logger.info("[BATCH PROCESS] 대량 도서 처리 완료")
        logger.info(f"[BATCH PROCESS] 전체: {total_count}개")
        logger.info(f"[BATCH PROCESS] 처리 완료: {processed_count}개")
        logger.info(f"[BATCH PROCESS] 이미 처리됨: {skipped_count}개")
        logger.info(f"[BATCH PROCESS] 실패: {failed_count}개")
        logger.info(f"[BATCH PROCESS] 총 소요시간: {batch_time/60:.1f}분 ({batch_time:.1f}초)")
        logger.info("=" * 100)
        
        if category_stats:
            logger.info("[BATCH PROCESS] 분야별 통계:")
            for category, count in sorted(category_stats.items()):
                logger.info(f"  {category}: {count}개")
        
        return report
        
    finally:
        db.close()


if __name__ == "__main__":
    # 설정
    csv_file = project_root / "docs" / "100권 노션 원본_수정.csv"
    search_dirs = [
        project_root / "data" / "input",
        # 추가 검색 디렉토리 필요 시 여기에 추가
    ]
    
    # 로그 파일 경로 (타임스탬프 포함)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = LOG_DIR / f"batch_process_{timestamp}.log"
    
    # DB 초기화
    init_db()
    
    print(f"\n{'='*80}")
    print(f"대량 도서 처리 시작")
    print(f"로그 파일: {log_file}")
    print(f"{'='*80}\n")
    
    # 대량 처리 실행
    report = batch_process_books(
        csv_path=csv_file,
        search_dirs=search_dirs,
        log_file=log_file,
        auto_apply_structure=True,  # 구조 분석 결과를 자동으로 적용
        generate_text_files=True,  # 텍스트 파일 생성
    )
    
    # 결과 출력 (콘솔)
    print(f"\n{'='*80}")
    print("처리 완료 리포트")
    print(f"{'='*80}")
    print(f"전체: {report['total']}개")
    print(f"처리 완료: {report['processed']}개")
    print(f"이미 처리됨: {report['skipped']}개")
    print(f"실패: {report['failed']}개")
    print(f"총 소요시간: {report['elapsed_time']/60:.1f}분 ({report['elapsed_time']:.1f}초)")
    print(f"상세 로그: {report['log_file']}")
    print(f"{'='*80}\n")
    
    if report["failed"] > 0:
        print("실패한 도서:")
        for result in report["results"]:
            if result["status"] == "failed":
                print(f"  - {result['csv_title']}: {result['error']}")
        print()
