"""
참고 파일: Upstage API 캐싱 시스템 - 비용 절약을 위한 필수 구현

출처: 기존 프로젝트 (사용자 제공)
참고 목적: 캐시 매니저 구현 참고

주요 차이점 예상:
1. 로깅 형식: 참고 파일은 일반 로깅, 현재 프로젝트는 `[INFO]`, `[ERROR]`, `[CACHE_SAVE]` 형식 사용
2. 캐시 디렉토리: 참고 파일은 `Path("cache/upstage")` 기본값, 현재 프로젝트는 `settings.cache_dir / "upstage"` 사용
3. 설정 관리: 참고 파일은 `settings` 직접 사용, 현재 프로젝트는 `Settings` 클래스 사용
4. 변수명/함수명: 현재 프로젝트 규칙에 맞게 Align 필요
5. 캐시 저장 검증: 참고 파일의 검증 로직을 현재 프로젝트에 맞게 개선 필요
"""
import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Optional, Dict, Any

from backend.config.settings import settings

logger = logging.getLogger(__name__)


class CacheManager:
    """Upstage API 결과 캐싱 매니저"""

    def __init__(self, cache_dir: Optional[str] = None):
        self.cache_dir = Path(cache_dir) if cache_dir else Path("cache/upstage")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"CacheManager initialized with cache directory: {self.cache_dir}")

    def get_file_hash(self, pdf_path: str) -> str:
        """PDF 파일의 안전한 해시 생성"""
        try:
            with open(pdf_path, 'rb') as f:
                # 대용량 파일을 위해 청크 단위로 읽기
                hasher = hashlib.md5()
                for chunk in iter(lambda: f.read(4096), b""):
                    hasher.update(chunk)
                return hasher.hexdigest()
        except Exception as e:
            logger.error(f"Failed to generate hash for {pdf_path}: {e}")
            raise

    def get_cache_key(self, pdf_path: str) -> str:
        """
        PDF 파일 내용 기반 캐시 키 생성
        
        파일 내용 해시만 사용하여 같은 PDF면 경로 무관하게 캐시 재사용
        (Phase 3: API 업로드 시 파일명/경로 변경되어도 캐시 유지)
        """
        try:
            file_hash = self.get_file_hash(pdf_path)
            
            logger.debug(f"Generated cache key: {file_hash} for {pdf_path}")
            return file_hash
            
        except Exception as e:
            logger.error(f"Failed to generate cache key for {pdf_path}: {e}")
            raise

    def get_cache_path(self, cache_key: str) -> Path:
        """캐시 파일 경로 생성"""
        return self.cache_dir / f"{cache_key}.json"

    def is_cache_valid(self, pdf_path: str, cache_key: str) -> bool:
        """
        캐시 유효성 확인
        
        캐시 키가 파일 내용 해시 기반이므로 파일 존재 여부만 확인
        (같은 내용이면 같은 키 → 캐시 재사용)
        """
        cache_file = self.get_cache_path(cache_key)
        return cache_file.exists()

    def get_cached_result(self, pdf_path: str) -> Optional[Dict[str, Any]]:
        """캐시된 결과 조회"""
        try:
            cache_key = self.get_cache_key(pdf_path)
            
            if not self.is_cache_valid(pdf_path, cache_key):
                return None
            
            cache_file = self.get_cache_path(cache_key)
            
            with open(cache_file, 'r', encoding='utf-8') as f:
                cached_data = json.load(f)
                
            # 캐시 메타데이터 제거
            cached_data.pop("_cache_meta", None)
            
            logger.info(f"Cache hit for {pdf_path}")
            return cached_data
            
        except Exception as e:
            logger.warning(f"Failed to retrieve cache for {pdf_path}: {e}")
            return None

    def save_cache(self, pdf_path: str, result: Dict[str, Any]) -> None:
        """결과를 캐시에 저장"""
        try:
            # Upstage API 응답 검증 (elements 또는 api 필드 존재 확인)
            if not (result.get("elements") is not None or result.get("api")):
                logger.warning(f"Not caching invalid result for {pdf_path}")
                return
            
            cache_key = self.get_cache_key(pdf_path)
            cache_file = self.get_cache_path(cache_key)
            
            # 캐시 메타데이터 추가
            stat = os.stat(pdf_path)
            cache_meta = {
                "file_hash": self.get_file_hash(pdf_path),
                "file_size": stat.st_size,
                "file_mtime": stat.st_mtime,
                "cached_at": time.time(),
                "pdf_path": pdf_path
            }
            
            # 결과 복사본에 메타데이터 추가
            result_to_cache = result.copy()
            result_to_cache["_cache_meta"] = cache_meta
            
            # 임시 파일로 안전하게 저장
            temp_file = cache_file.with_suffix('.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(result_to_cache, f, ensure_ascii=False, indent=2)
            
            # 원자적 이동
            temp_file.replace(cache_file)
            
            logger.info(f"Cached result for {pdf_path} (key: {cache_key})")
            
        except Exception as e:
            logger.error(f"Failed to cache result for {pdf_path}: {e}")

    def invalidate_cache(self, cache_key: str) -> None:
        """특정 캐시 무효화"""
        try:
            cache_file = self.get_cache_path(cache_key)
            if cache_file.exists():
                cache_file.unlink()
                logger.info(f"Invalidated cache: {cache_key}")
        except Exception as e:
            logger.warning(f"Failed to invalidate cache {cache_key}: {e}")

    def invalidate_cache_for_file(self, pdf_path: str) -> None:
        """특정 파일의 캐시 무효화"""
        try:
            cache_key = self.get_cache_key(pdf_path)
            self.invalidate_cache(cache_key)
        except Exception as e:
            logger.warning(f"Failed to invalidate cache for {pdf_path}: {e}")

    def cleanup_old_cache(self, max_age_days: int = 30) -> None:
        """오래된 캐시 파일 정리"""
        try:
            current_time = time.time()
            max_age_seconds = max_age_days * 24 * 60 * 60
            
            cleaned_count = 0
            for cache_file in self.cache_dir.glob("*.json"):
                try:
                    file_age = current_time - cache_file.stat().st_mtime
                    if file_age > max_age_seconds:
                        cache_file.unlink()
                        cleaned_count += 1
                except Exception:
                    continue
                    
            logger.info(f"Cleaned {cleaned_count} old cache files")
            
        except Exception as e:
            logger.error(f"Failed to cleanup old cache: {e}")

    def get_cache_stats(self) -> Dict[str, Any]:
        """캐시 통계 정보"""
        try:
            cache_files = list(self.cache_dir.glob("*.json"))
            total_size = sum(f.stat().st_size for f in cache_files)
            
            return {
                "cache_directory": str(self.cache_dir),
                "total_files": len(cache_files),
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2)
            }
        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {"error": str(e)}
