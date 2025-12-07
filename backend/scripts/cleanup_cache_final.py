"""
캐시 디렉토리 최종 정리

1. .tmp 파일 삭제
2. .backup 파일이 backup/ 폴더에 있는지 확인
3. 중복된 캐시 파일 확인 (같은 챕터에 대해 여러 파일)
"""
import logging
from pathlib import Path
from typing import Dict, Any, List
from collections import defaultdict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def cleanup_temp_files(cache_base_dir: Path) -> Dict[str, Any]:
    """임시 파일(.tmp) 삭제"""
    stats = {
        "tmp_files_found": 0,
        "tmp_files_deleted": 0,
        "errors": 0,
    }
    
    tmp_files = list(cache_base_dir.rglob("*.tmp"))
    stats["tmp_files_found"] = len(tmp_files)
    
    for tmp_file in tmp_files:
        try:
            tmp_file.unlink()
            stats["tmp_files_deleted"] += 1
            logger.debug(f"[DEBUG] Deleted temp file: {tmp_file}")
        except Exception as e:
            logger.error(f"[ERROR] Failed to delete {tmp_file}: {e}")
            stats["errors"] += 1
    
    return stats


def organize_backup_files(cache_base_dir: Path) -> Dict[str, Any]:
    """백업 파일을 backup/ 폴더로 이동"""
    stats = {
        "backup_files_found": 0,
        "backup_files_moved": 0,
        "errors": 0,
    }
    
    # 각 책별 디렉토리에서 백업 파일 찾기
    book_dirs = [d for d in cache_base_dir.iterdir() if d.is_dir() and d.name != "backup"]
    
    for book_dir in book_dirs:
        backup_files = list(book_dir.glob("*.backup"))
        stats["backup_files_found"] += len(backup_files)
        
        if backup_files:
            # backup 폴더 생성
            backup_dir = book_dir / "backup"
            backup_dir.mkdir(exist_ok=True)
            
            for backup_file in backup_files:
                try:
                    # backup 폴더로 이동
                    target_path = backup_dir / backup_file.name
                    if not target_path.exists():
                        backup_file.rename(target_path)
                        stats["backup_files_moved"] += 1
                        logger.debug(f"[DEBUG] Moved backup file: {backup_file.name}")
                    else:
                        # 이미 있으면 삭제
                        backup_file.unlink()
                        stats["backup_files_moved"] += 1
                        logger.debug(f"[DEBUG] Deleted duplicate backup: {backup_file.name}")
                except Exception as e:
                    logger.error(f"[ERROR] Failed to move {backup_file.name}: {e}")
                    stats["errors"] += 1
    
    return stats


def find_duplicate_cache_files(cache_base_dir: Path) -> Dict[str, Any]:
    """중복된 캐시 파일 확인 (같은 챕터에 대해 여러 파일)"""
    stats = {
        "duplicate_groups": 0,
        "total_duplicates": 0,
        "details": [],
    }
    
    book_dirs = [d for d in cache_base_dir.iterdir() if d.is_dir() and d.name != "backup"]
    
    for book_dir in book_dirs:
        chapter_files = list(book_dir.glob("chapter_*.json"))
        
        # chapter_number와 chapter_title로 그룹화
        chapter_groups = defaultdict(list)
        
        for chapter_file in chapter_files:
            try:
                import json
                with open(chapter_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                chapter_num = data.get("chapter_number")
                chapter_title = data.get("chapter_title")
                
                if chapter_num and chapter_title:
                    key = f"{chapter_num}_{chapter_title}"
                    chapter_groups[key].append(chapter_file)
            except Exception as e:
                logger.warning(f"[WARNING] Failed to read {chapter_file.name}: {e}")
        
        # 중복 그룹 찾기
        for key, files in chapter_groups.items():
            if len(files) > 1:
                stats["duplicate_groups"] += 1
                stats["total_duplicates"] += len(files) - 1  # 하나는 유지
                stats["details"].append({
                    "book": book_dir.name,
                    "chapter": key,
                    "files": [f.name for f in files],
                    "count": len(files),
                })
                logger.info(
                    f"[INFO] Duplicate found in {book_dir.name}: "
                    f"chapter={key}, files={len(files)}"
                )
    
    return stats


def main():
    """메인 함수"""
    from backend.config.settings import settings
    
    cache_base_dir = settings.cache_dir / "summaries"
    
    if not cache_base_dir.exists():
        logger.warning(f"[WARNING] Cache base directory not found: {cache_base_dir}")
        return
    
    logger.info(f"[INFO] Starting cache cleanup...")
    logger.info(f"[INFO] Cache directory: {cache_base_dir}")
    
    # 1. 임시 파일 삭제
    logger.info("\n[1] Cleaning up temporary files...")
    tmp_stats = cleanup_temp_files(cache_base_dir)
    logger.info(f"[INFO] Temp files: found={tmp_stats['tmp_files_found']}, deleted={tmp_stats['tmp_files_deleted']}")
    
    # 2. 백업 파일 정리
    logger.info("\n[2] Organizing backup files...")
    backup_stats = organize_backup_files(cache_base_dir)
    logger.info(
        f"[INFO] Backup files: found={backup_stats['backup_files_found']}, "
        f"moved={backup_stats['backup_files_moved']}"
    )
    
    # 3. 중복 파일 확인
    logger.info("\n[3] Checking for duplicate cache files...")
    duplicate_stats = find_duplicate_cache_files(cache_base_dir)
    logger.info(
        f"[INFO] Duplicates: groups={duplicate_stats['duplicate_groups']}, "
        f"total_duplicates={duplicate_stats['total_duplicates']}"
    )
    
    if duplicate_stats["details"]:
        logger.info("\n[INFO] Duplicate details:")
        for detail in duplicate_stats["details"]:
            logger.info(f"  {detail['book']}: {detail['chapter']} ({detail['count']} files)")
            for fname in detail["files"]:
                logger.info(f"    - {fname}")
    
    logger.info(f"\n{'='*80}")
    logger.info("캐시 정리 완료")
    logger.info(f"{'='*80}")
    logger.info(f"임시 파일 삭제: {tmp_stats['tmp_files_deleted']}")
    logger.info(f"백업 파일 정리: {backup_stats['backup_files_moved']}")
    logger.info(f"중복 파일 그룹: {duplicate_stats['duplicate_groups']}")
    logger.info(f"{'='*80}\n")


if __name__ == "__main__":
    main()

