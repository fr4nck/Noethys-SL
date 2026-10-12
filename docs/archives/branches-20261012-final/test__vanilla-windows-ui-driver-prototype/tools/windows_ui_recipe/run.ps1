param(
    [Parameter(Mandatory=$true)][string]$Exe,
    [Parameter(Mandatory=$true)][string]$ProfileRoot,
    [Parameter(Mandatory=$true)][string]$ExpectedDbHost,
    [Parameter(Mandatory=$true)][string]$ExpectedDbName,
    [int]$Repeat = 5,
    [int]$Timeout = 20,
    [string]$Artifacts = ".\artifacts\noethys-ui"
)

$ErrorActionPreference = "Stop"
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

python (Join-Path $scriptRoot "scenario_minimal.py") `
    --exe $Exe `
    --profile-root $ProfileRoot `
    --expected-db-host $ExpectedDbHost `
    --expected-db-name $ExpectedDbName `
    --repeat $Repeat `
    --timeout $Timeout `
    --artifacts $Artifacts
exit $LASTEXITCODE
