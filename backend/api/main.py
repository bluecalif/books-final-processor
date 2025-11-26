"""FastAPI 메인 애플리케이션"""
import logging
import sys
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.api.database import init_db
from backend.api.routers import books, structure

# 로깅 설정 (서버 시작 시 초기화)
def setup_logging():
    """
    서버 로깅 설정
    
    ⚠️ 중요: DEBUG 레벨 로그를 표준 출력으로 출력하여 서버 로그 파일에 기록되도록 함
    """
    # 루트 로거 설정
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    
    # 기존 핸들러 제거 (중복 방지)
    root_logger.handlers.clear()
    
    # 표준 출력 핸들러 (서버 로그 파일로 리다이렉트됨)
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.DEBUG)
    
    # 포맷터 설정 (한글 지원)
    formatter = logging.Formatter(
        "[%(asctime)s] %(name)s - %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    stdout_handler.setFormatter(formatter)
    
    root_logger.addHandler(stdout_handler)
    
    # 구조 분석 모듈 로거 레벨 설정
    logging.getLogger("backend.structure").setLevel(logging.DEBUG)
    logging.getLogger("backend.parsers").setLevel(logging.DEBUG)
    
    logger = logging.getLogger(__name__)
    logger.info("[INFO] 서버 로깅 설정 완료 (DEBUG 레벨)")

# 로깅 설정 초기화
setup_logging()

# 데이터베이스 초기화
init_db()

# FastAPI 앱 생성
app = FastAPI(
    title="Books Final Processor API",
    description="도서 PDF 구조 분석 및 서머리 서비스",
    version="0.1.0",
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 개발 환경용, 프로덕션에서는 특정 도메인으로 제한
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(books.router)
app.include_router(structure.router)


@app.get("/")
async def root():
    """루트 엔드포인트"""
    return {"message": "Books Final Processor API", "version": "0.1.0"}


@app.get("/health")
async def health_check():
    """헬스체크 엔드포인트"""
    return {"status": "ok"}

