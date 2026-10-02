#!/usr/bin/env python3
"""Synthetic check for the self-test website: submit the known-good
`demo-todo` fixture through the real submit -> dispatch -> grade -> callback
-> poll pipeline (using the site's internal-checker identity, which never
touches a participant's daily quota — see actions/README_ACTIONS.md
"Internal synthetic check" in the public repo) and verify the result lands
within the time budget and matches the expected score.

Run by .github/workflows/selftest-watch.yml, which opens an issue on
failure. Exits 1 and writes a reason to both $GITHUB_STEP_SUMMARY and
$FAILURE_FILE on any failure (wrong score, wrong status, timeout, or a
non-200 from the site); exits 0 and writes a short summary on success.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

WEB_BASE_URL = os.environ.get("WEB_BASE_URL", "https://arcbench-selftest-web.vercel.app").rstrip("/")
TASK_ID = os.environ.get("CHECK_TASK_ID", "demo-todo")
EXPECTED_PASSED = int(os.environ.get("EXPECTED_PASSED", "5"))
EXPECTED_TOTAL = int(os.environ.get("EXPECTED_TOTAL", "5"))
FIXTURE_ZIP = os.environ.get("FIXTURE_ZIP", "test-fixtures/app-todo-good.zip")
INTERNAL_CHECK_KEY = os.environ.get("INTERNAL_CHECK_KEY", "")
DEADLINE_S = int(os.environ.get("DEADLINE_S", str(10 * 60)))
POLL_INTERVAL_S = int(os.environ.get("POLL_INTERVAL_S", "20"))
FAILURE_FILE = os.environ.get("FAILURE_FILE", "selftest-failure.md")


def _write_summary(heading: str, body: str) -> None:
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(f"## {heading}\n\n{body}\n")


def fail(reason: str) -> None:
    _write_summary("自检失败 (self-test synthetic check FAILED)", reason)
    with open(FAILURE_FILE, "w", encoding="utf-8") as f:
        f.write(reason + "\n")
    print(f"FAILED: {reason}", file=sys.stderr)
    sys.exit(1)


def ok(detail: str) -> None:
    _write_summary("自检通过 (self-test synthetic check passed)", detail)
    print(f"PASSED: {detail}")


def request(method: str, path: str, data: bytes | None = None, headers: dict | None = None):
    req = urllib.request.Request(f"{WEB_BASE_URL}{path}", data=data, method=method)
    req.add_header("X-Internal-Key", INTERNAL_CHECK_KEY)
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        try:
            payload = json.loads(body) if body else {}
        except json.JSONDecodeError:
            payload = {"raw": body}
        return e.code, payload
    except urllib.error.URLError as e:
        return 0, {"error": str(e)}


def submit() -> str:
    boundary = "selftestwatchboundary"
    with open(FIXTURE_ZIP, "rb") as f:
        zip_bytes = f.read()

    def field(name: str, value: str) -> bytes:
        return (
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n"
        ).encode()

    body = b"".join(
        [
            field("taskId", TASK_ID),
            (
                f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; "
                f"filename=\"app.zip\"\r\nContent-Type: application/zip\r\n\r\n"
            ).encode()
            + zip_bytes
            + b"\r\n",
            f"--{boundary}--\r\n".encode(),
        ]
    )
    status, payload = request(
        "POST",
        "/api/internal/submit",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    if status != 200 or "id" not in payload:
        fail(f"提交失败：HTTP {status}，响应 {payload}")
    return payload["id"]


def poll(submission_id: str) -> dict:
    start = time.monotonic()
    last = None
    while time.monotonic() - start < DEADLINE_S:
        status, payload = request("GET", f"/api/internal/submissions/{submission_id}")
        if status == 200:
            sub = payload.get("submission", {})
            last = sub
            if sub.get("status") != "queued":
                return sub
        else:
            last = f"HTTP {status}: {payload}"
        time.sleep(POLL_INTERVAL_S)
    fail(
        f"超时：{DEADLINE_S // 60} 分钟内未出结果（提交 id={submission_id}，最后一次查询：{last}）"
    )
    raise AssertionError("unreachable")  # fail() always exits


def main() -> None:
    if not INTERNAL_CHECK_KEY:
        fail("未配置 INTERNAL_CHECK_KEY，无法发起内部自检提交")

    start = time.monotonic()
    submission_id = submit()
    sub = poll(submission_id)
    elapsed = time.monotonic() - start

    status = sub.get("status")
    result = sub.get("result") or {}
    passed = result.get("passed")
    total = result.get("total")

    if status != "passed":
        fail(
            f"网页状态异常：期望 status=passed，实际 status={status}，"
            f"detail={result.get('detail')!r}，提交 id={submission_id}，耗时 {elapsed:.0f}s"
        )
    if passed != EXPECTED_PASSED or total != EXPECTED_TOTAL:
        fail(
            f"分数不符：期望 {EXPECTED_PASSED}/{EXPECTED_TOTAL}，实际 {passed}/{total}，"
            f"提交 id={submission_id}，耗时 {elapsed:.0f}s"
        )

    ok(f"提交 id={submission_id}，{elapsed:.0f}s 内返回 {passed}/{total}，status=passed。")


if __name__ == "__main__":
    main()
