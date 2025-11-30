"""
Phase 4: 텍스트 생성 문제 해결 스크립트

ID 219: 김대식 빅퀘스천의 텍스트 파일 생성
"""
import sys
import logging
from pathlib import Path
from datetime import datetime
import time

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy.orm import Session

from backend.api.database import SessionLocal, init_db
from backend.api.models.book import Book, BookStatus
from backend.api.services.text_organizer_service import TextOrganizerService

# 로그 디렉토리 설정
LOG_DIR = project_root / "data" / "logs" / "batch_processing"
LOG_DIR.mkdir(parents=True, exist_ok=True)


def setup_logging() -> logging.Logger:
    """로깅 설정"""
    log_file = LOG_DIR / f"fix_text_generation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    
    logger = logging.getLogger("fix_text_generation")
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


def check_and_fix_structure(book_id: int, db: Session, logger: logging.Logger) -> bool:
    """구조 데이터 확인 및 수정 (챕터가 없으면 재구조 분석)"""
    from backend.api.services.structure_service import StructureService
    from backend.api.schemas.structure import FinalStructureInput, FinalChapterInput
    
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        return False
    
    # 구조 데이터 확인
    structure_data = book.structure_data or {}
    chapters = structure_data.get("chapters", [])
    
    if len(chapters) == 0:
        logger.info(f"[INFO] 챕터가 없습니다. 구조 분석을 다시 실행합니다.")
        print(f"[INFO] 챕터가 없습니다. 구조 분석을 다시 실행합니다.")
        
        # Status를 PARSED로 변경하여 구조 분석 가능하게 함
        book.status = BookStatus.PARSED
        db.commit()
        
        try:
            structure_service = StructureService(db)
            candidates_result = structure_service.get_structure_candidates(book_id)
            auto_candidates = candidates_result.get("auto_candidates", [])
            
            if not auto_candidates:
                logger.error(f"[ERROR] 구조 후보를 생성할 수 없습니다.")
                return False
            
            # 첫 번째 후보 선택
            first_candidate = auto_candidates[0]
            structure = first_candidate.get("structure", {})
            main = structure.get("main", {})
            main_pages = main.get("pages", [])
            chapters = main.get("chapters", [])
            
            main_start_page = main_pages[0] if main_pages else 1
            main_end_page = main_pages[-1] if main_pages else None
            
            # 챕터가 여전히 없으면 전체를 하나의 챕터로 처리
            if len(chapters) == 0:
                logger.info(f"[INFO] 챕터가 탐지되지 않았습니다. 전체를 하나의 챕터로 처리합니다.")
                print(f"[INFO] 챕터가 탐지되지 않았습니다. 전체를 하나의 챕터로 처리합니다.")
                final_chapters = [
                    FinalChapterInput(
                        title="전체",
                        start_page=main_start_page,
                        end_page=main_end_page or book.page_count or 1,
                    )
                ]
            else:
                final_chapters = [
                    FinalChapterInput(
                        title=ch.get("title", f"제{idx+1}장"),
                        start_page=ch.get("start_page", 1),
                        end_page=ch.get("end_page", 1),
                    )
                    for idx, ch in enumerate(chapters)
                ]
            
            final_structure = FinalStructureInput(
                main_start_page=main_start_page,
                main_end_page=main_end_page,
                chapters=final_chapters,
                notes_pages=[],
                start_pages=[],
                end_pages=[],
            )
            
            structure_service.apply_final_structure(book_id, final_structure)
            logger.info(f"[INFO] 구조 분석 완료: 챕터 {len(final_chapters)}개")
            print(f"[INFO] 구조 분석 완료: 챕터 {len(final_chapters)}개")
            return True
            
        except Exception as e:
            logger.error(f"[ERROR] 구조 분석 실패: {e}", exc_info=True)
            return False
    
    return True


def generate_text_file(book_id: int, db: Session, logger: logging.Logger) -> bool:
    """책 텍스트 파일 생성"""
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        logger.error(f"[ERROR] Book 레코드 없음: ID {book_id}")
        return False
    
    logger.info(f"[INFO] 책 정보: ID {book_id}, 제목: {book.title}, Status: {book.status.value}")
    
    # 구조 데이터 확인 및 수정
    if not check_and_fix_structure(book_id, db, logger):
        logger.error(f"[ERROR] 구조 데이터 수정 실패")
        return False
    
    # 최신 상태 다시 조회
    db.refresh(book)
    
    if book.status != BookStatus.STRUCTURED:
        logger.warning(f"[WARNING] 구조 분석 완료 상태가 아님: ID {book_id}, Status: {book.status}")
        return False
    
    try:
        logger.info(f"[PHASE 4] 텍스트 파일 생성 시작: ID {book_id}, {book.title}")
        text_start = time.time()
        
        text_organizer_service = TextOrganizerService(db)
        text_file_path = text_organizer_service.organize_book_text(book_id)
        
        text_time = time.time() - text_start
        logger.info(f"[PHASE 4] 텍스트 파일 생성 완료: ID {book_id}, 파일: {text_file_path}, 소요시간: {text_time:.1f}초")
        print(f"[완료] 텍스트 파일 생성 완료: {text_file_path}")
        print(f"  소요시간: {text_time:.1f}초")
        return True
        
    except Exception as e:
        logger.error(f"[ERROR] 텍스트 파일 생성 실패: ID {book_id}, {e}", exc_info=True)
        print(f"[실패] 텍스트 파일 생성 실패: {e}")
        return False


def verify_text_file(book_id: int, db: Session) -> bool:
    """텍스트 파일 존재 여부 확인"""
    from backend.scripts.diagnose_processing_issues import find_text_file
    
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        return False
    
    text_file = find_text_file(book)
    return text_file is not None and text_file.exists()


def main():
    """메인 함수"""
    book_id = 219  # 김대식 빅퀘스천
    
    logger, log_file = setup_logging()
    
    logger.info("=" * 100)
    logger.info("Phase 4: 텍스트 생성 문제 해결")
    logger.info("=" * 100)
    logger.info(f"처리할 책 ID: {book_id}")
    logger.info(f"로그 파일: {log_file}")
    
    print("=" * 80)
    print("Phase 4: 텍스트 생성 문제 해결")
    print("=" * 80)
    print(f"처리할 책 ID: {book_id}")
    print()
    
    init_db()
    db = SessionLocal()
    
    try:
        # 텍스트 파일 생성
        success = generate_text_file(book_id, db, logger)
        
        if success:
            # 파일 존재 확인
            if verify_text_file(book_id, db):
                print("\n[검증] 텍스트 파일이 정상적으로 생성되었습니다.")
                logger.info("[검증] 텍스트 파일이 정상적으로 생성되었습니다.")
            else:
                print("\n[경고] 텍스트 파일 생성은 완료되었지만 파일을 찾을 수 없습니다.")
                logger.warning("[경고] 텍스트 파일 생성은 완료되었지만 파일을 찾을 수 없습니다.")
        else:
            print("\n[실패] 텍스트 파일 생성에 실패했습니다.")
            logger.error("[실패] 텍스트 파일 생성에 실패했습니다.")
        
        # 최종 상태 확인
        book = db.query(Book).filter(Book.id == book_id).first()
        if book:
            print(f"\n[최종 상태]")
            print(f"  ID: {book.id}")
            print(f"  제목: {book.title}")
            print(f"  Status: {book.status.value}")
            print(f"  page_count: {book.page_count}")
            logger.info(f"[최종 상태] ID: {book.id}, Status: {book.status.value}, page_count: {book.page_count}")
        
        print(f"\n로그 파일: {log_file}")
        logger.info(f"로그 파일: {log_file}")
        
    finally:
        db.close()


if __name__ == "__main__":
    main()

