- `allowed_outbound_hosts` opened to all HTTPS — the operator's endpoints (BTCPay
  host, upstream APIs) arrive at runtime from the vault and can't be pre-enumerated
  at build time.
- Ledger debits persist per request (via tollbooth-wasmcp 0.1.5): a stateless Spin
  instance was discarding in-memory debits, so paid tools had been running for free.
