- Secure Courier works in-Wasm (via tollbooth-wasmcp 0.1.3): `request`/`receive_npub_proof`
  and credential channels, validated end-to-end against a live Pricing Studio proof.
- Declared the BTCPay `operator_credential_template` (dropped in the slim refactor),
  so `onboarding_status` reports the commerce credentials, the operator can receive
  them via Secure Courier, and `purchase_credits` mints real Lightning invoices.
- `current` returns labeled Fahrenheit/mph; `forecast` and `historical` request US units.
