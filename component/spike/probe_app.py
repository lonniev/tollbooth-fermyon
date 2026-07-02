"""Risk-A probe: does componentize-py's CPython have ssl, and can httpx import?

Import attempts run at module load (componentize pre-init) time, wrapped so the
build completes regardless; results are read back at runtime via the `probe` tool.
"""

import json
import sys
from typing import Optional
from wit_world import exports
from wit_world.imports import mcp, server_handler

_PROBE = {}

# 1. Is ssl present in the bundled CPython?
try:
    import ssl  # noqa: F401
    _PROBE["ssl"] = f"PRESENT ({getattr(ssl, 'OPENSSL_VERSION', '?')})"
except Exception as e:
    _PROBE["ssl"] = f"ABSENT: {type(e).__name__}: {e}"

# 2. Does httpx import (it does `import ssl` at module top)?
try:
    import httpx  # noqa: F401
    _PROBE["httpx"] = f"IMPORTED {httpx.__version__}"
except Exception as e:
    _PROBE["httpx"] = f"FAILED: {type(e).__name__}: {e}"

# 3. A few stdlib bits the gate touches.
for mod in ("hashlib", "hmac", "base64", "asyncio"):
    try:
        __import__(mod)
        _PROBE[mod] = "ok"
    except Exception as e:
        _PROBE[mod] = f"FAILED: {type(e).__name__}: {e}"

_PROBE["python"] = sys.version

# 4. Can httpx build a CLIENT without ssl? Default client may eagerly build an
#    SSLContext (verify=True); a custom transport should bypass that entirely.
try:
    import httpx as _hx

    class _DummyTransport(_hx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            return _hx.Response(200, content=b"ok")

    try:
        c = _hx.AsyncClient(transport=_DummyTransport())
        _PROBE["AsyncClient(custom_transport)"] = "CONSTRUCTED"
    except Exception as e:
        _PROBE["AsyncClient(custom_transport)"] = f"FAILED: {type(e).__name__}: {e}"

    try:
        c2 = _hx.AsyncClient()
        _PROBE["AsyncClient(default)"] = "CONSTRUCTED"
    except Exception as e:
        _PROBE["AsyncClient(default)"] = f"FAILED: {type(e).__name__}: {e}"
except Exception as e:
    _PROBE["client_tests"] = f"httpx missing: {e}"

# 5. Does creating an SSLContext fail (what an ssl stub would need to cover)?
try:
    import ssl as _ssl
    _ssl.create_default_context()
    _PROBE["ssl.create_default_context"] = "ok"
except Exception as e:
    _PROBE["ssl.create_default_context"] = f"FAILED: {type(e).__name__}: {e}"


class ProbeTools(exports.Tools):
    def list_tools(self, ctx, request):
        return mcp.ListToolsResult(
            tools=[mcp.Tool(
                name="probe",
                input_schema=json.dumps({"type": "object", "properties": {}}),
                options=None,
            )],
            meta=None,
            next_cursor=None,
        )

    def call_tool(self, ctx, request) -> Optional[mcp.CallToolResult]:
        if request.name != "probe":
            return None
        return _result(json.dumps(_PROBE, indent=2))


def _result(text: str) -> mcp.CallToolResult:
    return mcp.CallToolResult(
        content=[mcp.ContentBlock_Text(mcp.TextContent(
            text=mcp.TextData_Text(text), options=None))],
        is_error=None, meta=None, structured_content=None,
    )


Tools = ProbeTools
