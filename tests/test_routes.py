"""Integration tests for all HTTP routes in app/main.py."""

import json

from app.models import Question, QuestionType, Response

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def auth_cookies(token: str) -> dict:
    return {"admin_token": token}


# ---------------------------------------------------------------------------
# Public routes
# ---------------------------------------------------------------------------


async def test_index_returns_200(async_client):
    resp = await async_client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


async def test_participant_view_unknown_session_returns_404(async_client):
    resp = await async_client.get("/session/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


async def test_participant_view_valid_session(async_client, admin_session_factory):
    info = await admin_session_factory(title="My Live Poll")
    resp = await async_client.get(f"/session/{info['session_id']}")
    assert resp.status_code == 200
    assert "My Live Poll" in resp.text


# ---------------------------------------------------------------------------
# Admin session creation
# ---------------------------------------------------------------------------


async def test_admin_create_session_redirects(async_client):
    resp = await async_client.post(
        "/admin/create",
        data={"title": "New Session", "admin_password": "pass123"},
    )
    assert resp.status_code == 303
    assert "/dashboard" in resp.headers["location"]
    assert "admin_token" in resp.cookies


# ---------------------------------------------------------------------------
# Admin login
# ---------------------------------------------------------------------------


async def test_admin_login_form_returns_200(async_client, admin_session_factory):
    info = await admin_session_factory()
    resp = await async_client.get(f"/admin/session/{info['session_id']}")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


async def test_admin_login_correct_password_redirects(async_client, admin_session_factory):
    info = await admin_session_factory(password="mypassword")
    resp = await async_client.post(
        f"/admin/session/{info['session_id']}/login",
        data={"password": "mypassword"},
    )
    assert resp.status_code == 303
    assert "admin_token" in resp.cookies


async def test_admin_login_wrong_password_returns_401(async_client, admin_session_factory):
    info = await admin_session_factory(password="correct")
    resp = await async_client.post(
        f"/admin/session/{info['session_id']}/login",
        data={"password": "wrong"},
    )
    assert resp.status_code == 401


async def test_admin_login_unknown_session_returns_401(async_client):
    # The app treats "session not found" the same as "wrong password" to avoid
    # leaking whether a session ID exists.
    resp = await async_client.post(
        "/admin/session/00000000-0000-0000-0000-000000000000/login",
        data={"password": "any"},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Admin dashboard
# ---------------------------------------------------------------------------


async def test_dashboard_without_token_returns_401(async_client, admin_session_factory):
    info = await admin_session_factory()
    resp = await async_client.get(f"/admin/session/{info['session_id']}/dashboard")
    assert resp.status_code == 401


async def test_dashboard_with_valid_token_returns_200(async_client, admin_session_factory):
    info = await admin_session_factory(title="Dashboard Session")
    resp = await async_client.get(
        f"/admin/session/{info['session_id']}/dashboard",
        cookies=auth_cookies(info["admin_token"]),
    )
    assert resp.status_code == 200
    assert "Dashboard Session" in resp.text


async def test_dashboard_wrong_session_token_returns_401(async_client, admin_session_factory):
    info1 = await admin_session_factory(title="Session A")
    info2 = await admin_session_factory(title="Session B")
    # Use token for session 2 but request dashboard for session 1
    resp = await async_client.get(
        f"/admin/session/{info1['session_id']}/dashboard",
        cookies=auth_cookies(info2["admin_token"]),
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Question management
# ---------------------------------------------------------------------------


async def test_add_freetext_question(async_client, admin_session_factory, db_session):
    info = await admin_session_factory()
    resp = await async_client.post(
        f"/admin/session/{info['session_id']}/questions",
        data={"title": "What do you think?", "question_type": "freetext", "options": ""},
        cookies=auth_cookies(info["admin_token"]),
    )
    assert resp.status_code == 303

    from sqlalchemy import select

    result = await db_session.execute(select(Question).where(Question.session_id == info["session_id"]))
    questions = result.scalars().all()
    assert len(questions) == 1
    assert questions[0].title == "What do you think?"
    assert questions[0].type == QuestionType.FREETEXT


async def test_add_wordcloud_question(async_client, admin_session_factory, db_session):
    info = await admin_session_factory()
    resp = await async_client.post(
        f"/admin/session/{info['session_id']}/questions",
        data={"title": "One word that describes this?", "question_type": "wordcloud", "options": ""},
        cookies=auth_cookies(info["admin_token"]),
    )
    assert resp.status_code == 303

    from sqlalchemy import select

    result = await db_session.execute(select(Question).where(Question.session_id == info["session_id"]))
    q = result.scalars().first()
    assert q.type == QuestionType.WORDCLOUD


async def test_add_multiple_choice_question(async_client, admin_session_factory, db_session):
    info = await admin_session_factory()
    resp = await async_client.post(
        f"/admin/session/{info['session_id']}/questions",
        data={
            "title": "Favourite colour?",
            "question_type": "multiple_choice",
            "options": "Red\nGreen\nBlue",
        },
        cookies=auth_cookies(info["admin_token"]),
    )
    assert resp.status_code == 303

    from sqlalchemy import select

    result = await db_session.execute(select(Question).where(Question.session_id == info["session_id"]))
    q = result.scalars().first()
    assert q.type == QuestionType.MULTIPLE_CHOICE
    assert json.loads(q.options) == ["Red", "Green", "Blue"]


async def test_activate_question(async_client, admin_session_factory, db_session):
    info = await admin_session_factory()

    # Add two questions
    for title in ("Q1", "Q2"):
        await async_client.post(
            f"/admin/session/{info['session_id']}/questions",
            data={"title": title, "question_type": "freetext", "options": ""},
            cookies=auth_cookies(info["admin_token"]),
        )

    from sqlalchemy import select

    result = await db_session.execute(select(Question).where(Question.session_id == info["session_id"]))
    questions = result.scalars().all()
    assert len(questions) == 2

    q_to_activate = questions[0]
    resp = await async_client.post(
        f"/admin/session/{info['session_id']}/questions/{q_to_activate.id}/activate",
        cookies=auth_cookies(info["admin_token"]),
    )
    assert resp.status_code == 303

    # Refresh and verify only one is active
    db_session.expire_all()
    result = await db_session.execute(select(Question).where(Question.session_id == info["session_id"]))
    refreshed = result.scalars().all()
    active = [q for q in refreshed if q.is_active]
    assert len(active) == 1
    assert active[0].id == q_to_activate.id


async def test_delete_question(async_client, admin_session_factory, db_session):
    info = await admin_session_factory()

    await async_client.post(
        f"/admin/session/{info['session_id']}/questions",
        data={"title": "To be deleted", "question_type": "freetext", "options": ""},
        cookies=auth_cookies(info["admin_token"]),
    )

    from sqlalchemy import select

    result = await db_session.execute(select(Question).where(Question.session_id == info["session_id"]))
    q = result.scalars().first()

    resp = await async_client.post(
        f"/admin/session/{info['session_id']}/questions/{q.id}/delete",
        cookies=auth_cookies(info["admin_token"]),
    )
    assert resp.status_code == 303

    db_session.expire_all()
    result = await db_session.execute(select(Question).where(Question.session_id == info["session_id"]))
    assert result.scalars().first() is None


# ---------------------------------------------------------------------------
# Results API
# ---------------------------------------------------------------------------


async def _create_question_with_responses(db_session, session_id, q_type, options=None):
    """Helper: insert a question + some responses directly into the DB."""

    options_json = json.dumps(options) if options else None
    q = Question(
        session_id=session_id,
        type=q_type,
        title="Test question",
        options=options_json,
    )
    db_session.add(q)
    await db_session.commit()
    await db_session.refresh(q)

    for val in options[:2] if options else ["hello", "world"]:
        db_session.add(Response(question_id=q.id, value=val))
    await db_session.commit()
    return q


async def test_results_multiple_choice(async_client, admin_session_factory, db_session):
    info = await admin_session_factory()
    q = await _create_question_with_responses(
        db_session, info["session_id"], QuestionType.MULTIPLE_CHOICE, ["Yes", "No", "Maybe"]
    )
    resp = await async_client.get(
        f"/admin/session/{info['session_id']}/results/{q.id}",
        cookies=auth_cookies(info["admin_token"]),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["type"] == "multiple_choice"
    assert "counts" in body
    assert "total" in body
    assert set(body["counts"].keys()) == {"Yes", "No", "Maybe"}


async def test_results_freetext(async_client, admin_session_factory, db_session):
    info = await admin_session_factory()
    q = await _create_question_with_responses(db_session, info["session_id"], QuestionType.FREETEXT)
    resp = await async_client.get(
        f"/admin/session/{info['session_id']}/results/{q.id}",
        cookies=auth_cookies(info["admin_token"]),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["type"] == "freetext"
    assert "responses" in body
    assert len(body["responses"]) == 2


async def test_results_unknown_question_returns_404(async_client, admin_session_factory):
    info = await admin_session_factory()
    resp = await async_client.get(
        f"/admin/session/{info['session_id']}/results/00000000-0000-0000-0000-000000000000",
        cookies=auth_cookies(info["admin_token"]),
    )
    assert resp.status_code == 404


async def test_results_without_token_returns_401(async_client, admin_session_factory, db_session):
    info = await admin_session_factory()
    q = await _create_question_with_responses(db_session, info["session_id"], QuestionType.FREETEXT)
    resp = await async_client.get(
        f"/admin/session/{info['session_id']}/results/{q.id}",
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# QR code
# ---------------------------------------------------------------------------


async def test_qr_code_returns_png(async_client, admin_session_factory):
    info = await admin_session_factory()
    resp = await async_client.get(f"/admin/session/{info['session_id']}/qr")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    # PNG magic bytes
    assert resp.content[:4] == b"\x89PNG"
