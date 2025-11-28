"""
도서 테스트 설정 (외부 Config)

모든 도서의 PDF 파일 경로와 Ground Truth 모듈 정보를 한 곳에 관리합니다.
"""

from pathlib import Path
import importlib

# 프로젝트 루트 경로 (backend/tests/fixtures/book_configs.py -> backend/tests/fixtures -> backend/tests -> backend -> 프로젝트 루트)
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
INPUT_DIR = PROJECT_ROOT / "data" / "input"
FIXTURES_DIR = Path(__file__).parent


def get_ground_truth(module_name: str):
    """Ground Truth 모듈 동적 import"""
    module = importlib.import_module(f"backend.tests.fixtures.{module_name}")
    return module.GROUND_TRUTH, module.ACCURACY_THRESHOLDS


# 모든 도서 설정 (테스트 순서대로)
# ⚠️ 중요: pdf_file은 실제 data/input/ 디렉토리의 파일명과 정확히 일치해야 함
BOOK_CONFIGS = [
    {
        "name": "1등의 통찰",
        "pdf_file": "1등의 통찰.pdf",
        "ground_truth_module": "ground_truth_1등의통찰",
    },
    {
        "name": "3D프린터의모든것",
        "pdf_file": "3D프린터의 모든것.pdf",
        "ground_truth_module": "ground_truth_3D프린터의모든것",
    },
    {
        "name": "90년대생이온다",
        "pdf_file": "90년생이 온다.pdf",
        "ground_truth_module": "ground_truth_90년대생이온다",
    },
    {
        "name": "10년후세계사",
        "pdf_file": "10년후 세계사.pdf",
        "ground_truth_module": "ground_truth_10년후세계사",
    },
    {
        "name": "4차산업혁명전문직의미래",
        "pdf_file": "4차산업혁명 전문직의 미래.pdf",
        "ground_truth_module": "ground_truth_4차산업혁명전문직의미래",
    },
    {
        "name": "12가지인생의법칙",
        "pdf_file": "12가지 인생의 법칙.pdf",
        "ground_truth_module": "ground_truth_12가지인생의법칙",
    },
    {
        "name": "30개도시로읽는세계사",
        "pdf_file": "30개 도시로 읽는 세계사.pdf",
        "ground_truth_module": "ground_truth_30개도시로읽는세계사",
    },
    {
        "name": "10년후이곳은제2의판교",
        "pdf_file": "10년후 이곳은 제2의 판교.pdf",
        "ground_truth_module": "ground_truth_10년후이곳은제2의판교",
    },
    {
        "name": "10년후이곳은제2의강남",
        "pdf_file": "10년후 이곳은 제2의 강남.pdf",
        "ground_truth_module": "ground_truth_10년후이곳은제2의강남",
    },
    {
        "name": "99를위한경제",
        "pdf_file": "99를 위한 경제.pdf",
        "ground_truth_module": "ground_truth_99를위한경제",
    },
]


def get_test_books():
    """
    테스트할 도서 목록 반환

    환경변수:
    - TEST_FIRST_BOOK_ONLY=1: 첫 번째 도서만 반환
    - TEST_FIRST_TWO_BOOKS=1: 첫 번째와 두 번째 도서만 반환
    - TEST_FAILED_BOOKS_ONLY=1: 실패한 책 3권만 반환 (10년후세계사, 12가지인생의법칙, 30개도시로읽는세계사)
    - TEST_10년후세계사_ONLY=1: 10년후세계사만 반환
    - TEST_12가지인생의법칙_ONLY=1: 12가지인생의법칙만 반환
    - 기본값: 모든 도서 반환

    우선순위: TEST_FIRST_BOOK_ONLY > TEST_FIRST_TWO_BOOKS > TEST_10년후세계사_ONLY > TEST_12가지인생의법칙_ONLY > TEST_FAILED_BOOKS_ONLY > 기본값
    """
    import os

    first_only = os.getenv("TEST_FIRST_BOOK_ONLY")
    first_two = os.getenv("TEST_FIRST_TWO_BOOKS")
    test_10년후세계사_only = os.getenv("TEST_10년후세계사_ONLY")
    test_12가지인생의법칙_only = os.getenv("TEST_12가지인생의법칙_ONLY")
    failed_only = os.getenv("TEST_FAILED_BOOKS_ONLY")

    if first_only == "1":
        return BOOK_CONFIGS[:1]
    elif first_two == "1":
        return BOOK_CONFIGS[:2]
    elif test_10년후세계사_only == "1":
        # 10년후세계사만 반환
        return [config for config in BOOK_CONFIGS if config["name"] == "10년후세계사"]
    elif test_12가지인생의법칙_only == "1":
        # 12가지인생의법칙만 반환
        return [config for config in BOOK_CONFIGS if config["name"] == "12가지인생의법칙"]
    elif failed_only == "1":
        # 실패한 책 3권만 반환
        failed_books = ["10년후세계사", "12가지인생의법칙", "30개도시로읽는세계사"]
        return [config for config in BOOK_CONFIGS if config["name"] in failed_books]
    return BOOK_CONFIGS


def get_book_config(book_name: str):
    """도서명으로 설정 조회"""
    for config in BOOK_CONFIGS:
        if config["name"] == book_name:
            return config
    raise ValueError(f"Book config not found: {book_name}")


def get_pdf_path(pdf_file: str) -> Path:
    """PDF 파일 경로 반환"""
    return INPUT_DIR / pdf_file
