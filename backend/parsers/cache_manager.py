"""
Upstage API 캐싱 시스템 - 비용 절약을 위한 필수 구현
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

    def __init__(self, cache_dir: Optional[Path] = None):
        """
        Args:
            cache_dir: 캐시 디렉토리 (None이면 settings.cache_dir / "upstage" 사용)
        """
        if cache_dir is None:
            cache_dir = settings.cache_dir / "upstage"
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"[INFO] CacheManager initialized with cache directory: {self.cache_dir}")

    def get_file_hash(self, pdf_path: str) -> str:
        """
        PDF 파일의 안전한 해시 생성
        
        Args:
            pdf_path: PDF 파일 경로
            
        Returns:
            MD5 해시 문자열
        """
        try:
            with open(pdf_path, 'rb') as f:
                # 대용량 파일을 위해 청크 단위로 읽기
                hasher = hashlib.md5()
                for chunk in iter(lambda: f.read(4096), b""):
                    hasher.update(chunk)
                return hasher.hexdigest()
        except Exception as e:
            logger.error(f"[ERROR] Failed to generate hash for {pdf_path}: {e}")
            raise

    def get_cache_key(self, pdf_path: str) -> str:
        """
        PDF 파일 내용 기반 캐시 키 생성
        
        파일 내용 해시만 사용하여 같은 PDF면 경로 무관하게 캐시 재사용
        (업로드 시 파일명/경로 변경되어도 캐시 유지)
        
        Args:
            pdf_path: PDF 파일 경로
            
        Returns:
            캐시 키 (MD5 해시)
        """
        try:
            file_hash = self.get_file_hash(pdf_path)
            logger.debug(f"[DEBUG] Generated cache key: {file_hash} for {pdf_path}")
            return file_hash
        except Exception as e:
            logger.error(f"[ERROR] Failed to generate cache key for {pdf_path}: {e}")
            raise

    def get_cache_path(self, cache_key: str) -> Path:
        """
        캐시 파일 경로 생성
        
        Args:
            cache_key: 캐시 키
            
        Returns:
            캐시 파일 경로
        """
        return self.cache_dir / f"{cache_key}.json"

    def is_cache_valid(self, pdf_path: str, cache_key: str) -> bool:
        """
        캐시 유효성 확인
        
        캐시 키가 파일 내용 해시 기반이므로 파일 존재 여부만 확인
        (같은 내용이면 같은 키 → 캐시 재사용)
        
        Args:
            pdf_path: PDF 파일 경로
            cache_key: 캐시 키
            
        Returns:
            캐시 유효 여부
        """
        cache_file = self.get_cache_path(cache_key)
        return cache_file.exists()

    def get_cached_result(self, pdf_path: str) -> Optional[Dict[str, Any]]:
        """
        캐시된 결과 조회
        
        Args:
            pdf_path: PDF 파일 경로
            
        Returns:
            캐시된 결과 또는 None
        """
        try:
            cache_key = self.get_cache_key(pdf_path)
            
            if not self.is_cache_valid(pdf_path, cache_key):
                return None
            
            cache_file = self.get_cache_path(cache_key)
            
            with open(cache_file, 'r', encoding='utf-8') as f:
                cached_data = json.load(f)
            
            # 캐시 메타데이터 제거
            cached_data.pop("_cache_meta", None)
            
            logger.info(f"[INFO] Cache hit for {pdf_path}")
            return cached_data
            
        except Exception as e:
            logger.warning(f"[WARNING] Failed to retrieve cache for {pdf_path}: {e}")
            return None

    def save_cache(self, pdf_path: str, result: Dict[str, Any]) -> None:
        """
        결과를 캐시에 저장
        
        Args:
            pdf_path: PDF 파일 경로
            result: 캐시할 결과 (Upstage API 원본 응답)
        """
        import traceback
        
        logger.info(f"[CACHE_SAVE] 시작: pdf_path={pdf_path}")
        logger.info(f"[CACHE_SAVE] result 타입: {type(result)}")
        logger.info(f"[CACHE_SAVE] result 키: {list(result.keys()) if isinstance(result, dict) else 'N/A'}")
        
        try:
            # 검증 로직 상세 로깅
            has_elements = result.get("elements") is not None
            has_api = bool(result.get("api"))
            elements_type = type(result.get("elements")).__name__ if result.get("elements") is not None else "None"
            elements_len = len(result.get("elements", [])) if isinstance(result.get("elements"), list) else 0
            api_value = result.get("api")
            
            logger.info(f"[CACHE_SAVE] 검증: has_elements={has_elements} (type={elements_type}, len={elements_len})")
            logger.info(f"[CACHE_SAVE] 검증: has_api={has_api} (value={api_value})")
            
            # Upstage API 응답 검증 (elements 또는 api 필드 존재 확인)
            if not (has_elements or has_api):
                logger.warning(f"[CACHE_SAVE] 검증 실패: 저장하지 않음")
                logger.warning(f"[CACHE_SAVE] result 샘플 (처음 1000자): {json.dumps(result, ensure_ascii=False, indent=2)[:1000]}")
                return
            
            logger.info(f"[CACHE_SAVE] 검증 통과: 저장 진행")
            
            cache_key = self.get_cache_key(pdf_path)
            cache_file = self.get_cache_path(cache_key)
            
            logger.info(f"[CACHE_SAVE] cache_key={cache_key}")
            logger.info(f"[CACHE_SAVE] cache_file={cache_file}")
            
            # 파일 경로 확인
            pdf_path_obj = Path(pdf_path)
            pdf_exists = pdf_path_obj.exists()
            pdf_absolute = str(pdf_path_obj.resolve()) if pdf_exists else "N/A"
            
            logger.info(f"[CACHE_SAVE] pdf_path 존재: {pdf_exists}")
            logger.info(f"[CACHE_SAVE] pdf_path 절대경로: {pdf_absolute}")
            
            # 캐시 메타데이터 추가
            stat = os.stat(pdf_path)
            file_hash = self.get_file_hash(pdf_path)
            cache_meta = {
                "file_hash": file_hash,
                "file_size": stat.st_size,
                "file_mtime": stat.st_mtime,
                "cached_at": time.time(),
                "pdf_path": str(pdf_path)
            }
            
            logger.info(f"[CACHE_SAVE] 메타데이터 생성 완료: file_hash={file_hash[:8]}..., file_size={stat.st_size}, file_mtime={stat.st_mtime}")
            
            # 결과 복사본에 메타데이터 추가
            result_to_cache = result.copy()
            result_to_cache["_cache_meta"] = cache_meta
            
            # 임시 파일로 안전하게 저장
            temp_file = cache_file.with_suffix('.tmp')
            logger.info(f"[CACHE_SAVE] 임시 파일 저장 시작: {temp_file}")
            
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(result_to_cache, f, ensure_ascii=False, indent=2)
            
            temp_file_size = temp_file.stat().st_size
            logger.info(f"[CACHE_SAVE] 임시 파일 저장 완료: {temp_file_size} bytes")
            
            # 원자적 이동
            temp_file.replace(cache_file)
            logger.info(f"[CACHE_SAVE] 원자적 이동 완료: {cache_file}")
            
            final_exists = cache_file.exists()
            final_size = cache_file.stat().st_size if final_exists else 0
            logger.info(f"[CACHE_SAVE] 최종 파일 존재: {final_exists}")
            logger.info(f"[CACHE_SAVE] 최종 파일 크기: {final_size} bytes")
            logger.info(f"[CACHE_SAVE] 저장 완료: {pdf_path} (key: {cache_key})")
            
        except Exception as e:
            logger.error(f"[ERROR] Failed to cache result for {pdf_path}: {e}")
            logger.error(f"[ERROR] Exception type: {type(e).__name__}")
            logger.error(f"[ERROR] Traceback:\n{traceback.format_exc()}")
            # 예외를 다시 발생시키지 않음 - 캐시 저장 실패가 전체 파싱을 막지 않도록
            # 캐시는 비용 절약을 위한 것이므로 실패해도 파싱은 계속 진행
            logger.warning(f"[WARNING] Cache save failed, but parsing will continue")

    def invalidate_cache(self, cache_key: str) -> None:
        """
        특정 캐시 무효화
        
        Args:
            cache_key: 캐시 키
        """
        try:
            cache_file = self.get_cache_path(cache_key)
            if cache_file.exists():
                cache_file.unlink()
                logger.info(f"[INFO] Invalidated cache: {cache_key}")
        except Exception as e:
            logger.warning(f"[WARNING] Failed to invalidate cache {cache_key}: {e}")

    def invalidate_cache_for_file(self, pdf_path: str) -> None:
        """
        특정 파일의 캐시 무효화
        
        Args:
            pdf_path: PDF 파일 경로
        """
        try:
            cache_key = self.get_cache_key(pdf_path)
            self.invalidate_cache(cache_key)
        except Exception as e:
            logger.warning(f"[WARNING] Failed to invalidate cache for {pdf_path}: {e}")

    def cleanup_old_cache(self, max_age_days: int = 30) -> None:
        """
        오래된 캐시 파일 정리
        
        Args:
            max_age_days: 최대 보관 기간 (일)
        """
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
            
            logger.info(f"[INFO] Cleaned {cleaned_count} old cache files")
            
        except Exception as e:
            logger.error(f"[ERROR] Failed to cleanup old cache: {e}")

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        캐시 통계 정보
        
        Returns:
            캐시 통계 딕셔너리
        """
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
            logger.error(f"[ERROR] Failed to get cache stats: {e}")
            return {"error": str(e)}

