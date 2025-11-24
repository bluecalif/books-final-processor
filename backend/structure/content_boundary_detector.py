"""
콘텐츠 경계 탐지 모듈

키워드 기반으로 서문/본문/끝 영역의 경계를 탐지합니다.
"""
import logging
import re
from typing import Dict, Any, List, Optional
from backend.config.constants import START_KEYWORDS, END_KEYWORDS

logger = logging.getLogger(__name__)


class ContentBoundaryDetector:
    """콘텐츠 경계 탐지 클래스"""

    def __init__(self):
        """초기화"""
        self.start_keywords = START_KEYWORDS
        self.end_keywords = END_KEYWORDS

    def detect_boundaries(self, parsed_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        서문/본문/끝 영역 경계 탐지

        Args:
            parsed_data: PDFParser.parse_pdf() 결과

        Returns:
            {
                "start": {"pages": [1, 2, 3], "page_count": 3},
                "main": {"pages": [4, 5, ..., 95], "page_count": 92},
                "end": {"pages": [96, ..., 100], "page_count": 5}
            }
        """
        logger.info("[INFO] Detecting content boundaries...")

        pages = parsed_data.get("pages", [])
        total_pages = len(pages)

        if total_pages == 0:
            logger.warning("[WARNING] No pages found in parsed_data")
            return self._default_result(total_pages)

        # 1. 본문 시작 페이지 탐지 (앞쪽 20페이지에서 시작 키워드 검색)
        main_start_page = self._detect_main_start(pages, total_pages)

        # 2. 본문 끝 페이지 탐지 (뒤쪽 30페이지에서 끝 키워드 검색)
        main_end_page = self._detect_main_end(pages, total_pages, main_start_page)

        # 3. 영역별 페이지 리스트 생성
        start_pages = list(range(1, main_start_page)) if main_start_page > 1 else []
        main_pages = list(
            range(main_start_page, main_end_page + 1)
            if main_end_page
            else range(main_start_page, total_pages + 1)
        )
        end_pages = (
            list(range(main_end_page + 1, total_pages + 1))
            if main_end_page and main_end_page < total_pages
            else []
        )

        result = {
            "start": {"pages": start_pages, "page_count": len(start_pages)},
            "main": {"pages": main_pages, "page_count": len(main_pages)},
            "end": {"pages": end_pages, "page_count": len(end_pages)},
        }

        logger.info(
            f"[INFO] Boundaries detected: start={len(start_pages)} pages, "
            f"main={len(main_pages)} pages, end={len(end_pages)} pages"
        )

        return result

    def _detect_main_start(self, pages: List[Dict], total_pages: int) -> int:
        """
        본문 시작 페이지 탐지

        앞쪽 20페이지에서 시작 키워드 검색
        키워드를 찾으면 그 다음 페이지를 본문 시작으로 설정

        Returns:
            본문 시작 페이지 번호 (1-indexed, 최소 3)
        """
        search_limit = min(20, total_pages)
        search_pages = pages[:search_limit]

        for page in search_pages:
            page_num = page.get("page_number", 0)
            if page_num <= 2:  # 표지는 제외
                continue

            page_text = page.get("raw_text", "").lower()

            # 시작 키워드 검색
            for keyword in self.start_keywords:
                # 단어 경계 매칭
                pattern = r"\b" + re.escape(keyword.lower()) + r"\b"
                if re.search(pattern, page_text, re.IGNORECASE):
                    logger.info(
                        f"[INFO] Found start keyword '{keyword}' at page {page_num}, "
                        f"main starts at page {page_num + 1}"
                    )
                    return max(3, page_num + 1)  # 최소 3페이지부터

        # 키워드를 찾지 못한 경우 기본값 (3페이지부터)
        logger.info("[INFO] No start keyword found, using default: page 3")
        return 3

    def _detect_main_end(
        self, pages: List[Dict], total_pages: int, main_start: int
    ) -> Optional[int]:
        """
        본문 끝 페이지 탐지

        뒤쪽 30페이지에서 끝 키워드 검색
        키워드를 찾으면 그 이전 페이지를 본문 끝으로 설정

        Args:
            pages: 페이지 리스트
            total_pages: 전체 페이지 수
            main_start: 본문 시작 페이지

        Returns:
            본문 끝 페이지 번호 (None이면 끝까지)
        """
        search_limit = min(30, total_pages)
        search_start_idx = max(0, total_pages - search_limit)
        search_pages = pages[search_start_idx:]

        for page in reversed(search_pages):  # 뒤에서부터 검색
            page_num = page.get("page_number", 0)

            # 본문 시작 이전은 제외
            if page_num < main_start:
                continue

            page_text = page.get("raw_text", "").lower()

            # 끝 키워드 검색
            for keyword in self.end_keywords:
                # 단어 경계 매칭
                pattern = r"\b" + re.escape(keyword.lower()) + r"\b"
                if re.search(pattern, page_text, re.IGNORECASE):
                    logger.info(
                        f"[INFO] Found end keyword '{keyword}' at page {page_num}, "
                        f"main ends at page {page_num - 1}"
                    )
                    return max(main_start, page_num - 1)

        # 키워드를 찾지 못한 경우 None (끝까지)
        logger.info("[INFO] No end keyword found, main extends to the end")
        return None

    def _default_result(self, total_pages: int) -> Dict[str, Any]:
        """기본 결과 (탐지 실패 시)"""
        return {
            "start": {"pages": [], "page_count": 0},
            "main": {"pages": list(range(1, total_pages + 1)), "page_count": total_pages},
            "end": {"pages": [], "page_count": 0},
        }

