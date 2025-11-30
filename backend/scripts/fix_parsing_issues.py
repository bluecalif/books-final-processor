"""
Phase 2: 파싱 문제 해결 스크립트

파싱 불완전한 모든 책을 파싱 완료 상태로 만듭니다.
"""
import sys
import json
import logging
import time
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy.orm import Session

from backend.api.database import SessionLocal, init_db
from backend.api.models.book import Book, BookStatus
from backend.api.services.parsing_service import ParsingService
from backend.scripts.diagnose_processing_issues import verify_parsing_completeness

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def fix_parsing_issues():
    """파싱 문제 해결"""
    db = SessionLocal()
    
    try:
        # 진단 리포트 읽기
        diagnosis_file = project_root / "data" / "logs" / "batch_processing" / "diagnosis_report.json"
        if not diagnosis_file.exists():
            logger.error("[ERROR] 진단 리포트 파일이 없습니다. 먼저 진단 스크립트를 실행하세요.")
            return
        
        with open(diagnosis_file, 'r', encoding='utf-8') as f:
            report = json.load(f)
        
        parsing_issues = report.get("parsing_issues", [])
        
        print("=" * 80)
        print("Phase 2: 파싱 문제 해결")
        print("=" * 80)
        
        print(f"\n[처리 대상]")
        print(f"  파싱 문제 책: {len(parsing_issues)}권")
        
        parsing_service = ParsingService(db)
        
        success_count = 0
        failed_count = 0
        skipped_count = 0
        
        for idx, issue in enumerate(parsing_issues, start=1):
            book_id = issue["id"]
            book_title = issue["title"]
            issue_type = issue["issue_type"]
            
            print(f"\n[{idx}/{len(parsing_issues)}] ID {book_id}: {book_title}")
            print(f"  문제 유형: {issue_type}")
            
            # DB에서 최신 상태 확인
            book = db.query(Book).filter(Book.id == book_id).first()
            if not book:
                print(f"  [SKIP] Book 레코드 없음")
                skipped_count += 1
                continue
            
            # 이미 PARSED 상태인지 확인
            if book.status == BookStatus.PARSED:
                # 파싱 완전성 검증
                completeness = verify_parsing_completeness(book, db)
                if completeness["is_complete"]:
                    print(f"  [SKIP] 이미 파싱 완료 및 완전성 검증 통과")
                    skipped_count += 1
                    continue
                else:
                    print(f"  [WARNING] PARSED 상태이지만 완전성 검증 실패")
                    print(f"    문제: {', '.join(completeness['issues'])}")
                    # 재파싱 필요
                    # 상태를 UPLOADED로 변경하여 재파싱 가능하게 함
                    book.status = BookStatus.UPLOADED
                    db.commit()
            
            # 파일 경로 확인
            if not book.source_file_path:
                print(f"  [FAILED] source_file_path 없음")
                failed_count += 1
                continue
            
            pdf_path = Path(book.source_file_path)
            if not pdf_path.exists():
                print(f"  [FAILED] PDF 파일 없음: {book.source_file_path}")
                failed_count += 1
                continue
            
            # 캐시 파일 확인 및 삭제 (API 오류로 인한 불완전한 캐시 제거)
            from backend.parsers.cache_manager import CacheManager
            cache_manager = CacheManager()
            cache_key = cache_manager.get_file_hash(str(pdf_path))
            cache_file = cache_manager.get_cache_path(cache_key)
            
            if cache_file.exists():
                # 캐시 파일의 elements 확인
                try:
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        cache_data = json.load(f)
                    elements_count = len(cache_data.get("elements", []))
                    
                    if elements_count == 0:
                        print(f"  [CACHE] 불완전한 캐시 파일 삭제 (elements: 0개)")
                        cache_file.unlink()
                    else:
                        print(f"  [CACHE] 캐시 파일 유지 (elements: {elements_count}개)")
                except Exception as e:
                    print(f"  [CACHE] 캐시 파일 확인 실패, 삭제: {e}")
                    if cache_file.exists():
                        cache_file.unlink()
            
            # 파싱 실행 (캐시 무시하고 강제 재파싱)
            try:
                print(f"  [PARSING] 파싱 시작 (캐시 무시)...")
                parse_start = time.time()
                
                # ParsingService의 parse_book은 use_cache=True를 사용하므로
                # 직접 PDFParser를 사용하여 use_cache=False로 재파싱
                from backend.parsers.pdf_parser import PDFParser
                from backend.config.settings import settings
                
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
                
                # 파싱 완전성 검증
                completeness = verify_parsing_completeness(book, db)
                
                if completeness["is_complete"]:
                    print(f"  [SUCCESS] 파싱 완료 (소요시간: {parse_time:.1f}초)")
                    print(f"    page_count: {book.page_count}")
                    print(f"    캐시 페이지 수: {completeness['cache_pages']}")
                    print(f"    DB 페이지 수: {completeness['db_pages']}")
                    success_count += 1
                else:
                    print(f"  [WARNING] 파싱 완료했지만 완전성 검증 실패")
                    print(f"    문제: {', '.join(completeness['issues'])}")
                    failed_count += 1
                    
            except ValueError as e:
                # 상태 문제 등
                print(f"  [FAILED] {e}")
                failed_count += 1
            except Exception as e:
                print(f"  [FAILED] 예외 발생: {e}")
                logger.error(f"[ERROR] 파싱 실패: ID {book_id}, {e}", exc_info=True)
                failed_count += 1
        
        print("\n" + "=" * 80)
        print("[결과]")
        print(f"  성공: {success_count}권")
        print(f"  실패: {failed_count}권")
        print(f"  스킵: {skipped_count}권")
        print("=" * 80)
        
        # 최종 검증
        print("\n[최종 검증]")
        all_books = db.query(Book).filter(
            Book.id.in_([issue["id"] for issue in parsing_issues])
        ).all()
        
        parsed_count = 0
        incomplete_count = 0
        
        for book in all_books:
            if book.status == BookStatus.PARSED:
                completeness = verify_parsing_completeness(book, db)
                if completeness["is_complete"]:
                    parsed_count += 1
                else:
                    incomplete_count += 1
                    print(f"  [INCOMPLETE] ID {book.id}: {book.title}")
                    print(f"    문제: {', '.join(completeness['issues'])}")
        
        print(f"\n  PARSED 상태 및 완전성 검증 통과: {parsed_count}권")
        print(f"  PARSED 상태이지만 완전성 검증 실패: {incomplete_count}권")
        
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
    fix_parsing_issues()

