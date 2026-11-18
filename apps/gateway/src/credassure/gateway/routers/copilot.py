"""Ask CredAssure as a product assistant (ADR 0035): one copilot on every page.

- ``POST /v1/copilot/chat``: a turn with or without an open case (``case_id`` from the page the
  person is on; the gateway checks they may see it). The case route ``/v1/cases/{id}/chat`` is
  unchanged, so the frozen evaluation harness is unaffected.
- ``POST /v1/copilot/chat/stream`` (CP-12): the same turn as server-sent events. ``stage`` events
  say what the pipeline is doing; the answer text is sent as ``delta`` events only **after** the
  Critic has passed it, never as raw model tokens, then one ``final`` event with the full reply.
- ``GET``/``POST /v1/cases/{id}/chat[/reset]`` (CP-11): this user's own history in the case, and
  a reset that stops replaying it to the model (a marker; nothing is deleted).
- ``POST /v1/copilot/feedback`` (CP-12): thumbs up or down with a fixed reason code.

No route here accepts, signs or submits anything, and none reads another person's turns.
"""

import asyncio
import json
import logging
import re
import threading
from collections import Counter
from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from limits import parse
from pydantic import BaseModel, Field

from credassure.core.errors import ApiErrorCode
from credassure.gateway.deps import Svc, User, visible_case
from credassure.gateway.problems import ProblemError

router = APIRouter(prefix="/v1", tags=["copilot"])
_log = logging.getLogger("credassure.gateway")
CASE_ID = r"^[A-Za-z0-9-]{1,16}$"
_WORDS = re.compile(r"\S+\s*")
DELTA_WORDS = 6  # words per delta event: a readable reveal, not a token stream
# A copilot turn holds a worker thread for a whole model call, so each person gets at most two at a
# time and twenty a minute, on top of the gateway-wide limit (security review, ADR 0035).
PER_USER_AT_ONCE = 2
COPILOT_RATE = parse("20/minute")
_busy: Counter[str] = Counter()
_busy_lock = threading.Lock()
_tasks: set["asyncio.Task[None]"] = set()  # keeps a stream's worker referenced until it ends


@contextmanager
def _admit(request: Request, user_id: str) -> Iterator[None]:
    """One slot of this user's copilot capacity, or 429 RATE_LIMITED."""
    if not request.app.state.copilot_limiter.hit(COPILOT_RATE, user_id):
        raise ProblemError(429, "too many questions; wait a minute", ApiErrorCode.RATE_LIMITED)
    with _busy_lock:
        if _busy[user_id] >= PER_USER_AT_ONCE:
            raise ProblemError(
                429, "wait for your current answer to finish", ApiErrorCode.RATE_LIMITED
            )
        _busy[user_id] += 1
    try:
        yield
    finally:
        with _busy_lock:
            _busy[user_id] -= 1
            if _busy[user_id] <= 0:
                del _busy[user_id]


class CopilotChat(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    case_id: Annotated[str | None, Field(pattern=CASE_ID)] = None


class Feedback(BaseModel):
    trace_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    rating: Literal["up", "down"]
    # A fixed code, never free text: feedback carries no personal data and no instructions.
    reason: Literal["wrong", "not_cited", "unclear", "unhelpful", "unsafe", "other"] | None = None


@router.post("/copilot/chat")
def chat(body: CopilotChat, who: User, svc: Svc, request: Request) -> dict[str, Any]:
    """One copilot turn on any page (ADR 0035): help, regulations and policies everywhere; case
    status, blockers and figures only with a ``case_id`` the caller may see."""
    with _admit(request, who.user_id):
        reply: dict[str, Any] = svc.service.converse(who, body.case_id, body.message)
    return reply


def _sse(event: str, data: Any) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post(
    "/copilot/chat/stream",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}, "description": "SSE"}},
)
async def chat_stream(
    body: CopilotChat, who: User, svc: Svc, request: Request
) -> StreamingResponse:
    """CP-12 as SSE: ``stage`` → ``delta``… → ``final`` (or ``error``). Text leaves only after the
    Critic, so a blocked answer never shows a partial sentence."""
    if body.case_id is not None:
        visible_case(svc, who, body.case_id)  # 404 as a normal response, before the stream opens
    slot = _admit(request, who.user_id)
    slot.__enter__()  # 429 as a normal response; released when the worker ends
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[tuple[str, Any]] = asyncio.Queue()
    rid = getattr(request.state, "request_id", None)

    def progress(stage: str) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, ("stage", {"stage": stage}))

    async def work() -> None:
        try:
            reply = await asyncio.to_thread(
                svc.service.converse, who, body.case_id, body.message, progress
            )
            await queue.put(("reply", reply))
        except ProblemError as e:
            await queue.put(
                ("error", {"code": e.code.value, "detail": e.detail, "request_id": rid})
            )
        except Exception:  # the stream reports it; the stack goes to the log with the request id
            _log.exception("copilot stream failed", extra={"request_id": rid})
            await queue.put(
                ("error", {"code": "INTERNAL", "detail": "copilot failed", "request_id": rid})
            )
        finally:
            slot.__exit__(None, None, None)

    task = asyncio.create_task(work())
    _tasks.add(task)  # a disconnect does not cancel the model call; the turn is still recorded
    task.add_done_callback(_tasks.discard)

    async def stream() -> AsyncIterator[str]:
        try:
            while True:
                kind, data = await queue.get()
                if kind == "stage":
                    yield _sse("stage", data)
                    continue
                if kind == "error":
                    yield _sse("error", data)
                    return
                words = _WORDS.findall(data["answer"])
                for i in range(0, len(words), DELTA_WORDS):
                    yield _sse("delta", {"text": "".join(words[i : i + DELTA_WORDS])})
                yield _sse("final", data)
                return
        finally:
            if not task.done():
                await asyncio.shield(task)

    return StreamingResponse(
        stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"}
    )


@router.get("/cases/{case_id}/chat")
def history(case_id: str, who: User, svc: Svc) -> dict[str, Any]:
    """CP-11: this user's own turns in this case since their last reset (redacted)."""
    out: dict[str, Any] = svc.service.chat_history(who, case_id)
    return out


@router.post("/cases/{case_id}/chat/reset")
def reset(case_id: str, who: User, svc: Svc) -> dict[str, Any]:
    """CP-11: start a new conversation in this case. Earlier turns are kept as evidence but are
    no longer shown or replayed to the model."""
    out: dict[str, Any] = svc.service.reset_chat(who, case_id)
    return out


@router.post("/copilot/feedback")
def feedback(body: Feedback, who: User, svc: Svc) -> dict[str, Any]:
    """CP-12: rate one answer you received. 404 for an answer that is not yours."""
    out: dict[str, Any] = svc.service.feedback(who, body.trace_id, body.rating, body.reason)
    return out
