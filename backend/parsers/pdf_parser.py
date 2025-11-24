"""
PDF 파서

Upstage API 응답을 구조화하고 페이지별로 그룹화합니다.
양면 분리 로직을 포함합니다.
"""
import logging
import re
import copy
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup
from backend.parsers.upstage_api_client import UpstageAPIClient
from backend.parsers.cache_manager import CacheManager
from backend.config.settings import settings

logger = logging.getLogger(__name__)


class PDFParser:
    """PDF 파서 클래스"""

    def __init__(self, api_key: Optional[str] = None, clean_output: bool = True):
        """
        Args:
            api_key: Upstage API 키 (None이면 settings에서 가져옴)
            clean_output: 출력 시 불필요한 필드 제거 (기본값: True)
        """
        if api_key is None:
            api_key = settings.upstage_api_key
        self.api_client = UpstageAPIClient(api_key)
        self.cache_manager = CacheManager()  # 캐시 매니저 초기화
        self.clean_output = clean_output

    def parse_pdf(
        self, file_path: str, use_cache: bool = True, force_split: bool = True
    ) -> Dict[str, Any]:
        """
        PDF 파일 파싱

        Args:
            file_path: PDF 파일 경로
            use_cache: 캐시 사용 여부 (기본값: True)
            force_split: 강제 양면 분리 여부 (기본값: True)

        Returns:
            {
                "pages": [
                    {
                        "page_number": 1,  # 분리 후 페이지 번호
                        "elements": [...],
                        "raw_text": "..."  # 좌/우별 텍스트
                    },
                    ...
                ],
                "total_pages": 4,  # 분리 후 페이지 수
                "total_elements": N,
                "original_pages": 2,  # 원본 페이지 수
                "split_applied": True,  # 양면 분리 적용 여부
                "metadata": {...}
            }
        """
        # 1. 캐시 확인
        if use_cache:
            cached_result = self.cache_manager.get_cached_result(file_path)
            if cached_result:
                logger.info(f"[INFO] Cache hit for {file_path}")
                # 캐시된 API 응답을 구조화
                structured_elements = self._structure_elements(cached_result)
                # 양면 분리 적용
                pages = self._split_pages_by_side(structured_elements, force_split)
                # clean_output 처리
                if self.clean_output:
                    pages = self._clean_pages(pages)
                
                original_pages = cached_result.get("usage", {}).get("pages", 0)
                return {
                    "pages": pages,
                    "total_pages": len(pages),
                    "total_elements": len(structured_elements),
                    "original_pages": original_pages,
                    "split_applied": len(pages) > original_pages if original_pages > 0 else False,
                    "metadata": cached_result.get("metadata", {}),
                }

        # 2. API 호출 (캐시 미스)
        logger.info(f"[INFO] Cache miss for {file_path}, calling Upstage API")
        api_response = self.api_client.parse_pdf(file_path)

        # 3. Elements 구조화
        structured_elements = self._structure_elements(api_response)

        # 4. 양면 분리 적용
        pages = self._split_pages_by_side(structured_elements, force_split)

        # 5. clean_output 처리
        if self.clean_output:
            pages = self._clean_pages(pages)

        # 6. 원본 페이지 수 계산
        original_pages = api_response.get("usage", {}).get("pages", 0)

        result = {
            "pages": pages,
            "total_pages": len(pages),
            "total_elements": len(structured_elements),
            "original_pages": original_pages,
            "split_applied": len(pages) > original_pages if original_pages > 0 else False,
            "metadata": api_response.get("metadata", {}),
        }

        # 7. 캐시 저장 (API 원본 응답 저장)
        if use_cache:
            self.cache_manager.save_cache(file_path, api_response)
            logger.info(f"[INFO] Cached API response for {file_path}")

        logger.info(
            f"[INFO] Parsing completed: {original_pages} original pages → {len(pages)} final pages, {len(structured_elements)} elements"
        )
        return result

    def _structure_elements(
        self, api_response: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        API 응답의 elements를 표준 형식으로 구조화

        Input: api_response["elements"] = [
            {
                "id": 0,
                "page": 1,
                "category": "paragraph",
                "coordinates": [{"x": 0.1, "y": 0.2}, ...],
                "content": {"html": "<p>...</p>", ...}
            },
            ...
        ]

        Output: [
            {
                "id": 0,
                "page": 1,
                "text": "텍스트 내용",
                "category": "paragraph",
                "font_size": 20,
                "bbox": {"x0": 0.1, "y0": 0.2, "x1": 0.5, "y1": 0.3, "width": 0.4, "height": 0.1}
            },
            ...
        ]
        """
        elements = api_response.get("elements", [])
        structured = []

        for elem in elements:
            # HTML에서 텍스트 추출
            html_content = elem.get("content", {}).get("html", "")
            text = self._extract_text_from_html(html_content)

            # Font size 추출
            font_size = self._extract_font_size(html_content)

            # Bbox 계산
            bbox = self._calculate_bbox(elem.get("coordinates", []))

            structured.append(
                {
                    "id": elem.get("id"),
                    "page": elem.get("page"),
                    "text": text,
                    "category": elem.get("category", "unknown"),
                    "font_size": font_size,
                    "bbox": bbox,
                }
            )

        logger.info(f"[INFO] Structured {len(structured)} elements")
        return structured

    def _extract_text_from_html(self, html: str) -> str:
        """HTML에서 순수 텍스트 추출"""
        if not html:
            return ""
        soup = BeautifulSoup(html, "html.parser")
        return soup.get_text(strip=True)

    def _extract_font_size(self, html: str) -> int:
        """HTML style에서 font-size 추출"""
        if not html:
            return 12
        match = re.search(r"font-size:\s*(\d+)px", html)
        return int(match.group(1)) if match else 12

    def _calculate_bbox(
        self, coordinates: List[Dict[str, float]]
    ) -> Dict[str, float]:
        """좌표 배열에서 bbox 계산"""
        if not coordinates:
            return {"x0": 0, "y0": 0, "x1": 0, "y1": 0, "width": 0, "height": 0}

        x_coords = [c["x"] for c in coordinates]
        y_coords = [c["y"] for c in coordinates]

        x0, x1 = min(x_coords), max(x_coords)
        y0, y1 = min(y_coords), max(y_coords)

        return {
            "x0": x0,
            "y0": y0,
            "x1": x1,
            "y1": y1,
            "width": x1 - x0,
            "height": y1 - y0,
        }

    def _split_pages_by_side(
        self, elements: List[Dict[str, Any]], force_split: bool
    ) -> List[Dict[str, Any]]:
        """
        페이지별 양면 분리 (상대좌표 기준 0.5 고정)

        좌표가 정규화된 상대좌표이므로:
        - x < 0.5: 좌측 페이지
        - x >= 0.5: 우측 페이지

        Args:
            elements: 구조화된 elements 리스트
            force_split: 강제 양면 분리 여부

        Returns:
            분리된 페이지 리스트 (raw_text 포함)
        """
        CENTERLINE = 0.5  # 고정 중앙선

        # 페이지별로 그룹화
        pages_dict = {}
        for elem in elements:
            page_num = elem.get("page", 1)
            if page_num not in pages_dict:
                pages_dict[page_num] = []
            pages_dict[page_num].append(elem)

        # 페이지별로 좌/우 분리
        result_pages = []
        page_counter = 1

        for original_page in sorted(pages_dict.keys()):
            page_elements = pages_dict[original_page]

            # 좌/우 분리 (고정 중앙선 0.5 기준)
            left_elements = [
                e for e in page_elements
                if e.get("bbox", {}).get("x0", 0.5) < CENTERLINE
            ]
            right_elements = [
                e for e in page_elements
                if e.get("bbox", {}).get("x0", 0.5) >= CENTERLINE
            ]

            logger.debug(
                f"[DEBUG] Page {original_page}: {len(page_elements)} elements → "
                f"{len(left_elements)} left, {len(right_elements)} right "
                f"(centerline={CENTERLINE})"
            )

            # 좌측 페이지 (요소가 있을 경우만)
            if left_elements:
                # 요소 정렬 (y0, x0 순서)
                sorted_left = sorted(
                    left_elements,
                    key=lambda x: (
                        x.get("bbox", {}).get("y0", 1.0),
                        x.get("bbox", {}).get("x0", 0.0)
                    ),
                )
                # raw_text 생성
                raw_text_left = " ".join([e.get("text", "") for e in sorted_left])
                
                result_pages.append(
                    {
                        "page_number": page_counter,
                        "original_page": original_page,
                        "side": "left",
                        "elements": sorted_left,
                        "raw_text": raw_text_left,
                        "metadata": {
                            "is_split": True,
                            "centerline": CENTERLINE,
                            "element_count": len(left_elements),
                        },
                    }
                )
                page_counter += 1

            # 우측 페이지 (요소가 있을 경우만)
            if right_elements:
                # 요소 정렬 (y0, x0 순서)
                sorted_right = sorted(
                    right_elements,
                    key=lambda x: (
                        x.get("bbox", {}).get("y0", 1.0),
                        x.get("bbox", {}).get("x0", 0.0)
                    ),
                )
                # raw_text 생성
                raw_text_right = " ".join([e.get("text", "") for e in sorted_right])
                
                result_pages.append(
                    {
                        "page_number": page_counter,
                        "original_page": original_page,
                        "side": "right",
                        "elements": sorted_right,
                        "raw_text": raw_text_right,
                        "metadata": {
                            "is_split": True,
                            "centerline": CENTERLINE,
                            "element_count": len(right_elements),
                        },
                    }
                )
                page_counter += 1

        logger.info(
            f"[INFO] Page splitting completed: {len(pages_dict)} original pages → {len(result_pages)} split pages"
        )
        return result_pages

    def _clean_pages(self, pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        불필요한 필드 제거 (clean_output=True일 때)
        
        제거할 필드:
        - 페이지 레벨: original_page, side, metadata
        - element 레벨: page

        Args:
            pages: 분리된 페이지 리스트

        Returns:
            정리된 페이지 리스트
        """
        cleaned_pages = copy.deepcopy(pages)
        
        for page in cleaned_pages:
            # original_page 제거
            if "original_page" in page:
                del page["original_page"]
            
            # side 제거
            if "side" in page:
                del page["side"]
            
            # metadata 제거
            if "metadata" in page:
                del page["metadata"]
            
            # elements 내의 page 필드 제거
            if "elements" in page:
                for element in page["elements"]:
                    if "page" in element:
                        del element["page"]
        
        return cleaned_pages

