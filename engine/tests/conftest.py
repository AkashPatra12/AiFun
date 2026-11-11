import subprocess
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm import sessionmaker

from aifun.api.app import app
from aifun.db.session import engine, get_db, init_db


def _ffmpeg_generate(args: list[str], out_path) -> bytes:
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", *args, str(out_path)],
        check=True,
    )
    return out_path.read_bytes()


@pytest.fixture
def tiny_video_bytes(tmp_path):
    """A 2s, silent, tiny synthetic clip — no audio stream, exercising the
    "background track becomes the sole audio" branch of editing.audio.
    """
    return _ffmpeg_generate(
        ["-f", "lavfi", "-i", "testsrc=duration=2:size=320x240:rate=10"],
        tmp_path / "tiny.mp4",
    )


@pytest.fixture
def tiny_photo_bytes(tmp_path):
    return _ffmpeg_generate(
        ["-f", "lavfi", "-i", "color=c=blue:s=640x480", "-frames:v", "1"],
        tmp_path / "tiny.jpg",
    )


@pytest.fixture(scope="session", autouse=True)
def _tables():
    # init_db(), not a bare Base.metadata.create_all() — it also carries the
    # ad-hoc `stage` column migration for a `media` table that may already
    # exist from before that column was added (see aifun.db.session).
    init_db()
    yield


@pytest.fixture
def db_session():
    """A session bound to one connection/transaction that's rolled back
    after the test — so route handlers' own `db.commit()` calls never
    persist to the real dev database (docs/phase1-data-ingestion.md's
    Postgres-in-Docker instance), even though they run in-process against
    it. Standard SQLAlchemy "join a session into an external transaction"
    recipe: commits inside the test become SAVEPOINTs, released and
    immediately reopened, until the outer transaction rolls everything back.
    """
    connection = engine.connect()
    outer_transaction = connection.begin()
    session = sessionmaker(bind=connection)()

    nested = connection.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def _restart_savepoint(sess, trans):
        nonlocal nested
        if not nested.is_active:
            nested = connection.begin_nested()

    try:
        yield session
    finally:
        session.close()
        outer_transaction.rollback()
        connection.close()


@pytest.fixture
def make_real_media():
    """Creates a Media row via the *real* SessionLocal — not the rolled-back
    `db_session` above. Needed for tests exercising code that deliberately
    opens its own session (aifun.processing, the SSE endpoint's stream) and
    so must see genuinely committed rows from a separate connection, which
    a same-transaction row never becomes visible as. Deletes every row (and
    its Highlight rows) it created once the test ends.
    """
    from aifun.db.models import Highlight, Media
    from aifun.db.session import SessionLocal

    created_ids = []

    def _make(**kwargs) -> uuid.UUID:
        db = SessionLocal()
        try:
            media = Media(**kwargs)
            db.add(media)
            db.commit()
            created_ids.append(media.id)
            return media.id
        finally:
            db.close()

    yield _make

    db = SessionLocal()
    try:
        for media_id in created_ids:
            db.query(Highlight).filter(Highlight.media_id == media_id).delete()
            db.query(Media).filter(Media.id == media_id).delete()
        db.commit()
    finally:
        db.close()


@pytest.fixture
def client(db_session, monkeypatch):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    # Route tests exercise request/response behavior, not the real ffmpeg
    # pipeline — that's covered separately in test_assemble.py.
    monkeypatch.setattr("aifun.api.routes.schedule_processing", lambda media_id: None)

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
