"""
본문 영역 탐지 모듈 (Footer 기반, 개선 버전)

Footer의 구조 판별자를 기준으로 서문/본문/종문 영역을 분리합니다.
홀수 페이지(좌측)의 Footer를 우선적으로 확인하며, 챕터 표시 판별자와 페이지 번호를 구분합니다.
"""

import re
import logging
from typing import Dict, Any, List, Optional
from backend.config.constants import START_KEYWORDS, END_KEYWORDS

logger = logging.getLogger(__name__)


class ContentBoundaryDetector:
    """본문 영역 경계 탐지 클래스 (Footer 기반, 개선 버전)"""

    def __init__(self):
        """경계 탐지기 초기화"""
        # 챕터 패턴 (챕터 표시 판별자 인식용)
        self.chapter_patterns = [
            re.compile(r"제\s*\d+\s*[장강부]"),  # 제1장, 제1강, 제1부
            re.compile(r"CHAPTER\s*\d+", re.IGNORECASE),  # Chapter 1, Chapter1
            re.compile(r"Part\s*\d+", re.IGNORECASE),  # Part 1, Part1
            re.compile(r"^\d+\s*[장강부]"),  # 1장, 1강
            re.compile(r"^\d+\.\s*[가-힣]"),  # 1. 제목, 1.제목
            re.compile(r"^\d+[_\-\s]+[가-힣]"),  # 1_제목, 1-제목, 1 제목
            re.compile(r"^0?\d+[_\-\s]+[가-힣]"),  # 01 바빌론, 1_제목 (30개도시로읽는세계사)
            re.compile(r"^\d+_\s*[가-힣A-Z0-9]"),  # 1_3D, 1_제목 (3D프린터의모든것 - 영문/숫자 허용)
        ]

    def detect_boundaries(self, parsed_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        서문(start)/본문(main)/종문(end) 경계 탐지 (Footer 기반, 개선 버전)

        Returns:
            {
                "start": {"start": 1, "end": 3, "pages": [1,2,3]},
                "main": {"start": 4, "end": 95, "pages": [4,5,...,95]},
                "end": {"start": 96, "end": 100, "pages": [96,97,98,99,100]},
                "confidence": {"start": 0.9, "main": 1.0, "end": 0.8}
            }
        """
        logger.info("[INFO] Detecting content boundaries (Footer 기반, 개선 버전)...")

        pages = parsed_data.get("pages", [])
        if not pages:
            return self._default_result()

        # 1. 개선된 본문 시작 페이지 탐지 (챕터 표시 판별자 기준)
        main_start = self._detect_main_start_improved(pages)

        # 2. 종문 시작 페이지 탐지
        end_start = self._detect_notes_start_improved(pages, main_start)

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
                "main": 1.0 if main_pages else 0.0,
                "end": 0.8 if end_pages else 0.0,
            },
        }

        logger.info("[INFO] Boundaries detected (Footer 기반, 개선 버전):")
        logger.info(
            f"  서문(start): pages {result['start']['start']}-{result['start']['end']} ({len(start_pages)} pages)"
        )
        logger.info(
            f"  본문(main):  pages {result['main']['start']}-{result['main']['end']} ({len(main_pages)} pages)"
        )
        logger.info(
            f"  종문(end): pages {result['end']['start']}-{result['end']['end']} ({len(end_pages)} pages)"
        )

        return result

    def _detect_main_start_improved(self, pages: List[Dict]) -> int:
        """
        개선된 본문 시작 페이지 탐지

        로직:
        1. 홀수 페이지의 Footer에서 챕터 표시 판별자 찾기
        2. 첫 번째 챕터 표시가 나타나는 페이지를 본문 시작으로 판단
        3. 서문 키워드가 있는 페이지는 제외

        Args:
            pages: 페이지 리스트

        Returns:
            본문 시작 페이지 번호 (1-indexed)
        """
        logger.info("[INFO] Detecting main content start (개선 버전: 챕터 표시 판별자 기준)...")

        for page in pages:
            page_num = page.get("page_number", 0)

            # 표지는 제외 (1-2페이지)
            if page_num <= 2:
                continue

            # 홀수 페이지만 처리
            if page_num % 2 == 0:
                continue

            # Footer 요소 분류
            footer_elements = self._get_footer_elements(page)
            chapter_markers = [
                elem
                for elem in footer_elements
                if self._classify_footer_element(elem) == "chapter_marker"
            ]

            # 챕터 표시가 있으면 본문 시작 후보
            if chapter_markers:
                # 서문 키워드 확인 (페이지 전체 텍스트에서)
                if not self._has_start_keywords(page):
                    logger.info(
                        f"[INFO] Main starts at page {page_num} (챕터 표시 판별자 발견)"
                    )
                    return page_num

        # 기본값: 3페이지부터
        logger.info("[INFO] Main starts at page 3 (기본값, 챕터 표시 판별자 없음)")
        return 3

    def _detect_notes_start_improved(
        self, pages: List[Dict], main_start: int
    ) -> Optional[int]:
        """
        개선된 종문 시작 페이지 탐지

        Args:
            pages: 페이지 리스트
            main_start: 본문 시작 페이지

        Returns:
            종문 시작 페이지 번호 또는 None
        """
        logger.info("[INFO] Detecting notes/post-body section start (개선 버전)...")

        # 본문 후반부만 검사 (전체의 50% 이후)
        search_start_idx = max(main_start, int(len(pages) * 0.5))

        for page in pages[search_start_idx:]:
            page_num = page.get("page_number", 0)

            # 홀수 페이지만 처리
            if page_num % 2 == 0:
                continue

            # Footer 요소에서 종문 키워드 확인
            footer_elements = self._get_footer_elements(page)
            
            # Footer 요소 상세 로그 (159페이지 주변만)
            if 157 <= page_num <= 161:
                logger.info(f"[INFO] Page {page_num} 종문 탐지 검사:")
                logger.info(f"  - Footer 요소 개수: {len(footer_elements)}")
                for idx, elem in enumerate(footer_elements):
                    text = elem.get("text", "").strip()
                    bbox = elem.get("bbox", {})
                    x0 = bbox.get("x0", 0.5)
                    y0 = bbox.get("y0", 0.0)
                    classification = self._classify_footer_element(elem)
                    logger.info(
                        f"  - 요소 #{idx+1}: text='{text[:80]}', "
                        f"x0={x0:.3f}, y0={y0:.3f}, 분류={classification}"
                    )
            
            footer_text = " ".join(
                [
                    elem.get("text", "").strip()
                    for elem in footer_elements
                    if elem.get("text", "").strip()
                ]
            )

            # 종문 키워드 확인 (단어 단위 매칭)
            matched_keywords = []
            footer_lower = footer_text.lower()
            for keyword in END_KEYWORDS:
                keyword_lower = keyword.lower()
                
                # 단일 문자 키워드("주")는 단독으로만 매칭
                if len(keyword) == 1:
                    # 공백으로 분리된 단어들 중에 정확히 "주"가 있는지 확인
                    words = footer_lower.split()
                    if keyword_lower in words:
                        matched_keywords.append(keyword)
                else:
                    # 다중 문자 키워드는 기존 방식 (부분 문자열 매칭)
                    if keyword_lower in footer_lower:
                        matched_keywords.append(keyword)

            if matched_keywords:
                logger.info(
                    f"[INFO] Post-body starts at page {page_num} (종문 키워드 발견: {matched_keywords})"
                )
                logger.info(
                    f"[INFO] Page {page_num} Footer 텍스트 전체: {footer_text}"
                )
                # 각 키워드가 어디서 매칭되었는지 상세 확인
                for keyword in matched_keywords:
                    keyword_lower = keyword.lower()
                    footer_lower = footer_text.lower()
                    if keyword_lower in footer_lower:
                        start_idx = footer_lower.find(keyword_lower)
                        context_start = max(0, start_idx - 20)
                        context_end = min(len(footer_text), start_idx + len(keyword) + 20)
                        context = footer_text[context_start:context_end]
                        logger.info(
                            f"  - 키워드 '{keyword}' 매칭 위치: "
                            f"'{context}' (전체 텍스트의 {start_idx}번째 문자부터)"
                        )
                return page_num

        logger.info("[INFO] No post-body section detected")
        return None

    def _classify_footer_element(self, elem: Dict) -> str:
        """
        Footer 요소를 분류

        Returns:
            "chapter_marker": 챕터 표시 판별자
            "page_number": 페이지 번호
            "other": 기타 (저자명, 출판사 등)
        """
        text = elem.get("text", "").strip()
        bbox = elem.get("bbox", {})
        x0 = bbox.get("x0", 0.5)

        # 1. 챕터 패턴 확인 (최우선)
        if self._is_chapter_pattern(text):
            return "chapter_marker"

        # 2. 위치 기반 판단
        if x0 < 0.05:  # 왼쪽 끝 (페이지 번호 영역)
            if self._is_page_number(text):
                return "page_number"

        # 3. 중앙 영역 (챕터 제목 영역)
        if 0.05 < x0 < 0.5:  # 중앙
            if self._has_chapter_keywords(text):
                return "chapter_marker"

        # 4. 기타
        return "other"

    def _is_chapter_pattern(self, text: str) -> bool:
        """
        챕터 패턴 확인

        패턴 예시:
        - "제1장", "제1강", "제1부"
        - "Chapter 1", "Part 1"
        - "1장", "1강"
        """
        for pattern in self.chapter_patterns:
            if pattern.search(text):
                return True
        return False

    def _has_chapter_keywords(self, text: str) -> bool:
        """
        챕터 관련 키워드 확인

        예: "제", "장", "강", "Chapter", "Part" 등
        """
        keywords = ["제", "장", "강", "부", "chapter", "part"]
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in keywords)

    def _is_page_number(self, text: str) -> bool:
        """
        페이지 번호인지 확인

        기준:
        - 숫자만 있음 (1-3자리)
        - 챕터 패턴이 아님
        - 특정 범위 내 (예: 1-1000)
        """
        # 숫자만 있는지 확인
        if not re.match(r"^\d{1,3}$", text):
            return False

        number = int(text)

        # 합리적인 페이지 번호 범위
        if 1 <= number <= 1000:
            return True

        return False

    def _has_start_keywords(self, page: Dict) -> bool:
        """
        페이지에 서문 키워드가 있는지 확인

        Args:
            page: 페이지 딕셔너리

        Returns:
            서문 키워드 존재 여부
        """
        # 페이지 전체 텍스트 확인
        elements = page.get("elements", [])
        page_text = " ".join(
            [elem.get("text", "").strip() for elem in elements if elem.get("text", "")]
        )

        return any(
            keyword.lower() in page_text.lower() for keyword in START_KEYWORDS
        )

    def _get_footer_elements(self, page: Dict) -> List[Dict]:
        """
        페이지에서 Footer 영역 요소 추출

        Footer 영역:
        1. category='footer'인 요소
        2. y0 좌표가 큰 요소 (페이지 하단, y0 > 0.9)

        Args:
            page: 페이지 딕셔너리

        Returns:
            Footer 요소 리스트
        """
        elements = page.get("elements", [])
        footer_elements = []

        for elem in elements:
            # 1. category='footer'인 요소
            if elem.get("category") == "footer":
                footer_elements.append(elem)
                continue

            # 2. y0 좌표가 큰 요소 (페이지 하단)
            bbox = elem.get("bbox", {})
            y0 = bbox.get("y0", 0.0)
            if y0 > 0.9:  # 페이지 하단 10% 영역 (강화: 0.8 → 0.9)
                footer_elements.append(elem)

        # y0 기준으로 정렬 (하단에 가까울수록 우선)
        footer_elements.sort(
            key=lambda e: e.get("bbox", {}).get("y0", 0.0), reverse=True
        )

        return footer_elements

    def _default_result(self) -> Dict[str, Any]:
        """기본 결과 (탐지 실패 시)"""
        return {
            "start": {"start": None, "end": None, "pages": []},
            "main": {"start": 1, "end": 1, "pages": [1]},
            "end": {"start": None, "end": None, "pages": []},
            "confidence": {"start": 0.0, "main": 0.0, "end": 0.0},
        }
