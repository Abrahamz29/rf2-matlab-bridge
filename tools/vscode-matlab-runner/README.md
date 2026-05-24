# MATLAB Run Selected

Local VS Code extension that adds this command to `.m` files:

```text
MATLAB: Run Selected MATLAB File
```

The command starts MATLAB with `-r` from a visible VS Code terminal. MATLAB
opens normally with its desktop UI; it is not launched with `-batch`.

## Install

From this extension folder:

```powershell
.\install.ps1
```

Then reload VS Code with `Developer: Reload Window`.

## Behavior

- Scripts are launched with `run('selected-file.m')`.
- Function files are launched with `feval('functionName')`.
- The selected file's folder is added to the MATLAB path before execution.
- Configure the executable with `matlabRunSelected.executable` if `matlab` is
  not on `PATH`.
