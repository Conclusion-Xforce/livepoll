# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Run Commands

```bash
# Development (requires Python 3.11+)
pip install -r requirements.txt
uvicorn app.main:app --reload

# Docker
docker compose up --build

# With custom hostname
HOSTNAME=poll.example.com docker compose up
```

## Architecture

LivePoll is a FastAPI web application for live audience polling with real-time WebSocket updates.

### Core Components

- **app/main.py** - FastAPI routes, WebSocket endpoint, QR code generation
- **app/models.py** - SQLAlchemy models: Session, Question (wordcloud/multiple_choice/freetext), Response
- **app/websocket.py** - ConnectionManager for broadcasting results to participants
- **app/auth.py** - bcrypt password hashing, itsdangerous session tokens

### Data Flow

1. Admin creates Session with password → gets UUID
2. Admin adds Questions to session
3. Admin activates a question → broadcasts to participants via WebSocket
4. Participants submit responses → stored in Response table
5. Server broadcasts updated results to all connected clients

### Key Routes

- `GET /session/{uuid}` - Participant polling view
- `WS /ws/session/{uuid}` - WebSocket for real-time updates
- `GET /admin/session/{uuid}/dashboard` - Admin question management
- `GET /admin/session/{uuid}/qr` - QR code PNG for session URL

### Environment Variables

- `HOSTNAME` - Public hostname for QR codes (default: localhost)
- `PORT` - Server port (default: 8000)
- `SECRET_KEY` - Token signing key
- `DATABASE_URL` - SQLite path (default: sqlite+aiosqlite:///./livepoll.db)
