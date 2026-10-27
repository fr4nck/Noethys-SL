# Noethys-SL - recette utilisateur UI-432G (#432) : gel pendant la synchro Connecthys.
# Lance Noethys depuis les sources de la branche wx, avec NOETHYS_SL_UI_DIAG=1
# pour CETTE execution seulement, puis analyse le journal et prepare un extrait
# strictement anonymise. Ne modifie ni le depot, ni la configuration, ni les
# bases, ni le profil. Ne declenche aucune synchronisation : Noethys est utilise
# normalement. Compatible Windows PowerShell 5.1 et PowerShell 7 (fichier ASCII).
#
# Usage :
#   powershell -NoProfile -File tools\ui432g_recette.ps1 -VerifierSeulement   # verifications, sans lancer
#   powershell -NoProfile -File tools\ui432g_recette.ps1                      # verifications puis lancement
#   powershell -NoProfile -File tools\ui432g_recette.ps1 -Analyser <dossier> [-IconisationVolontaire]
#       (re)analyse un dossier de recette existant, sans rien verifier ni lancer.
#
# Codes de sortie : 0 recette REUSSIE (ou verifications OK avec -VerifierSeulement) ;
#   2 lancement refuse ; 10 NON RESPECTEE ; 11 A REVOIR ; 12 NON CONCLUANTE ;
#   1 erreur inattendue du lanceur.
param(
    [string]$Depot = "",
    [string]$Python = "",
    [switch]$VerifierSeulement,
    [string]$Analyser = "",
    [switch]$IconisationVolontaire
)
$ErrorActionPreference = "Stop"
$CorrectifGel = "dff8a13fdc36cc0e7a913c0cef22497be0e6616e"
$CorrectifSortie = "bb7dc1b6"
$SeuilGelMs = 5000
$CodeReussie = 0; $CodeRefus = 2; $CodeNonRespectee = 10; $CodeARevoir = 11; $CodeNonConcluante = 12

$FichierSortie = "stdout-COMPLET-NE-PAS-DIFFUSER.log"
$FichierErreurs = "stderr-COMPLET-NE-PAS-DIFFUSER.log"
$FichierExtrait = "extrait-anonymise-UI432G.txt"
$FichierMeta = "meta-anonyme.txt"
$FichierExecution = "execution.txt"
$FichierContexte = "contexte-local.txt"

function Refuser([string]$motif) {
    Write-Host ""
    Write-Host "LANCEMENT REFUSE : $motif" -ForegroundColor Red
    Write-Host "Aucune action n'a ete effectuee sur Noethys, le profil ou les bases." -ForegroundColor Red
    exit $CodeRefus
}
function Ok([string]$texte) { Write-Host "[OK] $texte" -ForegroundColor Green }
function Empreinte([string]$chemin) {
    if (Test-Path -LiteralPath $chemin) { return (Get-FileHash -LiteralPath $chemin -Algorithm SHA256).Hash }
    return "absent"
}
# Windows PowerShell 5.1 transforme la sortie d'erreur d'un programme natif en
# erreur bloquante quand ErrorActionPreference=Stop : les appels git/python
# passent par ce bloc et sont juges sur leur seul code de retour.
function Natif([scriptblock]$bloc) {
    $precedent = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try { & $bloc } finally { $ErrorActionPreference = $precedent }
}

# ---------------------------------------------------------------------------
# Analyse du journal (aucun acces au depot, a Python, au profil ni aux bases)
# ---------------------------------------------------------------------------
$Entier = '^-?[0-9]{1,9}$'
$Booleen = '^(True|False)$'
$Point = '^(hors_noethys|aucune|[A-Za-z_][A-Za-z0-9_]{0,70}\.py:[A-Za-z_][A-Za-z0-9_]{0,70}:[0-9]{1,6})$'
# Schema ferme de UTILS_Diagnostic_ui : toute autre cle ou valeur est masquee.
$Regles = @{
    evenement = '^(activation|blocage_thread|etape|etat|iconisation|maximisation|operation|retard_boucle|taille|veille_retardee)$'
    fenetre = '^(principale|demande)$'
    operation = '^(demande\.(traitement|enregistrement|actualisation)|reservations\.(initialisation_grille|calcul|sauvegarde)|inconnue)$'
    etape = '^grille\.[a-z_]{1,40}$'
    erreur_type = '^[A-Za-z_][A-Za-z0-9_]{0,79}$'
    point = $Point; point_synchro = $Point
    duree_ms = $Entier; sans_evenements_ms = $Entier; retard_ms = $Entier; largeur = $Entier
    hauteur = $Entier; veille_retard_ms = $Entier
    actif = $Booleen; maximise = $Booleen; iconise = $Booleen; wx_maximise = $Booleen
    win32_maximise = $Booleen; win32_iconise = $Booleen; premier_plan = $Booleen
    ne_repond_pas = $Booleen; fantome = $Booleen
}

function Lire-Cles([string]$chemin) {
    $r = @{}
    if (Test-Path -LiteralPath $chemin) {
        foreach ($l in (Get-Content -LiteralPath $chemin -Encoding UTF8)) {
            if ($l -match '^([a-z_0-9]+)=(.*)$') { $r[$Matches[1]] = $Matches[2] }
        }
    }
    return $r
}

function Analyser-Recette([string]$dossier, [bool]$iconisationDeclaree) {
    $sortie = Join-Path $dossier $FichierSortie
    $erreurs = Join-Path $dossier $FichierErreurs
    $meta = Lire-Cles (Join-Path $dossier $FichierMeta)
    $exec = Lire-Cles (Join-Path $dossier $FichierExecution)

    $lignes = New-Object System.Collections.Generic.List[string]
    $masques = 0; $evenements = 0; $principale = 0
    $tentatives = 0; $synchros = New-Object System.Collections.Generic.List[string]
    $enSynchro = $false
    $gels = New-Object System.Collections.Generic.List[object]
    $maxRetard = 0; $maxVeille = 0; $hung = 0; $fantome = 0; $iconise = 0

    $journalPresent = Test-Path -LiteralPath $sortie
    if ($journalPresent) {
        foreach ($l in (Get-Content -LiteralPath $sortie -Encoding UTF8)) {
            # Marqueurs de synchronisation : seul leur nombre et la duree sont
            # retenus, jamais l'URL ni le contenu de la ligne.
            if ($l -match 'URL syncdown =') { $tentatives++; $enSynchro = $true; $lignes.Add("MARQUEUR synchro_debut") }
            $mt = [regex]::Match($l, 'Temps upload_data\s*=\s*([0-9]{1,6}(\.[0-9]{1,9})?)')
            if ($mt.Success) {
                $inv = [Globalization.CultureInfo]::InvariantCulture
                $duree = [double]::Parse($mt.Groups[1].Value, $inv).ToString("0.0", $inv)
                $synchros.Add($duree); $enSynchro = $false
                $lignes.Add("MARQUEUR synchro_terminee upload_data_s=$duree")
            }
            $md = [regex]::Match($l, 'NOETHYS_UI_DIAG (.*)$')
            if (-not $md.Success) { continue }
            $obj = @{}; $gardes = New-Object System.Collections.Generic.List[string]; $masqueLigne = 0
            foreach ($jeton in ($md.Groups[1].Value -split ' ')) {
                if ($jeton -eq "") { continue }
                $mj = [regex]::Match($jeton, '^([a-z][a-z0-9_]{0,29})=(.{1,80})$')
                if ($mj.Success -and $Regles.ContainsKey($mj.Groups[1].Value) -and
                        $mj.Groups[2].Value -cmatch $Regles[$mj.Groups[1].Value] -and
                        -not $obj.ContainsKey($mj.Groups[1].Value)) {
                    $obj[$mj.Groups[1].Value] = $mj.Groups[2].Value
                    $gardes.Add($jeton)
                } else { $masqueLigne++ }
            }
            $masques += $masqueLigne
            if (-not $obj.ContainsKey("evenement")) { continue }
            $evenements++
            if ($obj["fenetre"] -eq "principale") { $principale++ }
            if ($masqueLigne -gt 0) { $gardes.Add("masque=$masqueLigne") }
            $lignes.Add("NOETHYS_UI_DIAG " + ($gardes -join ' '))

            $ev = $obj["evenement"]; $gel = 0
            if ($ev -eq "retard_boucle" -and $obj.ContainsKey("retard_ms")) { $gel = [int]$obj["retard_ms"] }
            if ($ev -eq "blocage_thread" -and $obj.ContainsKey("duree_ms")) { $gel = [int]$obj["duree_ms"] }
            if ($ev -eq "operation" -and $obj.ContainsKey("sans_evenements_ms")) { $gel = [int]$obj["sans_evenements_ms"] }
            if ($gel -gt $maxRetard) { $maxRetard = $gel }
            if ($gel -ge $SeuilGelMs) {
                $contexte = "hors_synchro"; if ($enSynchro) { $contexte = "pendant_synchro" }
                $gels.Add([pscustomobject]@{ ms = $gel; evenement = $ev; contexte = $contexte; point = $obj["point"] })
            }
            if ($obj.ContainsKey("veille_retard_ms") -and [int]$obj["veille_retard_ms"] -gt $maxVeille) { $maxVeille = [int]$obj["veille_retard_ms"] }
            if ($obj["ne_repond_pas"] -eq "True") { $hung++ }
            if ($obj["fantome"] -eq "True") { $fantome++ }
            if ($obj["win32_iconise"] -eq "True" -or $obj["iconise"] -eq "True") { $iconise++ }
        }
    }

    $fatal = 0; $traces = 0
    if (Test-Path -LiteralPath $erreurs) {
        foreach ($l in (Get-Content -LiteralPath $erreurs -Encoding UTF8)) {
            if ($l -match '^(Fatal Python error|Windows fatal exception)') { $fatal++ }
            if ($l -match '^Traceback \(most recent call last\)') { $traces++ }
        }
    }

    # Raisons d'une recette non concluante : jamais de succes par defaut.
    $nc = New-Object System.Collections.Generic.List[string]
    $codeSortie = $exec["code_sortie"]
    if ($exec["etat"] -ne "termine") { $nc.Add("lancement interrompu ou fin non enregistree (fenetre PowerShell fermee, Ctrl+C ?)") }
    elseif ($codeSortie -notmatch '^-?[0-9]+$') { $nc.Add("code de sortie de Noethys inconnu") }
    elseif ([int]$codeSortie -ne 0) { $nc.Add(("sortie anormale de Noethys : code {0} (0x{1:X8})" -f $codeSortie, [int]$codeSortie)) }
    if ($fatal -gt 0) { $nc.Add("erreur fatale Python/Windows dans stderr ($fatal)") }
    if (-not $journalPresent) { $nc.Add("journal stdout absent") }
    elseif ($principale -eq 0) { $nc.Add("aucun evenement de diagnostic de la fenetre principale (diagnostic inactif ou journal incomplet)") }
    if ($masques -gt 0) { $nc.Add("$masques valeur(s) hors schema masquee(s) : journal non conforme, analyse manuelle du journal local requise") }
    if ($synchros.Count -eq 0) {
        if ($tentatives -gt 0) { $nc.Add("$tentatives synchronisation(s) commencee(s) mais aucune terminee avec succes (pas de 'Temps upload_data')") }
        else { $nc.Add("aucune synchronisation observee : la session ne prouve rien sur le correctif") }
    }

    if ($gels.Count -gt 0 -or $hung -gt 0) { $verdict = "NON RESPECTEE"; $code = $CodeNonRespectee }
    elseif ($nc.Count -gt 0) { $verdict = "NON CONCLUANTE"; $code = $CodeNonConcluante }
    elseif ($iconise -gt 0 -and -not $iconisationDeclaree) { $verdict = "A REVOIR"; $code = $CodeARevoir }
    else { $verdict = "REUSSIE"; $code = $CodeReussie }

    $pendant = @($gels | Where-Object { $_.contexte -eq "pendant_synchro" }).Count
    $resume = New-Object System.Collections.Generic.List[string]
    $resume.Add("Recette UI-432G - extrait anonymise (cles et valeurs techniques uniquement)")
    $resume.Add("HEAD : $($meta['head']) ; Python $($meta['python']) ; wx $($meta['wx']) ; SQLAlchemy $($meta['sqlalchemy']) ; dateutil $($meta['dateutil'])")
    $resume.Add("Execution : debut $($meta['debut']) ; duree $($exec['duree_s']) s ; code de sortie $codeSortie")
    $resume.Add("Synchronisations : $($synchros.Count) terminee(s) [upload_data s : $($synchros -join ', ')] sur $tentatives commencee(s)")
    $resume.Add("Evenements de diagnostic : $evenements (fenetre principale : $principale) ; valeurs masquees : $masques")
    $resume.Add("Gel max : $maxRetard ms ; gels >= $SeuilGelMs ms : $($gels.Count) (pendant synchro : $pendant, hors synchro : $($gels.Count - $pendant))")
    foreach ($g in ($gels | Sort-Object ms -Descending | Select-Object -First 5)) {
        $resume.Add("  gel $($g.ms) ms ($($g.evenement), $($g.contexte), point=$($g.point))")
    }
    $resume.Add("ne_repond_pas=True : $hung ; fantome=True : $fantome ; veille retardee max : $maxVeille ms")
    $icTexte = "iconisation observee : $iconise"
    if ($iconise -gt 0 -and $iconisationDeclaree) { $icTexte += " (declaree volontaire par l'utilisateur)" }
    $resume.Add($icTexte)
    $resume.Add("Exceptions Python dans stderr : $traces (detail dans le journal local uniquement)")
    $resume.Add("Profil : Config.json $($meta['profil_config']) ; Customize.ini $($meta['profil_customize'])")
    $resume.Add("VERDICT : $verdict")
    if ($verdict -eq "NON RESPECTEE" -and $pendant -eq 0 -and $gels.Count -gt 0) {
        $resume.Add("  Note : gel(s) hors synchronisation, a rapprocher d'un traitement d'interface (voir #434), pas du correctif UI-432G seul.")
    }
    if ($verdict -eq "NON CONCLUANTE") { foreach ($r in $nc) { $resume.Add("  Raison : $r") } }
    elseif ($nc.Count -gt 0) { foreach ($r in $nc) { $resume.Add("  Reserve : $r") } }
    if ($verdict -eq "A REVOIR") {
        $resume.Add("  Iconisation de cause inconnue : si vous avez reduit Noethys vous-meme, relancer l'analyse avec -IconisationVolontaire.")
    }
    $resume.Add("Limites : synchro automatique ou manuelle non distinguable dans le journal ; lignes non horodatees (ordre seulement) ; journal Connecthys du panneau non collecte ; recette = une session sur ce poste.")
    $resume.Add("----")

    ($resume + $lignes) | Set-Content -LiteralPath (Join-Path $dossier $FichierExtrait) -Encoding UTF8
    return [pscustomobject]@{ verdict = $verdict; code = $code; resume = $resume }
}

if ($Analyser) {
    if (-not (Test-Path -LiteralPath $Analyser -PathType Container)) { Refuser "dossier de recette introuvable : $Analyser" }
    $res = Analyser-Recette (Resolve-Path -LiteralPath $Analyser).Path ([bool]$IconisationVolontaire)
    $res.resume | ForEach-Object { Write-Host $_ }
    Write-Host ""
    Write-Host "Extrait a transmettre : $(Join-Path $Analyser $FichierExtrait)"
    exit $res.code
}

# ---------------------------------------------------------------------------
# 1. Depot
# ---------------------------------------------------------------------------
if (-not $Depot) { $Depot = Split-Path -Parent $PSScriptRoot }
if (-not (Test-Path -LiteralPath (Join-Path $Depot "noethys\Noethys.py"))) { Refuser "depot Noethys introuvable : $Depot" }
$Depot = (Resolve-Path -LiteralPath $Depot).Path
Set-Location -LiteralPath $Depot
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { Refuser "git introuvable" }
$racine = Natif { & git rev-parse --show-toplevel 2>$null }
if ($LASTEXITCODE -ne 0 -or -not $racine) { Refuser "$Depot n'est pas un depot git" }
Ok "depot : $Depot"

# 2. Branche, HEAD, correctifs, modifications locales (rien n'est ecrase)
$branche = "$(Natif { & git rev-parse --abbrev-ref HEAD 2>$null })".Trim()
if ($branche -ne "wx") { Refuser "branche active '$branche' (attendu : wx). Faites 'git switch wx' vous-meme si l'arbre est propre." }
$head = "$(Natif { & git rev-parse HEAD 2>$null })".Trim()
Natif { & git merge-base --is-ancestor $CorrectifGel HEAD 2>$null }
if ($LASTEXITCODE -ne 0) { Refuser "le correctif UI-432G $CorrectifGel n'est pas dans HEAD $head. Mettre a jour : git pull --ff-only origin wx" }
Natif { & git merge-base --is-ancestor $CorrectifSortie HEAD 2>$null }
if ($LASTEXITCODE -ne 0) { Refuser "le correctif du diagnostic $CorrectifSortie n'est pas dans HEAD $head" }
$modifs = @(Natif { & git status --porcelain --untracked-files=no -- noethys 2>$null })
if ($modifs.Count -gt 0) { Refuser ("fichiers suivis modifies dans noethys\ (conserves, non ecrases) :`n  " + ($modifs -join "`n  ")) }
$nonSuivisCode = @(Natif { & git status --porcelain --untracked-files=all -- noethys 2>$null } |
    Where-Object { $_ -match '^\?\? .*\.py$' -and $_ -notmatch 'Portable/' })
if ($nonSuivisCode.Count -gt 0) { Refuser ("fichiers .py non suivis dans noethys\ susceptibles de masquer le code :`n  " + ($nonSuivisCode -join "`n  ")) }
$distant = ""
$sauveInvite = $env:GIT_TERMINAL_PROMPT; $env:GIT_TERMINAL_PROMPT = "0"
try { Natif { & git fetch --quiet origin wx 2>$null } } finally { $env:GIT_TERMINAL_PROMPT = $sauveInvite }
if ($LASTEXITCODE -eq 0) {
    $distant = "$(Natif { & git rev-parse origin/wx 2>$null })".Trim()
    if ($distant -and $distant -ne $head) {
        $avance = "$(Natif { & git rev-list --count "$head..origin/wx" 2>$null })".Trim()
        Write-Host "[INFO] origin/wx ($($distant.Substring(0,8))) a $avance commit(s) absent(s) de HEAD ; la recette porte sur HEAD $($head.Substring(0,8))." -ForegroundColor Yellow
    }
} else {
    Write-Host "[INFO] git fetch impossible (hors ligne ?) : HEAD local utilise." -ForegroundColor Yellow
}
Ok "branche wx, HEAD $head, correctifs $($CorrectifGel.Substring(0,8)) et $CorrectifSortie presents, fichiers suivis de noethys\ non modifies"

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
print("SONDE " + json.dumps(r))
'@
$sauvePythonPath = $env:PYTHONPATH
$env:PYTHONPATH = ""
try { $brut = @(Natif { $sonde | & $Python -I - 2>$null }) } finally { $env:PYTHONPATH = $sauvePythonPath }
$json = ($brut | Where-Object { $_ -like "SONDE *" } | Select-Object -Last 1)
if ($LASTEXITCODE -ne 0 -or -not $json) { Refuser "l'interpreteur $Python ne s'execute pas correctement" }
$deps = $json.Substring(6) | ConvertFrom-Json
if (@($deps.manquants).Count -gt 0) { Refuser ("dependances absentes pour $($deps.exe) : " + ($deps.manquants -join ", ")) }
try {
    $sa = [version](($deps.versions.sqlalchemy -split '[^0-9.]')[0].TrimEnd('.'))
    $du = [version](($deps.versions.dateutil -split '[^0-9.]')[0].TrimEnd('.'))
    $wxv = [version](($deps.versions.wx -split '[^0-9.]')[0].TrimEnd('.'))
} catch { Refuser "versions illisibles : SQLAlchemy '$($deps.versions.sqlalchemy)', dateutil '$($deps.versions.dateutil)', wx '$($deps.versions.wx)'" }
if ($sa -lt [version]"1.4") { Refuser "SQLAlchemy $($deps.versions.sqlalchemy) < 1.4 (non qualifie)" }
if ($du.Major -ge 3) { Refuser "python-dateutil $($deps.versions.dateutil) : la 3.x casse le demarrage (2.9 requis)" }
if ($wxv -lt [version]"4.2") { Refuser "wxPython $($deps.versions.wx) < 4.2" }
Ok "Python $($deps.python) : $($deps.exe)"
Ok "wx $($deps.versions.wx) ; SQLAlchemy $($deps.versions.sqlalchemy) ; dateutil $($deps.versions.dateutil) ; mysqlclient $($deps.versions.MySQLdb)"
if ($sa -ne [version]"2.0.55") {
    Write-Host "[INFO] SQLAlchemy $($deps.versions.sqlalchemy) (banc et build : 2.0.55) ; tests du correctif valides sur base fictive avec 2.0.52." -ForegroundColor Yellow
}

# 4. Le code charge sera bien celui du depot (et pas un ancien executable)
$verif = @'
import importlib.util, json, os, sys
racine = os.path.abspath(sys.argv[1])
sys.path.insert(0, racine)
r = {}
for nom, marqueurs in {
        "Utils.UTILS_Portail_synchro": ["UTILS_Priorite_ui.enregistrer_par_lots(session, consommations, priorite)",
                                         "UTILS_Priorite_ui.session_cooperative(Session(), priorite)",
                                         "Temps upload_data = "],
        "Utils.UTILS_Priorite_ui": ["def ceder(self)", "def enregistrer_par_lots("],
        "Utils.UTILS_Diagnostic_ui": ["self._wx.Timer()", "def _etat_fenetre_bloquee(self)"]}.items():
    spec = importlib.util.find_spec(nom)
    chemin = os.path.abspath(spec.origin) if spec and spec.origin else ""
    texte = open(chemin, encoding="utf-8").read() if chemin else ""
    r[nom] = {"chemin": chemin, "dans_depot": chemin.lower().startswith(racine.lower() + os.sep),
              "marqueurs": all(m in texte for m in marqueurs)}
print("CODE " + json.dumps(r))
'@
$noethysDir = Join-Path $Depot "noethys"
Push-Location -LiteralPath $noethysDir
$env:PYTHONPATH = ""
try { $brut = @(Natif { $verif | & $Python -I - $noethysDir 2>$null }) } finally { $env:PYTHONPATH = $sauvePythonPath; Pop-Location }
$json = ($brut | Where-Object { $_ -like "CODE *" } | Select-Object -Last 1)
if (-not $json) { Refuser "verification du code charge impossible" }
$code = $json.Substring(5) | ConvertFrom-Json
foreach ($p in $code.PSObject.Properties) {
    if (-not $p.Value.dans_depot) { Refuser "$($p.Name) serait charge hors du depot : $($p.Value.chemin)" }
    if (-not $p.Value.marqueurs) { Refuser "$($p.Name) ne contient pas le correctif attendu ($($p.Value.chemin))" }
}
Ok "code charge depuis $noethysDir avec les correctifs UI-432F/G (Noethys.py, pas un Noethys.exe)"

# Aucune autre instance de Noethys (meme base, meme profil)
$exe = @(Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -like "Noethys*" })
if ($exe.Count -gt 0) { Refuser "un executable Noethys est deja ouvert (PID $($exe.Id -join ', ')) : le fermer d'abord" }
$py = @(Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -match 'Noethys\.py' })
if ($py.Count -gt 0) { Refuser "Noethys est deja lance depuis Python (PID $($py.ProcessId -join ', '))" }
Ok "aucune autre instance de Noethys"

# Profil utilise (constat seulement : le lanceur n'y ecrit jamais)
$portable = Join-Path $noethysDir "Portable"
if (Test-Path -LiteralPath $portable -PathType Container) { $profil = $portable; $typeProfil = "Portable du depot" }
else { $profil = Join-Path $env:APPDATA "noethys"; $typeProfil = "profil utilisateur" }
$suivis = [ordered]@{ profil_config = (Join-Path $profil "Config.json"); profil_customize = (Join-Path $profil "Customize.ini") }
$avant = @{}; foreach ($k in $suivis.Keys) { $avant[$k] = Empreinte $suivis[$k] }
Ok "profil : $typeProfil ($profil) - le lanceur n'y ecrit pas"

# 5-6. Journal local (hors depot et hors profil)
$horodatage = Get-Date -Format "yyyyMMdd-HHmmss"
$dossier = Join-Path $env:LOCALAPPDATA "NoethysSL-recette\UI432G-$horodatage"

if ($VerifierSeulement) {
    Write-Host ""
    Write-Host "VERIFICATIONS OK - mode -VerifierSeulement : Noethys n'est PAS lance." -ForegroundColor Cyan
    exit 0
}

New-Item -ItemType Directory -Path $dossier -Force | Out-Null
$sortie = Join-Path $dossier $FichierSortie
$erreurs = Join-Path $dossier $FichierErreurs
$execution = Join-Path $dossier $FichierExecution
$debut = Get-Date
@(
    "head=$head", "python=$($deps.python)", "wx=$($deps.versions.wx)",
    "sqlalchemy=$($deps.versions.sqlalchemy)", "dateutil=$($deps.versions.dateutil)",
    "debut=$($debut.ToString('dd/MM/yyyy HH:mm'))"
) | Set-Content -LiteralPath (Join-Path $dossier $FichierMeta) -Encoding UTF8
@(
    "Recette UI-432G - contexte local (NE PAS DIFFUSER : chemins du poste)",
    "Depot : $Depot", "Branche : $branche", "HEAD : $head", "origin/wx : $distant",
    "Python : $($deps.exe)", "Profil : $typeProfil ($profil)"
) | Set-Content -LiteralPath (Join-Path $dossier $FichierContexte) -Encoding UTF8
"etat=en_cours" | Set-Content -LiteralPath $execution -Encoding UTF8

Write-Host ""
Write-Host "Lancement de Noethys (diagnostic actif pour cette execution seulement)." -ForegroundColor Cyan
Write-Host "Utilisez Noethys normalement et laissez au moins une synchronisation AUTOMATIQUE se terminer." -ForegroundColor Cyan
Write-Host "Ne fermez pas cette fenetre PowerShell ; fermez Noethys normalement a la fin." -ForegroundColor Cyan
$sauve = @{ NOETHYS_SL_UI_DIAG = $env:NOETHYS_SL_UI_DIAG; PYTHONIOENCODING = $env:PYTHONIOENCODING; PYTHONPATH = $env:PYTHONPATH }
$codeSortie = ""
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
@("etat=termine", "code_sortie=$codeSortie", "duree_s=$([int]($fin - $debut).TotalSeconds)") |
    Set-Content -LiteralPath $execution -Encoding UTF8
foreach ($k in $suivis.Keys) {
    $etat = "inchange"
    if ($avant[$k] -ne (Empreinte $suivis[$k])) { $etat = "modifie_par_Noethys_pendant_utilisation" }
    Add-Content -LiteralPath (Join-Path $dossier $FichierMeta) -Value "$k=$etat" -Encoding UTF8
}

$res = Analyser-Recette $dossier $false
Write-Host ""
$res.resume | ForEach-Object { Write-Host $_ }
Write-Host ""
Write-Host "Dossier de recette : $dossier"
Write-Host "  A transmettre    : $(Join-Path $dossier $FichierExtrait)"
Write-Host "  Local seulement  : $FichierSortie, $FichierErreurs, $FichierContexte (NE PAS diffuser)"
exit $res.code
