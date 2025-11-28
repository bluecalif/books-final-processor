"""
Ground Truth 데이터: 12가지 인생의 법칙.pdf

이 파일은 구조 분석 정확도 평가를 위한 Ground Truth 데이터입니다.
사용자가 제공한 정확한 구조 정보를 담고 있습니다.

⚠️ 중요:
- 정확도 평가는 페이지 번호만 사용합니다 (main_start_page, main_end_page, chapter start_page/end_page)
- 챕터 제목(title)은 참고용이며, 정확도 평가에 사용하지 않습니다
- E2E 테스트에서는 실제 파싱 결과의 페이지 번호와 Ground Truth의 페이지 번호를 비교합니다
"""

GROUND_TRUTH = {
    "book_title": "12가지인생의법칙",
    "pdf_file": "12가지 인생의 법칙.pdf",
    "original_pages": 417,  # 원본 PDF 페이지 수
    "total_pages": 834,  # 양면 분리 후 페이지 수 (원본 * 2)
    "main_start_page": 35,
    "main_end_page": 679,  # 종문 시작 페이지 - 1
    "chapters": [
        {
            "number": 1,
            "title": "제1장",  # 참고용 (정확도 평가에 사용하지 않음)
            "start_page": 35,
            "end_page": 85,  # 86 - 1
        },
        {
            "number": 2,
            "title": "제2장",  # 참고용 (정확도 평가에 사용하지 않음)
            "start_page": 86,  # 수정: 170 → 86
            "end_page": 150,  # 151 - 1
        },
        {
            "number": 3,
            "title": "제3장",  # 참고용 (정확도 평가에 사용하지 않음)
            "start_page": 151,  # 수정: 188 → 151
            "end_page": 187,  # 188 - 1
        },
        {
            "number": 4,
            "title": "제4장",  # 참고용 (정확도 평가에 사용하지 않음)
            "start_page": 188,
            "end_page": 242,  # 243 - 1
        },
        {
            "number": 5,
            "title": "제5장",  # 참고용 (정확도 평가에 사용하지 않음)
            "start_page": 243,
            "end_page": 301,  # 302 - 1
        },
        {
            "number": 6,
            "title": "제6장",  # 참고용 (정확도 평가에 사용하지 않음)
            "start_page": 302,  # 수정: 331 → 302
            "end_page": 329,  # 330 - 1
        },
        {
            "number": 7,
            "title": "제7장",  # 참고용 (정확도 평가에 사용하지 않음)
            "start_page": 330,
            "end_page": 407,  # 408 - 1
        },
        {
            "number": 8,
            "title": "제8장",  # 참고용 (정확도 평가에 사용하지 않음)
            "start_page": 408,
            "end_page": 462,  # 463 - 1
        },
        {
            "number": 9,
            "title": "제9장",  # 참고용 (정확도 평가에 사용하지 않음)
            "start_page": 463,
            "end_page": 503,  # 504 - 1
        },
        {
            "number": 10,
            "title": "제10장",  # 참고용 (정확도 평가에 사용하지 않음)
            "start_page": 504,  # 수정: 555 → 504
            "end_page": 554,  # 555 - 1
        },
        {
            "number": 11,
            "title": "제11장",  # 참고용 (정확도 평가에 사용하지 않음)
            "start_page": 555,  # 수정: 602 → 555
            "end_page": 640,  # 641 - 1
        },
        {
            "number": 12,
            "title": "제12장",  # 참고용 (정확도 평가에 사용하지 않음)
            "start_page": 641,
            "end_page": 679,
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
