"""SQLAlchemy 데이터베이스 설정"""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from pathlib import Path

# 데이터베이스 디렉토리
DATABASE_DIR = Path(__file__).parent.parent.parent / "data"
DATABASE_DIR.mkdir(exist_ok=True)

# SQLite 데이터베이스 URL
DATABASE_URL = f"sqlite:///{DATABASE_DIR / 'books.db'}"

# SQLAlchemy 엔진 생성
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # SQLite만 필요
    echo=False,
)

# 세션 팩토리
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base 클래스
Base = declarative_base()


def get_db():
    """데이터베이스 세션 의존성"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """데이터베이스 초기화 (테이블 생성)"""
    # 모델 import로 테이블 정의 로드
    from backend.api.models.book import Book, Page, Chapter, PageSummary, ChapterSummary
    
    Base.metadata.create_all(bind=engine)

