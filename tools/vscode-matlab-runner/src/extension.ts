import * as cp from "child_process";
import * as vscode from "vscode";
import { getRunnerConfiguration, type LaunchMode } from "./config";
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
            "matlabFileRunner.runSelectedFilesDesktop",
            async (uri?: vscode.Uri, selectedUris?: vscode.Uri[]) => runSelectedFiles(uri, selectedUris, "desktop")
        ),
        vscode.commands.registerCommand(
            "matlabFileRunner.runSelectedFilesHeadless",
            async (uri?: vscode.Uri, selectedUris?: vscode.Uri[]) => runSelectedFiles(uri, selectedUris, "batch")
        ),
        vscode.commands.registerCommand(
            "matlabFileRunner.runCurrentFile",
            async () => runCurrentFile()
        ),
        vscode.commands.registerCommand(
            "matlabFileRunner.runCurrentFileDesktop",
            async () => runCurrentFile("desktop")
        ),
        vscode.commands.registerCommand(
            "matlabFileRunner.runCurrentFileHeadless",
            async () => runCurrentFile("batch")
        )
    );
}

async function runSelectedFiles(
    uri?: vscode.Uri,
    selectedUris?: vscode.Uri[],
    launchModeOverride?: LaunchMode
): Promise<void> {
    const filePaths = collectMatlabFilePaths(
        Array.isArray(selectedUris) && selectedUris.length > 0 ? selectedUris : uri ? [uri] : [],
        getActiveEditorUri()
    );

    await runMatlabFiles(filePaths, launchModeOverride);
}

async function runCurrentFile(launchModeOverride?: LaunchMode): Promise<void> {
    const activeUri = getActiveEditorUri();
    const filePaths = collectMatlabFilePaths(activeUri ? [activeUri] : [], undefined);
    await runMatlabFiles(filePaths, launchModeOverride);
}

async function runMatlabFiles(filePaths: string[], launchModeOverride?: LaunchMode): Promise<void> {
    if (filePaths.length === 0) {
        vscode.window.showWarningMessage("No MATLAB .m file selected.");
        return;
    }

    const configuration = getRunnerConfiguration();
    const launchMode = launchModeOverride ?? configuration.launchMode;

    try {
        const entries = [];
        for (const filePath of filePaths) {
            entries.push(await readMatlabFileEntry(filePath));
        }

        const invocation = buildInvocation(entries, {
            launchMode,
            stopOnError: configuration.stopOnError,
            addFileDirectoryToPath: configuration.addFileDirectoryToPath
        });

        outputChannel.appendLine(`Starting MATLAB with ${entries.length} file(s).`);
        outputChannel.appendLine(`Mode: ${launchMode}; terminal: ${configuration.terminalMode}`);
        for (const entry of entries) {
            outputChannel.appendLine(`- ${entry.filePath}`);
        }

        if (configuration.terminalMode === "visible") {
            launchInVisibleTerminal(configuration.executable, invocation.args, invocation.cwd);
        } else {
            launchDetached(configuration.executable, invocation.args, invocation.cwd);
        }

        vscode.window.showInformationMessage(`Starting MATLAB ${displayLaunchMode(launchMode)}: ${entries.length} file(s)`);
    } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        outputChannel.appendLine(`Error: ${message}`);
        vscode.window.showErrorMessage(`Could not start MATLAB: ${message}`);
    }
}

function displayLaunchMode(launchMode: LaunchMode): string {
    return launchMode === "batch" ? "headless" : "with desktop";
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
