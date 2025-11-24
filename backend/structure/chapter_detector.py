"""
챕터 탐지 모듈

페이지 상단 요소 분석 및 정규식 패턴 매칭으로 챕터를 탐지합니다.
"""
import logging
import re
from typing import Dict, Any, List, Optional
from backend.config.constants import CHAPTER_PATTERNS

logger = logging.getLogger(__name__)


class ChapterDetector:
    """챕터 탐지 클래스"""

    def __init__(self):
        """초기화"""
        # 정규식 패턴 컴파일
        self.patterns = [re.compile(pattern) for pattern in CHAPTER_PATTERNS]

    def detect_chapters(
        self, parsed_data: Dict[str, Any], main_pages: List[int]
    ) -> List[Dict[str, Any]]:
        """
        챕터 탐지

        Args:
            parsed_data: PDFParser.parse_pdf() 결과
            main_pages: 본문 페이지 번호 리스트

        Returns:
            [
                {
                    "id": "ch1",
                    "number": 1,
                    "title": "제1장 제목",
                    "start_page": 4,
                    "end_page": 32
                },
                ...
            ]
        """
        logger.info("[INFO] Detecting chapters...")

        pages = parsed_data.get("pages", [])
        if not pages:
            logger.warning("[WARNING] No pages found in parsed_data")
            return []

        # 본문 페이지만 필터링
        main_pages_set = set(main_pages)
        main_pages_data = [
            p for p in pages if p.get("page_number") in main_pages_set
        ]

        # 챕터 후보 탐지
        chapter_candidates = self._detect_chapter_candidates(main_pages_data)

        if not chapter_candidates:
            logger.info("[INFO] No chapters detected")
            return []

        # 챕터 범위 계산
        chapters = self._calculate_chapter_ranges(
            chapter_candidates, main_pages_data
        )

        logger.info(f"[INFO] Detected {len(chapters)} chapters")
        for ch in chapters:
            logger.info(
                f"  Chapter {ch['number']}: '{ch['title']}' "
                f"(pages {ch['start_page']}-{ch['end_page']})"
            )

        return chapters

    def _detect_chapter_candidates(
        self, pages: List[Dict]
    ) -> List[Dict[str, Any]]:
        """
        챕터 후보 탐지

        페이지 상단 요소(y0 작음, font_size 큼)에서 챕터 패턴 매칭

        Returns:
            [
                {"page_number": 4, "title": "제1장 제목", "number": 1},
                ...
            ]
        """
        candidates = []

        for page in pages:
            page_num = page.get("page_number", 0)
            elements = page.get("elements", [])

            if not elements:
                continue

            # 페이지 상단 요소 찾기 (y0가 작은 순서대로)
            top_elements = sorted(
                elements,
                key=lambda e: e.get("bbox", {}).get("y0", 1.0),
            )[:5]  # 상위 5개 요소만 검사

            for elem in top_elements:
                text = elem.get("text", "").strip()
                if not text:
                    continue

                # 폰트 크기 확인 (큰 폰트 우선)
                font_size = elem.get("font_size", 12)
                if font_size < 14:  # 최소 14px 이상
                    continue

                # 챕터 패턴 매칭
                chapter_info = self._match_chapter_pattern(text)
                if chapter_info:
                    chapter_info["page_number"] = page_num
                    chapter_info["title"] = text
                    candidates.append(chapter_info)
                    break  # 한 페이지당 하나의 챕터만

        # 중복 제거 (같은 페이지에 여러 후보가 있는 경우)
        seen_pages = set()
        unique_candidates = []
        for candidate in candidates:
            page_num = candidate["page_number"]
            if page_num not in seen_pages:
                seen_pages.add(page_num)
                unique_candidates.append(candidate)

        # 페이지 번호 순으로 정렬
        unique_candidates.sort(key=lambda x: x["page_number"])

        logger.info(f"[INFO] Found {len(unique_candidates)} chapter candidates")
        return unique_candidates

    def _match_chapter_pattern(self, text: str) -> Optional[Dict[str, Any]]:
        """
        텍스트에서 챕터 패턴 매칭

        Args:
            text: 검사할 텍스트

        Returns:
            {"number": 1, ...} 또는 None
        """
        for pattern in self.patterns:
            match = pattern.search(text)
            if match:
                # 숫자 추출
                number = self._extract_chapter_number(text, match)
                return {"number": number}
        return None

    def _extract_chapter_number(self, text: str, match: re.Match) -> Optional[int]:
        """
        챕터 번호 추출

        Args:
            text: 전체 텍스트
            match: 정규식 매치 객체

        Returns:
            챕터 번호 또는 None
        """
        # 패턴 1: "제1장" -> 1
        match1 = re.search(r"제\s*(\d+)\s*장", text)
        if match1:
            return int(match1.group(1))

        # 패턴 2: "CHAPTER 1" -> 1
        match2 = re.search(r"CHAPTER\s+(\d+)", text, re.IGNORECASE)
        if match2:
            return int(match2.group(1))

        # 패턴 3: "1. 제목" -> 1
        match3 = re.search(r"^(\d+)\.\s+", text)
        if match3:
            return int(match3.group(1))

        return None

    def _calculate_chapter_ranges(
        self, candidates: List[Dict], pages: List[Dict]
    ) -> List[Dict[str, Any]]:
        """
        챕터 범위 계산

        각 챕터의 start_page와 end_page를 계산합니다.
        end_page는 다음 챕터의 start_page - 1입니다.

        Args:
            candidates: 챕터 후보 리스트
            pages: 페이지 리스트

        Returns:
            챕터 리스트 (start_page, end_page 포함)
        """
        if not candidates:
            return []

        chapters = []
        total_pages = max([p.get("page_number", 0) for p in pages]) if pages else 0

        for i, candidate in enumerate(candidates):
            start_page = candidate["page_number"]
            title = candidate["title"]
            number = candidate.get("number", i + 1)

            # end_page 계산
            if i < len(candidates) - 1:
                # 다음 챕터의 start_page - 1
                end_page = candidates[i + 1]["page_number"] - 1
            else:
                # 마지막 챕터는 본문 끝까지
                end_page = total_pages

            chapters.append(
                {
                    "id": f"ch{number}",
                    "number": number,
                    "title": title,
                    "start_page": start_page,
                    "end_page": end_page,
                }
            )

        return chapters

