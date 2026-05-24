"use strict";

const fs = require("fs");
const path = require("path");
const cp = require("child_process");
const vscode = require("vscode");

function activate(context) {
    const disposable = vscode.commands.registerCommand(
        "matlabRunSelected.runFile",
        async (uri, selectedUris) => runSelectedFile(uri, selectedUris)
    );

    context.subscriptions.push(disposable);
}

async function runSelectedFile(uri, selectedUris) {
    const target = pickTargetUri(uri, selectedUris);
    if (!target) {
        vscode.window.showWarningMessage("No MATLAB file selected.");
        return;
    }

    const filePath = target.fsPath;
    if (path.extname(filePath).toLowerCase() !== ".m") {
        vscode.window.showWarningMessage("Select a MATLAB .m file.");
        return;
    }

    let invocation;
    try {
        invocation = await buildMatlabInvocation(filePath);
    } catch (error) {
        vscode.window.showErrorMessage(`Could not prepare MATLAB launch: ${error.message}`);
        return;
    }

    const config = vscode.workspace.getConfiguration("matlabRunSelected");
    const executable = config.get("executable", "matlab");
    const showTerminal = config.get("showTerminal", true);

    try {
        if (showTerminal) {
            launchInVisibleTerminal(executable, invocation.command, invocation.cwd);
        } else {
            launchDetached(executable, invocation.command, invocation.cwd);
        }
        vscode.window.showInformationMessage(`Starting MATLAB: ${path.basename(filePath)}`);
    } catch (error) {
        vscode.window.showErrorMessage(`Could not start MATLAB: ${error.message}`);
    }
}

function pickTargetUri(uri, selectedUris) {
    if (Array.isArray(selectedUris) && selectedUris.length > 0) {
        return selectedUris[0];
    }
    if (uri && uri.fsPath) {
        return uri;
    }
    const editor = vscode.window.activeTextEditor;
    if (editor && editor.document && editor.document.uri.scheme === "file") {
        return editor.document.uri;
    }
    return null;
}

async function buildMatlabInvocation(filePath) {
    const fileText = await fs.promises.readFile(filePath, "utf8");
    const fileDir = path.dirname(filePath);
    const parsed = parseMatlabEntry(fileText, filePath);
    const command = [
        "try",
        `cd(${matlabString(fileDir)});`,
        `addpath(${matlabString(fileDir)});`,
        parsed.isFunction
            ? `feval(${matlabString(parsed.functionName)});`
            : `run(${matlabString(filePath)});`,
        "catch ME",
        "disp(getReport(ME, 'extended', 'hyperlinks', 'off'));",
        "end"
    ].join(" ");

    return {
        command,
        cwd: fileDir
    };
}

function parseMatlabEntry(fileText, filePath) {
    const fallbackName = path.basename(filePath, ".m");
    let inBlockComment = false;

    for (const rawLine of fileText.split(/\r?\n/)) {
        const line = rawLine.trim();
        if (!line) {
            continue;
        }
        if (inBlockComment) {
            if (line.startsWith("%}")) {
                inBlockComment = false;
            }
            continue;
        }
        if (line.startsWith("%{")) {
            inBlockComment = true;
            continue;
        }
        if (line.startsWith("%")) {
            continue;
        }
        if (!/^function\b/.test(line)) {
            return {
                isFunction: false,
                functionName: fallbackName
            };
        }

        const name = parseFunctionName(line) || fallbackName;
        return {
            isFunction: true,
            functionName: name
        };
    }

    return {
        isFunction: false,
        functionName: fallbackName
    };
}

function parseFunctionName(line) {
    const withoutKeyword = line.replace(/^function\b/, "").trim();
    const rhs = withoutKeyword.includes("=")
        ? withoutKeyword.slice(withoutKeyword.indexOf("=") + 1).trim()
        : withoutKeyword;
    const match = rhs.match(/^([A-Za-z]\w*)\b/);
    return match ? match[1] : "";
}

function matlabString(value) {
    return `'${String(value).replace(/'/g, "''")}'`;
}

function launchInVisibleTerminal(executable, matlabCommand, cwd) {
    const terminal = vscode.window.createTerminal({
        name: "MATLAB Run Selected",
        cwd,
        shellPath: process.platform === "win32" ? "powershell.exe" : undefined
    });

    terminal.show(true);
    terminal.sendText(formatShellCommand(executable, ["-r", matlabCommand]));
}

function launchDetached(executable, matlabCommand, cwd) {
    const child = cp.spawn(executable, ["-r", matlabCommand], {
        cwd,
        detached: true,
        stdio: "ignore",
        windowsHide: false
    });
    child.unref();
}

function formatShellCommand(executable, args) {
    if (process.platform === "win32") {
        return `& ${quotePowerShell(executable)} ${args.map(quotePowerShell).join(" ")}`;
    }
    return [quoteShell(executable), ...args.map(quoteShell)].join(" ");
}

function quotePowerShell(value) {
    return `'${String(value).replace(/'/g, "''")}'`;
}

function quoteShell(value) {
    return `'${String(value).replace(/'/g, "'\\''")}'`;
}

function deactivate() {}

module.exports = {
    activate,
    deactivate
};
