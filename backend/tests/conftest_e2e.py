"""E2E 테스트용 픽스처 (실제 서버 실행)"""
import pytest
import subprocess
import time
import httpx
from pathlib import Path
import platform
from datetime import datetime

# 테스트 서버 설정
TEST_SERVER_HOST = "127.0.0.1"
TEST_SERVER_PORT = 8001
TEST_SERVER_URL = f"http://{TEST_SERVER_HOST}:{TEST_SERVER_PORT}"


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
    
    # uvicorn 서버 시작
    cmd = [
        "poetry", "run", "uvicorn", "backend.api.main:app",
        "--host", TEST_SERVER_HOST,
        "--port", str(TEST_SERVER_PORT)
    ]
    
    # 서버 로그 파일 설정
    log_dir = project_root / "data" / "test_results"
    log_dir.mkdir(parents=True, exist_ok=True)
    server_log_file = log_dir / f"server_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    
    server_process = subprocess.Popen(
        cmd,
        cwd=project_root,
        stdout=open(server_log_file, 'w', encoding='utf-8'),
        stderr=subprocess.STDOUT,  # stderr도 같은 파일로
        text=True,
        shell=is_windows
    )
    
    print(f"[TEST_SERVER] 서버 로그 파일: {server_log_file}")
    
    # 서버가 시작될 때까지 대기 (헬스체크)
    max_wait_time = 30  # 최대 30초 대기
    start_time = time.time()
    
    while True:
        elapsed = time.time() - start_time
        if elapsed > max_wait_time:
            # 타임아웃 시 서버 종료
            server_process.terminate()
            server_process.wait()
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
            raise RuntimeError(f"Test server process exited unexpectedly with code {server_process.returncode}")
        
        try:
            # 헬스체크로 서버 준비 확인
            response = httpx.get(f"{TEST_SERVER_URL}/health", timeout=2.0)
            if response.status_code == 200:
                break
        except (httpx.ConnectError, httpx.TimeoutException):
            time.sleep(0.5)
            continue
    
    yield TEST_SERVER_URL
    
    # 서버 종료
    try:
        server_process.terminate()
        try:
            server_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server_process.kill()
            server_process.wait()
    except Exception as e:
        print(f"[WARNING] 서버 종료 중 오류: {e}")


@pytest.fixture(scope="function")
def e2e_client(test_server):
    """
    E2E 테스트용 HTTP 클라이언트 (실제 서버에 연결)
    
    ⚠️ 중요: TestClient가 아닌 실제 HTTP 클라이언트 사용
    """
    client = httpx.Client(base_url=test_server, timeout=30.0)
    yield client
    client.close()

