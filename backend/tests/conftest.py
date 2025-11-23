"""테스트 픽스처"""
import logging
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from backend.api.database import Base, get_db

# 모델 import로 테이블 정의 로드 (app import 전에 필수!)
from backend.api.models.book import Book, Page, Chapter, PageSummary, ChapterSummary

# 테스트 DB (in-memory SQLite)
TEST_DATABASE_URL = "sqlite:///:memory:"

# 로깅 설정
logger = logging.getLogger(__name__)
# 테스트 실행 시 INFO 레벨로 설정 (DEBUG는 너무 상세함)
logging.basicConfig(level=logging.INFO)

# app import는 client fixture에서만 (테이블 생성 후)


@pytest.fixture(scope="function")
def db_engine():
    """각 테스트마다 새로운 DB engine 생성 (테이블 포함)"""
    logger.info("=" * 80)
    logger.info("[FIXTURE] db_engine 시작")
    logger.info(f"[PARAM] TEST_DATABASE_URL={TEST_DATABASE_URL}")
    
    # Engine 생성
    logger.info("[CALL] create_engine() 호출 시작")
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    engine_id = id(engine)
    logger.info(f"[RETURN] create_engine() 반환값: engine_id={engine_id}")
    logger.info(f"[STATE] Engine 객체: {engine}")
    
    # 테이블 생성 전 확인
    logger.info("[CALL] inspect(engine) 호출 시작")
    inspector_before = inspect(engine)
    logger.info(f"[PARAM] inspect() 파라미터: engine_id={engine_id}")
    logger.info(f"[CALL] inspector.get_table_names() 호출 시작")
    tables_before = inspector_before.get_table_names()
    logger.info(f"[RETURN] get_table_names() 반환값: {tables_before}")
    logger.info(f"[EXPECTED] 테이블 생성 전 예상값: []")
    logger.info(f"[ACTUAL] 테이블 생성 전 실제값: {tables_before}")
    logger.info(f"[COMPARE] 예상값==실제값: {[] == tables_before}")
    
    # 테이블 생성
    logger.info("[CALL] Base.metadata.create_all(bind=engine) 호출 시작")
    logger.info(f"[PARAM] bind 파라미터: engine_id={engine_id}")
    Base.metadata.create_all(bind=engine)
    logger.info("[RETURN] Base.metadata.create_all() 완료 (반환값 없음)")
    
    # 테이블 생성 후 확인
    logger.info("[CALL] inspect(engine) 호출 시작 (테이블 생성 후)")
    inspector_after = inspect(engine)
    logger.info(f"[PARAM] inspect() 파라미터: engine_id={engine_id}")
    logger.info(f"[CALL] inspector.get_table_names() 호출 시작")
    tables_after = inspector_after.get_table_names()
    logger.info(f"[RETURN] get_table_names() 반환값: {tables_after}")
    expected_tables = ['books', 'chapter_summaries', 'chapters', 'page_summaries', 'pages']
    logger.info(f"[EXPECTED] 테이블 생성 후 예상값: {expected_tables}")
    logger.info(f"[ACTUAL] 테이블 생성 후 실제값: {tables_after}")
    logger.info(f"[COMPARE] 'books' in tables_after: {'books' in tables_after}")
    assert "books" in tables_after, f"Tables not created. Found: {tables_after}"
    
    logger.info(f"[STATE] Engine 유지됨: engine_id={engine_id}")
    logger.info("[CALL] yield engine 시작 전 확인")
    logger.info(f"[STATE] yield 전 engine_id={engine_id}")
    try:
        logger.info("[YIELD] engine yield 시작")
        yield engine
        logger.info("[YIELD] engine yield 완료")
    finally:
        logger.info("[FIXTURE] db_engine 정리 시작")
        logger.info(f"[STATE] 정리 전 engine_id={engine_id}")
        
        logger.info("[CALL] Base.metadata.drop_all(bind=engine) 호출 시작")
        logger.info(f"[PARAM] bind 파라미터: engine_id={engine_id}")
        Base.metadata.drop_all(bind=engine)
        logger.info("[RETURN] Base.metadata.drop_all() 완료 (반환값 없음)")
        
        logger.info("[CALL] engine.dispose() 호출 시작")
        logger.info(f"[PARAM] dispose() 파라미터: engine_id={engine_id}")
        engine.dispose()
        logger.info("[RETURN] engine.dispose() 완료 (반환값 없음)")
        
        logger.info("[FIXTURE] db_engine 정리 완료")
        logger.info("=" * 80)


@pytest.fixture(scope="function")
def db_connection(db_engine):
    """각 테스트마다 새로운 DB connection 생성 및 유지"""
    logger.info("=" * 80)
    logger.info("[FIXTURE] db_connection 시작")
    engine_id = id(db_engine)
    logger.info(f"[PARAM] db_engine 파라미터: engine_id={engine_id}")
    
    # Connection을 명시적으로 열어서 유지
    logger.info("[CALL] db_engine.connect() 호출 시작")
    logger.info(f"[PARAM] connect() 파라미터: engine_id={engine_id}")
    connection = db_engine.connect()
    connection_id = id(connection)
    logger.info(f"[RETURN] connect() 반환값: connection_id={connection_id}")
    logger.info(f"[STATE] Connection 객체: {connection}")
    logger.info(f"[STATE] Connection의 engine: {id(connection.engine)}")
    logger.info(f"[COMPARE] connection.engine == db_engine: {connection.engine is db_engine}")
    
    # Connection의 테이블 확인
    logger.info("[CALL] inspect(connection) 호출 시작")
    logger.info(f"[PARAM] inspect() 파라미터: connection_id={connection_id}")
    connection_inspector = inspect(connection)
    logger.info(f"[CALL] inspector.get_table_names() 호출 시작")
    connection_tables = connection_inspector.get_table_names()
    logger.info(f"[RETURN] get_table_names() 반환값: {connection_tables}")
    expected_tables = ['books', 'chapter_summaries', 'chapters', 'page_summaries', 'pages']
    logger.info(f"[EXPECTED] Connection 테이블 예상값: {expected_tables}")
    logger.info(f"[ACTUAL] Connection 테이블 실제값: {connection_tables}")
    logger.info(f"[COMPARE] 'books' in connection_tables: {'books' in connection_tables}")
    assert "books" in connection_tables, f"Connection has no books table. Found: {connection_tables}"
    
    logger.info(f"[STATE] Connection 유지됨: connection_id={connection_id}")
    logger.info("[CALL] yield connection 시작 전 확인")
    logger.info(f"[STATE] yield 전 connection_id={connection_id}")
    logger.info("[CALL] inspect(connection) 호출 시작 (yield 전)")
    logger.info(f"[PARAM] inspect() 파라미터: connection_id={connection_id}")
    yield_inspector = inspect(connection)
    logger.info(f"[CALL] inspector.get_table_names() 호출 시작 (yield 전)")
    yield_tables = yield_inspector.get_table_names()
    logger.info(f"[RETURN] get_table_names() 반환값 (yield 전): {yield_tables}")
    logger.info(f"[EXPECTED] yield 전 테이블 예상값: ['books', ...]")
    logger.info(f"[ACTUAL] yield 전 테이블 실제값: {yield_tables}")
    logger.info(f"[COMPARE] 'books' in yield_tables (yield 전): {'books' in yield_tables}")
    try:
        logger.info("[YIELD] connection yield 시작")
        yield connection
        logger.info("[YIELD] connection yield 완료")
    finally:
        logger.info("[FIXTURE] db_connection 정리 시작")
        logger.info(f"[STATE] 정리 전 connection_id={connection_id}")
        
        logger.info("[CALL] connection.close() 호출 시작")
        logger.info(f"[PARAM] close() 파라미터: connection_id={connection_id}")
        connection.close()
        logger.info("[RETURN] connection.close() 완료 (반환값 없음)")
        
        logger.info("[FIXTURE] db_connection 정리 완료")
        logger.info("=" * 80)


@pytest.fixture(scope="function")
def db_session(db_connection):
    """각 테스트마다 새로운 DB 세션 생성 (connection 사용)"""
    logger.info("=" * 80)
    logger.info("[FIXTURE] db_session 시작")
    connection_id = id(db_connection)
    logger.info(f"[PARAM] db_connection 파라미터: connection_id={connection_id}")
    
    # 세션 생성 (connection을 사용)
    logger.info("[CALL] Session(bind=db_connection) 호출 시작")
    logger.info(f"[PARAM] bind 파라미터: connection_id={connection_id}")
    from sqlalchemy.orm import Session
    session = Session(bind=db_connection)
    session_id = id(session)
    logger.info(f"[RETURN] Session() 반환값: session_id={session_id}")
    logger.info(f"[STATE] Session 객체: {session}")
    logger.info(f"[STATE] Session의 bind: {id(session.bind)}")
    logger.info(f"[COMPARE] session.bind == db_connection: {session.bind is db_connection}")
    
    # 세션의 connection 확인
    logger.info("[CALL] session.connection() 호출 시작 (세션 생성 직후)")
    logger.info(f"[PARAM] session.connection() 파라미터: session_id={session_id}")
    session_connection = session.connection()
    session_connection_id = id(session_connection)
    logger.info(f"[RETURN] session.connection() 반환값: connection_id={session_connection_id}")
    logger.info(f"[COMPARE] session.connection() == db_connection: {session_connection is db_connection}")
    logger.info(f"[COMPARE] session.connection() ID == db_connection ID: {session_connection_id == connection_id}")
    
    # 세션의 connection으로 테이블 확인
    logger.info("[CALL] inspect(session_connection) 호출 시작")
    logger.info(f"[PARAM] inspect() 파라미터: connection_id={session_connection_id}")
    session_inspector = inspect(session_connection)
    logger.info(f"[CALL] inspector.get_table_names() 호출 시작")
    session_tables = session_inspector.get_table_names()
    logger.info(f"[RETURN] get_table_names() 반환값: {session_tables}")
    expected_tables = ['books', 'chapter_summaries', 'chapters', 'page_summaries', 'pages']
    logger.info(f"[EXPECTED] Session connection 테이블 예상값: {expected_tables}")
    logger.info(f"[ACTUAL] Session connection 테이블 실제값: {session_tables}")
    logger.info(f"[COMPARE] 'books' in session_tables: {'books' in session_tables}")
    
    logger.info(f"[STATE] Session 유지됨: session_id={session_id}")
    logger.info("[CALL] yield session 시작 전 확인")
    logger.info(f"[STATE] yield 전 session_id={session_id}")
    logger.info("[CALL] session.connection() 호출 시작 (yield 전)")
    logger.info(f"[PARAM] session.connection() 파라미터: session_id={session_id}")
    yield_session_connection = session.connection()
    yield_session_connection_id = id(yield_session_connection)
    logger.info(f"[RETURN] session.connection() 반환값 (yield 전): connection_id={yield_session_connection_id}")
    logger.info("[CALL] inspect(yield_session_connection) 호출 시작 (yield 전)")
    logger.info(f"[PARAM] inspect() 파라미터: connection_id={yield_session_connection_id}")
    yield_session_inspector = inspect(yield_session_connection)
    logger.info(f"[CALL] inspector.get_table_names() 호출 시작 (yield 전)")
    yield_session_tables = yield_session_inspector.get_table_names()
    logger.info(f"[RETURN] get_table_names() 반환값 (yield 전): {yield_session_tables}")
    logger.info(f"[EXPECTED] yield 전 테이블 예상값: ['books', ...]")
    logger.info(f"[ACTUAL] yield 전 테이블 실제값: {yield_session_tables}")
    logger.info(f"[COMPARE] 'books' in yield_session_tables (yield 전): {'books' in yield_session_tables}")
    try:
        logger.info("[YIELD] session yield 시작")
        yield session
        logger.info("[YIELD] session yield 완료")
    finally:
        logger.info("[FIXTURE] db_session 정리 시작")
        logger.info(f"[STATE] 정리 전 session_id={session_id}")
        
        logger.info("[CALL] session.close() 호출 시작")
        logger.info(f"[PARAM] close() 파라미터: session_id={session_id}")
        session.close()
        logger.info("[RETURN] session.close() 완료 (반환값 없음)")
        
        logger.info("[FIXTURE] db_session 정리 완료")
        logger.info("=" * 80)


@pytest.fixture(scope="function")
def client(db_session):
    """FastAPI 테스트 클라이언트"""
    logger.info("=" * 80)
    logger.info("[FIXTURE] client 시작")
    session_id = id(db_session)
    logger.info(f"[PARAM] db_session 파라미터: session_id={session_id}")
    logger.info(f"[STATE] db_session의 bind: {id(db_session.bind)}")
    
    # 세션의 connection 확인
    logger.info("[CALL] db_session.connection() 호출 시작 (client fixture에서)")
    logger.info(f"[PARAM] db_session.connection() 파라미터: session_id={session_id}")
    client_connection = db_session.connection()
    client_connection_id = id(client_connection)
    logger.info(f"[RETURN] db_session.connection() 반환값: connection_id={client_connection_id}")
    logger.info(f"[STATE] client_connection의 engine: {id(client_connection.engine)}")
    
    # 세션의 connection으로 테이블 확인
    logger.info("[CALL] inspect(client_connection) 호출 시작")
    logger.info(f"[PARAM] inspect() 파라미터: connection_id={client_connection_id}")
    client_inspector = inspect(client_connection)
    logger.info(f"[CALL] inspector.get_table_names() 호출 시작")
    client_tables = client_inspector.get_table_names()
    logger.info(f"[RETURN] get_table_names() 반환값: {client_tables}")
    expected_tables = ['books', 'chapter_summaries', 'chapters', 'page_summaries', 'pages']
    logger.info(f"[EXPECTED] Client connection 테이블 예상값: {expected_tables}")
    logger.info(f"[ACTUAL] Client connection 테이블 실제값: {client_tables}")
    logger.info(f"[COMPARE] 'books' in client_tables: {'books' in client_tables}")
    
    # app import는 여기서 (테이블 생성 후)
    from backend.api.main import app
    
    def override_get_db():
        logger.info("=" * 80)
        logger.info("[FUNCTION] override_get_db 호출됨")
        logger.info(f"[STATE] yield할 db_session: session_id={session_id}")
        logger.info(f"[STATE] db_session의 bind: {id(db_session.bind)}")
        
        # 세션의 connection 확인 (yield 전)
        logger.info("[CALL] db_session.connection() 호출 시작 (override_get_db에서, yield 전)")
        logger.info(f"[PARAM] db_session.connection() 파라미터: session_id={session_id}")
        override_connection = db_session.connection()
        override_connection_id = id(override_connection)
        logger.info(f"[RETURN] db_session.connection() 반환값 (yield 전): connection_id={override_connection_id}")
        logger.info(f"[COMPARE] override_connection == client_connection: {override_connection is client_connection}")
        logger.info(f"[COMPARE] override_connection ID == client_connection ID: {override_connection_id == client_connection_id}")
        logger.info(f"[STATE] override_connection의 engine: {id(override_connection.engine)}")
        logger.info(f"[COMPARE] override_connection.engine == client_connection.engine: {override_connection.engine is client_connection.engine}")
        
        # 세션의 connection으로 테이블 확인 (yield 전)
        logger.info("[CALL] inspect(override_connection) 호출 시작 (yield 전)")
        logger.info(f"[PARAM] inspect() 파라미터: connection_id={override_connection_id}")
        override_inspector = inspect(override_connection)
        logger.info(f"[CALL] inspector.get_table_names() 호출 시작 (yield 전)")
        override_tables_before = override_inspector.get_table_names()
        logger.info(f"[RETURN] get_table_names() 반환값 (yield 전): {override_tables_before}")
        expected_tables = ['books', 'chapter_summaries', 'chapters', 'page_summaries', 'pages']
        logger.info(f"[EXPECTED] Override connection 테이블 예상값 (yield 전): {expected_tables}")
        logger.info(f"[ACTUAL] Override connection 테이블 실제값 (yield 전): {override_tables_before}")
        logger.info(f"[COMPARE] 'books' in override_tables_before (yield 전): {'books' in override_tables_before}")
        logger.info(f"[COMPARE] override_tables_before == client_tables: {override_tables_before == client_tables}")
        
        try:
            logger.info(f"[YIELD] db_session yield 시작: session_id={session_id}")
            logger.info(f"[STATE] yield 전 connection_id={override_connection_id}")
            logger.info(f"[STATE] yield 전 테이블 상태: {override_tables_before}")
            yield db_session
            logger.info(f"[YIELD] db_session yield 완료: session_id={session_id}")
            
            # yield 후 connection 확인
            logger.info("[CALL] db_session.connection() 호출 시작 (override_get_db에서, yield 후)")
            logger.info(f"[PARAM] db_session.connection() 파라미터: session_id={session_id}")
            override_connection_after = db_session.connection()
            override_connection_id_after = id(override_connection_after)
            logger.info(f"[RETURN] db_session.connection() 반환값 (yield 후): connection_id={override_connection_id_after}")
            logger.info(f"[COMPARE] override_connection_id (yield 전) == override_connection_id_after (yield 후): {override_connection_id == override_connection_id_after}")
            
            # yield 후 테이블 확인
            logger.info("[CALL] inspect(override_connection_after) 호출 시작 (yield 후)")
            logger.info(f"[PARAM] inspect() 파라미터: connection_id={override_connection_id_after}")
            override_inspector_after = inspect(override_connection_after)
            logger.info(f"[CALL] inspector.get_table_names() 호출 시작 (yield 후)")
            override_tables_after = override_inspector_after.get_table_names()
            logger.info(f"[RETURN] get_table_names() 반환값 (yield 후): {override_tables_after}")
            logger.info(f"[EXPECTED] Override connection 테이블 예상값 (yield 후): {expected_tables}")
            logger.info(f"[ACTUAL] Override connection 테이블 실제값 (yield 후): {override_tables_after}")
            logger.info(f"[COMPARE] 'books' in override_tables_after (yield 후): {'books' in override_tables_after}")
            logger.info(f"[COMPARE] override_tables_before (yield 전) == override_tables_after (yield 후): {override_tables_before == override_tables_after}")
        finally:
            logger.info("[FUNCTION] override_get_db 종료")
            logger.info("=" * 80)
    
    logger.info("[CALL] app.dependency_overrides[get_db] = override_get_db 설정")
    logger.info(f"[STATE] 설정 전 dependency_overrides: {list(app.dependency_overrides.keys())}")
    app.dependency_overrides[get_db] = override_get_db
    logger.info(f"[STATE] 설정 후 dependency_overrides: {list(app.dependency_overrides.keys())}")
    logger.info(f"[COMPARE] get_db in app.dependency_overrides: {get_db in app.dependency_overrides}")
    logger.info("[RETURN] dependency override 설정 완료")
    
    logger.info("[CALL] TestClient(app) 생성 시작")
    logger.info(f"[PARAM] app 파라미터: app={app}")
    logger.info(f"[STATE] app.dependency_overrides 상태: {list(app.dependency_overrides.keys())}")
    with TestClient(app) as test_client:
        test_client_id = id(test_client)
        logger.info(f"[RETURN] TestClient 생성 완료: test_client_id={test_client_id}")
        logger.info(f"[STATE] TestClient 생성 후 app.dependency_overrides 상태: {list(app.dependency_overrides.keys())}")
        yield test_client
    
    logger.info("[FIXTURE] client 정리 시작")
    
    logger.info("[CALL] app.dependency_overrides.clear() 호출 시작")
    logger.info(f"[PARAM] clear() 파라미터 없음")
    logger.info(f"[STATE] clear() 호출 전 dependency_overrides: {list(app.dependency_overrides.keys())}")
    app.dependency_overrides.clear()
    logger.info(f"[RETURN] clear() 완료 (반환값 없음)")
    logger.info(f"[STATE] clear() 호출 후 dependency_overrides: {list(app.dependency_overrides.keys())}")
    
    logger.info("[FIXTURE] client 정리 완료")
    logger.info("=" * 80)
