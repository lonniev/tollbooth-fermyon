"""tollbooth-fermyon operator — a DPYC weather Operator as a Spin WASI component.

A self-contained MCP served by Spin (and, in production, Akamai Functions). It
presents the same external interface as the reference tollbooth-sample — the full
DPYC standard toolset plus three weather tools — but implements everything itself
on WASI, with no FastMCP and no runtime pydantic. It reuses the tollbooth-dpyc
wheel UNTOUCHED, satisfying the wheel's native/OS seams from the WASI world:

  - httpx is routed over wasi:http (registry, bridge, Neon, Open-Meteo);
  - crypto (NIP-04 decrypt for bootstrap, vault AES-GCM, schnorr proof verify)
    is delegated to the composed dpyc:crypto Rust component;
  - the operator nsec + bridge URL arrive via `spin up --env` / Spin variables
    (os.environ is frozen in the pre-init snapshot, so it is refreshed at call
    time from the live WASI environment);
  - the Nostr relay round-trips the wheel would make are served by an owned
    HTTPS→relay bridge Worker (WASI has no outbound websockets).

The tool list and its metadata are a consequence of the code (the wheel's
registrations + these decorated methods + docstring-derived schemas), never a
static blob.
"""

import asyncio
import inspect
import json
import traceback
import typing
from typing import Optional

# 1) Route every httpx.AsyncClient over wasi:http BEFORE importing the wheel.
import httpx
from wasi_transport import WasiHttpTransport

_OrigAsyncClient = httpx.AsyncClient


class _WasiAsyncClient(_OrigAsyncClient):
    def __init__(self, *a, **k):
        k.setdefault("transport", WasiHttpTransport())
        super().__init__(*a, **k)


httpx.AsyncClient = _WasiAsyncClient

from wit_world import exports  # noqa: E402
from wit_world.imports import mcp as mcp_types  # noqa: E402
from wit_world.imports import ops  # noqa: E402,F401  (bundle the crypto binding at pre-init)
from poll_loop import PollLoop  # noqa: E402

from tollbooth.tool_identity import ToolIdentity, STANDARD_IDENTITIES, capability_uuid  # noqa: E402
from tollbooth.runtime import OperatorRuntime, register_standard_tools  # noqa: E402

# Route the wheel's crypto + bootstrap to the composed dpyc:crypto component and
# the bridge Worker (the WASI interpreter has neither native crypto nor websockets).
import cryptography.hazmat.primitives.ciphers.aead  # noqa: E402,F401  (AESGCM stub -> ops; bundle it)
import tollbooth.bootstrap  # noqa: E402
import bootstrap_wasm  # noqa: E402
tollbooth.bootstrap.ensure_bootstrapped = bootstrap_wasm.wasm_ensure_bootstrapped

# Force-bundle every importable wheel submodule at pre-init — componentize-py only
# bundles modules imported before the snapshot, but the wheel imports tools/*,
# pricing, etc. lazily at call time. Natives (coincurve) fail and are skipped.
import tollbooth as _tb  # noqa: E402
import importlib as _il  # noqa: E402
import pkgutil as _pk  # noqa: E402


def _force_bundle():
    for _m in _pk.walk_packages(_tb.__path__, _tb.__name__ + "."):
        try:
            _il.import_module(_m.name)
        except Exception:
            pass


_force_bundle()

# service_status reads the wheel version via importlib.metadata, which scans the
# filesystem for .dist-info — impossible in componentize-py's frozen runtime
# snapshot, so it returns "unknown". Resolve it now (pre-init, dist-info still on
# the build path) and pin it into a shim that answers at runtime.
import os as _os  # noqa: E402
import importlib.metadata as _ilm  # noqa: E402


def _resolve_wheel_version():
    try:
        return _ilm.version("tollbooth-dpyc")
    except Exception:
        import glob
        import sys as _sys
        for _d in _sys.path:
            for _p in glob.glob(_os.path.join(_d, "tollbooth_dpyc-*.dist-info")):
                base = _os.path.basename(_p)
                return base[len("tollbooth_dpyc-"):-len(".dist-info")]
    return "unknown"


_WHEEL_VERSION = _resolve_wheel_version()
_orig_ilm_version = _ilm.version
_ilm.version = lambda name: _WHEEL_VERSION if name == "tollbooth-dpyc" else _orig_ilm_version(name)

# Opt-in proof-rejection diagnostic (env PROOF_DEBUG). When a proof is rejected,
# enrich the error with WHICH sub-check failed (u-tag binding, pubkey, signature,
# timestamp) — invaluable for debugging a client's proof binding. OFF by default:
# leaking which check failed would help an attacker refine an invalid proof.
import tollbooth.runtime as _rt_mod  # noqa: E402
import tollbooth.identity_proof as _idp  # noqa: E402
_orig_require_proof = _rt_mod.require_proof


async def _require_proof_maybe_diag(npub, dpop_token, tool_name, *, proven_cache=None, window_seconds=_idp.DEFAULT_WINDOW_SECONDS):
    err = await _orig_require_proof(npub, dpop_token, tool_name, proven_cache=proven_cache, window_seconds=window_seconds)
    if isinstance(err, dict) and err.get("error_code") == "proof_invalid" and _os.environ.get("PROOF_DEBUG"):
        d = {"expected_tool_name": tool_name}
        try:
            import hashlib as _h
            import time as _t
            ev = json.loads(dpop_token)
            if not isinstance(ev, dict):
                d["dpop_token_form"] = "JSON but not an event object"
            else:
                d["u_tags"] = [t[1] for t in ev.get("tags", []) if len(t) >= 2 and t[0] == "u"]
                d["event_kind"] = ev.get("kind")
                d["age_seconds"] = round(_t.time() - (ev.get("created_at") or 0), 1)
                try:
                    d["pubkey_matches_operator"] = ev.get("pubkey") == _idp._npub_to_hex(npub)
                except Exception as e:
                    d["pubkey_check_error"] = str(e)
                ser = json.dumps([0, ev.get("pubkey"), ev.get("created_at"), ev.get("kind"), ev.get("tags"), ev.get("content")], separators=(",", ":"), ensure_ascii=False)
                rid = _h.sha256(ser.encode()).hexdigest()
                d["id_recomputes"] = ev.get("id") == rid
                try:
                    d["sig_verifies"] = ops.schnorr_verify(bytes.fromhex(rid), bytes.fromhex(ev.get("sig", "")), bytes.fromhex(ev.get("pubkey", "")))
                except Exception as e:
                    d["sig_error"] = str(e)
        except Exception:
            d["dpop_token_form"] = "not JSON (cache-key shape?): " + repr(str(dpop_token)[:40])
        err["_diagnostic"] = d
    return err


_rt_mod.require_proof = _require_proof_maybe_diag

import weather  # noqa: E402
import pynostr.key  # noqa: E402,F401  (bundle the pure-Python bech32 shim)
import pynostr.event  # noqa: E402,F401  (Event.verify via ops.schnorr_verify)
from wit_world.imports import environment as _wasi_environment  # noqa: E402
from wit_world.imports import store as _spin_config  # noqa: E402  (wasi:config/store = Spin variables)
from schema import tool_schema  # noqa: E402


_CONFIG_TO_ENV = {"operator_nsec": "TOLLBOOTH_NOSTR_OPERATOR_NSEC", "bridge_url": "BRIDGE_URL"}


def _sync_os_environ():
    """componentize-py freezes os.environ in the pre-init snapshot. Refresh it at
    call time from the live WASI environment (`spin up --env`) and Spin variables
    (wasi:config/store) — the channels that cross the wasmcp composition boundary."""
    import os
    for cfg_key, env_key in _CONFIG_TO_ENV.items():
        try:
            val = _spin_config.get(cfg_key)
            if val:
                os.environ[env_key] = val
        except Exception:
            pass
    try:
        for k, v in _wasi_environment.get_environment():
            os.environ[k] = v
    except Exception:
        pass


class WasmMcp:
    """Minimal stand-in for the FastMCP registration surface. Records every
    `mcp.tool(name=...)` the wheel's register_standard_tools performs, so the tool
    list is derived from real registrations rather than a hand-maintained blob."""

    def __init__(self, name=""):
        self.name = name
        self.registry = {}

    def tool(self, name=None, **_kw):
        def deco(fn):
            self.registry[name or fn.__name__] = fn
            return fn
        return deco


GET_CURRENT = "b7327eb8-92b4-5252-84e0-ba3f437a16ed"
GET_FORECAST = "b6d0e596-3aec-5a62-980b-7875aa04d079"
GET_HISTORICAL = "5608f3e9-44c4-5b28-9744-704af6d701f0"
_DOMAIN = {
    GET_CURRENT: ToolIdentity(tool_id=GET_CURRENT, capability="get_current_weather", category="read", intent="Get current weather conditions"),
    GET_FORECAST: ToolIdentity(tool_id=GET_FORECAST, capability="get_weather_forecast", category="write", intent="Get weather forecast"),
    GET_HISTORICAL: ToolIdentity(tool_id=GET_HISTORICAL, capability="get_historical_weather", category="heavy", intent="Get historical weather data"),
}

runtime = OperatorRuntime(tool_registry={**STANDARD_IDENTITIES, **_DOMAIN}, service_name="tollbooth-fermyon")
_mcp = WasmMcp("tollbooth-fermyon")
# Own namespace — a distinct peer of tollbooth-sample (slug "weather"), not a
# replacement. Its tools are fermyon_* so a client (e.g. Pricing Studio) can hold
# both operators at once without a tool-name collision.
tool = register_standard_tools(_mcp, "fermyon", runtime, service_name="tollbooth-fermyon", service_version="0.1.0")


@tool
@runtime.paid_tool(capability_uuid("get_current_weather"))
async def current(latitude: float, longitude: float, npub: str = "", dpop_token: str = "") -> dict:
    """Get current weather conditions for a location.

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
async def historical(latitude: float, longitude: float, start_date: str, end_date: str, npub: str = "", dpop_token: str = "") -> dict:
    """Get historical weather data for a location and date range.

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
    def list_tools(self, ctx, request):
        tools = []
        for name, fn in sorted(_mcp.registry.items()):
            doc = inspect.getdoc(fn) or ""
            summary = doc.split("\n\n", 1)[0] if doc else None
            tools.append(mcp_types.Tool(
                name=name, input_schema=json.dumps(tool_schema(fn)),
                options=mcp_types.ToolOptions(meta=None, annotations=None, description=summary, output_schema=None, icons=None, title=None) if summary else None,
            ))
        return mcp_types.ListToolsResult(tools=tools, meta=None, next_cursor=None)

    def call_tool(self, ctx, request) -> Optional[mcp_types.CallToolResult]:
        _sync_os_environ()
        fn = _mcp.registry.get(request.name)
        if fn is None:
            return None
        try:
            args = json.loads(request.arguments) if request.arguments else {}
        except Exception as e:
            return _text(f"invalid arguments: {e}", True)
        # Bind to the tool's declared params: drop unknown fields and coerce JSON
        # scalars to their annotated types (what FastMCP's pydantic layer does).
        args = _bind_args(fn, args)
        loop = PollLoop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(fn(**args))
        except Exception as e:
            return _text(json.dumps({"success": False, "error": f"{type(e).__name__}: {e}", "trace": traceback.format_exc()[-500:]}), True)
        out = result if isinstance(result, str) else json.dumps(result)
        is_err = isinstance(result, dict) and result.get("success") is False
        return _text(out, is_err)


def _base_scalar(ann):
    """Unwrap Annotated[T, ...] and Optional[T]/Union to the base scalar type
    (same traversal as schema.py's _json_type)."""
    origin = typing.get_origin(ann)
    if origin is typing.Annotated:
        return _base_scalar(typing.get_args(ann)[0])
    if origin is typing.Union:
        for a in typing.get_args(ann):
            if a is not type(None):
                return _base_scalar(a)
    return ann


def _bind_args(fn, args):
    """Filter to the tool's declared params and coerce JSON scalars to their
    annotated types. FastMCP does this via pydantic; the raw wasmcp transport
    hands us the JSON as-is, so `days="30"` reaches an `int` param and blows up
    (e.g. timedelta(days="30")). Mirror pydantic's lenient scalar coercion."""
    # Resolve PEP 563 string annotations (the wheel uses future annotations, so
    # p.annotation is e.g. "int" rather than the int type).
    try:
        hints = typing.get_type_hints(fn, include_extras=True)
    except Exception:
        hints = {}
    out = {}
    for name, p in inspect.signature(fn).parameters.items():
        if name not in args:
            continue
        v = args[name]
        t = _base_scalar(hints.get(name, p.annotation))
        try:
            if t is bool and isinstance(v, str):
                v = v.strip().lower() in ("true", "1", "yes", "on")
            elif t is int and isinstance(v, str) and v.strip():
                v = int(v)
            elif t is float and isinstance(v, (str, int)):
                v = float(v)
        except (ValueError, TypeError):
            pass  # leave as-is; the tool's own validation will speak
        out[name] = v
    return out


def _text(msg, is_error=None):
    return mcp_types.CallToolResult(
        content=[mcp_types.ContentBlock_Text(mcp_types.TextContent(text=mcp_types.TextData_Text(msg), options=None))],
        is_error=is_error, meta=None, structured_content=None,
    )


Tools = Tools
