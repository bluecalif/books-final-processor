"""
이미 처리된 도서 확인 모듈

DB에서 이미 구조 분석이 완료된 도서를 조회하고, CSV의 제목과 매칭합니다.
"""
import logging
import re
from typing import List, Set
from sqlalchemy.orm import Session

from backend.api.models.book import Book, BookStatus

logger = logging.getLogger(__name__)


def normalize_title(title: str) -> str:
    """
    제목 정규화 (매칭을 위해)
    
    - 공백 제거
    - 특수문자 제거 (% 등)
    - 숫자, 한글, 영문만 남기기
    """
    if not title:
        return ""
    
    # 공백 제거, 앞뒤 공백 제거
    normalized = title.strip().replace(" ", "").replace("　", "")  # 전각/반각 공백 모두
    
    # 특수 케이스: "90년대생" → "90년생" (CSV와 DB 불일치 해결)
    normalized = normalized.replace("90년대생", "90년생")
    
    # 특수문자 제거 (% 등) - 숫자, 한글, 영문만 남기기
    normalized = re.sub(r'[^0-9가-힣a-zA-Z]', '', normalized)
    
    return normalized


class ProcessedBooksChecker:
    """이미 처리된 도서 확인 클래스"""
    
    def __init__(self):
        """초기화"""
        pass
    
    def get_processed_books(self, db_session: Session) -> List[Book]:
        """
        DB에서 이미 구조 분석이 완료된 도서 조회
        
        Args:
            db_session: 데이터베이스 세션
            
        Returns:
            이미 처리된 Book 리스트 (status >= 'structured')
        """
        # STRUCTURED 이상의 상태인 도서 조회
        processed_books = db_session.query(Book).filter(
            Book.status.in_([
                BookStatus.STRUCTURED,
                BookStatus.PAGE_SUMMARIZED,
                BookStatus.SUMMARIZED,
            ])
        ).all()
        
        logger.info(f"[INFO] 처리된 도서 {len(processed_books)}개 발견")
        return processed_books
    
    def get_processed_titles(self, db_session: Session) -> Set[str]:
        """
        이미 처리된 도서의 제목 리스트 (정규화된 제목)
        
        Args:
            db_session: 데이터베이스 세션
            
        Returns:
            정규화된 제목 Set
        """
        processed_books = self.get_processed_books(db_session)
        
        normalized_titles = set()
        for book in processed_books:
            if book.title:
                normalized = normalize_title(book.title)
                if normalized:
                    normalized_titles.add(normalized)
        
        logger.info(f"[INFO] 처리된 도서 제목 {len(normalized_titles)}개 (정규화 후)")
        return normalized_titles
    
    def is_book_processed(self, csv_title: str, db_session: Session) -> bool:
        """
        CSV 제목이 이미 처리된 도서인지 확인
        
        Args:
            csv_title: CSV의 제목
            db_session: 데이터베이스 세션
            
        Returns:
            이미 처리되었으면 True
        """
        csv_normalized = normalize_title(csv_title)
        if not csv_normalized:
            return False
        
        processed_titles = self.get_processed_titles(db_session)
        return csv_normalized in processed_titles
    
    def find_matching_processed_book(
        self, csv_title: str, db_session: Session
    ) -> Book | None:
        """
        CSV 제목과 매칭되는 처리된 도서 찾기
        
        Args:
            csv_title: CSV의 제목
            db_session: 데이터베이스 세션
            
        Returns:
            매칭된 Book 객체 또는 None
        """
        csv_normalized = normalize_title(csv_title)
        if not csv_normalized:
            return None
        
        processed_books = self.get_processed_books(db_session)
        
        for book in processed_books:
            if not book.title:
                continue
            
            db_normalized = normalize_title(book.title)
            
            # 정확히 일치
            if csv_normalized == db_normalized:
                return book
            
            # 부분 일치 (CSV 제목이 DB 제목에 포함되거나 그 반대)
            if csv_normalized in db_normalized or db_normalized in csv_normalized:
                # 너무 짧은 제목은 제외 (예: "1" 같은 것)
                if len(csv_normalized) >= 3:
                    logger.debug(
                        f"[DEBUG] 부분 일치: CSV '{csv_title}' <-> DB '{book.title}'"
                    )
                    return book
        
        return None


def get_processed_books(db_session: Session) -> List[Book]:
    """
    DB에서 이미 구조 분석이 완료된 도서 조회 (편의 함수)
    
    Args:
        db_session: 데이터베이스 세션
        
    Returns:
        이미 처리된 Book 리스트
    """
    checker = ProcessedBooksChecker()
    return checker.get_processed_books(db_session)


def get_processed_titles(db_session: Session) -> Set[str]:
    """
    이미 처리된 도서의 제목 리스트 (편의 함수)
    
    Args:
        db_session: 데이터베이스 세션
        
    Returns:
        정규화된 제목 Set
    """
    checker = ProcessedBooksChecker()
    return checker.get_processed_titles(db_session)

