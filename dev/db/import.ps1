param(
    [Parameter(Mandatory = $true)]
    [string]$DumpPath,
    [switch]$SyntheticData
)
$ErrorActionPreference = 'Stop'
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $Here 'guard.ps1')

if (-not $SyntheticData) {
    throw 'Import refuse : seul le jeu fixture Noe-032 synthetique est accepte.'
}
$DumpPath = (Resolve-Path -LiteralPath $DumpPath -ErrorAction Stop).Path
if (-not (Test-Path -LiteralPath $DumpPath -PathType Leaf)) {
    throw 'Fichier SQL manquant.'
}
# Ce premier lot NE propose PAS d'import generique de sauvegardes Noethys.
# Whitelist stricte : deux objets connus du smoke test, base source fixe.
$sql = [System.IO.File]::ReadAllText($DumpPath)
if ($sql.Length -gt 1048576) {
    throw 'Dump trop volumineux pour le petit jeu de recette synthetique.'
}
$schemas = [regex]::Matches($sql, '(?im)^\s*USE\s+`([^`]+)`\s*;')
# mysqldump --databases repete USE avant la definition finale des vues :
# exiger une base unique, pas une instruction USE unique.
$schemaNames = @($schemas | ForEach-Object { $_.Groups[1].Value } | Sort-Object -Unique -CaseSensitive)
if ($schemas.Count -lt 1 -or $schemaNames.Count -ne 1 -or $schemaNames[0] -cne 'noethys_fixture_source') {
    throw 'Dump refuse : base source de recette non unique ou inattendue.'
}
$tables = [regex]::Matches($sql, '(?im)^\s*CREATE TABLE\s+`([^`]+)`')
if ($tables.Count -lt 1) { throw 'Dump sans table de fixture.' }
$names = @($tables | ForEach-Object { $_.Groups[1].Value })
if ('fixture_data' -cnotin $names -or @($names | Where-Object { $_ -cnotin @('fixture_data', 'fixture_view') }).Count -gt 0) {
    throw 'Dump refuse : objets non prevus par la fixture.'
}
if ($sql -notmatch 'fixture_view' -or $sql -notmatch 'fixture_data') {
    throw 'Dump refuse : objets de la fixture incomplets.'
}
# Chaque CREATE DATABASE/SCHEMA, ou qu'il soit, doit nommer la base source ;
# l'ancien motif revenait sur le backtick fermant et refusait tout dump.
$createdDatabases = @([regex]::Matches($sql,
    '(?i)\bCREATE\s+(?:DATABASE|SCHEMA)\s+(?:/\*!\d+\s*IF\s+NOT\s+EXISTS\s*\*/\s*|IF\s+NOT\s+EXISTS\s+)?(`[^`]*`|[^\s;]*)') |
    ForEach-Object { $_.Groups[1].Value.Trim('`') })
if ($sql -match '(?im)^\s*(DROP|ALTER)\s+DATABASE\b' -or
    $sql -match '(?i)\b(INTO\s+OUTFILE|LOAD\s+DATA|CREATE\s+USER|GRANT\s+|INSTALL\s+PLUGIN)\b' -or
    @($createdDatabases | Where-Object { $_ -cne 'noethys_fixture_source' }).Count -gt 0) {
    throw 'Dump refuse : instruction SQL non autorisee.'
}

$Project = 'noethys-sl-noe032'
$Container = 'noethys-sl-noe032-mysql55'
& (Join-Path $Here 'start.ps1')
if ($LASTEXITCODE -ne 0) { throw 'Bac a sable non disponible.' }

$ContainerDump = '/tmp/noethys-fixture-import.sql'
& docker cp $DumpPath "${Container}:$ContainerDump"
if ($LASTEXITCODE -ne 0) { throw 'Copie de la fixture dans Docker impossible.' }
try {
    $Script = @'
set -eu
test "$MYSQL_DATABASE" = noethys_dev
sed '/^CREATE DATABASE /d; /^USE `/d' /tmp/noethys-fixture-import.sql |
  mysql -uroot -p"$MYSQL_ROOT_PASSWORD" noethys_dev
'@
    # Checkout Windows (CRLF) : retirer les \r avant sh, sinon 'set -eu' echoue.
    $Script | & docker compose --project-name $Project --env-file $EnvFile -f $ComposeFile exec -T mysql55 sh -c 'tr -d ''\r'' | sh'
    if ($LASTEXITCODE -ne 0) { throw 'Import de la fixture echoue.' }
    $row = & docker compose --project-name $Project --env-file $EnvFile -f $ComposeFile exec -T mysql55 sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" noethys_dev -Nse "SELECT COUNT(*) FROM fixture_data;"'
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace(($row | Out-String))) {
        throw 'Controle SQL post-import en echec.'
    }
    Write-Host "Fixture de recette importee : $row ligne(s)." -ForegroundColor Green
}
finally {
    & docker compose --project-name $Project --env-file $EnvFile -f $ComposeFile exec -T mysql55 rm -f $ContainerDump | Out-Null
}
