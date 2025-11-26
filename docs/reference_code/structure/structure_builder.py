"""
전체 구조 통합 모듈

서문(start)/본문(main)/종문(end)를 통합하여 최종 구조 JSON을 생성합니다.
"""

import logging
from typing import Dict, Any

from backend.structure.content_boundary_detector import ContentBoundaryDetector
from backend.structure.chapter_detector import ChapterDetector
from backend.structure.hierarchy_builder import HierarchyBuilder

logger = logging.getLogger(__name__)


class StructureBuilder:
    """전체 구조 통합 클래스"""

    def __init__(self):
        """구조 빌더 초기화"""
        self.boundary_detector = ContentBoundaryDetector()
        self.chapter_detector = ChapterDetector()
        self.hierarchy_builder = HierarchyBuilder()

    def build_structure(self, parsed_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        전체 구조 분석 파이프라인

        Args:
            parsed_data: PDFParser.parse_pdf() 결과

        Returns:
            {
                "start": {"pages": [1,2,3], "page_count": 3},
                "main": {
                    "pages": [4, 5, ..., 95],
                    "page_count": 92,
                    "chapters": [
                        {
                            "id": "ch1",
                            "number": 1,
                            "title": "제1장 의식의 본질",
                            "start_page": 4,
                            "end_page": 25,
                            "sections": [...]
                        },
                        ...
                    ]
                },
                "end": {"pages": [96, ..., 100], "page_count": 5},
                "metadata": {
                    "total_pages": 100,
                    "chapter_count": 5,
                    "has_start": True,
                    "has_end": True
                }
            }
        """
        logger.info("=" * 80)
        logger.info("🏗️ Building complete book structure...")
        logger.info("=" * 80)

        # 1. 영역 경계 탐지 (서문/본문/종문)
        boundaries = self.boundary_detector.detect_boundaries(parsed_data)

        # 2. 챕터 탐지 (본문 영역에서)
        main_pages = boundaries["main"]["pages"]
        chapters = self.chapter_detector.detect_chapters(parsed_data, main_pages)

        # 3. 계층 구조 구축 (각 챕터 내 섹션)
        chapters = self.hierarchy_builder.build_hierarchy(parsed_data, chapters)

        # 4. 최종 구조 생성
        structure = {
            "start": {
                "pages": boundaries["start"]["pages"],
                "page_count": len(boundaries["start"]["pages"]),
            },
            "main": {
                "pages": main_pages,
                "page_count": len(main_pages),
                "chapters": chapters,
            },
            "end": {
                "pages": boundaries["end"]["pages"],
                "page_count": len(boundaries["end"]["pages"]),
            },
            "metadata": {
                "total_pages": parsed_data.get("total_pages", 0),
                "chapter_count": len(chapters),
                "has_start": len(boundaries["start"]["pages"]) > 0,
                "has_end": len(boundaries["end"]["pages"]) > 0,
                "confidence": boundaries.get("confidence", {}),
            },
        }

        logger.info("=" * 80)
        logger.info("✅ Structure building completed!")
        logger.info(f"   서문(start): {structure['start']['page_count']} pages")
        logger.info(
            f"   본문(main):  {structure['main']['page_count']} pages ({len(chapters)} chapters)"
        )
        logger.info(f"   종문(end): {structure['end']['page_count']} pages")
        logger.info("=" * 80)

        return structure
