param(
    [Parameter(Mandatory = $true)]
    [string]$DumpPath,

    [switch]$SyntheticData
)

$ErrorActionPreference = 'Stop'
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$ComposeFile = Join-Path $Here 'compose.yml'
$EnvFile = Join-Path $Here '.env'
$StartScript = Join-Path $Here 'start.ps1'

if (-not $SyntheticData) {
    throw "Import refusé : ce lot Noe-032 est réservé aux données 100 % synthétiques. Relancer avec -SyntheticData."
}

$DumpPath = (Resolve-Path $DumpPath).Path
if (-not (Test-Path $DumpPath -PathType Leaf)) { throw "Dump introuvable : $DumpPath" }
if (-not (Test-Path $EnvFile)) { throw "Configuration absente : $EnvFile" }

& $StartScript
if ($LASTEXITCODE -ne 0) { throw 'Impossible de démarrer la base de développement.' }

$ContainerDump = '/tmp/noethys-import.sql'
& docker cp $DumpPath "noethys-mysql55:$ContainerDump"
if ($LASTEXITCODE -ne 0) { throw 'Échec de docker cp.' }

try {
    Write-Host 'Import SQL synthétique en cours...' -ForegroundColor Cyan

    # Un dump Noethys créé avec mysqldump --databases contient CREATE DATABASE et USE.
    # On accepte au plus une base source, puis on retire ces directives afin que
    # toutes les instructions soient exécutées dans MYSQL_DATABASE, la base jetable.
    $ImportScript = @'
set -eu
schemas="$(sed -n 's/^USE `\([^`]*\)`;$/\1/p' /tmp/noethys-import.sql | sort -u)"
count="$(printf '%s\n' "$schemas" | sed '/^$/d' | wc -l | tr -d ' ')"
if [ "$count" -gt 1 ]; then
    echo "Dump multi-base refusé : $count bases source détectées." >&2
    exit 41
fi
sed '/^CREATE DATABASE /d;/^USE `/d' /tmp/noethys-import.sql     | mysql -uroot -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE"
'@

    $ImportScript | & docker compose --env-file $EnvFile -f $ComposeFile exec -T mysql55 sh
    if ($LASTEXITCODE -ne 0) { throw 'Import SQL en échec.' }

    $count = & docker compose --env-file $EnvFile -f $ComposeFile exec -T mysql55 sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE" -Nse "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE();"'
    if ($LASTEXITCODE -ne 0) { throw 'Import terminé mais contrôle final impossible.' }

    $countText = ($count | Out-String).Trim()
    $countValue = 0
    if (-not [int]::TryParse($countText, [ref]$countValue) -or $countValue -le 0) {
        throw "Import terminé sans objet SQL détecté dans la base cible ($countText)."
    }

    Write-Host "Import terminé : $countValue objets SQL détectés dans la base cible." -ForegroundColor Green
}
finally {
    & docker compose --env-file $EnvFile -f $ComposeFile exec -T mysql55 rm -f $ContainerDump | Out-Null
}
