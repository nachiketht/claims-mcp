import os

import httpx
import ollama


class ChatModel:
    def complete(self, prompt: str) -> str:
        raise NotImplementedError


class OllamaChat(ChatModel):
    def __init__(self) -> None:
        self.host = os.environ.get("OLLAMA_HOST", "http://host.docker.internal:11434")
        self.model = os.environ.get("OLLAMA_MODEL", "qwen3:8b")
        self.client = ollama.Client(host=self.host, timeout=60)

    def complete(self, prompt: str) -> str:
        error = None
        for _ in range(2):
            try:
                response = self.client.chat(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    think=False,
                )
                return response.message.content or ""
            except (httpx.ConnectError, httpx.TimeoutException) as caught:
                error = caught
        raise RuntimeError(f"cannot reach the model {self.model} at {self.host}") from error
