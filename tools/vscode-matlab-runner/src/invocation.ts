import * as fs from "fs/promises";
import * as path from "path";
import type { LaunchMode } from "./config";

export type MatlabEntryKind = "script" | "function";

export interface MatlabFileEntry {
    filePath: string;
    directory: string;
    kind: MatlabEntryKind;
    functionName: string;
}

export interface InvocationOptions {
    launchMode: LaunchMode;
    stopOnError: boolean;
    addFileDirectoryToPath: boolean;
}

export interface MatlabInvocation {
    args: string[];
    command: string;
    cwd: string;
}

export async function readMatlabFileEntry(filePath: string): Promise<MatlabFileEntry> {
    const fileText = await fs.readFile(filePath, "utf8");
    return parseMatlabEntry(fileText, filePath);
}

export function parseMatlabEntry(fileText: string, filePath: string): MatlabFileEntry {
    const fallbackName = path.basename(filePath, ".m");
    let inBlockComment = false;

    for (const rawLine of fileText.split(/\r?\n/)) {
        const line = rawLine.replace(/^\uFEFF/, "").trim();
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
            return createEntry(filePath, "script", fallbackName);
        }

        return createEntry(filePath, "function", parseFunctionName(line) || fallbackName);
    }

    return createEntry(filePath, "script", fallbackName);
}

export function buildInvocation(entries: MatlabFileEntry[], options: InvocationOptions): MatlabInvocation {
    if (entries.length === 0) {
        throw new Error("No MATLAB files were provided.");
    }

    const command = buildMatlabCommand(entries, options);
    const args = options.launchMode === "batch" ? ["-batch", command] : ["-r", command];

    return {
        args,
        command,
        cwd: entries[0].directory
    };
}

export function buildMatlabCommand(entries: MatlabFileEntry[], options: InvocationOptions): string {
    const statements = entries.map((entry) => buildEntryStatement(entry, options.addFileDirectoryToPath));
    const body = statements.join(" ");

    if (options.stopOnError) {
        return [
            "try",
            body,
            "catch ME",
            "disp(getReport(ME, 'extended', 'hyperlinks', 'off'));",
            "rethrow(ME);",
            "end"
        ].join(" ");
    }

    return statements
        .map((statement) => [
            "try",
            statement,
            "catch ME",
            "disp(getReport(ME, 'extended', 'hyperlinks', 'off'));",
            "end"
        ].join(" "))
        .join(" ");
}

function createEntry(filePath: string, kind: MatlabEntryKind, functionName: string): MatlabFileEntry {
    return {
        filePath,
        directory: path.dirname(filePath),
        kind,
        functionName
    };
}

function buildEntryStatement(entry: MatlabFileEntry, addFileDirectoryToPath: boolean): string {
    const setup = [
        `cd(${matlabString(entry.directory)});`,
        addFileDirectoryToPath ? `addpath(${matlabString(entry.directory)});` : ""
    ].filter(Boolean);

    const command = entry.kind === "function"
        ? `feval(${matlabString(entry.functionName)});`
        : `run(${matlabString(entry.filePath)});`;

    return [...setup, command].join(" ");
}

function parseFunctionName(line: string): string {
    const withoutKeyword = line.replace(/^function\b/, "").trim();
    const rhs = withoutKeyword.includes("=")
        ? withoutKeyword.slice(withoutKeyword.indexOf("=") + 1).trim()
        : withoutKeyword;
    const match = rhs.match(/^([A-Za-z]\w*)\b/);
    return match ? match[1] : "";
}

export function matlabString(value: string): string {
    return `'${String(value).replace(/'/g, "''")}'`;
}
