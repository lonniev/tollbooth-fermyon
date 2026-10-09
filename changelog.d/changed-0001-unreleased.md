- Bumped the `tollbooth-dpyc` wheel pin `0.62.0 → 0.62.1` (security-hardening
  batch): invoice-owner check on credit settlement, GCM credential vault,
  encrypted self-provisioning ledger, and no plaintext audit.

- The Spin/WASI host was extracted into the reusable **tollbooth-wasmcp** package
  (the peer of FastMCP) and this operator now depends on it (`==0.1.5`). `app.py`
  went 338 → ~120 lines and is business logic only; the vendored `crypto/`,
  `bridge/`, and host scaffolding described under [0.1.0] moved to tollbooth-wasmcp.
