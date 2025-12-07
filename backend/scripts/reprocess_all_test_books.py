"""
테스트 도서 4권의 챕터 서머리 일괄 재처리 스크립트

1. 챕터 서머리 캐시 삭제
2. 개선된 프롬프트로 재생성
3. 2페이지 이하 챕터는 자동 스킵
"""
import logging
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.scripts.delete_chapter_caches import delete_chapter_caches
from backend.scripts.reprocess_chapter_summaries import reprocess_chapter_summaries

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 테스트 도서 4권 ID
TEST_BOOK_IDS = [176, 177, 184, 175]


def reprocess_all_test_books() -> None:
    """
    테스트 도서 4권의 챕터 서머리 재처리
    """
    logger.info(f"[INFO] Starting reprocessing for {len(TEST_BOOK_IDS)} test books")
    logger.info(f"[INFO] Book IDs: {TEST_BOOK_IDS}")
    
    # 1. 챕터 서머리 캐시 삭제
    logger.info("[INFO] Step 1: Deleting chapter summary caches...")
    for book_id in TEST_BOOK_IDS:
        try:
            delete_chapter_caches(book_id=book_id)
        except Exception as e:
            logger.error(f"[ERROR] Failed to delete caches for book {book_id}: {e}")
            continue
    
    logger.info("[INFO] Step 1 completed: Chapter caches deleted")
    
    # 2. 챕터 서머리 재생성
    logger.info("[INFO] Step 2: Reprocessing chapter summaries with improved prompts...")
    for book_id in TEST_BOOK_IDS:
        try:
            logger.info(f"[INFO] Processing book {book_id}...")
            reprocess_chapter_summaries(book_id)
            logger.info(f"[INFO] Book {book_id} completed")
        except Exception as e:
            logger.error(f"[ERROR] Failed to reprocess book {book_id}: {e}")
            continue
    
    logger.info("[INFO] Step 2 completed: Chapter summaries reprocessed")
    logger.info("[INFO] All test books reprocessing completed")


if __name__ == "__main__":
    reprocess_all_test_books()

