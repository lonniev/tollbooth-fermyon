.PHONY: all deps build compose run clean

VENV       := .venv
PY         := $(VENV)/bin/python
CPY        := $(VENV)/bin/componentize-py
COMPONENT  := operator
# The tollbooth-wasmcp host adapter. In-repo we reference the sibling checkout;
# an out-of-repo operator instead installs it (pip install tollbooth-wasmcp) and
# points these at $(python -m tollbooth_wasmcp.paths …).
ADAPTER    := ../../../tollbooth-wasmcp
TOPLEVEL   := $(ADAPTER)/tollbooth_wasmcp/_toplevel
WIT        := $(ADAPTER)/tollbooth_wasmcp/wit
CRYPTO     := $(ADAPTER)/tollbooth_wasmcp/crypto.wasm

all: compose

# Build tool + bundled deps (tollbooth-dpyc --no-deps; httpx pure).
deps:
	rm -rf $(VENV) deps
	uv venv --python 3.12 $(VENV)
	uv pip install --python $(PY) "componentize-py==0.24.*"
	rm -rf deps
	uv pip install --target deps --no-deps "tollbooth-dpyc==0.59.1"
	uv pip install --target deps "httpx==0.28.1"

# Compile the component. The adapter package + its top-level shims join the module
# path; the standardized WIT world + crypto component come from the adapter.
# NOTE: never run `componentize-py bindings` — it clobbers the adapter's poll_loop.py.
build:
	$(CPY) --wit-path $(WIT) --world $(COMPONENT) componentize app \
	  -p . -p deps -p $(ADAPTER) -p $(TOPLEVEL) -o $(COMPONENT).wasm

compose: build
	wac plug $(COMPONENT).wasm --plug $(CRYPTO) -o plugged.wasm
	wasmcp compose server plugged.wasm -o server.wasm --force

# Run locally (nsec-only — supply nsec + bridge URL at run time). Start the bridge
# from the adapter: (cd $(ADAPTER)/bridge && npx wrangler dev --port 8799 --local)
run: compose
	spin up

clean:
	rm -rf $(VENV) deps wit_world __pycache__ componentize_py_runtime.pyi $(COMPONENT).wasm plugged.wasm server.wasm
