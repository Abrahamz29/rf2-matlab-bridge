import { describe, it } from "node:test";
import assert from "node:assert/strict";
import * as path from "path";
import {
    buildInvocation,
    matlabString,
    parseMatlabEntry
} from "../src/invocation";

describe("parseMatlabEntry", () => {
    it("detects script files", () => {
        const entry = parseMatlabEntry("% comment\nx = 1;", "C:\\work\\demo_script.m");

        assert.equal(entry.kind, "script");
        assert.equal(entry.functionName, "demo_script");
    });

    it("detects function files with output arguments", () => {
        const entry = parseMatlabEntry("function [a, b] = fitCurve(x)\na = x;", "C:\\work\\fitCurve.m");

        assert.equal(entry.kind, "function");
        assert.equal(entry.functionName, "fitCurve");
    });

    it("skips block comments before the entry point", () => {
        const entry = parseMatlabEntry("%{\nnotes\n%}\nfunction result = solveCase()\nresult = true;", "solveCase.m");

        assert.equal(entry.kind, "function");
        assert.equal(entry.functionName, "solveCase");
    });

    it("handles files with a byte order mark", () => {
        const entry = parseMatlabEntry("\uFEFFfunction runThing()\nend", "runThing.m");

        assert.equal(entry.kind, "function");
        assert.equal(entry.functionName, "runThing");
    });

    it("treats empty files as scripts", () => {
        const entry = parseMatlabEntry("", "emptyFile.m");

        assert.equal(entry.kind, "script");
        assert.equal(entry.functionName, "emptyFile");
    });
});

describe("buildInvocation", () => {
    it("builds a desktop invocation for a script", () => {
        const filePath = "C:\\Work Folder\\John's Scripts\\demo.m";
        const entry = parseMatlabEntry("disp('ok');", filePath);
        const invocation = buildInvocation([entry], {
            launchMode: "desktop",
            stopOnError: true,
            addFileDirectoryToPath: true
        });

        assert.deepEqual(invocation.args.slice(0, 1), ["-r"]);
        assert.equal(invocation.cwd, path.dirname(filePath));
        assert.match(invocation.command, /try/);
        assert.ok(invocation.command.includes(`cd(${matlabString(path.dirname(filePath))});`));
        assert.ok(invocation.command.includes(`run(${matlabString(filePath)});`));
        assert.ok(invocation.command.includes("rethrow(ME);"));
    });

    it("builds a batch invocation for multiple entries", () => {
        const entries = [
            parseMatlabEntry("disp('a');", "C:\\work\\a.m"),
            parseMatlabEntry("function b()\nend", "C:\\work\\b.m")
        ];
        const invocation = buildInvocation(entries, {
            launchMode: "batch",
            stopOnError: false,
            addFileDirectoryToPath: false
        });

        assert.deepEqual(invocation.args.slice(0, 1), ["-batch"]);
        assert.ok(invocation.command.includes("run("));
        assert.ok(invocation.command.includes("feval('b');"));
        assert.ok(!invocation.command.includes("addpath("));
        assert.ok(!invocation.command.includes("rethrow(ME);"));
    });
});
