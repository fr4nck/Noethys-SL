param(
    [switch]$Force,
    [string]$Confirmation
)
$ErrorActionPreference = 'Stop'
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $Here 'guard.ps1')
$Project = 'noethys-sl-noe032'
if (-not $Force -or $Confirmation -cne 'SUPPRIMER-noethys-sl-noe032') {
    throw 'Destruction refusee : exiger -Force -Confirmation SUPPRIMER-noethys-sl-noe032.'
}
# Uniquement le projet et son volume nommes dans dev/db/compose.yml.
# Ne PAS ajouter --remove-orphans, ni toucher aux autres projets Docker.
& docker compose --project-name $Project --env-file $EnvFile -f $ComposeFile down --volumes
if ($LASTEXITCODE -ne 0) { throw 'Echec de remise a zero du conteneur de recette.' }
& (Join-Path $Here 'start.ps1')
