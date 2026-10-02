# arcbench-grader

GitHub Actions grading channel for arcbench self-test submissions.

This repo is public so grading runs on GitHub's free Actions minutes. It
holds only what the grading pipeline needs: the workflow, the scripts that
run it, and the shared task-definition code. Task content (requirements and
tests) ships encrypted as `tasks.tar.enc`, decrypted only inside a grading
run, into a temp directory that's removed when the job ends.

## How grading works

`.github/workflows/grade.yml` runs on a `repository_dispatch` from the
self-test service (authenticated with an HMAC signature, see
`scripts/verify_signature.py`) or on a manual `workflow_dispatch` by anyone
with write access to this repo. It:

1. Verifies the dispatch is genuinely from the self-test service.
2. Decrypts `tasks.tar.enc` into a temp directory, builds and runs the
   submitted app in an isolated container, and scores it against the
   relevant task's tests.
3. Reports the result back to the self-test service by callback, filtered
   by the task's visibility setting. The Actions log and this repo's
   artifacts are never the channel a submitter sees results through.

A sibling, fully self-hosted channel (server + CLI + docker-compose) lives
in a separate repo and shares the same task format and result shape.

## Secrets this repo needs

- `TASKS_KEY` — decrypts `tasks.tar.enc`.
- `SELFTEST_DISPATCH_SIGNING_KEY` — HMAC key shared with the self-test
  service; verifies inbound dispatches and signs outbound callbacks.
- `INTERNAL_CHECK_KEY` — matches the same-named env var on the self-test
  site; used only by the synthetic check below.
- `APP_DOWNLOAD_TOKEN` — optional; only needed if submitted-app downloads
  require bearer auth.
- `SELFTEST_CALLBACK_TOKEN` — optional; adds a bearer header on top of the
  HMAC signature when posting results back.

None of these are ever printed in a workflow log.

- `.github/workflows/selftest-watch.yml` + `scripts/selftest_watch.py` —
  scheduled synthetic check (every 2 hours, plus manual `workflow_dispatch`):
  resubmits the known-good `test-fixtures/app-todo-good.zip` fixture against
  `demo-todo` through the live site's internal-checker endpoint, confirms a
  result lands within 10 minutes with the expected 5/5 score, and opens an
  issue here (so GitHub emails the repo owner) if anything's off.
