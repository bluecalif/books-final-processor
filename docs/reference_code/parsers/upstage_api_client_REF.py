"""
참고 파일: Upstage API 직접 호출 클라이언트

출처: 기존 프로젝트 (사용자 제공)
참고 목적: Upstage API 클라이언트 구현 참고

주요 차이점 예상:
1. 이모지 사용: 참고 파일에는 이모지(📄, 📡, ✅ 등)가 있으나, 현재 프로젝트는 이모지 사용 금지 → `[INFO]`, `[ERROR]` 형식으로 변경 필요
2. 로깅 형식: 참고 파일은 일반 로깅, 현재 프로젝트는 `[INFO]`, `[ERROR]` 형식 사용
3. PyPDF2 vs pypdf: 참고 파일은 PyPDF2 사용, 현재 프로젝트는 pypdf 사용 → 변경 필요
4. 설정 관리: 참고 파일은 `api_key`를 직접 받지만, 현재 프로젝트는 `Settings` 클래스 사용
5. 변수명/함수명: 현재 프로젝트 규칙에 맞게 Align 필요

Python requests를 사용하여 Upstage Document Parse API를 직접 호출합니다.
100페이지 초과 시 자동으로 분할 파싱합니다.
"""

import requests
from typing import Dict, Any, List
from pathlib import Path
import logging
import time
from PyPDF2 import PdfReader, PdfWriter
import tempfile

logger = logging.getLogger(__name__)


class UpstageAPIClient:
    """Upstage Document Parse API 클라이언트"""

    MAX_PAGES_PER_REQUEST = 100  # API 페이지 제한

    def __init__(self, api_key: str):
        """
        Args:
            api_key: Upstage API 키
        """
        self.api_key = api_key
        self.url = "https://api.upstage.ai/v1/document-digitization"

    def parse_pdf(self, pdf_path: str, retries: int = 3) -> Dict[str, Any]:
        """
        PDF 파싱 (100페이지 초과 시 자동 분할)

        Args:
            pdf_path: PDF 파일 경로
            retries: 재시도 횟수

        Returns:
            {
                "api": "2.0",
                "model": "document-parse-250618",
                "usage": {"pages": total_pages},
                "content": {"html": "...", "markdown": "", "text": ""},
                "elements": [...],
                "metadata": {
                    "split_parsing": True/False,
                    "total_chunks": N
                }
            }
        """
        # PDF 페이지 수 확인
        total_pages = self._get_pdf_page_count(pdf_path)
        logger.info(f"📄 PDF has {total_pages} pages")

        if total_pages <= self.MAX_PAGES_PER_REQUEST:
            # 100페이지 이하: 한 번에 파싱
            logger.info(f"📡 Single request parsing ({total_pages} pages)")
            result = self._parse_single_pdf(pdf_path, retries)
            result["metadata"] = {"split_parsing": False, "total_chunks": 1}
            return result
        else:
            # 100페이지 초과: 분할 파싱
            logger.info(
                f"📡 Split parsing required ({total_pages} pages, "
                f"max {self.MAX_PAGES_PER_REQUEST} per request)"
            )
            return self._parse_pdf_in_chunks(pdf_path, total_pages, retries)

    def _get_pdf_page_count(self, pdf_path: str) -> int:
        """PDF 페이지 수 확인"""
        try:
            reader = PdfReader(pdf_path)
            return len(reader.pages)
        except Exception as e:
            logger.error(f"Failed to read PDF page count: {e}")
            # 페이지 수를 알 수 없으면 일단 단일 파싱 시도
            return 0

    def _split_pdf(
        self, pdf_path: str, start_page: int, end_page: int, output_path: str
    ) -> None:
        """PDF를 특정 페이지 범위로 분할"""
        reader = PdfReader(pdf_path)
        writer = PdfWriter()

        for page_num in range(start_page, min(end_page, len(reader.pages))):
            writer.add_page(reader.pages[page_num])

        with open(output_path, "wb") as output_file:
            writer.write(output_file)

    def _parse_pdf_in_chunks(
        self, pdf_path: str, total_pages: int, retries: int
    ) -> Dict[str, Any]:
        """
        PDF를 100페이지씩 분할하여 파싱

        각 청크를 별도로 파싱한 후 결과를 병합합니다.
        """
        all_elements = []
        chunk_count = 0
        page_offset = 0

        # 100페이지씩 분할
        for start_page in range(0, total_pages, self.MAX_PAGES_PER_REQUEST):
            end_page = min(start_page + self.MAX_PAGES_PER_REQUEST, total_pages)
            chunk_count += 1

            logger.info(
                f"📄 Processing chunk {chunk_count}: "
                f"pages {start_page + 1}-{end_page} of {total_pages}"
            )

            # 임시 파일로 PDF 분할
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_file:
                temp_path = temp_file.name

            try:
                self._split_pdf(pdf_path, start_page, end_page, temp_path)

                # 분할된 PDF 파싱
                chunk_result = self._parse_single_pdf(temp_path, retries)

                # elements 수집 및 page 번호 조정
                for elem in chunk_result.get("elements", []):
                    # 원본 PDF의 페이지 번호로 조정
                    elem["page"] = elem["page"] + page_offset
                    # ID 재조정 (중복 방지)
                    elem["id"] = len(all_elements)
                    all_elements.append(elem)

                page_offset += chunk_result.get("usage", {}).get("pages", 0)

                # Rate limit 방지를 위한 대기
                if chunk_count < (total_pages // self.MAX_PAGES_PER_REQUEST + 1):
                    time.sleep(2)  # 청크 간 2초 대기

            finally:
                # 임시 파일 삭제
                Path(temp_path).unlink(missing_ok=True)

        logger.info(
            f"✅ Split parsing completed: "
            f"{chunk_count} chunks, {len(all_elements)} total elements"
        )

        # 병합된 결과 반환
        return {
            "api": "2.0",
            "model": "document-parse-250618",
            "usage": {"pages": total_pages},
            "content": {
                "html": "",  # 분할 파싱 시 전체 HTML은 생략
                "markdown": "",
                "text": "",
            },
            "elements": all_elements,
            "metadata": {
                "split_parsing": True,
                "total_chunks": chunk_count,
                "pages_per_chunk": self.MAX_PAGES_PER_REQUEST,
            },
        }

    def _parse_single_pdf(self, pdf_path: str, retries: int = 3) -> Dict[str, Any]:
        """
        단일 PDF 파싱 (Upstage API 직접 호출)

        Args:
            pdf_path: PDF 파일 경로
            retries: 재시도 횟수

        Returns:
            API 응답 JSON

        Raises:
            Exception: API 호출 실패 시
        """
        headers = {"Authorization": f"Bearer {self.api_key}"}
        data = {
            "ocr": "force",
            "base64_encoding": "['table']",
            "model": "document-parse",
        }

        for attempt in range(retries):
            try:
                with open(pdf_path, "rb") as f:
                    files = {"document": f}
                    response = requests.post(
                        self.url, headers=headers, files=files, data=data, timeout=120
                    )

                if response.status_code == 200:
                    result = response.json()
                    element_count = len(result.get("elements", []))
                    pages_count = result.get("usage", {}).get("pages", 0)
                    logger.info(
                        f"✅ API returned {element_count} elements from {pages_count} pages"
                    )
                    return result
                elif response.status_code == 429:  # Rate limit
                    if attempt < retries - 1:
                        wait_time = 2**attempt
                        logger.warning(
                            f"⏳ Rate limited, waiting {wait_time}s before retry"
                        )
                        time.sleep(wait_time)
                        continue
                    else:
                        raise Exception(f"Rate limit exceeded: {response.text}")
                else:
                    raise Exception(
                        f"API call failed: {response.status_code} - {response.text}"
                    )

            except requests.exceptions.RequestException as e:
                if attempt < retries - 1:
                    logger.warning(f"Request failed, retrying: {e}")
                    time.sleep(2**attempt)
                    continue
                else:
                    raise Exception(f"API request failed after {retries} retries: {e}")

        raise Exception("API call failed after all retries")
