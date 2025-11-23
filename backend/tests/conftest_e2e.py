"""E2E 테스트용 픽스처 (실제 서버 실행)"""
import pytest
import subprocess
import time
import httpx
import signal
import os
import sys
from pathlib import Path

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
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info("=" * 80)
    logger.info("[FIXTURE] test_server 시작")
    logger.info(f"[PARAM] TEST_SERVER_URL={TEST_SERVER_URL}")
    
    # 프로젝트 루트 경로
    project_root = Path(__file__).parent.parent.parent
    logger.info(f"[STATE] project_root={project_root}")
    
    # uvicorn 서버 시작
    # Windows 환경 고려: poetry 실행 경로 확인
    import shutil
    poetry_path = shutil.which("poetry")
    if not poetry_path:
        raise RuntimeError("poetry not found in PATH")
    
    logger.info("[CALL] subprocess.Popen() 호출 시작 (uvicorn 서버)")
    logger.info(f"[PARAM] poetry_path={poetry_path}")
    logger.info(f"[PARAM] command=['poetry', 'run', 'uvicorn', 'backend.api.main:app', '--host', '{TEST_SERVER_HOST}', '--port', '{TEST_SERVER_PORT}']")
    
    # Windows에서는 shell=True 사용
    import platform
    is_windows = platform.system() == "Windows"
    
    cmd = ["poetry", "run", "uvicorn", "backend.api.main:app", 
           "--host", TEST_SERVER_HOST, "--port", str(TEST_SERVER_PORT)]
    
    server_process = subprocess.Popen(
        cmd,
        cwd=project_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        shell=is_windows
    )
    
    logger.info(f"[RETURN] subprocess.Popen() 반환값: process_id={server_process.pid}")
    logger.info(f"[STATE] 서버 프로세스 시작됨: PID={server_process.pid}")
    
    # 서버가 시작될 때까지 대기 (최대 10초)
    logger.info("[CALL] 서버 시작 대기 시작")
    max_wait_time = 10
    start_time = time.time()
    
    while True:
        elapsed = time.time() - start_time
        if elapsed > max_wait_time:
            logger.error(f"[ERROR] 서버 시작 타임아웃 ({max_wait_time}초)")
            server_process.terminate()
            server_process.wait()
            raise RuntimeError(f"Test server failed to start within {max_wait_time} seconds")
        
        try:
            # 헬스체크로 서버 준비 확인
            response = httpx.get(f"{TEST_SERVER_URL}/health", timeout=1.0)
            if response.status_code == 200:
                logger.info(f"[RETURN] 서버 시작 완료: {elapsed:.2f}초 소요")
                break
        except (httpx.ConnectError, httpx.TimeoutException):
            time.sleep(0.5)
            continue
    
    logger.info(f"[INFO] Test server running at {TEST_SERVER_URL}")
    logger.info("=" * 80)
    
    yield TEST_SERVER_URL
    
    # 서버 종료
    logger.info("[FIXTURE] test_server 정리 시작")
    logger.info(f"[CALL] server_process.terminate() 호출 시작")
    logger.info(f"[PARAM] process_id={server_process.pid}")
    
    try:
        server_process.terminate()
        # 최대 5초 대기
        try:
            server_process.wait(timeout=5)
            logger.info("[RETURN] server_process.wait() 완료 (정상 종료)")
        except subprocess.TimeoutExpired:
            logger.warning("[WARNING] 서버가 5초 내 종료되지 않음, 강제 종료")
            server_process.kill()
            server_process.wait()
            logger.info("[RETURN] server_process.kill() 완료 (강제 종료)")
    except Exception as e:
        logger.error(f"[ERROR] 서버 종료 중 오류: {e}")
    
    logger.info("[FIXTURE] test_server 정리 완료")
    logger.info("=" * 80)


@pytest.fixture(scope="function")
def e2e_client(test_server):
    """
    E2E 테스트용 HTTP 클라이언트 (실제 서버에 연결)
    
    ⚠️ 중요: TestClient가 아닌 실제 HTTP 클라이언트 사용
    """
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info("=" * 80)
    logger.info("[FIXTURE] e2e_client 시작")
    logger.info(f"[PARAM] test_server={test_server}")
    
    logger.info("[CALL] httpx.Client() 생성 시작")
    logger.info(f"[PARAM] base_url={test_server}, timeout=30.0")
    client = httpx.Client(base_url=test_server, timeout=30.0)
    client_id = id(client)
    logger.info(f"[RETURN] httpx.Client() 반환값: client_id={client_id}")
    
    logger.info("=" * 80)
    yield client
    
    logger.info("[FIXTURE] e2e_client 정리 시작")
    logger.info("[CALL] client.close() 호출 시작")
    client.close()
    logger.info("[RETURN] client.close() 완료")
    logger.info("[FIXTURE] e2e_client 정리 완료")
    logger.info("=" * 80)

