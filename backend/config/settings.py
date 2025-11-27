"""애플리케이션 설정"""

from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    """애플리케이션 설정"""

    # API 키
    upstage_api_key: str
    openai_api_key: str

    # 데이터베이스
    database_url: str = ""

    # 파일 저장 경로
    upload_dir: Path = Path(__file__).parent.parent.parent / "data" / "uploads"
    cache_dir: Path = Path(__file__).parent.parent.parent / "data" / "cache"
    input_dir: Path = (
        Path(__file__).parent.parent.parent / "data" / "input"
    )  # 사용자 입력 PDF 파일
    output_dir: Path = (
        Path(__file__).parent.parent.parent / "data" / "output"
    )  # 구조 분석 결과 등 출력 파일

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",  # .env에 정의되지 않은 필드는 무시
    }


# 전역 설정 인스턴스
settings = Settings()

# 디렉토리 생성
settings.upload_dir.mkdir(parents=True, exist_ok=True)
settings.cache_dir.mkdir(parents=True, exist_ok=True)
settings.input_dir.mkdir(parents=True, exist_ok=True)
settings.output_dir.mkdir(parents=True, exist_ok=True)
