import * as vscode from "vscode";

export type LaunchMode = "desktop" | "batch";
export type TerminalMode = "visible" | "detached";

export interface RunnerConfiguration {
    executable: string;
    launchMode: LaunchMode;
    terminalMode: TerminalMode;
    stopOnError: boolean;
    addFileDirectoryToPath: boolean;
}

interface ConfigurationInspect<T> {
    globalValue?: T;
    workspaceValue?: T;
    workspaceFolderValue?: T;
    globalLanguageValue?: T;
    workspaceLanguageValue?: T;
    workspaceFolderLanguageValue?: T;
}

export function getRunnerConfiguration(): RunnerConfiguration {
    const config = vscode.workspace.getConfiguration("matlabFileRunner");
    const legacyConfig = vscode.workspace.getConfiguration("matlabRunSelected");

    return {
        executable: getConfiguredValue(config, "executable", legacyConfig, "executable", "matlab"),
        launchMode: getConfiguredValue(config, "launchMode", undefined, undefined, "desktop"),
        terminalMode: getTerminalMode(config, legacyConfig),
        stopOnError: getConfiguredValue(config, "stopOnError", undefined, undefined, true),
        addFileDirectoryToPath: getConfiguredValue(
            config,
            "addFileDirectoryToPath",
            undefined,
            undefined,
            true
        )
    };
}

function getTerminalMode(
    config: vscode.WorkspaceConfiguration,
    legacyConfig: vscode.WorkspaceConfiguration
): TerminalMode {
    if (hasConfiguredValue(config.inspect("terminalMode"))) {
        return config.get<TerminalMode>("terminalMode", "visible");
    }

    const legacyInspect = legacyConfig.inspect<boolean>("showTerminal");
    if (hasConfiguredValue(legacyInspect)) {
        return legacyConfig.get<boolean>("showTerminal", true) ? "visible" : "detached";
    }

    return "visible";
}

function getConfiguredValue<T>(
    config: vscode.WorkspaceConfiguration,
    key: string,
    legacyConfig: vscode.WorkspaceConfiguration | undefined,
    legacyKey: string | undefined,
    defaultValue: T
): T {
    if (hasConfiguredValue(config.inspect<T>(key))) {
        return config.get<T>(key, defaultValue);
    }

    if (legacyConfig && legacyKey && hasConfiguredValue(legacyConfig.inspect<T>(legacyKey))) {
        return legacyConfig.get<T>(legacyKey, defaultValue);
    }

    return defaultValue;
}

function hasConfiguredValue<T>(inspect: ConfigurationInspect<T> | undefined): boolean {
    return Boolean(
        inspect &&
            (
                inspect.globalValue !== undefined ||
                inspect.workspaceValue !== undefined ||
                inspect.workspaceFolderValue !== undefined ||
                inspect.globalLanguageValue !== undefined ||
                inspect.workspaceLanguageValue !== undefined ||
                inspect.workspaceFolderLanguageValue !== undefined
            )
    );
}
