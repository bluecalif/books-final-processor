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
    ) -> Dict[int, tuple]:
        """
        개선된 챕터 번호 추출 (단순화된 로직)

        로직:
        1. 각 홀수 페이지의 Footer에서 챕터 표시 판별자만 추출
        2. 텍스트 시작부터 첫 번째 숫자 추출
        3. 페이지 번호는 무시

        Args:
            pages: 본문 영역의 홀수 페이지 리스트

        Returns:
            {page_number: (chapter_number or None, chapter_marker_text or None)}
        """
        page_chapter_numbers = {}

        # 12가지인생의법칙 실패한 챕터 페이지 (GT 기준 ±2 페이지)
        # 챕터 11: GT=555 (553-557) - 현재 GT 기준
        failed_chapter_ranges = [(553, 557)]  # 챕터 11만 확인
        
        for page in pages:
            page_num = page.get("page_number", 0)
            is_important = self._is_important_page(page_num)
            
            # 12가지인생의법칙 실패한 챕터 페이지 범위 확인
            is_failed_chapter_page = any(start <= page_num <= end for start, end in failed_chapter_ranges)

            # Footer 영역 요소 추출
            footer_elements = self._get_footer_elements(page)

            # 중요 페이지 또는 실패한 챕터 페이지는 상세 로그
            if is_important or is_failed_chapter_page:
                if is_failed_chapter_page:
                    logger.info(f"[INFO] ========================================")
                    logger.info(f"[INFO] 실패한 챕터 페이지 상세 분석: Page {page_num} (12가지인생의법칙 챕터 11, GT=555)")
                    logger.info(f"[INFO] ========================================")
                else:
                    logger.info(f"[INFO] 중요 페이지 분석: Page {page_num} (챕터 5/6/7 시작 범위)")
                logger.info(f"  - Footer 요소 개수: {len(footer_elements)}")

            # 각 Footer 요소 분류 및 로깅
            chapter_markers = []
            page_numbers = []
            for idx, elem in enumerate(footer_elements):
                text = elem.get("text", "").strip()
                bbox = elem.get("bbox", {})
                x0 = bbox.get("x0", 0.5)
                classification = self._classify_footer_element(elem)

                if classification == "chapter_marker":
                    chapter_markers.append(elem)
                elif classification == "page_number":
                    page_numbers.append(elem)

                # 중요 페이지 또는 실패한 챕터 페이지는 상세 로그, 일반 페이지는 DEBUG
                if is_important or is_failed_chapter_page:
                    has_digit = "숫자O" if re.search(r'\d+', text) else "숫자X"
                    has_char = "문자O" if re.search(r'[가-힣a-zA-Z]', text) else "문자X"
                    logger.info(f"  - 요소 #{idx+1}: text='{text[:80]}', x0={x0:.3f}, 분류={classification}, {has_digit}/{has_char}")
                else:
                    logger.debug(f"[DEBUG] Page {page_num} 요소 #{idx+1}: text='{text[:50]}', 분류={classification}")

            # chapter_marker와 page_number 개수 로깅
            if is_important or is_failed_chapter_page or chapter_markers:
                logger.info(f"  - Footer 요소 요약: chapter_marker={len(chapter_markers)}개, page_number={len(page_numbers)}개")

            # 챕터 번호 추출
            # 숫자와 문자가 함께 있는 chapter_marker 우선 선택
            chapter_number = None
            chapter_marker_text = None
            
            # 1. 숫자와 문자가 함께 있는 marker 우선 선택
            for marker in chapter_markers:
                text = marker.get("text", "").strip()
                # 숫자와 문자가 함께 있는지 확인
                if re.search(r'\d+', text) and re.search(r'[가-힣a-zA-Z]', text):
                    number = self._extract_chapter_number_from_text(text)
                    if number:
                        chapter_number = number
                        chapter_marker_text = text  # 제목 추출을 위해 저장
                        if is_important or is_failed_chapter_page:
                            logger.info(f"  - 챕터 표시 발견 (문자 포함): text='{text[:80]}', 추출된 번호={number}")
                        else:
                            logger.debug(
                                f"[DEBUG] Page {page_num}: chapter_number={chapter_number}, "
                                f"text='{text[:50]}...' (문자 포함)"
                            )
                        break
            
            # 2. 숫자만 있는 marker는 fallback (문자 포함 marker가 없을 때만)
            if chapter_number is None:
                for marker in chapter_markers:
                    text = marker.get("text", "").strip()
                    # 숫자만 있는 경우 (페이지 번호 제외)
                    if re.search(r'\d+', text) and not re.search(r'[가-힣a-zA-Z]', text):
                        # 페이지 번호가 아닌 경우만 (위치 확인)
                        bbox = marker.get("bbox", {})
                        x0 = bbox.get("x0", 0.5)
                        if x0 >= 0.05:  # 왼쪽 끝이 아니면
                            number = self._extract_chapter_number_from_text(text)
                            if number:
                                chapter_number = number
                                chapter_marker_text = text
                                if is_important or is_failed_chapter_page:
                                    logger.info(f"  - 챕터 표시 발견 (숫자만, fallback): text='{text[:80]}', 추출된 번호={number}")
                                else:
                                    logger.debug(
                                        f"[DEBUG] Page {page_num}: chapter_number={chapter_number}, "
                                        f"text='{text[:50]}...' (숫자만, fallback)"
                                    )
                                break

            # chapter_marker 텍스트를 저장 (나중에 제목 추출에 사용)
            page_chapter_numbers[page_num] = (chapter_number, chapter_marker_text)

            # 중요 페이지 또는 실패한 챕터 페이지는 최종 결과도 INFO 레벨로
            if is_important or is_failed_chapter_page:
                if is_failed_chapter_page:
                    logger.info(f"[INFO] ========================================")
                    if chapter_number is None:
                        logger.warning(f"  - [경고] 최종 챕터 번호: None (챕터 마커를 찾지 못함)")
                        logger.warning(f"  - [원인 분석] Page {page_num}에서 챕터 11을 찾지 못함")
                    else:
                        logger.info(f"  - 최종 챕터 번호: {chapter_number}")
                        if chapter_number == 11:
                            logger.info(f"  - [성공] 챕터 11 발견! Page {page_num}")
                        else:
                            logger.warning(f"  - [경고] 챕터 11이 아님 (발견된 번호: {chapter_number})")
                    logger.info(f"[INFO] ========================================")
                else:
                    if chapter_number is None:
                        logger.warning(f"  - [경고] 최종 챕터 번호: None (챕터 마커를 찾지 못함)")
                    else:
                        logger.info(f"  - 최종 챕터 번호: {chapter_number}")
            elif chapter_number is None:
                logger.debug(
                    f"[DEBUG] Page {page_num}: no chapter number found in footer"
                )

        # 전체 요약
        extracted_count = len([n for n, _ in page_chapter_numbers.values() if n is not None])
        logger.info(
            f"[INFO] 추출된 챕터 번호: {extracted_count}개 페이지"
        )

        # 중요 페이지 범위의 최종 결과 요약
        for start, end in self.important_page_ranges:
            pages_in_range = [p for p in range(start, end + 1) if p in page_chapter_numbers]
            numbers_in_range = [page_chapter_numbers[p][0] for p in pages_in_range if page_chapter_numbers[p][0] is not None]
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

        # 1. 페이지 번호 확인 (최우선: 숫자만 있고 왼쪽 끝에 위치)
        if x0 < 0.05:  # 왼쪽 끝 (페이지 번호 영역)
            if self._is_page_number(text):
                return "page_number"

        # 2. 챕터 패턴 확인 (숫자 포함 + 문자 포함)
        # 숫자만 있는 것은 제외 (페이지 번호로 이미 처리됨)
        if self._is_chapter_pattern(text) and not self._is_page_number(text):
            # 숫자와 문자가 함께 있는 경우만 chapter_marker
            if re.search(r'[가-힣a-zA-Z]', text):  # 한글 또는 영문 포함
                return "chapter_marker"

        # 3. 중앙 영역 (챕터 제목 영역)
        if 0.05 < x0 < 0.5:  # 중앙
            if self._has_chapter_keywords(text):
                return "chapter_marker"

        # 4. 기타
        return "other"

    def _is_chapter_pattern(self, text: str) -> bool:
        """
        챕터 패턴 확인 (단순화: 숫자 포함 여부만 확인)

        텍스트에 숫자가 포함되어 있으면 챕터 마커로 간주합니다.
        """
        # 텍스트에 숫자가 포함되어 있는지 확인
        return bool(re.search(r'\d+', text))

    def _extract_chapter_number_from_text(self, text: str) -> Optional[int]:
        """
        텍스트에서 첫 번째 숫자 추출 (단순화된 로직)

        로직:
        1. 텍스트 시작부터 첫 번째 숫자 찾기
        2. 01, 02 형식 포함하여 정수로 변환

        예: "[c]4_실전!" -> 4, "01_바빌론" -> 1, "12가지 인생의 법칙" -> 12

        Args:
            text: 텍스트

        Returns:
            추출된 챕터 번호 또는 None
        """
        # 텍스트 시작부터 첫 번째 숫자 찾기
        match = re.search(r'\d+', text)
        if match:
            try:
                number = int(match.group())  # 01, 02 형식도 정수로 변환
                if number >= 1:
                    logger.debug(f"[DEBUG] 숫자 추출: text='{text[:50]}', 추출된 번호={number}")
                    return number
            except (ValueError, IndexError):
                pass

        logger.debug(f"[DEBUG] 숫자 추출 실패: text='{text[:50]}'")
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
        self, page_chapter_numbers: Dict[int, tuple]
    ) -> Dict[int, tuple]:
        """
        유효한 챕터 번호만 필터링

        기준:
        1. 연속적인 번호 (1, 2, 3, 4, ...)
        2. 합리적인 범위 (1-100)
        3. 비연속/비정상 번호 제외

        Args:
            page_chapter_numbers: {page_number: (chapter_number or None, chapter_marker_text or None)}

        Returns:
            필터링된 {page_number: (chapter_number or None, chapter_marker_text or None)}
        """
        # 모든 챕터 번호 수집
        all_numbers = [n for n, _ in page_chapter_numbers.values() if n is not None]

        if not all_numbers:
            logger.info("[INFO] 연속성 필터링: 추출된 챕터 번호 없음")
            return page_chapter_numbers

        # 필터링 전 상태
        logger.info(f"[INFO] 연속성 필터링 시작:")
        logger.info(f"  - 필터링 전 챕터 번호: {sorted(set(all_numbers))}")
        logger.info(f"  - 필터링 전 챕터 개수: {len(set(all_numbers))}개")
        logger.info(f"  - 페이지별 챕터 번호: {[(p, n) for p, (n, _) in sorted(page_chapter_numbers.items()) if n is not None]}")
        
        # 12가지인생의법칙 실패한 챕터 번호 확인 (챕터 11만)
        failed_chapter_numbers = [11]
        failed_in_all = [n for n in failed_chapter_numbers if n in all_numbers]
        if failed_in_all:
            logger.info(f"  - [12가지인생의법칙] 실패한 챕터 번호 중 필터링 전 존재: {failed_in_all}")
        else:
            logger.warning(f"  - [12가지인생의법칙] 실패한 챕터 번호(11)가 필터링 전에도 없음")

        # 가장 긴 연속 시퀀스 찾기
        valid_numbers = self._find_continuous_sequence(all_numbers)

        # 필터링 후 상태
        excluded_numbers = set(all_numbers) - valid_numbers
        logger.info(f"  - 필터링 후 유효한 챕터 번호: {sorted(valid_numbers)}")
        logger.info(f"  - 필터링 후 챕터 개수: {len(valid_numbers)}개")
        if excluded_numbers:
            logger.info(f"  - 제외된 챕터 번호: {sorted(excluded_numbers)}")
            logger.info(f"  - 제외된 챕터 개수: {len(excluded_numbers)}개")
        
        # 12가지인생의법칙 실패한 챕터 번호가 필터링에서 제외되었는지 확인
        failed_excluded = [n for n in failed_chapter_numbers if n in excluded_numbers]
        failed_valid = [n for n in failed_chapter_numbers if n in valid_numbers]
        if failed_excluded:
            logger.warning(f"  - [12가지인생의법칙] 챕터 11이 필터링에서 제외됨: {failed_excluded}")
            # 챕터 11이 제외된 이유 상세 분석
            if 11 in all_numbers:
                logger.warning(f"    - 챕터 11은 추출되었으나 연속성 필터링에서 제외됨")
                # 챕터 11이 있는 페이지 찾기
                pages_with_11 = [p for p, (n, _) in page_chapter_numbers.items() if n == 11]
                if pages_with_11:
                    logger.warning(f"    - 챕터 11이 추출된 페이지: {pages_with_11}")
                    for p in pages_with_11:
                        marker_text = page_chapter_numbers[p][1]
                        logger.warning(f"      - Page {p}: marker_text='{marker_text}'")
        if failed_valid:
            logger.info(f"  - [12가지인생의법칙] 챕터 11이 필터링 후 유효함: {failed_valid}")

        # 중요 페이지 범위의 챕터 번호가 제외되었는지 확인
        for start, end in self.important_page_ranges:
            pages_in_range = [p for p in range(start, end + 1) if p in page_chapter_numbers]
            numbers_in_range = [page_chapter_numbers[p][0] for p in pages_in_range if page_chapter_numbers[p][0] is not None]
            excluded_in_range = [n for n in numbers_in_range if n not in valid_numbers]
            if excluded_in_range:
                logger.warning(f"[WARNING] 중요 페이지 범위 {start}-{end}: 제외된 챕터 번호 {excluded_in_range}")
            elif numbers_in_range:
                logger.info(f"[INFO] 중요 페이지 범위 {start}-{end}: 유효한 챕터 번호 {numbers_in_range}")

        # 유효한 번호만 유지
        filtered = {}
        for page_num, (chapter_num, marker_text) in page_chapter_numbers.items():
            if chapter_num in valid_numbers:
                filtered[page_num] = (chapter_num, marker_text)
            else:
                filtered[page_num] = (None, marker_text)
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
        self, page_chapter_numbers: Dict[int, tuple], main_pages: List[int]
    ) -> List[Dict[str, Any]]:
        """
        챕터 경계 탐지 (숫자 변경 지점)

        Args:
            page_chapter_numbers: {page_number: (chapter_number or None, chapter_marker_text or None)}
            main_pages: 본문 페이지 목록

        Returns:
            챕터 리스트 (chapter_marker_text 포함)
        """
        chapters = []
        current_chapter = None
        current_start_page = None
        current_marker_text = None

        # 페이지 번호 순서대로 정렬
        sorted_pages = sorted(page_chapter_numbers.keys())

        for page_num in sorted_pages:
            chapter_number, marker_text = page_chapter_numbers[page_num]

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
                            "marker_text": current_marker_text,  # 제목 추출을 위해 저장
                        }
                    )

                # 새 챕터 시작
                current_chapter = chapter_number
                current_start_page = page_num
                current_marker_text = marker_text

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
                    "marker_text": current_marker_text,  # 제목 추출을 위해 저장
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
        챕터 제목 추출 (chapter_marker에서 직접 추출)

        Args:
            chapters: 챕터 리스트 (marker_text 포함)
            all_pages: 전체 페이지 리스트

        Returns:
            제목이 추가된 챕터 리스트
        """
        for ch in chapters:
            # 1. chapter_marker에서 직접 제목 추출 (우선)
            marker_text = ch.get("marker_text")
            if marker_text:
                title = self._extract_chapter_title_from_marker(marker_text)
                if title:
                    ch["title"] = title
                    logger.debug(f"[DEBUG] Chapter {ch['number']} title from marker: '{title}'")
                    continue

            # 2. 제목이 없으면 페이지 상단 요소에서 추출 (fallback)
            start_page = ch["start_page"]
            page_obj = None
            for p in all_pages:
                if p.get("page_number") == start_page:
                    page_obj = p
                    break

            if page_obj:
                title = self._extract_title_from_page_top(page_obj)
                if title:
                    ch["title"] = title
                    logger.debug(f"[DEBUG] Chapter {ch['number']} title from page top: '{title}'")

        return chapters

    def _extract_chapter_title_from_marker(self, text: str) -> Optional[str]:
        """
        chapter_marker 텍스트에서 제목 추출

        로직:
        1. 텍스트 시작부터 첫 번째 숫자 찾기
        2. 숫자 뒤의 단위 문자들 제거 (장, 강, 부, Chapter, Part 등)
        3. 특수문자 및 공백 제거 (], [, -, _, 공백 등)
        4. 일반 문자(한글/영문/숫자) 시작 부분부터 제목으로 사용

        예:
        - "[5장] 인간의 조건" -> "인간의 조건"
        - "4_실전!" -> "실전!"
        - "01_바빌론" -> "바빌론"
        - "12가지 인생의 법칙" -> "가지 인생의 법칙"

        Args:
            text: chapter_marker 텍스트

        Returns:
            추출된 제목 또는 None
        """
        if not text:
            return None

        # 1. 텍스트 시작부터 첫 번째 숫자 찾기
        match = re.search(r'\d+', text)
        if not match:
            return None

        # 숫자 끝 위치
        number_end = match.end()

        # 2. 숫자 뒤의 텍스트 추출
        remaining_text = text[number_end:]

        # 3. 단위 문자들 제거 (장, 강, 부, Chapter, Part 등)
        # 단위 패턴: 한글 단위(장, 강, 부) 또는 영문 단위(Chapter, Part)
        unit_pattern = r'\s*[장강부]|chapter|part'
        remaining_text = re.sub(unit_pattern, '', remaining_text, flags=re.IGNORECASE)

        # 4. 특수문자 및 공백 제거 (], [, -, _, 공백 등)
        # 단, 일반 문자(한글/영문/숫자)는 유지
        remaining_text = re.sub(r'[^\w가-힣]', '', remaining_text)

        # 5. 일반 문자 시작 부분 찾기
        # 한글, 영문, 숫자로 시작하는 부분부터 제목으로 사용
        match = re.search(r'[가-힣a-zA-Z0-9]', remaining_text)
        if match:
            title = remaining_text[match.start():]
            if title:
                logger.debug(f"[DEBUG] 제목 추출: 원본='{text[:50]}', 추출='{title}'")
                return title

        return None

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
