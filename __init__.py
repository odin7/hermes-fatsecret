from __future__ import annotations

import json
from pathlib import Path

from . import schemas, tools


def register(ctx) -> None:  # noqa: ANN001
    ctx.register_tool(
        name="analyze_food_photo",
        toolset="fatsecret-food",
        schema=schemas.ANALYZE_FOOD_PHOTO,
        handler=tools.analyze_food_photo,
    )
    ctx.register_tool(
        name="search_food",
        toolset="fatsecret-food",
        schema=schemas.SEARCH_FOOD,
        handler=tools.search_food,
    )
    ctx.register_tool(
        name="log_food_entry",
        toolset="fatsecret-food",
        schema=schemas.LOG_FOOD_ENTRY,
        handler=tools.log_food_entry,
    )

    ctx.register_skill("log-food-from-photo", Path(__file__).parent / "skills/log-food-from-photo/SKILL.md")
    ctx.register_hook("post_tool_call", _post_tool_call_hook)


def _post_tool_call_hook(
    tool_name: str,
    args: dict,
    result: str,
    task_id: str,
    duration_ms: int,
    **kwargs,
) -> None:
    if tool_name not in {"analyze_food_photo", "search_food", "log_food_entry"}:
        return
    try:
        parsed = json.loads(result)
        status = parsed.get("status", "ok")
    except Exception:
        status = "error"
    # Emit a structured log line; plug into any observability stack present
    print(
        json.dumps({
            "event": "fatsecret_tool",
            "tool": tool_name,
            "status": status,
            "duration_ms": duration_ms,
            "task_id": task_id,
        })
    )
