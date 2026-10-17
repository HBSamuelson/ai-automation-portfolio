"""FastAPI desk: a customer channel plus the human queue for the same chat."""

from __future__ import annotations

import argparse
import sys
import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from support_agent.agent import SupportAgent
from support_agent.planner import PlannerConfigError, PlannerError

PAGE = Path(__file__).resolve().parent / "static" / "index.html"


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    session_id: str | None = None


def create_app(mode: str | None = None) -> FastAPI:
    try:
        agent = SupportAgent.create(mode=mode)
    except PlannerConfigError as exc:
        raise RuntimeError(str(exc)) from exc

    app = FastAPI(title="Northline desk")
    app.state.agent = agent
    app.state.sessions = {}
    app.state.locks = {}
    app.state.guard = threading.Lock()

    @app.get("/api/health")
    def health() -> dict:
        return {
            "ok": True,
            "mode": agent.mode,
            "store": agent.catalog.store_name,
            "as_of": agent.catalog.as_of.isoformat(),
            "model": agent.model_name,
        }

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(PAGE)

    @app.post("/api/chat")
    def chat(body: ChatRequest) -> dict:
        message = body.message.strip()
        if not message:
            raise HTTPException(status_code=400, detail="Message is empty.")
        session = _session_for(app, body.session_id)
        lock = _lock_for(app, session.id)
        with lock:
            try:
                result = agent.handle(session, message)
            except PlannerError as exc:
                raise HTTPException(status_code=502, detail=str(exc)) from exc
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {
            "session_id": session.id,
            "reply": result.reply,
            "escalated": result.escalated,
            "tools_used": result.tools_used,
            "tickets": result.tickets,
            "returns": result.returns,
            "mode": agent.mode,
        }

    return app


def _session_for(app: FastAPI, session_id: str | None):
    with app.state.guard:
        if session_id is None:
            session = app.state.agent.new_session()
            app.state.sessions[session.id] = session
            return session
        session = app.state.sessions.get(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Unknown session. Start a new chat.")
        return session


def _lock_for(app: FastAPI, session_id: str) -> threading.Lock:
    with app.state.guard:
        lock = app.state.locks.get(session_id)
        if lock is None:
            lock = threading.Lock()
            app.state.locks[session_id] = lock
        return lock


app = create_app()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Serve the Northline support desk.")
    parser.add_argument("--mock", action="store_true", help="Force the offline planner.")
    parser.add_argument("--live", action="store_true", help="Force the OpenAI-compatible planner.")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8741)
    args = parser.parse_args(argv)
    if args.mock and args.live:
        print("Choose either --mock or --live.", file=sys.stderr)
        return 2
    mode = "mock" if args.mock else "live" if args.live else None
    try:
        application = create_app(mode=mode)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    import uvicorn

    uvicorn.run(application, host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
