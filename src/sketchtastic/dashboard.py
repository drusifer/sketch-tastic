"""Self-contained offline HTML interactive dashboard renderer (STORY-SKT-12, -17).

Bundles vendored MIT Chart.js v4.4.9 with modular static web assets from
`src/sketchtastic/assets/dashboard/` and embeds the lean analysis payload using
script-safe JSON escaping under a strict offline Content Security Policy.
"""

from __future__ import annotations

import html
import json
import re
from functools import cache
from importlib.resources import files
from typing import Any

_CSP = (
    "default-src 'none'; "
    "style-src 'unsafe-inline'; "
    "script-src 'unsafe-inline'; "
    "img-src data:; "
    "font-src 'none'; "
    "connect-src 'none'; "
    "base-uri 'none'; "
    "form-action 'none';"
)

_JS_MODULES = (
    "stats.js",
    "core.js",
    "charts.js",
    "correlations.js",
    "sankey.js",
    "explorer.js",
    "url_state.js",
    "app.js",
)

_PLACEHOLDERS = (
    "__CSP__",
    "__TITLE__",
    "__CSS__",
    "__SKETCH_PATH__",
    "__PROFILE_ID__",
    "__LAST_RUN__",
    "__DATA_JSON__",
    "__CHARTJS__",
    "__APP_JS__",
)
_PLACEHOLDER_RE = re.compile("|".join(re.escape(p) for p in _PLACEHOLDERS))


@cache
def _chartjs_source() -> str:
    return files("sketchtastic").joinpath("assets/chart.umd.min.js").read_text("utf-8")


@cache
def _dashboard_asset(name: str) -> str:
    return files("sketchtastic").joinpath("assets/dashboard", name).read_text("utf-8")


@cache
def _app_script_source() -> str:
    body = "\n".join(_dashboard_asset(module) for module in _JS_MODULES)
    return f'(function () {{\n"use strict";\n{body}\n}})();\n'


def _safe_json_for_script(value: Any) -> str:
    """Serialize JSON safe to embed inside an HTML `<script>` element."""
    raw = json.dumps(value, ensure_ascii=True, allow_nan=False, separators=(",", ":"))
    return (
        raw.replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def render_dashboard(payload: dict[str, Any], title: str | None = None) -> str:
    """Render a complete, offline, single-file HTML analysis dashboard."""
    meta = payload.get("meta", {})
    raw_title = title if title else f"Sketch Analysis — {meta.get('sketch_name', 'sketch')}"
    replacements = {
        "__CSP__": _CSP,
        "__TITLE__": html.escape(raw_title, quote=True),
        "__CSS__": _dashboard_asset("styles.css"),
        "__SKETCH_PATH__": html.escape(str(meta.get("sketch_path", "")), quote=True),
        "__PROFILE_ID__": html.escape(str(meta.get("profile_id") or "none"), quote=True),
        "__LAST_RUN__": html.escape(str(meta.get("last_run") or "none"), quote=True),
        "__DATA_JSON__": _safe_json_for_script(payload),
        "__CHARTJS__": _chartjs_source(),
        "__APP_JS__": _app_script_source(),
    }
    return _PLACEHOLDER_RE.sub(
        lambda match: replacements[match.group(0)],
        _dashboard_asset("template.html"),
    )
