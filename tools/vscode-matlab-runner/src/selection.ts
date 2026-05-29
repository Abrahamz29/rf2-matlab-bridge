import * as path from "path";

export interface FileUriLike {
    scheme: string;
    fsPath: string;
}

export function collectMatlabFilePaths(
    selectedUris: readonly FileUriLike[],
    fallbackUri: FileUriLike | undefined
): string[] {
    const uris = selectedUris.length > 0 ? selectedUris : fallbackUri ? [fallbackUri] : [];
    const seen = new Set<string>();
    const filePaths: string[] = [];

    for (const uri of uris) {
        if (uri.scheme !== "file" || path.extname(uri.fsPath).toLowerCase() !== ".m") {
            continue;
        }

        const key = normalizeForComparison(uri.fsPath);
        if (seen.has(key)) {
            continue;
        }

        seen.add(key);
        filePaths.push(uri.fsPath);
    }

    return filePaths;
}

function normalizeForComparison(filePath: string): string {
    const normalized = path.normalize(filePath);
    return process.platform === "win32" ? normalized.toLowerCase() : normalized;
}
