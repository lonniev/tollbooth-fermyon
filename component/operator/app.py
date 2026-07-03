"""tollbooth-fermyon operator — a DPYC weather Operator on Spin/WASI.

Business logic only. The Spin/WASI host is entirely `tollbooth-wasmcp`
(`SpinOperatorHost`) — the peer of FastMCP on the Horizon side — so this file is
structurally identical to the FastMCP `tollbooth-sample` server. `fermyon`-namespaced
distinct peer of `tollbooth-sample` (slug `weather`), so a client (e.g. Pricing
Studio) can hold both at once.

Rule: `import tollbooth_wasmcp` FIRST — it installs the pre-init seams (httpx→wasi:http,
dpyc:crypto + nsec-only bootstrap, schema+coercion, snapshot fixes) before the wheel.
"""

import tollbooth_wasmcp  # noqa: F401 — installs the pre-init seams (must precede the wheel)
from tollbooth_wasmcp import SpinOperatorHost

from tollbooth.tool_identity import ToolIdentity, capability_uuid
from tollbooth.credential_templates import CredentialTemplate, FieldSpec
from tollbooth.credential_validators import validate_btcpay_creds

import weather

GET_CURRENT = "b7327eb8-92b4-5252-84e0-ba3f437a16ed"
GET_FORECAST = "b6d0e596-3aec-5a62-980b-7875aa04d079"
GET_HISTORICAL = "5608f3e9-44c4-5b28-9744-704af6d701f0"
_DOMAIN = {
    GET_CURRENT: ToolIdentity(tool_id=GET_CURRENT, capability="get_current_weather", category="read", intent="Get current weather conditions"),
    GET_FORECAST: ToolIdentity(tool_id=GET_FORECAST, capability="get_weather_forecast", category="write", intent="Get weather forecast"),
    GET_HISTORICAL: ToolIdentity(tool_id=GET_HISTORICAL, capability="get_historical_weather", category="heavy", intent="Get historical weather data"),
}

# Operator commerce credentials — BTCPay for Lightning payments. Declaring the
# template is what makes onboarding_status report these as required (so Pricing
# Studio renders them) and lets the operator receive them via Secure Courier.
_BTCPAY_TEMPLATE = CredentialTemplate(
    service="fermyon-operator",
    version=2,
    description="Operator credentials for BTCPay Lightning payments",
    fields={
        "btcpay_host": FieldSpec(
            required=True, sensitive=True,
            description="The URL of your BTCPay Server instance (e.g. https://btcpay.example.com).",
        ),
        "btcpay_api_key": FieldSpec(
            required=True, sensitive=True,
            description="Your BTCPay Server API key (Account > Manage Account > API Keys).",
        ),
        "btcpay_store_id": FieldSpec(
            required=True, sensitive=True,
            description="Your BTCPay Store ID (Stores > Settings > General).",
        ),
    },
)

host = SpinOperatorHost(
    service_name="tollbooth-fermyon", slug="fermyon", service_version="0.1.0",
    domain_tools=_DOMAIN,
    operator_credential_template=_BTCPAY_TEMPLATE,
    operator_credential_greeting=(
        "Hi — I'm tollbooth-fermyon, a DPYC weather Operator running on Spin/WASI. "
        "You (or your AI agent) requested a credential channel to deliver my BTCPay secrets."
    ),
    credential_validator=validate_btcpay_creds,
)
tool = host.tool


@tool
@host.runtime.paid_tool(capability_uuid("get_current_weather"))
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
@host.runtime.paid_tool(capability_uuid("get_weather_forecast"))
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
@host.runtime.paid_tool(capability_uuid("get_historical_weather"))
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


Tools = host.tools_export()
