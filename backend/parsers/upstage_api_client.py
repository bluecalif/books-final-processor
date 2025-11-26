"""
Upstage API 직접 호출 클라이언트

Python requests를 사용하여 Upstage Document Parse API를 직접 호출합니다.
10페이지 초과 시 자동으로 병렬 분할 파싱합니다.
"""
import requests
from typing import Dict, Any, List, Tuple
from pathlib import Path
import logging
import time
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pypdf import PdfReader, PdfWriter

logger = logging.getLogger(__name__)


class UpstageAPIClient:
    """Upstage Document Parse API 클라이언트"""

    MAX_PAGES_PER_REQUEST = 100  # API 페이지 제한
    PARALLEL_CHUNK_SIZE = 10  # 병렬 처리 기본 청크 크기
    MAX_WORKERS = 5  # 동시 요청 수 제한 (Rate limit 고려)

    def __init__(self, api_key: str):
        """
        Args:
            api_key: Upstage API 키
        """
        self.api_key = api_key
        self.url = "https://api.upstage.ai/v1/document-digitization"

    def parse_pdf(self, pdf_path: str, retries: int = 3) -> Dict[str, Any]:
        """
        PDF 파싱 (10페이지 초과 시 자동 병렬 분할)

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
                    "total_chunks": N,
                    "pages_per_chunk": 10,
                    "parallel_processing": True
                }
            }
        """
        # PDF 페이지 수 확인
        total_pages = self._get_pdf_page_count(pdf_path)
        logger.info(f"[INFO] PDF has {total_pages} pages")

        if total_pages <= self.PARALLEL_CHUNK_SIZE:
            # 10페이지 이하: 한 번에 파싱
            logger.info(f"[INFO] Single request parsing ({total_pages} pages)")
            result = self._parse_single_pdf(pdf_path, retries)
            result["metadata"] = {
                "split_parsing": False,
                "total_chunks": 1,
                "pages_per_chunk": total_pages,
                "parallel_processing": False,
            }
            return result
        else:
            # 10페이지 초과: 병렬 분할 파싱
            logger.info(
                f"[INFO] Parallel parsing required ({total_pages} pages, "
                f"{self.PARALLEL_CHUNK_SIZE} pages per chunk)"
            )
            return self._parse_pdf_parallel(pdf_path, total_pages, retries)

    def _get_pdf_page_count(self, pdf_path: str) -> int:
        """PDF 페이지 수 확인"""
        try:
            reader = PdfReader(pdf_path)
            return len(reader.pages)
        except Exception as e:
            logger.error(f"[ERROR] Failed to read PDF page count: {e}")
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

    def _parse_pdf_parallel(
        self, pdf_path: str, total_pages: int, retries: int
    ) -> Dict[str, Any]:
        """
        PDF를 10페이지씩 분할하여 병렬 파싱

        ThreadPoolExecutor를 사용하여 여러 청크를 동시에 파싱합니다.
        각 청크를 별도로 파싱한 후 결과를 병합합니다.
        """
        # 청크 생성 (10페이지씩)
        chunks = []
        for start_page in range(0, total_pages, self.PARALLEL_CHUNK_SIZE):
            end_page = min(start_page + self.PARALLEL_CHUNK_SIZE, total_pages)
            chunks.append((start_page, end_page))

        logger.info(
            f"[INFO] Created {len(chunks)} chunks for parallel processing "
            f"({self.PARALLEL_CHUNK_SIZE} pages per chunk)"
        )

        # 병렬 처리
        chunk_results = []
        failed_chunks = []

        with ThreadPoolExecutor(max_workers=self.MAX_WORKERS) as executor:
            # 각 청크에 대한 Future 생성
            futures = {
                executor.submit(self._parse_chunk, pdf_path, start_page, end_page, retries): (
                    start_page,
                    end_page,
                )
                for start_page, end_page in chunks
            }

            # 결과 수집
            for future in as_completed(futures):
                start_page, end_page = futures[future]
                try:
                    result = future.result()
                    chunk_results.append((start_page, result))
                    logger.info(
                        f"[INFO] Chunk completed: pages {start_page + 1}-{end_page} "
                        f"({len(result.get('elements', []))} elements)"
                    )
                except Exception as e:
                    logger.error(
                        f"[ERROR] Chunk failed: pages {start_page + 1}-{end_page} - {e}"
                    )
                    failed_chunks.append((start_page, end_page, str(e)))

        # 실패한 청크 재시도
        if failed_chunks:
            logger.warning(
                f"[WARNING] Retrying {len(failed_chunks)} failed chunks"
            )
            for start_page, end_page, error in failed_chunks:
                try:
                    result = self._parse_chunk(pdf_path, start_page, end_page, retries)
                    chunk_results.append((start_page, result))
                    logger.info(
                        f"[INFO] Chunk retry succeeded: pages {start_page + 1}-{end_page}"
                    )
                except Exception as e:
                    logger.error(
                        f"[ERROR] Chunk retry failed: pages {start_page + 1}-{end_page} - {e}"
                    )
                    # 재시도 실패 시에도 계속 진행 (부분 성공 허용)

        # 청크를 시작 페이지 기준으로 정렬 후 병합
        chunk_results.sort(key=lambda x: x[0])
        merged_result = self._merge_chunk_results(chunk_results, total_pages)

        logger.info(
            f"[INFO] Parallel parsing completed: "
            f"{len(chunks)} chunks, {len(merged_result['elements'])} total elements, "
            f"{len(failed_chunks)} failed chunks"
        )

        return merged_result

    def _parse_chunk(
        self, pdf_path: str, start_page: int, end_page: int, retries: int
    ) -> Dict[str, Any]:
        """
        단일 청크 파싱 (ThreadPoolExecutor용)

        Args:
            pdf_path: 원본 PDF 파일 경로
            start_page: 청크 시작 페이지 (0-based)
            end_page: 청크 끝 페이지 (exclusive, 0-based)
            retries: 재시도 횟수

        Returns:
            API 응답 JSON
        """
        # 임시 파일로 PDF 분할
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_file:
            temp_path = temp_file.name

        try:
            self._split_pdf(pdf_path, start_page, end_page, temp_path)
            # 분할된 PDF 파싱
            return self._parse_single_pdf(temp_path, retries)
        finally:
            # 임시 파일 즉시 삭제
            Path(temp_path).unlink(missing_ok=True)

    def _merge_chunk_results(
        self, chunk_results: List[Tuple[int, Dict[str, Any]]], total_pages: int
    ) -> Dict[str, Any]:
        """
        병렬 파싱 결과 병합

        Args:
            chunk_results: (start_page, result) 튜플 리스트 (시작 페이지 기준으로 정렬됨)
            total_pages: 전체 페이지 수

        Returns:
            병합된 API 응답 형식
        """
        all_elements = []

        for start_page, chunk_result in chunk_results:
            # elements 수집 및 page 번호 조정
            for elem in chunk_result.get("elements", []):
                # 원본 PDF의 페이지 번호로 조정
                elem["page"] = elem["page"] + start_page
                # ID 재조정 (중복 방지)
                elem["id"] = len(all_elements)
                all_elements.append(elem)

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
                "total_chunks": len(chunk_results),
                "pages_per_chunk": self.PARALLEL_CHUNK_SIZE,
                "parallel_processing": True,
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
                        f"[INFO] API returned {element_count} elements from {pages_count} pages"
                    )
                    return result
                elif response.status_code == 429:  # Rate limit
                    if attempt < retries - 1:
                        wait_time = 2**attempt  # 지수 백오프
                        logger.warning(
                            f"[WARNING] Rate limited, waiting {wait_time}s before retry"
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
                    logger.warning(f"[WARNING] Request failed, retrying: {e}")
                    time.sleep(2**attempt)  # 지수 백오프
                    continue
                else:
                    raise Exception(f"API request failed after {retries} retries: {e}")

        raise Exception("API call failed after all retries")

