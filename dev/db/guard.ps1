# Noe-032 : verrouillage du bac a sable MySQL avant toute commande Docker.
# Dot-sourcer ce fichier depuis start.ps1, reset.ps1, smoke.ps1 et import.ps1.
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$EnvFile = Join-Path $Here '.env'
$ComposeFile = Join-Path $Here 'compose.yml'
if (-not (Test-Path -LiteralPath $EnvFile -PathType Leaf)) {
    throw "Configuration absente : copier dev/db/.env.example vers dev/db/.env."
}
$config = @{}
foreach ($line in (Get-Content -LiteralPath $EnvFile)) {
    if ($line -match '^\s*([A-Z][A-Z0-9_]*)=(.*)$') {
        $config[$Matches[1]] = $Matches[2].Trim()
    }
}
if ($config['NOETHYS_DB_NAME'] -cne 'noethys_dev' -or $config['NOETHYS_DB_PORT'] -cne '3308') {
    throw 'Bac a sable refuse : seuls NOETHYS_DB_NAME=noethys_dev et NOETHYS_DB_PORT=3308 sont autorises.'
}
foreach ($name in @('NOETHYS_DB_ROOT_PASSWORD', 'NOETHYS_DB_PASSWORD')) {
    if ([string]::IsNullOrWhiteSpace($config[$name]) -or $config[$name] -match '^CHANGE_ME') {
        throw "Mot de passe de recette non renseigne : $name."
    }
}
if ($config['NOETHYS_DB_USER'] -cne 'noethys') {
    throw 'Utilisateur de recette inattendu.'
}
$knownImage = 'mysql:5.5.62@sha256:d404d78aa797c87c255e5ae2beb5d8d0e4d095f930b1f20dc208eaa957477b74'
if ($config.ContainsKey('NOETHYS_MYSQL55_IMAGE') -and
    $config['NOETHYS_MYSQL55_IMAGE'] -cnotin @($knownImage, 'noethys-mysql55:converted')) {
    throw 'Image MySQL non approuvee pour la recette.'
}
$processImage = [Environment]::GetEnvironmentVariable('NOETHYS_MYSQL55_IMAGE', 'Process')
if (-not [string]::IsNullOrEmpty($processImage) -and
    $processImage -cnotin @($knownImage, 'noethys-mysql55:converted')) {
    throw 'Image MySQL du processus non approuvee.'
}
foreach ($name in @('NOETHYS_DB_NAME', 'NOETHYS_DB_PORT', 'NOETHYS_DB_USER',
                    'NOETHYS_DB_ROOT_PASSWORD', 'NOETHYS_DB_PASSWORD', 'NOETHYS_MYSQL55_IMAGE')) {
    $override = [Environment]::GetEnvironmentVariable($name, 'Process')
    if ($null -ne $override -and $config.ContainsKey($name) -and $override -cne $config[$name]) {
        throw "Variable de processus differente du bac a sable : $name."
    }
}
$env:NOETHYS_DB_NAME = 'noethys_dev'
$env:NOETHYS_DB_PORT = '3308'
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw 'Docker absent.'
}
# Docker CLI peut ignorer le contexte selectionne lorsque DOCKER_HOST ou
# DOCKER_CONTEXT est impose par l'environnement ; refuser toute redirection.
foreach ($name in @('DOCKER_HOST', 'DOCKER_CONTEXT', 'DOCKER_TLS_VERIFY', 'DOCKER_CERT_PATH')) {
    $value = [Environment]::GetEnvironmentVariable($name, 'Process')
    if (-not [string]::IsNullOrWhiteSpace($value)) {
        throw "Bac a sable refuse : supprimer la variable Docker $name avant la recette."
    }
}
$engine = (& docker context inspect --format '{{.Endpoints.docker.Host}}' 2>$null | Select-Object -First 1)
if ($LASTEXITCODE -ne 0 -or
    $engine -notmatch '^(npipe://|unix://|tcp://(127\.0\.0\.1|localhost)(:\d+)?$)') {
    throw "Contexte Docker distant ou non reconnu : $engine."
}
