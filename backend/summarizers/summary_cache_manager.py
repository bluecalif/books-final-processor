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

    def __init__(self, cache_dir: Optional[Path] = None, book_title: Optional[str] = None):
        """
        Args:
            cache_dir: 캐시 디렉토리 (None이면 settings.cache_dir / "summaries" 사용)
            book_title: 책 제목 (폴더 분리용, None이면 루트에 저장)
        """
        if cache_dir is None:
            cache_dir = settings.cache_dir / "summaries"
        
        # 책 제목이 제공된 경우 책별 폴더 생성
        if book_title:
            # 파일명으로 사용 불가능한 문자 제거
            safe_title = "".join(c for c in book_title if c.isalnum() or c in (' ', '-', '_')).strip()
            safe_title = safe_title.replace(' ', '_')[:100]  # 길이 제한
            cache_dir = Path(cache_dir) / safe_title
        
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
    ) -> Optional[Dict[str, Any]]:
        """
        캐시된 요약 조회 (새로운 시각화 구조)
        
        Args:
            content_hash: 콘텐츠 해시
            summary_type: 요약 타입 ("page" 또는 "chapter")
            
        Returns:
            캐시된 구조화된 딕셔너리 또는 None (summary_text 필드 없이 각 필드가 루트 레벨에 있음)
        """
        try:
            cache_file = self.get_cache_path(content_hash, summary_type)
            if not cache_file.exists():
                return None
            
            with open(cache_file, 'r', encoding='utf-8') as f:
                cached_data = json.load(f)
            
            # 새로운 시각화 구조: summary_text 필드가 없고 각 필드가 루트 레벨에 있음
            if "summary_text" in cached_data:
                # 기존 형식 (변환 전) - 변환 스크립트로 변환 필요
                logger.warning(
                    f"[WARNING] Old cache format detected for {summary_type} summary "
                    f"(hash: {content_hash[:8]}...). Please run migration script."
                )
                return None
            
            # 메타데이터 필드 제외하고 반환
            result = {
                k: v for k, v in cached_data.items()
                if k not in ("summary_type", "content_hash", "cached_at")
            }
            
            if result:
                logger.info(f"[INFO] Cache hit for {summary_type} summary (hash: {content_hash[:8]}...)")
                return result
            
            return None
            
        except Exception as e:
            logger.warning(f"[WARNING] Failed to retrieve cache for {summary_type} summary: {e}")
            return None

    def save_cache(
        self, content_hash: str, summary_type: str, structured_data: Dict[str, Any]
    ) -> None:
        """
        요약 결과 캐시 저장 (새로운 시각화 구조)
        
        Args:
            content_hash: 콘텐츠 해시
            summary_type: 요약 타입 ("page" 또는 "chapter")
            structured_data: 구조화된 딕셔너리 (각 필드가 루트 레벨에 있음)
        """
        try:
            cache_file = self.get_cache_path(content_hash, summary_type)
            
            # 구조화된 데이터에 메타데이터 추가
            cache_data = {
                **structured_data,  # 각 필드를 루트 레벨로 전개
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

