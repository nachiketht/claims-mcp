import json
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, StreamingResponse

from agent import run

app = FastAPI()
REVIEWS = Path("data/review_queue.json")
HOST_ERROR = "cannot reach the model at host.docker.internal:11434"


@app.get("/")
def index() -> FileResponse:
    return FileResponse("static/index.html")


@app.get("/reviews")
def reviews() -> list:
    if not REVIEWS.exists() or REVIEWS.stat().st_size == 0:
        return []
    return json.loads(REVIEWS.read_text(encoding="utf-8"))


@app.post("/decide")
async def decide(request: Request) -> StreamingResponse:
    body = await request.json()
    sentence = str(body.get("request", ""))

    def events():
        try:
            for event in run(sentence):
                yield _sse(event["type"], event["text"])
        except RuntimeError:
            yield _sse("error", HOST_ERROR)

    return StreamingResponse(events(), media_type="text/event-stream")


def _sse(kind: str, text: str) -> str:
    return f"event: {kind}\ndata: {json.dumps(text)}\n\n"
