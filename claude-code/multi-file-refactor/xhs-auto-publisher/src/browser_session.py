from __future__ import annotations

from pathlib import Path
from typing import Any


class BrowserSession:
    def __init__(
        self,
        *,
        profile_dir: Path,
        headless: bool,
        slow_mo_ms: int = 80,
        audit: Any = None,
        debug_url_keywords: list[str] | None = None,
    ) -> None:
        self.profile_dir = profile_dir
        self.headless = headless
        self.slow_mo_ms = slow_mo_ms
        self.audit = audit
        self.debug_url_keywords = [k.lower() for k in (debug_url_keywords or [])]
        self.playwright: Any = None
        self.context: Any = None
        self.page: Any = None

    async def __aenter__(self) -> "BrowserSession":
        try:
            from playwright.async_api import async_playwright
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "playwright is not installed. Install it with: pip install playwright && python -m playwright install chromium"
            ) from exc

        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self.playwright = await async_playwright().start()
        self.context = await self.playwright.chromium.launch_persistent_context(
            user_data_dir=str(self.profile_dir),
            headless=self.headless,
            slow_mo=self.slow_mo_ms,
            viewport={"width": 1440, "height": 1000},
            args=["--disable-blink-features=AutomationControlled"],
        )
        self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()
        if self.audit:
            self._attach_debug_hooks()
        return self

    def _attach_debug_hooks(self) -> None:
        if not self.page or not self.audit:
            return

        def short(text: Any, limit: int = 500) -> str:
            s = str(text or "")
            return s if len(s) <= limit else s[:limit] + "..."

        def on_console(msg: Any) -> None:
            try:
                level = msg.type
                text = short(msg.text)
                if level in {"error", "warning"} or any(k in text.lower() for k in ["publish", "fail", "error", "接口", "失败", "问题"]):
                    self.audit.event("console_message", level=level, text=text)
            except Exception:
                pass

        def on_page_error(err: Any) -> None:
            try:
                self.audit.event("page_error", error=short(err, 1000))
            except Exception:
                pass

        def is_interesting_url(url: str) -> bool:
            lowered = url.lower()
            base = ["publish", "note", "post", "upload", "creator", "draft", "web_api", "api/sns"]
            keys = base + self.debug_url_keywords
            return any(k in lowered for k in keys)

        def on_request(req: Any) -> None:
            try:
                url = str(req.url)
                if not is_interesting_url(url):
                    return
                post_data = req.post_data if req.method.upper() in {"POST", "PUT", "PATCH"} else None
                self.audit.event(
                    "request_seen",
                    method=req.method,
                    resource_type=req.resource_type,
                    url=short(url, 800),
                    post_data=short(post_data, 1200) if post_data else None,
                )
            except Exception:
                pass

        def on_request_failed(req: Any) -> None:
            try:
                failure = req.failure() or {}
                self.audit.event(
                    "request_failed",
                    method=req.method,
                    url=short(req.url, 800),
                    resource_type=req.resource_type,
                    error_text=failure.get("errorText", ""),
                )
            except Exception:
                pass

        def on_response(resp: Any) -> None:
            try:
                url = str(resp.url)
                interesting = is_interesting_url(url) or resp.status >= 400
                if not interesting:
                    return
                self.audit.event(
                    "response_seen",
                    status=resp.status,
                    url=short(url, 800),
                )
            except Exception:
                pass

        async def on_request_finished(req: Any) -> None:
            try:
                url = str(req.url)
                if not is_interesting_url(url):
                    return
                resp = await req.response()
                status = resp.status if resp else None
                body_text = None
                if resp and status and status >= 400:
                    try:
                        body_text = short(await resp.text(), 1500)
                    except Exception:
                        body_text = None
                self.audit.event(
                    "request_finished",
                    method=req.method,
                    url=short(url, 800),
                    status=status,
                    response_text=body_text,
                )
            except Exception:
                pass

        self.page.on("console", on_console)
        self.page.on("pageerror", on_page_error)
        self.page.on("request", on_request)
        self.page.on("requestfailed", on_request_failed)
        self.page.on("response", on_response)
        self.page.on("requestfinished", on_request_finished)

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if self.context:
            await self.context.close()
        if self.playwright:
            await self.playwright.stop()
