param(
    [string]$Python = 'py',
    [Parameter(ValueFromRemainingArguments = $true)][string[]]$BuildArguments
)
$ErrorActionPreference = 'Stop'
if ($Python -eq 'py') {
    & $Python -3.12 "$PSScriptRoot/build.py" @BuildArguments
} else {
    & $Python "$PSScriptRoot/build.py" @BuildArguments
}
exit $LASTEXITCODE
