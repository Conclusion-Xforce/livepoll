# LivePoll

LivePoll is a FastAPI app for running live audience polls with real-time updates over WebSockets.

## Features

- Create password-protected poll sessions
- Add and manage questions from an admin dashboard
- Support for wordcloud, multiple choice, and free-text questions
- Live participant updates through WebSockets
- QR code generation for quick session access

## Quick Start

### Local

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open: http://localhost:8000

### Docker

```bash
docker compose up --build
```

With custom hostname for QR codes:

```bash
HOSTNAME=poll.example.com docker compose up
```

## Main Endpoints

- `GET /session/{uuid}`: Participant view
- `WS /ws/session/{uuid}`: Real-time updates
- `GET /admin/session/{uuid}/dashboard`: Admin dashboard
- `GET /admin/session/{uuid}/qr`: Session QR code image

## Environment Variables

- `HOSTNAME` (default: `localhost`)
- `PORT` (default: `8000`)
- `SECRET_KEY` (token signing key)
- `DATABASE_URL` (default: `sqlite+aiosqlite:///./livepoll.db`)
