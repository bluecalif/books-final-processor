"""
Upstage API 직접 호출 클라이언트

Python requests를 사용하여 Upstage Document Parse API를 직접 호출합니다.
10페이지 초과 시 자동으로 병렬 분할 파싱합니다.
"""
import requests
from typing import Dict, Any, List, Tuple, Optional
from pathlib import Path
import logging
import time
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pypdf import PdfReader, PdfWriter
from backend.parsers.cache_manager import CacheManager

logger = logging.getLogger(__name__)


class UpstageAPIClient:
    """Upstage Document Parse API 클라이언트"""

    MAX_PAGES_PER_REQUEST = 100  # API 페이지 제한
    PARALLEL_CHUNK_SIZE = 10  # 병렬 처리 기본 청크 크기
    MAX_WORKERS = 5  # 동시 요청 수 제한 (Rate limit 고려)

    def __init__(self, api_key: str, use_cache: bool = True):
        """
        Args:
            api_key: Upstage API 키
            use_cache: 캐시 사용 여부 (기본값: True)
        """
        self.api_key = api_key
        self.url = "https://api.upstage.ai/v1/document-digitization"
        self.use_cache = use_cache
        self.cache_manager = CacheManager() if use_cache else None

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
        start_time = time.time()
        logger.info(f"[UpstageAPIClient] parse_pdf() 시작: {pdf_path}, use_cache={self.use_cache}")
        
        # 1. 캐시 확인 (전체 파일에 대한 캐시)
        if self.use_cache and self.cache_manager:
            cache_check_start = time.time()
            cached_result = self.cache_manager.get_cached_result(pdf_path)
            cache_check_time = time.time() - cache_check_start
            
            if cached_result:
                elapsed_time = time.time() - start_time
                logger.info(
                    f"[UpstageAPIClient] [CACHE_HIT] 캐시 확인 완료 ({cache_check_time:.3f}초): {pdf_path}"
                )
                logger.info(
                    f"[UpstageAPIClient] [CACHE_HIT] 캐시된 페이지 수: {cached_result.get('usage', {}).get('pages', 0)}"
                )
                logger.info(
                    f"[UpstageAPIClient] parse_pdf() 완료 (캐시 사용): {elapsed_time:.3f}초"
                )
                return cached_result
            else:
                logger.warning(
                    f"[UpstageAPIClient] [CACHE_MISS] 캐시 확인 완료 ({cache_check_time:.3f}초): {pdf_path} - 캐시 없음"
                )
        else:
            logger.info(f"[UpstageAPIClient] [CACHE_DISABLED] 캐시 사용 안 함: {pdf_path}")
        
        # 2. 캐시 미스: API 호출 필요
        logger.info(f"[UpstageAPIClient] [API_CALL_REQUIRED] API 호출 시작: {pdf_path}")
        
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
        else:
            # 10페이지 초과: 병렬 분할 파싱
            logger.info(
                f"[INFO] Parallel parsing required ({total_pages} pages, "
                f"{self.PARALLEL_CHUNK_SIZE} pages per chunk)"
            )
            result = self._parse_pdf_parallel(pdf_path, total_pages, retries)
        
        # 3. 캐시 저장 (API 호출 결과)
        if self.use_cache and self.cache_manager:
            cache_save_start = time.time()
            self.cache_manager.save_cache(pdf_path, result)
            cache_save_time = time.time() - cache_save_start
            logger.info(
                f"[UpstageAPIClient] [CACHE_SAVE] 캐시 저장 완료 ({cache_save_time:.3f}초): {pdf_path}"
            )
        
        elapsed_time = time.time() - start_time
        total_pages_parsed = result.get("usage", {}).get("pages", 0)
        logger.info(
            f"[UpstageAPIClient] parse_pdf() 완료 (API 호출): {elapsed_time:.3f}초, "
            f"파싱된 페이지 수: {total_pages_parsed}"
        )
        
        return result

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
        parallel_start = time.time()
        logger.info(
            f"[UpstageAPIClient] [PARALLEL_START] 병렬 파싱 시작: {pdf_path}, "
            f"총 {total_pages}페이지"
        )
        
        # 청크 생성 (10페이지씩)
        chunks = []
        for start_page in range(0, total_pages, self.PARALLEL_CHUNK_SIZE):
            end_page = min(start_page + self.PARALLEL_CHUNK_SIZE, total_pages)
            chunks.append((start_page, end_page))

        logger.info(
            f"[UpstageAPIClient] [PARALLEL_CHUNKS] {len(chunks)}개 청크 생성: "
            f"각 청크 {self.PARALLEL_CHUNK_SIZE}페이지"
        )
        
        # API 호출 횟수 추적
        api_call_count = 0

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
                    chunk_pages = result.get("usage", {}).get("pages", 0)
                    api_call_count += 1
                    logger.info(
                        f"[UpstageAPIClient] [CHUNK_SUCCESS] 청크 완료: "
                        f"페이지 {start_page + 1}-{end_page} ({chunk_pages}페이지 파싱), "
                        f"{len(result.get('elements', []))} elements, "
                        f"API 호출 횟수: {api_call_count}/{len(chunks)}"
                    )
                except Exception as e:
                    logger.error(
                        f"[UpstageAPIClient] [CHUNK_FAILED] 청크 실패: "
                        f"페이지 {start_page + 1}-{end_page} - {e}"
                    )
                    failed_chunks.append((start_page, end_page, str(e)))

        # 실패한 청크 재시도
        if failed_chunks:
            logger.warning(
                f"[UpstageAPIClient] [RETRY_START] {len(failed_chunks)}개 실패한 청크 재시도 시작"
            )
            for start_page, end_page, error in failed_chunks:
                try:
                    retry_start = time.time()
                    result = self._parse_chunk(pdf_path, start_page, end_page, retries)
                    retry_time = time.time() - retry_start
                    chunk_results.append((start_page, result))
                    chunk_pages = result.get("usage", {}).get("pages", 0)
                    api_call_count += 1
                    logger.info(
                        f"[UpstageAPIClient] [RETRY_SUCCESS] 청크 재시도 성공: "
                        f"페이지 {start_page + 1}-{end_page} ({chunk_pages}페이지 파싱), "
                        f"소요 시간: {retry_time:.3f}초, API 호출 횟수: {api_call_count}"
                    )
                except Exception as e:
                    logger.error(
                        f"[UpstageAPIClient] [RETRY_FAILED] 청크 재시도 실패: "
                        f"페이지 {start_page + 1}-{end_page} - {e}"
                    )
                    # 재시도 실패 시에도 계속 진행 (부분 성공 허용)

        # 청크를 시작 페이지 기준으로 정렬 후 병합
        chunk_results.sort(key=lambda x: x[0])
        merged_result = self._merge_chunk_results(chunk_results, total_pages)

        parallel_time = time.time() - parallel_start
        total_pages_parsed = sum(
            chunk_result.get("usage", {}).get("pages", 0)
            for _, chunk_result in chunk_results
        )
        
        logger.info(
            f"[UpstageAPIClient] [PARALLEL_END] 병렬 파싱 완료: "
            f"{parallel_time:.3f}초, {len(chunks)}개 청크 생성, "
            f"{len(chunk_results)}개 청크 성공, {len(failed_chunks)}개 청크 실패, "
            f"총 API 호출 횟수: {api_call_count}, "
            f"총 파싱된 페이지 수: {total_pages_parsed} (예상: {total_pages}), "
            f"{len(merged_result['elements'])} elements"
        )
        
        if total_pages_parsed != total_pages:
            logger.error(
                f"[UpstageAPIClient] [ERROR] 페이지 수 불일치: "
                f"예상 {total_pages}페이지, 실제 파싱 {total_pages_parsed}페이지 "
                f"(차이: {total_pages_parsed - total_pages}페이지)"
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
        chunk_start = time.time()
        chunk_pages = end_page - start_page
        logger.info(
            f"[UpstageAPIClient] [CHUNK_START] 청크 파싱 시작: "
            f"원본 파일 {pdf_path}, 페이지 {start_page + 1}-{end_page} ({chunk_pages}페이지)"
        )
        
        # 임시 파일로 PDF 분할
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_file:
            temp_path = temp_file.name

        try:
            split_start = time.time()
            self._split_pdf(pdf_path, start_page, end_page, temp_path)
            split_time = time.time() - split_start
            logger.info(
                f"[UpstageAPIClient] [CHUNK_SPLIT] PDF 분할 완료: {split_time:.3f}초, "
                f"임시 파일: {temp_path}"
            )
            
            # 분할된 PDF 파싱
            parse_start = time.time()
            result = self._parse_single_pdf(temp_path, retries)
            parse_time = time.time() - parse_start
            chunk_time = time.time() - chunk_start
            
            parsed_pages = result.get("usage", {}).get("pages", 0)
            logger.info(
                f"[UpstageAPIClient] [CHUNK_END] 청크 파싱 완료: {chunk_time:.3f}초 "
                f"(분할: {split_time:.3f}초, 파싱: {parse_time:.3f}초), "
                f"파싱된 페이지 수: {parsed_pages} (예상: {chunk_pages})"
            )
            
            if parsed_pages != chunk_pages:
                logger.warning(
                    f"[UpstageAPIClient] [CHUNK_WARNING] 페이지 수 불일치: "
                    f"예상 {chunk_pages}페이지, 실제 {parsed_pages}페이지"
                )
            
            return result
        finally:
            # 임시 파일 즉시 삭제
            Path(temp_path).unlink(missing_ok=True)
            logger.debug(f"[UpstageAPIClient] [CHUNK_CLEANUP] 임시 파일 삭제: {temp_path}")

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
        api_start = time.time()
        logger.info(
            f"[UpstageAPIClient] [API_CALL] _parse_single_pdf() 시작: {pdf_path}, "
            f"재시도 횟수: {retries}"
        )
        
        headers = {"Authorization": f"Bearer {self.api_key}"}
        data = {
            "ocr": "force",
            "base64_encoding": "['table']",
            "model": "document-parse",
        }

        # 재시도 로직 (지수 백오프)
        # Rate limit(429) 및 네트워크 오류 시 자동 재시도
        for attempt in range(retries):
            attempt_start = time.time()
            try:
                logger.info(
                    f"[UpstageAPIClient] [API_ATTEMPT] API 호출 시도 {attempt + 1}/{retries}: {pdf_path}"
                )
                with open(pdf_path, "rb") as f:
                    files = {"document": f}
                    # 타임아웃: 120초 (대형 PDF 처리 시간 고려)
                    response = requests.post(
                        self.url, headers=headers, files=files, data=data, timeout=120
                    )

                # 성공 응답 처리
                if response.status_code == 200:
                    result = response.json()
                    element_count = len(result.get("elements", []))
                    pages_count = result.get("usage", {}).get("pages", 0)
                    attempt_time = time.time() - attempt_start
                    total_time = time.time() - api_start
                    logger.info(
                        f"[UpstageAPIClient] [API_SUCCESS] API 호출 성공: "
                        f"시도 {attempt + 1}/{retries}, 소요 시간: {attempt_time:.3f}초 (총 {total_time:.3f}초), "
                        f"{element_count} elements, {pages_count} pages"
                    )
                    return result
                # Rate limit (429) 처리: 지수 백오프로 재시도
                elif response.status_code == 429:
                    if attempt < retries - 1:
                        wait_time = 2**attempt  # 지수 백오프: 1초, 2초, 4초
                        logger.warning(
                            f"[UpstageAPIClient] [API_RATE_LIMIT] Rate limit 발생, "
                            f"{wait_time}초 대기 후 재시도 ({attempt + 1}/{retries}): {pdf_path}"
                        )
                        time.sleep(wait_time)
                        continue
                    else:
                        # 모든 재시도 실패 시 예외 발생
                        logger.error(
                            f"[UpstageAPIClient] [API_RATE_LIMIT_FAILED] Rate limit 초과, "
                            f"모든 재시도 실패: {pdf_path}"
                        )
                        raise Exception(f"Rate limit exceeded: {response.text}")
                
                # 기타 HTTP 오류 (400, 500 등)
                else:
                    logger.error(
                        f"[UpstageAPIClient] [API_ERROR] API 호출 실패: "
                        f"시도 {attempt + 1}/{retries}, 상태 코드: {response.status_code}, "
                        f"파일: {pdf_path}"
                    )
                    raise Exception(
                        f"API call failed: {response.status_code} - {response.text}"
                    )

            # 네트워크 오류 처리 (타임아웃, 연결 실패 등)
            except requests.exceptions.RequestException as e:
                attempt_time = time.time() - attempt_start
                if attempt < retries - 1:
                    wait_time = 2**attempt  # 지수 백오프: 1초, 2초, 4초
                    logger.warning(
                        f"[UpstageAPIClient] [API_RETRY] 요청 실패, {wait_time}초 대기 후 재시도 "
                        f"({attempt + 1}/{retries}): {e}, 소요 시간: {attempt_time:.3f}초"
                    )
                    time.sleep(wait_time)
                    continue
                else:
                    # 모든 재시도 실패 시 예외 발생
                    total_time = time.time() - api_start
                    logger.error(
                        f"[UpstageAPIClient] [API_FAILED] 모든 재시도 실패: "
                        f"{retries}번 시도, 총 소요 시간: {total_time:.3f}초, 에러: {e}"
                    )
                    raise Exception(f"API request failed after {retries} retries: {e}")

        raise Exception("API call failed after all retries")

