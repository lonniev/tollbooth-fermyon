# tollbooth-fermyon

**A WebAssembly edge runtime for a [Tollbooth-DPYC](https://github.com/lonniev/tollbooth-dpyc) Operator** —
the same monetized MCP service the ecosystem runs on FastMCP, recompiled to a
WASI component and served from the global edge (Akamai Functions, formerly
Fermyon Wasm Functions) for near-zero cold starts.

This is a proof of concept: it mirrors the canonical
[tollbooth-sample](https://github.com/lonniev/tollbooth-sample) weather operator,
reusing the `tollbooth-dpyc` wheel **untouched**, and changes only two things —
the server runtime and how it is packaged. Same tools, same pricing, same
Lightning-funded credit gate; a different, faster host.

> **Status:** PoC. The full operator cold-start chain is proven end-to-end
> (relay bootstrap → decrypt → Neon persistence → credit gate), and the Spin/WASI
> host has since been extracted into the reusable
> [`tollbooth-wasmcp`](https://github.com/lonniev/tollbooth-wasmcp) package — so
> this repo is now the operator's business logic only. See
> [`component/operator/README.md`](component/operator/README.md) for the build recipe.

---

## What is DPYC?

**DPYC** stands for **Don't Pester Your Customer** — a philosophy and protocol
for API monetization that eliminates mid-session payment popups, subscription
nag screens, and KYC friction.

- **Pre-funded balances.** Users buy credits with Bitcoin Lightning *before*
  calling tools. Each call silently debits. No interruptions.
- **Nostr keypair identity.** Users are an `npub`, not an email and password.
- **Operator-controlled dynamic pricing.** Prices, discounts, and surge live in
  the operator's own datastore and change without a redeploy — the DPYC
  differentiator.
- **A federation, not a platform.** Independent MCP **Operators** sell tools;
  **Authorities** certify them and collect a small Lightning tax; an **Oracle**
  answers questions about the community. All coordinate over Nostr and a public
  [governance registry](https://github.com/lonniev/dpyc-community).

Learn more: [tollbooth-dpyc](https://github.com/lonniev/tollbooth-dpyc) (the SDK)
· [dpyc-community](https://github.com/lonniev/dpyc-community) (governance) ·
[tollbooth-sample](https://github.com/lonniev/tollbooth-sample) (reference operator).

---

## Why WebAssembly at the edge?

DPYC Operators are stateless request handlers: identity is a Nostr key, money is
a pre-funded Lightning balance, and persistence is a Neon Postgres database
reached over HTTP. That shape maps cleanly onto a WASI component running on a
global edge platform — and trades a container's multi-second cold start for a
sub-second one, which matters for a pay-per-call MCP tool.

The catch is that the interpreter has no native extension modules and no raw
sockets. The [`tollbooth-wasmcp`](https://github.com/lonniev/tollbooth-wasmcp)
host this operator runs on bridges that gap **without forking the SDK** — so this
repo stays business logic only:

| Concern | How the host bridges it |
|---|---|
| Outbound HTTP (Neon, upstream APIs) | `httpx` routed over `wasi:http` via a custom transport — no `ssl` module needed |
| secp256k1 + AES (Nostr proofs, NIP-04, vault) | a tiny native **Rust component** (`dpyc:crypto`) composed alongside the Python one |
| Reading the Authority's bootstrap config off Nostr relays | an HTTPS→relay **bridge Worker**, since relays are WebSocket-only |
| The operator's sole secret | its Nostr `nsec`, injected as one deploy-time variable — everything else is discovered at runtime |

## Repository layout

```
component/operator/   The operator — business logic only:
  app.py                tool identities + SpinOperatorHost bootstrap
  weather.py            the Open-Meteo backend client
  spin.toml             outbound allowlist + session KV
```

Everything else — the WASI HTTP transport, the `dpyc:crypto` Rust component, the
HTTPS→relay bridge Worker, and the nsec-only bootstrap — now lives in
[`tollbooth-wasmcp`](https://github.com/lonniev/tollbooth-wasmcp) and is shared
across all DPYC Spin operators.

## Quick start

```bash
# Requires componentize-py, wac, wasmcp, and spin on PATH; the sibling
# tollbooth-wasmcp checkout supplies the WASI host, dpyc:crypto, and the bridge.
cd component/operator
make deps      # venv + componentize-py + tollbooth-dpyc (--no-deps) + httpx
make compose   # componentize -> wac plug crypto -> wasmcp compose -> server.wasm

# Run locally (nsec-only — supply the nsec + bridge URL at run time):
#   (cd ../../../tollbooth-wasmcp/bridge && npx wrangler dev --port 8799 --local)
spin up --env TOLLBOOTH_NOSTR_OPERATOR_NSEC=<nsec> --env BRIDGE_URL=http://localhost:8799
```

## The Tollbooth-DPYC ecosystem

| Project | Role |
|---|---|
| [tollbooth-dpyc](https://github.com/lonniev/tollbooth-dpyc) | The shared SDK — all crypto, vault, auth, pricing, audit |
| [tollbooth-wasmcp](https://github.com/lonniev/tollbooth-wasmcp) | The Spin/WASI host adapter (`SpinOperatorHost`) — the WASI seams this operator runs on |
| [tollbooth-sample](https://github.com/lonniev/tollbooth-sample) | Reference Operator (this PoC mirrors it) |
| [dpyc-community](https://github.com/lonniev/dpyc-community) | Governance registry — members, rules, taxation |
| **tollbooth-fermyon** | This repo — a Wasm/edge runtime for a DPYC Operator |

## License

Apache License 2.0 — see [LICENSE](LICENSE) and [NOTICE](NOTICE).
