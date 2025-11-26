"""
본문 영역 탐지 모듈

Intro (표지, 서문) / Main (본문) / Notes (참고문헌, 부록) 영역을 분리합니다.
"""

import re
import logging
from typing import Dict, Any, List, Optional
from backend.config.constants import (
    START_KEYWORDS,
    END_KEYWORDS,
    MAIN_START_PATTERNS,
    MIN_PARAGRAPH_LENGTH,
)

logger = logging.getLogger(__name__)


class ContentBoundaryDetector:
    """본문 영역 경계 탐지 클래스"""

    def __init__(self):
        """경계 탐지기 초기화"""
        # FooterAnalyzer 의존성 제거 (Phase 3에서는 불필요)
        pass

    def detect_boundaries(self, parsed_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        서문(start)/본문(main)/종문(end) 경계 탐지

        Returns:
            {
                "start": {"start": 1, "end": 3, "pages": [1,2,3]},
                "main": {"start": 4, "end": 95, "pages": [4,5,...,95]},
                "end": {"start": 96, "end": 100, "pages": [96,97,98,99,100]},
                "confidence": {"start": 0.9, "main": 1.0, "end": 0.8}
            }
        """
        logger.info("[INFO] Detecting content boundaries (서문/본문/종문)...")

        pages = parsed_data.get("pages", [])
        if not pages:
            return self._default_result()

        # Footer 정보는 빈 dict로 처리 (FooterAnalyzer 제거)
        footer_info = {}

        # 1. 본문 시작 페이지 탐지
        main_start = self._detect_main_start(pages, footer_info)

        # 2. 종문 시작 페이지 탐지
        end_start = self._detect_notes_start(pages, main_start, footer_info)

        # 3. 경계 확정
        start_pages = list(range(1, main_start))
        main_end = end_start - 1 if end_start else len(pages)
        main_pages = list(range(main_start, main_end + 1))
        end_pages = list(range(end_start, len(pages) + 1)) if end_start else []

        result = {
            "start": {
                "start": start_pages[0] if start_pages else None,
                "end": start_pages[-1] if start_pages else None,
                "pages": start_pages,
            },
            "main": {
                "start": main_pages[0] if main_pages else 1,
                "end": main_pages[-1] if main_pages else len(pages),
                "pages": main_pages,
            },
            "end": {
                "start": end_pages[0] if end_pages else None,
                "end": end_pages[-1] if end_pages else None,
                "pages": end_pages,
            },
            "confidence": {
                "start": 0.8 if start_pages else 0.0,
                "main": 1.0,
                "end": 0.8 if end_pages else 0.0,
            },
        }

        logger.info("[INFO] Boundaries detected:")
        logger.info(
            f"  서문(start): pages {start_pages[0] if start_pages else None}-{start_pages[-1] if start_pages else None} ({len(start_pages)} pages)"
        )
        logger.info(
            f"  본문(main):  pages {main_pages[0]}-{main_pages[-1]} ({len(main_pages)} pages)"
        )
        logger.info(
            f"  종문(end): pages {end_pages[0] if end_pages else None}-{end_pages[-1] if end_pages else None} ({len(end_pages)} pages)"
        )

        return result

    def _detect_main_start(self, pages: List[Dict], footer_info: Dict) -> int:
        """
        본문 시작 페이지 탐지

        Returns:
            본문 시작 페이지 번호 (1-indexed)
        """
        logger.info("[INFO] Detecting main content start...")

        best_score = 0.0
        best_page = 3  # 최소 3페이지부터 시작 (표지 제외)

        for page in pages:
            page_num = page["page_number"]

            # 표지는 제외 (1-2페이지)
            if page_num <= 2:
                continue

            score = self._calculate_main_start_score(page, footer_info)

            if score > best_score:
                best_score = score
                best_page = page_num

        # Footer 힌트로 추가 검증 (footer_info가 비어있으면 스킵)
        chapter_hints = footer_info.get("chapter_hints", [])
        if chapter_hints and best_score < 0.6:
            # 챕터 힌트가 있으면 그 부근을 우선
            first_chapter_page = min(chapter_hints)
            if first_chapter_page >= 3:
                logger.info(
                    f"[INFO] Using footer hint: first chapter at page {first_chapter_page}"
                )
                best_page = first_chapter_page

        logger.info(
            f"[INFO] Main starts at page {best_page} (score: {best_score:.2f})"
        )
        return best_page

    def _detect_notes_start(
        self, pages: List[Dict], main_start: int, footer_info: Dict
    ) -> Optional[int]:
        """
        종문 시작 페이지 탐지 (3단계 계층적 필터링)

        Phase 1: Footer 요소 우선 검사 (단어 경계 매칭)
        Phase 2: 제목 형태 Element 검사 (짧은 텍스트 + 큰 폰트 + 상단)
        Phase 3: 전체 텍스트 검사 (fallback, 단어 경계 매칭)

        Args:
            main_start: 본문 시작 페이지
            footer_info: Footer 분석 정보

        Returns:
            종문 시작 페이지 번호 또는 None
        """
        logger.info("[INFO] Detecting notes/post-body section start...")

        # Footer 힌트 먼저 확인
        post_body_start = footer_info.get("post_body_start")
        if post_body_start and post_body_start > main_start:
            logger.info(
                f"[INFO] Using footer hint: post-body starts at page {post_body_start}"
            )
            return post_body_start

        # 본문 후반부만 검사 (전체의 50% 이후)
        search_start_idx = max(main_start, int(len(pages) * 0.5))
        logger.info(
            f"[INFO] Searching from page {pages[search_start_idx]['page_number']} (50% of total)"
        )

        # Phase 1: Footer 우선 검사
        result = self._check_footer_elements(pages, search_start_idx)
        if result:
            return result

        # Phase 2: 제목 형태 Element 검사
        result = self._check_title_like_elements(pages, search_start_idx)
        if result:
            return result

        # Phase 3: 전체 텍스트 검사 (fallback)
        result = self._check_full_text(pages, search_start_idx)
        if result:
            return result

        logger.info("[INFO] No post-body section detected")
        return None

    def _check_footer_elements(
        self, pages: List[Dict], start_idx: int
    ) -> Optional[int]:
        """Phase 1: Footer 요소만 검사 (단어 경계 매칭)"""
        logger.info("[INFO] Phase 1: Checking footer elements...")

        for page in pages[start_idx:]:
            page_num = page["page_number"]
            footer_elements = [
                e for e in page.get("elements", []) if e.get("category") == "footer"
            ]

            for elem in footer_elements:
                text = elem.get("text", "").strip()

                for keyword in END_KEYWORDS:
                    # 단어 경계 매칭 (\b = word boundary)
                    pattern = r"\b" + re.escape(keyword) + r"\b"
                    if re.search(pattern, text, re.IGNORECASE):
                        logger.info(
                            f"[INFO] Found in footer at page {page_num}: "
                            f"keyword='{keyword}', text='{text[:50]}...'"
                        )
                        return page_num

        return None

    def _check_title_like_elements(
        self, pages: List[Dict], start_idx: int
    ) -> Optional[int]:
        """Phase 2: 제목 형태 Element 검사 (짧은 텍스트 + 큰 폰트 + 상단)"""
        logger.info("[INFO] Phase 2: Checking title-like elements...")

        for page in pages[start_idx:]:
            page_num = page["page_number"]
            elements = page.get("elements", [])

            if not elements:
                continue

            # 페이지 맨 위 요소들만 검사 (상위 20%)
            top_elements = []
            for elem in elements:
                bbox = elem.get("bbox", {})
                y0 = bbox.get("y0", 1.0)
                if y0 < 0.2:  # 상단 20% 이내
                    top_elements.append(elem)

            for elem in top_elements:
                text = elem.get("text", "").strip()
                font_size = elem.get("font_size", 12)
                text_length = len(text)

                # 제목 조건: 짧고(≤50자) + 큰 폰트(≥14px)
                if text_length <= 50 and font_size >= 14:
                    for keyword in END_KEYWORDS:
                        # 단어 경계 매칭
                        pattern = r"\b" + re.escape(keyword) + r"\b"
                        if re.search(pattern, text, re.IGNORECASE):
                            logger.info(
                                f"[INFO] Found title-like at page {page_num}: "
                                f"keyword='{keyword}', text='{text}', "
                                f"font_size={font_size}, length={text_length}"
                            )
                            return page_num

        return None

    def _check_full_text(self, pages: List[Dict], start_idx: int) -> Optional[int]:
        """Phase 3: 전체 텍스트 검사 (fallback, 단어 경계 매칭)"""
        logger.info("[INFO] Phase 3: Checking full text (fallback)...")

        best_page = None
        best_score = 0.0

        for page in pages[start_idx:]:
            page_num = page["page_number"]
            page_text = " ".join(
                [elem.get("text", "") for elem in page.get("elements", [])]
            )

            for keyword in END_KEYWORDS:
                # 단어 경계 매칭
                pattern = r"\b" + re.escape(keyword) + r"\b"
                if re.search(pattern, page_text, re.IGNORECASE):
                    # 키워드 중요도에 따라 점수 부여
                    if keyword in [
                        "맺음말",
                        "에필로그",
                        "epilogue",
                        "각주",
                        "미주",
                        "endnote",
                        "참고문헌",
                        "references",
                    ]:
                        score = 1.0
                    else:
                        score = 0.7

                    if score > best_score:
                        best_score = score
                        best_page = page_num
                        logger.info(
                            f"[INFO] Post-body candidate at page {best_page} "
                            f"(keyword: '{keyword}', score: {score:.2f})"
                        )
                        break

            # 점수가 높으면 바로 리턴
            if best_score >= 1.0:
                break

        if best_page:
            logger.info(
                f"[INFO] Post-body starts at page {best_page} (full text match)"
            )
            return best_page

        return None

    def _calculate_main_start_score(self, page: Dict, footer_info: Dict) -> float:
        """
        본문 시작 가능성 점수 계산

        점수 구성:
        - 본문 패턴 매칭: 50% (0.5점)
        - 긴 단락 존재: 30% (0.3점)
        - Footer 힌트: 20% (0.2점)
        - Pre Body 키워드 페널티: -0.4점
        """
        elements = page.get("elements", [])
        page_text = " ".join([elem.get("text", "") for elem in elements])
        page_num = page.get("page_number", 0)

        score = 0.0

        # 1. 본문 시작 패턴 확인 (50%)
        if any(pattern.search(page_text) for pattern in MAIN_START_PATTERNS):
            score += 0.5

        # 2. 긴 단락 확인 (30%)
        has_long_paragraph = any(
            len(elem.get("text", "")) >= MIN_PARAGRAPH_LENGTH
            for elem in elements
            if elem.get("category") == "paragraph"
        )
        if has_long_paragraph:
            score += 0.3

        # 3. Footer 힌트 (20%) - footer_info가 비어있으면 스킵
        chapter_hints = footer_info.get("chapter_hints", [])
        if page_num in chapter_hints:
            score += 0.2

        # 4. Pre Body 키워드 페널티
        has_pre_body_keyword = any(
            keyword.lower() in page_text.lower() for keyword in START_KEYWORDS
        )
        if has_pre_body_keyword:
            score = max(0, score - 0.4)

        return min(1.0, score)

    def _default_result(self) -> Dict[str, Any]:
        """기본 결과 (탐지 실패 시)"""
        return {
            "start": {"start": None, "end": None, "pages": []},
            "main": {"start": 1, "end": 1, "pages": [1]},
            "end": {"start": None, "end": None, "pages": []},
            "confidence": {"start": 0.0, "main": 0.0, "end": 0.0},
        }
