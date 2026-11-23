"""Bộ kết nối AI (Gemini REST API thuần Python + OpenAI/DeepSeek/Grok/Claude) — không lỗi lazy_import khi đóng gói .exe."""
from __future__ import annotations
import base64
import json
import mimetypes
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class AIUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


@dataclass
class AIResult:
    text: str
    parsed: object | None = None
    finish_reason: str = "STOP"
    usage: AIUsage = field(default_factory=AIUsage)


@dataclass
class AIConfig:
    provider: str = "gemini"
    api_key: str = ""
    model: str = "gemini-2.5-flash"
    temperature: float = 0.2
    max_output_tokens: int = 32768
    thinking_budget: int | None = None
    max_retries: int = 3


def _strip_json_schema_unsupported(obj):
    """Loại bỏ các khóa JSON Schema mà Gemini REST API không chấp nhận (title, additionalProperties, $defs)."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k in ("title", "additionalProperties", "default"):
                continue
            out[k] = _strip_json_schema_unsupported(v)
        return out
    if isinstance(obj, list):
        return [_strip_json_schema_unsupported(x) for x in obj]
    return obj


class AIProviderClient:
    OPENAI_URLS = {
        "openai": "https://api.openai.com/v1/chat/completions",
        "deepseek": "https://api.deepseek.com/v1/chat/completions",
        "grok": "https://api.x.ai/v1/chat/completions",
    }

    def __init__(self, config: AIConfig):
        self.config = config

    def _gemini_key(self) -> str:
        key = (self.config.api_key or os.getenv("GEMINI_API_KEY", "")).strip()
        if not key:
            raise RuntimeError("Thiếu Gemini API Key. Hãy nhập API Key trong mục 'Tuỳ chọn' rồi bấm 'Lưu'.")
        return key

    def _with_backoff(self, fn: Callable):
        delay = 2.0
        for attempt in range(max(1, self.config.max_retries)):
            try:
                return fn()
            except urllib.error.HTTPError as exc:
                err_body = ""
                try:
                    err_body = exc.read().decode("utf-8", errors="replace")
                except Exception:
                    pass
                code = exc.code
                if code in (429, 500, 503) and attempt < self.config.max_retries - 1:
                    time.sleep(delay)
                    delay *= 2.0
                    continue
                if code in (400, 401, 403):
                    raise RuntimeError(f"Gemini API từ chối yêu cầu (HTTP {code}). Kiểm tra lại API Key hoặc quyền truy cập.\nChi tiết: {err_body[:350]}") from exc
                if code == 429:
                    raise RuntimeError(f"Gemini API hết hạn mức tạm thời (HTTP 429). Hãy chờ vài giây rồi thử lại.\nChi tiết: {err_body[:350]}") from exc
                raise RuntimeError(f"Lỗi Gemini API (HTTP {code}): {err_body[:350]}") from exc
            except Exception as exc:
                msg = str(exc).lower()
                if not any(k in msg for k in ("429", "rate", "quota", "timeout", "503", "timed out")) or attempt == self.config.max_retries - 1:
                    raise
                time.sleep(delay)
                delay *= 2.0

    def _gemini_post(self, payload: dict, timeout: int = 180) -> dict:
        key = self._gemini_key()
        model = (self.config.model or "gemini-2.5-flash").strip()
        if model.startswith("models/"):
            model = model[len("models/"):]
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{urllib.parse.quote(model)}:generateContent?key={urllib.parse.quote(key)}"
        req = urllib.request.Request(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))

    @staticmethod
    def _parse_gemini_response(data: dict) -> AIResult:
        cands = data.get("candidates") or []
        if not cands:
            fb = data.get("promptFeedback") or {}
            raise RuntimeError(f"Gemini không trả về nội dung (promptFeedback={fb}).")
        c0 = cands[0]
        parts = (c0.get("content") or {}).get("parts") or []
        text = "".join(str(p.get("text") or "") for p in parts if isinstance(p, dict))
        reason = str(c0.get("finishReason") or "STOP")
        um = data.get("usageMetadata") or {}
        usage = AIUsage(
            int(um.get("promptTokenCount") or 0),
            int(um.get("candidatesTokenCount") or 0),
            int(um.get("totalTokenCount") or 0),
        )
        return AIResult(text=text, finish_reason=reason, usage=usage)

    def generate_gemini_multimodal_file(
        self,
        file_path: str,
        instruction: str,
        mime_type: str | None = None,
    ) -> AIResult:
        """Gửi trực tiếp tệp PDF hoặc Ảnh tới Gemini REST API (inlineData base64) — không cần SDK google-genai."""
        with open(file_path, "rb") as f:
            raw = f.read()
        if not mime_type:
            ext = os.path.splitext(file_path)[1].lower()
            mime_type = {
                ".pdf": "application/pdf",
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".webp": "image/webp",
            }.get(ext) or mimetypes.guess_type(file_path)[0] or "application/octet-stream"

        b64 = base64.b64encode(raw).decode("ascii")
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"inlineData": {"mimeType": mime_type, "data": b64}},
                        {"text": instruction},
                    ],
                }
            ],
            "generationConfig": {
                "temperature": self.config.temperature,
                "maxOutputTokens": self.config.max_output_tokens,
            },
        }
        data = self._with_backoff(lambda: self._gemini_post(payload, timeout=240))
        return self._parse_gemini_response(data)

    def generate_structured(self, prompt: str, schema_cls, system_instruction: str = "") -> AIResult:
        if self.config.provider == "gemini":
            gen_cfg: dict = {
                "temperature": self.config.temperature,
                "maxOutputTokens": self.config.max_output_tokens,
                "responseMimeType": "application/json",
            }
            if hasattr(schema_cls, "model_json_schema"):
                raw_schema = schema_cls.model_json_schema()
                if "$defs" not in raw_schema:
                    gen_cfg["responseSchema"] = _strip_json_schema_unsupported(raw_schema)
            payload: dict = {
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": gen_cfg,
            }
            if system_instruction:
                payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}
            data = self._with_backoff(lambda: self._gemini_post(payload, timeout=120))
            res = self._parse_gemini_response(data)
            parsed = schema_cls.model_validate_json(res.text) if res.text else None
            return AIResult(res.text, parsed, res.finish_reason, res.usage)

        if self.config.provider in self.OPENAI_URLS:
            schema_js = json.dumps(schema_cls.model_json_schema(), ensure_ascii=False)
            msgs = ([{"role": "system", "content": system_instruction}] if system_instruction else []) + [{"role": "user", "content": f"{prompt}\nJSON Schema:\n{schema_js}"}]
            req = urllib.request.Request(
                self.OPENAI_URLS[self.config.provider],
                data=json.dumps({"model": self.config.model, "messages": msgs, "temperature": self.config.temperature, "response_format": {"type": "json_object"}}).encode("utf-8"),
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.config.api_key}"}, method="POST",
            )
            data = self._with_backoff(lambda: json.loads(urllib.request.urlopen(req, timeout=90).read().decode("utf-8")))
            txt, u = data["choices"][0]["message"]["content"], data.get("usage", {})
            return AIResult(txt, schema_cls.model_validate_json(txt), usage=AIUsage(u.get("prompt_tokens", 0), u.get("completion_tokens", 0), u.get("total_tokens", 0)))

        if self.config.provider == "claude":
            schema_js = json.dumps(schema_cls.model_json_schema(), ensure_ascii=False)
            req = urllib.request.Request(
                "https://api.anthropic.com/v1/messages",
                data=json.dumps({"model": self.config.model, "max_tokens": min(self.config.max_output_tokens, 8192), "system": system_instruction or "Chỉ trả JSON.", "messages": [{"role": "user", "content": f"{prompt}\nSchema:\n{schema_js}"}]}).encode("utf-8"),
                headers={"Content-Type": "application/json", "x-api-key": self.config.api_key, "anthropic-version": "2023-06-01"}, method="POST",
            )
            data = self._with_backoff(lambda: json.loads(urllib.request.urlopen(req, timeout=90).read().decode("utf-8")))
            txt = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
            u = data.get("usage", {})
            return AIResult(txt, schema_cls.model_validate_json(txt), usage=AIUsage(u.get("input_tokens", 0), u.get("output_tokens", 0), u.get("input_tokens", 0) + u.get("output_tokens", 0)))
        raise ValueError(f"Provider không hỗ trợ: {self.config.provider}")

    def stream_gemini_multimodal(self, file_part, instruction: str, on_chunk: Callable[[str], None] | None = None) -> AIResult:
        """Tương thích ngược: nếu file_part là đường dẫn tệp thì gọi trực tiếp REST API."""
        if isinstance(file_part, (str, os.PathLike)):
            res = self.generate_gemini_multimodal_file(str(file_part), instruction)
            if on_chunk and res.text:
                on_chunk(res.text)
            return res
        raise RuntimeError("Hãy truyền đường dẫn tệp trực tiếp cho generate_gemini_multimodal_file.")
