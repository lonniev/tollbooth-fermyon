# operator — the fermyon DPYC weather Operator

Business logic only. The Spin/WASI host is [`tollbooth-wasmcp`](https://github.com/lonniev/tollbooth-wasmcp)
(`SpinOperatorHost`) — the peer of FastMCP on the Horizon side — so this operator is
just the domain tool identities + three weather methods + the host bootstrap, the
same shape as the FastMCP [tollbooth-sample](https://github.com/lonniev/tollbooth-sample).
Its tools are `fermyon_*`, a distinct peer of the sample's `weather_*`.

## Files

- `app.py` — the operator: `import tollbooth_wasmcp` (installs the pre-init seams),
  construct `SpinOperatorHost(service_name, slug="fermyon", domain_tools=…)`, decorate
  the three weather tools, `Tools = host.tools_export()`.
- `weather.py` — the Open-Meteo backend client.
- `spin.toml` — the operator's `allowed_outbound_hosts` (incl. open-meteo) + session KV.

Everything else — the schema generator, arg coercion, the WASI transport, the
nsec-only bootstrap, the `dpyc:crypto` component, and the HTTPS→relay bridge — lives
in `tollbooth-wasmcp` and is shared across all DPYC Spin operators.

## Build & run

Requires `componentize-py`, `wac`, `wasmcp`, `spin` on PATH. In-repo builds reference
the sibling `tollbooth-wasmcp` checkout (see the Makefile); an out-of-repo operator
instead `pip install tollbooth-wasmcp` and points the Makefile at
`python -m tollbooth_wasmcp.paths {toplevel,wit,crypto}`.

```
make deps      # venv + componentize-py + tollbooth-dpyc (--no-deps) + httpx
make compose   # componentize (via adapter) -> wac plug crypto -> wasmcp compose -> server.wasm
```

Run locally (nsec-only — supply the nsec + bridge URL at run time, never in the manifest):

```
# start the bridge:  (cd ../../../tollbooth-wasmcp/bridge && npx wrangler dev --port 8799 --local)
spin up --env TOLLBOOTH_NOSTR_OPERATOR_NSEC=<nsec> --env BRIDGE_URL=http://localhost:8799
```
