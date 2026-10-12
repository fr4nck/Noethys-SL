# Stabilisation Noethys Vanilla

> Statut au 2026-09-07 : **NON STABLE — qualification en cours**.
>
> Branche de référence : `maintenance/vanilla`.

## Baseline auditée

L'audit UI/cycle de vie/DPI du 2026-09-07 a été conduit sur la branche `maintenance/vanilla`, dont le point de départ de l'audit était le commit :

`b09082726278d397b9f107ea470245ce51851fa3`

Le rapport détaillé est conservé dans :

`docs/VANILLA_UI_COMMAND_AUDIT.md`

Les deux documents de traçabilité sont des modifications **documentation uniquement**. Aucune correction runtime, métier, SQL, Connecthys ou packaging n'a été introduite par cet audit.

## Contexte de recette à conserver

- Recette humaine uniquement sur copie Docker locale des données, jamais sur production.
- Le candidat `74d25fdd8431eb7a167ab35cab8e1e8aa4e3bdc9` a fait l'objet d'une recette humaine, mais n'est pas le même SHA que la branche auditée et ses résultats ne valent donc pas validation automatique de `maintenance/vanilla`.
- Vanilla doit rester en **thème clair**, y compris lorsque Windows est en thème sombre, tant que le sombre n'est pas qualifié.
- Le comportement « Voir tout » est rejeté : la liste complète des consommations doit être directement visible.
- Aucun chantier Qt n'entre dans ce périmètre.

## État de qualification résumé

### Actions

- 36 commandes/parcours prioritaires recensés dans la passe actuelle.
- 2 disposent d'une preuve d'exécution disponible.
- 1 `OK`.
- 3 `KO`.
- 32 `NON TESTABLE` dans l'environnement de cette passe.

### Crashs / cycle de vie

- 1 crash confirmé : liste détaillée des consommations, fermeture pendant chargement puis réouverture immédiate, crash natif Windows `0xc0000005`.
- 0 exception Python/wx confirmée dans cette passe.
- 8 comportements de cycle de vie classés suspects et nécessitant reproduction ciblée.

### DPI / layout

- 1 défaut de layout confirmé : bouton **Modifier** de la liste détaillée des consommations créé mais absent du sizer et sans binding.
- Aucun défaut spécifiquement DPI n'est déclaré confirmé, faute d'exécution Windows interactive à 100/150/200 % pendant cette passe.
- La qualification thème clair sous Windows sombre reste obligatoire.

## P1 connu — liste détaillée des consommations

Le défaut prioritaire reste le crash natif reproductible :

1. ouvrir la liste détaillée des consommations ;
2. laisser le chargement démarrer ;
3. fermer avant la fin ;
4. rouvrir immédiatement ;
5. répéter ;
6. refaire avec la croix Windows ;
7. vérifier l'absence d'Application Error 1000 / `0xc0000005`.

La PR #359 apporte un correctif ciblé de cycle de vie : arrêt du timer de recherche, neutralisation de l'`objectGetter` et du cache du `FastObjectListView`, remise du compteur natif à zéro et cleanup idempotent. Elle ne doit **pas** être considérée validée avant passage du scénario ci-dessus sur le build Windows de recette.

## Anomalies importantes révélées par l'audit

- Le bouton **Modifier** de la liste détaillée des consommations est créé mais inaccessible : pas de sizer, pas de binding.
- Le chargement des consommations charge globalement les réponses des questionnaires individu avant de construire les lignes ; la lenteur observée doit être mesurée séparément du crash de fermeture.
- Le bouton/commande **Liste d'attente** possède bien une route statique jusqu'à `OuvrirListeAttente()` et `DLG_Attente`, mais a été observé sans effet lors d'une recette sur un autre candidat : reproduction obligatoire sur `maintenance/vanilla` avant toute correction.
- `DLG_Famille.Notebook` programme des `wx.CallLater` sans annulation explicite à la destruction ; le mapping entre indices du notebook et liste canonique des pages mérite une recette avec pages masquées.
- Le tableau de remplissage peut programmer une mise à jour automatique via `wx.CallLater` global sans hook de destruction explicite.
- Deux entrées de menu différentes utilisent le même code `liste_pieces_fournies`, ce qui rend leur représentation ambiguë dans le dictionnaire utilisé par les barres d'outils personnalisées.
- La couverture automatisée de la branche est insuffisante pour la stabilité UI : le workflow r2 construit et smoke-teste l'exécutable, mais ne pilote aucun parcours métier et ne couvre ni clavier ni DPI.

## CI existante

Le workflow `.github/workflows/vanilla-r2.yml` couvre notamment :

- compilation Python ;
- test du destinataire de crashreports ;
- import wxPython sur Windows ;
- build PyInstaller ;
- création installateur Inno Setup ;
- installation silencieuse ;
- lancement de `Noethys.exe` pendant environ 10 secondes ;
- vérification de conservation de la configuration ;
- création du portable.

Ce workflow ne constitue pas une validation UI fonctionnelle.

## Tests à ajouter avant de réduire fortement la recette humaine

Priorités :

1. boucle automatisée ouvrir/fermer/réouvrir consommations sur Windows ;
2. détection `0xc0000005` / Event Viewer ;
3. test cleanup FastObjectListView et timer de recherche ;
4. contrôle structurel des boutons créés mais non sizés/non bindés ;
5. unicité des codes de commandes ;
6. route complète Liste d'attente ;
7. base vide / zéro activité ;
8. destruction avec `CallLater`/timers en attente ;
9. fiche famille avec pages masquées ;
10. contrat « liste complète directe, pas de Voir tout » ;
11. Entrée/Echap/TAB/Shift+TAB ;
12. exports/impressions ;
13. contrôles de bornes/layout à 100/150/200 % ;
14. thème Windows sombre avec Vanilla restant claire.

## Validations humaines Windows encore obligatoires

- PR #359 sur le scénario exact du crash, y compris croix Windows et Event Viewer.
- Liste d'attente depuis menu et toolbar.
- Liste complète des consommations visible immédiatement.
- Thème clair sous Windows sombre.
- DPI 100 %, 150 %, 200 % sur fenêtres principales.
- Clavier et focus sur dialogues prioritaires.
- Exports, impressions et aperçus.
- Fermeture complète puis relance.

## Ordre recommandé

Le premier changement runtime recommandé après validation de ce rapport est **uniquement** le correctif de cycle de vie de la PR #359, sous réserve de réussite de la recette Windows native. La lenteur questionnaire, le bouton Modifier, la Liste d'attente et les autres anomalies doivent rester dans des correctifs séparés et seulement après reproduction/qualification.

## Garde-fous

- Ne pas déclarer Vanilla stable à ce stade.
- Ne pas mélanger Qt, Teamworks ou adaptations locales.
- Ne jamais tester sur production.
- Ne pas introduire de migration BDD dans ce chantier.
- Ne pas modifier Connecthys/Ivan dans ce chantier.
- Aucun refactoring général tant que les défauts bloquants et majeurs ne sont pas isolés et couverts.

## Addendum du 12/10/2026 (branches canoniques `main` / `wx` / `qt`)

`maintenance/vanilla` n'est plus la référence : les constats ci-dessus ont été revérifiés sur `main`, `wx` et `qt` (fichiers identiques).

- **P1 liste détaillée des consommations (PR #359)** : le nettoyage de cycle de vie (arrêt du timer de recherche, neutralisation de l'`objectGetter` et du cache, `SetItemCount(0)`, cleanup idempotent sur fermeture et croix) est **présent** sur les trois branches. Statut : **EN ATTENTE** de la recette Windows native du scénario ci-dessus (Event Viewer `0xc0000005`).
- **Bouton Modifier orphelin** : masqué (`b20cc82e` main, `ebd1b0e9` wx, `b5db5656` qt). Un scan AST de tout `noethys/` n'a trouvé que deux autres boutons créés sans placement : `CTRL_Liste_inscriptions.bouton_supprimer` (masqué, binding commenté en amont) et `CTRL_Badgeage_controles.CTRL_Importation.boutonTest` (panneau de test, toléré). Test structurel `tests/test_vanilla_boutons_places.py` en CI rapide (point 4 de la liste ci-dessus).
- Toujours **NON STABLE** : Liste d'attente, codes de commande dupliqués (`liste_pieces_fournies`), `CallLater` sans annulation, DPI et thème clair sous Windows sombre restent à reproduire ou recetter.

## Addendum du 12/10/2026 (2) — défauts utilisateur qualifiés

- **Crash natif des consommations : CAUSE RACINE TROUVÉE ET CORRIGÉE.** Reproduit sous Windows sur base fictive (défilement, saisie dans la recherche, fermeture par la croix, réouverture immédiate) : la version d'avant la PR #359 meurt en `0xC0000005` (3/3). Cause : le `wx.Timer` de `BarreRecherche` (`CTRL_ObjectListView`, ~150 listes) reste armé après destruction. Le seul arrêt du timer à la destruction suffit à faire survivre l'ancienne version (3/3) : le défaut menaçait toutes les listes avec recherche, pas seulement les consommations. Correctif générique (`CTRL_ObjectListView`, `OL_Individus`, `OL_Villes`) : main `64d15533`, wx `0d7c86ce`, qt `553ed375`. Version actuelle : 400 cycles sans crash. Test en sous-processus `tests/test_vanilla_consommations_fermeture.py` exécuté par la CI rapide Windows (verte).
- **Liste d'attente sans effet : NON REPRODUCTIBLE** sur le code actuel. Parcours réel (contrôle des effectifs → `OuvrirListeAttente` → `DLG_Attente`) rejoué en SQLite et sur MySQL 5.5 fictif, avec et sans activité sélectionnée : dialogue ouvert, lignes correctes, aucune exception. Le correctif de dates Python 3 (#360) explique probablement l'observation sur l'ancien candidat. Recette humaine à confirmer.
- **Code `liste_pieces_fournies` partagé : DÉJÀ CORRIGÉ** (`5e559d24`, #379 : `liste_pieces_manquantes`), présent et testé sur les trois branches.
- **`wx.CallLater` de la fiche famille et du remplissage : DÉJÀ CORRIGÉS** (#379, testés). Recensement des 55 `CallLater` : délais 0-10 ms à la construction, ou parcours rares ; `CTRL_Grille_renderers.Flash` (1 s) est du code mort. Timer d'info-bulle de `CTRL_Timeline` : aucun crash reproduit, ancienne version comprise, donc non modifié.
