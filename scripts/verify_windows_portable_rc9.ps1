# RC9 Windows: smoke the extracted executable and the real configuration API.
# Runner-only scratch paths; never point this script at a production profile.
$ErrorActionPreference = 'Stop'
$zip = Get-ChildItem 'windows-output' -Filter '*-Windows-portable.zip' | Select-Object -First 1
if ($null -eq $zip) { throw 'ZIP portable absent' }
$extrait = Join-Path $env:RUNNER_TEMP 'rc9-portable-extracted'
Expand-Archive -LiteralPath $zip.FullName -DestinationPath $extrait -Force
$portable = Join-Path $extrait 'Portable'
$config = Join-Path $portable 'Config.json'
$customize = Join-Path $portable 'Customize.ini'
$journal = Join-Path $portable 'journal.log'
if (-not (Test-Path (Join-Path $portable 'README.txt') -PathType Leaf)) {
    throw 'Marqueur Portable/README.txt absent du ZIP extrait'
}
$profileRoot = Join-Path $env:RUNNER_TEMP 'rc9-virgin-windows-profile'
$env:APPDATA = Join-Path $profileRoot 'Roaming'
$env:LOCALAPPDATA = Join-Path $profileRoot 'Local'
New-Item -ItemType Directory -Path $env:APPDATA, $env:LOCALAPPDATA -Force | Out-Null

function Assert-NoExternalProfile {
    foreach ($root in @($env:APPDATA, $env:LOCALAPPDATA)) {
        if (Test-Path (Join-Path $root 'noethys')) {
            throw "Profil Noethys cree hors Portable/ dans $root"
        }
    }
}

function Show-PortableDiagnostics {
    param([string] $phase, $process)
    Write-Host "Diagnostic $phase / Noethys.exe : pid=$($process.Id), exited=$($process.HasExited)"
    if ($process.HasExited) { Write-Host "Code de sortie : $($process.ExitCode)" }
    foreach ($root in @($portable, $env:APPDATA, $env:LOCALAPPDATA)) {
        Write-Host "Inventaire de $root :"
        if (Test-Path $root) {
            Get-ChildItem -LiteralPath $root -Recurse -Force -ErrorAction Continue |
                Select-Object -First 35 -ExpandProperty FullName | ForEach-Object { Write-Host $_ }
        }
    }
    if (Test-Path $journal -PathType Leaf) {
        Write-Host 'Fin du journal portable :'
        Get-Content -LiteralPath $journal -Tail 35 -ErrorAction Continue
    }
}

function Start-PortableAndCheck {
    param([string] $phase)
    $process = Start-Process -FilePath (Join-Path $extrait 'Noethys.exe') -WorkingDirectory $extrait -WindowStyle Hidden -PassThru
    $debut = [DateTime]::UtcNow
    $limite = $debut.AddSeconds(120)
    $pret = $false
    try {
        while ([DateTime]::UtcNow -lt $limite) {
            $dossiers = @('Temp', 'Updates', 'Sync', 'Lang', 'Extensions')
            $absents = @($dossiers | Where-Object { -not (Test-Path (Join-Path $portable $_) -PathType Container) })
            $profilPret = (Test-Path $config -PathType Leaf) -and (Test-Path $customize -PathType Leaf) -and ($absents.Count -eq 0)
            $secondLancement = $phase -eq 'second'
            $secondeInitialisation = ([DateTime]::UtcNow - $debut).TotalSeconds -ge 10
            if ($profilPret -and (-not $secondLancement -or $secondeInitialisation)) {
                if ($process.HasExited) { break }
                $pret = $true
                break
            }
            if ($process.HasExited) { break }
            Start-Sleep -Seconds 2
        }
        if (-not $pret) {
            Show-PortableDiagnostics -phase $phase -process $process
            throw "Noethys.exe n'a pas initialise son profil portable ($phase) avant sortie ou timeout"
        }
        Write-Host "Profil portable initialise ($phase) apres $([math]::Round(([DateTime]::UtcNow - $debut).TotalSeconds, 1)) secondes"
    }
    finally {
        if (-not $process.HasExited) { Stop-Process -Id $process.Id -Force }
        Assert-NoExternalProfile
    }
}

# The first boot must itself create Config.json, Customize.ini, and runtime dirs.
Start-PortableAndCheck -phase 'first'
$cfg = Get-Content -LiteralPath $config -Raw -Encoding UTF8 | ConvertFrom-Json
if ($null -eq $cfg -or -not ($cfg.PSObject.Properties.Name -contains 'nomFichier')) {
    throw 'Config.json portable absent ou non conforme apres premier lancement'
}

# Persist a benign setting via the actual UTILS_Config API, not a fake file.
# Change only the temporary, extracted ZIP profile.
$env:NOETHYS_RC9_SMOKE_ROOT = $extrait
$env:NOETHYS_RC9_SMOKE_VALUE = [string]$env:GITHUB_RUN_ID
python -c "import os,sys;sys.path.insert(0,'noethys');import Chemins;Chemins.REP_COURANT=os.environ['NOETHYS_RC9_SMOKE_ROOT'];from Utils import UTILS_Config;c=UTILS_Config.FichierConfig();c.SetItemConfig('rc9_portable_smoke',os.environ['NOETHYS_RC9_SMOKE_VALUE']);assert UTILS_Config.FichierConfig().GetItemConfig('rc9_portable_smoke')==os.environ['NOETHYS_RC9_SMOKE_VALUE']"
if ($LASTEXITCODE -ne 0) { throw 'Echec de sauvegarde par UTILS_Config' }
Assert-NoExternalProfile

Start-PortableAndCheck -phase 'second'
$relu = Get-Content -LiteralPath $config -Raw -Encoding UTF8 | ConvertFrom-Json
if ($relu.rc9_portable_smoke -ne $env:NOETHYS_RC9_SMOKE_VALUE) {
    throw 'Le parametre modifie a disparu apres le second demarrage'
}
Assert-NoExternalProfile
Write-Host 'PASS: ZIP extrait, deux demarrages, vraie sauvegarde Config.json, persistance, aucun profil Windows externe'
