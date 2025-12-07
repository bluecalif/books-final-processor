"""
캐시 디렉토리의 백업 파일들을 별도 폴더로 정리하는 스크립트

백업 파일(.backup)을 각 책별 디렉토리 내의 backup/ 폴더로 이동합니다.
"""
import logging
import shutil
from pathlib import Path
from backend.config.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def organize_backup_files(cache_dir: Path):
    """백업 파일들을 정리"""
    if not cache_dir.exists():
        logger.error(f"[ERROR] 캐시 디렉토리가 없습니다: {cache_dir}")
        return
    
    # 각 책별 디렉토리 확인
    book_dirs = [d for d in cache_dir.iterdir() if d.is_dir()]
    
    total_moved = 0
    total_skipped = 0
    
    for book_dir in book_dirs:
        # 백업 파일 찾기
        backup_files = list(book_dir.glob("*.backup"))
        
        if not backup_files:
            continue
        
        logger.info(f"[INFO] {book_dir.name}: 백업 파일 {len(backup_files)}개 발견")
        
        # backup 폴더 생성
        backup_folder = book_dir / "backup"
        backup_folder.mkdir(exist_ok=True)
        
        # 백업 파일 이동
        moved_count = 0
        for backup_file in backup_files:
            try:
                # backup 폴더로 이동
                dest_file = backup_folder / backup_file.name
                shutil.move(str(backup_file), str(dest_file))
                moved_count += 1
            except Exception as e:
                logger.warning(f"[WARNING] {backup_file.name} 이동 실패: {e}")
                total_skipped += 1
        
        total_moved += moved_count
        logger.info(f"[INFO] {book_dir.name}: {moved_count}개 파일 이동 완료")
    
    logger.info("=" * 80)
    logger.info(f"[INFO] 정리 완료: 총 {total_moved}개 파일 이동, {total_skipped}개 스킵")
    logger.info("=" * 80)


def main():
    """메인 함수"""
    logger.info("=" * 80)
    logger.info("[INFO] 캐시 백업 파일 정리 스크립트 시작")
    logger.info("=" * 80)
    
    cache_dir = settings.cache_dir / "summaries"
    organize_backup_files(cache_dir)


if __name__ == "__main__":
    main()

