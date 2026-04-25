# AutoPipe Production Readiness Roadmap

## Issues

### DONE

| # | Issue | Severity | Fix |
|---|-------|----------|-----|
| 1 | TUI subsystem (tui.py, widgets.py, state.py, --tui flag) | - | Removed cleanly; 107 core unit tests pass, 83 backend tests pass |
| 2 | Cross-subsystem dependency: core/pipeline.py imports dashboard.state | Medium | Eliminated watcher system from core Pipeline; core no longer imports dashboard |

### IN PROGRESS

| # | Issue | Severity | File | Fix |
|---|-------|----------|------|-----|
| 3 | psutil._psplatform private API | Medium | runner.py:244-245 | Replace with pynvml/nvidia-ml-py or remove GPU metric collection |
| 4 | seed.py uses print() instead of structured logging | Low | app/seed.py:75-751 | Convert to logging.getLogger(__name__) |

### PENDING

| # | Issue | Severity | File | Fix |
|---|-------|----------|------|-----|
| 5 | No integration tests for actual pipeline executor | High | app/executor/runner.py | Write tests that create a pipeline, trigger run, verify DB + WebSocket state |
| 6 | Frontend pnpm-lock.yaml drift | Low | pnpm-lock.yaml | Commit lockfile or revert |
| 7 | Backend seed script has hardcoded demo credentials | Medium | app/seed.py:135-140 | Document as dev-only or generate random passwords |
| 8 | `__import__` in TUI simulated metric ticks | - | FIXED by TUI removal |
| 9 | Module-level mutable globals without locking in runner.py | - | FIXED in commit 382d61d2 |

## Acceptance Criteria

- [ ] All backend tests pass (83/83)
- [ ] All core unit tests pass (107/107)
- [ ] No `except: pass` patterns
- [ ] No private API access (psutil._psplatform)
- [ ] Seed script uses structured logging
- [ ] Integration tests exist for executor thread logic
