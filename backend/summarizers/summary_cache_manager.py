"""
OpenAI 요약 결과 캐싱 시스템 - 비용 절약을 위한 필수 구현
"""
import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Optional, Dict, Any

from backend.config.settings import settings

logger = logging.getLogger(__name__)


class SummaryCacheManager:
    """OpenAI 요약 결과 캐싱 매니저"""

    def __init__(self, cache_dir: Optional[Path] = None):
        """
        Args:
            cache_dir: 캐시 디렉토리 (None이면 settings.cache_dir / "summaries" 사용)
        """
        if cache_dir is None:
            cache_dir = settings.cache_dir / "summaries"
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"[INFO] SummaryCacheManager initialized with cache directory: {self.cache_dir}")

    def get_content_hash(self, content: str) -> str:
        """
        텍스트 내용의 MD5 해시 생성
        
        Args:
            content: 텍스트 내용
            
        Returns:
            MD5 해시 문자열
        """
        return hashlib.md5(content.encode('utf-8')).hexdigest()

    def get_cache_path(self, content_hash: str, summary_type: str) -> Path:
        """
        캐시 파일 경로 생성
        
        Args:
            content_hash: 콘텐츠 해시
            summary_type: 요약 타입 ("page" 또는 "chapter")
            
        Returns:
            캐시 파일 경로
        """
        return self.cache_dir / f"{summary_type}_{content_hash}.json"

    def get_cached_summary(
        self, content_hash: str, summary_type: str
    ) -> Optional[str]:
        """
        캐시된 요약 조회
        
        Args:
            content_hash: 콘텐츠 해시
            summary_type: 요약 타입 ("page" 또는 "chapter")
            
        Returns:
            캐시된 요약 텍스트 또는 None
        """
        try:
            cache_file = self.get_cache_path(content_hash, summary_type)
            if not cache_file.exists():
                return None
            
            with open(cache_file, 'r', encoding='utf-8') as f:
                cached_data = json.load(f)
            
            summary_text = cached_data.get("summary_text")
            if summary_text:
                logger.info(f"[INFO] Cache hit for {summary_type} summary (hash: {content_hash[:8]}...)")
                return summary_text
            
            return None
            
        except Exception as e:
            logger.warning(f"[WARNING] Failed to retrieve cache for {summary_type} summary: {e}")
            return None

    def save_cache(
        self, content_hash: str, summary_type: str, summary_text: str
    ) -> None:
        """
        요약 결과 캐시 저장
        
        Args:
            content_hash: 콘텐츠 해시
            summary_type: 요약 타입 ("page" 또는 "chapter")
            summary_text: 요약 텍스트
        """
        try:
            cache_file = self.get_cache_path(content_hash, summary_type)
            
            cache_data = {
                "summary_text": summary_text,
                "summary_type": summary_type,
                "content_hash": content_hash,
                "cached_at": time.time()
            }
            
            # 임시 파일로 안전하게 저장
            temp_file = cache_file.with_suffix('.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            
            # 원자적 이동
            temp_file.replace(cache_file)
            
            logger.info(f"[INFO] Cached {summary_type} summary (hash: {content_hash[:8]}...)")
            
        except Exception as e:
            logger.error(f"[ERROR] Failed to cache {summary_type} summary: {e}")

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        캐시 통계 정보
        
        Returns:
            캐시 통계 딕셔너리
        """
        try:
            cache_files = list(self.cache_dir.glob("*.json"))
            total_size = sum(f.stat().st_size for f in cache_files)
            
            page_count = len([f for f in cache_files if f.name.startswith("page_")])
            chapter_count = len([f for f in cache_files if f.name.startswith("chapter_")])
            
            return {
                "cache_directory": str(self.cache_dir),
                "total_files": len(cache_files),
                "page_summaries": page_count,
                "chapter_summaries": chapter_count,
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2)
            }
        except Exception as e:
            logger.error(f"[ERROR] Failed to get cache stats: {e}")
            return {"error": str(e)}

