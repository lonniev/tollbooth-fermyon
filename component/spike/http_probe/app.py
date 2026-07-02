"""Prove httpx-over-wasi:http: on any inbound request, fetch a real HTTPS URL
via httpx + WasiHttpTransport and return the result. This is the decisive
Risk-A end-to-end test (no ssl module involved)."""

import asyncio
import json
import traceback

import httpx
import poll_loop
from poll_loop import PollLoop, Sink
from wasi_transport import WasiHttpTransport
from componentize_py_types import Ok
from wit_world import exports
from wit_world.imports.types import (
    IncomingRequest, ResponseOutparam, OutgoingResponse, Fields, OutgoingBody,
)

TEST_URL = "https://api.open-meteo.com/v1/forecast?latitude=40.71&longitude=-74.01&current=temperature_2m"


class IncomingHandler(exports.IncomingHandler):
    def handle(self, request: IncomingRequest, response_out: ResponseOutparam) -> None:
        loop = PollLoop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_run(response_out))


async def _run(response_out: ResponseOutparam) -> None:
    try:
        async with httpx.AsyncClient(transport=WasiHttpTransport()) as client:
            r = await client.get(TEST_URL)
            # POST with a JSON body (the NeonVault code path) — echo service
            # reflects the body so we confirm it was transmitted intact.
            pr = await client.post(
                "https://postman-echo.com/post",
                json={"probe": "neonvault-post", "n": 42},
            )
        echoed = pr.json().get("data") if pr.status_code == 200 else None
        payload = json.dumps({
            "ok": True,
            "GET": {"status": r.status_code, "body_head": r.text[:160]},
            "POST": {"status": pr.status_code, "echoed_body": echoed},
        }).encode()
    except Exception as e:
        payload = json.dumps({
            "ok": False,
            "error": f"{type(e).__name__}: {e}",
            "trace": traceback.format_exc()[-800:],
        }).encode()

    response = OutgoingResponse(Fields.from_list([("content-type", b"application/json")]))
    body = response.body()
    ResponseOutparam.set(response_out, Ok(response))
    sink = Sink(body)
    await sink.send(payload)
    sink.close()


IncomingHandler = IncomingHandler
