Placeholder — this task's real content (requirements, tests) ships only
inside the encrypted `tasks.tar.enc` at the repo root, decrypted at
grading time. This empty directory exists only so the self-test website
can list valid task ids via the GitHub Contents API without ever reading
task content from the web tier (see arcbench-selftest-demo's
lib/github.ts:listTaskIds).
