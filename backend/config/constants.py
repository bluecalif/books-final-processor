"""애플리케이션 상수"""

import re

# 챕터 탐지 패턴 (ChapterDetector용)
CHAPTER_PATTERNS = {
    # 한글 패턴
    "korean_chapter_full": (re.compile(r"^제\s*(\d+)\s*장"), 50),  # 제1장
    "korean_chapter_short": (re.compile(r"^(\d+)\s*장$"), 50),  # 1장, 2장 (단독)
    "korean_part": (re.compile(r"^제\s*(\d+)\s*부"), 55),  # 제1부 (상위 계층)
    # 영어 패턴
    "english_chapter": (re.compile(r"^CHAPTER\s+(\d+)", re.IGNORECASE), 50),
    "english_part": (re.compile(r"^Part\s+(\d+)", re.IGNORECASE), 55),
    # 번호 패턴
    "numbered_title": (
        re.compile(r"^(\d+)\.\s+([가-힣a-zA-Z].{3,})"),
        35,
    ),  # 1. 제목
}

# 본문 시작 키워드 (ContentBoundaryDetector용, 확장됨)
START_KEYWORDS = [
    # 한글
    "작가",
    "작가 소개",
    "저자",
    "저자 소개",
    "저자소개",
    "지은이",
    "추천",
    "추천의 글",
    "추천사",
    "추천하는 말",
    "서문",
    "머리말",
    "프롤로그",
    "들어가며",
    "들어가는 글",
    "들어가는 말",
    "처음으로",
    "작품 소개",
    "작품소개",
    "옮긴이",
    "서론",
    "감수",
    "시작하며",
    "감사의 글",
    "감사",
    "헌정",
    "표지",
    "판권",
    "저작권",
    "차례",
    "목차",
    # 영어
    "author",
    "about the author",
    "recommendation",
    "foreword",
    "preface",
    "prologue",
    "introduction",
    "acknowledgment",
    "dedication",
    "copyright",
    "contents",
    "table of contents",
]

# 본문 끝 키워드 (ContentBoundaryDetector용, 확장됨)
END_KEYWORDS = [
    # 한글
    "맺음말",
    "맺는 글",
    "맺는 말",
    "끝맺음",
    "나가며",
    "마치며",
    "에필로그",
    "결론",
    "주",
    "각주",
    "미주",
    "참고 주",
    "주석",
    "참고문헌",
    "참고 문헌",
    "참고자료",
    "문헌",
    "bibliography",
    "부록",
    "색인",
    "용어집",
    "출판",
    "출판사",
    "출판정보",
    "판권",
    "출처",
    "해설",
    "감사",
    "닫는 글",
    "도서정보",
    "찾아보기",
    "감수",
    # 영어
    "epilogue",
    "conclusion",
    "closing",
    "endnote",
    "endnotes",
    "notes",
    "footnote",
    "references",
    "bibliography",
    "appendix",
    "appendices",
    "index",
    "glossary",
    "publisher",
    "publishing",
]

# 본문 시작 패턴 (ContentBoundaryDetector용)
MAIN_START_PATTERNS = [
    # 챕터 패턴
    re.compile(r"제\s*1\s*장"),  # 제1장
    re.compile(r"제\s*1\s*부"),  # 제1부
    re.compile(r"CHAPTER\s+[1I]", re.IGNORECASE),  # Chapter 1, Chapter I
    re.compile(r"Part\s+[1I]", re.IGNORECASE),  # Part 1, Part I
    re.compile(r"^1\s*장"),  # 1장
    re.compile(r"^1\.\s+[가-힣a-zA-Z]"),  # 1. 제목
    # 서론 패턴
    re.compile(r"^서론$"),  # 서론
    re.compile(r"^Introduction$", re.IGNORECASE),  # Introduction
    re.compile(r"^들어가며$"),  # 들어가며
    re.compile(r"^시작하며$"),  # 시작하며
]

# 본문 단락 최소 길이
MIN_PARAGRAPH_LENGTH = 100

# 챕터 탐지 임계값 (ChapterDetector용)
MIN_CHAPTER_SPACING = 3  # 챕터 간 최소 페이지 간격
LARGE_FONT_THRESHOLD = 16  # 큰 폰트 기준 (16px 이상)
SCORE_THRESHOLD = 55  # 챕터 확정 점수

# 요약 설정
SUMMARY_MAX_LENGTH = 500  # 토큰
SUMMARY_TEMPERATURE = 0.7

# Upstage API 설정
MAX_PAGES_PER_REQUEST = 100  # API 제한

