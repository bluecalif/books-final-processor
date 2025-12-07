"""
중복된 캐시 파일 정리

같은 챕터에 대해 여러 캐시 파일이 있는 경우, 가장 최신 파일을 유지하고 나머지는 backup으로 이동
"""
import json
import logging
from pathlib import Path
from typing import Dict, Any, List
from collections import defaultdict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def remove_duplicates(cache_base_dir: Path) -> Dict[str, Any]:
    """중복된 캐시 파일 정리"""
    stats = {
        "duplicate_groups": 0,
        "files_moved_to_backup": 0,
        "errors": 0,
    }
    
    book_dirs = [d for d in cache_base_dir.iterdir() if d.is_dir() and d.name != "backup"]
    
    for book_dir in book_dirs:
        chapter_files = list(book_dir.glob("chapter_*.json"))
        
        # chapter_number와 chapter_title로 그룹화
        chapter_groups = defaultdict(list)
        
        for chapter_file in chapter_files:
            try:
                with open(chapter_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                chapter_num = data.get("chapter_number")
                chapter_title = data.get("chapter_title")
                
                if chapter_num and chapter_title:
                    key = f"{chapter_num}_{chapter_title}"
                    # 파일 정보 저장 (파일 경로, 수정 시간, cached_at)
                    cached_at = data.get("cached_at", 0)
                    mtime = chapter_file.stat().st_mtime
                    chapter_groups[key].append({
                        "file": chapter_file,
                        "cached_at": cached_at,
                        "mtime": mtime,
                        "data": data,
                    })
            except Exception as e:
                logger.warning(f"[WARNING] Failed to read {chapter_file.name}: {e}")
        
        # 중복 그룹 처리
        for key, files in chapter_groups.items():
            if len(files) > 1:
                stats["duplicate_groups"] += 1
                
                # 가장 최신 파일 찾기 (cached_at 우선, 없으면 mtime)
                files.sort(key=lambda x: (x["cached_at"] or 0, x["mtime"]), reverse=True)
                keep_file = files[0]["file"]
                duplicate_files = files[1:]
                
                logger.info(
                    f"[INFO] {book_dir.name}: chapter={key}, "
                    f"keeping={keep_file.name}, duplicates={len(duplicate_files)}"
                )
                
                # backup 폴더 생성
                backup_dir = book_dir / "backup"
                backup_dir.mkdir(exist_ok=True)
                
                # 중복 파일들을 backup으로 이동
                for dup_info in duplicate_files:
                    dup_file = dup_info["file"]
                    try:
                        backup_path = backup_dir / f"{dup_file.stem}_duplicate{dup_file.suffix}"
                        dup_file.rename(backup_path)
                        stats["files_moved_to_backup"] += 1
                        logger.debug(f"[DEBUG] Moved duplicate: {dup_file.name} -> backup/")
                    except Exception as e:
                        logger.error(f"[ERROR] Failed to move {dup_file.name}: {e}")
                        stats["errors"] += 1
    
    return stats


def main():
    """메인 함수"""
    from backend.config.settings import settings
    
    cache_base_dir = settings.cache_dir / "summaries"
    
    if not cache_base_dir.exists():
        logger.warning(f"[WARNING] Cache base directory not found: {cache_base_dir}")
        return
    
    logger.info(f"[INFO] Starting duplicate cache cleanup...")
    logger.info(f"[INFO] Cache directory: {cache_base_dir}")
    
    stats = remove_duplicates(cache_base_dir)
    
    logger.info(f"\n{'='*80}")
    logger.info("중복 캐시 파일 정리 완료")
    logger.info(f"{'='*80}")
    logger.info(f"중복 그룹: {stats['duplicate_groups']}")
    logger.info(f"백업으로 이동: {stats['files_moved_to_backup']}")
    logger.info(f"오류: {stats['errors']}")
    logger.info(f"{'='*80}\n")


if __name__ == "__main__":
    main()

