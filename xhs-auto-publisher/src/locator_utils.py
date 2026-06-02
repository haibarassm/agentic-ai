from __future__ import annotations

from typing import Any


class LocatorNotFound(RuntimeError):
    pass


async def first_visible(page: Any, specs: list[dict[str, Any]], *, timeout_ms: int = 1500) -> Any:
    errors: list[str] = []
    for spec in specs:
        try:
            locator = build_locator(page, spec)
            await locator.first.wait_for(state="visible", timeout=timeout_ms)
            return locator.first
        except Exception as exc:  # noqa: BLE001 - keep trying candidate selectors.
            errors.append(f"{spec}: {exc}")
    raise LocatorNotFound("; ".join(errors))


async def first_attached(page: Any, specs: list[dict[str, Any]], *, timeout_ms: int = 1500) -> Any:
    errors: list[str] = []
    for spec in specs:
        try:
            locator = build_locator(page, spec)
            await locator.first.wait_for(state="attached", timeout=timeout_ms)
            return locator.first
        except Exception as exc:  # noqa: BLE001 - keep trying candidate selectors.
            errors.append(f"{spec}: {exc}")
    raise LocatorNotFound("; ".join(errors))


async def any_visible(page: Any, specs: list[dict[str, Any]], *, timeout_ms: int = 1000) -> bool:
    try:
        await first_visible(page, specs, timeout_ms=timeout_ms)
        return True
    except LocatorNotFound:
        return False


def build_locator(page: Any, spec: dict[str, Any]) -> Any:
    kind = spec.get("kind")
    value = spec.get("value")
    if kind == "text":
        return page.get_by_text(str(value), exact=False)
    if kind == "placeholder":
        return page.get_by_placeholder(str(value), exact=False)
    if kind == "role":
        role = spec.get("role")
        name = spec.get("name")
        return page.get_by_role(str(role), name=str(name) if name else None)
    if kind == "css":
        return page.locator(str(value))
    raise ValueError(f"unsupported selector kind: {kind}")


async def fill_first(page: Any, specs: list[dict[str, Any]], value: str, *, timeout_ms: int = 2500) -> None:
    locator = await first_visible(page, specs, timeout_ms=timeout_ms)
    try:
        await locator.fill(value)
    except Exception:
        await locator.click()
        await page.keyboard.press("Control+A")
        await page.keyboard.type(value)


async def click_first(page: Any, specs: list[dict[str, Any]], *, timeout_ms: int = 2500) -> None:
    locator = await first_visible(page, specs, timeout_ms=timeout_ms)
    await locator.click()
