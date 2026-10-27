# Noethys-SL - recette utilisateur UI-432G (#432) : gel pendant la synchro Connecthys.
# Lance Noethys depuis les sources de la branche wx, avec NOETHYS_SL_UI_DIAG=1
# pour CETTE execution seulement, et prepare un extrait anonymise du journal.
# Ne modifie ni le depot, ni la configuration, ni les bases, ni le profil.
# Ne declenche aucune synchronisation : Noethys est utilise normalement.
#
# Usage : powershell -ExecutionPolicy Bypass -File tools\ui432g_recette.ps1 [-VerifierSeulement] [-Python <python.exe>]
param(
    [string]$Depot = "C:\Users\Ordi\Documents\GitHub\Noethys",
    [string]$Python = "",
    [switch]$VerifierSeulement
)
$ErrorActionPreference = "Stop"
$CorrectifGel = "dff8a13fdc36cc0e7a913c0cef22497be0e6616e"
$CorrectifSortie = "bb7dc1b6"

function Refuser([string]$motif) {
    Write-Host ""
    Write-Host "LANCEMENT REFUSE : $motif" -ForegroundColor Red
    Write-Host "Aucune action n'a ete effectuee sur Noethys, le profil ou les bases." -ForegroundColor Red
    exit 2
}
function Ok([string]$texte) { Write-Host "[OK] $texte" -ForegroundColor Green }
function Empreinte([string]$chemin) {
    if (Test-Path -LiteralPath $chemin) { return (Get-FileHash -LiteralPath $chemin -Algorithm SHA256).Hash }
    return "absent"
}

# 1. Depot
if (-not (Test-Path -LiteralPath (Join-Path $Depot "noethys\Noethys.py"))) { Refuser "depot Noethys introuvable : $Depot" }
Set-Location -LiteralPath $Depot
$git = Get-Command git -ErrorAction SilentlyContinue
if (-not $git) { Refuser "git introuvable" }
$racine = (& git rev-parse --show-toplevel 2>$null)
if ($LASTEXITCODE -ne 0 -or -not $racine) { Refuser "$Depot n'est pas un depot git" }
Ok "depot : $Depot"

# 2. Branche, HEAD, correctifs, modifications locales (rien n'est ecrase)
$branche = (& git rev-parse --abbrev-ref HEAD).Trim()
if ($branche -ne "wx") { Refuser "branche active '$branche' (attendu : wx). Faites 'git switch wx' vous-meme si l'arbre est propre." }
$head = (& git rev-parse HEAD).Trim()
& git merge-base --is-ancestor $CorrectifGel HEAD 2>$null
if ($LASTEXITCODE -ne 0) { Refuser "le correctif UI-432G $CorrectifGel n'est pas dans HEAD $head. Mettre a jour : git pull --ff-only origin wx" }
& git merge-base --is-ancestor $CorrectifSortie HEAD 2>$null
if ($LASTEXITCODE -ne 0) { Refuser "le correctif du diagnostic $CorrectifSortie n'est pas dans HEAD" }
$modifs = @(& git status --porcelain --untracked-files=no -- noethys)
if ($modifs.Count -gt 0) { Refuser ("fichiers suivis modifies dans noethys\ (non ecrases) :`n  " + ($modifs -join "`n  ")) }
$nonSuivisCode = @(& git status --porcelain --untracked-files=all -- noethys | Where-Object { $_ -match '^\?\? .*\.py$' -and $_ -notmatch 'Portable/' })
if ($nonSuivisCode.Count -gt 0) { Refuser ("fichiers .py non suivis dans noethys\ susceptibles de masquer le code :`n  " + ($nonSuivisCode -join "`n  ")) }
$distant = ""
& git fetch --quiet origin wx 2>$null
if ($LASTEXITCODE -eq 0) {
    $distant = (& git rev-parse origin/wx).Trim()
    if ($distant -ne $head) {
        $avance = (& git rev-list --count "$head..origin/wx").Trim()
        Write-Host "[INFO] origin/wx ($($distant.Substring(0,8))) a $avance commit(s) de plus que HEAD ; la recette porte sur HEAD $($head.Substring(0,8))." -ForegroundColor Yellow
    }
} else {
    Write-Host "[INFO] git fetch impossible (hors ligne ?) : HEAD local utilise." -ForegroundColor Yellow
}
Ok "branche wx, HEAD $head, correctifs $($CorrectifGel.Substring(0,8)) et $CorrectifSortie presents, arbre noethys\ propre"

# 3. Python reellement utilise et dependances
if (-not $Python) { $Python = Join-Path $Depot ".venv\Scripts\python.exe" }
if (-not (Test-Path -LiteralPath $Python)) { Refuser "interpreteur introuvable : $Python (preciser -Python <chemin>)" }
if ($env:PYTHONHOME) { Refuser "PYTHONHOME est defini ($env:PYTHONHOME) : environnement Python ambigu" }
$sonde = @'
import importlib, json, sys
r = {"exe": sys.executable, "python": sys.version.split()[0], "manquants": [], "versions": {}}
for nom in ["wx", "sqlalchemy", "MySQLdb", "Crypto.Cipher.AES", "paramiko", "dateutil", "six", "appdirs",
            "numpy", "lxml.etree", "reportlab", "psutil", "PIL", "requests"]:
    try:
        m = importlib.import_module(nom)
        r["versions"][nom] = m.version() if nom == "wx" else str(getattr(m, "__version__", ""))
    except Exception as err:
        r["manquants"].append("%s (%s)" % (nom, type(err).__name__))
print(json.dumps(r))
'@
$sauvePythonPath = $env:PYTHONPATH
$env:PYTHONPATH = ""
try { $json = ($sonde | & $Python -I - 2>$null) } finally { $env:PYTHONPATH = $sauvePythonPath }
if ($LASTEXITCODE -ne 0 -or -not $json) { Refuser "l'interpreteur $Python ne s'execute pas" }
$deps = $json | ConvertFrom-Json
if ($deps.manquants.Count -gt 0) { Refuser ("dependances absentes pour $($deps.exe) : " + ($deps.manquants -join ", ")) }
$sa = [version](($deps.versions.sqlalchemy -split '[^0-9.]')[0])
if ($sa -lt [version]"1.4") { Refuser "SQLAlchemy $($deps.versions.sqlalchemy) < 1.4 (non qualifie)" }
$du = [version](($deps.versions.dateutil -split '[^0-9.]')[0].TrimEnd('.'))
if ($du.Major -ge 3) { Refuser "python-dateutil $($deps.versions.dateutil) : la 3.x casse le demarrage (2.9 requis)" }
$wxv = [version](($deps.versions.wx -split ' ')[0])
if ($wxv -lt [version]"4.2") { Refuser "wxPython $($deps.versions.wx) < 4.2" }
Ok "Python $($deps.python) : $($deps.exe)"
Ok "wx $($deps.versions.wx) ; SQLAlchemy $($deps.versions.sqlalchemy) ; dateutil $($deps.versions.dateutil) ; mysqlclient $($deps.versions.MySQLdb)"

# 4. Le code charge sera bien celui du depot (et pas un ancien executable)
$verif = @'
import importlib.util, json, os, sys
racine = os.path.abspath(sys.argv[1])
sys.path.insert(0, racine)
r = {}
for nom, marqueurs in {
        "Utils.UTILS_Portail_synchro": ["UTILS_Priorite_ui.enregistrer_par_lots(session, consommations, priorite)",
                                         "UTILS_Priorite_ui.session_cooperative(Session(), priorite)"],
        "Utils.UTILS_Priorite_ui": ["def ceder(self)", "def enregistrer_par_lots("],
        "Utils.UTILS_Diagnostic_ui": ["self._wx.Timer()", "def _etat_fenetre_bloquee(self)"]}.items():
    spec = importlib.util.find_spec(nom)
    chemin = os.path.abspath(spec.origin) if spec and spec.origin else ""
    texte = open(chemin, encoding="utf-8").read() if chemin else ""
    r[nom] = {"chemin": chemin, "dans_depot": chemin.lower().startswith(racine.lower() + os.sep),
              "marqueurs": all(m in texte for m in marqueurs)}
print(json.dumps(r))
'@
$noethysDir = Join-Path $Depot "noethys"
Push-Location -LiteralPath $noethysDir
$env:PYTHONPATH = ""
try { $json = ($verif | & $Python -I - $noethysDir 2>$null) } finally { $env:PYTHONPATH = $sauvePythonPath; Pop-Location }
if (-not $json) { Refuser "verification du code charge impossible" }
$code = $json | ConvertFrom-Json
foreach ($p in $code.PSObject.Properties) {
    if (-not $p.Value.dans_depot) { Refuser "$($p.Name) serait charge hors du depot : $($p.Value.chemin)" }
    if (-not $p.Value.marqueurs) { Refuser "$($p.Name) ne contient pas le correctif attendu ($($p.Value.chemin))" }
}
Ok "code charge depuis $noethysDir avec les correctifs UI-432F/G (pas d'executable Noethys.exe)"

# Aucune autre instance de Noethys (meme base, meme profil)
$exe = @(Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -like "Noethys*" })
if ($exe.Count -gt 0) { Refuser "un executable Noethys est deja ouvert (PID $($exe.Id -join ', ')) : le fermer d'abord" }
$py = @(Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -match 'Noethys\.py' })
if ($py.Count -gt 0) { Refuser "Noethys est deja lance depuis Python (PID $($py.ProcessId -join ', '))" }
Ok "aucune autre instance de Noethys"

# Profil utilise (constat seulement : rien n'est lu ni modifie)
$portable = Join-Path $noethysDir "Portable"
if (Test-Path -LiteralPath $portable -PathType Container) { $profil = $portable; $typeProfil = "Portable du depot" }
else { $profil = Join-Path $env:APPDATA "noethys"; $typeProfil = "profil utilisateur" }
$suivis = @("Config.json", "Customize.ini") | ForEach-Object { Join-Path $profil $_ }
$avant = @{}; foreach ($f in $suivis) { $avant[$f] = Empreinte $f }
Ok "profil : $typeProfil ($profil) - non modifie par ce lanceur"

# 5-6. Journal local (hors depot et hors profil)
$horodatage = Get-Date -Format "yyyyMMdd-HHmmss"
$dossier = Join-Path $env:LOCALAPPDATA "NoethysSL-recette\UI432G-$horodatage"
$sortie = Join-Path $dossier "stdout-COMPLET-NE-PAS-DIFFUSER.log"
$erreurs = Join-Path $dossier "stderr-COMPLET-NE-PAS-DIFFUSER.log"
$extrait = Join-Path $dossier "extrait-anonymise-UI432G.txt"
$contexte = Join-Path $dossier "contexte.txt"

if ($VerifierSeulement) {
    Write-Host ""
    Write-Host "VERIFICATIONS OK - mode -VerifierSeulement : Noethys n'est PAS lance." -ForegroundColor Cyan
    exit 0
}

New-Item -ItemType Directory -Path $dossier -Force | Out-Null
@(
    "Recette UI-432G - $(Get-Date -Format 'dd/MM/yyyy HH:mm:ss')",
    "Depot : $Depot", "Branche : $branche", "HEAD : $head", "origin/wx : $distant",
    "Python : $($deps.exe) ($($deps.python))",
    "wx : $($deps.versions.wx) ; SQLAlchemy : $($deps.versions.sqlalchemy) ; dateutil : $($deps.versions.dateutil)",
    "Profil : $typeProfil"
) | Set-Content -LiteralPath $contexte -Encoding UTF8

Write-Host ""
Write-Host "Lancement de Noethys (diagnostic actif pour cette execution seulement)." -ForegroundColor Cyan
Write-Host "Utilisez Noethys normalement ; laissez la synchronisation AUTOMATIQUE se produire." -ForegroundColor Cyan
Write-Host "Fermez Noethys normalement a la fin : l'extrait sera prepare automatiquement." -ForegroundColor Cyan
$sauve = @{ NOETHYS_SL_UI_DIAG = $env:NOETHYS_SL_UI_DIAG; PYTHONIOENCODING = $env:PYTHONIOENCODING; PYTHONPATH = $env:PYTHONPATH }
$debut = Get-Date
try {
    $env:NOETHYS_SL_UI_DIAG = "1"
    $env:PYTHONIOENCODING = "utf-8"
    $env:PYTHONPATH = ""
    # Sans -Wait : attendre Noethys seul, pas d'eventuels processus enfants.
    $proc = Start-Process -FilePath $Python -ArgumentList @("-u", "-X", "faulthandler", "Noethys.py") `
        -WorkingDirectory $noethysDir -NoNewWindow -PassThru `
        -RedirectStandardOutput $sortie -RedirectStandardError $erreurs
    $null = $proc.Handle   # necessaire pour lire ExitCode apres la fin
    $proc.WaitForExit()
    $codeSortie = $proc.ExitCode
} finally {
    foreach ($k in $sauve.Keys) {
        if ($null -eq $sauve[$k]) { Remove-Item "Env:$k" -ErrorAction SilentlyContinue }
        else { Set-Item "Env:$k" $sauve[$k] }
    }
}
$fin = Get-Date

# Extrait anonymise : liste blanche stricte de cles et de valeurs techniques
$cles = '^(evenement|fenetre|operation|etape|duree_ms|sans_evenements_ms|erreur_type|retard_ms|actif|maximise|largeur|hauteur|iconise|wx_maximise|win32_maximise|win32_iconise|premier_plan|point|point_synchro|veille_retard_ms|ne_repond_pas|fantome)$'
$lignes = New-Object System.Collections.Generic.List[string]
$evts = @()
foreach ($l in (Get-Content -LiteralPath $sortie -Encoding UTF8 -ErrorAction SilentlyContinue)) {
    if ($l -match '^NOETHYS_UI_DIAG (.+)$') {
        $paires = $Matches[1] -split ' '
        $ok = $true; $obj = @{}
        foreach ($p in $paires) {
            if ($p -notmatch '^([a-z_0-9]+)=([A-Za-z0-9_.:\-]{1,80})$') { $ok = $false; break }
            $cle = $Matches[1]; $valeur = $Matches[2]
            if ($cle -notmatch $cles) { $ok = $false; break }
            $obj[$cle] = $valeur
        }
        if ($ok) { $lignes.Add($l); $evts += ,$obj }
    } elseif ($l -match '^Temps (upload_data|download_data)\s*=\s*([0-9.]+)\s*$') {
        $lignes.Add("Temps $($Matches[1]) = $($Matches[2])")
    }
}
$retards = @($evts | Where-Object { $_.evenement -eq "retard_boucle" } | ForEach-Object { [int]$_.retard_ms })
$maxRetard = 0; if ($retards.Count -gt 0) { $maxRetard = ($retards | Measure-Object -Maximum).Maximum }
$nb5s = @($retards | Where-Object { $_ -ge 5000 }).Count
$hung = @($evts | Where-Object { $_.ne_repond_pas -eq "True" }).Count
$icon = @($evts | Where-Object { $_.win32_iconise -eq "True" }).Count
$apres = @{}; foreach ($f in $suivis) { $apres[$f] = Empreinte $f }
$verdict = "CRITERES RESPECTES"
if ($nb5s -gt 0 -or $hung -gt 0) { $verdict = "CRITERES NON RESPECTES" }
if ($evts.Count -eq 0) { $verdict = "AUCUN EVENEMENT DE DIAGNOSTIC (recette non concluante)" }
$resume = @(
    "Recette UI-432G - extrait anonymise (cles et valeurs techniques uniquement)",
    "HEAD : $head ; Python $($deps.python) ; wx $($deps.versions.wx) ; SQLAlchemy $($deps.versions.sqlalchemy)",
    "Execution : $($debut.ToString('dd/MM/yyyy HH:mm:ss')) -> $($fin.ToString('HH:mm:ss')) ; code de sortie $codeSortie",
    "Evenements retenus : $($evts.Count) ; retard_boucle max : $maxRetard ms ; >= 5000 ms : $nb5s",
    "ne_repond_pas=True : $hung ; win32_iconise=True : $icon (verifier qu'il s'agit d'une reduction volontaire)",
    "Verdict automatique : $verdict",
    "----"
)
($resume + $lignes) | Set-Content -LiteralPath $extrait -Encoding UTF8
foreach ($f in $suivis) {
    $etat = "inchange"; if ($avant[$f] -ne $apres[$f]) { $etat = "modifie par Noethys pendant l'utilisation (normal : preferences, dernier fichier)" }
    Add-Content -LiteralPath $contexte -Value "$(Split-Path $f -Leaf) : $etat" -Encoding UTF8
}

Write-Host ""
$resume | ForEach-Object { Write-Host $_ }
Write-Host ""
Write-Host "Dossier de recette : $dossier"
Write-Host "  A transmettre    : $extrait"
Write-Host "  Local seulement  : $sortie et $erreurs (peuvent contenir des donnees : NE PAS diffuser)"
