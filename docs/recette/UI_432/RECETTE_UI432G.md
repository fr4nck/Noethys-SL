# Recette utilisateur ciblée — UI-432G (gel pendant la synchro Connecthys)

Objet : vérifier sur le poste réel que l'interface ne se fige plus pendant la
synchronisation **automatique** Connecthys, après le correctif
« synchro Connecthys sans contention GIL prolongée » (branche `wx`, `dff8a13f`).

État : correctif VALIDÉ sur banc et CI ; **correction du gel réel EN ATTENTE DE
RECETTE UTILISATEUR** tant que cette recette n'a pas été exécutée et analysée.

## Ce qui a été corrigé (et prouvé sur banc)

- Cause démontrée sur banc fictif (SQLAlchemy 2.0.55, version livrée) : la
  préparation de l'export (`Upload_data`) exécutait des secondes de Python pur
  (un objet et un INSERT par ouverture/consommation, puis un commit d'un bloc).
  wxPython rendant le GIL à chaque appel, tout traitement d'interface lancé en
  même temps (ouverture d'une grille, d'une fiche, etc.) était ralenti 5 à 20 fois.
- Correctif : insertion groupée, écriture par tranches dans la même
  transaction, et pause automatique de la synchro dès que l'interface est occupée.
- Mesures banc (1000 familles, 140 722 consommations fictives) : traitement
  d'interface de référence 0,25 s → **max 5,17 s avant, 1,18 s après** ;
  `Upload_data` 12,3 s → 6,3 s ; export identique.
- **Non démontré sur le poste réel** : volumes PMSL, MySQL et durée réelle de
  vos traitements d'interface diffèrent du banc.
- Environnement du poste (`.venv`) : Python 3.11.9, wxPython 4.2.5,
  **SQLAlchemy 2.0.52** (banc et build : 2.0.55), python-dateutil 2.9,
  mysqlclient. Les 10 tests du correctif, dont l'export réel `Upload_data`
  comparé aux sources sur base SQLite fictive, passent avec 2.0.52 : aucune
  mise à jour de dépendance n'est nécessaire.

## Bloc à coller dans PowerShell (5.1 ou 7)

Fermer Noethys avant de coller. Le bloc fait d'abord un passage à blanc (aucun
lancement), puis lance Noethys seulement si tout est conforme, et affiche
l'extrait anonymisé après fermeture.

```powershell
& {
    $depot = "C:\Users\Ordi\Documents\GitHub\Noethys"
    $lanceur = Join-Path $depot "tools\ui432g_recette.ps1"
    if (-not (Test-Path -LiteralPath $lanceur)) { Write-Host "Lanceur absent : executer 'git pull --ff-only origin wx' dans $depot" -ForegroundColor Red; return }
    Set-Location -LiteralPath $depot
    # 1) Passage a blanc : verifications seules, Noethys n'est PAS lance
    powershell.exe -NoProfile -File $lanceur -VerifierSeulement
    if ($LASTEXITCODE -ne 0) { Write-Host "Verifications en echec (code $LASTEXITCODE) : Noethys n'est PAS lance. Lire le motif ci-dessus." -ForegroundColor Red; return }
    # 2) Lancement reel : utiliser Noethys normalement, laisser au moins une synchro AUTOMATIQUE se terminer, puis fermer Noethys
    powershell.exe -NoProfile -File $lanceur
    $code = $LASTEXITCODE
    # 3) Recuperation de l'extrait anonymise (le seul fichier a transmettre)
    $d = Get-ChildItem -LiteralPath "$env:LOCALAPPDATA\NoethysSL-recette" -Directory -Filter "UI432G-*" -ErrorAction SilentlyContinue | Sort-Object Name | Select-Object -Last 1
    if (-not $d) { Write-Host "Aucun dossier de recette (code $code)." -ForegroundColor Red; return }
    $extrait = Join-Path $d.FullName "extrait-anonymise-UI432G.txt"
    if (-not (Test-Path -LiteralPath $extrait)) {
        Write-Host "Extrait absent (code $code). Pour analyser : powershell.exe -NoProfile -File `"$lanceur`" -Analyser `"$($d.FullName)`"" -ForegroundColor Yellow; return
    }
    Get-Content -LiteralPath $extrait -Encoding UTF8 -Raw | Set-Clipboard
    Write-Host "Extrait copie dans le presse-papiers : $extrait" -ForegroundColor Cyan
    if ($code -eq 11) { Write-Host "Si vous avez reduit Noethys vous-meme : powershell.exe -NoProfile -File `"$lanceur`" -Analyser `"$($d.FullName)`" -IconisationVolontaire" -ForegroundColor Yellow }
}
```

Si la politique d'exécution refuse le script, ajouter `-ExecutionPolicy Bypass`
après `-NoProfile` sur les deux lignes `powershell.exe` : cela ne vaut que
pour ce processus et ne modifie pas la politique du système.

Récupérer plus tard le dernier extrait (après fermeture) :

```powershell
$d = Get-ChildItem -LiteralPath "$env:LOCALAPPDATA\NoethysSL-recette" -Directory -Filter "UI432G-*" | Sort-Object Name | Select-Object -Last 1
Get-Content -LiteralPath (Join-Path $d.FullName "extrait-anonymise-UI432G.txt") -Encoding UTF8 -Raw | Set-Clipboard
Invoke-Item $d.FullName
```

## Ce que vérifie le lanceur (`tools/ui432g_recette.ps1`)

Il refuse (code 2, rien n'est lancé) si : dépôt introuvable, branche autre que
`wx`, correctif `dff8a13f` ou `bb7dc1b6` absent de HEAD, fichier suivi modifié
sous `noethys\` (conservé, jamais écrasé), `.py` non suivi sous `noethys\`,
interpréteur absent ou ambigu (`PYTHONHOME`), dépendance absente, SQLAlchemy
< 1.4, dateutil ≥ 3, wx < 4.2, modules chargés hors du dépôt ou sans les
marqueurs du correctif, autre instance de Noethys ouverte (exécutable ou
`Noethys.py`). Il ne fait jamais `pull`, `checkout`, `reset` ni `stash`, et ne
modifie pas la politique d'exécution.

Il lance `Noethys.py` du dépôt avec le `.venv` du dépôt (seul interpréteur du
poste avec `mysqlclient`), avec `NOETHYS_SL_UI_DIAG=1` pour ce seul processus
(variables restaurées ensuite). Le lanceur n'écrit jamais dans le profil
`noethys\Portable`, les bases ni `journal.log` ; il compare seulement les
empreintes de `Config.json` et `Customize.ini` avant/après et signale une
modification faite **par Noethys** pendant l'utilisation (préférences), ce qui
est normal.

Fichiers dans `%LOCALAPPDATA%\NoethysSL-recette\UI432G-<date>\` :

| Fichier | Diffusion |
|---|---|
| `extrait-anonymise-UI432G.txt` | **à transmettre** |
| `meta-anonyme.txt`, `execution.txt` | techniques (versions, code de sortie) |
| `stdout-COMPLET-NE-PAS-DIFFUSER.log`, `stderr-COMPLET-NE-PAS-DIFFUSER.log`, `contexte-local.txt` | **local uniquement** (URL Connecthys, erreurs SQL, chemins du poste) |

L'extrait ne contient que les lignes `NOETHYS_UI_DIAG` filtrées clé par clé
selon le schéma fermé du diagnostic (valeurs typées : entiers, `True`/`False`,
noms d'opération, `fichier.py:fonction:ligne`) ; toute autre valeur est
masquée (`masque=N`). Les URL et les lignes non diagnostiques ne sont jamais
copiées : seuls des marqueurs `synchro_debut` / `synchro_terminee
upload_data_s=…` sont ajoutés.

## Verdicts automatiques

| Verdict | Code | Condition |
|---|---|---|
| **NON RESPECTÉE** | 10 | gel ≥ 5 000 ms (`retard_boucle`, `blocage_thread` ou opération sans événements) ou `ne_repond_pas=True`, quel que soit le reste |
| **NON CONCLUANTE** | 12 | aucune synchronisation terminée observée (`Temps upload_data`, imprimé seulement après réponse `True` du serveur), synchro commencée sans fin, lancement interrompu, sortie anormale (code ≠ 0, ex. 0xC0000005), erreur fatale, journal absent, diagnostic inactif, valeur hors schéma |
| **À REVOIR** | 11 | iconisation observée, cause inconnue (relancer l'analyse avec `-IconisationVolontaire` si la réduction était volontaire) |
| **RÉUSSIE** | 0 | au moins une synchronisation terminée, sortie normale, diagnostic actif, aucun des cas ci-dessus |

Chaque gel est situé **pendant** ou **hors** synchronisation (ordre des lignes
entre le début du téléchargement et `Temps upload_data`). Un gel hors
synchronisation reste NON RESPECTÉE, avec une note : il relève d'un traitement
d'interface (voir #434), pas du seul correctif UI-432G.

Testé sans Noethys : `tests/test_ui432g_lanceur_recette.py` (journaux
synthétiques : synchro normale, sans synchro, gel, ne répond pas,
iconisation, arrêt anormal, journal incomplet, valeurs sensibles, synchros
multiples, seuil 5 000 ms ; refus sur dépôts git temporaires), sous Windows
PowerShell 5.1 et PowerShell 7.

## Limites de la recette

- Synchro automatique ou manuelle non distinguable dans le journal : ne pas
  lancer de synchro manuelle pendant la recette.
- Lignes non horodatées : seul l'ordre situe un gel par rapport à la synchro.
- Le journal Connecthys du panneau n'est pas collecté.
- Une session sur un poste : une RÉUSSIE ne prouve pas l'absence de gel dans
  toutes les configurations ; une NON RESPECTÉE hors synchro ne met pas
  forcément en cause le correctif.

## Scénario

1. Pendant qu'une synchronisation automatique est en cours (icône/état
   « Synchronisation… »), utiliser Noethys comme lors du gel observé :
   traitement des demandes Connecthys, ouverture de la grille de réservation,
   navigation dans les fiches.
2. Ne pas forcer de synchro manuelle ; ne pas fermer la fenêtre PowerShell.
3. Fermer Noethys normalement après au moins une synchro terminée (« À jour »).

## Si un gel persiste

Relever dans l'extrait la ligne `blocage_thread` la plus longue : `point`,
`point_synchro`, `veille_retard_ms`, `ne_repond_pas`. Elle indique si le thread
wx attend la base (`GestionDB.py:ExecuterReq`), exécute un code précis, ou si
la synchro est en cause (`point_synchro` dans `UTILS_Portail_synchro.py`).
