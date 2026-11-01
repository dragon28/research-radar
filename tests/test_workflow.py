import json
import re
from pathlib import Path

WF = json.loads(Path("n8n/workflow.json").read_text())


def test_workflow_is_wired_end_to_end():
    names = {n["name"] for n in WF["nodes"]}
    assert {"Run manually", "Every Monday 07:00", "Fetch feed", "Build digest"} <= names
    targets = {c["node"] for v in WF["connections"].values() for out in v["main"] for c in out}
    assert names - targets == {"Run manually", "Every Monday 07:00"}


def test_no_secrets_or_credentials_in_export():
    text = Path("n8n/workflow.json").read_text()
    assert '"credentials"' not in text
    assert not re.search(r"(gh[pousr]_[A-Za-z0-9]{20,}|github_pat_|Bearer\s+[A-Za-z0-9])", text)


def test_feed_fetch_is_resilient():
    fetch = next(n for n in WF["nodes"] if n["name"] == "Fetch feed")
    assert fetch["retryOnFail"] and fetch["onError"] == "continueRegularOutput"
    assert fetch["parameters"]["options"]["timeout"] <= 30000
