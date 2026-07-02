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
> (relay bootstrap → decrypt → Neon persistence → credit gate). Final assembly
> into a single deployed component is in progress. See
> [`component/spike/FINDINGS.md`](component/spike/FINDINGS.md).

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
sockets. This repo shows how to bridge that gap **without forking the SDK**:

| Concern | How it works here |
|---|---|
| Outbound HTTP (Neon, upstream APIs) | `httpx` routed over `wasi:http` via a custom transport — no `ssl` module needed |
| secp256k1 + AES (Nostr proofs, NIP-04, vault) | a tiny native **Rust component** (`crypto/`) composed alongside the Python one |
| Reading the Authority's bootstrap config off Nostr relays | an HTTPS→relay **bridge Worker** (`bridge/`), since relays are WebSocket-only |
| The operator's sole secret | its Nostr `nsec`, injected as one deploy-time variable — everything else is discovered at runtime |

## Repository layout

```
component/   Python WASI component (componentize-py): the MCP tools + the credit gate
crypto/      Rust component (cargo-component): secp256k1 + AES primitives, exported over WIT
bridge/      Cloudflare Worker: HTTPS → Nostr relay fetch for cold-start bootstrap
wit/         Shared WIT interfaces
```

## Quick start

```bash
# Rust crypto component — validated byte-for-byte against the tollbooth-dpyc wheel
cd crypto && cargo test && cargo component build --release

# Bridge Worker — HTTPS → Nostr relay fetch
cd bridge && npm install && npm run dev

# Python component — see component/spike/FINDINGS.md for the current build recipe
```

## The Tollbooth-DPYC ecosystem

| Project | Role |
|---|---|
| [tollbooth-dpyc](https://github.com/lonniev/tollbooth-dpyc) | The shared SDK — all crypto, vault, auth, pricing, audit |
| [tollbooth-sample](https://github.com/lonniev/tollbooth-sample) | Reference Operator (this PoC mirrors it) |
| [dpyc-community](https://github.com/lonniev/dpyc-community) | Governance registry — members, rules, taxation |
| **tollbooth-fermyon** | This repo — a Wasm/edge runtime for a DPYC Operator |

## License

Apache License 2.0 — see [LICENSE](LICENSE) and [NOTICE](NOTICE).
