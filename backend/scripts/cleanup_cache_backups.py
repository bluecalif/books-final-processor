"""
캐시 폴더 정리: 백업 파일들을 backup 폴더로 이동

최종 버전 JSON만 남기고 .backup 파일들을 각 책별 backup/ 폴더로 이동합니다.
"""
import logging
from pathlib import Path
from typing import Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def cleanup_book_cache_backups(book_cache_dir: Path) -> Dict[str, Any]:
    """
    특정 도서의 캐시 디렉토리에서 백업 파일 정리
    
    Returns:
        처리 통계
    """
    if not book_cache_dir.exists():
        logger.warning(f"[WARNING] Cache directory not found: {book_cache_dir}")
        return {"success": False, "error": "Cache directory not found"}
    
    # backup 폴더 생성
    backup_dir = book_cache_dir / "backup"
    backup_dir.mkdir(exist_ok=True)
    
    # .backup 파일 찾기
    backup_files = list(book_cache_dir.glob("*.backup"))
    
    stats = {
        "total_backups": len(backup_files),
        "moved": 0,
        "failed": 0,
    }
    
    for backup_file in backup_files:
        try:
            # backup 폴더로 이동
            target_path = backup_dir / backup_file.name
            backup_file.rename(target_path)
            stats["moved"] += 1
            logger.debug(f"[DEBUG] Moved {backup_file.name} to backup/")
        except Exception as e:
            logger.error(f"[ERROR] Failed to move {backup_file.name}: {e}")
            stats["failed"] += 1
    
    # .tmp 파일도 정리 (있다면)
    tmp_files = list(book_cache_dir.glob("*.tmp"))
    for tmp_file in tmp_files:
        try:
            tmp_file.unlink()
            logger.debug(f"[DEBUG] Removed temporary file: {tmp_file.name}")
        except Exception as e:
            logger.warning(f"[WARNING] Failed to remove {tmp_file.name}: {e}")
    
    stats["success"] = True
    return stats


def main():
    """메인 함수"""
    from backend.config.settings import settings
    
    cache_base_dir = settings.cache_dir / "summaries"
    
    if not cache_base_dir.exists():
        logger.warning(f"[WARNING] Cache base directory not found: {cache_base_dir}")
        return
    
    # 각 책별 캐시 디렉토리 찾기
    book_dirs = [d for d in cache_base_dir.iterdir() if d.is_dir() and d.name != "backup"]
    
    logger.info(f"[INFO] Found {len(book_dirs)} book cache directories")
    
    total_stats = {
        "total_books": len(book_dirs),
        "books_processed": 0,
        "books_failed": 0,
        "total_backups_moved": 0,
    }
    
    for book_dir in book_dirs:
        logger.info(f"[INFO] Processing: {book_dir.name}")
        stats = cleanup_book_cache_backups(book_dir)
        
        if stats.get("success"):
            total_stats["books_processed"] += 1
            total_stats["total_backups_moved"] += stats.get("moved", 0)
        else:
            total_stats["books_failed"] += 1
    
    logger.info(f"\n{'='*80}")
    logger.info("캐시 백업 파일 정리 완료")
    logger.info(f"{'='*80}")
    logger.info(f"처리된 도서: {total_stats['books_processed']}/{total_stats['total_books']}")
    logger.info(f"실패한 도서: {total_stats['books_failed']}")
    logger.info(f"이동된 백업 파일: {total_stats['total_backups_moved']}")
    logger.info(f"{'='*80}\n")


if __name__ == "__main__":
    main()

