"""구조 분석 서비스"""
import logging
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from backend.api.models.book import Book, Chapter, BookStatus
from backend.parsers.pdf_parser import PDFParser
from backend.structure.structure_builder import StructureBuilder
from backend.api.schemas.structure import FinalStructureInput
from backend.config.settings import settings

logger = logging.getLogger(__name__)


class StructureService:
    """구조 분석 서비스 클래스 (Footer 기반, LLM 보정 제외)"""

    def __init__(self, db: Session):
        """
        Args:
            db: 데이터베이스 세션
        """
        self.db = db
        self.pdf_parser = PDFParser(api_key=settings.upstage_api_key)
        self.structure_builder = StructureBuilder()

    def get_structure_candidates(self, book_id: int) -> Dict[str, Any]:
        """
        구조 후보 생성 (Footer 기반, LLM 보정 제외)
        
        **캐시 재사용 원칙**: 이미 구조 분석이 완료된 책의 경우, 
        `data/output/structure/{hash_6}_{title}_structure.json` 파일을 재사용합니다.
        PDF 해시 기반으로 구조 파일을 찾아 재사용하여 불필요한 구조 분석을 방지합니다.

        Args:
            book_id: 책 ID

        Returns:
            {
                "meta": {...},
                "auto_candidates": [
                    {"label": "footer_based_v1", "structure": {...}}
                ],
                "chapter_title_candidates": [...],
                "samples": {...}
            }
        """
        logger.info(f"[INFO] Getting structure candidates for book {book_id} (Footer 기반)")

        # 책 조회
        book = self.db.query(Book).filter(Book.id == book_id).first()
        if not book:
            raise ValueError(f"Book {book_id} not found")

        if book.status != BookStatus.PARSED:
            raise ValueError(
                f"Book {book_id} must be in 'parsed' status. Current status: {book.status}"
            )

        # PDF 파싱 (캐시 사용)
        import time
        total_start = time.time()
        
        logger.info(f"[INFO] Parsing PDF: {book.source_file_path}")
        parse_start = time.time()
        parsed_data = self.pdf_parser.parse_pdf(book.source_file_path, use_cache=True)
        parse_time = time.time() - parse_start
        logger.info(f"[INFO] PDF 파싱 완료: {parse_time:.3f}초")

        # 구조 분석 캐시 확인 및 재사용
        pdf_hash_6 = self._get_pdf_hash_6(book.source_file_path)
        structure_file = self._find_structure_file_by_hash(pdf_hash_6, book.title)
        
        if structure_file and structure_file.exists():
            # 구조 파일이 있으면 재사용
            logger.info(f"[INFO] Using cached structure file: {structure_file.name}")
            structure_start = time.time()
            with open(structure_file, "r", encoding="utf-8") as f:
                structure_json = json.load(f)
            footer_structure = self._convert_json_to_structure_format(structure_json.get("structure", {}))
            structure_time = time.time() - structure_start
            logger.info(f"[INFO] 구조 파일 로드 완료: {structure_time:.3f}초 (캐시 재사용)")
        else:
            # 구조 파일이 없으면 새로 구조 분석 수행
            logger.info(f"[INFO] Structure file not found, building new structure...")
            structure_start = time.time()
            footer_structure = self.structure_builder.build_structure(parsed_data)
            structure_time = time.time() - structure_start
            logger.info(f"[INFO] 구조 빌딩 완료: {structure_time:.3f}초")

        # 샘플 페이지 추출
        samples_start = time.time()
        samples = self._extract_samples(parsed_data, footer_structure)
        samples_time = time.time() - samples_start
        logger.info(f"[INFO] 샘플 추출 완료: {samples_time:.3f}초")

        # 챕터 제목 후보 추출
        titles_start = time.time()
        chapter_title_candidates = self._extract_chapter_title_candidates(
            parsed_data, footer_structure
        )
        titles_time = time.time() - titles_start
        logger.info(f"[INFO] 챕터 제목 후보 추출 완료: {titles_time:.3f}초")
        
        total_time = time.time() - total_start
        logger.info(f"[INFO] 전체 구조 분석 완료: {total_time:.3f}초 (파싱={parse_time:.3f}초, 구조={structure_time:.3f}초, 샘플={samples_time:.3f}초, 제목={titles_time:.3f}초)")

        # 메타데이터
        meta = {
            "total_pages": parsed_data.get("total_pages", 0),
            "book_id": book_id,
            "book_title": book.title,
        }

        result = {
            "meta": meta,
            "auto_candidates": [
                {"label": "footer_based_v1", "structure": footer_structure},
            ],
            "chapter_title_candidates": chapter_title_candidates,
            "samples": samples,
        }

        logger.info("[INFO] Structure candidates generated successfully (Footer 기반)")
        return result

    def apply_final_structure(
        self, book_id: int, final_structure: FinalStructureInput
    ) -> Book:
        """
        최종 구조 확정 및 DB 저장

        Args:
            book_id: 책 ID
            final_structure: 최종 구조 입력

        Returns:
            업데이트된 Book 객체
        """
        logger.info(f"[INFO] Applying final structure for book {book_id}")

        # 책 조회
        book = self.db.query(Book).filter(Book.id == book_id).first()
        if not book:
            raise ValueError(f"Book {book_id} not found")

        if book.status != BookStatus.PARSED:
            raise ValueError(
                f"Book {book_id} must be in 'parsed' status. Current status: {book.status}"
            )

        # 1. structure_data에 JSON 저장
        structure_data = {
            "main_start_page": final_structure.main_start_page,
            "main_end_page": final_structure.main_end_page,
            "chapters": [
                {
                    "title": ch.title,
                    "start_page": ch.start_page,
                    "end_page": ch.end_page,
                    "order_index": ch.order_index or idx,
                }
                for idx, ch in enumerate(final_structure.chapters)
            ],
            "notes_pages": final_structure.notes_pages,
            "start_pages": final_structure.start_pages,
            "end_pages": final_structure.end_pages,
        }
        book.structure_data = structure_data

        # 2. 기존 Chapter 레코드 삭제 후 재생성
        logger.info("[INFO] Deleting existing chapters...")
        existing_chapters = self.db.query(Chapter).filter(Chapter.book_id == book_id).all()
        for chapter in existing_chapters:
            self.db.delete(chapter)

        logger.info("[INFO] Creating new chapters...")
        for idx, ch_input in enumerate(final_structure.chapters):
            chapter = Chapter(
                book_id=book_id,
                title=ch_input.title,
                order_index=ch_input.order_index or idx,
                start_page=ch_input.start_page,
                end_page=ch_input.end_page,
                section_type="main",  # 기본값
            )
            self.db.add(chapter)

        # 3. 상태 변경: parsed → structured
        book.status = BookStatus.STRUCTURED

        # 4. 커밋
        self.db.commit()
        self.db.refresh(book)

        # 5. 구조 분석 결과 JSON 파일 저장 (이후 Phase에서 재사용)
        self._save_structure_to_json(book_id, structure_data, book.title, book.source_file_path)

        logger.info(f"[INFO] Final structure applied. Status changed to: {book.status}")
        return book

    def _save_structure_to_json(
        self, book_id: int, structure_data: Dict[str, Any], book_title: str = None, pdf_path: str = None
    ) -> Path:
        """
        구조 분석 결과를 JSON 파일로 저장

        Args:
            book_id: 책 ID
            structure_data: 구조 데이터 딕셔너리
            book_title: 책 제목 (선택)
            pdf_path: PDF 파일 경로 (해시 계산용)

        Returns:
            저장된 JSON 파일 경로
        """
        # 출력 디렉토리 생성
        output_dir = settings.output_dir / "structure"
        output_dir.mkdir(parents=True, exist_ok=True)

        # PDF 파일 해시 계산 (6글자)
        # pdf_path는 업로드된 파일 경로이므로, 원본 파일을 찾거나 업로드된 파일에서 해시 계산
        file_hash_6 = ""
        if pdf_path:
            import hashlib
            from pathlib import Path
            pdf_file = Path(pdf_path)
            if pdf_file.exists():
                try:
                    with open(pdf_file, "rb") as f:
                        hasher = hashlib.md5()
                        for chunk in iter(lambda: f.read(4096), b""):
                            hasher.update(chunk)
                        file_hash = hasher.hexdigest()
                        file_hash_6 = file_hash[:6]  # 앞 6글자만 사용
                        logger.info(f"[INFO] PDF 해시 계산 완료: {file_hash_6} (전체: {file_hash[:12]}...)")
                except Exception as e:
                    logger.warning(f"[WARNING] PDF 해시 계산 실패: {e}, pdf_path={pdf_path}")
            else:
                logger.warning(f"[WARNING] PDF 파일 없음: {pdf_path}")

        # 파일명에 사용할 수 없는 문자 제거 및 책 제목 10글자 제한
        safe_title = ""
        if book_title:
            # 파일명에 사용할 수 없는 문자 제거: \ / : * ? " < > |
            import re
            safe_title = re.sub(r'[\\/:*?"<>|]', '_', book_title)
            # 공백을 언더스코어로 변환
            safe_title = safe_title.replace(' ', '_')
            # 10글자로 제한
            safe_title = safe_title[:10]
        
        # JSON 파일 경로: {해시6글자}_{책제목10글자}_structure.json
        # 해시와 책제목이 모두 있어야 함
        if not file_hash_6:
            logger.error(f"[ERROR] PDF 해시 계산 실패 - pdf_path={pdf_path}, file_hash_6={file_hash_6}")
        if not safe_title:
            logger.warning(f"[WARNING] 책제목 없음 - book_title={book_title}, safe_title={safe_title}")
        
        if file_hash_6 and safe_title:
            json_file = output_dir / f"{file_hash_6}_{safe_title}_structure.json"
        elif file_hash_6:
            json_file = output_dir / f"{file_hash_6}_structure.json"
        elif safe_title:
            json_file = output_dir / f"{safe_title}_structure.json"
        else:
            # 해시와 책제목이 모두 없으면 book_id 사용 (fallback)
            logger.warning(f"[WARNING] 해시와 책제목 모두 없음 - book_id={book_id} 사용")
            json_file = output_dir / f"{book_id}_structure.json"
        
        logger.info(f"[INFO] JSON 파일 경로: {json_file} (해시={file_hash_6}, 책제목={safe_title})")

        # JSON 데이터 구성 (깔끔하게 정리)
        json_data = {
            "book_id": book_id,
            "book_title": book_title,
            "structure": {
                "main_start_page": structure_data.get("main_start_page"),
                "main_end_page": structure_data.get("main_end_page"),
                "chapters": [
                    {
                        "order_index": ch.get("order_index"),
                        "title": ch.get("title"),
                        "start_page": ch.get("start_page"),
                        "end_page": ch.get("end_page"),
                    }
                    for ch in structure_data.get("chapters", [])
                ],
                "notes_pages": structure_data.get("notes_pages", []),
                "start_pages": structure_data.get("start_pages", []),
                "end_pages": structure_data.get("end_pages", []),
            },
        }

        # JSON 파일 저장 (UTF-8, 들여쓰기 2칸)
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)

        logger.info(f"[INFO] Structure saved to JSON: {json_file}")
        return json_file

    def _extract_samples(
        self, parsed_data: Dict[str, Any], heuristic_structure: Dict[str, Any]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        샘플 페이지 추출

        Args:
            parsed_data: PDF 파싱 결과
            heuristic_structure: 휴리스틱 구조

        Returns:
            {
                "head": [...],
                "tail": [...],
                "around_main_start": [...]
            }
        """
        pages = parsed_data.get("pages", [])
        total_pages = len(pages)

        # head: 앞 5페이지
        head = [
            {
                "page_number": p.get("page_number"),
                "snippet": p.get("raw_text", "")[:200],
            }
            for p in pages[:5]
        ]

        # tail: 뒤 5페이지
        tail = [
            {
                "page_number": p.get("page_number"),
                "snippet": p.get("raw_text", "")[:200],
            }
            for p in pages[-5:]
        ]

        # around_main_start: 본문 시작 주변
        main_pages = heuristic_structure.get("main", {}).get("pages", [])
        around_main_start = []
        if main_pages:
            main_start = main_pages[0]
            start_idx = max(0, main_start - 3)
            end_idx = min(len(pages), main_start + 3)
            for p in pages[start_idx:end_idx]:
                around_main_start.append(
                    {
                        "page_number": p.get("page_number"),
                        "snippet": p.get("raw_text", "")[:200],
                    }
                )

        return {
            "head": head,
            "tail": tail,
            "around_main_start": around_main_start,
        }

    def _extract_chapter_title_candidates(
        self, parsed_data: Dict[str, Any], heuristic_structure: Dict[str, Any]
    ) -> List[str]:
        """
        챕터 제목 후보 추출

        Args:
            parsed_data: PDF 파싱 결과
            heuristic_structure: 휴리스틱 구조

        Returns:
            챕터 제목 후보 리스트
        """
        chapters = heuristic_structure.get("main", {}).get("chapters", [])
        return [ch.get("title", "") for ch in chapters if ch.get("title")]

    def _get_pdf_hash_6(self, pdf_path: str) -> str:
        """
        PDF 파일의 MD5 해시 6글자 계산

        Args:
            pdf_path: PDF 파일 경로

        Returns:
            MD5 해시 앞 6글자
        """
        import hashlib
        pdf_file = Path(pdf_path)
        if not pdf_file.exists():
            logger.warning(f"[WARNING] PDF 파일 없음: {pdf_path}")
            return ""
        
        try:
            with open(pdf_file, "rb") as f:
                hasher = hashlib.md5()
                for chunk in iter(lambda: f.read(4096), b""):
                    hasher.update(chunk)
                file_hash = hasher.hexdigest()
                file_hash_6 = file_hash[:6]
                logger.debug(f"[DEBUG] PDF 해시 계산 완료: {file_hash_6} (전체: {file_hash[:12]}...)")
                return file_hash_6
        except Exception as e:
            logger.warning(f"[WARNING] PDF 해시 계산 실패: {e}, pdf_path={pdf_path}")
            return ""

    def _find_structure_file_by_hash(self, hash_6: str, book_title: Optional[str] = None) -> Optional[Path]:
        """
        PDF 해시 기반으로 구조 파일 찾기

        Args:
            hash_6: PDF 해시 6글자
            book_title: 책 제목 (선택)

        Returns:
            구조 파일 경로 또는 None
        """
        if not hash_6:
            return None
        
        structure_dir = settings.output_dir / "structure"
        if not structure_dir.exists():
            return None

        # 1. 해시 + 책 제목으로 찾기 (정확한 매칭)
        if book_title:
            import re
            safe_title = re.sub(r'[\\/:*?"<>|]', '_', book_title)
            safe_title = safe_title.replace(' ', '_')[:10]
            pattern = f"{hash_6}_{safe_title}_structure.json"
            structure_file = structure_dir / pattern
            if structure_file.exists():
                logger.debug(f"[DEBUG] Found structure file by hash+title: {structure_file.name}")
                return structure_file

        # 2. 해시만으로 찾기 (와일드카드)
        pattern = f"{hash_6}_*_structure.json"
        matches = list(structure_dir.glob(pattern))
        if matches:
            logger.debug(f"[DEBUG] Found structure file by hash: {matches[0].name}")
            return matches[0]

        # 3. 해시만으로 찾기 (해시만 있는 파일)
        pattern = f"{hash_6}_structure.json"
        structure_file = structure_dir / pattern
        if structure_file.exists():
            logger.debug(f"[DEBUG] Found structure file by hash only: {structure_file.name}")
            return structure_file

        logger.debug(f"[DEBUG] Structure file not found for hash={hash_6}, title={book_title}")
        return None

    def _convert_json_to_structure_format(self, structure_json: Dict[str, Any]) -> Dict[str, Any]:
        """
        JSON 파일의 구조 데이터를 StructureBuilder 출력 형식으로 변환
        
        **중요**: 구조 확정 API에서 `main_start_page`와 `main_end_page`가 필요하므로,
        이 필드들을 루트 레벨에 포함하여 반환합니다.

        Args:
            structure_json: JSON 파일의 structure 필드 딕셔너리

        Returns:
            StructureBuilder 출력 형식 딕셔너리
            {
                "main_start_page": int,  # 구조 확정 API에서 필요
                "main_end_page": int,    # 구조 확정 API에서 필요
                "start": {"pages": [...], "page_count": N},
                "main": {"pages": [...], "page_count": N, "chapters": [...]},
                "end": {"pages": [...], "page_count": N}
            }
        """
        main_start_page = structure_json.get("main_start_page")
        main_end_page = structure_json.get("main_end_page")
        chapters = structure_json.get("chapters", [])
        start_pages = structure_json.get("start_pages", [])
        end_pages = structure_json.get("end_pages", [])
        notes_pages = structure_json.get("notes_pages", [])

        # main_pages 생성 (main_start_page ~ main_end_page 범위)
        main_pages = []
        if main_start_page and main_end_page:
            main_pages = list(range(main_start_page, main_end_page + 1))

        # StructureBuilder 출력 형식으로 변환
        # 구조 확정 API에서 main_start_page와 main_end_page가 필요하므로 루트 레벨에 포함
        result = {
            "main_start_page": main_start_page,  # 구조 확정 API에서 필요
            "main_end_page": main_end_page,       # 구조 확정 API에서 필요
            "start": {
                "pages": start_pages,
                "page_count": len(start_pages),
            },
            "main": {
                "pages": main_pages,
                "page_count": len(main_pages),
                "chapters": [
                    {
                        "title": ch.get("title", ""),
                        "start_page": ch.get("start_page"),
                        "end_page": ch.get("end_page"),
                        "order_index": ch.get("order_index", idx),
                    }
                    for idx, ch in enumerate(chapters)
                ],
            },
            "end": {
                "pages": end_pages,
                "page_count": len(end_pages),
            },
        }

        logger.debug(
            f"[DEBUG] Converted structure format: main_start_page={main_start_page}, "
            f"main_end_page={main_end_page}, main_pages={len(main_pages)}, chapters={len(chapters)}"
        )
        return result

