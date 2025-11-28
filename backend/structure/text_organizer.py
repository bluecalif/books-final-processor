"""도서 텍스트 정리 모듈"""
import logging
import json
import hashlib
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
from backend.config.settings import settings
from backend.parsers.pdf_parser import PDFParser

logger = logging.getLogger(__name__)


class TextOrganizer:
    """도서 텍스트 정리 클래스"""

    def __init__(self):
        """초기화"""
        self.pdf_parser = PDFParser(api_key=settings.upstage_api_key)

    def organize_text(
        self,
        book_id: int,
        structure_data: Dict[str, Any],
        pdf_path: str,
        book_title: Optional[str] = None,
    ) -> Path:
        """
        본문 텍스트 정리

        Args:
            book_id: 책 ID
            structure_data: 구조 분석 결과 (structure JSON 파일 또는 DB의 structure_data)
            pdf_path: PDF 파일 경로 (캐시 로드용)
            book_title: 책 제목 (선택)

        Returns:
            저장된 JSON 파일 경로
        """
        logger.info(f"[INFO] 텍스트 정리 시작: book_id={book_id}, pdf_path={pdf_path}")

        # 1. 구조 분석 결과에서 본문 범위 및 챕터 정보 추출
        structure = structure_data.get("structure", structure_data)
        main_start_page = structure.get("main_start_page", 1)
        main_end_page = structure.get("main_end_page")
        chapters = structure.get("chapters", [])

        if not chapters:
            raise ValueError(f"챕터 정보가 없습니다: book_id={book_id}")

        logger.info(
            f"[INFO] 본문 범위: {main_start_page} ~ {main_end_page}, "
            f"챕터 수: {len(chapters)}"
        )

        # 2. 캐시된 파싱 결과 로드 (use_cache=True)
        logger.info(f"[INFO] 캐시된 파싱 결과 로드: {pdf_path}")
        parsed_data = self.pdf_parser.parse_pdf(pdf_path, use_cache=True, force_split=True)

        if not parsed_data or "pages" not in parsed_data:
            raise ValueError(f"파싱 결과가 없습니다: book_id={book_id}")

        pages = parsed_data["pages"]
        total_pages = parsed_data.get("total_pages", len(pages))

        logger.info(
            f"[INFO] 파싱 결과 로드 완료: 총 {total_pages}페이지, "
            f"본문 범위 {main_start_page}~{main_end_page}"
        )

        # 3. 페이지 번호로 페이지 딕셔너리 생성 (빠른 조회용)
        pages_dict = {page["page_number"]: page for page in pages}

        # 4. 챕터별 텍스트 정리
        text_content_chapters = []
        for chapter in chapters:
            order_index = chapter.get("order_index", 0)
            chapter_number = order_index + 1  # 1부터 시작
            title = chapter.get("title", "")
            start_page = chapter.get("start_page")
            end_page = chapter.get("end_page")

            if start_page is None or end_page is None:
                logger.warning(
                    f"[WARNING] 챕터 {chapter_number}의 페이지 범위가 없습니다: "
                    f"start_page={start_page}, end_page={end_page}"
                )
                continue

            # 챕터 범위의 페이지 텍스트 추출
            chapter_pages = []
            for page_num in range(start_page, end_page + 1):
                if page_num not in pages_dict:
                    logger.warning(
                        f"[WARNING] 페이지 {page_num}이 파싱 결과에 없습니다"
                    )
                    continue

                page_data = pages_dict[page_num]
                raw_text = page_data.get("raw_text", "")

                chapter_pages.append(
                    {
                        "page_number": page_num,
                        "text": raw_text,
                    }
                )

            if not chapter_pages:
                logger.warning(
                    f"[WARNING] 챕터 {chapter_number}에 유효한 페이지가 없습니다: "
                    f"start_page={start_page}, end_page={end_page}"
                )
                continue

            text_content_chapters.append(
                {
                    "order_index": order_index,
                    "chapter_number": chapter_number,
                    "title": title,
                    "start_page": start_page,
                    "end_page": end_page,
                    "pages": chapter_pages,
                }
            )

            logger.info(
                f"[INFO] 챕터 {chapter_number} 정리 완료: "
                f"페이지 {start_page}~{end_page}, {len(chapter_pages)}개 페이지"
            )

        # 5. 메타 데이터 생성
        metadata = {
            "total_pages": total_pages,
            "main_start_page": main_start_page,
            "main_end_page": main_end_page,
            "chapter_count": len(text_content_chapters),
        }

        # 6. JSON 구조 생성
        result = {
            "book_id": book_id,
            "book_title": book_title or "",
            "metadata": metadata,
            "text_content": {
                "chapters": text_content_chapters,
            },
            "summaries": {
                "page_summaries": [],
                "chapter_summaries": [],
            },
        }

        # 7. JSON 파일 저장
        output_path = self._save_text_to_json(
            book_id=book_id,
            text_data=result,
            book_title=book_title,
            pdf_path=pdf_path,
        )

        logger.info(f"[INFO] 텍스트 정리 완료: {output_path}")
        return output_path

    def _save_text_to_json(
        self,
        book_id: int,
        text_data: Dict[str, Any],
        book_title: Optional[str] = None,
        pdf_path: Optional[str] = None,
    ) -> Path:
        """
        텍스트 정리 결과를 JSON 파일로 저장

        Args:
            book_id: 책 ID
            text_data: 텍스트 데이터 딕셔너리
            book_title: 책 제목 (선택)
            pdf_path: PDF 파일 경로 (해시 계산용)

        Returns:
            저장된 JSON 파일 경로
        """
        # 출력 디렉토리 생성
        output_dir = settings.output_dir / "text"
        output_dir.mkdir(parents=True, exist_ok=True)

        # PDF 파일 해시 계산 (6글자)
        file_hash_6 = ""
        if pdf_path:
            pdf_file = Path(pdf_path)
            if pdf_file.exists():
                try:
                    with open(pdf_file, "rb") as f:
                        hasher = hashlib.md5()
                        for chunk in iter(lambda: f.read(4096), b""):
                            hasher.update(chunk)
                        file_hash = hasher.hexdigest()
                        file_hash_6 = file_hash[:6]  # 앞 6글자만 사용
                        logger.info(
                            f"[INFO] PDF 해시 계산 완료: {file_hash_6} "
                            f"(전체: {file_hash[:12]}...)"
                        )
                except Exception as e:
                    logger.warning(
                        f"[WARNING] PDF 해시 계산 실패: {e}, pdf_path={pdf_path}"
                    )
            else:
                logger.warning(f"[WARNING] PDF 파일 없음: {pdf_path}")

        # 파일명에 사용할 수 없는 문자 제거 및 책 제목 10글자 제한
        safe_title = ""
        if book_title:
            # 파일명에 사용할 수 없는 문자 제거: \ / : * ? " < > |
            safe_title = re.sub(r'[\\/:*?"<>|]', "_", book_title)
            # 공백을 언더스코어로 변환
            safe_title = safe_title.replace(" ", "_")
            # 10글자로 제한
            safe_title = safe_title[:10]

        # JSON 파일 경로: {해시6글자}_{책제목10글자}_text.json
        if file_hash_6 and safe_title:
            json_file = output_dir / f"{file_hash_6}_{safe_title}_text.json"
        elif file_hash_6:
            json_file = output_dir / f"{file_hash_6}_text.json"
        elif safe_title:
            json_file = output_dir / f"{safe_title}_text.json"
        else:
            json_file = output_dir / f"{book_id}_text.json"

        # JSON 파일 저장
        try:
            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(
                    text_data,
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
            logger.info(f"[INFO] 텍스트 JSON 파일 저장 완료: {json_file}")
            return json_file
        except Exception as e:
            logger.error(f"[ERROR] 텍스트 JSON 파일 저장 실패: {e}, json_file={json_file}")
            raise

