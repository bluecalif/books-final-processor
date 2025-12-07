"""
책 전체 보고서 생성 스크립트 (Phase 6.3)

사용법:
    poetry run python -m backend.scripts.generate_book_report <book_id>
"""
import sys
import logging
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.api.database import SessionLocal
from backend.api.services.book_report_service import BookReportService

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """메인 함수"""
    if len(sys.argv) < 2:
        print("Usage: poetry run python -m backend.scripts.generate_book_report <book_id>")
        sys.exit(1)
    
    try:
        book_id = int(sys.argv[1])
    except ValueError:
        print(f"Error: Invalid book_id: {sys.argv[1]}")
        sys.exit(1)
    
    db = SessionLocal()
    try:
        service = BookReportService(db)
        report = service.generate_report(book_id)
        
        print(f"\n[SUCCESS] Book report generated for book_id={book_id}")
        print(f"Report saved to: data/output/book_summaries/")
        print(f"\nMetadata:")
        print(f"  - Title: {report['metadata']['title']}")
        print(f"  - Author: {report['metadata']['author']}")
        print(f"  - Category: {report['metadata']['category']}")
        print(f"  - Chapters: {report['metadata']['chapter_count']}")
        print(f"\nBook Summary:")
        print(f"  - Core Message: {report['book_summary']['core_message']}")
        print(f"\nEntity Synthesis:")
        print(f"  - Insights: {len(report['entity_synthesis']['insights'])} items")
        print(f"  - Key Events: {len(report['entity_synthesis']['key_events'])} items")
        print(f"  - Key Examples: {len(report['entity_synthesis']['key_examples'])} items")
        print(f"  - Key Persons: {len(report['entity_synthesis']['key_persons'])} items")
        print(f"  - Key Concepts: {len(report['entity_synthesis']['key_concepts'])} items")
        
    except Exception as e:
        logger.error(f"[ERROR] Failed to generate book report: {e}", exc_info=True)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()

