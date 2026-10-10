"""Exercise the shipped shell recipes from a rig witness directory.

The transaction stub keeps destructive patrol rollover off real stores. The
optional real-gc test separately proves CLI routing and hook identity using a
disposable city and an isolated bd backend stub.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import tomllib

import pytest

ROOT = Path(__file__).resolve().parents[1]


def step(role, name):
    formula = tomllib.loads((ROOT / f"gastown/formulas/mol-{role}-patrol.toml").read_text())
    return next(s["description"] for s in formula["steps"] if s["id"] == name)


def bash_blocks(text):
    return re.findall(r"```bash\n(.*?)\n```", text, re.S)


def startup(city):
    text = (ROOT / "gastown/agents/witness/prompt.template.md").read_text()
    text = text.split("## Startup Protocol", 1)[1].split("## CRITICAL:", 1)[0]
    return bash_blocks(text)[0].replace("{{ .CityRoot }}", str(city))


@pytest.fixture
def shell_fixture(tmp_path):
    city = tmp_path / "city with spaces"
    cwd = city / ".gc/agents/fixture/witness"
    cwd.mkdir(parents=True)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    stub = bin_dir / "gc"
    stub.write_text('''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
a = sys.argv[1:]
with open(os.environ["CALLS"], "a") as f: f.write(json.dumps(a) + "\\n")
if a[:2] == ["session", "list"]:
    print(os.environ["SESSIONS"]); sys.exit(0)
if a[0] == "ready":
    if os.environ.get("FAIL_QUEUE"): sys.exit(9)
    agent = next(x.split("=", 1)[1] for x in a if x.startswith("--assignee="))
    print(json.dumps(json.loads(os.environ["QUEUES"]).get(agent, []))); sys.exit(0)
if a[0] == "bd":
    if "--city=" + os.environ["GC_CITY_PATH"] not in a:
        sys.exit("patrol/session operation reached the rig store")
    a = [x for x in a[1:] if not x.startswith("--city=")]
    if a[0] == "list":
        status = next(x.split("=", 1)[1] for x in a if x.startswith("--status="))
        if os.environ.get("FAIL_LIST") or os.environ.get("FAIL_STATUS") == status: sys.exit(9)
        print(json.dumps(json.loads(os.environ["WISPS"]).get(status, [])))
    elif a[:2] == ["mol", "wisp"]:
        if os.environ.get("FAIL_POUR"): sys.exit(9)
        print('{"new_epic_id":"town-next"}')
    elif a[0] == "update" and os.environ.get("FAIL_ASSIGN"): sys.exit(9)
elif a[0] not in ("mail", "hook", "runtime"):
    sys.exit("unexpected command")
''')
    stub.chmod(0o755)
    calls = tmp_path / "calls.jsonl"
    env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}",
           "GC_CITY_PATH": str(city), "GC_AGENT": "fixture/gastown.witness",
           "CALLS": str(calls), "WISPS": "{}", "SESSIONS": '{"sessions":[]}',
           "QUEUES": "{}"}

    def run(script, **overrides):
        calls.write_text("")
        result = subprocess.run(["bash", "-c", script], cwd=cwd,
                                env={**env, **overrides}, text=True, capture_output=True)
        return result, [json.loads(line) for line in calls.read_text().splitlines()]
    return city, run


def test_startup_reuses_city_hook_without_pouring(shell_fixture):
    city, run = shell_fixture
    result, calls = run(startup(city), WISPS=json.dumps({"in_progress": [{"id": "town-hook"}]}))
    assert result.returncode == 0, result.stderr
    assert "Resuming patrol wisp town-hook" in result.stdout
    assert not any("wisp" in c or "burn" in c for c in calls)


def test_missing_scope_negative_control(shell_fixture):
    city, run = shell_fixture
    script = startup(city).replace(f'--city="{city}" ', "")
    result, calls = run(script)
    assert result.returncode != 0
    assert not any("wisp" in c or "burn" in c for c in calls)


@pytest.mark.parametrize("status", ["open", "in_progress"])
def test_startup_read_failure_does_not_pour(shell_fixture, status):
    city, run = shell_fixture
    result, calls = run(startup(city), FAIL_STATUS=status)
    assert result.returncode != 0
    assert not any("wisp" in c or "burn" in c for c in calls)


@pytest.mark.parametrize("queued", [False, True])
def test_witness_rollover_reuses_or_pours_exactly_one(shell_fixture, queued):
    _, run = shell_fixture
    script = bash_blocks(step("witness", "next-iteration"))[1]
    wisps = {"open": [{"id": "town-next"}]} if queued else {}
    result, calls = run(script, WISPS=json.dumps(wisps))
    assert result.returncode == 0, result.stderr
    assert sum("wisp" in c for c in calls) == (0 if queued else 1)
    assert "NEXT" not in result.stderr


@pytest.mark.parametrize("failure", ["FAIL_LIST", "FAIL_POUR", "FAIL_ASSIGN"])
def test_failed_rollover_never_burns_current(shell_fixture, failure):
    _, run = shell_fixture
    blocks = bash_blocks(step("witness", "next-iteration"))
    script = "\n".join(blocks[1:3]).replace("<this-wisp-id>", "town-current")
    result, calls = run(script, **{failure: "1"})
    assert result.returncode != 0
    assert not any("burn" in c for c in calls)


def test_queue_check_preserves_session_and_assignee_identities(shell_fixture):
    _, run = shell_fixture
    sessions = {"sessions": [
        {"id": "numeric-1", "name": "city-session", "agent_name": "gastown.mayor", "state": "active"},
        {"id": "numeric-2", "name": "fixture-session", "template": "fixture/gastown.refinery", "state": "active"},
        {"name": "closed", "state": "active", "closed": True},
        {"name": "asleep", "state": "asleep"},
    ]}
    queues = {"gastown.mayor": [{"updated_at": "2026-10-10T18:00:00Z"}],
              "fixture/gastown.refinery": [{"updated_at": "2026-10-10T18:01:00Z"}, {"updated_at": "2026-10-10T18:02:00Z"}]}
    result, calls = run(bash_blocks(step("deacon", "queue-starvation-check"))[0],
                        SESSIONS=json.dumps(sessions), QUEUES=json.dumps(queues))
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [
        "city-session\tgastown.mayor\t1\t2026-10-10T18:00:00Z",
        "fixture-session\tfixture/gastown.refinery\t2\t2026-10-10T18:02:00Z"]
    assert all(c[0] == "ready" for c in calls[1:])


@pytest.mark.parametrize("roster", ["[]", '{"sessions":null}', '{"sessions":[{"state":"active","id":"123"}]}'])
def test_bad_roster_is_not_an_empty_queue(shell_fixture, roster):
    _, run = shell_fixture
    result, _ = run(bash_blocks(step("deacon", "queue-starvation-check"))[0], SESSIONS=roster)
    assert result.returncode != 0
    assert result.stdout == ""


def test_queue_failure_is_not_zero_work(shell_fixture):
    _, run = shell_fixture
    result, _ = run(bash_blocks(step("deacon", "queue-starvation-check"))[0],
                    SESSIONS='{"sessions":[{"name":"fixture/gastown.refinery","state":"active"}]}', FAIL_QUEUE="1")
    assert result.returncode != 0
    assert result.stdout == ""


@pytest.mark.parametrize("role", ["witness", "deacon"])
def test_successor_is_not_reported_idle(role):
    text = step(role, "next-iteration")
    assert "IDLE: no work" not in text
    assert "gc hook\ngc runtime request-restart" in text

