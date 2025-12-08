"""
E2E 테스트 공통 유틸리티 함수

진행률, 소요 시간, 남은 시간 표시를 위한 공통 함수
"""
import time
import httpx
from typing import Dict, Any, Optional


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
            print(f"[TEST] ✅ Status changed to {target_status} (Time: {elapsed_min:02d}:{elapsed_sec:02d})")
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
            print(f"[TEST] Waiting for {target_status}... (current: {current_status}, Time: {elapsed_min:02d}:{elapsed_sec:02d})")
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
    check_interval: int = 10,
) -> Dict[str, Any]:
    """
    추출 작업 완료 대기 (진행률, 소요 시간, 남은 시간 표시)
    
    Args:
        e2e_client: HTTP 클라이언트
        book_id: 책 ID
        target_status: 목표 상태 (예: "page_summarized", "summarized")
        expected_count: 예상 개수 (페이지 수 또는 챕터 수)
        get_current_count_func: 현재 개수를 가져오는 함수 (book_id) -> int
        extraction_type: 추출 타입 ("pages" or "chapters")
        max_wait_time: 최대 대기 시간 (초)
        check_interval: 상태 확인 간격 (초)
    
    Returns:
        최종 책 데이터
    """
    start_time = time.time()
    last_count = 0
    last_print_time = 0
    
    print(f"[TEST] Starting {extraction_type} extraction: expected {expected_count} items")
    print(f"[TEST] Max wait time: {max_wait_time}s ({max_wait_time//60} min)")
    
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
        
        # 현재 개수 확인
        try:
            current_count = get_current_count_func(book_id)
        except:
            current_count = 0
        
        # 진행률 계산
        progress_pct = int(current_count * 100 / expected_count) if expected_count > 0 else 0
        
        # 평균 시간 및 예상 남은 시간 계산
        if current_count > 0:
            avg_time = elapsed / current_count
            remaining_count = expected_count - current_count
            est_remaining = avg_time * remaining_count
            est_min = int(est_remaining // 60)
            est_sec = int(est_remaining % 60)
        else:
            avg_time = 0.0
            est_min = 0
            est_sec = 0
        
        # 출력 조건: 개수 변화 또는 10초마다
        should_print = (
            current_count != last_count or  # 개수 변화
            int(elapsed) - last_print_time >= 10  # 10초마다
        )
        
        if should_print:
            elapsed_min = int(elapsed // 60)
            elapsed_sec = int(elapsed % 60)
            
            print(
                f"[TEST] {extraction_type.capitalize()}: {current_count}/{expected_count} ({progress_pct}%) | "
                f"Time: {elapsed_min:02d}:{elapsed_sec:02d} | "
                f"Avg: {avg_time:.1f}s/item | "
                f"Est: {est_min:02d}:{est_sec:02d}"
            )
            last_count = current_count
            last_print_time = int(elapsed)
        
        # 완료 확인
        if status == target_status:
            elapsed_min = int(elapsed // 60)
            elapsed_sec = int(elapsed % 60)
            print(f"[TEST] ✅ {extraction_type.capitalize()} extraction completed (Time: {elapsed_min:02d}:{elapsed_sec:02d})")
            return response.json()
        elif status in ["error_summarizing", "failed"]:
            raise AssertionError(f"{extraction_type.capitalize()} extraction failed: status={status}")
        
        time.sleep(check_interval)

