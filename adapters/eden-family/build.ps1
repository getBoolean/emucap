param([Parameter(ValueFromRemainingArguments = $true)][string[]]$BuildArgs)
$ErrorActionPreference = 'Stop'
& py -3.12 (Join-Path $PSScriptRoot 'build.py') @BuildArgs
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
