"""
Ground Truth 데이터: 30개 도시로 읽는 세계사.pdf

이 파일은 구조 분석 정확도 평가를 위한 Ground Truth 데이터입니다.
사용자가 제공한 정확한 구조 정보를 담고 있습니다.

⚠️ 중요:
- 정확도 평가는 페이지 번호만 사용합니다 (main_start_page, main_end_page, chapter start_page/end_page)
- 챕터 제목(title)은 참고용이며, 정확도 평가에 사용하지 않습니다
- E2E 테스트에서는 실제 파싱 결과의 페이지 번호와 Ground Truth의 페이지 번호를 비교합니다
"""

GROUND_TRUTH = {
    "book_title": "30개도시로읽는세계사",
    "pdf_file": "30개 도시로 읽는 세계사.pdf",
    "original_pages": 300,  # 원본 PDF 페이지 수
    "total_pages": 600,  # 양면 분리 후 페이지 수 (원본 * 2)
    "main_start_page": 23,
    "main_end_page": 570,  # 종문 시작 페이지 - 1
    "chapters": [
        {
            "number": 1,
            "title": "제1장",  # 참고용 (정확도 평가에 사용하지 않음)
            "start_page": 23,
            "end_page": 210,
        },
        {
            "number": 11,
            "title": "제11장",  # 참고용 (정확도 평가에 사용하지 않음)
            "start_page": 211,
            "end_page": 382,
        },
        {
            "number": 21,
            "title": "제21장",  # 참고용 (정확도 평가에 사용하지 않음)
            "start_page": 383,
            "end_page": 554,
        },
        {
            "number": 30,
            "title": "제30장",  # 참고용 (정확도 평가에 사용하지 않음)
            "start_page": 555,
            "end_page": 570,
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
