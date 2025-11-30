"""Book 테이블에 category 컬럼 추가 마이그레이션 스크립트"""
import logging
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.api.database import engine, DATABASE_DIR
from sqlalchemy import inspect, text

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def add_category_column():
    """books 테이블에 category 컬럼 추가"""
    logger.info("=" * 80)
    logger.info("[INFO] Book 테이블에 category 컬럼 추가 시작")
    logger.info("=" * 80)
    
    # 1. 현재 상태 확인
    inspector = inspect(engine)
    if 'books' not in inspector.get_table_names():
        logger.error("[ERROR] books 테이블이 존재하지 않습니다.")
        return False
    
    columns = [c['name'] for c in inspector.get_columns('books')]
    logger.info(f"[INFO] 현재 books 테이블 컬럼: {columns}")
    
    if 'category' in columns:
        logger.info("[INFO] category 컬럼이 이미 존재합니다. 마이그레이션 불필요.")
        return True
    
    # 2. DB 백업 (선택적)
    db_file = DATABASE_DIR / "books.db"
    if db_file.exists():
        from datetime import datetime
        backup_file = DATABASE_DIR / f"books_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        import shutil
        shutil.copy2(db_file, backup_file)
        logger.info(f"[INFO] DB 백업 완료: {backup_file}")
    
    # 3. ALTER TABLE 실행
    try:
        with engine.connect() as conn:
            logger.info("[INFO] ALTER TABLE 실행 중...")
            conn.execute(text("ALTER TABLE books ADD COLUMN category VARCHAR"))
            conn.commit()
            logger.info("[INFO] category 컬럼 추가 완료")
        
        # 4. 확인
        inspector = inspect(engine)
        columns_after = [c['name'] for c in inspector.get_columns('books')]
        logger.info(f"[INFO] 추가 후 books 테이블 컬럼: {columns_after}")
        
        if 'category' in columns_after:
            logger.info("[INFO] 마이그레이션 성공")
            logger.info("=" * 80)
            return True
        else:
            logger.error("[ERROR] 마이그레이션 후에도 category 컬럼이 없습니다.")
            return False
            
    except Exception as e:
        logger.error(f"[ERROR] 마이그레이션 실패: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


if __name__ == "__main__":
    success = add_category_column()
    sys.exit(0 if success else 1)

