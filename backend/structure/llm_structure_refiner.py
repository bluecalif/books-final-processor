"""
LLM 기반 구조 정제 모듈

휴리스틱 구조를 LLM으로 보정하여 더 정확한 구조를 생성합니다.
"""
import json
import logging
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, ValidationError
from openai import OpenAI
from backend.config.settings import settings

logger = logging.getLogger(__name__)


class LLMChapterSuggestion(BaseModel):
    """LLM 챕터 제안 스키마"""
    number: Optional[int] = None
    title: str
    start_page: int
    end_page: int


class LLMStructureSuggestion(BaseModel):
    """LLM 구조 제안 스키마"""
    main_start_page: int
    main_end_page: Optional[int] = None
    chapters: List[LLMChapterSuggestion]
    notes_pages: List[int] = []
    issues: Optional[str] = None


class LLMStructureRefiner:
    """LLM 기반 구조 정제 클래스"""

    def __init__(self, api_key: Optional[str] = None):
        """
        Args:
            api_key: OpenAI API 키 (None이면 settings에서 가져옴)
        """
        if api_key is None:
            api_key = settings.openai_api_key
        self.client = OpenAI(api_key=api_key)
        self.model = "gpt-4o-mini"
        self.temperature = 0.3

    def refine_structure(
        self, parsed_data: Dict[str, Any], heuristic_structure: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        휴리스틱 구조를 LLM으로 보정

        Args:
            parsed_data: PDFParser.parse_pdf() 결과
            heuristic_structure: StructureBuilder.build_structure() 결과

        Returns:
            LLMStructureSuggestion을 dict로 변환한 결과
        """
        logger.info("[INFO] Refining structure with LLM...")

        try:
            # 1. 컨텍스트 구축
            context = self._build_context_for_llm(parsed_data, heuristic_structure)

            # 2. 프롬프트 생성
            prompt = self._build_prompt(context, heuristic_structure)

            # 3. LLM 호출
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": prompt["system"]},
                    {"role": "user", "content": prompt["user"]},
                ],
                temperature=self.temperature,
                response_format={"type": "json_object"},
            )

            # 4. 응답 파싱 및 검증
            response_text = response.choices[0].message.content
            suggestion = self._parse_llm_response(response_text)

            logger.info("[INFO] LLM structure refinement completed")
            logger.info(
                f"  Main: pages {suggestion['main_start_page']}-"
                f"{suggestion.get('main_end_page', 'end')}"
            )
            logger.info(f"  Chapters: {len(suggestion['chapters'])}")

            return suggestion

        except Exception as e:
            logger.error(f"[ERROR] LLM refinement failed: {e}")
            logger.warning("[WARNING] Falling back to heuristic structure")
            # 실패 시 휴리스틱 구조로 fallback
            return self._fallback_to_heuristic(heuristic_structure)

    def _build_page_toplines_chain(
        self, pages: List[Dict], max_chars_per_page: int = 50
    ) -> str:
        """
        각 페이지 상단 50자 체인 생성

        Args:
            pages: 페이지 리스트
            max_chars_per_page: 페이지당 최대 문자 수

        Returns:
            "p{page_number}: {text}\n..." 형식의 문자열
        """
        lines = []

        for page in sorted(pages, key=lambda x: x.get("page_number", 0)):
            page_num = page.get("page_number")
            elements = page.get("elements", [])

            if not elements:
                continue

            # y0가 가장 작은(페이지 상단에 가까운) 요소 선택
            top_elem = min(
                elements, key=lambda e: e.get("bbox", {}).get("y0", 1.0)
            )

            text = (top_elem.get("text") or "").strip()
            if not text:
                continue

            snippet = text[:max_chars_per_page]
            lines.append(f"p{page_num}: {snippet}")

        return "\n".join(lines)

    def _sample_pages(
        self, pages: List[Dict], page_numbers: range, max_chars: int = 200
    ) -> List[Dict[str, Any]]:
        """
        페이지 샘플 생성

        Args:
            pages: 페이지 리스트
            page_numbers: 샘플링할 페이지 번호 범위
            max_chars: 최대 문자 수

        Returns:
            [{"page_number": 1, "snippet": "..."}, ...]
        """
        samples = []
        page_dict = {p.get("page_number"): p for p in pages}

        for page_num in page_numbers:
            if page_num not in page_dict:
                continue

            page = page_dict[page_num]
            raw_text = page.get("raw_text", "")
            snippet = raw_text[:max_chars] + ("..." if len(raw_text) > max_chars else "")

            samples.append({"page_number": page_num, "snippet": snippet})

        return samples

    def _build_context_for_llm(
        self, parsed_data: Dict[str, Any], heuristic_structure: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        LLM 컨텍스트 구축

        Args:
            parsed_data: PDFParser.parse_pdf() 결과
            heuristic_structure: StructureBuilder.build_structure() 결과

        Returns:
            컨텍스트 딕셔너리
        """
        pages = parsed_data.get("pages", [])
        total_pages = parsed_data.get("total_pages", len(pages))

        # 1) 글로벌 메타
        global_info = {
            "total_pages": total_pages,
            "original_pages": parsed_data.get("original_pages", total_pages),
        }

        # 2) head / tail / around_main_start 샘플
        head_samples = self._sample_pages(pages, range(1, min(6, total_pages + 1)))
        tail_samples = self._sample_pages(
            pages, range(max(1, total_pages - 4), total_pages + 1)
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

        # 3) 챕터 후보 (휴리스틱에서 탐지된 챕터)
        chapter_candidates = heuristic_structure.get("main", {}).get("chapters", [])

        # 4) 페이지 맨 위 50자 체인
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

    def _build_prompt(
        self, context: Dict[str, Any], heuristic_structure: Dict[str, Any]
    ) -> Dict[str, str]:
        """
        프롬프트 생성

        Args:
            context: LLM 컨텍스트
            heuristic_structure: 휴리스틱 구조

        Returns:
            {"system": "...", "user": "..."}
        """
        context_json = json.dumps(context, ensure_ascii=False, indent=2)
        heuristic_json = json.dumps(heuristic_structure, ensure_ascii=False, indent=2)

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

        return {
            "system": system + "\n\n" + instructions,
            "user": user_content,
        }

    def _parse_llm_response(self, response_text: str) -> Dict[str, Any]:
        """
        LLM 응답 파싱 및 검증

        Args:
            response_text: LLM 응답 텍스트

        Returns:
            검증된 구조 딕셔너리
        """
        try:
            data = json.loads(response_text)
        except json.JSONDecodeError as e:
            raise ValueError(f"LLM response is not valid JSON: {e}")

        try:
            suggestion = LLMStructureSuggestion.model_validate(data)
        except ValidationError as e:
            raise ValueError(f"LLM response failed validation: {e}")

        return suggestion.model_dump()

    def _fallback_to_heuristic(
        self, heuristic_structure: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        휴리스틱 구조로 fallback

        Args:
            heuristic_structure: 휴리스틱 구조

        Returns:
            LLMStructureSuggestion 형식으로 변환된 구조
        """
        main_pages = heuristic_structure.get("main", {}).get("pages", [])
        main_start = main_pages[0] if main_pages else 1
        main_end = main_pages[-1] if main_pages else None

        chapters = []
        for ch in heuristic_structure.get("main", {}).get("chapters", []):
            chapters.append(
                {
                    "number": ch.get("number"),
                    "title": ch.get("title", ""),
                    "start_page": ch.get("start_page", 1),
                    "end_page": ch.get("end_page", 1),
                }
            )

        return {
            "main_start_page": main_start,
            "main_end_page": main_end,
            "chapters": chapters,
            "notes_pages": [],
            "issues": "LLM refinement failed, using heuristic structure",
        }

