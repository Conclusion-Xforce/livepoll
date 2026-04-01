import os
import json
import io
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Depends, Form, HTTPException, WebSocket, WebSocketDisconnect, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
import qrcode

from app.database import get_db, init_db
from app.models import Session, Question, Response, QuestionType
from app.schemas import SessionCreate, QuestionCreate, ResponseCreate
from app.auth import hash_password, verify_password, create_admin_token, verify_admin_token
from app.websocket import manager

HOSTNAME = os.getenv("HOSTNAME", "localhost")
PORT = os.getenv("PORT", "8000")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="LivePoll", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


def get_base_url() -> str:
    port_suffix = f":{PORT}" if PORT not in ("80", "443") else ""
    return f"http://{HOSTNAME}{port_suffix}"


# Public routes
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/session/{session_id}", response_class=HTMLResponse)
async def participant_view(request: Request, session_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Session).where(Session.id == session_id).options(selectinload(Session.questions))
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    active_question = next((q for q in session.questions if q.is_active), None)
    options = json.loads(active_question.options) if active_question and active_question.options else []

    return templates.TemplateResponse("participant/session.html", {
        "request": request,
        "session": session,
        "question": active_question,
        "options": options,
        "base_url": get_base_url()
    })


# WebSocket for real-time updates
@app.websocket("/ws/session/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str, db: AsyncSession = Depends(get_db)):
    await manager.connect(websocket, session_id)
    try:
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "response":
                response_data = data.get("data", {})
                question_id = response_data.get("question_id")
                value = response_data.get("value", "").strip()

                if question_id and value:
                    response = Response(question_id=question_id, value=value)
                    db.add(response)
                    await db.commit()

                    # Broadcast updated results
                    await broadcast_results(session_id, question_id, db)
    except WebSocketDisconnect:
        manager.disconnect(websocket, session_id)


async def broadcast_results(session_id: str, question_id: str, db: AsyncSession):
    result = await db.execute(
        select(Question).where(Question.id == question_id).options(selectinload(Question.responses))
    )
    question = result.scalar_one_or_none()
    if not question:
        return

    responses = [{"id": r.id, "value": r.value} for r in question.responses]

    if question.type == QuestionType.MULTIPLE_CHOICE:
        options = json.loads(question.options) if question.options else []
        counts = {opt: 0 for opt in options}
        for r in question.responses:
            if r.value in counts:
                counts[r.value] += 1
        await manager.broadcast(session_id, {
            "type": "results",
            "data": {"question_id": question_id, "counts": counts, "total": len(responses)}
        })
    else:
        await manager.broadcast(session_id, {
            "type": "results",
            "data": {"question_id": question_id, "responses": responses}
        })


# Admin routes
@app.get("/admin/create", response_class=HTMLResponse)
async def admin_create_form(request: Request):
    return templates.TemplateResponse("admin/create.html", {"request": request})


@app.post("/admin/create")
async def admin_create_session(
    request: Request,
    title: str = Form(...),
    admin_password: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    session = Session(
        title=title,
        admin_password_hash=hash_password(admin_password)
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    token = create_admin_token(session.id)
    response = RedirectResponse(url=f"/admin/session/{session.id}/dashboard", status_code=303)
    response.set_cookie("admin_token", token, httponly=True, max_age=86400)
    return response


@app.get("/admin/session/{session_id}", response_class=HTMLResponse)
async def admin_login_form(request: Request, session_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return templates.TemplateResponse("admin/login.html", {
        "request": request,
        "session": session
    })


@app.post("/admin/session/{session_id}/login")
async def admin_login(
    session_id: str,
    password: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    if not session or not verify_password(password, session.admin_password_hash):
        raise HTTPException(status_code=401, detail="Invalid password")

    token = create_admin_token(session.id)
    response = RedirectResponse(url=f"/admin/session/{session.id}/dashboard", status_code=303)
    response.set_cookie("admin_token", token, httponly=True, max_age=86400)
    return response


def require_admin(session_id: str, admin_token: str | None = Cookie(None)):
    if not admin_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    token_session_id = verify_admin_token(admin_token)
    if token_session_id != session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return True


@app.get("/admin/session/{session_id}/dashboard", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    session_id: str,
    admin_token: str | None = Cookie(None),
    db: AsyncSession = Depends(get_db)
):
    require_admin(session_id, admin_token)

    result = await db.execute(
        select(Session).where(Session.id == session_id).options(selectinload(Session.questions))
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    questions = sorted(session.questions, key=lambda q: q.display_order)
    for q in questions:
        q.options_list = json.loads(q.options) if q.options else []

    return templates.TemplateResponse("admin/dashboard.html", {
        "request": request,
        "session": session,
        "questions": questions,
        "base_url": get_base_url(),
        "question_types": [t.value for t in QuestionType]
    })


@app.post("/admin/session/{session_id}/questions")
async def add_question(
    session_id: str,
    title: str = Form(...),
    question_type: str = Form(...),
    options: str = Form(""),
    admin_token: str | None = Cookie(None),
    db: AsyncSession = Depends(get_db)
):
    require_admin(session_id, admin_token)

    result = await db.execute(
        select(Session).where(Session.id == session_id).options(selectinload(Session.questions))
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    max_order = max((q.display_order for q in session.questions), default=-1) + 1

    options_list = [o.strip() for o in options.split("\n") if o.strip()] if options else None
    options_json = json.dumps(options_list) if options_list else None

    question = Question(
        session_id=session_id,
        type=QuestionType(question_type),
        title=title,
        options=options_json,
        display_order=max_order
    )
    db.add(question)
    await db.commit()

    return RedirectResponse(url=f"/admin/session/{session_id}/dashboard", status_code=303)


@app.post("/admin/session/{session_id}/questions/{question_id}/activate")
async def activate_question(
    session_id: str,
    question_id: str,
    admin_token: str | None = Cookie(None),
    db: AsyncSession = Depends(get_db)
):
    require_admin(session_id, admin_token)

    # Deactivate all questions in session
    result = await db.execute(
        select(Question).where(Question.session_id == session_id)
    )
    questions = result.scalars().all()
    for q in questions:
        q.is_active = q.id == question_id
    await db.commit()

    # Get the activated question to broadcast
    result = await db.execute(
        select(Question).where(Question.id == question_id).options(selectinload(Question.responses))
    )
    question = result.scalar_one_or_none()

    if question:
        options = json.loads(question.options) if question.options else []
        await manager.broadcast(session_id, {
            "type": "question",
            "data": {
                "id": question.id,
                "title": question.title,
                "type": question.type.value,
                "options": options
            }
        })

    return RedirectResponse(url=f"/admin/session/{session_id}/dashboard", status_code=303)


@app.post("/admin/session/{session_id}/questions/{question_id}/delete")
async def delete_question(
    session_id: str,
    question_id: str,
    admin_token: str | None = Cookie(None),
    db: AsyncSession = Depends(get_db)
):
    require_admin(session_id, admin_token)

    result = await db.execute(select(Question).where(Question.id == question_id))
    question = result.scalar_one_or_none()
    if question and question.session_id == session_id:
        await db.delete(question)
        await db.commit()

    return RedirectResponse(url=f"/admin/session/{session_id}/dashboard", status_code=303)


@app.get("/admin/session/{session_id}/qr")
async def get_qr_code(session_id: str):
    url = f"{get_base_url()}/session/{session_id}"
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    return StreamingResponse(buffer, media_type="image/png")


@app.get("/admin/session/{session_id}/results/{question_id}")
async def get_question_results(
    session_id: str,
    question_id: str,
    admin_token: str | None = Cookie(None),
    db: AsyncSession = Depends(get_db)
):
    require_admin(session_id, admin_token)

    result = await db.execute(
        select(Question).where(Question.id == question_id).options(selectinload(Question.responses))
    )
    question = result.scalar_one_or_none()
    if not question or question.session_id != session_id:
        raise HTTPException(status_code=404, detail="Question not found")

    responses = [{"id": r.id, "value": r.value} for r in question.responses]

    if question.type == QuestionType.MULTIPLE_CHOICE:
        options = json.loads(question.options) if question.options else []
        counts = {opt: 0 for opt in options}
        for r in question.responses:
            if r.value in counts:
                counts[r.value] += 1
        return {"question_id": question_id, "type": question.type.value, "counts": counts, "total": len(responses)}

    return {"question_id": question_id, "type": question.type.value, "responses": responses}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(PORT))
