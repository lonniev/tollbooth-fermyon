.PHONY: all deps build compose run clean

VENV       := .venv
PY         := $(VENV)/bin/python
CPY        := $(VENV)/bin/componentize-py
COMPONENT  := operator
CRYPTO_WASM := ../../crypto/target/wasm32-wasip1/release/dpyc_crypto.wasm

all: build

# Build tool + bundled deps. tollbooth-dpyc goes in --no-deps (its native crypto
# libs are lazy and must not be bundled); only httpx (+ its pure deps) is added.
deps:
	uv venv --python 3.12 $(VENV)
	uv pip install --python $(PY) "componentize-py==0.24.*"
	rm -rf deps
	uv pip install --target deps --no-deps "tollbooth-dpyc==0.59.1"
	uv pip install --target deps "httpx==0.28.1"

# Compile the Python component (schemas generated in-Wasm; no pydantic).
# `componentize` generates the wit_world bindings internally for app.py's pre-init
# imports; we do NOT run `bindings .` separately because that regenerates
# poll_loop.py with the template's `types` name, clobbering the committed
# poll_loop.py / wasi_transport.py that reference the merged world's
# `wasi_http_types` binding.
build:
	$(CPY) --wit-path wit --world $(COMPONENT) componentize app -p . -p deps -o $(COMPONENT).wasm

# Plug the native crypto component in, then wrap with wasmcp transport/middleware.
# Requires `wac` and `wasmcp` on PATH (see repo README).
compose: build
	wac plug $(COMPONENT).wasm --plug $(CRYPTO_WASM) -o plugged.wasm
	wasmcp compose server plugged.wasm -o server.wasm --force

run: compose
	spin up -f server.wasm

clean:
	rm -rf $(VENV) deps wit_world __pycache__ $(COMPONENT).wasm plugged.wasm server.wasm
