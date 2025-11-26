"""
소제목 계층 구조 파악 모듈

챕터 내부의 섹션, 소제목 계층을 분석합니다.
"""

import re
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class HierarchyBuilder:
    """계층 구조 분석 클래스"""

    # 섹션 번호 패턴
    SECTION_PATTERNS = {
        "decimal_1": (re.compile(r"^(\d+\.\d+)\s+(.+)"), 1),  # 1.1 제목
        "decimal_2": (re.compile(r"^(\d+\.\d+\.\d+)\s+(.+)"), 2),  # 1.1.1 제목
        "korean_list": (re.compile(r"^([가-하])\.\s+(.+)"), 1),  # 가. 제목
        "paren_number": (re.compile(r"^\((\d+)\)\s+(.+)"), 2),  # (1) 제목
    }

    # 폰트 크기 기준
    NORMAL_FONT_SIZE = 12
    SECTION_FONT_THRESHOLD = 14

    def __init__(self):
        """계층 분석기 초기화"""
        pass

    def build_hierarchy(
        self, parsed_data: Dict[str, Any], chapters: List[Dict]
    ) -> List[Dict]:
        """
        챕터별 계층 구조 생성

        Args:
            parsed_data: PDF 파싱 결과
            chapters: 탐지된 챕터 목록

        Returns:
            챕터 목록 (각 챕터에 sections 추가)
        """
        logger.info(f"🔍 Building hierarchy for {len(chapters)} chapters...")

        pages = parsed_data.get("pages", [])

        for chapter in chapters:
            start = chapter["start_page"]
            end = chapter["end_page"]

            # 챕터 페이지 추출
            chapter_pages = [p for p in pages if start <= p["page_number"] <= end]

            # 섹션 탐지
            sections = self._detect_sections(chapter_pages)
            chapter["sections"] = sections

            logger.info(
                f"  Chapter {chapter['number']}: {len(sections)} sections "
                f"(pages {start}-{end})"
            )

        logger.info(f"✅ Hierarchy built")
        return chapters

    def _detect_sections(self, chapter_pages: List[Dict]) -> List[Dict]:
        """
        챕터 내 섹션 탐지
        """
        sections = []

        for page in chapter_pages:
            elements = page.get("elements", [])

            for elem in elements:
                text = elem.get("text", "").strip()
                if not text or len(text) < 3:
                    continue

                # 패턴 매칭
                for pattern_name, (pattern, level) in self.SECTION_PATTERNS.items():
                    match = pattern.match(text)
                    if match:
                        groups = match.groups()
                        section_number = groups[0]
                        section_title = groups[1].strip() if len(groups) > 1 else text

                        # 폰트 크기 확인
                        font_size = elem.get("font_size", self.NORMAL_FONT_SIZE)
                        is_prominent = font_size >= self.SECTION_FONT_THRESHOLD

                        sections.append(
                            {
                                "id": f"s{section_number}".replace(".", "_"),
                                "number": section_number,
                                "title": text,
                                "level": level,
                                "page": page["page_number"],
                                "font_size": font_size,
                                "is_prominent": is_prominent,
                            }
                        )
                        break

        return sections
