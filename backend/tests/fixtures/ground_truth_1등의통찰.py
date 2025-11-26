"""
Ground Truth 데이터: 1등의 통찰.pdf

이 파일은 구조 분석 정확도 평가를 위한 Ground Truth 데이터입니다.
사용자가 제공한 정확한 구조 정보를 담고 있습니다.

⚠️ 중요:
- 정확도 평가는 페이지 번호만 사용합니다 (main_start_page, main_end_page, chapter start_page/end_page)
- 챕터 제목(title)은 참고용이며, 정확도 평가에 사용하지 않습니다
- E2E 테스트에서는 실제 파싱 결과의 페이지 번호와 Ground Truth의 페이지 번호를 비교합니다
"""

GROUND_TRUTH = {
    "book_title": "1등의 통찰",
    "pdf_file": "1등의 통찰.pdf",
    "original_pages": 142,  # 원본 PDF 페이지 수
    "total_pages": 284,  # 양면 분리 후 페이지 수 (원본 * 2)
    "main_start_page": 36,
    "main_end_page": 245,  # 마지막 챕터의 end_page (그 이후는 부록/참고문헌 등)
    "chapters": [
        {
            "number": 1,
            "title": "제1장",  # 참고용 (정확도 평가에 사용하지 않음)
            "start_page": 36,
            "end_page": 65,
        },
        {
            "number": 2,
            "title": "제2장",  # 참고용 (정확도 평가에 사용하지 않음)
            "start_page": 66,
            "end_page": 97,
        },
        {
            "number": 3,
            "title": "[제3강] 생각을 눈에 보이게 그린다 : 통찰력 사고의 1단계",  # 참고용
            "start_page": 97,
            "end_page": 120,
        },
        {
            "number": 4,
            "title": "[제4강] 과거를 해석하고 미래를 예측한다 : 통찰력 사고의 2단계",  # 참고용
            "start_page": 121,
            "end_page": 166,
        },
        {
            "number": 5,
            "title": "[제5강] 모델을 바꿔 해결책을 찾는다 : 통찰력 사고의 3단계",  # 참고용
            "start_page": 167,
            "end_page": 194,
        },
        {
            "number": 6,
            "title": "[제6강] 현실에서 피드백을 얻는다 : 통찰력 사고의 4단계",  # 참고용
            "start_page": 195,
            "end_page": 223,
        },
        {
            "number": 7,
            "title": "제7장",  # 참고용 (정확도 평가에 사용하지 않음)
            "start_page": 224,
            "end_page": 245,
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

