"""Executable hostile-message checks for the generated Shopify iframe bridge."""

import json
import os
import subprocess

import pytest


HERE = os.path.dirname(os.path.abspath(__file__))


def _node_env():
    env = dict(os.environ)
    node_path = env.get("DOMELAB_NODE_PATH")
    if not node_path:
        candidate = os.path.abspath(os.path.join(HERE, "..", "js", "node_modules"))
        if os.path.isdir(os.path.join(candidate, "jsdom")):
            node_path = candidate
    if not node_path:
        pytest.skip(
            "jsdom not available; set DOMELAB_NODE_PATH or run npm ci in generator/js"
        )
    env["NODE_PATH"] = node_path
    return env


def test_shopify_embed_runtime_battery(review_staging):
    result = subprocess.run(
        [
            "node",
            os.path.join(HERE, "shopify_embed_runtime_battery.js"),
            os.path.join(review_staging, "packs", "picker.staged.html"),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=_node_env(),
    )
    assert result.stdout, result.stderr
    payload = json.loads(result.stdout[result.stdout.index("{"):])
    failed = [check for check in payload["checks"] if not check["pass"]]
    assert result.returncode == 0 and not failed, failed
    assert payload["total"] >= 10
