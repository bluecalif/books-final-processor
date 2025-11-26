"""
Footer 분석 모듈

Footer 정보를 추출하여 섹션 변화 힌트를 제공합니다.
⚠️ Footer는 보조 수단으로만 사용 (상위 계층 표시 가능)
"""

import re
import logging
from typing import Dict, Any, List, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)


class FooterAnalyzer:
    """Footer 분석 클래스"""

    # Pre Body 관련 키워드
    PRE_BODY_KEYWORDS = [
        "작가",
        "저자",
        "author",
        "추천",
        "추천의 글",
        "추천사",
        "recommendation",
        "서문",
        "머리말",
        "foreword",
        "preface",
        "감사",
        "acknowledgment",
        "헌정",
        "dedication",
    ]

    # Post Body 관련 키워드
    POST_BODY_KEYWORDS = [
        "맺음말",
        "에필로그",
        "epilogue",
        "conclusion",
        "주",
        "각주",
        "미주",
        "endnote",
        "note",
        "참고문헌",
        "references",
        "bibliography",
        "부록",
        "appendix",
        "색인",
        "index",
        "용어집",
        "glossary",
    ]

    # 챕터 관련 키워드
    CHAPTER_KEYWORDS = [
        "장",
        "chapter",
        "부",
        "part",
    ]

    def __init__(self):
        """초기화"""
        self.footer_data = defaultdict(dict)  # {page: {section_name, page_number}}
        self.section_changes = []  # [(page, old_section, new_section)]
        self.section_hints = defaultdict(list)  # {section_type: [pages]}

    def analyze(self, parsed_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        전체 Footer 정보 분석

        Args:
            parsed_data: PDFParser.parse_pdf() 결과

        Returns:
            {
                "footer_data": {page: {section_name, page_number}},
                "section_changes": [(page, old, new)],
                "pre_body_hints": [pages],
                "post_body_hints": [pages],
                "chapter_hints": [pages]
            }
        """
        logger.info("📑 Analyzing footer information...")

        pages = parsed_data.get("pages", [])

        # 1. 모든 페이지의 Footer 추출
        for page_data in pages:
            self._extract_page_footer(page_data)

        # 2. 섹션 변화 감지
        self._detect_section_changes()

        # 3. 섹션 타입별 힌트 분류
        self._classify_section_hints()

        # Post Body 시작 페이지 추정
        post_body_start = self.get_post_body_start()

        result = {
            "footer_data": dict(self.footer_data),
            "section_changes": self.section_changes,
            "pre_body_hints": self.section_hints.get("pre_body", []),
            "post_body_hints": self.section_hints.get("post_body", []),
            "post_body_start": post_body_start,  # 추가
            "chapter_hints": self.section_hints.get("chapter", []),
        }

        logger.info(f"   Footers found: {len(self.footer_data)} pages")
        logger.info(f"   Section changes: {len(self.section_changes)}")
        logger.info(f"   Pre-body hints: {len(result['pre_body_hints'])} pages")
        logger.info(f"   Post-body hints: {len(result['post_body_hints'])} pages")
        logger.info(f"   Post-body start: {post_body_start}")
        logger.info(f"   Chapter hints: {len(result['chapter_hints'])} pages")

        return result

    def _extract_page_footer(self, page_data: Dict) -> None:
        """단일 페이지의 Footer 추출"""
        page_num = page_data.get("page", 0)
        elements = page_data.get("elements", [])

        section_name = None
        page_number = None

        # Footer 요소 찾기
        for elem in elements:
            if elem.get("category") == "footer":
                text = elem.get("text", "").strip()
                bbox = elem.get("bbox", {})
                y_position = bbox.get("y0", 0)

                # 페이지 하단 (y > 0.9) 확인
                if y_position > 0.85:  # 하단 15% 영역
                    # 섹션명 추출 (페이지 번호가 아닌 텍스트)
                    if text and not text.isdigit() and len(text) > 1:
                        # 숫자만 있는 경우 제외
                        if not re.match(r"^[\d\s\-]+$", text):
                            section_name = text

                    # 페이지 번호 추출
                    page_num_match = re.search(r"\d+", text)
                    if page_num_match:
                        page_number = int(page_num_match.group())

        # Footer 정보 저장
        if section_name or page_number:
            self.footer_data[page_num] = {
                "section_name": section_name,
                "page_number": page_number,
            }

    def _detect_section_changes(self) -> None:
        """섹션 변화 감지"""
        sorted_pages = sorted(self.footer_data.keys())
        prev_section = None

        for page in sorted_pages:
            curr_section = self.footer_data[page].get("section_name")

            if curr_section and curr_section != prev_section:
                self.section_changes.append(
                    {
                        "page": page,
                        "old_section": prev_section,
                        "new_section": curr_section,
                    }
                )
                prev_section = curr_section

    def _classify_section_hints(self) -> None:
        """섹션 타입별 힌트 분류"""
        for page, footer_info in self.footer_data.items():
            section_name = footer_info.get("section_name")
            if not section_name:
                continue

            section_lower = section_name.lower()

            # Pre Body 키워드 매칭
            for keyword in self.PRE_BODY_KEYWORDS:
                if keyword.lower() in section_lower:
                    self.section_hints["pre_body"].append(page)
                    break

            # Post Body 키워드 매칭
            for keyword in self.POST_BODY_KEYWORDS:
                if keyword.lower() in section_lower:
                    self.section_hints["post_body"].append(page)
                    break

            # Chapter 키워드 매칭
            for keyword in self.CHAPTER_KEYWORDS:
                if keyword.lower() in section_lower:
                    self.section_hints["chapter"].append(page)
                    break

    def get_section_hint_for_page(self, page: int, tolerance: int = 2) -> Optional[str]:
        """
        특정 페이지의 섹션 힌트 조회 (±tolerance 페이지 범위)

        Args:
            page: 조회할 페이지
            tolerance: 앞뒤 페이지 범위

        Returns:
            "pre_body", "post_body", "chapter", None
        """
        for page_offset in range(-tolerance, tolerance + 1):
            check_page = page + page_offset
            if check_page in self.footer_data:
                section_name = self.footer_data[check_page].get("section_name")
                if section_name:
                    section_lower = section_name.lower()

                    # Pre Body 체크
                    for keyword in self.PRE_BODY_KEYWORDS:
                        if keyword.lower() in section_lower:
                            return "pre_body"

                    # Post Body 체크
                    for keyword in self.POST_BODY_KEYWORDS:
                        if keyword.lower() in section_lower:
                            return "post_body"

                    # Chapter 체크
                    for keyword in self.CHAPTER_KEYWORDS:
                        if keyword.lower() in section_lower:
                            return "chapter"

        return None

    def get_pre_body_range(self) -> Optional[tuple]:
        """Pre Body 페이지 범위 추정"""
        pre_pages = self.section_hints.get("pre_body", [])
        if pre_pages:
            return (min(pre_pages), max(pre_pages))
        return None

    def get_post_body_start(self) -> Optional[int]:
        """Post Body 시작 페이지 추정"""
        post_pages = self.section_hints.get("post_body", [])
        if post_pages:
            return min(post_pages)
        return None
