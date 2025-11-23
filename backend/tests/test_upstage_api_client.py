"""UpstageAPIClient 단위 테스트"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
from backend.parsers.upstage_api_client import UpstageAPIClient


class TestUpstageAPIClient:
    """UpstageAPIClient 테스트"""

    def test_get_pdf_page_count_success(self):
        """PDF 페이지 수 확인 성공 테스트"""
        client = UpstageAPIClient(api_key="test-key")
        
        with patch("backend.parsers.upstage_api_client.PdfReader") as mock_reader:
            mock_pages = [Mock() for _ in range(10)]
            mock_reader.return_value.pages = mock_pages
            
            result = client._get_pdf_page_count("test.pdf")
            
            assert result == 10
            mock_reader.assert_called_once_with("test.pdf")

    def test_get_pdf_page_count_error(self):
        """PDF 페이지 수 확인 실패 테스트"""
        client = UpstageAPIClient(api_key="test-key")
        
        with patch("backend.parsers.upstage_api_client.PdfReader") as mock_reader:
            mock_reader.side_effect = Exception("File not found")
            
            result = client._get_pdf_page_count("test.pdf")
            
            assert result == 0  # 에러 시 0 반환

    @patch("builtins.open", create=True)
    @patch("backend.parsers.upstage_api_client.requests.post")
    def test_parse_single_pdf_success(self, mock_post, mock_open):
        """단일 PDF 파싱 성공 테스트"""
        client = UpstageAPIClient(api_key="test-key")
        
        # 파일 열기 모킹
        mock_file = Mock()
        mock_open.return_value.__enter__.return_value = mock_file
        
        # API 응답 모킹
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "elements": [{"id": 0, "page": 1, "category": "paragraph"}],
            "usage": {"pages": 1}
        }
        mock_post.return_value = mock_response
        
        # 테스트 실행
        result = client._parse_single_pdf("test.pdf", retries=1)
        
        # 검증
        assert result["usage"]["pages"] == 1
        assert len(result["elements"]) == 1
        mock_post.assert_called_once()

    @patch("builtins.open", create=True)
    @patch("backend.parsers.upstage_api_client.requests.post")
    def test_parse_single_pdf_rate_limit_retry(self, mock_post, mock_open):
        """Rate limit 재시도 테스트"""
        client = UpstageAPIClient(api_key="test-key")
        
        # 파일 열기 모킹
        mock_file = Mock()
        mock_open.return_value.__enter__.return_value = mock_file
        
        # Rate limit (429) 에러 모킹 후 성공
        mock_response_429 = Mock()
        mock_response_429.status_code = 429
        mock_response_429.text = "Rate limit exceeded"
        
        mock_response_200 = Mock()
        mock_response_200.status_code = 200
        mock_response_200.json.return_value = {
            "elements": [],
            "usage": {"pages": 1}
        }
        
        mock_post.side_effect = [mock_response_429, mock_response_200]
        
        with patch("time.sleep"):  # 실제 대기 시간 제거
            result = client._parse_single_pdf("test.pdf", retries=2)
        
        assert mock_post.call_count == 2  # 재시도 확인
        assert result["usage"]["pages"] == 1

    @patch("builtins.open", create=True)
    @patch("backend.parsers.upstage_api_client.requests.post")
    def test_parse_single_pdf_network_error_retry(self, mock_post, mock_open):
        """네트워크 에러 재시도 테스트"""
        client = UpstageAPIClient(api_key="test-key")
        
        # 파일 열기 모킹
        mock_file = Mock()
        mock_open.return_value.__enter__.return_value = mock_file
        
        import requests
        mock_response_200 = Mock()
        mock_response_200.status_code = 200
        mock_response_200.json.return_value = {"elements": [], "usage": {"pages": 1}}
        
        mock_post.side_effect = [
            requests.exceptions.RequestException("Network error"),
            mock_response_200
        ]
        
        with patch("time.sleep"):  # 실제 대기 시간 제거
            result = client._parse_single_pdf("test.pdf", retries=2)
        
        assert mock_post.call_count == 2  # 재시도 확인
        assert result["usage"]["pages"] == 1

    def test_parse_pdf_under_100_pages(self):
        """100페이지 이하 PDF 파싱 테스트"""
        client = UpstageAPIClient(api_key="test-key")
        
        with patch.object(client, "_get_pdf_page_count", return_value=50):
            with patch.object(client, "_parse_single_pdf") as mock_parse:
                mock_parse.return_value = {
                    "elements": [],
                    "usage": {"pages": 50},
                    "api": "2.0",
                    "model": "document-parse-250618"
                }
                
                result = client.parse_pdf("test.pdf", retries=1)
                
                assert result["metadata"]["split_parsing"] is False
                assert result["metadata"]["total_chunks"] == 1
                mock_parse.assert_called_once()

    def test_parse_pdf_over_100_pages(self):
        """100페이지 초과 PDF 분할 파싱 테스트"""
        client = UpstageAPIClient(api_key="test-key")
        
        with patch.object(client, "_get_pdf_page_count", return_value=250):
            with patch.object(client, "_parse_pdf_in_chunks") as mock_chunks:
                mock_chunks.return_value = {
                    "elements": [],
                    "usage": {"pages": 250},
                    "metadata": {"split_parsing": True, "total_chunks": 3}
                }
                
                result = client.parse_pdf("test.pdf", retries=1)
                
                assert result["metadata"]["split_parsing"] is True
                mock_chunks.assert_called_once_with("test.pdf", 250, 1)

