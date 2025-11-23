"""애플리케이션 상수"""

# 챕터 탐지 패턴
CHAPTER_PATTERNS = [
    r"^제\s*\d+\s*장",  # 제1장
    r"^CHAPTER\s+\d+",  # CHAPTER 1
    r"^\d+\.\s*[^.]+\s*$",  # 1. 제목
]

# 본문 시작/끝 키워드
START_KEYWORDS = ["차례", "contents", "목차", "서문", "preface", "introduction"]
END_KEYWORDS = ["참고문헌", "references", "부록", "appendix", "index", "찾아보기"]

# 요약 설정
SUMMARY_MAX_LENGTH = 500  # 토큰
SUMMARY_TEMPERATURE = 0.7

# Upstage API 설정
MAX_PAGES_PER_REQUEST = 100  # API 제한

