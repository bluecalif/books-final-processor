"""
챕터 경계 탐지 모듈 (Footer 기반, 개선 버전)

Footer의 구조 판별자에서 챕터 패턴을 인식하여 챕터 경계를 탐지합니다.
챕터 표시 판별자와 페이지 번호를 구분하며, 연속적인 챕터 번호만 필터링합니다.
"""

import re
import logging
from typing import Dict, Any, List, Optional, Set

logger = logging.getLogger(__name__)


class ChapterDetector:
    """챕터 경계 탐지 클래스 (Footer 기반, 개선 버전)"""

    def __init__(self):
        """챕터 탐지기 초기화"""
        # 챕터 패턴 (챕터 표시 판별자 인식용)
        self.chapter_patterns = [
            re.compile(r"제\s*(\d+)\s*[장강부]"),  # 제1장, 제1강, 제1부
            re.compile(r"CHAPTER\s*(\d+)", re.IGNORECASE),  # Chapter 1, Chapter1
            re.compile(r"Part\s*(\d+)", re.IGNORECASE),  # Part 1, Part1
            re.compile(r"^(\d+)\s*[장강부]"),  # 1장, 1강
            re.compile(r"^(\d+)\.\s*[가-힣]"),  # 1. 제목, 1.제목
            re.compile(r"^(\d+)[_\-\s]+[가-힣]"),  # 1_제목, 1-제목, 1 제목
            re.compile(r"^(0?\d+)[_\-\s]+[가-힣]"),  # 01 바빌론, 1_제목 (30개도시로읽는세계사)
            re.compile(r"^(\d+)_\s*[가-힣A-Z0-9]"),  # 1_3D, 1_제목 (3D프린터의모든것 - 영문/숫자 허용)
        ]
        
        # 중요 페이지 범위 (GT 기준 ±1~2 페이지)
        # 챕터 5: 167 (165-169), 챕터 6: 195 (193-197), 챕터 7: 224 (222-226)
        self.important_page_ranges = [(165, 169), (193, 197), (222, 226)]
    
    def _is_important_page(self, page_num: int) -> bool:
        """중요 페이지인지 확인 (GT 기준 ±1~2 페이지)"""
        return any(start <= page_num <= end for start, end in self.important_page_ranges)

    def detect_chapters(
        self, parsed_data: Dict[str, Any], main_pages: List[int]
    ) -> List[Dict[str, Any]]:
        """
        챕터 경계 탐지 (Footer 기반, 개선 버전)

        Args:
            parsed_data: PDF 파싱 결과
            main_pages: 본문 페이지 목록

        Returns:
            [
                {
                    "id": "ch1",
                    "number": 1,
                    "title": "제1장",
                    "start_page": 36,
                    "end_page": 65,
                    "score": 100.0,
                    "detection_method": "footer_pattern"
                },
                ...
            ]
        """
        logger.info(
            f"[INFO] Detecting chapters in {len(main_pages)} main pages (Footer 기반, 개선 버전)..."
        )

        pages = parsed_data.get("pages", [])

        # 본문 영역의 홀수 페이지만 필터링
        main_odd_pages = [
            p
            for p in pages
            if p["page_number"] in main_pages and p["page_number"] % 2 == 1
        ]

        # 1. 개선된 챕터 번호 추출 (패턴 기반)
        page_chapter_numbers = self._extract_chapter_numbers_improved(main_odd_pages)

        # 2. 챕터 번호 필터링 (연속성 검증)
        page_chapter_numbers = self._filter_valid_chapter_numbers(
            page_chapter_numbers
        )

        # 3. 챕터 경계 탐지 (숫자 변경 지점)
        chapters = self._detect_chapter_boundaries(page_chapter_numbers, main_pages)

        # 4. 챕터 제목 추출 (페이지 상단 요소에서)
        chapters = self._extract_chapter_titles(chapters, pages)

        logger.info(f"[INFO] Detected {len(chapters)} chapters (Footer 기반, 개선 버전)")
        for ch in chapters:
            logger.info(
                f"[INFO] Chapter {ch['number']}: '{ch['title']}' "
                f"(pages {ch['start_page']}-{ch['end_page']})"
            )

        return chapters

    def _extract_chapter_numbers_improved(
        self, pages: List[Dict]
    ) -> Dict[int, Optional[int]]:
        """
        개선된 챕터 번호 추출 (패턴 기반)

        로직:
        1. 각 홀수 페이지의 Footer에서 챕터 표시 판별자만 추출
        2. 챕터 패턴에서 숫자 추출
        3. 페이지 번호는 무시

        Args:
            pages: 본문 영역의 홀수 페이지 리스트

        Returns:
            {page_number: chapter_number or None}
        """
        page_chapter_numbers = {}

        for page in pages:
            page_num = page.get("page_number", 0)
            is_important = self._is_important_page(page_num)

            # Footer 영역 요소 추출
            footer_elements = self._get_footer_elements(page)

            # 중요 페이지는 상세 로그
            if is_important:
                logger.info(f"[INFO] 중요 페이지 분석: Page {page_num} (챕터 5/6/7 시작 범위)")
                logger.info(f"  - Footer 요소 개수: {len(footer_elements)}")

            # 각 Footer 요소 분류 및 로깅
            chapter_markers = []
            for idx, elem in enumerate(footer_elements):
                text = elem.get("text", "").strip()
                bbox = elem.get("bbox", {})
                x0 = bbox.get("x0", 0.5)
                classification = self._classify_footer_element(elem)

                if classification == "chapter_marker":
                    chapter_markers.append(elem)

                # 중요 페이지는 상세 로그, 일반 페이지는 DEBUG
                if is_important:
                    logger.info(f"  - 요소 #{idx+1}: text='{text[:50]}', x0={x0:.3f}, 분류={classification}")
                else:
                    logger.debug(f"[DEBUG] Page {page_num} 요소 #{idx+1}: text='{text[:50]}', 분류={classification}")

            # 챕터 번호 추출
            chapter_number = None
            for marker in chapter_markers:
                text = marker.get("text", "").strip()
                number = self._extract_chapter_number_from_pattern(text)
                if number:
                    chapter_number = number
                    if is_important:
                        logger.info(f"  - 챕터 표시 발견: text='{text}', 추출된 번호={number}")
                    else:
                        logger.debug(
                            f"[DEBUG] Page {page_num}: chapter_number={chapter_number}, "
                            f"text='{text[:50]}...'"
                        )
                    break

            page_chapter_numbers[page_num] = chapter_number

            # 중요 페이지는 최종 결과도 INFO 레벨로
            if is_important:
                logger.info(f"  - 최종 챕터 번호: {chapter_number}")
            elif chapter_number is None:
                logger.debug(
                    f"[DEBUG] Page {page_num}: no chapter number found in footer"
                )

        # 전체 요약
        extracted_count = len([n for n in page_chapter_numbers.values() if n])
        logger.info(
            f"[INFO] 추출된 챕터 번호: {extracted_count}개 페이지"
        )

        # 중요 페이지 범위의 최종 결과 요약
        for start, end in self.important_page_ranges:
            pages_in_range = [p for p in range(start, end + 1) if p in page_chapter_numbers]
            numbers_in_range = [page_chapter_numbers[p] for p in pages_in_range if page_chapter_numbers[p] is not None]
            if numbers_in_range:
                logger.info(f"[INFO] 중요 페이지 범위 {start}-{end}: 챕터 번호 {numbers_in_range}")
            else:
                logger.warning(f"[WARNING] 중요 페이지 범위 {start}-{end}: 챕터 번호 없음")

        return page_chapter_numbers

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

    def _extract_chapter_number_from_pattern(self, text: str) -> Optional[int]:
        """
        챕터 패턴에서 숫자 추출

        예: "제1장" -> 1, "Chapter 2" -> 2

        Args:
            text: 텍스트

        Returns:
            추출된 챕터 번호 또는 None
        """
        for pattern in self.chapter_patterns:
            match = pattern.search(text)
            if match:
                # 그룹에서 숫자 추출
                groups = match.groups()
                if groups:
                    try:
                        number = int(groups[0])
                        if number >= 1:
                            logger.debug(f"[DEBUG] 챕터 패턴 매칭: text='{text[:50]}', 패턴={pattern.pattern}, 추출된 번호={number}")
                            return number
                    except (ValueError, IndexError):
                        continue

        logger.debug(f"[DEBUG] 챕터 패턴 매칭 실패: text='{text[:50]}'")
        return None

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

    def _filter_valid_chapter_numbers(
        self, page_chapter_numbers: Dict[int, Optional[int]]
    ) -> Dict[int, Optional[int]]:
        """
        유효한 챕터 번호만 필터링

        기준:
        1. 연속적인 번호 (1, 2, 3, 4, ...)
        2. 합리적인 범위 (1-100)
        3. 비연속/비정상 번호 제외

        Args:
            page_chapter_numbers: {page_number: chapter_number or None}

        Returns:
            필터링된 {page_number: chapter_number or None}
        """
        # 모든 챕터 번호 수집
        all_numbers = [n for n in page_chapter_numbers.values() if n is not None]

        if not all_numbers:
            logger.info("[INFO] 연속성 필터링: 추출된 챕터 번호 없음")
            return page_chapter_numbers

        # 필터링 전 상태
        logger.info(f"[INFO] 연속성 필터링 시작:")
        logger.info(f"  - 필터링 전 챕터 번호: {sorted(set(all_numbers))}")
        logger.info(f"  - 페이지별 챕터 번호: {[(p, n) for p, n in sorted(page_chapter_numbers.items()) if n is not None]}")

        # 가장 긴 연속 시퀀스 찾기
        valid_numbers = self._find_continuous_sequence(all_numbers)

        # 필터링 후 상태
        excluded_numbers = set(all_numbers) - valid_numbers
        logger.info(f"  - 필터링 후 유효한 챕터 번호: {sorted(valid_numbers)}")
        if excluded_numbers:
            logger.info(f"  - 제외된 챕터 번호: {sorted(excluded_numbers)}")

        # 중요 페이지 범위의 챕터 번호가 제외되었는지 확인
        for start, end in self.important_page_ranges:
            pages_in_range = [p for p in range(start, end + 1) if p in page_chapter_numbers]
            numbers_in_range = [page_chapter_numbers[p] for p in pages_in_range if page_chapter_numbers[p] is not None]
            excluded_in_range = [n for n in numbers_in_range if n not in valid_numbers]
            if excluded_in_range:
                logger.warning(f"[WARNING] 중요 페이지 범위 {start}-{end}: 제외된 챕터 번호 {excluded_in_range}")
            elif numbers_in_range:
                logger.info(f"[INFO] 중요 페이지 범위 {start}-{end}: 유효한 챕터 번호 {numbers_in_range}")

        # 유효한 번호만 유지
        filtered = {}
        for page_num, chapter_num in page_chapter_numbers.items():
            if chapter_num in valid_numbers:
                filtered[page_num] = chapter_num
            else:
                filtered[page_num] = None
                if chapter_num is not None:
                    logger.debug(
                        f"[DEBUG] Page {page_num}: chapter {chapter_num} filtered out (not in continuous sequence)"
                    )

        return filtered

    def _find_continuous_sequence(self, numbers: List[int]) -> Set[int]:
        """
        연속적인 번호 시퀀스 찾기

        예: [1, 2, 3, 4, 5, 6, 7, 100, 200] -> {1, 2, 3, 4, 5, 6, 7}

        Args:
            numbers: 챕터 번호 리스트

        Returns:
            연속적인 번호 집합
        """
        unique_numbers = sorted(set(numbers))

        if not unique_numbers:
            return set()

        logger.debug(f"[DEBUG] 연속 시퀀스 탐색 시작: {unique_numbers}")

        # 가장 긴 연속 시퀀스 찾기
        longest_sequence = []
        current_sequence = [unique_numbers[0]]

        for i in range(1, len(unique_numbers)):
            if unique_numbers[i] == unique_numbers[i - 1] + 1:
                current_sequence.append(unique_numbers[i])
            else:
                # 시퀀스 종료
                if len(current_sequence) > len(longest_sequence):
                    longest_sequence = current_sequence
                    logger.debug(f"  - 새로운 최장 시퀀스 발견: {longest_sequence} (길이: {len(longest_sequence)})")
                current_sequence = [unique_numbers[i]]

        # 마지막 시퀀스 확인
        if len(current_sequence) > len(longest_sequence):
            longest_sequence = current_sequence
            logger.debug(f"  - 최종 최장 시퀀스: {longest_sequence} (길이: {len(longest_sequence)})")

        logger.info(f"[INFO] 최종 선택된 연속 시퀀스: {longest_sequence} (길이: {len(longest_sequence)})")

        return set(longest_sequence)

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

    def _detect_chapter_boundaries(
        self, page_chapter_numbers: Dict[int, Optional[int]], main_pages: List[int]
    ) -> List[Dict[str, Any]]:
        """
        챕터 경계 탐지 (숫자 변경 지점)

        Args:
            page_chapter_numbers: {page_number: chapter_number or None}
            main_pages: 본문 페이지 목록

        Returns:
            챕터 리스트
        """
        chapters = []
        current_chapter = None
        current_start_page = None

        # 페이지 번호 순서대로 정렬
        sorted_pages = sorted(page_chapter_numbers.keys())

        for page_num in sorted_pages:
            chapter_number = page_chapter_numbers[page_num]

            if chapter_number is None:
                # 숫자가 없으면 현재 챕터에 포함
                continue

            if current_chapter is None or chapter_number != current_chapter:
                # 새로운 챕터 시작
                if current_chapter is not None:
                    # 이전 챕터 종료
                    chapters.append(
                        {
                            "id": f"ch{current_chapter}",
                            "number": current_chapter,
                            "title": f"제{current_chapter}장",  # 임시 제목, 나중에 추출
                            "start_page": current_start_page,
                            "end_page": page_num - 1,  # 다음 챕터 시작 전까지
                            "score": 100.0,  # Footer 기반이므로 높은 신뢰도
                            "detection_method": "footer_pattern",
                        }
                    )

                # 새 챕터 시작
                current_chapter = chapter_number
                current_start_page = page_num

        # 마지막 챕터 종료
        if current_chapter is not None:
            chapters.append(
                {
                    "id": f"ch{current_chapter}",
                    "number": current_chapter,
                    "title": f"제{current_chapter}장",  # 임시 제목, 나중에 추출
                    "start_page": current_start_page,
                    "end_page": main_pages[-1] if main_pages else current_start_page,
                    "score": 100.0,
                    "detection_method": "footer_pattern",
                }
            )

        # 짝수 페이지도 포함하여 경계 조정
        chapters = self._adjust_boundaries_for_even_pages(chapters, main_pages)

        return chapters

    def _adjust_boundaries_for_even_pages(
        self, chapters: List[Dict], main_pages: List[int]
    ) -> List[Dict]:
        """
        짝수 페이지(우측)도 포함하여 경계 조정

        홀수 페이지(좌측)의 챕터 구분을 기준으로, 짝수 페이지(우측)도 동일한 챕터로 간주합니다.

        Args:
            chapters: 챕터 리스트 (홀수 페이지 기준)
            main_pages: 본문 페이지 목록

        Returns:
            경계 조정된 챕터 리스트
        """
        adjusted = []

        for i, ch in enumerate(chapters):
            start_page = ch["start_page"]
            end_page = ch["end_page"]

            # 다음 챕터 시작 페이지 확인
            if i < len(chapters) - 1:
                next_start = chapters[i + 1]["start_page"]
                # 짝수 페이지까지 포함
                if next_start % 2 == 1:
                    # 다음 챕터가 홀수 페이지에서 시작하면, 현재 챕터는 그 전 짝수 페이지까지
                    end_page = next_start - 1
                else:
                    # 다음 챕터가 짝수 페이지에서 시작하면, 현재 챕터는 그 전 홀수 페이지까지
                    end_page = next_start - 2
            else:
                # 마지막 챕터: 본문 끝까지
                end_page = main_pages[-1] if main_pages else start_page

            adjusted.append(
                {
                    **ch,
                    "start_page": start_page,
                    "end_page": end_page,
                }
            )

        return adjusted

    def _extract_chapter_titles(
        self, chapters: List[Dict], all_pages: List[Dict]
    ) -> List[Dict]:
        """
        챕터 제목 추출 (페이지 상단 요소에서)

        Args:
            chapters: 챕터 리스트
            all_pages: 전체 페이지 리스트

        Returns:
            제목이 추가된 챕터 리스트
        """
        for ch in chapters:
            start_page = ch["start_page"]

            # 시작 페이지 찾기
            page_obj = None
            for p in all_pages:
                if p.get("page_number") == start_page:
                    page_obj = p
                    break

            if not page_obj:
                continue

            # 페이지 상단 요소에서 제목 추출
            title = self._extract_title_from_page_top(page_obj)
            if title:
                ch["title"] = title
                logger.debug(f"[DEBUG] Chapter {ch['number']} title: '{title}'")

        return chapters

    def _extract_title_from_page_top(self, page: Dict) -> Optional[str]:
        """
        페이지 상단 요소에서 챕터 제목 추출

        Args:
            page: 페이지 딕셔너리

        Returns:
            추출된 제목 또는 None
        """
        elements = page.get("elements", [])
        if not elements:
            return None

        # 페이지 상단 요소 (y0가 작은 요소)
        top_elements = sorted(
            elements, key=lambda e: e.get("bbox", {}).get("y0", 1.0)
        )[:3]  # 상위 3개 요소

        for elem in top_elements:
            text = elem.get("text", "").strip()
            if text:
                # 챕터 패턴 확인 (제N장, Chapter N 등)
                if re.search(
                    r"(제\s*\d+\s*장|CHAPTER\s+\d+|Part\s+\d+)", text, re.IGNORECASE
                ):
                    return text[:100]  # 최대 100자
                # 숫자로 시작하는 제목 (1. 제목, 1장 등)
                if re.match(r"^\d+", text):
                    return text[:100]

        # 패턴이 없으면 상단 첫 번째 요소의 텍스트 사용
        if top_elements:
            text = top_elements[0].get("text", "").strip()
            if text:
                return text[:100]

        return None
