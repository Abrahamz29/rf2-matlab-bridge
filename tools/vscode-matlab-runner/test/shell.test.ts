import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { formatShellCommand } from "../src/shell";

describe("formatShellCommand", () => {
    it("quotes executable and arguments for the host shell", () => {
        const command = formatShellCommand("C:\\Program Files\\MATLAB\\bin\\matlab.exe", [
            "-r",
            "run('C:\\Work Folder\\John''s Scripts\\demo.m');"
        ]);

        if (process.platform === "win32") {
            assert.equal(
                command,
                "& 'C:\\Program Files\\MATLAB\\bin\\matlab.exe' '-r' 'run(''C:\\Work Folder\\John''''s Scripts\\demo.m'');'"
            );
        } else {
            assert.equal(
                command,
                "'C:\\Program Files\\MATLAB\\bin\\matlab.exe' '-r' 'run('\\''C:\\Work Folder\\John'\\''\\'''\\''s Scripts\\demo.m'\\'');'"
            );
        }
    });
});
