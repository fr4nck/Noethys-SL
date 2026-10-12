# Noethys Vanilla — pilote de recette Windows interactif (prototype)

Prototype strictement séparé du code métier. Il pilote le vrai `Noethys.exe` sous Windows comme un utilisateur et n'appelle aucun handler Noethys directement.

## Choix technique

- `pywinauto==0.6.9`.
- UI Automation (`uia`) en priorité pour les contrôles nommés et la croix Windows.
- Win32 en complément pour les HWND, listes natives, hiérarchie et diagnostic.
- actions utilisateur via `click_input()`, `double_click_input()`, `right_click_input()` et vraies frappes clavier quand elles sont sûres.
- aucun clic à coordonnées fixes dans le scénario pilote.
- attentes explicites, polling borné et détection de fenêtre non responsive (`IsHungAppWindow` + `SendMessageTimeout(WM_NULL)`).

Le choix est volontairement hybride : Noethys mélange `wx.Frame`, `wx.Dialog`, `wx.Button`, `wx.SearchCtrl`, `wx.ListCtrl` virtuel, AGW/AUI et contrôles owner-drawn. Le premier run interactif doit produire les arbres UIA **et** Win32 avant toute généralisation des sélecteurs.

## Dépendances

```text
pywinauto==0.6.9
comtypes==1.4.16
pywin32==312
psutil==7.2.2
Pillow==12.3.0
```

Installation dans la session Windows de recette :

```powershell
python -m pip install -r tools\windows_ui_recipe\requirements.txt
```

## Garde-fous BDD

Le pilote refuse de lancer Noethys si :

- Windows n'est pas utilisé ;
- l'exécutable ne s'appelle pas `Noethys.exe` ;
- le profil n'a pas le marqueur `NOETHYS_UI_RECIPE_PROFILE=1` ;
- `Roaming\noethys\Config.json` est absent ;
- `nomFichier` ne désigne pas une base réseau/MySQL ;
- le host ou le nom de base ne correspond pas aux valeurs attendues ;
- le host ne résout pas exclusivement vers la boucle locale ;
- `assistant_demarrage` n'est pas configuré pour empêcher l'assistant de démarrage de perturber le scénario.

`APPDATA` et `LOCALAPPDATA` du processus Noethys sont redirigés vers le profil jetable. Ce chemin correspond au comportement réel de `UTILS_Fichiers.GetRepUtilisateur()` : `appdirs.user_config_dir(..., roaming=True)` puis sous-répertoire `noethys`.

Les actions génériques dont le libellé évoque suppression, envoi, facturation ou publication sont refusées par le prototype. Aucune écriture Connecthys/Ivan n'est autorisée.

`prepare_profile.ps1` copie uniquement un `Config.json` de recette déjà préparé. Il ne crée, ne migre et ne modifie aucune base.

## Préparation

```powershell
.\tools\windows_ui_recipe\prepare_profile.ps1 `
  -ProfileRoot "C:\Noethys-Recipe-Profile" `
  -RecipeConfig "C:\recette\Config.json"
```

## Exécution locale interactive

```powershell
.\tools\windows_ui_recipe\run.ps1 `
  -Exe "C:\Noethys-Vanilla\Noethys.exe" `
  -ProfileRoot "C:\Noethys-Recipe-Profile" `
  -ExpectedDbHost "127.0.0.1" `
  -ExpectedDbName "NOETHYS_RECETTE" `
  -Repeat 5
```

Chaque étape produit exactement l'un des statuts :

- `PASS`
- `FAIL`
- `TIMEOUT`
- `CRASH`
- `NON_AUTOMATISABLE`

`NON_AUTOMATISABLE` ne masque jamais une exception fonctionnelle : il est réservé à une limite démontrée du pilote (par exemple contrôle non exposé de manière sûre ou événement interne impossible à provoquer en boîte noire).

Le détail est écrit dans `artifacts\noethys-ui\scenario.jsonl` et le comptage final dans `summary.json`.

## Premier lot A → E

### A — Démarrage (`WIN-01`)

1. lancer `Noethys.exe` avec le profil isolé ;
2. attendre la fenêtre principale ;
3. vérifier le processus et la réactivité ;
4. capturer les arbres UIA et Win32.

### B — Affichage (`WIN-01`, cycle `WIN-13`)

`Affichage` est un menu principal, pas un dialogue unique. Pour obtenir un dialogue réel sans modifier la configuration, le pilote ouvre **Affichage → Sauvegarder la disposition actuelle**, vérifie `Sauvegarde d'une disposition`, ferme par **Annuler**, rouvre puis ferme par **Echap**. Aucun `OK` n'est envoyé.

### C — Liste d'attente (`WIN-06`, cycle `WIN-13`)

Ouvrir `Consommations → Liste d'attente`, vérifier la fenêtre, fermer par **Fermer**, rouvrir immédiatement, puis fermer avec **Echap**.

### D — Liste détaillée des consommations (`WIN-04`)

1. ouvrir `Consommations → Liste détaillée des consommations` ;
2. fermer au premier instant où le dialogue est réellement visible ;
3. rouvrir immédiatement ;
4. répéter fermeture/réouverture ;
5. fermer par la vraie croix Windows ;
6. vérifier que Noethys reste vivant et responsive.

La branche prototype contient déjà le correctif de PR #359. Le résultat doit donc être consigné comme **CORRECTIF EXISTANT — VALIDATION RUNTIME REQUISE**, jamais comme découverte/correction du pilote.

### E — Cycle de vie wx (`WIN-13`)

- ouverture/fermeture et ouverture/annulation : couverts par B/C ;
- liste virtuelle : `FastObjectListView` est recherché via UIA puis Win32, puis fermeture/réouverture réelle ;
- timer actif : le pilote tape réellement dans le `wx.SearchCtrl`, ce qui déclenche `EVT_TEXT` et arme le `wx.Timer`, puis ferme immédiatement ;
- callback tardif : observation de 1,25 s, au-delà du délai maximal de 1000 ms codé dans `BarreRecherche.OnDoSearch`, avec contrôle continu du processus et de la réapparition du dialogue ;
- double fermeture physique : `NON_AUTOMATISABLE` dans ce prototype, car le deuxième clic après destruction peut tomber sur un contrôle différent sous la fenêtre ; un double `WM_CLOSE` serait une fausse recette utilisateur ;
- `wx.CallAfter` arbitraire après destruction : `NON_AUTOMATISABLE` sans instrumentation métier. Le chemin réel du timer est exercé à la place.

## Détection d'échec et artefacts

Sur `FAIL`, `TIMEOUT`, `CRASH` et `NON_AUTOMATISABLE`, le pilote conserve autant que possible :

- WIN, section, étape, action, attendu, obtenu ;
- durée et horodatage ;
- titre de la fenêtre active ;
- PID, état vivant/sorti, hung/responsive ;
- screenshot multi-écrans ;
- traceback du pilote ;
- dumps UIA et Win32 ;
- fin de `journal.log` du profil et lignes wx/traceback détectées ;
- événements Application corrélés, notamment Event ID 1000 ;
- codes d'exception trouvés, dont `0xc0000005`.

L'absence d'un Event 1000 n'est jamais utilisée comme preuve d'absence de crash.

## Contrôles wx : ce que le pilote vérifie

Probables candidats accessibles, à confirmer par le premier run sur **le vrai binaire** :

- `wx.Frame` / `wx.Dialog` ;
- menus wx ;
- `wx.Button` / `CTRL_Bouton_image.CTRL` ;
- `wx.SearchCtrl` ;
- certaines listes `wx.ListCtrl`.

Candidats à risque, donc jamais supposés accessibles :

- AUI/AGW notebooks, toolbars et panes ;
- contrôles owner-drawn ;
- `FastObjectListView` virtuel ;
- `wx.BitmapButton` sans nom accessible ;
- contrôles dont UIA ne remonte ni nom ni rôle et dont Win32 n'expose qu'un HWND générique.

Le pilote écrit des dumps d'accessibilité sur les fenêtres clés. Ces dumps servent à décider ensuite quel backend/sélecteur est fiable ; ils ne valent pas preuve fonctionnelle par eux-mêmes.

## Croix Windows

La fermeture par croix cherche le vrai bouton de `TitleBar` via UI Automation et exécute un clic utilisateur. Il n'existe volontairement **aucun fallback `WM_CLOSE`** pour cette étape. Si la croix n'est pas exposée de façon sûre, le scénario doit le signaler, pas fabriquer un PASS.

## Session Windows et GitHub Actions

Une session Windows utilisateur active et déverrouillée est requise pour `click_input()`, focus et clavier.

`.github/workflows/vanilla-windows-ui-recipe.yml` sépare :

1. `contract` sur `windows-latest` : installation des dépendances, compilation et tests non interactifs uniquement ; **ce job n'est jamais une validation Windows fonctionnelle** ;
2. `live-ui` : seulement sur `[self-hosted, Windows, vanilla-ui-recipe]`, déclenché manuellement avec `live=true`.

Le job live refuse la Session 0 et vérifie qu'un `explorer.exe` existe dans la même session que le runner. La machine doit disposer localement du binaire de recette, du profil jetable et de la base Docker. Le runner ne doit pas être utilisé comme simple service Windows en Session 0.
