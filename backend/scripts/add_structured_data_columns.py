"""
DB 마이그레이션: page_summaries, chapter_summaries 테이블에 structured_data 컬럼 추가

사용법:
    poetry run python -m backend.scripts.add_structured_data_columns
"""
import sys
import logging
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from backend.api.database import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def add_structured_data_columns():
    """page_summaries, chapter_summaries 테이블에 structured_data 컬럼 추가"""
    logger.info("[INFO] Starting migration: adding structured_data columns...")
    
    try:
        with engine.connect() as conn:
            # 트랜잭션 시작
            trans = conn.begin()
            
            try:
                # 1. page_summaries 테이블에 structured_data 컬럼 추가
                logger.info("[INFO] Adding structured_data column to page_summaries table...")
                conn.execute(text("""
                    ALTER TABLE page_summaries 
                    ADD COLUMN structured_data TEXT
                """))
                logger.info("[INFO] Successfully added structured_data to page_summaries")
                
                # 2. chapter_summaries 테이블에 structured_data 컬럼 추가
                logger.info("[INFO] Adding structured_data column to chapter_summaries table...")
                conn.execute(text("""
                    ALTER TABLE chapter_summaries 
                    ADD COLUMN structured_data TEXT
                """))
                logger.info("[INFO] Successfully added structured_data to chapter_summaries")
                
                # 커밋
                trans.commit()
                logger.info("[INFO] Migration completed successfully")
                
            except Exception as e:
                trans.rollback()
                logger.error(f"[ERROR] Migration failed: {e}")
                raise
                
    except Exception as e:
        logger.error(f"[ERROR] Database connection error: {e}")
        raise


if __name__ == "__main__":
    add_structured_data_columns()

