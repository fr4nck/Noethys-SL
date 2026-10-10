param()

$ErrorActionPreference = 'Stop'
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$ComposeFile = Join-Path $Here 'compose.yml'
$EnvFile = Join-Path $Here '.env'
$StartScript = Join-Path $Here 'start.ps1'
$ImportScript = Join-Path $Here 'import.ps1'
$DumpPath = Join-Path ([System.IO.Path]::GetTempPath()) ("noethys-noe032-{0}.sql" -f [guid]::NewGuid().ToString("N"))

if (-not (Test-Path $EnvFile)) { throw "Configuration absente : $EnvFile" }

& $StartScript

try {
    $FixtureScript = @'
set -eu
case "$MYSQL_DATABASE" in
  ""|*[!A-Za-z0-9_]*)
    echo "MYSQL_DATABASE invalide pour le smoke test." >&2
    exit 42
    ;;
esac

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
mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -e "DROP DATABASE IF EXISTS `$MYSQL_DATABASE`; CREATE DATABASE `$MYSQL_DATABASE` CHARACTER SET utf8 COLLATE utf8_general_ci;"
'@

    $FixtureScript | & docker compose --env-file $EnvFile -f $ComposeFile exec -T mysql55 sh
    if ($LASTEXITCODE -ne 0) { throw 'Création du jeu synthétique en échec.' }

    & docker cp "noethys-mysql55:/tmp/noethys-fixture.sql" $DumpPath
    if ($LASTEXITCODE -ne 0) { throw 'Extraction du dump synthétique en échec.' }

    & $ImportScript -DumpPath $DumpPath -SyntheticData

    $VerifyScript = @'
set -eu
rows="$(mysql -uroot -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE" -Nse 'SELECT COUNT(*) FROM fixture_data;')"
views="$(mysql -uroot -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE" -Nse "SELECT COUNT(*) FROM information_schema.views WHERE table_schema=DATABASE() AND table_name='fixture_view';")"
if [ "$rows" != "2" ]; then
    echo "Postcondition lignes invalide : $rows" >&2
    exit 43
fi
if [ "$views" != "1" ]; then
    echo "Postcondition vue invalide : $views" >&2
    exit 44
fi
printf 'NOE-032 MYSQL SYNTHETIC SMOKE: PASS (%s rows, %s view)\n' "$rows" "$views"
'@

    $VerifyScript | & docker compose --env-file $EnvFile -f $ComposeFile exec -T mysql55 sh
    if ($LASTEXITCODE -ne 0) { throw 'Postconditions du smoke test en échec.' }
}
finally {
    if (Test-Path $DumpPath) {
        Remove-Item -Force $DumpPath
    }
    & docker compose --env-file $EnvFile -f $ComposeFile exec -T mysql55 sh -c 'rm -f /tmp/noethys-fixture.sql; mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -e "DROP DATABASE IF EXISTS noethys_fixture_source;"' 2>$null | Out-Null
}
