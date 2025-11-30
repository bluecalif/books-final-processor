"""
CSV 파일 파서 - 도서 리스트 및 분야 정보 추출

CSV 파일에서 도서 정보를 파싱하여 구조화된 데이터로 반환합니다.
"""
import csv
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class BookCSVParser:
    """CSV 파일에서 도서 정보를 파싱하는 클래스"""
    
    REQUIRED_COLUMNS = ["일련번호", "Title", "연도", "저자", "분야", "Topic", "요약"]
    
    def __init__(self):
        """초기화"""
        pass
    
    def parse_book_list(self, csv_path: str | Path) -> List[Dict[str, Any]]:
        """
        CSV 파일에서 도서 리스트 파싱
        
        Args:
            csv_path: CSV 파일 경로
            
        Returns:
            도서 정보 리스트
            [
                {
                    "일련번호": "0",
                    "Title": "1000년",
                    "연도": "2022",
                    "저자": "발레리 한센",
                    "분야": "역사/사회",
                    "Topic": "초기 세계화",
                    "요약": "..."
                },
                ...
            ]
        
        Raises:
            FileNotFoundError: CSV 파일이 존재하지 않음
            ValueError: CSV 파일 형식이 올바르지 않음
        """
        csv_path = Path(csv_path)
        
        if not csv_path.exists():
            raise FileNotFoundError(f"CSV 파일이 존재하지 않습니다: {csv_path}")
        
        logger.info(f"[INFO] CSV 파일 파싱 시작: {csv_path}")
        
        books = []
        
        try:
            # UTF-8 BOM 처리
            with open(csv_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                
                # 컬럼 검증
                if not reader.fieldnames:
                    raise ValueError("CSV 파일에 컬럼이 없습니다")
                
                missing_columns = set(self.REQUIRED_COLUMNS) - set(reader.fieldnames)
                if missing_columns:
                    raise ValueError(
                        f"CSV 파일에 필수 컬럼이 없습니다: {missing_columns}. "
                        f"발견된 컬럼: {reader.fieldnames}"
                    )
                
                # 각 행 파싱
                for row_num, row in enumerate(reader, start=2):  # 헤더가 1행이므로 2부터 시작
                    try:
                        # 빈 행 건너뛰기
                        if not any(row.values()):
                            continue
                        
                        # 도서 정보 추출
                        book_data = {
                            "일련번호": self._clean_value(row.get("일련번호", "")),
                            "Title": self._clean_value(row.get("Title", "")),
                            "연도": self._clean_value(row.get("연도", "")),
                            "저자": self._clean_value(row.get("저자", "")),
                            "분야": self._clean_value(row.get("분야", "")),
                            "Topic": self._clean_value(row.get("Topic", "")),
                            "요약": self._clean_value(row.get("요약", "")),
                        }
                        
                        # 제목 검증 (필수)
                        if not book_data["Title"]:
                            logger.warning(f"[WARNING] {row_num}행: Title이 비어있어 건너뜁니다")
                            continue
                        
                        # 분야 정보 검증 및 정규화
                        book_data["분야"] = self._normalize_category(book_data["분야"])
                        
                        books.append(book_data)
                        
                    except Exception as e:
                        logger.error(f"[ERROR] {row_num}행 파싱 실패: {e}")
                        continue
            
            logger.info(f"[INFO] CSV 파일 파싱 완료: {len(books)}개 도서 발견")
            return books
            
        except Exception as e:
            logger.error(f"[ERROR] CSV 파일 파싱 실패: {e}")
            raise
    
    def _clean_value(self, value: Optional[str]) -> str:
        """
        값 정리 (공백 제거)
        
        Args:
            value: 원본 값
            
        Returns:
            정리된 값
        """
        if value is None:
            return ""
        return str(value).strip()
    
    def _normalize_category(self, category: str) -> str:
        """
        분야 정보 정규화 및 검증
        
        Args:
            category: 원본 분야 정보
            
        Returns:
            정규화된 분야 정보 (빈 문자열이면 "미분류" 반환)
        """
        category = self._clean_value(category)
        
        # 빈 값 처리
        if not category:
            logger.debug(f"[DEBUG] 분야 정보가 비어있음: '{category}' -> '미분류'")
            return "미분류"
        
        # 일반적인 분야 목록 (검증용)
        # 실제 분야는 CSV 파일에 따라 다를 수 있으므로 유효성 검사는 완화
        common_categories = [
            "역사/사회",
            "경제/경영",
            "인문/자기계발",
            "과학/기술",
            "문학/예술",
            "종교/철학",
            "기타",
            "미분류",
        ]
        
        # 분야가 유효한 형식인지 간단히 확인 (너무 긴 값 등)
        if len(category) > 50:
            logger.warning(f"[WARNING] 분야 정보가 너무 깁니다: '{category[:50]}...' (50자로 제한)")
            category = category[:50]
        
        return category
    
    def get_books_by_category(self, books: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """
        도서 리스트를 분야별로 그룹화
        
        Args:
            books: 도서 정보 리스트
            
        Returns:
            분야별로 그룹화된 도서 딕셔너리
            {
                "역사/사회": [...],
                "경제/경영": [...],
                ...
            }
        """
        categorized = {}
        
        for book in books:
            category = book.get("분야", "미분류")
            if category not in categorized:
                categorized[category] = []
            categorized[category].append(book)
        
        return categorized
    
    def validate_book_data(self, book_data: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        도서 데이터 유효성 검증
        
        Args:
            book_data: 도서 정보 딕셔너리
            
        Returns:
            (유효 여부, 오류 메시지)
        """
        # 제목 필수
        if not book_data.get("Title"):
            return False, "Title이 없습니다"
        
        # 분야 정보
        category = book_data.get("분야", "")
        if not category:
            logger.debug(f"[DEBUG] 분야 정보가 없습니다: {book_data.get('Title')}")
            # 분야가 없어도 경고만 (필수는 아님)
        
        return True, None


def parse_book_list(csv_path: str | Path) -> List[Dict[str, Any]]:
    """
    CSV 파일에서 도서 리스트 파싱 (편의 함수)
    
    Args:
        csv_path: CSV 파일 경로
        
    Returns:
        도서 정보 리스트
    """
    parser = BookCSVParser()
    return parser.parse_book_list(csv_path)

