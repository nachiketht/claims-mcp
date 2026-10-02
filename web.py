import json
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, StreamingResponse

from agent import run
from review_queue import JsonFileQueue

app = FastAPI()
STATIC = Path(__file__).resolve().parent / "static"
HOST_ERROR = "cannot reach the model at host.docker.internal:11434"


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/reviews")
def reviews() -> list:
    return JsonFileQueue()._read()


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
