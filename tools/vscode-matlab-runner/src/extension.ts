import * as cp from "child_process";
import * as vscode from "vscode";
import { getRunnerConfiguration } from "./config";
import { buildInvocation, readMatlabFileEntry } from "./invocation";
import { collectMatlabFilePaths } from "./selection";
import { formatShellCommand } from "./shell";

let outputChannel: vscode.OutputChannel;

export function activate(context: vscode.ExtensionContext): void {
    outputChannel = vscode.window.createOutputChannel("MATLAB File Runner");

    context.subscriptions.push(
        outputChannel,
        vscode.commands.registerCommand(
            "matlabFileRunner.runSelectedFiles",
            async (uri?: vscode.Uri, selectedUris?: vscode.Uri[]) => runSelectedFiles(uri, selectedUris)
        ),
        vscode.commands.registerCommand(
            "matlabFileRunner.runCurrentFile",
            async () => runCurrentFile()
        )
    );
}

async function runSelectedFiles(uri?: vscode.Uri, selectedUris?: vscode.Uri[]): Promise<void> {
    const filePaths = collectMatlabFilePaths(
        Array.isArray(selectedUris) && selectedUris.length > 0 ? selectedUris : uri ? [uri] : [],
        getActiveEditorUri()
    );

    await runMatlabFiles(filePaths);
}

async function runCurrentFile(): Promise<void> {
    const activeUri = getActiveEditorUri();
    const filePaths = collectMatlabFilePaths(activeUri ? [activeUri] : [], undefined);
    await runMatlabFiles(filePaths);
}

async function runMatlabFiles(filePaths: string[]): Promise<void> {
    if (filePaths.length === 0) {
        vscode.window.showWarningMessage("No MATLAB .m file selected.");
        return;
    }

    const configuration = getRunnerConfiguration();

    try {
        const entries = [];
        for (const filePath of filePaths) {
            entries.push(await readMatlabFileEntry(filePath));
        }

        const invocation = buildInvocation(entries, {
            launchMode: configuration.launchMode,
            stopOnError: configuration.stopOnError,
            addFileDirectoryToPath: configuration.addFileDirectoryToPath
        });

        outputChannel.appendLine(`Starting MATLAB with ${entries.length} file(s).`);
        outputChannel.appendLine(`Mode: ${configuration.launchMode}; terminal: ${configuration.terminalMode}`);
        for (const entry of entries) {
            outputChannel.appendLine(`- ${entry.filePath}`);
        }

        if (configuration.terminalMode === "visible") {
            launchInVisibleTerminal(configuration.executable, invocation.args, invocation.cwd);
        } else {
            launchDetached(configuration.executable, invocation.args, invocation.cwd);
        }

        vscode.window.showInformationMessage(`Starting MATLAB: ${entries.length} file(s)`);
    } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        outputChannel.appendLine(`Error: ${message}`);
        vscode.window.showErrorMessage(`Could not start MATLAB: ${message}`);
    }
}

function getActiveEditorUri(): vscode.Uri | undefined {
    const editor = vscode.window.activeTextEditor;
    if (!editor || editor.document.uri.scheme !== "file") {
        return undefined;
    }

    return editor.document.uri;
}

function launchInVisibleTerminal(executable: string, args: string[], cwd: string): void {
    const terminal = vscode.window.createTerminal({
        name: "MATLAB File Runner",
        cwd,
        shellPath: process.platform === "win32" ? "powershell.exe" : undefined
    });

    terminal.show(true);
    terminal.sendText(formatShellCommand(executable, args));
}

function launchDetached(executable: string, args: string[], cwd: string): void {
    const child = cp.spawn(executable, args, {
        cwd,
        detached: true,
        stdio: "ignore",
        windowsHide: false
    });
    child.unref();
}

export function deactivate(): void {}
