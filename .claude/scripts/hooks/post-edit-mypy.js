// Post-edit hook: run mypy on modified Python files
const { execSync } = require("child_process");
const path = require("path");

module.exports = async function postEditMypyHook(context) {
    const editedFile = context.filePath;
    if (!editedFile || !editedFile.endsWith(".py")) {
        return {};
    }

    try {
        const repoRoot = path.resolve(__dirname, "../../../..");
        const relPath = path.relative(repoRoot, editedFile);
        const output = execSync(`conda run -n pipeline mypy ${relPath}`, {
            cwd: repoRoot,
            encoding: "utf-8",
            timeout: 20000
        });
        return {
            notifications: [{
                type: "info",
                title: "Mypy Check",
                message: `mypy passed for ${relPath}`
            }]
        };
    } catch (err) {
        return {
            notifications: [{
                type: "warning",
                title: "Mypy Issues",
                message: `mypy found type errors in ${relPath}:\n${err.stdout || err.message}`
            }]
        };
    }
};
