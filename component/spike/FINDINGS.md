# Step-0 spike findings (2026-07-03, Opus session)

Toolchain (all installed, native arm64):
- spin 4.0.2 (brew spinframework/tap) + aka 0.7.3 plugin
- componentize-py 0.24.0 (bundles **CPython 3.14.0**, not 3.12)
- wasmcp 0.4.13 (~/.cargo/bin, not on PATH)

Proven end-to-end: `wasmcp new --language python` → `componentize-py componentize`
→ `wasmcp compose server` → `spin up -f server.wasm` → MCP tools/list + tools/call
over HTTP (streamable, SSE-framed `data:` responses). Base component 18.5 MB;
with httpx 24.5 MB; composed server 29.9 MB — all well under the 50 MiB Akamai ceiling.

Risk A (ssl / httpx) — RESOLVED by runtime probe on spin:
- ssl: ABSENT (`No module named '_ssl'`).
- httpx 0.28.1: IMPORTS anyway (no import-time ssl stub needed).
- httpx.AsyncClient(transport=<custom>): CONSTRUCTS.
- httpx.AsyncClient()  [default transport]: FAILS (No _ssl).
- ssl.create_default_context(): FAILS.
=> Conclusion: DROP the ssl stub. Monkeypatching httpx.AsyncClient to always
   inject WasiHttpTransport (already planned, before importing tollbooth) both
   routes over wasi:http AND avoids ssl entirely. One fewer shim.

Remaining crypto-free step (next): outbound over wasi:http.
- poll_loop.py (componentize-py bundled/, saved here) provides PollLoop + send()
  over wasi:http@0.2.x, but imports wit_world.imports.{types,streams,poll,outgoing_handler}.
- The wasmcp tools world does NOT import wasi:http; generated wit_world.imports.types
  is MCP types (name collision). Must: add wasi:http@0.2.x WIT to deps, extend the
  world to import outgoing-handler, regenerate bindings, adapt poll_loop import paths,
  write WasiHttpTransport(send), rebuild, ensure Spin allowed_outbound_hosts, GET test.
- Risks to watch: world-merge with wasmcp compose; Spin outbound gating.

hashlib/hmac/base64/asyncio all present (gate hot-path stdlib OK).

## UPDATE — wasi:http transport PROVEN end-to-end (2026-07-03)

Risk A fully defeated. Built a minimal componentize-py component targeting the
`wasi:http/proxy@0.2.8` world (WIT fetched with `wkg wit fetch`), wired httpx to
`WasiHttpTransport` (component/wasi_transport.py) over componentize-py's poll_loop,
ran on `spin up`, and confirmed:
- GET https://api.open-meteo.com/... -> 200 with real JSON (TLS by host, no ssl module).
- POST https://postman-echo.com/post with JSON body -> 200, body echoed back INTACT.

Covers both operator code paths: weather tools (GET) and NeonVault (POST).

Key implementation notes for the real component:
- Import httpx + wasi_transport at MODULE TOP LEVEL (componentize-py only bundles
  modules imported at pre-init; a deferred `import httpx` -> ModuleNotFoundError at runtime).
- Filter wasi:http-forbidden headers before Fields.from_list (host, content-length,
  connection, keep-alive, transfer-encoding, upgrade, proxy-connection, te, trailer)
  or Fields raises HeaderError_Forbidden. host -> set_authority; content-length -> body.
- wkg 0.15.1 `wkg wit fetch` on a world that `include`s wasi:http/proxy@0.2.8 pulls the
  whole dep tree (http/clocks/io/cli/random) cleanly. In that clean proxy world,
  wit_world.imports.{types,outgoing_handler,streams,poll} match poll_loop.py's imports
  as-is (no name collision — the collision only appears when merging with the wasmcp
  tools world, which is the next integration step).
- Proven world: component/spike/http_probe/ (app.py, wit/world.wit, spin.toml).
- Reusable core saved: component/wasi_transport.py, component/poll_loop.py.

## Next integration step (the hard merge)
Combine the wasmcp tools world (exports mcp tools) WITH wasi:http outgoing-handler
import in ONE component world, resolving the `types` module name collision (wasmcp
auth/jwt `types` vs wasi:http `types`). Then monkeypatch httpx.AsyncClient to inject
WasiHttpTransport before importing tollbooth. Then Rust crypto component for decrypt.

## Deployment URL decision (user, 2026-07-03)
Public operator MCP URL: https://fermyon.tollbooth-dpyc.com/mcp — a custom subdomain
of the user's tollbooth-dpyc.com, to be pointed at the Akamai app's <app-id>.fwf.app
origin via Akamai Property Manager once the user has an Akamai workspace. Configure the
Spin HTTP route so MCP is served at /mcp. Akamai default URL is https://<generated-uuid>.fwf.app
(stable across redeploys, single global anycast endpoint, 30s request cap). Adoption records
URL metadata only — the MCP need NOT be operational at adoption time (user confirmed).
