"""
페이지 엔티티 추출기

도메인별 스키마를 사용하여 페이지 텍스트에서 구조화된 엔티티를 추출합니다.
캐시를 통합하여 비용을 절감합니다.
"""
import json
import logging
from typing import Dict, Any, Optional
from backend.summarizers.llm_chains import PageExtractionChain
from backend.summarizers.summary_cache_manager import SummaryCacheManager
from backend.summarizers.schemas import get_domain_from_category, BasePageSchema

logger = logging.getLogger(__name__)


class PageExtractor:
    """페이지 엔티티 추출기"""

    def __init__(self, domain: str, enable_cache: bool = True, book_title: str = None):
        """
        Args:
            domain: 도메인 코드 ("history", "economy", "humanities", "science")
            enable_cache: 캐시 사용 여부
            book_title: 책 제목 (캐시 폴더 분리용)
        """
        self.domain = domain
        self.chain = PageExtractionChain(domain)
        self.cache_manager = SummaryCacheManager(book_title=book_title) if enable_cache else None
        
        logger.info(
            f"[INFO] PageExtractor initialized: domain={domain}, cache={enable_cache}"
        )

    def extract_page_entities(
        self,
        page_text: str,
        book_context: Dict[str, Any],
        use_cache: bool = True,
    ) -> Dict[str, Any]:
        """
        페이지 엔티티 추출 (캐시 통합)

        Args:
            page_text: 페이지 원문 텍스트
            book_context: 책 컨텍스트 (book_title, chapter_title, chapter_number)
            use_cache: 캐시 사용 여부

        Returns:
            구조화된 엔티티 딕셔너리 (JSON 직렬화 가능)
        """
        # 1. 캐시 확인
        if use_cache and self.cache_manager:
            content_hash = self.cache_manager.get_content_hash(page_text)
            cached_result = self.cache_manager.get_cached_summary(
                content_hash, "page"
            )
            if cached_result:
                logger.info(
                    f"[INFO] Cache hit for page extraction (hash: {content_hash[:8]}...)"
                )
                try:
                    # 캐시된 결과는 JSON 문자열이므로 파싱하여 반환
                    # SummaryCacheManager는 summary_text 필드에 JSON 문자열을 저장
                    return json.loads(cached_result)
                except (json.JSONDecodeError, TypeError) as e:
                    logger.warning(
                        f"[WARNING] Failed to parse cached result: {e}, will re-extract"
                    )
                    # 파싱 실패 시 재추출

        # 2. LLM 호출
        logger.info(
            f"[INFO] Extracting page entities (domain={self.domain}, "
            f"chapter={book_context.get('chapter_title', 'N/A')})"
        )
        
        try:
            result = self.chain.extract_entities(page_text, book_context)
            
            # 3. Pydantic 모델을 JSON으로 변환
            result_json = result.model_dump_json()
            result_dict = json.loads(result_json)
            
            # 4. 캐시 저장
            if use_cache and self.cache_manager:
                content_hash = self.cache_manager.get_content_hash(page_text)
                self.cache_manager.save_cache(content_hash, "page", result_json)
                logger.info(
                    f"[INFO] Cached page extraction result (hash: {content_hash[:8]}...)"
                )
            
            return result_dict
            
        except Exception as e:
            logger.error(f"[ERROR] Page extraction failed: {e}")
            raise

