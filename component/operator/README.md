# operator — the fermyon DPYC weather Operator (Python WASI component)

A self-contained MCP served by Spin. It presents the same external interface as
the reference [tollbooth-sample](https://github.com/lonniev/tollbooth-sample) —
the full DPYC standard toolset plus three weather tools — but implements
everything itself, the conventional way, with no FastMCP and no runtime pydantic.

## How it works

- `app.py` — the server. A `WasmMcp` shim records what the wheel's
  `register_standard_tools()` registers; the three weather tools are decorated
  methods backed by the Open-Meteo REST API. `list_tools`/`call_tool` are the
  wasmcp `exports.Tools` surface.
- `schema.py` — self-contained JSON Schema generation. Derives each tool's
  `inputSchema` from its signature and Google-style docstring (types, titles,
  descriptions, required, defaults). This is why the metadata matches FastMCP's
  quality without any coupling — both read the same typed, documented functions.
- `weather.py` — the Open-Meteo backend client.

The tool list is a consequence of the code, not a static blob.

## Build & run

```
make deps      # componentize-py + bundle tollbooth-dpyc (--no-deps) + httpx
make build     # componentize -> operator.wasm
make compose   # wac plug crypto component + wasmcp compose -> server.wasm
make run       # spin up -f server.wasm   (local; also the Akamai Functions runtime)
```

## Test

```
pip install tollbooth-dpyc==0.59.0 httpx pytest
pytest tests
```
