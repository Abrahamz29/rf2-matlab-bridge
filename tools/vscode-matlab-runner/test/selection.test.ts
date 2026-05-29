import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { collectMatlabFilePaths } from "../src/selection";

describe("collectMatlabFilePaths", () => {
    it("keeps only MATLAB files", () => {
        const files = collectMatlabFilePaths([
            { scheme: "file", fsPath: "C:\\work\\a.m" },
            { scheme: "file", fsPath: "C:\\work\\notes.txt" },
            { scheme: "untitled", fsPath: "C:\\work\\b.m" }
        ], undefined);

        assert.deepEqual(files, ["C:\\work\\a.m"]);
    });

    it("uses the active editor fallback when no selection is provided", () => {
        const files = collectMatlabFilePaths([], { scheme: "file", fsPath: "C:\\work\\active.m" });

        assert.deepEqual(files, ["C:\\work\\active.m"]);
    });

    it("deduplicates selected files", () => {
        const files = collectMatlabFilePaths([
            { scheme: "file", fsPath: "C:\\work\\a.m" },
            { scheme: "file", fsPath: "C:\\work\\a.m" }
        ], undefined);

        assert.deepEqual(files, ["C:\\work\\a.m"]);
    });
});
