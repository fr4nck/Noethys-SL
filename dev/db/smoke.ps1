# Recette exclusivement synthetique : aucune entree de fichier utilisateur.
$ErrorActionPreference = 'Stop'
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $Here 'guard.ps1')
$Project = 'noethys-sl-noe032'
$Container = 'noethys-sl-noe032-mysql55'
$DumpPath = Join-Path ([System.IO.Path]::GetTempPath()) ("noethys-fixture-{0}.sql" -f [guid]::NewGuid().ToString('N'))
& (Join-Path $Here 'start.ps1')
if ($LASTEXITCODE -ne 0) { throw 'Bac a sable non disponible.' }
try {
    $FixtureScript = @'
set -eu
test "$MYSQL_DATABASE" = noethys_dev
mysql -uroot -p"$MYSQL_ROOT_PASSWORD" <<'SQL'
DROP DATABASE IF EXISTS noethys_fixture_source;
CREATE DATABASE noethys_fixture_source CHARACTER SET utf8 COLLATE utf8_general_ci;
USE noethys_fixture_source;
CREATE TABLE fixture_data (
    id INT NOT NULL PRIMARY KEY,
    label VARCHAR(64) NOT NULL
) ENGINE=InnoDB;
INSERT INTO fixture_data (id, label) VALUES (1, 'alpha'), (2, 'beta');
CREATE VIEW fixture_view AS SELECT id, label FROM fixture_data;
SQL
mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" --single-transaction --opt --databases noethys_fixture_source > /tmp/noethys-fixture.sql
# Destination fixe et jetable. Aucun nom de base issu d'un dump utilisateur.
mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -e 'DROP DATABASE IF EXISTS noethys_dev; CREATE DATABASE noethys_dev CHARACTER SET utf8 COLLATE utf8_general_ci;'
'@
    # Checkout Windows (CRLF) : retirer les \r avant sh, sinon 'set -eu' echoue.
    $FixtureScript | & docker compose --project-name $Project --env-file $EnvFile -f $ComposeFile exec -T mysql55 sh -c 'tr -d ''\r'' | sh'
    if ($LASTEXITCODE -ne 0) { throw 'Creation de la fixture en echec.' }
    & docker cp "${Container}:/tmp/noethys-fixture.sql" $DumpPath
    if ($LASTEXITCODE -ne 0) { throw 'Extraction de la fixture en echec.' }
    & (Join-Path $Here 'import.ps1') -DumpPath $DumpPath -SyntheticData
    $VerifyScript = @'
set -eu
rows="$(mysql -uroot -p"$MYSQL_ROOT_PASSWORD" noethys_dev -Nse 'SELECT COUNT(*) FROM fixture_data;')"
views="$(mysql -uroot -p"$MYSQL_ROOT_PASSWORD" noethys_dev -Nse "SELECT COUNT(*) FROM information_schema.views WHERE table_schema=DATABASE() AND table_name='fixture_view';")"
test "$rows" = 2
test "$views" = 1
printf 'NOE-032 SYNTHETIC MYSQL: PASS (%s rows; %s view)\n' "$rows" "$views"
'@
    $VerifyScript | & docker compose --project-name $Project --env-file $EnvFile -f $ComposeFile exec -T mysql55 sh -c 'tr -d ''\r'' | sh'
    if ($LASTEXITCODE -ne 0) { throw 'Postconditions synthetiques en echec.' }
}
finally {
    if (Test-Path -LiteralPath $DumpPath) { Remove-Item -LiteralPath $DumpPath -Force }
    & docker compose --project-name $Project --env-file $EnvFile -f $ComposeFile exec -T mysql55 sh -c 'rm -f /tmp/noethys-fixture.sql; mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -e "DROP DATABASE IF EXISTS noethys_fixture_source;"' 2>$null | Out-Null
}
