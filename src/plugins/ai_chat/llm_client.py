"""Unified LLM API client — supports Claude, OpenAI, and custom endpoints."""

from typing import Any, Dict, List

import httpx

from src.config import config


class ChatAPIError(Exception):
    """User-facing error message from the LLM API."""


class LLMClient:
    """Unified LLM API client.

    Supports three provider types:
    - claude:  Anthropic Messages API (system prompt separate from messages)
    - openai:  OpenAI Chat Completions API
    - custom:  OpenAI-compatible endpoint (DeepSeek, Ollama, vLLM, etc.)
    """

    def __init__(self) -> None:
        self.provider = config.llm_provider
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            kwargs: Dict[str, Any] = {"timeout": 60.0}
            if config.http_proxy:
                kwargs["proxy"] = config.http_proxy
            self._client = httpx.AsyncClient(**kwargs)
        return self._client

    async def chat(self, messages: List[Dict[str, str]], system_prompt: str) -> str:
        """Send conversation to LLM and return the response text."""
        if self.provider == "claude":
            return await self._chat_claude(messages, system_prompt)
        elif self.provider == "openai":
            return await self._chat_openai(messages, system_prompt)
        elif self.provider == "custom":
            return await self._chat_custom(messages, system_prompt)
        else:
            raise ChatAPIError(f"未知的 LLM provider: {self.provider}")

    # ------------------------------------------------------------------
    # Claude (Anthropic Messages API)
    # ------------------------------------------------------------------
    async def _chat_claude(
        self, messages: List[Dict[str, str]], system_prompt: str
    ) -> str:
        payload: Dict[str, Any] = {
            "model": config.claude_model,
            "system": system_prompt,
            "messages": [
                {"role": m["role"], "content": m["content"]}
                for m in messages
                if m["role"] in ("user", "assistant")
            ],
            "max_tokens": config.max_response_tokens,
            "temperature": config.temperature,
        }

        headers = {
            "x-api-key": config.claude_api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        try:
            response = await self.client.post(
                f"{config.claude_api_base}/v1/messages",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
        except httpx.TimeoutException:
            raise ChatAPIError("AI 服务响应超时，请稍后再试。")
        except httpx.HTTPStatusError as e:
            raise self._handle_http_error(e)
        except (httpx.ConnectError, httpx.NetworkError):
            raise ChatAPIError("无法连接到 AI 服务，请检查网络或代理设置。")

        # Extract text from content blocks
        text_parts: List[str] = []
        for block in data.get("content", []):
            if block.get("type") == "text":
                text_parts.append(block.get("text", ""))
        return "\n".join(text_parts)

    # ------------------------------------------------------------------
    # OpenAI (Chat Completions API)
    # ------------------------------------------------------------------
    async def _chat_openai(
        self, messages: List[Dict[str, str]], system_prompt: str
    ) -> str:
        api_messages: List[Dict[str, str]] = [
            {"role": "system", "content": system_prompt}
        ]
        api_messages.extend(messages)

        payload = {
            "model": config.openai_model,
            "messages": api_messages,
            "max_tokens": config.max_response_tokens,
            "temperature": config.temperature,
        }

        headers = {
            "Authorization": f"Bearer {config.openai_api_key}",
            "content-type": "application/json",
        }

        try:
            response = await self.client.post(
                f"{config.openai_api_base}/chat/completions",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
        except httpx.TimeoutException:
            raise ChatAPIError("AI 服务响应超时，请稍后再试。")
        except httpx.HTTPStatusError as e:
            raise self._handle_http_error(e)
        except (httpx.ConnectError, httpx.NetworkError):
            raise ChatAPIError("无法连接到 AI 服务，请检查网络或代理设置。")

        return data["choices"][0]["message"]["content"]

    # ------------------------------------------------------------------
    # Custom OpenAI-compatible endpoint
    # ------------------------------------------------------------------
    async def _chat_custom(
        self, messages: List[Dict[str, str]], system_prompt: str
    ) -> str:
        """Call custom endpoint with automatic model fallback.

        Tries the primary model first, then each backup model in order.
        Only retries on recoverable errors (5xx, timeout, network);
        auth errors (401, 403) and bad requests (400) fail immediately.
        """
        # Build the ordered model list: primary → backups
        models = [config.custom_model]
        if config.custom_backup_models:
            models.extend(
                m.strip()
                for m in config.custom_backup_models.split(",")
                if m.strip()
            )

        api_messages: List[Dict[str, str]] = [
            {"role": "system", "content": system_prompt}
        ]
        api_messages.extend(messages)

        headers = {
            "Authorization": f"Bearer {config.custom_api_key}",
            "content-type": "application/json",
        }

        last_error: ChatAPIError | None = None

        for i, model in enumerate(models):
            payload = {
                "model": model,
                "messages": api_messages,
                "max_tokens": config.max_response_tokens,
                "temperature": config.temperature,
            }

            try:
                response = await self.client.post(
                    f"{config.custom_api_base}/chat/completions",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()

                # Log if we fell back
                if i > 0:
                    from nonebot.log import logger
                    logger.info(
                        f"Fallback model {model!r} succeeded "
                        f"(primary {config.custom_model!r} was unavailable)"
                    )

                return data["choices"][0]["message"]["content"]

            except httpx.TimeoutException:
                last_error = ChatAPIError("AI 服务响应超时，请稍后再试。")
            except httpx.HTTPStatusError as e:
                # Fail fast on auth / client errors — fallback won't help
                if e.response.status_code in (400, 401, 403):
                    raise self._handle_http_error(e)
                last_error = self._handle_http_error(e)
            except (httpx.ConnectError, httpx.NetworkError):
                last_error = ChatAPIError("无法连接到 AI 服务，请检查网络或代理设置。")

        # All models exhausted — raise the last error
        assert last_error is not None
        raise last_error

    # ------------------------------------------------------------------
    # Error handling
    # ------------------------------------------------------------------
    @staticmethod
    def _handle_http_error(exc: httpx.HTTPStatusError) -> ChatAPIError:
        status = exc.response.status_code

        if status == 429:
            return ChatAPIError("AI 服务繁忙（请求过多），请稍后再试。")
        elif status == 401:
            return ChatAPIError(
                "API 鉴权失败，请检查 API Key 配置。"
            )
        elif status == 403:
            return ChatAPIError(
                "API 访问被拒绝，请检查账户权限或余额。"
            )
        elif status == 400:
            try:
                error_body = exc.response.json()
                detail = _extract_error_message(error_body)
            except Exception:
                detail = "请求参数有误"
            return ChatAPIError(f"请求错误: {detail}")
        elif status >= 500:
            return ChatAPIError(f"AI 服务端错误 (HTTP {status})，请稍后再试。")
        else:
            return ChatAPIError(
                f"AI 服务返回异常状态 (HTTP {status})，请稍后再试。"
            )

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None


def _extract_error_message(body: dict) -> str:
    """Best-effort extraction of error detail from various API formats."""
    # OpenAI / custom format
    if "error" in body:
        err = body["error"]
        if isinstance(err, dict):
            return err.get("message", str(err))
        return str(err)
    # Anthropic format
    if "error" in body:
        err = body["error"]
        if isinstance(err, dict):
            return err.get("message", str(err))
        return str(err)
    return str(body)
