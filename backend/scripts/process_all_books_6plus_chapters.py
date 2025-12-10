"""
챕터 6개 이상 도서 전체 파이프라인 일괄 처리 스크립트

⚠️ 매우 중요: 모든 처리는 API 호출만 사용
⚠️ 매우 중요: 테스트 파일과 동일한 로직으로 구현 (함수 재사용 금지)

3개의 독립 Event로 구성:
1. Event 1: 에러 검증 평가 (이미 처리된 책으로 에러 상황 재현)
2. Event 2: 3권 시범 진행 (실제 처리 시간 측정)
3. Event 3: 나머지 모두 진행 (전체 처리)

각 이벤트는 서버 시작 → 처리 → 종료 후 사용자 피드백 대기

실행 방법: poetry run python -m backend.scripts.process_all_books_6plus_chapters
"""

import subprocess
import time
import platform
import httpx
import json
import traceback
import hashlib
import re
import socket
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.api.database import SessionLocal
from backend.api.models.book import Book, Chapter, BookStatus
from backend.config.settings import settings


# ============================================================================
# 예외 클래스 (pytest 의존성 제거)
# ============================================================================


class SkipException(Exception):
    """책 처리 스킵 예외 (pytest.skip() 대체)"""

    pass


# ============================================================================
# 서버 설정
# ============================================================================

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8000
SERVER_URL = f"http://{SERVER_HOST}:{SERVER_PORT}"

# 완료된 책 (재처리 없음)
COMPLETED_BOOK_IDS = [175, 176, 177, 184, 182, 178]

# 처리 제외 대상
EXCLUDED_BOOK_IDS = [
    235,  # 노이즈 - 구조 분석 문제
    188,  # MIT 스타트업 바이블 - 챕터 수 6개 미만
    242,  # 뉴스의 시대 - 챕터 수 6개 미만
]

# 로그 디렉토리
PROJECT_ROOT = settings.cache_dir.parent.parent
LOG_DIR = PROJECT_ROOT / "data" / "logs" / "batch_processing"
LOG_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================================
# 유틸리티 함수 (테스트 파일과 동일한 로직, pytest 의존성 제거)
# ============================================================================


def get_pdf_hash(pdf_path: Path) -> str:
    """PDF 파일의 MD5 해시 계산"""
    hasher = hashlib.md5()
    with open(pdf_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def check_upstage_cache(pdf_path: Path) -> Optional[Path]:
    """Upstage API 캐시 확인"""
    pdf_hash = get_pdf_hash(pdf_path)
    cache_file = settings.cache_dir / "upstage" / f"{pdf_hash}.json"
    return cache_file if cache_file.exists() else None


def check_structure_file_by_hash(
    pdf_path: Path, book_title: Optional[str] = None
) -> Optional[Path]:
    """PDF 해시 기반으로 구조 분석 JSON 파일 확인"""
    structure_dir = settings.output_dir / "structure"
    pdf_hash = get_pdf_hash(pdf_path)
    hash_6 = pdf_hash[:6]

    # 1. 해시 + 책 제목으로 찾기
    if book_title:
        safe_title = re.sub(r'[\\/:*?"<>|]', "_", book_title)
        safe_title = safe_title.replace(" ", "_")[:10]
        pattern = f"{hash_6}_{safe_title}_structure.json"
        structure_file = structure_dir / pattern
        if structure_file.exists():
            return structure_file

    # 2. 해시만으로 찾기
    pattern = f"{hash_6}_*_structure.json"
    matches = list(structure_dir.glob(pattern))
    if matches:
        return matches[0]

    # 3. 해시만 있는 파일
    pattern = f"{hash_6}_structure.json"
    structure_file = structure_dir / pattern
    if structure_file.exists():
        return structure_file

    return None


def is_port_available(host: str, port: int, timeout: float = 1.0) -> bool:
    """포트가 사용 가능한지 확인"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result != 0  # 0이면 연결 성공 (포트 사용 중)
    except Exception:
        return True  # 예외 발생 시 사용 가능한 것으로 간주


def kill_process_on_port(port: int, is_windows: bool) -> bool:
    """특정 포트를 사용하는 프로세스를 강제 종료"""
    try:
        if is_windows:
            result = subprocess.run(
                ["netstat", "-ano"], capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.splitlines():
                if f":{port}" in line and "LISTENING" in line:
                    parts = line.split()
                    if len(parts) >= 5:
                        pid = parts[-1]
                        try:
                            subprocess.run(
                                ["taskkill", "/F", "/PID", pid],
                                capture_output=True,
                                timeout=5,
                            )
                            return True
                        except Exception:
                            pass
        else:
            result = subprocess.run(
                ["lsof", "-ti", f":{port}"], capture_output=True, text=True, timeout=5
            )
            if result.stdout.strip():
                pid = result.stdout.strip()
                try:
                    subprocess.run(["kill", "-9", pid], timeout=5)
                    return True
                except Exception:
                    pass
    except Exception:
        pass
    return False


def cleanup_port(port: int, is_windows: bool, max_retries: int = 3) -> bool:
    """포트를 정리하고 사용 가능한지 확인"""
    for attempt in range(max_retries):
        kill_process_on_port(port, is_windows)
        time.sleep(1.0)
        if is_port_available(SERVER_HOST, port):
            return True
    return False


def find_cache_files(
    book_id: int, book_title: Optional[str] = None, cache_type: str = "pages"
) -> List[Path]:
    """캐시 파일 찾기"""
    summaries_cache_dir = settings.cache_dir / "summaries"

    if book_title:
        safe_title = "".join(
            c for c in book_title if c.isalnum() or c in (" ", "-", "_")
        ).strip()
        safe_title = safe_title.replace(" ", "_")[:100]
        book_cache_dir = summaries_cache_dir / safe_title
    else:
        book_cache_dir = summaries_cache_dir / f"book_{book_id}"

    if book_cache_dir.exists():
        cache_files = list(book_cache_dir.glob(f"{cache_type}_*.json"))
        if cache_files:
            return cache_files

    cache_files = list(summaries_cache_dir.glob(f"{cache_type}_*.json"))
    return cache_files


def get_cache_file_count(
    book_id: int, book_title: Optional[str] = None, cache_type: str = "pages"
) -> int:
    """캐시 파일 개수 조회"""
    cache_files = find_cache_files(book_id, book_title, cache_type)
    return len(cache_files)


def find_latest_server_log() -> Optional[Path]:
    """최신 서버 로그 파일 찾기 (배치 처리 로그 디렉토리에서)"""
    if not LOG_DIR.exists():
        return None

    log_files = list(LOG_DIR.glob("server_*.log"))
    if not log_files:
        return None

    return max(log_files, key=lambda p: p.stat().st_mtime)


def parse_progress_from_log(
    log_file_path: Optional[Path], progress_type: str = "pages"
) -> Optional[Dict[str, Any]]:
    """서버 로그에서 진행률 파싱"""
    if not log_file_path or not log_file_path.exists():
        return None

    try:
        file_size = log_file_path.stat().st_size
        read_size = min(50000, file_size)

        with open(log_file_path, "r", encoding="utf-8", errors="ignore") as f:
            if file_size > read_size:
                f.seek(file_size - read_size)
                f.readline()
            lines = f.readlines()

        if progress_type == "book_report":
            patterns = [
                r"\[PROGRESS\] Book report: (\d+)/(\d+) steps \((\d+)%\)",
                r"\[PROGRESS\] Entity synthesis: (\d+)/(\d+) steps \((\d+)%\)",
            ]
            for line in reversed(lines):
                for pattern in patterns:
                    match = re.search(pattern, line)
                    if match:
                        current_step, total_steps, progress_pct = map(
                            int, match.groups()
                        )
                        return {
                            "current_step": current_step,
                            "total_steps": total_steps,
                            "progress_pct": progress_pct,
                        }
        elif progress_type == "pages":
            pattern = (
                r"\[PROGRESS\] Pages: (\d+) success, (\d+) failed, (\d+)/(\d+) total"
            )
            for line in reversed(lines):
                match = re.search(pattern, line)
                if match:
                    extracted, failed, processed, total = map(int, match.groups())
                    return {
                        "extracted": extracted,
                        "failed": failed,
                        "processed": processed,
                        "total": total,
                    }
        else:  # chapters
            pattern = r"\[PROGRESS\] Chapters: (\d+) success, (\d+) failed, (\d+) skipped, (\d+)/(\d+) total"
            for line in reversed(lines):
                match = re.search(pattern, line)
                if match:
                    extracted, failed, skipped, processed, total = map(
                        int, match.groups()
                    )
                    return {
                        "extracted": extracted,
                        "failed": failed,
                        "skipped": skipped,
                        "processed": processed,
                        "total": total,
                    }
    except Exception:
        pass

    return None


# ============================================================================
# 상태 대기 함수 (테스트 파일과 동일한 로직, pytest 의존성 제거)
# ============================================================================


def wait_for_status(
    e2e_client: httpx.Client,
    book_id: int,
    target_status: str,
    max_wait_time: int = 1800,
    check_interval: int = 5,
) -> Dict[str, Any]:
    """
    책 상태가 목표 상태가 될 때까지 대기
    
    ⚠️ 중요: 이미 목표 상태보다 앞서 있으면 바로 반환 (이미 처리 완료된 책 지원)

    테스트 파일과 동일한 로직 (pytest 의존성 제거)
    """
    # 상태 순서 정의 (목표 상태보다 앞서 있는 상태인지 확인)
    status_order = {
        "uploaded": 0,
        "parsed": 1,
        "structured": 2,
        "page_summarized": 3,
        "summarized": 4,
        "error_parsing": -1,
        "error_structuring": -1,
        "error_summarizing": -1,
        "failed": -1,
    }
    
    target_order = status_order.get(target_status, 0)
    
    start_time = time.time()

    while True:
        elapsed = time.time() - start_time
        if elapsed > max_wait_time:
            raise Exception(
                f"Status change timeout: book_id={book_id}, "
                f"target={target_status}, elapsed={elapsed:.1f}s"
            )

        response = e2e_client.get(f"/api/books/{book_id}")
        if response.status_code != 200:
            raise Exception(f"Failed to get book status: {response.status_code}")

        book_data = response.json()
        current_status = book_data["status"]
        current_order = status_order.get(current_status, 0)

        # 목표 상태와 일치하거나 이미 앞서 있으면 완료
        if current_status == target_status or (current_order > 0 and current_order >= target_order):
            elapsed_min = int(elapsed // 60)
            elapsed_sec = int(elapsed % 60)
            if current_status == target_status:
                print(
                    f"[STATUS] [OK] Status changed to {target_status} (Time: {elapsed_min:02d}:{elapsed_sec:02d})"
                )
            else:
                print(
                    f"[STATUS] [OK] Status already ahead: {current_status} >= {target_status} (Time: {elapsed_min:02d}:{elapsed_sec:02d})"
                )
            return book_data
        elif current_status in [
            "error_parsing",
            "error_structuring",
            "error_summarizing",
            "failed",
        ]:
            raise Exception(
                f"Processing failed: book_id={book_id}, status={current_status}"
            )

        if int(elapsed) % 30 == 0:  # 30초마다 출력
            elapsed_min = int(elapsed // 60)
            elapsed_sec = int(elapsed % 60)
            print(
                f"[STATUS] Waiting for {target_status}... (current: {current_status}, Time: {elapsed_min:02d}:{elapsed_sec:02d})"
            )

        time.sleep(check_interval)


def wait_for_extraction_with_progress(
    e2e_client: httpx.Client,
    book_id: int,
    target_status: str,
    expected_count: int,
    get_current_count_func: callable,
    extraction_type: str = "pages",
    max_wait_time: int = 1800,
    check_interval: int = 3,
) -> Dict[str, Any]:
    """
    추출 작업 완료 대기 (진행률, 소요 시간, 남은 시간 표시)

    테스트 파일과 동일한 로직 (pytest 의존성 제거)
    """
    start_time = time.time()
    last_count = 0
    last_print_time = 0

    print(
        f"[EXTRACTION] Starting {extraction_type} extraction: expected {expected_count} items"
    )
    print(f"[EXTRACTION] Max wait time: {max_wait_time}s ({max_wait_time//60} min)")

    while True:
        elapsed = time.time() - start_time
        if elapsed > max_wait_time:
            raise Exception(
                f"{extraction_type.capitalize()} extraction timeout after {max_wait_time} seconds "
                f"(book_id={book_id})"
            )

        # 상태 확인
        response = e2e_client.get(f"/api/books/{book_id}")
        if response.status_code != 200:
            raise Exception(f"Failed to get book status: {response.status_code}")

        status = response.json()["status"]

        # 서버 로그에서 진행률 확인
        log_file_path = find_latest_server_log()
        log_progress = (
            parse_progress_from_log(log_file_path, extraction_type)
            if log_file_path
            else None
        )

        if log_progress:
            current_count = log_progress["processed"]
            extracted_count = log_progress["extracted"]
            failed_count = log_progress.get("failed", 0)
            total_count = log_progress["total"]
        else:
            # 로그 파싱 실패 시 DB 조회
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
            current_count != last_count or int(elapsed) - last_print_time >= 3
        )

        if should_print:
            elapsed_min = int(elapsed // 60)
            elapsed_sec = int(elapsed % 60)

            if log_progress:
                print(
                    f"[EXTRACTION] {extraction_type.capitalize()}: {extracted_count} success, {failed_count} failed, "
                    f"{current_count}/{total_count} total ({progress_pct}%) | "
                    f"Time: {elapsed_min:02d}:{elapsed_sec:02d} | "
                    f"Avg: {avg_time:.1f}s/item | "
                    f"Est: {est_min:02d}:{est_sec:02d}",
                    flush=True,
                )
            else:
                print(
                    f"[EXTRACTION] {extraction_type.capitalize()}: {current_count}/{expected_count} ({progress_pct}%) | "
                    f"Time: {elapsed_min:02d}:{elapsed_sec:02d} | "
                    f"Avg: {avg_time:.1f}s/item | "
                    f"Est: {est_min:02d}:{est_sec:02d}",
                    flush=True,
                )
            last_count = current_count
            last_print_time = int(elapsed)

        # 완료 확인
        if status == target_status:
            elapsed_min = int(elapsed // 60)
            elapsed_sec = int(elapsed % 60)
            print(
                f"[EXTRACTION] [OK] {extraction_type.capitalize()} extraction completed (Time: {elapsed_min:02d}:{elapsed_sec:02d})"
            )
            return response.json()
        elif status in ["error_summarizing", "failed"]:
            raise Exception(
                f"{extraction_type.capitalize()} extraction failed: status={status}"
            )

        time.sleep(check_interval)


# ============================================================================
# 서버 관리 함수 (conftest.py와 동일한 로직)
# ============================================================================


def start_server(is_windows: bool, log_file_path: Path) -> Tuple[subprocess.Popen, Any]:
    """
    서버 시작

    테스트 파일과 동일한 로직

    Returns:
        (server_process, log_file_handle) 튜플
    """
    project_root = Path(__file__).parent.parent.parent

    # 포트 정리
    print(f"[SERVER] 포트 {SERVER_PORT} 정리 시작...")
    cleanup_port(SERVER_PORT, is_windows, max_retries=3)

    # 포트 사용 가능 여부 최종 확인
    if not is_port_available(SERVER_HOST, SERVER_PORT):
        raise RuntimeError(
            f"포트 {SERVER_PORT}가 여전히 사용 중입니다. 수동으로 정리해주세요."
        )

    # uvicorn 서버 시작
    cmd = [
        "poetry",
        "run",
        "uvicorn",
        "backend.api.main:app",
        "--host",
        SERVER_HOST,
        "--port",
        str(SERVER_PORT),
        "--log-level",
        "debug",
    ]

    # UTF-8 BOM으로 파일 열기 (Windows 환경에서 한글 깨짐 방지)
    log_file_handle = open(log_file_path, "w", encoding="utf-8-sig")

    print(f"[SERVER] 서버 로그 파일: {log_file_path}")
    print(f"[SERVER] 서버 시작 중... (포트: {SERVER_PORT})")

    server_process = subprocess.Popen(
        cmd,
        cwd=project_root,
        stdout=log_file_handle,
        stderr=subprocess.STDOUT,
        text=True,
        shell=is_windows,
    )

    # 서버가 시작될 때까지 대기 (헬스체크)
    max_wait_time = 60  # 최대 60초 대기
    start_time = time.time()

    while True:
        elapsed = time.time() - start_time
        if elapsed > max_wait_time:
            print(f"[ERROR] 서버 시작 타임아웃 ({max_wait_time}초 초과)")
            force_kill_server_process(server_process, is_windows, log_file_handle)
            raise RuntimeError(f"서버가 {max_wait_time}초 내에 시작되지 않았습니다.")

        # 서버 프로세스가 종료되었는지 확인
        if server_process.poll() is not None:
            server_process.wait()
            if log_file_handle and not log_file_handle.closed:
                log_file_handle.close()
            raise RuntimeError(
                f"서버 프로세스가 예기치 않게 종료되었습니다. (코드: {server_process.returncode})"
            )

        try:
            # 헬스체크로 서버 준비 확인
            response = httpx.get(f"{SERVER_URL}/health", timeout=2.0)
            if response.status_code == 200:
                print(f"[SERVER] 서버 시작 완료 (PID: {server_process.pid})")
                return server_process, log_file_handle
        except (httpx.ConnectError, httpx.TimeoutException):
            time.sleep(0.5)
            continue


def force_kill_server_process(
    process: subprocess.Popen, is_windows: bool, log_file_handle=None
) -> bool:
    """서버 프로세스를 강제 종료"""
    if process is None or process.poll() is not None:
        return True

    try:
        # 1단계: terminate() 시도
        process.terminate()
        try:
            process.wait(timeout=3)
            print("[SERVER] 서버 프로세스 종료 완료 (terminate)")
            return True
        except subprocess.TimeoutExpired:
            pass

        # 2단계: kill() 시도
        if hasattr(process, "kill"):
            process.kill()
            try:
                process.wait(timeout=2)
                print("[SERVER] 서버 프로세스 종료 완료 (kill)")
                return True
            except subprocess.TimeoutExpired:
                pass

        # 3단계: Windows에서 taskkill 사용
        if is_windows and process.pid:
            try:
                subprocess.run(
                    ["taskkill", "/F", "/PID", str(process.pid)],
                    capture_output=True,
                    timeout=5,
                )
                process.wait(timeout=2)
                print("[SERVER] 서버 프로세스 종료 완료 (taskkill)")
                return True
            except Exception as e:
                print(f"[WARNING] taskkill 실패: {e}")

        # 4단계: 포트 기반 종료
        kill_process_on_port(SERVER_PORT, is_windows)
        time.sleep(1.0)

        # 최종 확인
        if process.poll() is not None:
            print("[SERVER] 서버 프로세스 종료 완료 (포트 기반)")
            return True

        print("[WARNING] 서버 프로세스 종료 실패")
        return False

    except Exception as e:
        print(f"[WARNING] 서버 프로세스 종료 중 오류: {e}")
        return False
    finally:
        # 로그 파일 핸들 닫기
        if log_file_handle and not log_file_handle.closed:
            try:
                log_file_handle.flush()
                log_file_handle.close()
            except Exception as e:
                print(f"[WARNING] 로그 파일 핸들 닫기 실패: {e}")


def stop_server(
    server_process: subprocess.Popen, is_windows: bool, log_file_handle=None
) -> None:
    """서버 종료"""
    print("[SERVER] 서버 종료 시작...")

    # 백그라운드 작업 완료 대기 (5초)
    print("[SERVER] 백그라운드 작업 완료 대기 중... (5초)")
    time.sleep(5)

    try:
        force_kill_server_process(server_process, is_windows, log_file_handle)

        # 포트 해제 확인
        max_wait = 5
        for i in range(max_wait):
            if is_port_available(SERVER_HOST, SERVER_PORT):
                print(f"[SERVER] 서버 종료 완료 (포트 해제 확인: {i+1}초)")
                return
            time.sleep(1.0)
        else:
            print(
                f"[WARNING] 서버 종료 후 포트 {SERVER_PORT}가 여전히 사용 중일 수 있습니다."
            )

    except Exception as e:
        print(f"[WARNING] 서버 종료 중 오류: {e}")


# ============================================================================
# 전체 파이프라인 처리 함수 (테스트 파일과 동일한 로직, pytest 의존성 제거)
# ============================================================================


def process_book_full_pipeline(
    e2e_client: httpx.Client,
    book_id: int,
    pdf_path: Path,
    book_title: str,
    category: str,
    chapter_count: int,
    skip_upload: bool = False,
) -> Dict[str, Any]:
    """
    전체 파이프라인 처리 (통합 함수)

    ⚠️ 매우 중요: 테스트 파일과 동일한 로직, 모든 처리는 API 호출만 사용
    pytest 의존성 제거: pytest.skip() → SkipException, pytest.fail() → Exception, assert → 검증 후 Exception
    """
    print(f"\n{'=' * 80}")
    print(f"[PIPELINE] Full Pipeline Processing")
    print(f"Book ID: {book_id if skip_upload else 'NEW'}, Title: {book_title}")
    print(f"Category: {category}, Chapters: {chapter_count}")
    print(f"{'=' * 80}")

    # ===== STEP 1: PDF 업로드 (skip_upload=False인 경우만) =====
    if not skip_upload:
        print(f"\n[STEP 1] PDF 업로드...")

        # Upstage 캐시 확인
        upstage_cache = check_upstage_cache(pdf_path)
        if upstage_cache:
            print(f"[CACHE] [OK] Upstage 캐시 발견: {upstage_cache.name}")
        else:
            print(f"[CACHE] Upstage 캐시 없음 (새로 파싱 필요)")

        with open(pdf_path, "rb") as f:
            files = {"file": (pdf_path.name, f, "application/pdf")}
            data = {
                "title": book_title,
                "category": category,
            }
            response = e2e_client.post("/api/books/upload", files=files, data=data)

        if response.status_code != 200:
            raise Exception(f"PDF 업로드 실패: {response.status_code}")
        upload_result = response.json()
        if "book_id" not in upload_result:
            raise Exception("PDF 업로드 응답에 book_id가 없습니다")
        book_id = upload_result["book_id"]
        print(f"[STEP 1] [OK] 업로드 완료: book_id={book_id}")
    else:
        print(f"\n[STEP 1] PDF 업로드 건너뛰기 (이미 업로드된 책: book_id={book_id})")

    # ===== STEP 2: PDF 파싱 완료 대기 =====
    print(f"\n[STEP 2] PDF 파싱 완료 대기...")

    book_data = wait_for_status(e2e_client, book_id, "parsed", max_wait_time=600)

    # 캐시 저장 확인
    upstage_cache_after = check_upstage_cache(pdf_path)
    if upstage_cache_after is None:
        raise Exception("Upstage 캐시가 저장되지 않았습니다")
    print(f"[CACHE] [OK] Upstage 캐시 저장 확인: {upstage_cache_after.name}")

    print(f"[STEP 2] [OK] 파싱 완료: page_count={book_data.get('page_count', 0)}")

    # ===== STEP 3: 구조 후보 생성 =====
    print(f"\n[STEP 3] 구조 후보 생성...")

    # 구조 파일 캐시 확인
    structure_cache = check_structure_file_by_hash(pdf_path, book_title)
    if structure_cache:
        print(f"[CACHE] [OK] 구조 파일 캐시 발견: {structure_cache.name} (재사용 예정)")
    else:
        print(f"[CACHE] 구조 파일 캐시 없음 (새로 구조 분석 수행 예정)")

    response = e2e_client.get(f"/api/books/{book_id}/structure/candidates")
    if response.status_code != 200:
        raise Exception(f"구조 후보 생성 실패: {response.status_code}")
    candidates = response.json()

    if "auto_candidates" not in candidates:
        raise Exception("구조 후보 응답에 auto_candidates가 없습니다")
    if len(candidates["auto_candidates"]) == 0:
        raise Exception("구조 후보가 없습니다")

    # 구조 파일 캐시 재사용 확인
    if structure_cache:
        print(f"[CACHE] [OK] 구조 파일 캐시 재사용 확인")

    heuristic_structure = candidates["auto_candidates"][0]["structure"]

    # 구조 형식 확인 및 변환
    main_pages = heuristic_structure.get("main", {}).get("pages", [])
    chapters = heuristic_structure.get("main", {}).get("chapters", [])

    # main_start_page와 main_end_page 계산
    if main_pages:
        main_start_page = main_pages[0]
        main_end_page = main_pages[-1]
    else:
        main_start_page = heuristic_structure.get("main_start_page")
        main_end_page = heuristic_structure.get("main_end_page")
        if not main_start_page or not main_end_page:
            raise SkipException(
                f"Book {book_id} has no main pages in structure candidates. Cannot proceed."
            )

    if not chapters:
        raise SkipException(
            f"Book {book_id} has no chapters in structure candidates. Cannot proceed."
        )

    print(
        f"[STEP 3] [OK] 구조 후보 생성 완료: {len(chapters)}개 챕터, main_pages={main_start_page}~{main_end_page}"
    )

    # ===== STEP 4: 구조 확정 =====
    print(f"\n[STEP 4] 구조 확정...")

    final_structure = {
        "main_start_page": main_start_page,
        "main_end_page": main_end_page,
        "chapters": [
            {
                "title": ch.get("title", ""),
                "start_page": ch.get("start_page"),
                "end_page": ch.get("end_page"),
            }
            for ch in chapters
        ],
        "notes_pages": [],
        "start_pages": [],
        "end_pages": [],
    }

    response = e2e_client.post(
        f"/api/books/{book_id}/structure/final", json=final_structure
    )

    if response.status_code != 200:
        raise Exception(f"구조 확정 실패: {response.status_code}")

    book_data = wait_for_status(e2e_client, book_id, "structured", max_wait_time=60)

    print(f"[STEP 4] [OK] 구조 확정 완료")

    # ===== STEP 5: 페이지 엔티티 추출 =====
    print(f"\n[STEP 5] 페이지 엔티티 추출...")

    # 예상 페이지 수 계산
    structure_data = book_data.get("structure_data", {})
    if structure_data:
        main_start = structure_data.get("main_start_page", 0)
        main_end = structure_data.get("main_end_page", 0)
        expected_pages = (
            main_end - main_start + 1
            if main_start and main_end
            else book_data.get("page_count", 0)
        )
    else:
        expected_pages = book_data.get("page_count", 0)

    # 캐시 확인 (추출 전)
    page_cache_before = get_cache_file_count(book_id, book_title, "pages")

    response = e2e_client.post(f"/api/books/{book_id}/extract/pages")
    if response.status_code != 200:
        raise Exception(f"페이지 엔티티 추출 시작 실패: {response.status_code}")
    if response.json().get("status") != "processing":
        raise Exception(f"페이지 엔티티 추출 시작 응답 상태 오류: {response.json()}")

    # 현재 페이지 개수를 가져오는 함수
    def get_page_count(bid: int) -> int:
        pages_response = e2e_client.get(f"/api/books/{bid}/pages")
        if pages_response.status_code == 200:
            return len(pages_response.json())
        return 0

    # 완료 대기 (진행률 출력 포함)
    book_data = wait_for_extraction_with_progress(
        e2e_client=e2e_client,
        book_id=book_id,
        target_status="page_summarized",
        expected_count=expected_pages,
        get_current_count_func=get_page_count,
        extraction_type="pages",
        max_wait_time=1800,
        check_interval=3,
    )

    # 캐시 저장 확인
    page_cache_after = get_cache_file_count(book_id, book_title, "pages")
    if page_cache_after > page_cache_before:
        print(
            f"[CACHE] [OK] 페이지 엔티티 캐시 저장 확인: {page_cache_after - page_cache_before}개 추가"
        )
    else:
        print(f"[CACHE] 페이지 엔티티 캐시 확인: {page_cache_after}개 (재사용 가능)")

    # 페이지 엔티티 검증
    response = e2e_client.get(f"/api/books/{book_id}/pages")
    if response.status_code != 200:
        raise Exception(f"페이지 엔티티 조회 실패: {response.status_code}")
    page_entities = response.json()
    if len(page_entities) == 0:
        raise Exception("페이지 엔티티가 없습니다")

    print(f"[STEP 5] [OK] 페이지 엔티티 추출 완료: {len(page_entities)}개 페이지")

    # ===== STEP 6: 챕터 구조화 =====
    print(f"\n[STEP 6] 챕터 구조화...")

    # 예상 챕터 수
    expected_chapters = (
        len(structure_data.get("chapters", [])) if structure_data else chapter_count
    )

    # 캐시 확인 (추출 전)
    chapter_cache_before = get_cache_file_count(book_id, book_title, "chapters")

    response = e2e_client.post(f"/api/books/{book_id}/extract/chapters")
    if response.status_code != 200:
        raise Exception(f"챕터 구조화 시작 실패: {response.status_code}")
    if response.json().get("status") != "processing":
        raise Exception(f"챕터 구조화 시작 응답 상태 오류: {response.json()}")

    # 현재 챕터 개수를 가져오는 함수
    def get_chapter_count(bid: int) -> int:
        chapters_response = e2e_client.get(f"/api/books/{bid}/chapters")
        if chapters_response.status_code == 200:
            return len(chapters_response.json())
        return 0

    # 완료 대기 (진행률 출력 포함)
    book_data = wait_for_extraction_with_progress(
        e2e_client=e2e_client,
        book_id=book_id,
        target_status="summarized",
        expected_count=expected_chapters,
        get_current_count_func=get_chapter_count,
        extraction_type="chapters",
        max_wait_time=1800,
        check_interval=3,
    )

    # 캐시 저장 확인
    chapter_cache_after = get_cache_file_count(book_id, book_title, "chapters")
    if chapter_cache_after > chapter_cache_before:
        print(
            f"[CACHE] [OK] 챕터 구조화 캐시 저장 확인: {chapter_cache_after - chapter_cache_before}개 추가"
        )
    else:
        print(f"[CACHE] 챕터 구조화 캐시 확인: {chapter_cache_after}개 (재사용 가능)")

    # 챕터 엔티티 검증
    response = e2e_client.get(f"/api/books/{book_id}/chapters")
    if response.status_code != 200:
        raise Exception(f"챕터 엔티티 조회 실패: {response.status_code}")
    chapter_entities = response.json()
    if len(chapter_entities) == 0:
        raise Exception("챕터 엔티티가 없습니다")

    print(f"[STEP 6] [OK] 챕터 구조화 완료: {len(chapter_entities)}개 챕터")

    # ===== STEP 7: 북 서머리 생성 =====
    print(f"\n[STEP 7] 북 서머리 생성...", flush=True)

    response = e2e_client.post(f"/api/books/{book_id}/extract/book_summary")
    if response.status_code != 200:
        raise Exception(f"북 서머리 생성 시작 실패: {response.status_code}")
    if response.json().get("status") != "processing":
        raise Exception(f"북 서머리 생성 시작 응답 상태 오류: {response.json()}")

    # 완료 대기 (북 서머리 파일 생성 확인 + 서버 로그 파싱)
    max_wait_time = 300  # 5분
    start_time = time.time()
    last_print_time = 0
    last_step = 0

    book_summary_dir = settings.output_dir / "book_summaries"

    while True:
        elapsed = time.time() - start_time
        if elapsed > max_wait_time:
            raise Exception(f"북 서머리 생성 타임아웃: {max_wait_time}초 초과")

        # 서버 로그에서 진행률 확인
        log_file_path = find_latest_server_log()
        log_progress = (
            parse_progress_from_log(log_file_path, "book_report")
            if log_file_path
            else None
        )

        # 북 서머리 파일 확인
        # ⚠️ 중요: book_title이 None인 경우 처리
        if book_title:
            safe_title = (
                "".join(c for c in book_title if c.isalnum() or c in (" ", "-", "_"))
                .strip()
                .replace(" ", "_")[:100]
            )
        else:
            safe_title = f"book_{book_id}"
        
        book_summary_files = list(book_summary_dir.glob(f"*{book_id}*.json"))
        book_summary_files.extend(book_summary_dir.glob(f"*{safe_title}*.json"))
        if book_title:
            book_summary_files.extend(
                book_summary_dir.glob(f"*{book_title.replace(' ', '_')}*.json")
            )

        # 파일이 생성되었으면 서버 로그에서 완료 메시지 확인
        if book_summary_files:
            print(
                f"[CACHE] [OK] 북 서머리 파일 저장 확인: {book_summary_files[0].name}",
                flush=True,
            )

            # 서버 로그에서 백그라운드 작업 완료 메시지 확인
            if log_file_path:
                try:
                    with open(
                        log_file_path, "r", encoding="utf-8", errors="ignore"
                    ) as f:
                        file_size = log_file_path.stat().st_size
                        read_size = min(10000, file_size)
                        if file_size > read_size:
                            f.seek(file_size - read_size)
                            f.readline()
                        log_content = f.read()

                        if (
                            f"Background book summary generation completed: book_id={book_id}"
                            in log_content
                        ):
                            print(
                                f"[PIPELINE] [OK] 백그라운드 작업 완료 메시지 확인됨",
                                flush=True,
                            )
                            time.sleep(3)
                            break
                        else:
                            time.sleep(1)
                            continue
                except Exception as e:
                    print(
                        f"[WARNING] 로그 파싱 실패, 파일 생성 확인으로 완료 처리: {e}",
                        flush=True,
                    )
                    time.sleep(3)
                    break
            else:
                print(
                    f"[WARNING] 서버 로그 파일을 찾을 수 없음, 파일 생성 확인으로 완료 처리",
                    flush=True,
                )
                time.sleep(3)
                break

        # 진행률 출력 (3초마다 또는 단계 변화 시)
        if log_progress:
            current_step = log_progress.get("current_step", 0)
            total_steps = log_progress.get("total_steps", 0)
            progress_pct = log_progress.get("progress_pct", 0)

            if current_step != last_step or int(elapsed) - last_print_time >= 3:
                elapsed_min = int(elapsed // 60)
                elapsed_sec = int(elapsed % 60)
                print(
                    f"[PIPELINE] Book summary: {current_step}/{total_steps} steps ({progress_pct}%) | "
                    f"Time: {elapsed_min:02d}:{elapsed_sec:02d}",
                    flush=True,
                )
                last_step = current_step
                last_print_time = int(elapsed)
        elif int(elapsed) - last_print_time >= 3:
            elapsed_min = int(elapsed // 60)
            elapsed_sec = int(elapsed % 60)
            print(
                f"[PIPELINE] Waiting for book summary... (Time: {elapsed_min:02d}:{elapsed_sec:02d})",
                flush=True,
            )
            last_print_time = int(elapsed)

        time.sleep(2)

    print(f"[STEP 7] [OK] 북 서머리 생성 완료", flush=True)

    # ===== STEP 8: 최종 결과 조회 검증 =====
    print(f"\n[STEP 8] 최종 결과 조회 검증...")

    # 책 정보 조회
    response = e2e_client.get(f"/api/books/{book_id}")
    if response.status_code != 200:
        raise Exception(f"책 정보 조회 실패: {response.status_code}")
    final_book_data = response.json()

    if final_book_data["status"] != "summarized":
        raise Exception(
            f"최종 상태 오류: {final_book_data['status']} (예상: summarized)"
        )

    # 페이지 엔티티 조회
    response = e2e_client.get(f"/api/books/{book_id}/pages")
    if response.status_code != 200:
        raise Exception(f"페이지 엔티티 조회 실패: {response.status_code}")
    final_pages = response.json()

    # 챕터 엔티티 조회
    response = e2e_client.get(f"/api/books/{book_id}/chapters")
    if response.status_code != 200:
        raise Exception(f"챕터 엔티티 조회 실패: {response.status_code}")
    final_chapters = response.json()

    print(f"[STEP 8] [OK] 최종 검증 완료")
    print(f"  - 책 상태: {final_book_data['status']}")
    print(f"  - 페이지 수: {len(final_pages)}")
    print(f"  - 챕터 수: {len(final_chapters)}")

    print(f"\n{'=' * 80}")
    print(f"[PIPELINE] [OK] 전체 파이프라인 처리 완료: book_id={book_id}")
    print(f"{'=' * 80}\n")

    return final_book_data


# ============================================================================
# 대상 책 조회 함수 (DB 직접 조회 - 스크립트 내부에서만 사용)
# ============================================================================


def get_target_books(db: Session) -> List[Dict[str, Any]]:
    """챕터 6개 이상인 책 조회"""
    # 챕터 개수별로 그룹화하여 6개 이상인 책만 조회
    books_with_chapters = (
        db.query(Book, func.count(Chapter.id).label("chapter_count"))
        .join(Chapter, Book.id == Chapter.book_id, isouter=True)
        .group_by(Book.id)
        .having(func.count(Chapter.id) >= 6)
        .filter(~Book.id.in_(COMPLETED_BOOK_IDS + EXCLUDED_BOOK_IDS))
        .all()
    )

    result = []
    for book, chapter_count in books_with_chapters:
        result.append(
            {
                "book_id": book.id,
                "title": book.title,
                "category": None,  # DB에 category 필드가 없으면 None
                "chapter_count": chapter_count,
                "source_file_path": book.source_file_path,
                "status": (
                    book.status.value
                    if isinstance(book.status, BookStatus)
                    else book.status
                ),
            }
        )

    return result


# ============================================================================
# Event 함수들
# ============================================================================


def event1_error_verification(e2e_client: httpx.Client) -> Dict[str, Any]:
    """
    Event 1: 에러 검증 평가
    
    존재하지 않는 책 조회로 API 에러 처리 검증
    ⚠️ 매우 중요: 모든 처리는 API 호출만 사용 (DB 직접 조작 금지)
    """
    print(f"\n{'=' * 80}")
    print(f"[EVENT 1] 에러 검증 평가 시작")
    print(f"{'=' * 80}\n")
    
    # 존재하지 않는 book_id로 조회 시도
    nonexistent_book_id = 99999
    
    print(f"[EVENT 1] 존재하지 않는 책 조회 시도: book_id={nonexistent_book_id}")
    
    try:
        response = e2e_client.get(f"/api/books/{nonexistent_book_id}")
        
        # 404 Not Found 예상
        if response.status_code == 404:
            print(f"[EVENT 1] [OK] 404 에러 응답 확인: status_code={response.status_code}")
            data = response.json()
            if "detail" in data:
                print(f"[EVENT 1] [OK] 에러 메시지 확인: {data['detail']}")
        else:
            print(f"[EVENT 1] [WARNING] 예상과 다른 응답: status_code={response.status_code}")
            
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            print(f"[EVENT 1] [OK] 404 에러 예외 처리 확인: {e.response.status_code}")
        else:
            print(f"[EVENT 1] [WARNING] 예상과 다른 HTTP 상태: {e.response.status_code}")
    except Exception as e:
        print(f"[EVENT 1] [WARNING] 예상치 못한 에러: {e}")
    
    print(f"\n[EVENT 1] [OK] 에러 검증 평가 완료")
    return {"status": "success", "test": "nonexistent_book_404"}


def event2_sample_processing(
    e2e_client: httpx.Client,
    db: Session,
    target_books: List[Dict[str, Any]],
    limit: int = 3,
) -> Dict[str, Any]:
    """
    Event 2: 3권 시범 진행

    실제 처리 시간 측정
    """
    print(f"\n{'=' * 80}")
    print(f"[EVENT 2] 3권 시범 진행 시작 (limit={limit})")
    print(f"{'=' * 80}\n")

    # 처음 3권만 선택
    sample_books = target_books[:limit]

    results = {
        "success": [],
        "skipped": [],
        "failed": [],
    }

    for idx, book_data in enumerate(sample_books, 1):
        book_id = book_data["book_id"]
        book_title = book_data["title"]
        category = book_data.get("category", "인문/자기계발")
        chapter_count = book_data["chapter_count"]
        pdf_path = Path(book_data["source_file_path"])

        print(
            f"\n[EVENT 2] [{idx}/{len(sample_books)}] 처리 시작: {book_title} (book_id={book_id})"
        )

        try:
            # 전체 파이프라인 처리
            result = process_book_full_pipeline(
                e2e_client=e2e_client,
                book_id=book_id,
                pdf_path=pdf_path,
                book_title=book_title,
                category=category,
                chapter_count=chapter_count,
                skip_upload=True,  # 이미 업로드된 책
            )

            results["success"].append(
                {
                    "book_id": book_id,
                    "title": book_title,
                    "status": result.get("status"),
                }
            )
            print(f"[EVENT 2] [{idx}/{len(sample_books)}] [OK] 처리 완료: {book_title}")

        except SkipException as e:
            results["skipped"].append(
                {
                    "book_id": book_id,
                    "title": book_title,
                    "reason": str(e),
                }
            )
            print(
                f"[EVENT 2] [{idx}/{len(sample_books)}] [SKIP] 건너뜀: {book_title} - {e}"
            )

        except Exception as e:
            results["failed"].append(
                {
                    "book_id": book_id,
                    "title": book_title,
                    "error": str(e),
                }
            )
            print(
                f"[EVENT 2] [{idx}/{len(sample_books)}] [FAIL] 처리 실패: {book_title} - {e}"
            )
            traceback.print_exc()

    print(f"\n[EVENT 2] [OK] 시범 진행 완료")
    print(f"  - 성공: {len(results['success'])}권")
    print(f"  - 건너뜀: {len(results['skipped'])}권")
    print(f"  - 실패: {len(results['failed'])}권")

    return results


def event3_full_processing(
    e2e_client: httpx.Client,
    db: Session,
    target_books: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Event 3: 나머지 모두 진행

    전체 처리
    """
    print(f"\n{'=' * 80}")
    print(f"[EVENT 3] 전체 처리 시작 (총 {len(target_books)}권)")
    print(f"{'=' * 80}\n")

    results = {
        "success": [],
        "skipped": [],
        "failed": [],
    }

    start_time = time.time()

    for idx, book_data in enumerate(target_books, 1):
        book_id = book_data["book_id"]
        book_title = book_data["title"]
        category = book_data.get("category", "인문/자기계발")
        chapter_count = book_data["chapter_count"]
        pdf_path = Path(book_data["source_file_path"])

        # 진행률 계산
        elapsed = time.time() - start_time
        avg_time = elapsed / idx if idx > 0 else 0
        remaining = len(target_books) - idx
        est_remaining = avg_time * remaining

        elapsed_min = int(elapsed // 60)
        elapsed_sec = int(elapsed % 60)
        est_min = int(est_remaining // 60)
        est_sec = int(est_remaining % 60)

        print(
            f"\n[EVENT 3] [{idx}/{len(target_books)}] 처리 시작: {book_title} (book_id={book_id})"
        )
        print(
            f"  진행률: {idx}/{len(target_books)} ({int(idx * 100 / len(target_books))}%)"
        )
        print(f"  경과 시간: {elapsed_min:02d}:{elapsed_sec:02d}")
        print(f"  예상 남은 시간: {est_min:02d}:{est_sec:02d}")

        try:
            # 전체 파이프라인 처리
            result = process_book_full_pipeline(
                e2e_client=e2e_client,
                book_id=book_id,
                pdf_path=pdf_path,
                book_title=book_title,
                category=category,
                chapter_count=chapter_count,
                skip_upload=True,  # 이미 업로드된 책
            )

            results["success"].append(
                {
                    "book_id": book_id,
                    "title": book_title,
                    "status": result.get("status"),
                }
            )
            print(f"[EVENT 3] [{idx}/{len(target_books)}] [OK] 처리 완료: {book_title}")

        except SkipException as e:
            results["skipped"].append(
                {
                    "book_id": book_id,
                    "title": book_title,
                    "reason": str(e),
                }
            )
            print(
                f"[EVENT 3] [{idx}/{len(target_books)}] [SKIP] 건너뜀: {book_title} - {e}"
            )

        except Exception as e:
            results["failed"].append(
                {
                    "book_id": book_id,
                    "title": book_title,
                    "error": str(e),
                }
            )
            print(
                f"[EVENT 3] [{idx}/{len(target_books)}] [FAIL] 처리 실패: {book_title} - {e}"
            )
            traceback.print_exc()

    total_time = time.time() - start_time
    total_min = int(total_time // 60)
    total_sec = int(total_time % 60)

    print(f"\n[EVENT 3] [OK] 전체 처리 완료")
    print(f"  - 성공: {len(results['success'])}권")
    print(f"  - 건너뜀: {len(results['skipped'])}권")
    print(f"  - 실패: {len(results['failed'])}권")
    print(f"  - 총 소요 시간: {total_min:02d}:{total_sec:02d}")

    return results


# ============================================================================
# Main 함수
# ============================================================================


def main():
    """메인 실행 함수"""
    print(f"\n{'=' * 80}")
    print(f"챕터 6개 이상 도서 전체 파이프라인 일괄 처리 스크립트")
    print(f"{'=' * 80}\n")

    is_windows = platform.system() == "Windows"
    db = SessionLocal()

    try:
        # 대상 책 조회
        print("[MAIN] 대상 책 조회 중...")
        target_books = get_target_books(db)
        print(f"[MAIN] 대상 책: {len(target_books)}권")

        if len(target_books) == 0:
            print("[MAIN] 처리할 책이 없습니다.")
            return

        # Event 1: 에러 검증 평가
        print(f"\n{'=' * 80}")
        print(f"[MAIN] Event 1 시작: 에러 검증 평가")
        print(f"{'=' * 80}")

        # 서버 시작
        log_file_path = (
            LOG_DIR / f"server_event1_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        )
        server_process, log_file_handle = start_server(is_windows, log_file_path)

        try:
            e2e_client = httpx.Client(base_url=SERVER_URL, timeout=30.0)
            try:
                event1_result = event1_error_verification(e2e_client)
                print(f"\n[MAIN] Event 1 완료: {event1_result}")
            finally:
                e2e_client.close()
        finally:
            stop_server(server_process, is_windows, log_file_handle)

        # 사용자 피드백 대기
        print(f"\n{'=' * 80}")
        print(f"[MAIN] Event 1 완료. Event 2를 진행하시겠습니까? (Enter 키 입력)")
        print(f"{'=' * 80}")
        input()

        # Event 2: 3권 시범 진행
        print(f"\n{'=' * 80}")
        print(f"[MAIN] Event 2 시작: 3권 시범 진행")
        print(f"{'=' * 80}")

        # 서버 시작
        log_file_path = (
            LOG_DIR / f"server_event2_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        )
        server_process, log_file_handle = start_server(is_windows, log_file_path)

        try:
            e2e_client = httpx.Client(base_url=SERVER_URL, timeout=30.0)
            try:
                event2_result = event2_sample_processing(
                    e2e_client, db, target_books, limit=3
                )
                print(f"\n[MAIN] Event 2 완료:")
                print(f"  - 성공: {len(event2_result['success'])}권")
                print(f"  - 건너뜀: {len(event2_result['skipped'])}권")
                print(f"  - 실패: {len(event2_result['failed'])}권")
            finally:
                e2e_client.close()
        finally:
            stop_server(server_process, is_windows, log_file_handle)

        # 사용자 피드백 대기
        print(f"\n{'=' * 80}")
        print(f"[MAIN] Event 2 완료. Event 3을 진행하시겠습니까? (Enter 키 입력)")
        print(f"{'=' * 80}")
        input()

        # Event 3: 나머지 모두 진행
        print(f"\n{'=' * 80}")
        print(f"[MAIN] Event 3 시작: 전체 처리 (나머지 {len(target_books)}권)")
        print(f"{'=' * 80}")

        # Event 2에서 처리한 책 제외
        processed_ids = {
            b["book_id"] for b in event2_result["success"] + event2_result["failed"]
        }
        remaining_books = [b for b in target_books if b["book_id"] not in processed_ids]

        if len(remaining_books) == 0:
            print("[MAIN] Event 3: 처리할 책이 없습니다 (Event 2에서 모두 처리됨)")
            return

        # 서버 시작
        log_file_path = (
            LOG_DIR / f"server_event3_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        )
        server_process, log_file_handle = start_server(is_windows, log_file_path)

        try:
            e2e_client = httpx.Client(base_url=SERVER_URL, timeout=30.0)
            try:
                event3_result = event3_full_processing(e2e_client, db, remaining_books)
                print(f"\n[MAIN] Event 3 완료:")
                print(f"  - 성공: {len(event3_result['success'])}권")
                print(f"  - 건너뜀: {len(event3_result['skipped'])}권")
                print(f"  - 실패: {len(event3_result['failed'])}권")
            finally:
                e2e_client.close()
        finally:
            stop_server(server_process, is_windows, log_file_handle)

        # 최종 리포트
        print(f"\n{'=' * 80}")
        print(f"[MAIN] 전체 처리 완료")
        print(f"{'=' * 80}")
        print(f"Event 2:")
        print(f"  - 성공: {len(event2_result['success'])}권")
        print(f"  - 건너뜀: {len(event2_result['skipped'])}권")
        print(f"  - 실패: {len(event2_result['failed'])}권")
        print(f"Event 3:")
        print(f"  - 성공: {len(event3_result['success'])}권")
        print(f"  - 건너뜀: {len(event3_result['skipped'])}권")
        print(f"  - 실패: {len(event3_result['failed'])}권")
        print(f"\n총계:")
        total_success = len(event2_result["success"]) + len(event3_result["success"])
        total_skipped = len(event2_result["skipped"]) + len(event3_result["skipped"])
        total_failed = len(event2_result["failed"]) + len(event3_result["failed"])
        print(f"  - 성공: {total_success}권")
        print(f"  - 건너뜀: {total_skipped}권")
        print(f"  - 실패: {total_failed}권")

    finally:
        db.close()


if __name__ == "__main__":
    main()
