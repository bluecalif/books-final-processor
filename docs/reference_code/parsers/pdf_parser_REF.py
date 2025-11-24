"""
참고 파일: PDF 파싱 메인 모듈

출처: 기존 프로젝트 (사용자 제공)
참고 목적: PDF 파서 구현 참고

주요 차이점 예상:
1. 이모지 사용: 참고 파일에는 이모지(🔍, 💾, ✅, ❌ 등)가 있으나, 현재 프로젝트는 이모지 사용 금지 → `[INFO]`, `[ERROR]` 형식으로 변경 필요
2. 로깅 형식: 참고 파일은 일반 로깅, 현재 프로젝트는 `[INFO]`, `[ERROR]` 형식 사용
3. 양면 분리 로직: 참고 파일에는 `_split_pages_by_side()` 메서드가 있으나, 현재 프로젝트에는 필요 여부 확인 필요
4. clean_output 옵션: 참고 파일에는 `clean_output` 옵션이 있으나, 현재 프로젝트에는 없을 수 있음
5. 설정 관리: 참고 파일은 `settings.upstage_api_key` 직접 사용, 현재 프로젝트는 `Settings` 클래스 사용
6. 변수명/함수명: 현재 프로젝트 규칙에 맞게 Align 필요
7. 캐싱 통합: 참고 파일의 캐싱 로직을 현재 프로젝트의 `CacheManager`와 통합 필요

Upstage API를 직접 호출하여 PDF를 파싱하고,
양면 스캔 분리 처리를 수행합니다.
"""

import os
import logging
from typing import Dict, Any, List
from pathlib import Path
from bs4 import BeautifulSoup
import re

from backend.config.settings import settings
from backend.parsers.upstage_api_client import UpstageAPIClient
from backend.parsers.cache_manager import CacheManager

logger = logging.getLogger(__name__)


class PDFParser:
    """
    PDF 파싱 메인 클래스

    Flow:
    1. 캐시 확인
    2. 캐시 미스 시 Upstage API 호출 및 캐싱
    3. API 응답 → 구조화된 Elements 변환
    4. 양면 분리 로직 적용
    5. 최종 JSON 반환
    """

    def __init__(self, enable_cache: bool = True, clean_output: bool = True):
        """
        Args:
            enable_cache: 캐시 사용 여부
            clean_output: 출력 시 불필요한 필드 제거 (original_page, page)
        """
        self.upstage_client = UpstageAPIClient(settings.upstage_api_key)
        self.cache_manager = CacheManager() if enable_cache else None
        self.clean_output = clean_output

    def parse_pdf(
        self, pdf_path: str, use_cache: bool = True, force_split: bool = False
    ) -> Dict[str, Any]:
        """
        PDF 파싱 메인 함수

        Args:
            pdf_path: PDF 파일 경로
            use_cache: 캐시 사용 여부
            force_split: 강제 양면 분리 여부

        Returns:
            {
                "success": True,
                "pages": [
                    {
                        "page_number": 1,
                        "original_page": 1,
                        "side": "left",
                        "elements": [
                            {
                                "id": 0,
                                "page": 1,
                                "text": "...",
                                "category": "paragraph",
                                "font_size": 20,
                                "bbox": {"x0": 0.1, "y0": 0.2, ...}
                            },
                            ...
                        ]
                    },
                    ...
                ],
                "total_pages": 4,
                "original_pages": 2,
                "split_applied": True,
                "metadata": {...}
            }
        """
        try:
            pdf_path = Path(pdf_path)
            if not pdf_path.exists():
                raise FileNotFoundError(f"PDF not found: {pdf_path}")

            logger.info(f"🔍 Parsing PDF: {pdf_path.name}")

            # 1. 캐시 확인
            api_response = None
            if use_cache and self.cache_manager:
                api_response = self.cache_manager.get_cached_result(str(pdf_path))
                if api_response:
                    logger.info(f"💾 Using cached API response for {pdf_path.name}")

            # 2. API 호출
            if api_response is None:
                api_response = self.upstage_client.parse_pdf(str(pdf_path))

                # 캐싱 (API 응답 원본 그대로)
                if use_cache and self.cache_manager:
                    self.cache_manager.save_cache(str(pdf_path), api_response)
                    logger.info(f"💾 Cached API response for {pdf_path.name}")

            # 3. Elements 구조화
            logger.info("🔧 Structuring elements...")
            structured_elements = self._structure_elements(api_response)

            # 4. 양면 분리
            logger.info("📄 Splitting pages by side...")
            pages = self._split_pages_by_side(structured_elements, force_split)

            # 5. clean_output 처리 (불필요한 필드 제거)
            if self.clean_output:
                pages = self._clean_pages(pages)
            
            # 6. 최종 결과
            original_pages = api_response.get("usage", {}).get("pages", 0)
            result = {
                "success": True,
                "pages": pages,
                "total_pages": len(pages),
                "original_pages": original_pages,
                "split_applied": len(pages) > original_pages,
                "force_split_applied": force_split,
                "pdf_path": str(pdf_path),
                "metadata": {
                    "api_version": api_response.get("api"),
                    "model": api_response.get("model"),
                    "processing_applied": {
                        "upstage_parsing": True,
                        "element_structuring": True,
                        "page_splitting": len(pages) > original_pages,
                    },
                },
            }

            logger.info(
                f"✅ Parsing completed: {original_pages} original pages → {len(pages)} final pages"
            )
            return result

        except Exception as e:
            logger.error(f"❌ PDF parsing failed: {e}")
            raise

    def _structure_elements(self, api_response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        API 응답의 elements를 우리 형식으로 구조화

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
                    "page": elem.get("page"),  # 내부 처리용 (양면 분리에 필요)
                    "text": text,
                    "category": elem.get("category", "unknown"),
                    "font_size": font_size,
                    "bbox": bbox,
                }
            )

        logger.info(f"Structured {len(structured)} elements")
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
        match = re.search(r"font-size:(\d+)px", html)
        return int(match.group(1)) if match else 12

    def _calculate_bbox(self, coordinates: List[Dict]) -> Dict[str, float]:
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
        """
        CENTERLINE = 0.5  # 고정 중앙선

        # 페이지별로 그룹화
        pages_dict = {}
        for elem in elements:
            page_num = elem["page"]
            if page_num not in pages_dict:
                pages_dict[page_num] = []
            pages_dict[page_num].append(elem)

        # 페이지별로 좌/우 분리
        result_pages = []
        page_counter = 1

        for original_page in sorted(pages_dict.keys()):
            page_elements = pages_dict[original_page]

            # 좌/우 분리 (고정 중앙선 0.5 기준)
            left_elements = [e for e in page_elements if e["bbox"]["x0"] < CENTERLINE]
            right_elements = [e for e in page_elements if e["bbox"]["x0"] >= CENTERLINE]

            logger.debug(
                f"  Page {original_page}: {len(page_elements)} elements → "
                f"{len(left_elements)} left, {len(right_elements)} right "
                f"(centerline={CENTERLINE})"
            )

            # 좌측 페이지 (요소가 있을 경우만)
            if left_elements:
                result_pages.append(
                    {
                        "page_number": page_counter,
                        "original_page": original_page,
                        "side": "left",
                        "elements": sorted(
                            left_elements,
                            key=lambda x: (x["bbox"]["y0"], x["bbox"]["x0"]),
                        ),
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
                result_pages.append(
                    {
                        "page_number": page_counter,
                        "original_page": original_page,
                        "side": "right",
                        "elements": sorted(
                            right_elements,
                            key=lambda x: (x["bbox"]["y0"], x["bbox"]["x0"]),
                        ),
                        "metadata": {
                            "is_split": True,
                            "centerline": CENTERLINE,
                            "element_count": len(right_elements),
                        },
                    }
                )
                page_counter += 1

        logger.info(f"Page splitting completed: {len(pages_dict)} original pages → {len(result_pages)} split pages")
        return result_pages

    def _clean_pages(self, pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        불필요한 필드 제거 (clean_output=True일 때)
        
        제거할 필드:
        - 페이지 레벨: original_page
        - element 레벨: page
        """
        import copy
        cleaned_pages = copy.deepcopy(pages)
        
        for page in cleaned_pages:
            # original_page 제거
            if "original_page" in page:
                del page["original_page"]
            
            # elements 내의 page 필드 제거
            if "elements" in page:
                for element in page["elements"]:
                    if "page" in element:
                        del element["page"]
        
        return cleaned_pages
