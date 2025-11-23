"""
PDF 파서

Upstage API 응답을 구조화하고 페이지별로 그룹화합니다.
"""
import logging
import re
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup
from backend.parsers.upstage_api_client import UpstageAPIClient
from backend.config.settings import settings

logger = logging.getLogger(__name__)


class PDFParser:
    """PDF 파서 클래스"""

    def __init__(self, api_key: Optional[str] = None):
        """
        Args:
            api_key: Upstage API 키 (None이면 settings에서 가져옴)
        """
        if api_key is None:
            api_key = settings.upstage_api_key
        self.api_client = UpstageAPIClient(api_key)

    def parse_pdf(
        self, file_path: str, use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        PDF 파일 파싱

        Args:
            file_path: PDF 파일 경로
            use_cache: 캐시 사용 여부 (현재는 미구현)

        Returns:
            {
                "pages": [
                    {
                        "page_number": 1,
                        "elements": [...],
                        "raw_text": "..."
                    },
                    ...
                ],
                "total_pages": N,
                "total_elements": N
            }
        """
        # TODO: 캐시 확인 (use_cache=True일 때)
        # if use_cache:
        #     cached_result = cache_manager.get_cached_result(file_path)
        #     if cached_result:
        #         return cached_result

        # API 호출
        logger.info(f"[INFO] Parsing PDF: {file_path}")
        api_response = self.api_client.parse_pdf(file_path)

        # Elements 구조화
        structured_elements = self._structure_elements(api_response)

        # 페이지별 그룹화
        pages = self._group_by_page(structured_elements)

        result = {
            "pages": pages,
            "total_pages": len(pages),
            "total_elements": len(structured_elements),
            "metadata": api_response.get("metadata", {}),
        }

        # TODO: 캐시 저장 (use_cache=True일 때)
        # if use_cache:
        #     cache_manager.save_result(file_path, result)

        logger.info(
            f"[INFO] Parsing completed: {len(pages)} pages, {len(structured_elements)} elements"
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

    def _group_by_page(self, elements: List[Dict]) -> List[Dict]:
        """Elements를 페이지별로 그룹화"""
        pages_dict = {}

        for elem in elements:
            page_num = elem.get("page", 1)
            if page_num not in pages_dict:
                pages_dict[page_num] = {
                    "page_number": page_num,
                    "elements": [],
                }
            pages_dict[page_num]["elements"].append(elem)

        # 각 페이지의 전체 텍스트 추출
        for page in pages_dict.values():
            page["raw_text"] = " ".join(
                [e.get("text", "") for e in page["elements"]]
            )

        return sorted(pages_dict.values(), key=lambda p: p["page_number"])

