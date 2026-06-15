from pathlib import Path


def test_coding_openapi_does_not_expose_operator_tools():
    text = Path("coding-openapi.yaml").read_text(encoding="utf-8")
    forbidden = [
        "runShellCommand",
        "manageFiles",
        "packageManager",
        "appControl",
        "manageGPTs",
        "dispatchToAgent",
        "bulkActions",
        "/shell",
        "/files",
        "/package",
        "/apps",
        "/gpts",
        "/dispatch",
    ]
    for item in forbidden:
        assert item not in text


def test_coding_openapi_is_served(client, auth_headers):
    resp = client.get("/coding-openapi.yaml")
    assert resp.status_code == 200
    assert "Coding Agent API" in resp.text
