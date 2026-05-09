<!--
Thanks for the PR! A few quick checks before you submit:
- One concern per PR. Stack only when changes genuinely depend on each other.
- Branch prefix: feat/, fix/, docs/, ci/, chore/
- Run the local check loop for the area you touched (see CONTRIBUTING.md)
-->

## Summary
<!-- 1-3 sentences: what does this PR do, and why? Link issue if relevant. -->

## What this changes
<!-- Bullet list of the actual changes. -->
-
-

## Test plan
<!-- How you verified this works. Check whatever applies; add specifics. -->
- [ ] `cargo fmt --all -- --check` clean
- [ ] `cargo clippy --workspace --all-targets -- -D warnings` clean
- [ ] `cargo test --workspace` passes
- [ ] `cd frontend && npm run check` clean
- [ ] `cd frontend && npm run build` produces a clean `build/`
- [ ] Bench: `python -m bench.cli dry-run-all` (if bench/ touched)
- [ ] Manual smoke test (if user-facing): describe what you exercised

## Linked spec / decisions
<!-- If this touches a locked decision in the v1 spec or implements a row from the
     plan, link it. If it changes a locked decision, link the issue where
     that change was discussed. -->

## Notes for the reviewer
<!-- Tricky parts, alternative approaches considered, things you're unsure about. -->
