"""
챕터 구조화기

페이지 엔티티를 집계하여 챕터 단위 구조화를 수행합니다.
캐시를 통합하여 비용을 절감합니다.
"""
import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from backend.summarizers.llm_chains import ChapterStructuringChain
from backend.summarizers.summary_cache_manager import SummaryCacheManager

logger = logging.getLogger(__name__)


class ChapterStructurer:
    """챕터 구조화기"""

    def __init__(self, domain: str, enable_cache: bool = True, book_title: str = None):
        """
        Args:
            domain: 도메인 코드 ("history", "economy", "humanities", "science")
            enable_cache: 캐시 사용 여부
            book_title: 책 제목 (캐시 폴더 분리용)
        """
        self.domain = domain
        self.chain = ChapterStructuringChain(domain)
        self.cache_manager = SummaryCacheManager(book_title=book_title) if enable_cache else None
        
        logger.info(
            f"[INFO] ChapterStructurer initialized: domain={domain}, cache={enable_cache}"
        )

    def structure_chapter(
        self,
        page_entities_list: List[Dict[str, Any]],
        book_context: Dict[str, Any],
        use_cache: bool = True,
    ) -> Tuple[Dict[str, Any], Optional[Dict[str, int]]]:
        """
        챕터 구조화 (페이지 엔티티 집계)

        Args:
            page_entities_list: 페이지 엔티티 목록 (각 페이지의 structured_data)
            book_context: 책 컨텍스트 (book_title, chapter_title, chapter_number, book_summary 등)
            use_cache: 캐시 사용 여부

        Returns:
            구조화된 챕터 엔티티 딕셔너리 (JSON 직렬화 가능)
        """
        # 0. 2페이지 이하 챕터 스킵
        if len(page_entities_list) <= 2:
            logger.warning(
                f"[WARNING] Chapter has {len(page_entities_list)} pages, skipping chapter structuring "
                f"(chapter: {book_context.get('chapter_title', 'N/A')})"
            )
            # None 반환하여 스킵 표시
            return None, None
        
        # 1. 페이지 엔티티 압축 (상위 N개만 추려서 LLM에 전달)
        compressed_pages = self._compress_page_entities(page_entities_list)
        
        # 디버깅: 페이지 엔티티 수 및 페이지 번호 로깅
        page_numbers = [pe.get("page_number") for pe in page_entities_list if pe.get("page_number")]
        logger.info(
            f"[CACHE_DEBUG] Chapter structuring input: "
            f"chapter={book_context.get('chapter_title', 'N/A')}, "
            f"page_entities_count={len(page_entities_list)}, "
            f"page_numbers={sorted(page_numbers)[:10]}{'...' if len(page_numbers) > 10 else ''}, "
            f"compressed_count={len(compressed_pages)}"
        )
        
        # 2. 캐시 확인
        if use_cache and self.cache_manager:
            cache_key = self._generate_cache_key(compressed_pages, book_context)
            logger.info(
                f"[CACHE_DEBUG] Generated cache key: {cache_key[:16]}... "
                f"(chapter={book_context.get('chapter_title', 'N/A')}, "
                f"compressed_pages_count={len(compressed_pages)})"
            )
            cached_result = self.cache_manager.get_cached_summary(
                cache_key, "chapter"
            )
            if cached_result:
                logger.info(
                    f"[INFO] Cache hit for chapter structuring (hash: {cache_key[:8]}...)"
                )
                # 캐시된 결과는 이미 딕셔너리 형태 (새로운 시각화 구조)
                # 캐시 히트 시에는 usage 정보가 없음 (None 반환)
                # 메타 정보가 없는 경우 추가 (기존 캐시 보강 전)
                if "chapter_number" not in cached_result or "chapter_title" not in cached_result:
                    chapter_number = book_context.get("chapter_number")
                    chapter_title = book_context.get("chapter_title")
                    if isinstance(chapter_number, str):
                        try:
                            chapter_number = int(chapter_number)
                        except (ValueError, TypeError):
                            chapter_number = None
                    # chapter_number는 이미 1-based로 전달됨 (추가 변환 불필요)
                    cached_result["chapter_number"] = chapter_number
                    cached_result["chapter_title"] = chapter_title
                
                # page_count가 없는 경우 추가
                if "page_count" not in cached_result:
                    cached_result["page_count"] = len(page_entities_list)
                
                return cached_result, None
            else:
                logger.info(
                    f"[CACHE_DEBUG] Cache miss for chapter structuring (hash: {cache_key[:8]}...)"
                )

        # 3. LLM 호출
        logger.info(
            f"[INFO] Structuring chapter (domain={self.domain}, "
            f"chapter={book_context.get('chapter_title', 'N/A')}, "
            f"pages={len(page_entities_list)})"
        )
        
        try:
            result, usage = self.chain.structure_chapter(compressed_pages, book_context)
            
            # 4. Pydantic 모델을 JSON으로 변환
            result_json = result.model_dump_json()
            result_dict = json.loads(result_json)
            
            # 5. 챕터 메타 정보 추가 (chapter_number, chapter_title)
            chapter_number = book_context.get("chapter_number")
            chapter_title = book_context.get("chapter_title")
            
            # chapter_number가 문자열인 경우 숫자로 변환 시도
            if isinstance(chapter_number, str):
                try:
                    # "1", "2" 같은 문자열을 숫자로 변환
                    chapter_number = int(chapter_number)
                except (ValueError, TypeError):
                    # 변환 실패 시 None으로 설정
                    chapter_number = None
            
            # chapter_number는 이미 1-based로 전달됨 (ExtractionService에서 order_index + 1)
            # 추가 변환 불필요
            
            result_dict["chapter_number"] = chapter_number
            result_dict["chapter_title"] = chapter_title
            result_dict["page_count"] = len(page_entities_list)  # 페이지 수 추가
            
            # 6. 캐시 저장
            if use_cache and self.cache_manager:
                cache_key = self._generate_cache_key(compressed_pages, book_context)
                # 딕셔너리를 직접 전달 (JSON 문자열 변환 제거, 메타 정보 포함)
                self.cache_manager.save_cache(cache_key, "chapter", result_dict)
                logger.info(
                    f"[INFO] Cached chapter structuring result (hash: {cache_key[:16]}... "
                    f"chapter={chapter_title or 'N/A'}, number={chapter_number or 'N/A'})"
                )
            
            return result_dict, usage
            
        except Exception as e:
            logger.error(f"[ERROR] Chapter structuring failed: {e}")
            raise

    def _compress_page_entities(
        self, page_entities_list: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        페이지 엔티티 압축 (상위 N개만 추려서 LLM에 전달)

        Args:
            page_entities_list: 페이지 엔티티 목록

        Returns:
            압축된 페이지 엔티티 목록
        """
        compressed = []
        
        for page_entity in page_entities_list:
            # 각 페이지에서 핵심 정보만 추출
            compressed_page = {
                "page_number": page_entity.get("page_number"),
                "page_summary": page_entity.get("page_summary", ""),
                "page_function_tag": page_entity.get("page_function_tag"),
                # 주요 엔티티만 상위 N개 추려서 포함
                "key_concepts": page_entity.get("concepts", [])[:5],  # 상위 5개
                "key_events": page_entity.get("events", [])[:3],  # 상위 3개
                "key_examples": page_entity.get("examples", [])[:3],  # 상위 3개
                "key_persons": page_entity.get("persons", [])[:3],  # 상위 3개
                "key_sentences": page_entity.get("key_sentences", [])[:3],  # 상위 3개
            }
            
            # 도메인별 추가 필드 (있는 경우만)
            if self.domain == "history":
                compressed_page["locations"] = page_entity.get("locations", [])[:3]
                compressed_page["time_periods"] = page_entity.get("time_periods", [])[:2]
            elif self.domain == "economy":
                compressed_page["indicators"] = page_entity.get("indicators", [])[:3]
                compressed_page["strategies"] = page_entity.get("strategies", [])[:2]
            elif self.domain == "humanities":
                compressed_page["practices"] = page_entity.get("practices", [])[:3]
                compressed_page["life_situations"] = page_entity.get("life_situations", [])[:2]
            elif self.domain == "science":
                compressed_page["technologies"] = page_entity.get("technologies", [])[:3]
                compressed_page["applications"] = page_entity.get("applications", [])[:2]
            
            compressed.append(compressed_page)
        
        return compressed

    def _generate_cache_key(
        self, compressed_pages: List[Dict[str, Any]], book_context: Dict[str, Any]
    ) -> str:
        """
        캐시 키 생성 (압축된 페이지 엔티티 + 책 컨텍스트 해시)

        Args:
            compressed_pages: 압축된 페이지 엔티티 목록
            book_context: 책 컨텍스트

        Returns:
            MD5 해시 문자열
        """
        # 압축된 페이지 엔티티와 책 컨텍스트를 JSON으로 직렬화
        cache_data = {
            "compressed_pages": compressed_pages,
            "book_context": {
                "book_title": book_context.get("book_title"),
                "chapter_title": book_context.get("chapter_title"),
                "chapter_number": book_context.get("chapter_number"),
            },
        }
        
        cache_json = json.dumps(cache_data, sort_keys=True, ensure_ascii=False)
        return self.cache_manager.get_content_hash(cache_json)

