# arcbench-grader

GitHub Actions grading channel for arcbench self-test submissions.

This repo is public so grading runs on GitHub's free Actions minutes. It
holds only what the grading pipeline needs: the workflow, the scripts that
run it, and the shared task-definition code. Task content (requirements and
tests) ships encrypted as `tasks.tar.enc`, decrypted only inside a grading
run, into a temp directory that's removed when the job ends.

`tasks/<task_id>/` directories at the repo root are empty placeholders
(just a README each) — they exist only so the self-test website can list
valid task ids via the GitHub Contents API without reading any task
content from the web tier. The real content lives only in `tasks.tar.enc`.

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
  service; verifies inbound dispatches and signs outbound callbacks. This
  is the actual integrity check on both directions — not a bearer token.
- `INTERNAL_CHECK_KEY` — matches the same-named env var on the self-test
  site; used only by the synthetic check below.
- `APP_DOWNLOAD_TOKEN` — unused currently: submission zips are uploaded to
  a public Blob URL, so no download auth is needed. Kept as an option in
  grade.sh in case that ever changes.
- `SELFTEST_CALLBACK_TOKEN` — unused currently: the site's callback route
  only checks the HMAC signature above, not a bearer token. Kept as an
  option in report_back.py for the same reason.

None of these are ever printed in a workflow log.

## Synthetic check

`.github/workflows/selftest-watch.yml` + `scripts/selftest_watch.py` run
every 2 hours (plus manual `workflow_dispatch`): resubmit the known-good
`test-fixtures/app-todo-good.zip` fixture against `demo-todo` through the
live site's internal-checker endpoint, confirm a result lands within 10
minutes with the expected 5/5 score, and open an issue here (so GitHub
emails the repo owner) if anything's off.
