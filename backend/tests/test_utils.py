"""
E2E 테스트 공통 유틸리티 함수

진행률, 소요 시간, 남은 시간 표시를 위한 공통 함수
"""
import time
import httpx
import re
from pathlib import Path
from typing import Dict, Any, Optional, List
from backend.config.settings import settings


def wait_for_status_with_progress(
    e2e_client: httpx.Client,
    book_id: int,
    target_status: str,
    max_wait_time: int = 1800,
    check_interval: int = 5,
    progress_callback: Optional[callable] = None,
) -> Dict[str, Any]:
    """
    책 상태가 목표 상태가 될 때까지 대기 (진행률 출력 포함)
    
    Args:
        e2e_client: HTTP 클라이언트
        book_id: 책 ID
        target_status: 목표 상태
        max_wait_time: 최대 대기 시간 (초)
        check_interval: 상태 확인 간격 (초)
        progress_callback: 진행률 출력 콜백 함수 (book_data, elapsed) -> None
    
    Returns:
        최종 책 데이터
    """
    start_time = time.time()
    last_print_time = 0
    
    while True:
        elapsed = time.time() - start_time
        if elapsed > max_wait_time:
            raise AssertionError(
                f"Status change timeout: book_id={book_id}, "
                f"target={target_status}, elapsed={elapsed:.1f}s"
            )
        
        response = e2e_client.get(f"/api/books/{book_id}")
        assert response.status_code == 200
        book_data = response.json()
        current_status = book_data["status"]
        
        if current_status == target_status:
            elapsed_min = int(elapsed // 60)
            elapsed_sec = int(elapsed % 60)
            print(f"[TEST] [OK] Status changed to {target_status} (Time: {elapsed_min:02d}:{elapsed_sec:02d})", flush=True)
            return book_data
        elif current_status in ["error_parsing", "error_structuring", "error_summarizing", "failed"]:
            raise AssertionError(
                f"Processing failed: book_id={book_id}, status={current_status}"
            )
        
        # 10초마다 또는 progress_callback이 있으면 더 자주 출력
        print_interval = 5 if progress_callback else 10
        if int(elapsed) - last_print_time >= print_interval:
            elapsed_min = int(elapsed // 60)
            elapsed_sec = int(elapsed % 60)
            print(f"[TEST] Waiting for {target_status}... (current: {current_status}, Time: {elapsed_min:02d}:{elapsed_sec:02d})", flush=True)
            last_print_time = int(elapsed)
            
            # progress_callback 호출 (페이지/챕터 추출 진행률 등)
            if progress_callback:
                progress_callback(book_data, elapsed)
        
        time.sleep(check_interval)


def wait_for_extraction_with_progress(
    e2e_client: httpx.Client,
    book_id: int,
    target_status: str,
    expected_count: int,
    get_current_count_func: callable,
    extraction_type: str = "pages",  # "pages" or "chapters"
    max_wait_time: int = 1800,
    check_interval: int = 3,  # 10초 → 3초로 단축
) -> Dict[str, Any]:
    """
    추출 작업 완료 대기 (진행률, 소요 시간, 남은 시간 표시)
    
    서버 로그 파일을 실시간으로 파싱하여 진행률을 확인합니다.
    DB에 저장되기 전에도 서버 로그에서 진행률을 확인할 수 있습니다.
    
    Args:
        e2e_client: HTTP 클라이언트
        book_id: 책 ID
        target_status: 목표 상태 (예: "page_summarized", "summarized")
        expected_count: 예상 개수 (페이지 수 또는 챕터 수)
        get_current_count_func: 현재 개수를 가져오는 함수 (book_id) -> int
        extraction_type: 추출 타입 ("pages" or "chapters")
        max_wait_time: 최대 대기 시간 (초)
        check_interval: 상태 확인 간격 (초, 기본값 3초)
    
    Returns:
        최종 책 데이터
    """
    start_time = time.time()
    last_count = 0
    last_print_time = 0
    
    print(f"[TEST] Starting {extraction_type} extraction: expected {expected_count} items", flush=True)
    print(f"[TEST] Max wait time: {max_wait_time}s ({max_wait_time//60} min)", flush=True)
    
    while True:
        elapsed = time.time() - start_time
        if elapsed > max_wait_time:
            raise AssertionError(
                f"{extraction_type.capitalize()} extraction timeout after {max_wait_time} seconds "
                f"(book_id={book_id})"
            )
        
        # 상태 확인
        response = e2e_client.get(f"/api/books/{book_id}")
        assert response.status_code == 200
        status = response.json()["status"]
        
        # 서버 로그에서 진행률 확인 (DB 커밋 전에도 확인 가능)
        log_file_path = find_latest_server_log()
        log_progress = parse_progress_from_log(log_file_path, extraction_type) if log_file_path else None
        
        if log_progress:
            # 서버 로그에서 진행률 확인 (실시간, DB 커밋 전에도 가능)
            current_count = log_progress["processed"]
            extracted_count = log_progress["extracted"]
            failed_count = log_progress.get("failed", 0)
            total_count = log_progress["total"]
        else:
            # 로그 파싱 실패 시 DB 조회 (커밋 후에만 가능)
            try:
                current_count = get_current_count_func(book_id)
                extracted_count = current_count
                failed_count = 0
                total_count = expected_count
            except:
                current_count = 0
                extracted_count = 0
                failed_count = 0
                total_count = expected_count
        
        # 진행률 계산
        progress_pct = int(current_count * 100 / total_count) if total_count > 0 else 0
        
        # 평균 시간 및 예상 남은 시간 계산
        if current_count > 0:
            avg_time = elapsed / current_count
            remaining_count = total_count - current_count
            est_remaining = avg_time * remaining_count
            est_min = int(est_remaining // 60)
            est_sec = int(est_remaining % 60)
        else:
            avg_time = 0.0
            est_min = 0
            est_sec = 0
        
        # 출력 조건: 개수 변화 또는 3초마다
        should_print = (
            current_count != last_count or  # 개수 변화
            int(elapsed) - last_print_time >= 3  # 3초마다
        )
        
        if should_print:
            elapsed_min = int(elapsed // 60)
            elapsed_sec = int(elapsed % 60)
            
            # 서버 로그에서 가져온 정보가 있으면 더 상세하게 출력
            if log_progress:
                print(
                    f"[TEST] {extraction_type.capitalize()}: {extracted_count} success, {failed_count} failed, "
                    f"{current_count}/{total_count} total ({progress_pct}%) | "
                    f"Time: {elapsed_min:02d}:{elapsed_sec:02d} | "
                    f"Avg: {avg_time:.1f}s/item | "
                    f"Est: {est_min:02d}:{est_sec:02d}",
                    flush=True
                )
            else:
                print(
                    f"[TEST] {extraction_type.capitalize()}: {current_count}/{expected_count} ({progress_pct}%) | "
                    f"Time: {elapsed_min:02d}:{elapsed_sec:02d} | "
                    f"Avg: {avg_time:.1f}s/item | "
                    f"Est: {est_min:02d}:{est_sec:02d}",
                    flush=True
                )
            last_count = current_count
            last_print_time = int(elapsed)
        
        # 완료 확인
        if status == target_status:
            elapsed_min = int(elapsed // 60)
            elapsed_sec = int(elapsed % 60)
            print(f"[TEST] [OK] {extraction_type.capitalize()} extraction completed (Time: {elapsed_min:02d}:{elapsed_sec:02d})", flush=True)
            return response.json()
        elif status in ["error_summarizing", "failed"]:
            raise AssertionError(f"{extraction_type.capitalize()} extraction failed: status={status}")
        
        time.sleep(check_interval)


def find_cache_files(
    book_id: int, 
    book_title: Optional[str] = None, 
    cache_type: str = "pages"
) -> List[Path]:
    """
    캐시 파일 찾기 (책 제목 폴더 또는 루트 폴더)
    
    Args:
        book_id: 책 ID
        book_title: 책 제목 (None이면 book_{book_id} 사용)
        cache_type: "pages" 또는 "chapters"
    
    Returns:
        캐시 파일 경로 리스트
    """
    summaries_cache_dir = settings.cache_dir / "summaries"
    
    # 1. 책 제목 폴더 확인
    if book_title:
        # SummaryCacheManager와 동일한 로직 사용
        safe_title = "".join(c for c in book_title if c.isalnum() or c in (' ', '-', '_')).strip()
        safe_title = safe_title.replace(' ', '_')[:100]
        book_cache_dir = summaries_cache_dir / safe_title
    else:
        book_cache_dir = summaries_cache_dir / f"book_{book_id}"
    
    # 2. 책 제목 폴더에서 찾기
    if book_cache_dir.exists():
        cache_files = list(book_cache_dir.glob(f"{cache_type}_*.json"))
        if cache_files:
            return cache_files
    
    # 3. 루트 폴더에서 찾기 (fallback)
    cache_files = list(summaries_cache_dir.glob(f"{cache_type}_*.json"))
    return cache_files


def get_cache_file_count(
    book_id: int,
    book_title: Optional[str] = None,
    cache_type: str = "pages"
) -> int:
    """
    캐시 파일 개수 조회
    
    Args:
        book_id: 책 ID
        book_title: 책 제목
        cache_type: "pages" 또는 "chapters"
    
    Returns:
        캐시 파일 개수
    """
    cache_files = find_cache_files(book_id, book_title, cache_type)
    return len(cache_files)


def find_latest_server_log() -> Optional[Path]:
    """최신 서버 로그 파일 찾기"""
    log_dir = Path("data/test_results")
    if not log_dir.exists():
        return None
    
    log_files = list(log_dir.glob("server_*.log"))
    if not log_files:
        return None
    
    # 최신 파일 반환
    return max(log_files, key=lambda p: p.stat().st_mtime)


def parse_progress_from_log(log_file_path: Path, progress_type: str = "pages") -> Optional[Dict[str, Any]]:
    """
    서버 로그에서 진행률 파싱
    
    Args:
        log_file_path: 서버 로그 파일 경로
        progress_type: "pages" 또는 "chapters"
        
    Returns:
        {"extracted": int, "failed": int, "processed": int, "total": int} 또는 
        {"current_step": int, "total_steps": int, "progress_pct": int} (book_report의 경우) 또는 None
    """
    if not log_file_path or not log_file_path.exists():
        return None
    
    try:
        # 파일 크기가 크면 마지막 부분만 읽기 (성능 최적화)
        file_size = log_file_path.stat().st_size
        read_size = min(50000, file_size)  # 마지막 50KB만 읽기
        
        with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
            if file_size > read_size:
                f.seek(file_size - read_size)
                # 첫 줄이 잘릴 수 있으므로 버림
                f.readline()
            
            # 마지막 부분 읽기
            lines = f.readlines()
        
        # 역순으로 검색하여 최신 진행률 찾기
        if progress_type == "book_report":
            # 북 서머리 진행률 파싱 (Book report 또는 Entity synthesis 패턴 모두 지원)
            patterns = [
                r"\[PROGRESS\] Book report: (\d+)/(\d+) steps \((\d+)%\)",
                r"\[PROGRESS\] Entity synthesis: (\d+)/(\d+) steps \((\d+)%\)"
            ]
            for line in reversed(lines):
                for pattern in patterns:
                    match = re.search(pattern, line)
                    if match:
                        current_step, total_steps, progress_pct = map(int, match.groups())
                        return {
                            "current_step": current_step,
                            "total_steps": total_steps,
                            "progress_pct": progress_pct
                        }
        elif progress_type == "pages":
            pattern = r"\[PROGRESS\] Pages: (\d+) success, (\d+) failed, (\d+)/(\d+) total"
            for line in reversed(lines):
                match = re.search(pattern, line)
                if match:
                    extracted, failed, processed, total = map(int, match.groups())
                    return {
                        "extracted": extracted,
                        "failed": failed,
                        "processed": processed,
                        "total": total
                    }
        else:  # chapters
            pattern = r"\[PROGRESS\] Chapters: (\d+) success, (\d+) failed, (\d+) skipped, (\d+)/(\d+) total"
            for line in reversed(lines):
                match = re.search(pattern, line)
                if match:
                    extracted, failed, skipped, processed, total = map(int, match.groups())
                    return {
                        "extracted": extracted,
                        "failed": failed,
                        "skipped": skipped,
                        "processed": processed,
                        "total": total
                    }
    
    except Exception as e:
        # 로그 파싱 실패는 무시 (DB 조회로 fallback)
        pass
    
    return None

