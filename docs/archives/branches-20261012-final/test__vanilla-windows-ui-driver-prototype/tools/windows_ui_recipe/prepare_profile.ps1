param(
    [Parameter(Mandatory=$true)][string]$ProfileRoot,
    [Parameter(Mandatory=$true)][string]$RecipeConfig
)

$ErrorActionPreference = "Stop"
$profile = [System.IO.Path]::GetFullPath($ProfileRoot)
$configSource = [System.IO.Path]::GetFullPath($RecipeConfig)
if (-not (Test-Path -LiteralPath $configSource -PathType Leaf)) {
    throw "Config.json de recette introuvable : $configSource"
}

$roamingNoethys = Join-Path $profile "Roaming\noethys"
$local = Join-Path $profile "Local"
New-Item -ItemType Directory -Path $roamingNoethys,$local -Force | Out-Null
Copy-Item -LiteralPath $configSource -Destination (Join-Path $roamingNoethys "Config.json") -Force
Set-Content -LiteralPath (Join-Path $profile "NOETHYS_UI_RECIPE_PROFILE.txt") -Value "NOETHYS_UI_RECIPE_PROFILE=1" -Encoding UTF8 -NoNewline

Write-Host "Profil de recette préparé : $profile"
Write-Host "Le pilote vérifiera encore l'hôte loopback et le nom exact de la base Docker avant tout lancement."
