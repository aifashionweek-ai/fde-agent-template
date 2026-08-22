"""D-039 guard: the local chat UI is served by the existing FastAPI app and is governance-VISIBLE:
it renders the pending proposal (tool + args + proposal_hashes) and its approve call echoes the hashes
the human SAW (the D-038 binding), plus the trace path. The deep invariants are server-side (D-038);
this guards the surface: page served, and the client wires the binding rather than a bare approve:true."""
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)


def test_chat_page_served_at_root():
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "/run" in r.text and "/approve" in r.text     # drives the EXISTING endpoints, no new surface


def test_chat_page_wires_the_approval_binding():
    html = client.get("/").text
    # The UI must display the binding artifact and echo it on approve — not send a bare approve:true.
    assert "proposal_hashes" in html                     # renders what the human is approving
    assert "hashes:" in html                             # /approve body carries the SEEN hashes (D-038)
    assert "pending_tool_calls" in html                  # shows the exact proposed action
    assert "path" in html                                # trace path visible — governance on screen


def test_chat_page_never_blind_parses_responses():
    """D-041: a non-JSON or non-2xx response must land in the error card, never a SyntaxError.
    Source-level guard: the client reads text and parses defensively — a bare `await r.json()`
    (blind parse) is banned."""
    html = client.get("/").text
    assert "await r.json()" not in html                  # blind parse would throw on a plain-text 500
    assert "JSON.parse(text)" in html                    # defensive parse of the text body
    assert "r.ok" in html                                # status checked before treating it as a result
