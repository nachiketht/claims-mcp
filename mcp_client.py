import asyncio
import concurrent.futures
import os
import sys
import threading
from pathlib import Path

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

ROOT = Path(__file__).resolve().parent
PASSED_ENV = ("CLAIMS_LOG", "CLAIMS_AS_OF", "CLAIMS_REVIEW_QUEUE")
CALL_TIMEOUT = 60


class ToolCaller:
    def list_tools(self) -> list:
        raise NotImplementedError

    def call_tool(self, name: str, arguments: dict) -> str:
        raise NotImplementedError

    def close(self) -> None:
        pass


class StdioMcpClient(ToolCaller):
    """One server.py process and one MCP session, kept open until close()."""

    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._requests: asyncio.Queue | None = None
        self._done: concurrent.futures.Future | None = None

    def __enter__(self) -> "StdioMcpClient":
        return self

    def __exit__(self, *_exc) -> None:
        self.close()

    def list_tools(self) -> list:
        result = self._submit(lambda session: session.list_tools())
        return [
            {
                "name": tool.name,
                "description": tool.description or "",
                "arguments": {
                    "properties": (tool.input_schema or {}).get("properties", {}),
                    "required": (tool.input_schema or {}).get("required", []),
                },
            }
            for tool in result.tools
        ]

    def call_tool(self, name: str, arguments: dict) -> str:
        result = self._submit(lambda session: session.call_tool(name, arguments))
        if not result.content:
            return ""
        return result.content[0].text

    def close(self) -> None:
        if self._loop is None:
            return
        self._loop.call_soon_threadsafe(self._requests.put_nowait, None)
        try:
            self._done.result(timeout=CALL_TIMEOUT)
        finally:
            self._loop.call_soon_threadsafe(self._loop.stop)
            self._thread.join(timeout=CALL_TIMEOUT)
            self._loop.close()
            self._loop = None

    def _submit(self, call):
        if self._loop is None:
            self._start()
        future: concurrent.futures.Future = concurrent.futures.Future()
        self._loop.call_soon_threadsafe(self._requests.put_nowait, (call, future))
        return future.result(timeout=CALL_TIMEOUT)

    def _start(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._thread.start()
        ready: concurrent.futures.Future = concurrent.futures.Future()
        self._done = asyncio.run_coroutine_threadsafe(self._serve(ready), self._loop)
        try:
            ready.result(timeout=CALL_TIMEOUT)
        except BaseException:
            self._loop.call_soon_threadsafe(self._loop.stop)
            self._thread.join(timeout=CALL_TIMEOUT)
            self._loop.close()
            self._loop = None
            raise

    async def _serve(self, ready: concurrent.futures.Future) -> None:
        # The session must be opened and closed by the same task, so every
        # call is queued to this one coroutine instead of run as its own task.
        env = {key: os.environ[key] for key in PASSED_ENV if os.environ.get(key)}
        params = StdioServerParameters(
            command=sys.executable,
            args=[str(ROOT / "server.py")],
            env=env or None,
        )
        try:
            async with (
                stdio_client(params) as (read, write),
                ClientSession(read, write) as session,
            ):
                await session.initialize()
                self._requests = asyncio.Queue()
                ready.set_result(None)
                while (item := await self._requests.get()) is not None:
                    call, future = item
                    try:
                        future.set_result(await call(session))
                    except Exception as error:
                        future.set_exception(error)
        except BaseException as error:
            if not ready.done():
                ready.set_exception(error)
            raise
