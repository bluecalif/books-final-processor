"""FastAPI 메인 애플리케이션"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.api.database import init_db

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


@app.get("/")
async def root():
    """루트 엔드포인트"""
    return {"message": "Books Final Processor API", "version": "0.1.0"}


@app.get("/health")
async def health_check():
    """헬스체크 엔드포인트"""
    return {"status": "ok"}

