"""Starting from the environment, and refusing to start degraded."""

import pytest
import uvicorn

from strata.common.service import serve


class Missing(Exception):
    pass


def test_a_built_app_is_served_where_the_environment_says(monkeypatch):
    served = {}
    monkeypatch.setattr(uvicorn, "run", lambda app, **kw: served.update(app=app, **kw))
    monkeypatch.setenv("STRATA_SERVE_HOST", "127.0.0.1")
    monkeypatch.setenv("STRATA_SERVE_PORT", "9999")
    serve(lambda: "the app", prog="strata-thing", port=8000, error=Missing)
    assert served == {"app": "the app", "host": "127.0.0.1", "port": 9999}


def test_the_port_defaults_per_service(monkeypatch):
    served = {}
    monkeypatch.setattr(uvicorn, "run", lambda app, **kw: served.update(**kw))
    monkeypatch.delenv("STRATA_SERVE_HOST", raising=False)
    monkeypatch.delenv("STRATA_SERVE_PORT", raising=False)
    serve(lambda: "the app", prog="strata-thing", port=8000, error=Missing)
    assert served == {"host": "0.0.0.0", "port": 8000}


def test_a_missing_setting_is_a_failed_start_not_a_running_one(monkeypatch, capsys):
    monkeypatch.setattr(uvicorn, "run", lambda *a, **kw: pytest.fail("must not serve"))

    def build():
        raise Missing("$STRATA_THING is not set.")

    with pytest.raises(SystemExit) as raised:
        serve(build, prog="strata-thing", port=8000, error=Missing)
    assert raised.value.code == 2
    assert capsys.readouterr().err == "strata-thing: $STRATA_THING is not set.\n"


def test_any_other_failure_is_a_bug_and_propagates(monkeypatch):
    monkeypatch.setattr(uvicorn, "run", lambda *a, **kw: pytest.fail("must not serve"))

    def build():
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        serve(build, prog="strata-thing", port=8000, error=Missing)
