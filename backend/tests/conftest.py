"""E2E 테스트용 픽스처 (실제 서버 실행)"""
import pytest
import subprocess
import time
import httpx
import os
import socket
from pathlib import Path
import platform
from datetime import datetime

# 테스트 서버 설정
TEST_SERVER_HOST = "127.0.0.1"
TEST_SERVER_PORT = 8001
TEST_SERVER_URL = f"http://{TEST_SERVER_HOST}:{TEST_SERVER_PORT}"


def kill_process_on_port(port: int, is_windows: bool) -> bool:
    """
    특정 포트를 사용하는 프로세스를 강제 종료
    
    Args:
        port: 포트 번호
        is_windows: Windows 환경 여부
    
    Returns:
        프로세스 종료 성공 여부
    """
    try:
        if is_windows:
            # Windows: netstat로 PID 찾기
            result = subprocess.run(
                ["netstat", "-ano"],
                capture_output=True,
                text=True,
                timeout=5
            )
            for line in result.stdout.splitlines():
                if f":{port}" in line and "LISTENING" in line:
                    parts = line.split()
                    if len(parts) >= 5:
                        pid = parts[-1]
                        try:
                            # taskkill로 강제 종료
                            subprocess.run(
                                ["taskkill", "/F", "/PID", pid],
                                capture_output=True,
                                timeout=5
                            )
                            print(f"[CLEANUP] 포트 {port} 사용 프로세스 (PID: {pid}) 종료")
                            return True
                        except Exception as e:
                            print(f"[WARNING] 프로세스 종료 실패 (PID: {pid}): {e}")
        else:
            # Unix: lsof로 PID 찾기
            result = subprocess.run(
                ["lsof", "-ti", f":{port}"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.stdout.strip():
                pid = result.stdout.strip()
                try:
                    subprocess.run(["kill", "-9", pid], timeout=5)
                    print(f"[CLEANUP] 포트 {port} 사용 프로세스 (PID: {pid}) 종료")
                    return True
                except Exception as e:
                    print(f"[WARNING] 프로세스 종료 실패 (PID: {pid}): {e}")
    except Exception as e:
        print(f"[WARNING] 포트 {port} 정리 중 오류: {e}")
    
    return False


def is_port_available(host: str, port: int, timeout: float = 1.0) -> bool:
    """
    포트가 사용 가능한지 확인
    
    Args:
        host: 호스트 주소
        port: 포트 번호
        timeout: 타임아웃 (초)
    
    Returns:
        포트 사용 가능 여부
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result != 0  # 0이면 연결 성공 (포트 사용 중)
    except Exception:
        return True  # 예외 발생 시 사용 가능한 것으로 간주


def cleanup_port(port: int, is_windows: bool, max_retries: int = 3) -> bool:
    """
    포트를 정리하고 사용 가능한지 확인
    
    Args:
        port: 포트 번호
        is_windows: Windows 환경 여부
        max_retries: 최대 재시도 횟수
    
    Returns:
        포트 정리 성공 여부
    """
    for attempt in range(max_retries):
        # 포트 사용 중인 프로세스 종료
        kill_process_on_port(port, is_windows)
        
        # 잠시 대기 (포트 해제 시간)
        time.sleep(1.0)
        
        # 포트 사용 가능 여부 확인
        if is_port_available(TEST_SERVER_HOST, port):
            print(f"[CLEANUP] 포트 {port} 정리 완료 (시도 {attempt + 1}/{max_retries})")
            return True
        
        print(f"[CLEANUP] 포트 {port} 아직 사용 중... (시도 {attempt + 1}/{max_retries})")
    
    print(f"[WARNING] 포트 {port} 정리 실패 (최대 재시도 횟수 초과)")
    return False


def force_kill_server_process(process: subprocess.Popen, is_windows: bool) -> bool:
    """
    서버 프로세스를 강제 종료
    
    Args:
        process: 서버 프로세스
        is_windows: Windows 환경 여부
    
    Returns:
        프로세스 종료 성공 여부
    """
    if process is None or process.poll() is not None:
        return True  # 이미 종료됨
    
    try:
        # 1단계: terminate() 시도
        process.terminate()
        try:
            process.wait(timeout=3)
            print("[CLEANUP] 서버 프로세스 종료 완료 (terminate)")
            return True
        except subprocess.TimeoutExpired:
            pass
        
        # 2단계: kill() 시도
        if hasattr(process, 'kill'):
            process.kill()
            try:
                process.wait(timeout=2)
                print("[CLEANUP] 서버 프로세스 종료 완료 (kill)")
                return True
            except subprocess.TimeoutExpired:
                pass
        
        # 3단계: Windows에서 taskkill 사용
        if is_windows and process.pid:
            try:
                subprocess.run(
                    ["taskkill", "/F", "/PID", str(process.pid)],
                    capture_output=True,
                    timeout=5
                )
                process.wait(timeout=2)
                print("[CLEANUP] 서버 프로세스 종료 완료 (taskkill)")
                return True
            except Exception as e:
                print(f"[WARNING] taskkill 실패: {e}")
        
        # 4단계: 포트 기반 종료
        kill_process_on_port(TEST_SERVER_PORT, is_windows)
        time.sleep(1.0)
        
        # 최종 확인
        if process.poll() is not None:
            print("[CLEANUP] 서버 프로세스 종료 완료 (포트 기반)")
            return True
        
        print("[WARNING] 서버 프로세스 종료 실패")
        return False
        
    except Exception as e:
        print(f"[WARNING] 서버 프로세스 종료 중 오류: {e}")
        return False


@pytest.fixture(scope="session")
def test_server():
    """
    E2E 테스트용 실제 서버 실행
    
    ⚠️ 중요: 프로덕션 플로우와 동일하게 검증하기 위해 실제 서버를 띄움
    """
    # 프로젝트 루트 경로
    project_root = Path(__file__).parent.parent.parent
    
    # Windows 환경 고려
    is_windows = platform.system() == "Windows"
    
    # 1. 테스트 시작 전 포트 정리
    print(f"[TEST_SERVER] 포트 {TEST_SERVER_PORT} 정리 시작...")
    cleanup_port(TEST_SERVER_PORT, is_windows, max_retries=3)
    
    # 포트 사용 가능 여부 최종 확인
    if not is_port_available(TEST_SERVER_HOST, TEST_SERVER_PORT):
        raise RuntimeError(f"포트 {TEST_SERVER_PORT}가 여전히 사용 중입니다. 수동으로 정리해주세요.")
    
    # uvicorn 서버 시작 (로그 레벨 DEBUG로 설정)
    cmd = [
        "poetry", "run", "uvicorn", "backend.api.main:app",
        "--host", TEST_SERVER_HOST,
        "--port", str(TEST_SERVER_PORT),
        "--log-level", "debug"  # DEBUG 레벨 로그 활성화
    ]
    
    # 서버 로그 파일 설정 (UTF-8 BOM 추가로 Windows 환경에서 한글 깨짐 방지)
    log_dir = project_root / "data" / "test_results"
    log_dir.mkdir(parents=True, exist_ok=True)
    server_log_file = log_dir / f"server_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    
    # UTF-8 BOM으로 파일 열기 (Windows 환경에서 한글 깨짐 방지)
    log_file_handle = open(server_log_file, 'w', encoding='utf-8-sig')
    
    print(f"[TEST_SERVER] 서버 로그 파일: {server_log_file}")
    print(f"[TEST_SERVER] 서버 시작 중... (포트: {TEST_SERVER_PORT})")
    
    server_process = subprocess.Popen(
        cmd,
        cwd=project_root,
        stdout=log_file_handle,
        stderr=subprocess.STDOUT,  # stderr도 같은 파일로
        text=True,
        shell=is_windows,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"}  # Python 출력 인코딩 설정
    )
    
    # 서버가 시작될 때까지 대기 (헬스체크)
    max_wait_time = 30  # 최대 30초 대기
    start_time = time.time()
    
    while True:
        elapsed = time.time() - start_time
        if elapsed > max_wait_time:
            # 타임아웃 시 서버 종료
            print(f"[ERROR] 서버 시작 타임아웃 ({max_wait_time}초 초과)")
            force_kill_server_process(server_process, is_windows)
            if log_file_handle and not log_file_handle.closed:
                log_file_handle.close()
            raise RuntimeError(f"Test server failed to start within {max_wait_time} seconds")
        
        # 서버 프로세스가 종료되었는지 확인
        if server_process.poll() is not None:
            # 프로세스가 종료됨 - 에러 로그 확인
            try:
                stderr_output = server_process.stderr.read() if server_process.stderr else None
                if stderr_output:
                    print(f"[ERROR] 서버 stderr: {stderr_output}")
            except:
                pass
            server_process.wait()
            if log_file_handle and not log_file_handle.closed:
                log_file_handle.close()
            raise RuntimeError(f"Test server process exited unexpectedly with code {server_process.returncode}")
        
        try:
            # 헬스체크로 서버 준비 확인
            response = httpx.get(f"{TEST_SERVER_URL}/health", timeout=2.0)
            if response.status_code == 200:
                print(f"[TEST_SERVER] 서버 시작 완료 (PID: {server_process.pid})")
                break
        except (httpx.ConnectError, httpx.TimeoutException):
            time.sleep(0.5)
            continue
    
    yield TEST_SERVER_URL
    
    # 서버 종료 (강제 종료 포함)
    print("[TEST_SERVER] 서버 종료 시작...")
    try:
        force_kill_server_process(server_process, is_windows)
        
        # 포트 해제 확인
        max_wait = 5
        for i in range(max_wait):
            if is_port_available(TEST_SERVER_HOST, TEST_SERVER_PORT):
                print(f"[TEST_SERVER] 서버 종료 완료 (포트 해제 확인: {i+1}초)")
                break
            time.sleep(1.0)
        else:
            print(f"[WARNING] 서버 종료 후 포트 {TEST_SERVER_PORT}가 여전히 사용 중일 수 있습니다.")
        
    except Exception as e:
        print(f"[WARNING] 서버 종료 중 오류: {e}")
    finally:
        # 로그 파일 핸들 닫기
        if log_file_handle and not log_file_handle.closed:
            try:
                log_file_handle.flush()
                log_file_handle.close()
                print("[TEST_SERVER] 로그 파일 핸들 닫기 완료")
            except Exception as e:
                print(f"[WARNING] 로그 파일 핸들 닫기 실패: {e}")


@pytest.fixture(scope="function")
def e2e_client(test_server):
    """
    E2E 테스트용 HTTP 클라이언트 (실제 서버에 연결)
    
    ⚠️ 중요: TestClient가 아닌 실제 HTTP 클라이언트 사용
    """
    client = httpx.Client(base_url=test_server, timeout=30.0)
    yield client
    client.close()

