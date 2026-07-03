# operator — the fermyon DPYC weather Operator (Python WASI component)

A self-contained, **execution-capable** MCP served by Spin (and, in production,
Akamai Functions). It presents the same external interface as the reference
[tollbooth-sample](https://github.com/lonniev/tollbooth-sample) — the full DPYC
standard toolset plus three weather tools — but implements everything itself on
WASI, with no FastMCP and no runtime pydantic, reusing the `tollbooth-dpyc` wheel
**untouched**. Its tools are namespaced `fermyon_*` (a distinct peer of the
`weather_*` sample, not a drop-in replacement).

## How it works

The wheel expects native crypto, a filesystem, outbound sockets, and Nostr relay
access — none of which the WASI Python interpreter has. The operator supplies each
as a **seam**, wired at import time before the wheel is used:

- **`app.py`** — the server. A `WasmMcp` shim records what the wheel's
  `register_standard_tools()` registers; the weather tools are decorated methods.
  `list_tools`/`call_tool` are the wasmcp `exports.Tools` surface. `call_tool`
  drives the wheel's async tool bodies on componentize-py's `PollLoop`.
- **`wasi_transport.py`** — an `httpx` transport over `wasi:http`. `httpx.AsyncClient`
  is monkeypatched before the wheel imports, so every call the wheel makes
  (registry, bridge, Neon, Open-Meteo) rides `wasi:http`.
- **`bootstrap_wasm.py`** — replaces the wheel's `ensure_bootstrapped`: fetches the
  operator's encrypted kind-30078 config event through the HTTPS→relay **bridge**
  Worker and decrypts it with the composed crypto component to recover the Neon URL.
  The operator holds only its **nsec**; the Neon URL is never configured.
- **`pynostr/`** — pure-Python bech32 (npub/nsec) + `Event.verify` (identity-proof
  signature check) delegating BIP-340 to the crypto component. **`cryptography/`** —
  an `AESGCM` stub routing the vault cipher to the crypto component.
- **`schema.py`** — self-contained JSON-Schema generation from each tool's signature
  and Google-style docstring. This is why metadata matches FastMCP's quality with no
  coupling — both read the same typed, documented functions.
- **`weather.py`** — the Open-Meteo backend client.

Config (`operator nsec`, `bridge URL`) arrives at run time via `spin up --env` /
Spin variables and is refreshed into `os.environ` each call, because componentize-py
freezes the environment in its pre-init snapshot. The tool list and its metadata are
a **consequence of the code**, never a static blob.

## Build & run

Requires `wac` and `wasmcp` on PATH, plus the crypto component built once
(`cd ../../crypto && cargo component build --release`).

```
make deps      # venv + componentize-py + tollbooth-dpyc (--no-deps) + httpx into deps/
make compose   # componentize -> wac plug crypto component -> wasmcp compose -> server.wasm
```

Run locally (the operator is nsec-only; supply the nsec and bridge URL at run time,
never in the manifest):

```
# start the bridge Worker in ../../bridge:  npx wrangler dev --port 8799 --local
spin up --env TOLLBOOTH_NOSTR_OPERATOR_NSEC=<nsec> --env BRIDGE_URL=http://localhost:8799
```

`spin.toml` grants the operator's `allowed_outbound_hosts` and the KV store the
wasmcp session layer uses. Use `spin up` (the manifest), not `spin up -f server.wasm`
(which ignores it).

## Test

```
pip install tollbooth-dpyc==0.59.0 httpx pytest
pytest tests
```
