# MATLAB File Runner

Portable VS Code extension for running selected MATLAB `.m` files from the
Explorer or the active editor.

## Commands

```text
MATLAB: Run Selected File(s)
MATLAB: Run Selected File(s) with Desktop
MATLAB: Run Selected File(s) Headless
MATLAB: Run Current File
MATLAB: Run Current File with Desktop
MATLAB: Run Current File Headless
```

## Build

```powershell
npm install
npm run compile
npm test
npm run package
```

The package command creates:

```text
matlab-file-runner-0.2.1.vsix
```

## Install

From this extension folder:

```powershell
.\install.ps1
```

Or install the package directly:

```powershell
code --install-extension .\matlab-file-runner-0.2.1.vsix --force
```

## Settings

- `matlabFileRunner.executable`: MATLAB executable or full path to `matlab.exe`.
- `matlabFileRunner.launchMode`: `desktop` or `batch` for the generic commands.
- `matlabFileRunner.terminalMode`: `visible` or `detached`.
- `matlabFileRunner.stopOnError`: stop the selected sequence after an error.
- `matlabFileRunner.addFileDirectoryToPath`: add each file directory to the MATLAB path before execution.

## Behavior

- Scripts are launched with `run(filePath)`.
- Function files are launched with `feval(functionName)`.
- Multiple selected `.m` files run sequentially in one MATLAB invocation.
- Desktop menu entries start MATLAB with `-r`.
- Headless menu entries start MATLAB with `-batch`.
- Non-MATLAB files are ignored when multiple files are selected.
- Errors are written with MATLAB's extended error report.
