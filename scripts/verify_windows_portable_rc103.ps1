# RC102 Windows: smoke the extracted executable and the real configuration API.
# Runner-only scratch paths; never point this script at a production profile.
#
# Diagnostic : chaque lancement écrit un journal NOETHYS_DIAGNOSTIC_DEMARRAGE
# (imports, étapes, exceptions invisibles, piles périodiques) dans
# $env:RUNNER_TEMP/diagnostics-demarrage, publié comme artefact par le
# workflow. En cas d'échec, les fenêtres du processus (titres et textes,
# y compris une boîte d'erreur masquée) sont inventoriées.
$ErrorActionPreference = 'Stop'
$zip = Get-ChildItem 'windows-output' -Filter '*-Windows-portable.zip' | Select-Object -First 1
if ($null -eq $zip) { throw 'ZIP portable absent' }
$extrait = Join-Path $env:RUNNER_TEMP 'rc103-portable-extracted'
Expand-Archive -LiteralPath $zip.FullName -DestinationPath $extrait -Force
$portable = Join-Path $extrait 'Portable'
$config = Join-Path $portable 'Config.json'
$customize = Join-Path $portable 'Customize.ini'
$journal = Join-Path $portable 'journal.log'
$diagnostics = Join-Path $env:RUNNER_TEMP 'diagnostics-demarrage'
New-Item -ItemType Directory -Path $diagnostics -Force | Out-Null
if (-not (Test-Path (Join-Path $portable 'README.txt') -PathType Leaf)) {
    throw 'Marqueur Portable/README.txt absent du ZIP extrait'
}
$profileRoot = Join-Path $env:RUNNER_TEMP 'rc103-virgin-windows-profile'
$env:APPDATA = Join-Path $profileRoot 'Roaming'
$env:LOCALAPPDATA = Join-Path $profileRoot 'Local'
New-Item -ItemType Directory -Path $env:APPDATA, $env:LOCALAPPDATA -Force | Out-Null

# appdirs résout le profil Windows par l'API système (SHGetFolderPath) et
# ignore %APPDATA% : surveiller aussi les dossiers réels du compte du runner.
$dossiersReels = @(@(
    [Environment]::GetFolderPath('ApplicationData'),
    [Environment]::GetFolderPath('LocalApplicationData'),
    [Environment]::GetFolderPath('CommonApplicationData')
) | Where-Object { $_ } | ForEach-Object { Join-Path $_ 'noethys' })

function Get-ProfilsExternes {
    $etat = @{}
    foreach ($racine in @((Join-Path $env:APPDATA 'noethys'), (Join-Path $env:LOCALAPPDATA 'noethys')) + $dossiersReels) {
        if (Test-Path $racine) {
            $etat[$racine] = @(Get-ChildItem -LiteralPath $racine -Recurse -Force -File -ErrorAction SilentlyContinue |
                ForEach-Object { "$($_.FullName)|$($_.Length)|$($_.LastWriteTimeUtc.Ticks)" }) -join "`n"
        }
    }
    return $etat
}
$profilsAvant = Get-ProfilsExternes

function Assert-NoExternalProfile {
    $apres = Get-ProfilsExternes
    foreach ($racine in $apres.Keys) {
        if (-not $profilsAvant.ContainsKey($racine)) { throw "Profil Noethys cree hors Portable/ : $racine" }
        if ($profilsAvant[$racine] -ne $apres[$racine]) { throw "Profil Noethys modifie hors Portable/ : $racine" }
    }
}

Add-Type @"
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;
public static class FenetresProcessus {
    delegate bool EnumProc(IntPtr hWnd, IntPtr lParam);
    [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc f, IntPtr p);
    [DllImport("user32.dll")] static extern bool EnumChildWindows(IntPtr h, EnumProc f, IntPtr p);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetClassName(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
    static string Texte(IntPtr h) { var s = new StringBuilder(4096); GetWindowText(h, s, s.Capacity); return s.ToString(); }
    static string Classe(IntPtr h) { var s = new StringBuilder(256); GetClassName(h, s, s.Capacity); return s.ToString(); }
    public static List<string> Lister(uint cible) {
        var lignes = new List<string>();
        EnumWindows((h, p) => {
            uint pid; GetWindowThreadProcessId(h, out pid);
            if (pid == cible) {
                lignes.Add(string.Format("FENETRE [{0}] visible={1} titre={2}", Classe(h), IsWindowVisible(h), Texte(h)));
                EnumChildWindows(h, (c, q) => {
                    string t = Texte(c);
                    if (t.Length > 0) lignes.Add(string.Format("  [{0}] {1}", Classe(c), t));
                    return true;
                }, IntPtr.Zero);
            }
            return true;
        }, IntPtr.Zero);
        return lignes;
    }
}
"@

function Show-PortableDiagnostics {
    param([string] $phase, $process, [string] $diagnostic)
    Write-Host "Diagnostic $phase / Noethys.exe : pid=$($process.Id), exited=$($process.HasExited)"
    if ($process.HasExited) { Write-Host "Code de sortie : $($process.ExitCode)" }
    else {
        $fenetres = [FenetresProcessus]::Lister([uint32]$process.Id)
        $fenetres | Set-Content -LiteralPath (Join-Path $diagnostics "fenetres-$phase.txt") -Encoding UTF8
        Write-Host "Fenetres du processus ($($fenetres.Count) lignes) :"
        $fenetres | Select-Object -First 60 | ForEach-Object { Write-Host $_ }
    }
    foreach ($root in @($portable, $env:APPDATA, $env:LOCALAPPDATA) + $dossiersReels) {
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
    if (Test-Path $diagnostic -PathType Leaf) {
        Write-Host 'Etapes et exceptions du diagnostic de demarrage :'
        Select-String -LiteralPath $diagnostic -Pattern ' (DEBUT|ETAPE|EXCEPTION|FIN_PROCESSUS|PROFIL)' |
            ForEach-Object { Write-Host $_.Line }
        Write-Host 'Fin du diagnostic de demarrage :'
        Get-Content -LiteralPath $diagnostic -Tail 80 -ErrorAction Continue
    }
    else { Write-Host "Aucun diagnostic de demarrage ecrit ($diagnostic) : blocage avant le premier module Python." }
}

function Start-PortableAndCheck {
    param([string] $phase)
    $diagnostic = Join-Path $diagnostics "demarrage-$phase.log"
    $env:NOETHYS_DIAGNOSTIC_DEMARRAGE = $diagnostic
    $env:NOETHYS_DIAGNOSTIC_DELAI_PILES = '20'
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
            Show-PortableDiagnostics -phase $phase -process $process -diagnostic $diagnostic
            throw "Noethys.exe n'a pas initialise son profil portable ($phase) avant sortie ou timeout"
        }
        Write-Host "Profil portable initialise ($phase) apres $([math]::Round(([DateTime]::UtcNow - $debut).TotalSeconds, 1)) secondes"
    }
    finally {
        if (-not $process.HasExited) { Stop-Process -Id $process.Id -Force }
        Remove-Item Env:NOETHYS_DIAGNOSTIC_DEMARRAGE -ErrorAction SilentlyContinue
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
$env:NOETHYS_RC102_SMOKE_ROOT = $extrait
$env:NOETHYS_RC102_SMOKE_VALUE = [string]$env:GITHUB_RUN_ID
python -c "import os,sys;sys.path.insert(0,'noethys');import Chemins;Chemins.REP_COURANT=os.environ['NOETHYS_RC102_SMOKE_ROOT'];from Utils import UTILS_Config;c=UTILS_Config.FichierConfig();c.SetItemConfig('rc103_portable_smoke',os.environ['NOETHYS_RC102_SMOKE_VALUE']);assert UTILS_Config.FichierConfig().GetItemConfig('rc103_portable_smoke')==os.environ['NOETHYS_RC102_SMOKE_VALUE']"
if ($LASTEXITCODE -ne 0) { throw 'Echec de sauvegarde par UTILS_Config' }
Assert-NoExternalProfile

Start-PortableAndCheck -phase 'second'
$relu = Get-Content -LiteralPath $config -Raw -Encoding UTF8 | ConvertFrom-Json
if ($relu.rc103_portable_smoke -ne $env:NOETHYS_RC102_SMOKE_VALUE) {
    throw 'Le parametre modifie a disparu apres le second demarrage'
}
Assert-NoExternalProfile
Write-Host 'PASS: ZIP extrait, deux demarrages, vraie sauvegarde Config.json, persistance, aucun profil Windows externe'
