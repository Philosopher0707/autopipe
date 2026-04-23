// Post-edit hook: run ruff check --fix on modified Python files
const { execSync } = require("child_process");
const path = require("path");

module.exports = async function postEditRuffHook(context) {
    const editedFile = context.filePath;
    if (!editedFile || !editedFile.endsWith(".py")) {
        return {};
    }

    try {
        const repoRoot = path.resolve(__dirname, "../../../..");
        const relPath = path.relative(repoRoot, editedFile);
        const output = execSync(`conda run -n pipeline ruff check --fix ${relPath}`, {
            cwd: repoRoot,
            encoding: "utf-8",
            timeout: 15000
        });
        return {
            notifications: [{
                type: "info",
                title: "Ruff Check",
                message: `ruff check --fix passed for ${relPath}`
            }]
        };
    } catch (err) {
        return {
            notifications: [{
                type: "warning",
                title: "Ruff Issues",
                message: `ruff found issues in ${relPath}:\n${err.stdout || err.message}`
            }]
        };
    }
};
