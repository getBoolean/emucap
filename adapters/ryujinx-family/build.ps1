param([Parameter(ValueFromRemainingArguments=$true)][string[]]$BuildArguments)
$ErrorActionPreference = 'Stop'
py -3.12 "$PSScriptRoot/build.py" @BuildArguments
exit $LASTEXITCODE
