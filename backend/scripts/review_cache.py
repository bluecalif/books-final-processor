"""
캐시 리뷰 도구: 페이지 엔티티 및 챕터 서머리를 HTML로 시각화

Book 184 (AI지도책) 우선 지원
"""
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from backend.api.database import SessionLocal
from backend.api.models.book import Book, Chapter, PageSummary, ChapterSummary
from backend.summarizers.summary_cache_manager import SummaryCacheManager

def get_book_data(book_id: int, db: Session) -> Optional[Dict[str, Any]]:
    """도서 데이터 조회"""
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        return None
    
    # 챕터 목록 조회
    chapters = (
        db.query(Chapter)
        .filter(Chapter.book_id == book_id)
        .order_by(Chapter.order_index)
        .all()
    )
    
    # 챕터별 ChapterSummary 조회
    chapter_summaries = {}
    for chapter in chapters:
        chapter_summary = (
            db.query(ChapterSummary)
            .filter(ChapterSummary.chapter_id == chapter.id)
            .first()
        )
        if chapter_summary:
            chapter_summaries[chapter.id] = chapter_summary
    
    # 챕터별 PageSummary 조회
    page_summaries_by_chapter = {}
    for chapter in chapters:
        page_summaries = (
            db.query(PageSummary)
            .filter(
                PageSummary.book_id == book_id,
                PageSummary.page_number >= chapter.start_page,
                PageSummary.page_number <= chapter.end_page
            )
            .order_by(PageSummary.page_number)
            .all()
        )
        page_summaries_by_chapter[chapter.id] = page_summaries
    
    return {
        "book": book,
        "chapters": chapters,
        "chapter_summaries": chapter_summaries,
        "page_summaries_by_chapter": page_summaries_by_chapter,
    }


def load_cache_data(book_title: str, page_summaries: List[PageSummary], chapter_summaries: Dict[int, ChapterSummary]) -> Dict[str, Any]:
    """캐시에서 structured_data 로드"""
    cache_manager = SummaryCacheManager(book_title=book_title)
    
    # 페이지 엔티티 캐시 로드
    page_entities = {}
    for page_summary in page_summaries:
        if page_summary.structured_data:
            # DB에 structured_data가 있으면 사용
            page_entities[page_summary.page_number] = page_summary.structured_data
        else:
            # 캐시에서 로드 시도 (content_hash 기반)
            # PageSummary에는 content_hash가 없으므로, summary_text로 해시 생성
            content_hash = cache_manager.get_content_hash(page_summary.summary_text)
            cached = cache_manager.get_cached_summary(content_hash, "page")
            if cached:
                page_entities[page_summary.page_number] = cached
    
    # 챕터 서머리 캐시 로드
    chapter_entities = {}
    for chapter_id, chapter_summary in chapter_summaries.items():
        if chapter_summary.structured_data:
            # DB에 structured_data가 있으면 사용
            chapter_entities[chapter_id] = chapter_summary.structured_data
        else:
            # 캐시에서 로드 시도
            content_hash = cache_manager.get_content_hash(chapter_summary.summary_text)
            cached = cache_manager.get_cached_summary(content_hash, "chapter")
            if cached:
                chapter_entities[chapter_id] = cached
    
    return {
        "page_entities": page_entities,
        "chapter_entities": chapter_entities,
    }


def generate_html(book_data: Dict[str, Any], cache_data: Dict[str, Any]) -> str:
    """HTML 생성"""
    book = book_data["book"]
    chapters = book_data["chapters"]
    chapter_summaries = book_data["chapter_summaries"]
    page_summaries_by_chapter = book_data["page_summaries_by_chapter"]
    
    page_entities = cache_data["page_entities"]
    chapter_entities = cache_data["chapter_entities"]
    
    # HTML 헤더
    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{book.title} - 엔티티 리뷰</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            background: #f5f5f5;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }}
        
        .header {{
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }}
        
        .header h1 {{
            font-size: 28px;
            margin-bottom: 10px;
            color: #2c3e50;
        }}
        
        .header .meta {{
            color: #7f8c8d;
            font-size: 14px;
        }}
        
        .stats {{
            display: flex;
            gap: 20px;
            margin-top: 15px;
            flex-wrap: wrap;
        }}
        
        .stat-item {{
            background: #ecf0f1;
            padding: 10px 15px;
            border-radius: 4px;
            font-size: 14px;
        }}
        
        .stat-item strong {{
            color: #3498db;
        }}
        
        .controls {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 20px;
            display: flex;
            gap: 15px;
            flex-wrap: wrap;
            align-items: center;
        }}
        
        .controls input[type="text"] {{
            flex: 1;
            min-width: 200px;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 14px;
        }}
        
        .controls select {{
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 14px;
        }}
        
        .chapter-section {{
            background: white;
            margin-bottom: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        
        .chapter-header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        
        .chapter-header:hover {{
            background: linear-gradient(135deg, #764ba2 0%, #667eea 100%);
        }}
        
        .chapter-header h2 {{
            font-size: 20px;
            margin: 0;
        }}
        
        .chapter-header .toggle {{
            font-size: 24px;
            user-select: none;
        }}
        
        .chapter-content {{
            padding: 0;
            display: none;
        }}
        
        .chapter-content.expanded {{
            display: block;
        }}
        
        .chapter-summary {{
            padding: 25px;
            background: #f8f9fa;
            border-bottom: 2px solid #e9ecef;
        }}
        
        .chapter-summary h3 {{
            color: #495057;
            margin-bottom: 15px;
            font-size: 18px;
        }}
        
        .field-group {{
            margin-bottom: 20px;
        }}
        
        .field-label {{
            font-weight: 600;
            color: #495057;
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        
        .field-label .mapping-badge {{
            background: #28a745;
            color: white;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 11px;
            cursor: pointer;
        }}
        
        .field-label .mapping-badge.synthetic {{
            background: #007bff;
        }}
        
        .field-value {{
            color: #212529;
            line-height: 1.8;
        }}
        
        .field-value ul {{
            list-style: none;
            padding-left: 0;
        }}
        
        .field-value li {{
            padding: 5px 0;
            padding-left: 20px;
            position: relative;
        }}
        
        .field-value li:before {{
            content: "•";
            position: absolute;
            left: 0;
            color: #667eea;
            font-weight: bold;
        }}
        
        .pages-section {{
            padding: 25px;
        }}
        
        .pages-section h3 {{
            color: #495057;
            margin-bottom: 15px;
            font-size: 18px;
        }}
        
        .page-item {{
            background: #f8f9fa;
            border: 1px solid #e9ecef;
            border-radius: 6px;
            margin-bottom: 15px;
            overflow: hidden;
        }}
        
        .page-header {{
            background: #e9ecef;
            padding: 12px 15px;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        
        .page-header:hover {{
            background: #dee2e6;
        }}
        
        .page-header .page-number {{
            font-weight: 600;
            color: #495057;
        }}
        
        .page-header .toggle {{
            color: #6c757d;
            user-select: none;
        }}
        
        .page-content {{
            padding: 15px;
            display: none;
        }}
        
        .page-content.expanded {{
            display: block;
        }}
        
        .highlight {{
            background: #fff3cd;
            padding: 2px 4px;
            border-radius: 2px;
        }}
        
        .search-highlight {{
            background: #ffeb3b;
            padding: 2px 4px;
            border-radius: 2px;
        }}
        
        .empty-state {{
            text-align: center;
            padding: 40px;
            color: #6c757d;
        }}
        
        .empty-state-icon {{
            font-size: 48px;
            margin-bottom: 10px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{book.title or '제목 없음'}</h1>
            <div class="meta">
                <div>저자: {book.author or '저자 없음'} | 분야: {book.category or '분야 없음'} | 상태: {book.status.value}</div>
            </div>
            <div class="stats">
                <div class="stat-item"><strong>챕터 수:</strong> {len(chapters)}</div>
                <div class="stat-item"><strong>총 페이지:</strong> {book.page_count or 0}</div>
                <div class="stat-item"><strong>페이지 엔티티:</strong> {len(page_entities)}</div>
                <div class="stat-item"><strong>챕터 서머리:</strong> {len(chapter_entities)}</div>
            </div>
        </div>
        
        <div class="controls">
            <input type="text" id="searchInput" placeholder="키워드 검색 (Enter 키로 검색)">
            <select id="chapterFilter">
                <option value="">모든 챕터</option>
"""
    
    # 챕터 필터 옵션
    for chapter in chapters:
        html += f'                <option value="chapter-{chapter.id}">{chapter.order_index + 1}. {chapter.title}</option>\n'
    
    html += """            </select>
        </div>
"""
    
    # 챕터별 섹션
    for chapter in chapters:
        chapter_id = chapter.id
        chapter_summary = chapter_summaries.get(chapter_id)
        chapter_entity = chapter_entities.get(chapter_id)
        page_summaries = page_summaries_by_chapter.get(chapter_id, [])
        
        html += f"""
        <div class="chapter-section" data-chapter-id="chapter-{chapter_id}">
            <div class="chapter-header" onclick="toggleChapter({chapter_id})">
                <h2>챕터 {chapter.order_index + 1}: {chapter.title}</h2>
                <span class="toggle" id="toggle-{chapter_id}">▼</span>
            </div>
            <div class="chapter-content" id="chapter-{chapter_id}">
"""
        
        # 챕터 서머리 (출력)
        if chapter_entity:
            html += f"""
                <div class="chapter-summary">
                    <h3>📊 챕터 서머리 (출력)</h3>
"""
            
            # core_message
            if chapter_entity.get("core_message"):
                html += f"""
                    <div class="field-group">
                        <div class="field-label">
                            핵심 메시지
                            <span class="mapping-badge synthetic" title="페이지 엔티티의 page_summary들을 합성하여 생성">합성</span>
                        </div>
                        <div class="field-value">{chapter_entity.get("core_message", "")}</div>
                    </div>
"""
            
            # summary_3_5_sentences
            if chapter_entity.get("summary_3_5_sentences"):
                html += f"""
                    <div class="field-group">
                        <div class="field-label">
                            3-5문장 요약
                            <span class="mapping-badge synthetic" title="페이지 엔티티의 page_summary들을 합성하여 생성">합성</span>
                        </div>
                        <div class="field-value">{chapter_entity.get("summary_3_5_sentences", "")}</div>
                    </div>
"""
            
            # argument_flow
            if chapter_entity.get("argument_flow"):
                arg_flow = chapter_entity.get("argument_flow", {})
                html += f"""
                    <div class="field-group">
                        <div class="field-label">
                            논증 흐름
                            <span class="mapping-badge synthetic" title="페이지 엔티티의 page_summary, key_sentences, page_function_tag를 합성하여 생성">합성</span>
                        </div>
                        <div class="field-value">
                            <div><strong>문제:</strong> {arg_flow.get("problem", "")}</div>
                            <div><strong>배경:</strong> {arg_flow.get("background", "")}</div>
                            <div><strong>주요 주장:</strong>
                                <ul>
"""
                for claim in arg_flow.get("main_claims", []):
                    html += f"                                    <li>{claim}</li>\n"
                html += f"""
                                </ul>
                            </div>
                            <div><strong>증거 개요:</strong> {arg_flow.get("evidence_overview", "")}</div>
                            <div><strong>반론/한계:</strong> {arg_flow.get("counterpoints_or_limits", "")}</div>
                            <div><strong>결론/행동:</strong> {arg_flow.get("conclusion_or_action", "")}</div>
                        </div>
                    </div>
"""
            
            # key_events (직접 매핑)
            if chapter_entity.get("key_events"):
                html += f"""
                    <div class="field-group">
                        <div class="field-label">
                            핵심 사건
                            <span class="mapping-badge" title="페이지 엔티티의 events를 통합/중복 제거하여 생성" onclick="highlightSource('events', {chapter_id})">출처 보기</span>
                        </div>
                        <div class="field-value">
                            <ul>
"""
                for event in chapter_entity.get("key_events", []):
                    html += f"                                <li>{event}</li>\n"
                html += """
                            </ul>
                        </div>
                    </div>
"""
            
            # key_examples (직접 매핑)
            if chapter_entity.get("key_examples"):
                html += f"""
                    <div class="field-group">
                        <div class="field-label">
                            핵심 예시
                            <span class="mapping-badge" title="페이지 엔티티의 examples를 통합/중복 제거하여 생성" onclick="highlightSource('examples', {chapter_id})">출처 보기</span>
                        </div>
                        <div class="field-value">
                            <ul>
"""
                for example in chapter_entity.get("key_examples", []):
                    html += f"                                <li>{example}</li>\n"
                html += """
                            </ul>
                        </div>
                    </div>
"""
            
            # key_persons (직접 매핑)
            if chapter_entity.get("key_persons"):
                html += f"""
                    <div class="field-group">
                        <div class="field-label">
                            핵심 인물
                            <span class="mapping-badge" title="페이지 엔티티의 persons를 통합/중복 제거하여 생성" onclick="highlightSource('persons', {chapter_id})">출처 보기</span>
                        </div>
                        <div class="field-value">
                            <ul>
"""
                for person in chapter_entity.get("key_persons", []):
                    html += f"                                <li>{person}</li>\n"
                html += """
                            </ul>
                        </div>
                    </div>
"""
            
            # key_concepts (직접 매핑)
            if chapter_entity.get("key_concepts"):
                html += f"""
                    <div class="field-group">
                        <div class="field-label">
                            핵심 개념
                            <span class="mapping-badge" title="페이지 엔티티의 concepts를 통합/중복 제거하여 생성" onclick="highlightSource('concepts', {chapter_id})">출처 보기</span>
                        </div>
                        <div class="field-value">
                            <ul>
"""
                for concept in chapter_entity.get("key_concepts", []):
                    html += f"                                <li>{concept}</li>\n"
                html += """
                            </ul>
                        </div>
                    </div>
"""
            
            # insights
            if chapter_entity.get("insights"):
                html += f"""
                    <div class="field-group">
                        <div class="field-label">
                            인사이트
                            <span class="mapping-badge synthetic" title="페이지 엔티티의 key_sentences를 합성하여 생성">합성</span>
                        </div>
                        <div class="field-value">
                            <ul>
"""
                for insight in chapter_entity.get("insights", []):
                    if isinstance(insight, dict):
                        insight_text = insight.get("text", str(insight))
                    else:
                        insight_text = str(insight)
                    html += f"                                <li>{insight_text}</li>\n"
                html += """
                            </ul>
                        </div>
                    </div>
"""
            
            # chapter_level_synthesis
            if chapter_entity.get("chapter_level_synthesis"):
                html += f"""
                    <div class="field-group">
                        <div class="field-label">
                            챕터 수준 종합
                            <span class="mapping-badge synthetic" title="페이지 엔티티의 page_summary들을 합성하여 생성">합성</span>
                        </div>
                        <div class="field-value">{chapter_entity.get("chapter_level_synthesis", "")}</div>
                    </div>
"""
            
            # references (직접 매핑)
            if chapter_entity.get("references"):
                html += f"""
                    <div class="field-group">
                        <div class="field-label">
                            참고자료
                            <span class="mapping-badge" title="페이지 엔티티의 references를 통합하여 생성" onclick="highlightSource('references', {chapter_id})">출처 보기</span>
                        </div>
                        <div class="field-value">
                            <ul>
"""
                for ref in chapter_entity.get("references", []):
                    html += f"                                <li>{ref}</li>\n"
                html += """
                            </ul>
                        </div>
                    </div>
"""
            
            html += """
                </div>
"""
        else:
            html += """
                <div class="chapter-summary">
                    <div class="empty-state">
                        <div class="empty-state-icon">⚠️</div>
                        <div>챕터 서머리 데이터가 없습니다.</div>
                    </div>
                </div>
"""
        
        # 페이지 엔티티 (입력)
        html += f"""
                <div class="pages-section">
                    <h3>📄 페이지 엔티티 (입력) - {len(page_summaries)}개 페이지</h3>
"""
        
        if page_summaries:
            for page_summary in page_summaries:
                page_number = page_summary.page_number
                page_entity = page_entities.get(page_number)
                
                if page_entity:
                    html += f"""
                    <div class="page-item" data-page-number="{page_number}">
                        <div class="page-header" onclick="togglePage({chapter_id}, {page_number})">
                            <span class="page-number">페이지 {page_number}</span>
                            <span class="toggle" id="toggle-page-{chapter_id}-{page_number}">▼</span>
                        </div>
                        <div class="page-content" id="page-{chapter_id}-{page_number}">
"""
                    
                    # page_summary
                    if page_entity.get("page_summary"):
                        html += f"""
                            <div class="field-group">
                                <div class="field-label">페이지 요약</div>
                                <div class="field-value">{page_entity.get("page_summary", "")}</div>
                            </div>
"""
                    
                    # page_function_tag
                    if page_entity.get("page_function_tag"):
                        html += f"""
                            <div class="field-group">
                                <div class="field-label">페이지 기능 태그</div>
                                <div class="field-value">{page_entity.get("page_function_tag", "")}</div>
                            </div>
"""
                    
                    # persons
                    if page_entity.get("persons"):
                        html += f"""
                            <div class="field-group" data-field="persons">
                                <div class="field-label">인물 → 챕터 key_persons</div>
                                <div class="field-value">
                                    <ul>
"""
                        for person in page_entity.get("persons", []):
                            html += f"                                        <li>{person}</li>\n"
                        html += """
                                    </ul>
                                </div>
                            </div>
"""
                    
                    # concepts
                    if page_entity.get("concepts"):
                        html += f"""
                            <div class="field-group" data-field="concepts">
                                <div class="field-label">개념 → 챕터 key_concepts</div>
                                <div class="field-value">
                                    <ul>
"""
                        for concept in page_entity.get("concepts", []):
                            html += f"                                        <li>{concept}</li>\n"
                        html += """
                                    </ul>
                                </div>
                            </div>
"""
                    
                    # events
                    if page_entity.get("events"):
                        html += f"""
                            <div class="field-group" data-field="events">
                                <div class="field-label">사건 → 챕터 key_events</div>
                                <div class="field-value">
                                    <ul>
"""
                        for event in page_entity.get("events", []):
                            html += f"                                        <li>{event}</li>\n"
                        html += """
                                    </ul>
                                </div>
                            </div>
"""
                    
                    # examples
                    if page_entity.get("examples"):
                        html += f"""
                            <div class="field-group" data-field="examples">
                                <div class="field-label">예시 → 챕터 key_examples</div>
                                <div class="field-value">
                                    <ul>
"""
                        for example in page_entity.get("examples", []):
                            html += f"                                        <li>{example}</li>\n"
                        html += """
                                    </ul>
                                </div>
                            </div>
"""
                    
                    # references
                    if page_entity.get("references"):
                        html += f"""
                            <div class="field-group" data-field="references">
                                <div class="field-label">참고자료 → 챕터 references</div>
                                <div class="field-value">
                                    <ul>
"""
                        for ref in page_entity.get("references", []):
                            html += f"                                        <li>{ref}</li>\n"
                        html += """
                                    </ul>
                                </div>
                            </div>
"""
                    
                    # key_sentences
                    if page_entity.get("key_sentences"):
                        html += f"""
                            <div class="field-group">
                                <div class="field-label">핵심 문장 → 챕터 argument_flow/insights</div>
                                <div class="field-value">
                                    <ul>
"""
                        for sentence in page_entity.get("key_sentences", []):
                            html += f"                                        <li>{sentence}</li>\n"
                        html += """
                                    </ul>
                                </div>
                            </div>
"""
                    
                    html += """
                        </div>
                    </div>
"""
                else:
                    html += f"""
                    <div class="page-item">
                        <div class="page-header">
                            <span class="page-number">페이지 {page_number}</span>
                        </div>
                        <div class="page-content">
                            <div class="empty-state">
                                <div>페이지 엔티티 데이터가 없습니다.</div>
                            </div>
                        </div>
                    </div>
"""
        else:
            html += """
                    <div class="empty-state">
                        <div class="empty-state-icon">📄</div>
                        <div>페이지 엔티티가 없습니다.</div>
                    </div>
"""
        
        html += """
                </div>
            </div>
        </div>
"""
    
    # JavaScript
    html += """
    <script>
        function toggleChapter(chapterId) {
            const content = document.getElementById('chapter-' + chapterId);
            const toggle = document.getElementById('toggle-' + chapterId);
            
            if (content.classList.contains('expanded')) {
                content.classList.remove('expanded');
                toggle.textContent = '▼';
            } else {
                content.classList.add('expanded');
                toggle.textContent = '▲';
            }
        }
        
        function togglePage(chapterId, pageNumber) {
            const content = document.getElementById('page-' + chapterId + '-' + pageNumber);
            const toggle = document.getElementById('toggle-page-' + chapterId + '-' + pageNumber);
            
            if (content.classList.contains('expanded')) {
                content.classList.remove('expanded');
                toggle.textContent = '▼';
            } else {
                content.classList.add('expanded');
                toggle.textContent = '▲';
            }
        }
        
        function highlightSource(fieldName, chapterId) {
            // 해당 챕터의 모든 페이지에서 해당 필드 하이라이트
            const chapterContent = document.getElementById('chapter-' + chapterId);
            const fieldGroups = chapterContent.querySelectorAll(`[data-field="${fieldName}"]`);
            
            // 기존 하이라이트 제거
            document.querySelectorAll('.highlight').forEach(el => {
                el.classList.remove('highlight');
            });
            
            // 새 하이라이트 추가
            fieldGroups.forEach(group => {
                group.style.background = '#fff3cd';
                group.style.padding = '10px';
                group.style.borderRadius = '4px';
                group.style.border = '2px solid #ffc107';
            });
            
            // 스크롤
            if (fieldGroups.length > 0) {
                fieldGroups[0].scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        }
        
        // 검색 기능
        document.getElementById('searchInput').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                const searchTerm = this.value.toLowerCase();
                if (!searchTerm) {
                    // 검색어가 없으면 하이라이트 제거
                    document.querySelectorAll('.search-highlight').forEach(el => {
                        el.classList.remove('search-highlight');
                        const parent = el.parentNode;
                        parent.replaceChild(document.createTextNode(el.textContent), el);
                        parent.normalize();
                    });
                    return;
                }
                
                // 모든 텍스트에서 검색
                const walker = document.createTreeWalker(
                    document.body,
                    NodeFilter.SHOW_TEXT,
                    null,
                    false
                );
                
                const textNodes = [];
                let node;
                while (node = walker.nextNode()) {
                    if (node.textContent.toLowerCase().includes(searchTerm)) {
                        textNodes.push(node);
                    }
                }
                
                // 하이라이트
                textNodes.forEach(textNode => {
                    const parent = textNode.parentNode;
                    const text = textNode.textContent;
                    const regex = new RegExp(`(${searchTerm})`, 'gi');
                    const highlighted = text.replace(regex, '<span class="search-highlight">$1</span>');
                    
                    if (highlighted !== text) {
                        const wrapper = document.createElement('span');
                        wrapper.innerHTML = highlighted;
                        parent.replaceChild(wrapper, textNode);
                    }
                });
            }
        });
        
        // 챕터 필터
        document.getElementById('chapterFilter').addEventListener('change', function() {
            const selectedChapter = this.value;
            const chapters = document.querySelectorAll('.chapter-section');
            
            chapters.forEach(chapter => {
                if (!selectedChapter || chapter.dataset.chapterId === selectedChapter) {
                    chapter.style.display = 'block';
                } else {
                    chapter.style.display = 'none';
                }
            });
        });
    </script>
</body>
</html>
"""
    
    return html


def main():
    """메인 함수"""
    import sys
    
    # Book ID (기본값: 184)
    book_id = int(sys.argv[1]) if len(sys.argv) > 1 else 184
    
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    logger.info(f"[INFO] Generating review HTML for book_id={book_id}")
    
    # DB 세션 생성
    db = SessionLocal()
    try:
        # 도서 데이터 조회
        book_data = get_book_data(book_id, db)
        if not book_data:
            logger.error(f"[ERROR] Book {book_id} not found")
            return
        
        book = book_data["book"]
        logger.info(f"[INFO] Book found: {book.title}")
        
        # 캐시 데이터 로드
        logger.info("[INFO] Loading cache data...")
        cache_data = load_cache_data(
            book.title or f"book_{book_id}",
            [ps for pss in book_data["page_summaries_by_chapter"].values() for ps in pss],
            book_data["chapter_summaries"]
        )
        
        logger.info(f"[INFO] Loaded {len(cache_data['page_entities'])} page entities")
        logger.info(f"[INFO] Loaded {len(cache_data['chapter_entities'])} chapter entities")
        
        # HTML 생성
        logger.info("[INFO] Generating HTML...")
        html = generate_html(book_data, cache_data)
        
        # 출력 디렉토리 생성
        output_dir = Path(__file__).parent.parent.parent / "data" / "output" / "reviews"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 파일명 생성 (책 제목 기반)
        safe_title = "".join(c for c in (book.title or f"book_{book_id}") if c.isalnum() or c in (' ', '-', '_')).strip()
        safe_title = safe_title.replace(' ', '_')[:100]
        output_path = output_dir / f"{safe_title}_review.html"
        
        # HTML 저장
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)
        
        logger.info(f"[INFO] HTML saved to: {output_path}")
        logger.info(f"[INFO] Open in browser: file:///{output_path.as_posix()}")
        
        # 절대 경로 출력 (Windows)
        abs_path = output_path.resolve()
        logger.info(f"[INFO] Absolute path: {abs_path}")
        
    finally:
        db.close()


if __name__ == "__main__":
    main()

