export function formatShellCommand(executable: string, args: string[]): string {
    if (process.platform === "win32") {
        return `& ${quotePowerShell(executable)} ${args.map(quotePowerShell).join(" ")}`;
    }

    return [quoteShell(executable), ...args.map(quoteShell)].join(" ");
}

function quotePowerShell(value: string): string {
    return `'${String(value).replace(/'/g, "''")}'`;
}

function quoteShell(value: string): string {
    return `'${String(value).replace(/'/g, "'\\''")}'`;
}
