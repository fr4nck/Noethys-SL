# Noethys SL wx — PR #375 : verrouillage de l'apparence claire wxAUI

Ce document accompagne la PR #375 (« Noethys SL 0.1.0 — verrouiller
l'apparence claire et les cadres »), branche `fix/noethys-sl-0.1.0-light-ui`,
base `release/noethys-sl-0.1.0`. Il ne remplace pas les tests automatisés
(`tests/test_vanilla_apparence_claire.py`, `tests/test_noethys_sl_ui_assets.py`) :
il couvre ce qu'eux ne peuvent pas prouver — le rendu réel à l'écran sous
Windows en thème sombre — et fixe la frontière architecturale du module
introduit pour cela.

## 1. Frontière architecturale — `noethys/Utils/UTILS_AUI_Apparence.py`

- Ce module appartient exclusivement à la couche **Noethys SL wx**
  (présentation wxPython / wx.lib.agw.aui). Il ne contient et ne doit
  contenir **aucune logique métier** (pas d'accès DB, pas de règles de
  facturation/réservation/planning, aucune dépendance vers `GestionDB` ou
  les modules `Ctrl`/`Dlg` métier).
- Il constitue le **point de centralisation unique** du rendu wxAUI pour
  Noethys SL : `NoethysSLDockArt` (art provider du `AuiManager` principal)
  et `NoethysSLToolBarArt` (art provider de chaque `AuiToolBar`) y sont
  définis une seule fois et réutilisés partout où `Noethys.py` crée un
  manager ou une barre d'outils — aucune couleur AUI n'est fixée ailleurs
  dans le code applicatif.
- Conséquence pratique de cette centralisation : c'est la base naturelle
  pour une future vraie palette claire/sombre pilotable (au lieu d'un
  verrouillage univoque sur le clair). Le jour où Noethys SL proposera un
  thème sombre choisi par l'utilisateur, c'est dans ce module que la
  bascule de palette devra être implémentée — pas dans `Noethys.py` ni
  dans les écrans métier, et pas en réintroduisant `ModernDockArt` ou un
  quelconque contournement d'API privée.
- Ce module ne doit pas grossir avec des responsabilités étrangères
  (icônes, DPI, traduction...) : ces sujets restent dans leurs modules
  `Utils/UTILS_*` respectifs.

Aucun changement de comportement AUI n'accompagne ce document : il est
strictement documentaire.

## 2. Recette manuelle Windows sombre — à exécuter, pas exécutée

**Ce document ne prétend pas que cette recette a été réalisée.** C'est un
protocole prêt à l'emploi pour la qualification visuelle réelle sur un
poste Windows en thème sombre (ex. PMSL001), qui ne peut pas être vérifiée
par la CI headless.

Pré-requis : Windows configuré en thème sombre (Paramètres > Personnalisation
> Couleurs > Choisir votre couleur : **Sombre**), avant de lancer Noethys SL.

| # | Étape | Résultat attendu |
|---|-------|-------------------|
| 1 | Démarrage de l'application | Aucune bande ni cadre noir parasite dans l'AUI (légendes de panes, barres d'outils) dès l'affichage de la fenêtre principale |
| 2 | Maximiser puis restaurer la fenêtre | Le rendu clair est conservé après le changement de taille ; pas de réapparition de surface noire |
| 3 | Redimensionner la fenêtre (bords/coins, plusieurs tailles) | Le rendu clair est conservé pendant et après le redimensionnement |
| 4 | Déplacer / re-docker une barre d'outils personnalisée (Paramétrage > barres d'outils, ou glisser une barre existante) | Pas de scintillement noir/clair pendant le déplacement ; rendu final clair, cohérent avec le reste de l'interface |
| 5 | Charger une perspective enregistrée (menu Affichage > Perspectives, ou équivalent) | Le rendu reste clair après le changement de disposition des panneaux |
| 6 | Pendant que Noethys SL reste ouvert : basculer Windows clair → sombre → clair (Paramètres Windows, sans fermer Noethys) | À chaque bascule, l'interface Noethys SL reste claire — aucune surface sombre n'apparaît après le retour à un thème clair, ni pendant le passage par le thème sombre |

**Résultat global attendu :** aucune surface noire parasite à aucune étape,
aucune régression du rendu clair historique de Noethys SL 0.1.0.

Toute étape qui ne donnerait pas le résultat attendu doit être signalée
avec : étape précise, capture d'écran, version de Windows, thème
Windows exact, wxPython/wxWidgets (`wx.version()`), et SHA du commit testé.

## 3. Ce que la CI ne couvre pas actuellement

Voir le commentaire correspondant sur la PR #375 pour l'état réel des
workflows GitHub Actions sur cette branche (aucun trigger `pull_request`
ne couvre actuellement `release/noethys-sl-0.1.0` ni les fichiers touchés
par cette PR ; `tests/test_vanilla_apparence_claire.py` — qui exerce
`UTILS_AUI_Apparence.py` — n'est exécuté que par des workflows
`workflow_dispatch` manuels ou restreints à la branche
`maintenance/vanilla`). Ce point est un constat, pas une modification :
aucun workflow n'a été changé à ce titre.
