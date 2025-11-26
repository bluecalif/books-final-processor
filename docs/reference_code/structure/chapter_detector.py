"""
챕터 경계 탐지 모듈

레이아웃 신호와 텍스트 패턴을 결합하여 챕터 경계를 탐지합니다.
"""

import re
import logging
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)


class ChapterDetector:
    """챕터 경계 탐지 클래스"""

    # 챕터 제목 패턴 (확장됨)
    CHAPTER_PATTERNS = {
        # 한글 패턴
        "korean_chapter_full": (re.compile(r"^제\s*(\d+)\s*장"), 50),  # 제1장
        "korean_chapter_short": (re.compile(r"^(\d+)\s*장$"), 50),  # 1장, 2장 (단독)
        "korean_part": (re.compile(r"^제\s*(\d+)\s*부"), 55),  # 제1부 (상위 계층)
        # 영어 패턴
        "english_chapter": (re.compile(r"^CHAPTER\s+(\d+)", re.IGNORECASE), 50),
        "english_part": (re.compile(r"^Part\s+(\d+)", re.IGNORECASE), 55),
        # 번호 패턴
        "numbered_title": (
            re.compile(r"^(\d+)\.\s+([가-힣a-zA-Z].{3,})"),
            35,
        ),  # 1. 제목
    }

    # 레이아웃 임계값
    MIN_CHAPTER_SPACING = 3  # 챕터 간 최소 페이지 간격
    LARGE_FONT_THRESHOLD = 16  # 큰 폰트 기준 (16px 이상)
    SCORE_THRESHOLD = 55  # 챕터 확정 점수 (낮춤)

    def __init__(self):
        """챕터 탐지기 초기화"""
        pass

    def detect_chapters(
        self, parsed_data: Dict[str, Any], main_pages: List[int]
    ) -> List[Dict[str, Any]]:
        """
        챕터 경계 탐지

        Args:
            parsed_data: PDF 파싱 결과
            main_pages: 본문 페이지 목록

        Returns:
            [
                {
                    "id": "ch1",
                    "number": 1,
                    "title": "제1장 의식의 본질",
                    "start_page": 4,
                    "end_page": 25,
                    "score": 85.0,
                    "detection_method": "korean_chapter"
                },
                ...
            ]
        """
        logger.info(f"🔍 Detecting chapters in {len(main_pages)} main pages...")

        pages = parsed_data.get("pages", [])

        # Main 페이지만 필터링
        main_page_objects = [p for p in pages if p["page_number"] in main_pages]

        # 1. 챕터 제목 후보 탐지
        candidates = []
        for page in main_page_objects:
            page_candidates = self._find_chapter_candidates(page)
            candidates.extend(page_candidates)

        logger.info(f"  Found {len(candidates)} chapter title candidates")

        # 2. 점수 기반 필터링
        chapters = []
        for candidate in candidates:
            if candidate["score"] >= self.SCORE_THRESHOLD:
                chapters.append(candidate)
                logger.info(
                    f"    ✓ Chapter {candidate['number']}: '{candidate['title']}' "
                    f"(page {candidate['start_page']}, score: {candidate['score']:.1f})"
                )

        # 3. 품질 검증 및 정제
        chapters = self._validate_and_refine_chapters(chapters, main_pages)

        logger.info(f"✅ Detected {len(chapters)} chapters")
        return chapters

    def _find_chapter_candidates(self, page: Dict) -> List[Dict[str, Any]]:
        """
        페이지에서 챕터 제목 후보 찾기
        """
        candidates = []
        elements = page.get("elements", [])

        for elem in elements:
            text = elem.get("text", "").strip()
            if not text:  # 빈 문자열만 제외 (한글 챕터 "1장"=2글자 허용)
                continue

            # 텍스트 패턴 매칭
            for pattern_name, (pattern, base_score) in self.CHAPTER_PATTERNS.items():
                match = pattern.match(text)
                if match:
                    # 점수 계산
                    score = self._calculate_chapter_score(
                        elem, pattern_name, base_score
                    )

                    # 챕터 번호 및 제목 추출
                    groups = match.groups()
                    chapter_number = int(groups[0]) if groups[0].isdigit() else 0
                    chapter_title = groups[1].strip() if len(groups) > 1 else text

                    candidates.append(
                        {
                            "id": f"ch{chapter_number}",
                            "number": chapter_number,
                            "title": text,
                            "start_page": page["page_number"],
                            "end_page": None,  # 나중에 설정
                            "score": score,
                            "detection_method": pattern_name,
                            "element": elem,
                        }
                    )
                    break

        return candidates

    def _calculate_chapter_score(
        self, elem: Dict, pattern_name: str, base_score: float
    ) -> float:
        """
        챕터 제목 후보의 점수 계산

        점수 구성:
        - 텍스트 패턴 점수: 35-55점 (base_score)
        - 레이아웃 점수: 0-45점
          - 큰 폰트 크기: +25점 (강화)
          - 페이지 상단 배치: +20점 (강화)
          - 카테고리가 heading: +15점
          - 짧은 텍스트: +10점 (챕터 제목은 짧음)
        """
        score = base_score

        # 레이아웃 점수
        font_size = elem.get("font_size", 12)
        bbox = elem.get("bbox", {})
        category = elem.get("category", "")
        text = elem.get("text", "").strip()
        y0 = bbox.get("y0", 0.5)

        # 1. 큰 폰트 (강화)
        if font_size >= 20:
            score += 30  # 매우 큰 폰트
        elif font_size >= self.LARGE_FONT_THRESHOLD:
            score += 20  # 큰 폰트

        # 2. 페이지 상단 배치 (강화)
        if y0 < 0.1:
            score += 25  # 맨 위
        elif y0 < 0.2:
            score += 20  # 상단

        # 3. Heading 카테고리
        if category in ["heading", "heading1", "title"]:
            score += 15

        # 4. 짧은 텍스트 (챕터 제목은 대부분 짧음)
        if len(text) <= 20:  # "1장", "제1장 제목" 등
            score += 10

        return min(100.0, score)

    def _validate_and_refine_chapters(
        self, chapters: List[Dict], main_pages: List[int]
    ) -> List[Dict]:
        """
        챕터 목록 검증 및 정제

        - 챕터 번호 순서대로 정렬
        - 중복 제거
        - 최소 간격 확인
        - end_page 설정
        """
        if not chapters:
            return []

        # 1. 챕터 번호 순서대로 정렬
        chapters = sorted(chapters, key=lambda x: x["number"])

        # 2. 중복 제거 (같은 번호의 챕터는 점수가 높은 것만)
        unique_chapters = {}
        for ch in chapters:
            ch_num = ch["number"]
            if (
                ch_num not in unique_chapters
                or ch["score"] > unique_chapters[ch_num]["score"]
            ):
                unique_chapters[ch_num] = ch

        chapters = list(unique_chapters.values())
        chapters = sorted(chapters, key=lambda x: x["number"])

        # 3. 최소 간격 확인
        filtered = []
        for i, ch in enumerate(chapters):
            # 이전 챕터와의 간격 확인
            if (
                filtered
                and ch["start_page"] - filtered[-1]["start_page"]
                < self.MIN_CHAPTER_SPACING
            ):
                logger.warning(
                    f"  ⚠️ Skipping chapter {ch['number']} - too close to previous chapter "
                    f"({ch['start_page'] - filtered[-1]['start_page']} pages apart)"
                )
                continue

            filtered.append(ch)

        # 4. end_page 설정
        for i, ch in enumerate(filtered):
            if i < len(filtered) - 1:
                ch["end_page"] = filtered[i + 1]["start_page"] - 1
            else:
                ch["end_page"] = main_pages[-1] if main_pages else ch["start_page"]

        return filtered
