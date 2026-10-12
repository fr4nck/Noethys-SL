# Demarrage uniquement du conteneur de recette Noe-032.
$ErrorActionPreference = 'Stop'
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $Here 'guard.ps1')
$Project = 'noethys-sl-noe032'
$Container = 'noethys-sl-noe032-mysql55'

& docker compose --project-name $Project --env-file $EnvFile -f $ComposeFile up -d mysql55
if ($LASTEXITCODE -ne 0) { throw 'Echec du demarrage Docker Compose.' }
$status = ''
for ($i = 0; $i -lt 75; $i++) {
    $status = (& docker inspect --format '{{.State.Health.Status}}' $Container 2>$null)
    if ($status -eq 'healthy' -or $status -eq 'unhealthy') { break }
    Start-Sleep -Seconds 2
}
if ($status -ne 'healthy') { throw "MySQL de recette non sain : $status." }
$version = & docker compose --project-name $Project --env-file $EnvFile -f $ComposeFile exec -T mysql55 sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -Nse "SELECT VERSION();"'
if ($LASTEXITCODE -ne 0) { throw 'MySQL ne repond pas a la verification de version.' }
$binding = & docker port $Container 3306/tcp
if ($LASTEXITCODE -ne 0 -or (($binding | Out-String).Trim() -ne '127.0.0.1:3308')) {
    throw 'MySQL de recette expose sur une interface ou un port inattendu.'
}
Write-Host "Bac a sable Noe-032 pret : $version - 127.0.0.1:3308" -ForegroundColor Green
