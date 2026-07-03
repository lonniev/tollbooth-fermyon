"""tollbooth-fermyon — DPYC weather Operator as a Spin WASI component.

A self-contained MCP: the standard DPYC toolset is produced by the wheel's
`register_standard_tools()`; the three weather tools are decorated methods backed
by the Open-Meteo REST API. Tool metadata (inputSchema) is generated here from
each function's signature and docstring by `schema.tool_schema` — the conventional
way, with no FastMCP and no runtime pydantic. The tool list is a consequence of
the code.
"""

import inspect
import json
from typing import Optional

from wit_world import exports
from wit_world.imports import mcp as mcp_types

from tollbooth.tool_identity import ToolIdentity, STANDARD_IDENTITIES, capability_uuid
from tollbooth.runtime import OperatorRuntime, register_standard_tools

import weather
from schema import tool_schema


# --- middle layer: FastMCP-compatible sink recording the wheel's registrations
class WasmMcp:
    def __init__(self, name: str = "") -> None:
        self.name = name
        self.registry: dict = {}

    def tool(self, name=None, **_kw):
        def deco(fn):
            self.registry[name or fn.__name__] = fn
            return fn
        return deco


# Frozen domain-tool UUIDs — stable across renames; pricing rows key off these.
GET_CURRENT = "b7327eb8-92b4-5252-84e0-ba3f437a16ed"
GET_FORECAST = "b6d0e596-3aec-5a62-980b-7875aa04d079"
GET_HISTORICAL = "5608f3e9-44c4-5b28-9744-704af6d701f0"

_DOMAIN = {
    GET_CURRENT: ToolIdentity(tool_id=GET_CURRENT, capability="get_current_weather",
                              category="read", intent="Get current weather conditions"),
    GET_FORECAST: ToolIdentity(tool_id=GET_FORECAST, capability="get_weather_forecast",
                               category="write", intent="Get weather forecast"),
    GET_HISTORICAL: ToolIdentity(tool_id=GET_HISTORICAL, capability="get_historical_weather",
                                 category="heavy", intent="Get historical weather data"),
}

runtime = OperatorRuntime(
    tool_registry={**STANDARD_IDENTITIES, **_DOMAIN},
    service_name="tollbooth-fermyon",
)
_mcp = WasmMcp("tollbooth-fermyon")

tool = register_standard_tools(
    _mcp, "weather", runtime,
    service_name="tollbooth-fermyon", service_version="0.1.0",
)


@tool
@runtime.paid_tool(capability_uuid("get_current_weather"))
async def current(latitude: float, longitude: float, npub: str = "", dpop_token: str = "") -> dict:
    """Get current weather conditions for a location.

    Returns temperature, wind speed, and weather code from Open-Meteo.

    Args:
        latitude: Latitude (-90 to 90).
        longitude: Longitude (-180 to 180).
        npub: Required. Your Nostr public key (npub1...) for credit billing.
        dpop_token: A kind-27235 Nostr event signed by npub for this tool.
    """
    return await weather.get_current(latitude, longitude)


@tool
@runtime.paid_tool(capability_uuid("get_weather_forecast"))
async def forecast(latitude: float, longitude: float, days: int = 7, npub: str = "", dpop_token: str = "") -> dict:
    """Get a multi-day weather forecast for a location.

    Returns daily high/low temperatures and precipitation for 1-16 days.

    Args:
        latitude: Latitude (-90 to 90).
        longitude: Longitude (-180 to 180).
        days: Number of forecast days (1-16, default 7).
        npub: Required. Your Nostr public key (npub1...) for credit billing.
        dpop_token: A kind-27235 Nostr event signed by npub for this tool.
    """
    return await weather.get_forecast(latitude, longitude, days)


@tool
@runtime.paid_tool(capability_uuid("get_historical_weather"))
async def historical(latitude: float, longitude: float, start_date: str, end_date: str,
                     npub: str = "", dpop_token: str = "") -> dict:
    """Get historical weather data for a location and date range.

    Returns daily temperature and precipitation from the Open-Meteo archive.

    Args:
        latitude: Latitude (-90 to 90).
        longitude: Longitude (-180 to 180).
        start_date: Start date (YYYY-MM-DD).
        end_date: End date (YYYY-MM-DD).
        npub: Required. Your Nostr public key (npub1...) for credit billing.
        dpop_token: A kind-27235 Nostr event signed by npub for this tool.
    """
    return await weather.get_historical(latitude, longitude, start_date, end_date)


class Tools(exports.Tools):
    def list_tools(self, ctx, request) -> mcp_types.ListToolsResult:
        tools = []
        for name, fn in sorted(_mcp.registry.items()):
            doc = inspect.getdoc(fn) or ""
            summary = doc.split("\n\n", 1)[0] if doc else None
            tools.append(mcp_types.Tool(
                name=name,
                input_schema=json.dumps(tool_schema(fn)),
                options=mcp_types.ToolOptions(
                    meta=None, annotations=None, description=summary,
                    output_schema=None, icons=None, title=None,
                ) if summary else None,
            ))
        return mcp_types.ListToolsResult(tools=tools, meta=None, next_cursor=None)

    def call_tool(self, ctx, request) -> Optional[mcp_types.CallToolResult]:
        fn = _mcp.registry.get(request.name)
        if fn is None:
            return None
        return _text(
            f"'{request.name}' resolved from operator code. Execution over "
            "wasi:http (backend + credit gate) is the next assembly step.",
            is_error=True,
        )


def _text(msg: str, is_error=None) -> mcp_types.CallToolResult:
    return mcp_types.CallToolResult(
        content=[mcp_types.ContentBlock_Text(mcp_types.TextContent(
            text=mcp_types.TextData_Text(msg), options=None))],
        is_error=is_error, meta=None, structured_content=None,
    )


Tools = Tools
