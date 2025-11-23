"""PDFParser 단위 테스트"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from backend.parsers.pdf_parser import PDFParser


class TestPDFParser:
    """PDFParser 테스트"""

    def test_extract_text_from_html(self):
        """HTML에서 텍스트 추출 테스트"""
        parser = PDFParser(api_key="test-key")
        
        html = "<p>Hello <strong>World</strong></p>"
        result = parser._extract_text_from_html(html)
        
        # BeautifulSoup의 get_text(strip=True)는 공백을 제거하므로
        assert "Hello" in result
        assert "World" in result
        assert result == "HelloWorld"  # 공백 제거됨

    def test_extract_text_from_html_empty(self):
        """빈 HTML 처리 테스트"""
        parser = PDFParser(api_key="test-key")
        
        result = parser._extract_text_from_html("")
        assert result == ""
        
        result = parser._extract_text_from_html(None)
        assert result == ""

    def test_extract_font_size(self):
        """Font size 추출 테스트"""
        parser = PDFParser(api_key="test-key")
        
        html = '<p style="font-size: 20px">Text</p>'
        result = parser._extract_font_size(html)
        
        assert result == 20

    def test_extract_font_size_default(self):
        """Font size 없을 때 기본값 테스트"""
        parser = PDFParser(api_key="test-key")
        
        html = "<p>No font size</p>"
        result = parser._extract_font_size(html)
        
        assert result == 12  # 기본값

    def test_calculate_bbox(self):
        """Bbox 계산 테스트"""
        parser = PDFParser(api_key="test-key")
        
        coordinates = [
            {"x": 0.1, "y": 0.2},
            {"x": 0.5, "y": 0.3},
            {"x": 0.2, "y": 0.4},
        ]
        
        result = parser._calculate_bbox(coordinates)
        
        assert result["x0"] == 0.1
        assert result["y0"] == 0.2
        assert result["x1"] == 0.5
        assert result["y1"] == 0.4
        assert result["width"] == 0.4
        assert result["height"] == 0.2

    def test_calculate_bbox_empty(self):
        """빈 좌표 배열 처리 테스트"""
        parser = PDFParser(api_key="test-key")
        
        result = parser._calculate_bbox([])
        
        assert result == {"x0": 0, "y0": 0, "x1": 0, "y1": 0, "width": 0, "height": 0}

    def test_structure_elements(self):
        """Elements 구조화 테스트"""
        parser = PDFParser(api_key="test-key")
        
        api_response = {
            "elements": [
                {
                    "id": 0,
                    "page": 1,
                    "category": "paragraph",
                    "coordinates": [{"x": 0.1, "y": 0.2}, {"x": 0.5, "y": 0.3}],
                    "content": {"html": '<p style="font-size: 16px">Test text</p>'}
                }
            ]
        }
        
        result = parser._structure_elements(api_response)
        
        assert len(result) == 1
        assert result[0]["id"] == 0
        assert result[0]["page"] == 1
        assert result[0]["text"] == "Test text"
        assert result[0]["category"] == "paragraph"
        assert result[0]["font_size"] == 16
        assert "bbox" in result[0]

    def test_group_by_page(self):
        """페이지별 그룹화 테스트"""
        parser = PDFParser(api_key="test-key")
        
        elements = [
            {"id": 0, "page": 1, "text": "Page 1 text"},
            {"id": 1, "page": 1, "text": "Page 1 more"},
            {"id": 2, "page": 2, "text": "Page 2 text"},
        ]
        
        result = parser._group_by_page(elements)
        
        assert len(result) == 2
        assert result[0]["page_number"] == 1
        assert result[1]["page_number"] == 2
        assert len(result[0]["elements"]) == 2
        assert len(result[1]["elements"]) == 1
        assert "raw_text" in result[0]
        assert "Page 1 text" in result[0]["raw_text"]

    @patch("backend.parsers.pdf_parser.UpstageAPIClient")
    def test_parse_pdf(self, mock_client_class):
        """PDF 파싱 통합 테스트"""
        # API 클라이언트 모킹
        mock_client = Mock()
        mock_client.parse_pdf.return_value = {
            "elements": [
                {
                    "id": 0,
                    "page": 1,
                    "category": "paragraph",
                    "coordinates": [{"x": 0.1, "y": 0.2}],
                    "content": {"html": "<p>Test</p>"}
                }
            ],
            "usage": {"pages": 1},
            "metadata": {}
        }
        mock_client_class.return_value = mock_client
        
        parser = PDFParser(api_key="test-key")
        result = parser.parse_pdf("test.pdf", use_cache=False)
        
        assert result["total_pages"] == 1
        assert result["total_elements"] == 1
        assert len(result["pages"]) == 1
        assert result["pages"][0]["page_number"] == 1

