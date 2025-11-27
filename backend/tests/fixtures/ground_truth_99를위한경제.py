"""
Ground Truth 데이터: 99%를 위한 경제.pdf

이 파일은 구조 분석 정확도 평가를 위한 Ground Truth 데이터입니다.
사용자가 제공한 정확한 구조 정보를 담고 있습니다.

⚠️ 중요:
- 정확도 평가는 페이지 번호만 사용합니다 (main_start_page, main_end_page, chapter start_page/end_page)
- 챕터 제목(title)은 참고용이며, 정확도 평가에 사용하지 않습니다
- E2E 테스트에서는 실제 파싱 결과의 페이지 번호와 Ground Truth의 페이지 번호를 비교합니다
"""

GROUND_TRUTH = {
    "book_title": "99를위한경제",
    "pdf_file": "99%를 위한 경제.pdf",
    "original_pages": 278,  # 원본 PDF 페이지 수
    "total_pages": 556,  # 양면 분리 후 페이지 수 (원본 * 2)
    "main_start_page": 41,
    "main_end_page": 348,  # 종문 시작 페이지 - 1
    "chapters": [
        {
            "number": 1,
            "title": "제1장",  # 참고용 (정확도 평가에 사용하지 않음)
            "start_page": 41,
            "end_page": 68,
        },
        {
            "number": 2,
            "title": "제2장",  # 참고용 (정확도 평가에 사용하지 않음)
            "start_page": 69,
            "end_page": 124,
        },
        {
            "number": 3,
            "title": "제3장",  # 참고용 (정확도 평가에 사용하지 않음)
            "start_page": 125,
            "end_page": 144,
        },
        {
            "number": 4,
            "title": "제4장",  # 참고용 (정확도 평가에 사용하지 않음)
            "start_page": 145,
            "end_page": 176,
        },
        {
            "number": 5,
            "title": "제5장",  # 참고용 (정확도 평가에 사용하지 않음)
            "start_page": 177,
            "end_page": 256,
        },
        {
            "number": 6,
            "title": "제6장",  # 참고용 (정확도 평가에 사용하지 않음)
            "start_page": 257,
            "end_page": 320,
        },
        {
            "number": 7,
            "title": "제7장",  # 참고용 (정확도 평가에 사용하지 않음)
            "start_page": 321,
            "end_page": 348,
        },
    ],
}

# 정확도 평가 기준 (페이지 오차 허용 범위)
ACCURACY_THRESHOLDS = {
    "heuristic": {
        "main_start_page": 3,  # ±3페이지 오차 허용
        "chapter_start_page": 3,  # ±3페이지 오차 허용
        "chapter_count": 2,  # ±2개 오차 허용
    },
    "llm": {
        "main_start_page": 1,  # ±1페이지 오차 허용
        "chapter_start_page": 2,  # ±2페이지 오차 허용
        "chapter_count": 1,  # ±1개 오차 허용
    },
}
