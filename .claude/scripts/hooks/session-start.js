// Autopipe Session Start Hook
// Loads key project context reminders for Claude Code.

module.exports = async function sessionStartHook(context) {
    return {
        systemPromptAdditions: [
            "**Autopipe Context**",
            "- Three independent subsystems: core (`autopipe/`), dashboard backend (`autopipe/dashboard/backend/`), dashboard frontend (`autopipe/dashboard/frontend/`).",
            "- Core library uses conda env `pipeline`. Backend uses its own `.venv` in `dashboard/backend/`. Frontend uses `pnpm`.",
            "- Strict mypy, ruff lint, black format, 80% pytest coverage gates.",
            "- Steps should be ~20-50 lines; thin CLI handlers delegate to core.",
            "- No secrets in source; use `.env` + `python-dotenv`.",
            "- Prefer `pathlib.Path`, `structlog`, and Pydantic v2 models.",
            ""
        ].join("\n")
    };
};
