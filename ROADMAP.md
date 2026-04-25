# AutoPipe Production Readiness Roadmap

## Issues

### DONE

| # | Issue | Severity | Fix |
|---|-------|----------|-----|
| 1 | TUI subsystem (tui.py, widgets.py, state.py, --tui flag) | - | Removed cleanly; 107 core unit tests pass, 86 backend tests pass |
| 2 | Cross-subsystem dependency: core/pipeline.py imports dashboard.state | Medium | Eliminated watcher system from core Pipeline; core no longer imports dashboard |
| 3 | psutil._psplatform private API | Medium | Removed GPU metric collection via private API; CPU/memory metrics remain via public psutil APIs |
| 4 | seed.py uses print() instead of structured logging | Low | Converted to logger.info(); added dev-only warning docstring |
| 5 | No integration tests for actual pipeline executor | High | Added tests/test_executor.py with 3 integration tests: success, failure, cancellation |
| 6 | Frontend pnpm-lock.yaml drift | Low | Committed lockfile with Playwright dependency |
| 7 | Backend seed script has hardcoded demo credentials | Medium | Added module-level WARNING docstring; credentials are dev-only by design |
| 8 | `__import__` in TUI simulated metric ticks | - | FIXED by TUI removal |
| 9 | Module-level mutable globals without locking in runner.py | - | FIXED in commit 382d61d2 |

## Test Results

- Core unit tests: **107 passed**
- Backend tests: **86 passed** (83 API + 3 executor integration)

## Acceptance Criteria

- [x] All backend tests pass (86/86)
- [x] All core unit tests pass (107/107)
- [x] No `except: pass` patterns
- [x] No private API access (psutil._psplatform)
- [x] Seed script uses structured logging
- [x] Integration tests exist for executor thread logic
