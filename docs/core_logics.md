````markdown
# 인터랙티브 책 구조 분석 백엔드 설계 요약

이 문서는 **여러 권의 책에 대해 “파서 → 책 구조 분석 → 요약” 전처리 파이프라인**을 만들기 위한 백엔드 설계를 정리한 것이다.  
또한, **LLM 기반 구조 정제기(LLMStructureRefiner)**와 **사용자 인터랙션(UI)과 연결되는 API 설계**를 포함한다.

---

## 1. 전체 목표와 큰 흐름

### 1.1 최종 목표

- PDF 책을 업로드하면,
  1. **PDF 파싱(PDFParser)**  
  2. **책 구조 분석(StructureBuilder + LLMStructureRefiner + Human-in-the-loop)**  
  3. **책/챕터/페이지 요약(SummaryService + HierarchicalSummarizer)**  
  까지 **여러 권을 자동/반자동으로 전처리**해 두는 것이 목표다.
- 벡터 검색(FAISS, 임베딩)은 현재 범위 밖이며, **구조 확정과 요약까지**가 범위다.

### 1.2 한 권의 책에 대한 파이프라인 개요

```text
PDF 파일
  └─ (PDFParser.parse_pdf)
       → parsed_data (pages/elements: text + category + font + bbox ...)
         └─ (StructureBuilder.build_structure)
              → heuristic_structure (start/main/end + chapters)
                └─ (LLMStructureRefiner.refine_structure)
                     → llm_structure (보정된 구조 후보)
                       └─ Human-in-the-loop (사용자가 최종 구조 확정)
                            → final_structure (Book.structure_data 에 저장)
                              └─ (SummaryService + HierarchicalSummarizer)
                                   → Summary 테이블에 챕터/페이지 요약 저장
````

---

## 2. 기존 코어 컴포넌트 개요

### 2.1 PDFParser

**역할**: Upstage 등 외부 레이아웃 분석 API를 사용해, PDF를 **페이지/요소 단위 JSON**으로 정규화한다.

**입력**

```python
parse_pdf(file_path: str, use_cache: bool = True) -> dict
```

**출력(대표 스키마 예시)**

```json
{
  "success": true,
  "pages": [
    {
      "page_number": 1,
      "original_page": 1,
      "side": "left",
      "elements": [
        {
          "id": 0,
          "page": 1,
          "text": "문단 내용...",
          "category": "paragraph",
          "font_size": 18.0,
          "font_weight": "bold",
          "bbox": { "x0": 0.1, "y0": 0.2, "x1": 0.9, "y1": 0.3 },
          "line_number": 3
        }
      ]
    }
  ],
  "total_pages": 250,
  "original_pages": 125,
  "split_applied": true,
  "metadata": { ... }
}
```

**구조 분석/요약이 의존하는 핵심 필드**

* `pages[*].elements[*].text`
* `category` (heading/paragraph/header/footer 등)
* `bbox` (y0가 작을수록 페이지 상단)
* `font_size`, `font_weight`

---

### 2.2 StructureBuilder (휴리스틱 기반 1차 구조 분석)

**역할**: `parsed_data`를 기반으로 **서문/본문/끝** 범위와 **챕터 리스트**를 휴리스틱으로 생성한다.

최종 구조 JSON 예시:

```json
{
  "start": {
    "pages": [1, 2, 3],
    "page_count": 3
  },
  "main": {
    "pages": [4, 5, ..., 245],
    "page_count": 242,
    "chapters": [
      {
        "id": "ch1",
        "number": 1,
        "title": "제1장. 왜 우리는 ...",
        "start_page": 4,
        "end_page": 32,
        "sections": []
      }
    ]
  },
  "end": {
    "pages": [246, 247],
    "page_count": 2
  }
}
```

**휴리스틱 개념**

* **서문/본문/끝(ContentBoundaryDetector)**

  * 앞쪽 페이지에서 “차례, contents, 목차” 등 키워드 전까지를 `start`
  * 이후를 기본 `main`
  * 뒤에서부터 “참고문헌, index, 부록, 에필로그” 등의 키워드가 나오면 그 이후를 `end`
* **챕터 후보(Heading/Chapter Detector)**

  * 페이지 상단(y0가 작고, font_size가 크고, bold) + “제1장, Chapter 1…” 패턴
  * 후보를 페이지 순서대로 정렬하여:

    * `chap[i].start_page = candidate[i].page`
    * `chap[i].end_page = candidate[i+1].page - 1` 형태로 범위 계산

이 결과는 `Book.structure_data`와 `Chapter` 테이블로 저장되며, 이후 LLM 보정 및 사용자의 수정 대상이 된다.

---

### 2.3 SummaryService + HierarchicalSummarizer

**SummaryService.summarize_book(book_id)**

1. `book.structure_data`에서 챕터 리스트 추출
2. `parsed_data = PDFParser.parse_pdf(..., use_cache=True)`
3. 각 챕터마다:

   * `start_page ~ end_page` 구간의 텍스트를 모아 LangChain `Document` 생성
   * `HierarchicalSummarizer.summarize_chapter(doc)` 호출
4. 결과를 `Summary` 테이블에 JSON으로 저장
   (챕터 요약 + 페이지별 요약/팩트/키워드 등)

**HierarchicalSummarizer (개념)**

```python
class HierarchicalSummarizer:
    def summarize_chapter(self, chapter_doc: Document, ...) -> dict:
        # 1) 챕터 텍스트를 페이지/청크 단위로 나눔
        page_docs = self._split_to_pages(chapter_doc)

        # 2) 각 페이지/청크 요약
        page_summaries = [self._summarize_page(d) for d in page_docs]

        # 3) 페이지 요약들을 다시 통합하여 챕터 요약 생성
        chapter_summary = self._summarize_chapter_from_pages(page_summaries)

        return {
            "chapter_summary": chapter_summary,
            "page_summaries": page_summaries
        }
```

이때 **챕터 경계 정보는 전적으로 `structure_data`에 의존**하므로,
구조가 정확해야 요약도 제대로 나온다.

---

## 3. LLMStructureRefiner 설계

### 3.1 목적

> “휴리스틱으로 만든 1차 구조(heuristic_structure)를 받아,
> LLM이 본문 시작/끝 및 챕터 시작 페이지를 다시 검토하고 보정한다.”

최종 출력은 **LLM이 제안하는 구조 후보**이고,
휴리스틱 버전과 함께 “candidates”로 저장되어,
사용자가 UI에서 비교/선택/수정할 수 있다.

---

### 3.2 LLM 응답 스키마 (Pydantic 기반)

LLM이 맞춰야 할 **타겟 스키마**를 먼저 정의한다.

```python
from typing import List, Optional
from pydantic import BaseModel


class LLMChapterSuggestion(BaseModel):
    number: Optional[int] = None
    title: str
    start_page: int
    end_page: int


class LLMStructureSuggestion(BaseModel):
    main_start_page: int            # 본문 시작 페이지
    main_end_page: Optional[int]    # 본문 끝 페이지(없으면 null)
    chapters: List[LLMChapterSuggestion]
    notes_pages: List[int] = []     # 참고/부록/색인 등으로 보이는 페이지들
    issues: Optional[str] = None    # 애매한 부분에 대한 설명(선택)
```

LLM에게는 **반드시 위 JSON 구조 그대로** 출력하게 한다.

---

### 3.3 `_build_context_for_llm` — 컨텍스트 설계

#### 3.3.1 컨텍스트 구성 요소

1. **글로벌 정보 (global_info)**

   * total_pages, original_pages, split_applied 등
2. **페이지 샘플 (samples)**

   * `head`: 앞 5페이지 snippet
   * `tail`: 뒤 5페이지 snippet
   * `around_main_start`: 휴리스틱 `main.start_page` 주변 ±2페이지 snippet
3. **챕터 후보 리스트(chapter_candidates)**

   * 휴리스틱이 “챕터일 것 같다”고 찍은 후보(페이지/텍스트/위치 등)
4. **페이지 맨 위 50자 체인(page_toplines_chain)**

   * **새로 추가된, 매우 중요한 정보**
   * 각 페이지마다 **맨 위 요소의 텍스트 앞 50글자 + 페이지 번호**를 모아서
     한 줄에 하나씩 이어붙인 큰 텍스트

#### 3.3.2 페이지 맨 위 50자 체인 생성

```python
def _build_page_toplines_chain(self, pages, max_chars_per_page: int = 50) -> str:
    lines = []

    for p in sorted(pages, key=lambda x: x.get("page_number", 0)):
        page_num = p.get("page_number")
        elements = p.get("elements", [])
        if not elements:
            continue

        # y0가 가장 작은(페이지 상단에 가까운) 요소 선택
        top_elem = min(
            elements,
            key=lambda e: e.get("bbox", {}).get("y0", 1.0)
        )

        text = (top_elem.get("text") or "").strip()
        if not text:
            continue

        snippet = text[:max_chars_per_page]
        lines.append(f"p{page_num}: {snippet}")

    return "\n".join(lines)
```

**핵심 의도**

* 실제 책에서 **본문/챕터 시작을 알리는 헤딩**은 거의 항상 각 페이지의 상단에 온다.
* 모든 페이지를 훑되, **맨 위 요소 + 50자**만 사용해서 토큰을 최소화한다.
* 이 체인 하나만으로도 LLM은
  "p10: 차례", "p15: 제1장 왜 우리는 ...", "p32: 제2장 ..." 같은 패턴을 빠르게 읽어낼 수 있다.

#### 3.3.3 전체 컨텍스트 구축

```python
def _build_context_for_llm(self, parsed_data, heuristic_structure) -> dict:
    pages = parsed_data.get("pages", [])
    total_pages = parsed_data.get("total_pages", len(pages))
    orig_pages = parsed_data.get("original_pages", total_pages)

    # 1) 글로벌 메타
    global_info = {
        "total_pages": total_pages,
        "original_pages": orig_pages,
        "split_applied": parsed_data.get("split_applied", False),
    }

    # 2) head / tail / around_main_start 샘플
    head_samples = self._sample_pages(pages, range(1, min(6, total_pages + 1)))
    tail_samples = self._sample_pages(
        pages,
        range(max(1, total_pages - 4), total_pages + 1),
    )

    heuristic_main_pages = heuristic_structure.get("main", {}).get("pages", [])
    if heuristic_main_pages:
        main_start = heuristic_main_pages[0]
        around_main = range(
            max(1, main_start - 2),
            min(total_pages, main_start + 2) + 1,
        )
        main_start_samples = self._sample_pages(pages, around_main)
    else:
        main_start_samples = []

    chapter_candidates = heuristic_structure.get("main", {}).get(
        "chapter_candidates", []
    )

    # 3) 페이지 맨 위 50자 체인
    page_toplines_chain = self._build_page_toplines_chain(pages)

    context = {
        "global_info": global_info,
        "samples": {
            "head": head_samples,
            "tail": tail_samples,
            "around_main_start": main_start_samples,
        },
        "chapter_candidates": chapter_candidates,
        "page_toplines_chain": page_toplines_chain,
    }
    return context
```

여기서 `_sample_pages`는 각 페이지의 전체 텍스트를 잘라 snippet으로 만드는 헬퍼다.

---

### 3.4 `_build_prompt` — 프롬프트 설계

핵심 포인트:

* **LLMStructureSuggestion 스키마**를 정확히 설명
* `page_toplines_chain` 사용법을 명확히 지시
* 응답은 **JSON 하나만** 출력하도록 강하게 제한

의사코드 예시:

```python
import json

def _build_prompt(self, context: dict, heuristic_structure: dict) -> str:
    context_json = json.dumps(context, ensure_ascii=False)
    heuristic_json = json.dumps(heuristic_structure, ensure_ascii=False)

    system = (
        "You are an expert book structure analyst. "
        "Given partial text snippets and heuristic structure candidates, "
        "you infer the most plausible book structure: where the main body starts, "
        "where it ends, and which headings are main chapters."
    )

    instructions = """
You receive:
1) global_info: basic info such as total_pages.
2) samples: text snippets from the beginning, the end, and around the heuristic main start.
3) chapter_candidates: lines that the heuristic detector thinks might be chapter titles.
4) page_toplines_chain:
   - For every page, the first line of text at the top of the page.
   - Format: "p{page_number}: {first_50_characters_of_top_element}" per line.
   - Any text that signals the start of main body or chapters will almost always appear here.

Your tasks:
- Decide the most plausible main_start_page (where the actual main content begins).
- Optionally, decide main_end_page (if you can clearly separate back-matter like references, index, appendices).
- Use page_toplines_chain as the primary clue to:
  - Find the first page that looks like the main content (not preface/TOC).
  - Identify pages whose topline looks like chapter headings.
- From chapter_candidates and the toplines, choose which lines are main chapter titles.
  - Ignore subheadings or noisy titles.
- For each selected chapter, assign:
  - title (string)
  - start_page (int)
  - end_page (int, inclusive)
- Optionally, list pages that are likely notes, references, appendices, or index as notes_pages.
- If there is ambiguity, do your best guess and mention it in 'issues'.

Output:
Return a single JSON object with this exact schema:

{
  "main_start_page": <int>,
  "main_end_page": <int or null>,
  "chapters": [
    {
      "number": <int or null>,
      "title": "<string>",
      "start_page": <int>,
      "end_page": <int>
    }
  ],
  "notes_pages": [<int>, ...],
      "issues": "<string or null>"
}

Do NOT add any fields. Do NOT add any commentary outside the JSON.
"""

    user_content = f"""
# CONTEXT_JSON
{context_json}

# HEURISTIC_STRUCTURE
{heuristic_json}

# PAGE_TOPLINES_CHAIN
{context['page_toplines_chain']}
"""

    prompt = system + "\n\n" + instructions + "\n\n" + user_content
    return prompt
```

---

### 3.5 `_parse_llm_response` — 응답 파싱 전략

```python
import json
from pydantic import ValidationError

def _parse_llm_response(self, response: str) -> dict:
    try:
        data = json.loads(response)
    except json.JSONDecodeError:
        raise ValueError("LLM response is not valid JSON")

    try:
        suggestion = LLMStructureSuggestion.model_validate(data)
    except ValidationError as e:
        # 필요하다면 부분 보정/기본값 전략 추가 가능
        raise ValueError(f"LLM response failed validation: {e}")

    return suggestion.model_dump()
```

* Pydantic을 사용해 **형식/타입을 강하게 검증**한다.
* 실패 시에는 상위 레벨에서 **휴리스틱 구조로 fallback**하도록 설계 가능.

---

## 4. GET `/books/{id}/structure/candidates` — 구조 후보 + 풍부한 컨텍스트

### 4.1 목표

단순히 `{ heuristic_v1, llm_v2 }`만 주지 말고,
프론트에서 “인터랙티브 구조 분석기 UI”를 만들 수 있도록 **풍부한 정보**를 제공한다.

필요한 정보:

1. **meta**

   * total_pages, original_pages, split_applied 등
2. **auto_candidates**

   * 휴리스틱 구조, LLM 보정 구조 등 복수의 구조 후보
3. **chapter_title_candidates**

   * 휴리스틱/LLM 양쪽에서 나온 챕터 제목 후보 (페이지/텍스트/출처)
4. **samples**

   * head/tail/around_main_start 페이지 snippet (LLM 컨텍스트 재사용 가능)

### 4.2 Response 모델 예시

```python
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class PageSample(BaseModel):
    page: int
    text_snippet: str


class CandidateStructure(BaseModel):
    label: str                # "heuristic_v1", "llm_v2"
    structure: Dict[str, Any] # 기존 구조 JSON 그대로


class StructureCandidatesResponse(BaseModel):
    meta: Dict[str, Any]  # total_pages, original_pages 등
    auto_candidates: List[CandidateStructure]
    chapter_title_candidates: List[Dict[str, Any]]  # {page, text, source, ...}
    samples: Dict[str, List[PageSample]]            # head, tail, around_main_start
```

**프론트 활용 예**

* `auto_candidates`에서 후보 A/B를 탭으로 보여주고,
* `chapter_title_candidates`를 기반으로 “제목 후보 리스트” 표시,
* `samples`를 기반으로 사용자가 페이지를 클릭했을 때 아래에 snippet 표시.

---

## 5. POST `/books/{id}/structure/final` — UI 상호작용과 최종 구조 확정

### 5.1 핵심 UI 컨셉

> “후보 구조를 띄워놓고, 사용자가 **페이지를 좌우로 넘기면서**
> **본문 시작 페이지**와 **각 챕터 시작 페이지**를 지정한다.”

#### 5.1.1 사용자 인터랙션 흐름 (MVP)

1. **후보 구조 선택**

   * 자동 구조 A(휴리스틱), B(LLM)를 전환해 보면서,
   * 기본이 될 후보를 하나 선택 (단, 필수는 아님).

2. **본문 시작 페이지 지정**

   * 페이지 뷰어(좌/우 버튼 or 스크롤)를 넘기다가,
   * “여기부터 진짜 본문이다”라고 판단한 페이지에서
     **“본문 시작” 버튼 클릭 → main_start_page로 기록**

3. **챕터 시작 페이지 지정**

   * 각 챕터 제목이 나오는 페이지에서
     **“챕터 시작” 버튼 토글 → chapterStartPages에 추가/삭제**

4. (선택) **노트/부록 시작 페이지 지정**

   * 참고문헌/부록/색인 등이 시작되는 페이지에서
     “노트/부록 시작” 버튼을 클릭해서 notesStartPage 등으로 기록

이렇게 하면 사용자가 직접 다루는 정보는:

* mainStartPage (int)
* chapterStartPages (List[int])
* (선택) notesStartPage (int)

으로 매우 단순해진다.

**end_page 계산, main_end_page 계산, 챕터별 end_page 계산은
프론트 또는 서버에서 자동으로 할 수 있다.**

---

### 5.2 프론트 내부 상태 예시

```ts
type StructureSelectionState = {
  mainStartPage: number | null;
  chapterStartPages: number[];   // 정렬된 페이지 번호들
  notesStartPage: number | null; // 선택하면 여기부터 notes/end
};
```

이 상태를 **최종 구조 입력(FinalStructureInput)**으로 변환한다.

1. `main_start_page = mainStartPage`
2. `main_end_page`

   * notesStartPage가 있으면: `notesStartPage - 1`
   * 없으면: 책 전체 페이지 수(meta.total_pages)
3. `chapters` 리스트

   * `chapterStartPages` 정렬
   * `chapters[i].start_page = chapterStartPages[i]`
   * `chapters[i].end_page = chapterStartPages[i+1] - 1`
     (마지막 챕터는 main_end_page까지)
   * `title`은 후보 구조나 topline 텍스트에서 기본값 가져오고,
     필요시 사용자 수정 UI 제공

---

### 5.3 FinalStructureInput / FinalStructureUpdate 스키마

#### 5.3.1 챕터 입력 모델

```python
from typing import Optional, List
from pydantic import BaseModel


class FinalChapterInput(BaseModel):
    id: Optional[str] = None
    number: Optional[int] = None
    title: Optional[str] = None
    start_page: int
    end_page: Optional[int] = None  # 서버가 자동 보정 가능
```

#### 5.3.2 최종 구조 입력 모델

```python
class FinalStructureInput(BaseModel):
    # 1) 사용자가 지정한 핵심 정보
    main_start_page: int
    main_end_page: Optional[int] = None  # 없으면 서버에서 total_pages/notes_start로 계산

    # 2) 챕터 정보
    chapters: List[FinalChapterInput]

    # 3) 기타 영역
    notes_pages: List[int] = []   # notesStartPage 이후 페이지들 (서버에서 계산 가능)
    start_pages: List[int] = []   # 서문(start 영역) 페이지들
    end_pages: List[int] = []     # end 영역 페이지들 (notes_pages와 중복 사용 가능)

    # 4) 어떤 후보에서 출발했는지
    base_candidate: Optional[str] = None  # "heuristic_v1" / "llm_v2" 등
```

#### 5.3.3 FinalStructureUpdate

```python
class FinalStructureUpdate(BaseModel):
    base: Optional[str] = None          # base_candidate와 동일한 의미로 사용 가능
    structure: FinalStructureInput
}
```

프론트는:

* UI 상호작용(페이지 넘기며 클릭) → `StructureSelectionState`를 유지
* “구조 확정” 버튼을 누를 때:

  * `StructureSelectionState` + 후보 구조/제목 후보 정보를 사용해
    `FinalStructureInput`을 생성
  * 이를 `FinalStructureUpdate` 형태로 감싸서 POST로 전송

---

### 5.4 `apply_final_structure` — 서버 측 처리

**역할**

* `FinalStructureInput`을 받아,

  * 부족한 end_page/main_end_page를 보정하고
  * 기존 `structure_data` 스키마(`start/main/end + chapters`)로 변환
  * `Chapter` 테이블을 재생성

의사코드 예시:

```python
def apply_final_structure(self, book_id: int, final_structure: FinalStructureInput):
    book = self._get_book(book_id)

    total_pages = book.total_pages or final_structure.main_end_page or 0

    main_start = final_structure.main_start_page
    main_end = final_structure.main_end_page or total_pages

    # 1) 챕터 정렬 및 end_page 보정
    chapters_in = sorted(
        final_structure.chapters,
        key=lambda ch: ch.start_page
    )

    chapters_payload = []
    for idx, ch in enumerate(chapters_in, start=1):
        start_page = ch.start_page
        if ch.end_page is not None:
            end_page = ch.end_page
        else:
            # 다음 챕터 시작 전까지, 아니면 main_end까지
            if idx < len(chapters_in):
                next_start = chapters_in[idx].start_page
                end_page = next_start - 1
            else:
                end_page = main_end

        number = ch.number or idx
        title = ch.title or f"Chapter {number}"

        chapters_payload.append(
            {
                "id": f"ch{number}",
                "number": number,
                "title": title,
                "start_page": start_page,
                "end_page": end_page,
                "sections": [],
            }
        )

    # 2) main/start/end 페이지 계산
    main_pages = list(range(main_start, main_end + 1))
    start_pages = final_structure.start_pages
    end_pages = final_structure.end_pages or final_structure.notes_pages

    new_structure_data = {
        "start": {
            "pages": start_pages,
            "page_count": len(start_pages),
        },
        "main": {
            "pages": main_pages,
            "page_count": len(main_pages),
            "chapters": chapters_payload,
        },
        "end": {
            "pages": end_pages,
            "page_count": len(end_pages),
        },
    }

    book.structure_data = new_structure_data
    # Chapter row 재생성 로직 (예: 기존 것 삭제 후 새로 insert)
    # self.db.query(Chapter).filter(Chapter.book_id == book.id).delete()
    # for ch in chapters_payload: ...
    self.db.commit()

    return new_structure_data
```

이렇게 하면,

* UI는 **“페이지 넘기며 본문/챕터 시작을 찍는 단순한 인터랙션”**에 집중하고,
* 서버는 이를 받아 **일관된 구조 JSON**으로 정리하여
  이후 요약 파이프라인에서 그대로 활용할 수 있다.

---

## 6. 한 줄 요약

1. **LLMStructureRefiner**

   * 휴리스틱 구조 + `page_toplines_chain` + 샘플 텍스트를 사용해
     본문 시작 페이지와 챕터 경계를 LLM이 보정한다.
2. **GET /books/{id}/structure/candidates**

   * 구조 후보(휴리스틱/LLM) + 메타 + 제목 후보 + 페이지 샘플을 반환하여
     인터랙티브 구조 분석 UI를 위한 풍부한 컨텍스트를 제공한다.
3. **POST /books/{id}/structure/final**

   * 사용자가 페이지를 넘기며 선택한 **본문 시작/챕터 시작**을 기반으로
     최종 구조(FinalStructureInput)를 받아
     기존 `structure_data`(start/main/end + chapters)로 변환, DB에 저장한다.

```



