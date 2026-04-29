import pytest


@pytest.fixture(autouse=True)
def isolate_hosted_environment(monkeypatch):
    for name in (
        "STAFF_TOOL_PASSWORD",
        "SESSION_SECRET",
        "STAFF_TOOL_DATA_DIR",
        "STAFF_TOOL_HOSTED",
        "STAFF_TOOL_ENABLE_HOSTED_JOBS",
        "RAILWAY_ENVIRONMENT",
    ):
        monkeypatch.delenv(name, raising=False)
