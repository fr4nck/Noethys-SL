# Reprise du chantier Noethys-SL — état au 08/10/2026

Document de transmission (Claude Code → Codex). Mettre à jour en fin de chaque session.


## Lot limité Noe-032 — ZIP partiel sur fichier absent — 10/10/2026

- **Départ vérifié** : `main = wx = qt = 025112dd55744988989f0c3f321e76557f0fe11d` ; `master = b0be3c7ebdf2d69d6028eb4fd6fc08e340a68b9e`, toujours branche par défaut. [CI wx #38033543533](https://github.com/fr4nck/Noethys-SL/actions/runs/38033543533) : succès au SHA antérieur `32841c42`. Consignes lues : `AGENTS.md`, ce document, PMSL-Arch `main` (`cbe3e6e65b53d98783a5192846979aedbe375465`), politique de développement, ADR-006/010 et gouvernance Actions.
- **Code : `4b5dc5103d8af14e5eab1500368be43e55061415`**. Deux lignes ferment puis suppriment le ZIP temporaire lorsqu'un fichier local manque. Test historique `test_missing_local_file_closes_zip_and_removes_partial_archive` repris avec assertions intactes et harnais AST isolé ; deux cas ajoutés : absence après une première entrée avec destination existante préservée, sauvegarde complète réussie. Test inclus en CI rapide ; restauration SQL inchangée.
- **25 tests historiques inchangés réutilisés** (`test_noe_032_backup_integrity.py`, `test_noe_032_restore_flow.py`) : 25/25 sur le module `master`, mocks et données fictives. Sur `main` initial : 5 succès / 5 échecs / 15 erreurs ; candidat : 6 succès / 5 échecs / 14 erreurs. Seul le test du lot passe de défaut à succès ; les 19 écarts préexistants hors lot (SQL, exceptions sous-processus, nettoyage email…) restent EN ATTENTE. Journaux hors Git dans l'espace Codex : `tmp/qualification-noe032/main-before.log` et `main-after.log`.
- **Qualification** : verrou ZIP Windows reproduit avant correction ; 15 tests ciblés réussis après, compilation et diff contrôlés. [CI main #38036079406](https://github.com/fr4nck/Noethys-SL/actions/runs/38036079406) : SUCCÈS syntaxe Ubuntu et 96 tests Windows, réseau isolé, sans packaging. CI wx : [wx #38036255934](https://github.com/fr4nck/Noethys-SL/actions/runs/38036255934), SUCCÈS Ubuntu et Windows au même SHA de code.
- **Propagation prouvée** : les trois branches étaient identiques, sans commit propre à perdre. Après CI main, push atomique fast-forward non forcé de `wx`/`qt` vers `4b5dc510`, HEAD distants revérifiés. Une seule note documentaire pour ce lot, également propagée par fast-forward.

| Périmètre au commit de code `4b5dc510` | `main` | `wx` | `qt` |
| --- | --- | --- | --- |
| ZIP partiel, 3 tests | VALIDÉ + CI | VALIDÉ, arbre identique + CI wx | VALIDÉ code commun ; UI Qt EN ATTENTE |
| Gardes réseau/fermeture ZIP antérieures, 12 tests conservés | VALIDÉ + CI | CODE IDENTIQUE + CI wx | CODE IDENTIQUE ; UI Qt EN ATTENTE |
| Protections SQL avancées / restauration MySQL réelle | EN ATTENTE / STOP-GATE | EN ATTENTE / STOP-GATE | EN ATTENTE / STOP-GATE |

- **PR #104 examinée, non dupliquée** : HEAD `bbbddddec529074729acc1bed5f947361b3ee4a9`, MySQL 5.5.62 épinglé par digest, `127.0.0.1:3308`, `.env` hors Git, scripts start/import/reset. README : ancienne ADR-004 à remplacer par ADR-006 ; comptage de tables insuffisant pour qualifier la restauration. Inventaire Docker en lecture seule : seul `noethys-mysql57` actif (`127.0.0.1:3307`), laissé intact.
- **Suite / limite** : aucune recette SQL réelle dans ce lot indépendant. Réutiliser #104 sur environnement isolé et données 100 % synthétiques pour qualifier dumps complets/tronqués, manifeste, marqueur et postconditions avant portage SQL. Aucune base existante touchée, migration, nouvelle branche, fusion globale, suppression ou force-push ; `master` et PR préservées.

## Synchronisation et durcissement Noe-032 — 10/10/2026

- **Non-régression interbranches** : invariant ajouté dans `AGENTS.md` et matrice initiale documentée par le commit `edc014bc9de286cee24c5f19d32c743763246eca`. Les anciennes références `wx` (`98af4873`) et `qt` (`6deee441`) étaient des ancêtres stricts de `main`, avec respectivement 0 commit unique ; chacune a été avancée par fast-forward non forcé vers `edc014bc`, sans perte ni conflit. Run [wx #38032993554](https://github.com/fr4nck/Noethys-SL/actions/runs/38032993554) : Ubuntu et tests Windows **SUCCÈS**.
- **Lot indépendant Noe-032** : le commit `c6130084c04e023a5a014bdd51b694176f76d1ee` reprend uniquement cinq appels `fichierZip.close()` avant les retours d'annulation ou d'erreur dans `Restauration`, présents historiquement dans `master`. Le test `tests/test_noethys_sl_restore_network_config.py` couvre les chemins locaux/réseau factices et vérifie statiquement les six retours précoces. Aucune restauration SQL, migration ni base réelle.
- **Qualification des tests** : run [main #38033235384](https://github.com/fr4nck/Noethys-SL/actions/runs/38033235384) **ÉCHEC DU TEST FICTIF UNIQUEMENT** : entrée sans suffixe `.sql` n'activant pas le chemin d'annulation réseau. Commit `32841c42d8f45f34ff96d4f8737c8ecf546b995c` : correction d'une seule ligne dans la donnée de test ; le code de production `c6130084` reste inchangé. Run [main #38033397162](https://github.com/fr4nck/Noethys-SL/actions/runs/38033397162) : Ubuntu et tests Windows **SUCCÈS**.
- **Propagation contrôlée** : `main`, `wx` et `qt` ont été vérifiées au même SHA `32841c42d8f45f34ff96d4f8737c8ecf546b995c` après deux fast-forwards non forcés des branches `wx` et `qt`. CI de requalification `wx` : [#38033543533](https://github.com/fr4nck/Noethys-SL/actions/runs/38033543533), **SUCCÈS (tests Ubuntu et Windows)**.
- **Matrice actualisée de non-régression au SHA `32841c42` :**

| Périmètre commun / interface | `main` | `wx` | `qt` |
| --- | --- | --- | --- |
| Deux garde-fous réseau Noe-032, tests `a09df2cc` et `64f68c0e` | VALIDÉ (CI main) | CODE IDENTIQUE, SUCCÈS (tests Ubuntu et Windows) | CODE IDENTIQUE ; recette Qt EN ATTENTE |
| Fermeture ZIP sur annulations/erreurs, `c6130084` et `32841c42` | VALIDÉ (CI main #38033397162) | CODE IDENTIQUE, SUCCÈS (tests Ubuntu et Windows) | CODE IDENTIQUE ; recette Qt EN ATTENTE |
| Résolution `ObjectListView`, `eab750f6` | VALIDÉ | CODE IDENTIQUE, SUCCÈS (tests Ubuntu et Windows) | CODE IDENTIQUE ; recette Qt EN ATTENTE |
| Restaurations MySQL/MariaDB réelles et protections SQL avancées de `master` | NON INTÉGRÉ / EN ATTENTE | NON INTÉGRÉ / EN ATTENTE | NON INTÉGRÉ / EN ATTENTE |
| Interface Qt native | NON APPLICABLE | NON APPLICABLE | NON QUALIFIÉE |

- **Environnement de recette existant** : la PR [#104](https://github.com/fr4nck/Noethys-SL/pull/104) contient déjà `dev/db/compose.yml` (MySQL 5.5.62 épinglé, port `127.0.0.1:3308` par défaut) et scripts PowerShell de démarrage. Elle n'est **ni fusionnée ni qualifiée localement dans cette session** ; ne pas dupliquer son travail. Ce serveur ancien doit être lancé uniquement en environnement jetable isolé, avec données synthétiques et secrets hors Git.
- **Stop-gates / suite** : 25 tests Noe-032 historiques `master` réussis sur mocks (run #35826834598) mais **non requalifiés sur `main`**. Aucun serveur réel MySQL/MariaDB de recette accessible dans cette session : manifeste SQL, marqueur terminal, postconditions et restauration d'une base fictive demeurent bloqués. `master` reste la branche GitHub par défaut, le contenu divergent est préservé, huit PR ouvertes. Aucune branche créée, aucun force-push, PR close ou suppression de branche ; aucun packaging lourd.
- **Prochaine action** : qualifier la PR #104 ou un environnement équivalent sur une machine de recette, lancer sauvegarde puis restauration sur **données 100 % synthétiques**, requalifier les 25 tests contre le candidat `main`, puis intégrer les protections avancées sous preuve avant une éventuelle bascule de branche par défaut.

## Non-régression interbranches — contrôle initial du 10/10/2026

- **Source de vérité :** comparer les SHA et arbres Git du dépôt `fr4nck/Noethys-SL` ; ne pas déduire l'équivalence du simple nom des branches.
- **SHA avant synchronisation :** `main` = `28ebcaf7aa096001f49c354486e38f641914a746`, `wx` = `98af487389c4a1fd392f3b1fc2c75186066e6edc`, `qt` = `6deee441050fb653c95901a8ae4dd1145c4ed96e`. `master` = `b0be3c7ebdf2d69d6028eb4fd6fc08e340a68b9e`, toujours branche GitHub par défaut, à conserver.
- **Comparaisons prouvées :** `wx` est ancêtre strict de `main` (12 commits seulement sur `main`, zéro commit propre à `wx`) ; `qt` est également ancêtre strict (14 commits seulement sur `main`, zéro commit propre à `qt`). Pas de merge global requis. Ces chiffres sont ceux **avant** le commit de cette politique et doivent être revérifiés immédiatement avant un éventuel fast-forward.
- **Protection permanente :** invariant de non-régression maintenant dans `AGENTS.md`. Pour chaque future publication, vérifier la propagation des correctifs communs et les comportements propres aux interfaces. Une ascendance Git seule ne vaut pas recette Windows/Qt.
- **Matrice au point de contrôle (avant propagation)** :

| Ensemble testé / correctif | `main` | `wx` | `qt` |
| --- | --- | --- | --- |
| Noe-032 — refus sauvegarde réseau sans connexion (`a09df2cc`, CI #37981580013) | VALIDÉ | ABSENT, à propager | ABSENT, à propager |
| Noe-032 — refus restauration réseau sans connexion (`64f68c0e`, CI #37982029069) | VALIDÉ | ABSENT, à propager | ABSENT, à propager |
| `ObjectListView` — résolution imports (`eab750f6`, CI #37972096356 puis #37979402584) | VALIDÉ | ABSENT, à propager | ABSENT, à propager |
| Restauration MySQL/MariaDB réelle, manifeste SQL, postconditions | EN ATTENTE (non intégré) | EN ATTENTE | EN ATTENTE |
| Parcours UI spécifiques Qt | NON APPLICABLE à ce stade (code actuel wx) | NON APPLICABLE | EN ATTENTE (aucune recette Qt) |

- **Propagation prévue :** mettre `wx` et `qt` au HEAD du socle commun par fast-forward avec vérification de SHA, puis constater réellement les nouvelles références. Cette section constitue l'état *avant* l'opération : ne pas conclure que la propagation a eu lieu sur cette seule documentation.
- **Stop-gates inchangés :** MySQL/MariaDB jetable requis avant qualification réelle des restaurations et avant reprise des protections SQL avancées ; recette UI Windows et Qt nécessaire avant leur publication. Aucune nouvelle branche, aucun force-push, suppression ou modification des données de production.

## Lot Noe-032 qualifie — 09/10/2026

- **Branche et code vérifiés** : `main` à `64f68c0eaae13a2771944ff49cbb556810123849` avant cette note. `master` n'a pas été modifiée ; GitHub conserve `master` comme branche par défaut.
- **TERMINÉ / VALIDÉ — Sauvegarde réseau sans paramètres** : commit `a09df2cc386c6321ae9db7682436dbb0b551a0f3`. `Sauvegarde` refuse les fichiers réseau lorsque `dictConnexion is None` avant toute création de ZIP, y compris en mode mixte local + réseau. Trois tests unitaires isolés dans `tests/test_noethys_sl_backup_network_config.py` (réseau seul, mixte, chemin local conservé), ajoutés à la CI rapide. Run [#37981580013](https://github.com/fr4nck/Noethys-SL/actions/runs/37981580013) : succès syntaxe Ubuntu et tests Windows.
- **TERMINÉ / VALIDÉ — Restauration réseau sans paramètres** : commit `64f68c0eaae13a2771944ff49cbb556810123849`. `Restauration` refuse le réseau sans `dictConnexion`, ferme le ZIP et s'arrête avant toute extraction locale, même en restauration mixte. Trois tests unitaires isolés dans `tests/test_noethys_sl_restore_network_config.py` (archive factice, refus réseau et mixte, parcours local conservé), ajoutés à la CI rapide. Run [#37982029069](https://github.com/fr4nck/Noethys-SL/actions/runs/37982029069) : succès syntaxe Ubuntu et tests Windows.
- **Portée exacte** : deux gardes de refus et six tests, sans modification de schéma, de formats `.nod/.noc`, de code de restauration SQL exécutée, de production ou de données réelles. Aucune branche créée, aucune branche ni PR supprimée/fermée, aucun force-push ni packaging lourd. Vérification de tests sur GitHub Actions ; aucune recette MySQL réelle ni tests intégrés locaux de toute l'application lors de cette passe.
- **CONFIRMÉ SUR `master`, NON RÉIMPORTÉ** : le run historique [#35826834598](https://github.com/fr4nck/Noethys-SL/actions/runs/35826834598) réussissait les 25 tests Noe-032 (10 intégrité de backup, 15 flux restauration) contre des simulations MySQL. Les blobs des deux fichiers de test et du module du commit testé sont identiques à ceux du HEAD `master` contrôlé. Ceci ne valide PAS leur exécution sur `main`.
- **BLOQUÉ / STOP-GATE** : transfert du manifeste SHA-256 SQL, analyse de dump tronqué, marqueur terminal, postconditions MySQL (tables, vues, événements, fonctions) et nettoyage des secrets sans preuve d'une recette contre un serveur MySQL/MariaDB jetable. L'environnement de cette session ne possède pas de serveur ou client MySQL/MariaDB ni Docker/Podman et ne peut pas accéder à GitHub par `git clone` local. Aucun test de restauration sur une base existante, ni publication.
- **PROCHAINE ACTION CONCRÈTE** : sur une machine/runner de qualification disposant de MySQL ou MariaDB, créer des bases **entièrement fictives et jetables**, sans profil Portable ni accès réseau de production ; qualifier à la fois dumps complets, tronqués, hérités sans manifeste, échecs de sous-processus et restauration partiellement réussie ; requalifier les 25 tests historiques sur le candidat `main` sans affaiblir les assertions ; porter ensuite les protections Noe-032 par petits lots et mesurer les postconditions.
- **Bascule de branche par défaut : NON FAITE**. `master`, `wx`, `qt`, RC et les huit PR restent des références à préserver tant que les travaux uniques ne sont pas qualifiés.

## Poursuite consolidation — 09/10/2026 (soir)

- **Inventaire confirmé** : `master` reste divergente. Fonctions sauvegarde/restauration MySQL et contrôles Noe-032 présents dans `master` mais pas dans `main` : ne pas fusionner intégralement ni effacer `master` avant qualification ciblée. Exemples : `_AjouterManifesteIntegriteSQL`, `_VerifierPostconditionRestaurationMySQL` ; tests `tests/test_noe_032_backup_integrity.py` et `tests/test_noe_032_restore_flow.py` restés sur `master`.
- **Correction isolée appliquée sur `main`** : commit `05022fae5946a4db486b3ed973b9d70453b0abaf`, `UTILS_Sauvegarde.GetListeFichiersZIP` ferme l'archive ZIP avec `with`, comme dans `master` ; test sans base réelle `tests/test_noethys_sl_backup_zip_lifecycle.py`. Commit `b0d71728fe44e52e2483e1353299eb35744ca282` ajoute ce test à la CI rapide.
- **CI** : run de qualification du dernier commit [#37979402584](https://github.com/fr4nck/Noethys-SL/actions/runs/37979402584), en attente du résultat au moment de la rédaction. Le run précédent a été annulé par la concurrence automatique.
- **Aucune autre modification** : aucun `master`/RC/WIP modifié, aucune création ou suppression de branche, aucun force-push, aucun schéma SQL modifié. La branche par défaut demeure `master`. Ne pas confondre CI rapide et qualification complète de restauration réseau.
- **Suite** : porter le lot Noe-032 uniquement après revue des 2 suites de tests, des contrats historiques `.nod/.noc` et d'une restauration réelle sur base fictive isolée. Puis traiter les domaines tiers, interventions et synchronisation sans réactiver implicitement d'anciens comportements Repens.

## Mise à jour de consolidation — 09/10/2026

- **But confirmé :** `main` sera la branche par défaut après qualification. Seules les branches de développement `main`, `wx`, `qt` seront conservées à terme ; aucune nouvelle branche ne doit être créée. Consignes applicables dans `AGENTS.md`.
- **Opérations Git réalisées :** `main` a avancé par fast-forward depuis `6deee441050fb653c95901a8ae4dd1145c4ed96e` jusqu'au HEAD `wx` `98af487389c4a1fd392f3b1fc2c75186066e6edc` (deux commits CI seulement). Ensuite, ajout du déclenchement rapide sur `main` par `b36f037ce9934d508f71bdbbff8466e663e54845`, puis ajout des règles `AGENTS.md` via `f8f889ba98145f47f5d6c37d9711751f7779c087`.
- **Non effectués :** aucune création/suppression de branche, aucune fusion de `master`, aucun force-push, aucun changement de branche par défaut, aucune modification SQL ou du code métier, aucun test sur la base réelle.
- **Références au moment du contrôle :** `wx` = `98af4873` ; `qt` = `6deee441` ; `master` = `b0be3c7e`. `master` est toujours la branche par défaut sur GitHub et doit être préservée : son arbre diverge fortement de `main` (modules Repens, synchronisations, interventions, autres code/tests/docs). Ne jamais inférer d'un nombre de commits que tout le code correspondant est absent ou présent.
- **Qualification du 09/10 :** premier run [#37971043856](https://github.com/fr4nck/Noethys-SL/actions/runs/37971043856) : syntaxe OK, trois échecs Windows sur un import `ObjectListView` masqué par `sys.path`. Correctif ciblé `eab750f65c6674edcf4068f922c034bde28d18cb` (`Chemins.py` et test), correction de l'alias du test `7b3a0307147116f0f8e348390fb1cb50a5b8dbe6`. Run [#37972096356](https://github.com/fr4nck/Noethys-SL/actions/runs/37972096356) sur `7b3a0307` : **succès Ubuntu et tests Windows**, sans packaging lourd. Ceci ne remplace ni recette Windows complète ni validation Connecthys réelle.
- **Prochaine étape :** classer les différences métier encore utiles de `master` et des branches RC/WIP, ne réimporter que les correctifs prouvés, requalifier sur la ligne cible, puis changer la branche par défaut dans les paramètres GitHub après l'accord de publication. Ne pas effacer `master` ni fermer une PR non intégrée avant préservation vérifiée.


## 1. Dossier, branches, commits

- Dossier principal : `C:\Users\Ordi\Documents\GitHub\Noethys` (poste 5700x), dépôt `fr4nck/Noethys-SL`.
- Invariant PMSL-Arch : trois branches seulement, `main` (moteur), `wx`, `qt`. Au 08/10/2026 elles pointent sur le même commit (tout le code actuel est wx ; la séparation moteur/UI n'est pas commencée).
- Base de `main` : ligne RC2/RC2.1 en service (`fea13ce7`, tag `noethys-sl-0.1.0-rc.2.1`), puis :
  - fusion des deux commits divergents `integration/rc2-convention-recovery-20261004` (`cc39c887`) ;
  - fusion de la ligne de secours `rescue/noethys-sl-20261004` / `d9b70c2b` (`7be696f9`) ;
  - reprise thématique du travail non commité de `Noethys-RC2-clean` (instantané de diagnostic `d08e37fb`, objet local non référencé) ;
  - corrections listées ci-dessous.
- Worktrees existants (non supprimés) : `Noethys-RC2` (`integration/rc2-convention-recovery-20261004`, propre, intégrée) et `Noethys-RC2-clean` (HEAD détaché `8b3789d9`, **modifications non commitées conservées** ; éléments volontairement non repris : `DialogFondu`/`UTILS_Transitions`, ancienne variante Word, suppression du Toaster d'accueil).
- PMSL-Arch : `main` porte `66e5e06` (registre TRV-016/031/032) et `9dc3f97` (règle du titulaire de l'adhésion). La branche locale de travail de ce dépôt reste `docs/profil-poste-5700x-2026-09-24`.

## 2. Corrections terminées et preuves

| Sujet | Commits | Preuve |
|---|---|---|
| Boutons Mode / Émetteur de la saisie d'un règlement (TAILLE_IMAGE float refusé par Phoenix) | `c17fdf27` | `tests/test_noethys_sl_parametrage_reglement.py` (échoue sans correctif) ; artefact : dialogues ouverts par Paramétrage > Comptabilité, ajout + persistance en base fictive ; RC2.1 publiée : aucune fenêtre |
| Adhésions : chevauchement refusé, au plus une adhésion à venir | `746bbd6e` | `test_noethys_sl_adhesions.py` |
| Adhésions : signalement « à vérifier » (fenêtre ou historique) | `9eac1977` | `test_noethys_sl_adhesions_signalement.py` ; simulation portail (sans Connecthys) |
| Adhésions : sauvegardes simultanées (SQLite `BEGIN IMMEDIATE`, MySQL `GET_LOCK` + InnoDB exigé), aucune écriture partielle | `aee1626e` | `test_noethys_sl_adhesions_concurrence.py` : deux processus, SQLite et MySQL 5.7 local ; ancien code = 2 adhésions + 2 prestations |
| Adhésions : titulaire (structure personne morale / chaque personne d'une famille) | `7f56aecf` | `test_noethys_sl_adhesions_titulaire.py` (6/8 échouent avec l'ancien code) |
| Sortie Word : écriture atomique, refus des mots-clés inconnus | `f0d90147`, doc `200e148f` | `test_vanilla_convention_docx.py` |
| Devis d'une famille sans adresse (None refusé par wx) | `cdf8ecc5` | `test_noethys_sl_devis_adresse_incomplete.py` ; PDF de devis contrôlés (avec/sans adresse, règlement non ventilé) |
| Noedoc : blocs flottants des conventions sans débordement | `d16d907c`, `e6c9f2de` | `test_noethys_sl_noedoc_ecoulement.py` ; captures Windows 3 modèles × 2 tailles |
| Garde des tests (production) | `4a3739f7`, `03b56fca`, `aee1626e`, `b9c8b386` | suite complète + 72 modules seuls : 0 connexion au pilote MySQL |
| Module `etat_global` exécuté par unittest | `da8cd8ec` | 40 tests, 1 échec attendu documenté |
| Incident et diagnostics | `5dafe288`, `9f0f007f` | voir § 9 |
| Procédure de recette et fichier fictif | `169a93b0` | `docs/recette/RECETTE_CANDIDAT_2026-10-08.md` |

Résultat global au commit `e6c9f2de` : 661 tests OK (1 échec attendu), sous garde réseau et avec le MySQL local.

## 3. Modifications non commitées

Aucune dans `Noethys` hors éléments locaux ignorés volontairement (jamais à committer) : `local-diff.txt`, `local-status.txt`, `portable-inventory.txt`, `tracked-files.txt` (inventaires préexistants) et `noethys/Portable/` (**profil réel pointant vers la base de production**).

## 4. Commandes

Depuis `C:\Users\Ordi\Documents\GitHub\Noethys` :

```powershell
# Suite complète (garde réseau incluse dans chaque module)
.venv310\Scripts\python.exe -m compileall -q noethys tests
.venv310\Scripts\python.exe -m unittest discover -s tests
# Avec le serveur MySQL local de test (voir § 5)
$env:NOETHYS_TEST_MYSQL_HOST="127.0.0.1"; $env:NOETHYS_TEST_MYSQL_PORT="3307"
$env:NOETHYS_TEST_MYSQL_USER="root"; $env:NOETHYS_TEST_MYSQL_PASSWORD="<mot de passe du conteneur>"
.venv310\Scripts\python.exe -m unittest tests.test_noethys_sl_adhesions_concurrence
```

Build portable (reproduit `.github/workflows/noethys-sl-windows.yml`) dans un environnement propre :

```powershell
python -m venv <build>\venv
<build>\venv\Scripts\python.exe -m pip install -r requirements.txt   # sans la ligne « pyttsx »
<build>\venv\Scripts\python.exe -m pip install pyttsx3 wxPython==4.2.5 "pyinstaller>=6,<7"
<build>\venv\Scripts\pyinstaller.exe --noconfirm --clean packaging/vanilla-noethys.spec
# puis BUILD-INFO.txt et Compress-Archive -Path dist/Noethys (voir le workflow)
```

`.venv310` ne contient ni pytest ni PyInstaller ; Inno Setup (Setup.exe) n'est pas installé sur le poste.

## 5. MySQL Docker de test

- Conteneur `noethys-mysql57`, MySQL 5.7.44, InnoDB par défaut, `127.0.0.1:3307`, utilisateur `root` ; mot de passe connu de Franck, **jamais dans Git**.
- Bases existantes à ne pas modifier : `docker_mad*`, `docker_mairies*`, `docker_pelemele_*`.
- Les tests créent puis suppriment uniquement des bases `zz_test_adh_<aléa>` ; `_garde_reseau.ServeurMySQLDeTest()` n'autorise que l'hôte local déclaré.

## 6. Artefact portable existant (candidat local non publié)

- `C:\Users\Ordi\Documents\GitHub\Noethys\dist\Noethys-SL-0.1.0-rc.2+e6c9f2de-local-Windows-portable.zip`
- Commit `e6c9f2deb172b9f0041bc6d1a9c11b29b717ebe2` ; SHA-256 `5967EDADC68DE302D14B62A3640F2A1449EBCBAA25E36F4973B6CB06AB362FE8`.
- Bytecode des 29 modules modifiés depuis RC2.1 identique au commit. Titre affiché encore « RC2 » ; `BUILD-INFO.txt` porte le commit.

## 7. Sauvegarde

`C:\Users\Ordi\Documents\Sauvegardes-Noethys\Noethys-avant-consolidation-20261008-112618.tar` (1,58 Go, Noethys + Noethys-RC2 + Noethys-RC2-clean, `.git` commun ; `git fsck` propre sur extraction). Seule copie de l'état d'origine de `Noethys-RC2-clean` hors du worktree.

## 8. Processus et ressources temporaires

- Processus actifs : `C:\Noethys\Noethys.exe` (instance de l'utilisateur, **ne pas toucher**) ; conteneur `noethys-mysql57`. Aucune instance de test restante.
- Temporaires (scratchpad Claude Code, supprimables) : environnement de build, environnement pywinauto, copie extraite de l'artefact avec profil Portable fictif et fichier `Recette`, RC2.1 publiée téléchargée, captures et scripts de recette.

## 9. Incident du 08/10/2026 (production)

Rapport : `docs/incidents/2026-10-08-tests-base-reseau.md` ; famille TRV-032 dans PMSL-Arch `docs/AUDIT_BUGS_TRANSVERSAUX.md`. Quatre exécutions de la suite avant la garde, 31 connexions chacune ; au plus une écriture possible (`parametres` email/timeout vide) ; **aucune écriture confirmée**. Contrôle en lecture seule : `docs/diagnostics/diagnostic_adhesions.sql`, requêtes 9 et 9 bis.

## 10. Règle métier des adhésions

Référence : PMSL-Arch `docs/REGLES_ADHESION_ACTIVITES.md` ; implémentation `docs/metier/ADHESIONS_AUTOMATIQUES.md`.

- Structure (association, école/collectivité, organisme, entreprise : personne morale titulaire de la famille) : **une adhésion pour la structure**, quelles que soient ses sections, activités ou représentants.
- Famille de personnes physiques : **une adhésion par personne qui participe**, couvrant toutes ses activités, jamais commune à la famille.

## 11. Tâches restantes (par priorité)

**P0**
1. Diagnostic réel d'Arthur (famille 688) **non effectué** : exécuter en lecture seule `docs/diagnostics/diagnostic_adhesions.sql` (identification par rattachement, puis par IDindividu) ; ne corriger aucune donnée.
2. **Validé en recette fictive par Codex** : boutons Mode / Émetteur depuis la saisie d'un règlement dans le portable, avec création effective des deux éléments. La recette par le comptable sur données fictives reste possible ; ne jamais ouvrir la production avec le candidat.
3. Contrôle en lecture seule de la ligne `parametres` de l'incident (requêtes 9 / 9 bis).

**P1**
4. Recette **125 % et 150 %** effectuée : règlement et devis accessibles ; crash Noedoc au double-clic isolé et corrigé. Nouveau portable à retester graphiquement ; voir § 13 pour les limites exactes.
5. **Corrigé et validé** : crash à la fermeture après « Rappel de sauvegarde ». Arrêt des timers du bandeau avant destruction (commit source `db27767b`) ; nouveau portable testé sur Recette, fermeture normale avec code 0. Voir § 12.
6. **Aucune recette Connecthys réelle** : seul le traitement d'une demande de réservation a été simulé localement (grille, adhésion, signalement).
7. Avant publication officielle : numéro de version (RC3), notes de version, reciblage du workflow `noethys-sl-windows.yml` (déclencheur actuel `release/noethys-sl-0.1.0`), Setup via la CI.

**P2 — à préserver, ne rien supprimer sans décision de Franck**
8. Ligne **Upgrade** `origin/master` (1 478 commits propres, non intégrée à `main`).
9. 144 branches distantes non intégrées à `main` (10 déjà intégrées : `integration/rc2-…`, `release/noethys-sl-0.1.0`, `maintenance/vanilla`, etc.).
10. Trois **stashes** du 25/09/2026 (dépôt commun) à examiner avant toute résorption.
11. Worktrees `Noethys-RC2` et `Noethys-RC2-clean` : résorption après recette et accord sur les éléments non repris.
12. Famille de défauts « valeur par défaut évaluée à l'import » (`GenerationNomDoc`, 14 occurrences) : à ratisser.


## 12. Reprise Codex — 08/10/2026

- Push vérifié : `main`, `wx`, `qt` sur `a66e404a` ; PMSL-Arch `main` sur `9dc3f97`.
- Portable e6c9f2de testé dans une extraction dédiée avec le fichier SQLite fictif
  **Recette**, sans profil réel. Parcours fiche famille > saisie d'un règlement :
  bouton Mode, création `MODE RECETTE CODEX`, bouton Émetteur, création
  `EMETTEUR RECETTE CODEX` ; les deux éléments apparaissent dans leurs listes.
  Le règlement de test a été annulé ; aucune base réelle touchée.
- Crash reproduit dans ce portable : exception Windows `0xc0000005` dans
  `wxbase32u_vc140_x64.dll`. Reproduit aussi depuis les sources sans fichier
  ouvert et sans Noedoc. La piste Noedoc n'explique pas ce cas.
- Isolation : sans le panneau éphéméride, la fermeture réussit ; arrêter le
  seul timer de défilement avant la fermeture suffit aussi. Désinstaller le
  gestionnaire AUI seul ne suffit pas. Correctif : arrêter le bandeau et son
  timer de pause après acceptation de la fermeture, avant destruction wx.
- Nouveau test `test_noethys_sl_fermeture_windows.py` : fermeture réelle de
  l'accueil dans un sous-processus Windows, profil temporaire, réseau interdit.
  Succès après correctif, zéro tentative de connexion réseau.
- Le portable e6c9f2de existant **ne contient pas** ce nouveau correctif tant
  qu'un nouveau build n'a pas été produit et vérifié.
- Restent : DPI 125 % / 150 %, confirmation des données réelles d'Arthur,
  recette Connecthys réelle et résorption des anciens travaux après validation.
- Deux instances de l'installation réelle ont été constatées. Celle lancée
  à 14:23 semble provenir du premier essai de lancement du portable via
  Computer Use. Aucune interaction métier ni fermeture sur ces instances.

Validation du correctif : suite `python -m unittest discover -s tests` terminée
avec code 0. Des avertissements de nettoyage de bases temporaires et les
exceptions volontairement simulées restent imprimés par les tests existants.


Nouveau portable local construit avec le commit source `db27767b` :
`C:\Users\Ordi\Documents\GitHub\Noethys\dist\Noethys-SL-0.1.0-rc.2+db27767b-local-Windows-portable.zip`.
SHA-256 : `8ca961a436cc73ae5e5233de91e593293fb4cc702e3caf89b48715ab8c5ebc05`.
Intégrité ZIP vérifiée ; aucun profil Portable ni base inclus dans l'archive.
Le nouvel exécutable démarre et propose l'ouverture du fichier fictif Recette.
Après identification manuelle par Franck, la fermeture graphique du nouveau
portable sur le fichier fictif Recette a été validée : croix de la fenêtre,
« Pas maintenant » au rappel de sauvegarde, processus terminé avec code 0.
La fermeture depuis les sources est également validée par le test.
Le titre reste RC2 : aucune nouvelle version publique ni release créée.


## 13. Recette DPI et crash au double-clic Noedoc — 08/10/2026

Écran Windows 2560 × 1440 ; mise à l'échelle 125 %, puis 150 %, vérifiée
dans les Paramètres. Candidat `db27767b`, fichier SQLite fictif Recette.
Aucune donnée réelle ni aucun profil de production utilisé.

- À 125 % : fiche famille, saisie de règlement, boutons Mode et Émetteur
  ouverts et fermés ; commandes accessibles. Devis fictif généré et ouvert
  dans Adobe Reader malgré un règlement de 50 € non ventilé. Deux messages
  Windows « Font Capture », exception `0xc06d007e`, sont apparus pendant
  l'ouverture de l'aperçu ; Franck les a fermés. Causalité non établie.
- À 150 % : mêmes parcours règlement/Mode/Émetteur accessibles ; devis
  fictif généré et ouvert dans Reader sans nouveau message Font Capture.
  L'éditeur Noedoc s'ouvre et se ferme via le bouton Modifier.
- Au double-clic sur « Facture par défaut », le portable s'arrête à 125 %
  et à 150 % : événements Windows 1000, `0xc0000005` puis `0xc000041d`,
  module `_core.cp310-win_amd64.pyd`. Reproduction depuis le code source
  sur une copie temporaire de Recette avec garde réseau.
- Trace faulthandler : `FloatCanvas.GetHitTestColor`, appelé depuis
  `GUIMode.OnLeftUp`, lit le point `(289, 257)` dans un tampon `(20, 20)`
  avant le premier dessin. AlphaPixelData n'effectue pas de contrôle des
  bornes ; le relâchement du double-clic provoque la lecture native invalide.
- Correctif isolé `027ffe7e` : CanvasNoedoc contrôle l'existence et les
  dimensions du tampon de sélection avant lecture. Hors tampon : aucune
  sélection ; dans le tampon : comportement FloatCanvas conservé.
- Vérification graphique du code corrigé à 150 % : double-clic depuis la
  liste des modèles, dessin complet, sélection d'un bloc et affichage des
  propriétés, Annuler puis fermeture de la liste et de l'accueil ; code 0.
- Cinq tests ciblés passent : trois `test_noethys_sl_noedoc*.py`, un
  `test_noedoc_texte_ui.py`, un `test_noethys_sl_fermeture_windows.py`.
  Le nouveau test exerce dans un sous-processus les coordonnées négatives,
  les bords et le point réel du crash, les pixels valides, la priorité du
  tampon de premier plan et l'absence de tampon. Réseau interdit.

Nouveau portable local (correctifs fermeture + Noedoc), commit source
`027ffe7e98faa67478934db3bdca1919bf8658d7` :
`C:\Users\Ordi\Documents\GitHub\Noethys\dist\Noethys-SL-0.1.0-rc.2+027ffe7e-local-Windows-portable.zip`.
SHA-256 : `778485c3ba9aa36317604f0b2afc3f33dd8b954834ca2d728fa270bc27bdd998`.
Build terminé, intégrité ZIP vérifiée, aucun profil Portable dans l'archive.
Un profil fictif séparé a été préparé dans l'extraction de recette.

Validation graphique du nouveau portable `027ffe7e` terminée :
- À 150 % : double-clic sur le modèle, dessin complet, sélection d'un bloc,
  propriétés affichées, Annuler puis fermeture des fenêtres et du processus.
  Aucun crash observé ; code de sortie non recueilli pour cette exécution.
- À 125 % : même parcours, puis fermeture de l'accueil ; code de sortie 0
  recueilli sur le processus conservé depuis son lancement.

La recette DPI est ciblée : elle ne valide pas exhaustivement l'éditeur,
les autres écrans ou toutes les résolutions. Les messages Font Capture
restent une anomalie non attribuée. L'affichage Windows est actuellement
à 125 % ; la valeur habituelle de Franck reste à confirmer pour restauration.
Arthur réel, contrôle de l'incident et recette Connecthys réelle restent
en attente. Aucun tag, release ou déploiement ; anciens travaux préservés.


## 14. Élagage local vérifié — 11/10/2026

Demande de Franck : élaguer les branches/worktrees et les fichiers locaux
d'audit. Aucun changement de code métier ni de branche distante.

- Trois branches locales supprimées par `git branch -d`, après preuve qu'elles
  sont des ancêtres de main `694ccacc2d37ba71298b56e7ddb6901be6a55d2d` :
  `integration/rc2-convention-recovery-20261004` (`a78c6581`),
  `release/noethys-sl-0.1.0` (`aa88f53a`),
  `rescue/noethys-sl-20261004` (`d9b70c2b`). Aucun travail unique à perdre.
- Worktree propre `C:\Users\Ordi\Documents\GitHub\Noethys-RC2` retiré par
  `git worktree remove`, sans forçage. Ses 2 760 fichiers, dont 272 caches
  ignorés, sont archivés et vérifiés par SHA-256 avant retrait.
- Neuf fichiers d'audit archivés puis retirés du dossier principal : les cinq
  fichiers de `audit-branches-20261011-022224/`, `local-diff.txt`,
  `local-status.txt`, `portable-inventory.txt`, `tracked-files.txt`.
- Archives conservées dans
  `C:\Users\Ordi\.codex\.chatgpt-projects\g-p-6a9e93a502648191a942e5ece9d8ebea\elagage-20261011` :
  `original-all-refs.bundle`, `github-all-refs.bundle`, `audits-locaux.zip`,
  `Noethys-RC2-clean-integrated-worktree.zip` (ce dernier contient le worktree
  propre **Noethys-RC2**, pas le worktree WIP **Noethys-RC2-clean**).
  Les bundles sont vérifiés par Git, les ZIP contrôlés entrée par entrée et
  les empreintes enregistrées dans `backup-manifest.json`.

Préservés et vérifiés après retrait : main/master/wx/qt locaux, tags, trois
stashes, les deux profils Portable (empreintes inchangées), et le worktree
`Noethys-RC2-clean` à HEAD détaché `8b3789d9` avec ses 32 fichiers suivis
modifiés et ses fichiers non suivis. Ses différences et son inventaire restent
identiques. Aucun test sur base ou profil réel, aucune migration.

GitHub : 63 branches distantes inventoriées et toutes revérifiées aux mêmes
SHA après intervention ; huit PR toujours ouvertes avec mêmes têtes/bases :
#422, #384, #369, #366, #355, #112, #104, #102. Les noms canoniques et toutes les
têtes/bases de PR sont protégés. Parmi les 49 autres branches, aucune n'est
entièrement ancêtre d'une référence protégée. Ceci ne prouve pas l'absence
d'une intégration squash : leur qualification fichier/comportement reste
EN ATTENTE, donc aucune suppression distante effectuée.

État du dossier principal après nettoyage, avant ce commit documentaire :
seul `?? noethys/Portable/`, aucune modification suivie. Branches locales
restantes : main, master, wx, qt ; worktrees restants : Noethys et
Noethys-RC2-clean. La copie isolée Codex de propagation Nomadhys est conservée
comme espace de preuves, distincte des worktrees historiques.

Têtes distantes inchangées : main `694ccacc2d37ba71298b56e7ddb6901be6a55d2d`,
wx `dcede8170874dd79cd9a5b5825bc3b4ed85feb62`,
qt `8902e655f93cebabdc84ff3ab8ea1f1ac89b73e0`,
master `b0be3c7ebdf2d69d6028eb4fd6fc08e340a68b9e`.
La présente note est un commit documentaire local sur main, non publié.
CI : aucune nouvelle exécution demandée, aucun packaging ou release.

Suite : qualifier les apports squash et les travaux uniques des 49 branches
historiques par petits lots ; comparer les sources WIP de Noethys-RC2-clean
avec main avant archivage/retrait éventuel. Ne pas restaurer le fichier .git
de l'archive du worktree tel quel ; utiliser la sauvegarde Git et recréer un
worktree historique seulement sur décision explicite de restauration.


## 15. Qualification des branches historiques et élagage distant — 11/10/2026
Suite explicitement demandée par Franck après l’élagage local. Les 49 branches
historiques hors références canoniques et têtes/bases de PR ont été examinées
contre les 14 références protégées. Inventaire de 325 PR, dont huit ouvertes.
Une PR fermée sans fusion n’a jamais été traitée comme une preuve d’intégration.

Méthode : pour chaque source/cible, calcul de l’ancêtre commun puis liste
complète des fichiers modifiés dans le delta source. Comparaison des blobs Git,
des modes de fichier et des suppressions avec l’arbre de la cible conservée.
Critère de retrait : tous les fichiers du delta final sont identiques dans
une même référence protégée. L’archivage de l’historique complet couvre aussi
les commits intermédiaires. Ceci qualifie la conservation du contenu pour
élagage, sans qualification métier globale ni annonce de synchronisation.

### Cinq suppressions distantes réellement effectuées

| Branche supprimée | SHA source | Contenu conservé dans | SHA cible | Fichiers identiques |
| --- | --- | --- | --- | --- |
| candidate/vanilla-20260907 | 451e8e35635aeb8179566ae7175a784387282f2b | feature/vanilla-conventions | c2c3e87a5b7dd883d397b6b1a7d8965997bd34ed | 1 |
| fix/rc2-fiscal-age-reference-year | 82128134e3070efc13e5c977fff39c774c5bee65 | rc/noethys-sl-0.1.0-rc.2 | 91d9e625d96c5a1460d42dda053db509fa28d181 | 8 |
| fix/rc2-fiscal-reportlab-import | 0a6e217da224fb3f2daddb5b74ad1154eb4da007 | main | 694ccacc2d37ba71298b56e7ddb6901be6a55d2d | 1 |
| fix/rc2-network-users-list-index | ec7389322b697122be8c11220942a7b84f3cc8a9 | rc/noethys-sl-0.1.0-rc.2 | 91d9e625d96c5a1460d42dda053db509fa28d181 | 4 |
| fix/wx-period-controller-final | 243b87aab71129e200cdf165815ac507f52abbde | design-form-density-standard | f96fa35865462500f12ad2caee98027e488f3955 | 2 |

Suppression atomique, sans force. Contrôle de l’ensemble des refs distantes
avant exécution et garde pre-push vérifiant les SHA annoncés pour chacune
des cinq suppressions ; la garde accepte le SHA attendu et rejette un SHA
modifié dans ses deux vérifications. Les cinq têtes sont présentes dans
github-all-refs.bundle, dont l’intégrité et les refs sont revérifiées.
Après suppression : **58 branches distantes**, toutes aux SHA inchangés ;
huit PR ouvertes inchangées (titres, descriptions, brouillons, têtes/bases) :
#102, #104, #112, #355, #366, #369, #384, #422. Aucun nouveau nom de branche,
aucune fusion, aucun changement de branche par défaut, tag ou release.
Références de suivi locales obsolètes nettoyées par fetch --prune.

### Matrice des 44 branches conservées

Ces branches présentent encore au moins un fichier différent des références
comparées. Une différence ne signifie pas automatiquement un correctif absent :
elle peut être un apport unique, une variante ou une évolution ultérieure.
Leur retrait est donc EN ATTENTE de qualification ciblée des comportements.

| Branche conservée | SHA source | Meilleure comparaison | Fichiers différents / delta | Statut de retrait |
| --- | --- | --- | --- | --- |
| agent/windows-ci-audit | 7df621ea3a30 | master | 7/9 | EN ATTENTE |
| agent/windows11-pyinstaller | f85f77266eec | master | 60/63 | EN ATTENTE |
| audit/vanilla-black-ui-rex | bcee84abff89 | main | 1/1 | EN ATTENTE |
| audit/vanilla-deep-scan-20260826 | cacafa37eb31 | main | 4/4 | EN ATTENTE |
| audit/vanilla-final-undefined-names | 8ae3a36f9394 | feature/vanilla-conventions | 3/8 | EN ATTENTE |
| audit/vanilla-ui-command-inventory | eef718234412 | main | 7/7 | EN ATTENTE |
| audit/vanilla-upstream-630ef | 58dcab19fd0e | main | 2/2 | EN ATTENTE |
| build/vanilla-windows-portable | 4d5dda48269b | rc/noethys-sl-0.1.0-rc.2 | 22/50 | EN ATTENTE |
| chatgpt/noethys-convention-ui-activites-20260929 | 7cd062c3f634 | rc/noethys-sl-0.1.0-rc.2 | 23/51 | EN ATTENTE |
| chore/noethys-sl-requirements-documentation | d3964671af35 | main | 1/1 | EN ATTENTE |
| chore/workflows-consolidation | f28861260cf2 | master | 1/4 | EN ATTENTE |
| claude/noethys-windows-ci-audit-qy5m9t | 3b847c6b2957 | master | 25/25 | EN ATTENTE |
| diagnostic/vanilla-ui-black-surfaces | f7362db86d47 | main | 1/1 | EN ATTENTE |
| feat/noethys-sl-afas-previsionnel | 108dc5f5e61e | main | 1/2 | EN ATTENTE |
| feat/noethys-sl-rc1-convention-finalise | f6cac3302a2f | main | 18/28 | EN ATTENTE |
| feat/noethys-sl-vacances-sportives | 77f2be447110 | main | 1/2 | EN ATTENTE |
| feat/rc2-reception-quotient | f48450935bb1 | rc/noethys-sl-0.1.0-rc.2 | 1/15 | EN ATTENTE |
| feature/extensions-registry | 9174ba32a45e | master | 4/4 | EN ATTENTE |
| feature/noe-060-reporting | dcfce2954011 | master | 1/1 | EN ATTENTE |
| feature/noe-062-conventions | f85fd51ee404 | master | 2/2 | EN ATTENTE |
| feature/noe-062-mises-a-disposition | c69f3c80325e | master | 8/8 | EN ATTENTE |
| feature/noe-062b-groupes-structures | 203fff34134c | master | 4/4 | EN ATTENTE |
| feature/noe-062b-roles-contacts | 177b4c3dcd1b | master | 4/4 | EN ATTENTE |
| feature/noe-063-portail-consolide | 55b2b129e67e | master | 21/21 | EN ATTENTE |
| feature/noe-063b-rss-atom-connecthys | 8f84f5edb72b | master | 12/12 | EN ATTENTE |
| feature/noe-063d-tarifs-ui | 20d5b15c1adb | master | 21/21 | EN ATTENTE |
| fix/noe-062b-hardening | 752645c5a772 | master | 4/4 | EN ATTENTE |
| fix/noethys-sl-aui-docking-minimize | aac763f24480 | rc/noethys-sl-0.1.0-rc.2 | 3/12 | EN ATTENTE |
| fix/noethys-sl-aui-guides-fantomes | 7704ee753687 | rc/noethys-sl-0.1.0-rc.2 | 4/12 | EN ATTENTE |
| fix/noethys-sl-light-only | ccdfb82bcf1b | master | 3/3 | EN ATTENTE |
| fix/noethys-sl-mailjet-consolidation | 51ee128a60de | rc/noethys-sl-0.1.0-rc.2 | 2/16 | EN ATTENTE |
| fix/noethys-sl-mailjet-email-confirmation | 9e0945b5d0a4 | rc/noethys-sl-0.1.0-rc.2 | 6/16 | EN ATTENTE |
| fix/rc2-network-stopgate-1 | cf5f9fbe6ccd | rc/noethys-sl-0.1.0-rc.2 | 40/40 | EN ATTENTE |
| fix/rc2-pr385-compatible | ba67c6b9a5fc | rc/noethys-sl-0.1.0-rc.2 | 3/13 | EN ATTENTE |
| fix/vanilla-no-black | 7c39f16ab148 | main | 15/15 | EN ATTENTE |
| fix/windows-installable-config | fbdebc8b6ef4 | master | 5/5 | EN ATTENTE |
| noe-041-portable-mode | 3cf6cbfe5d6f | design-form-density-standard | 5/9 | EN ATTENTE |
| noe-042-rc-gate | 085115c40fa5 | design-form-density-standard | 1/3 | EN ATTENTE |
| noe-062-programmation-occurrences | 88904fc780a0 | master | 4/4 | EN ATTENTE |
| noe-062c-lieux-execution-seances | be059ccd4804 | master | 5/7 | EN ATTENTE |
| poc/qt-theme-isole | cba459cd62cb | master | 54/54 | EN ATTENTE |
| refactor/ui-list-tools-repens | 52ed49bf888b | master | 14/23 | EN ATTENTE |
| refactor/ui-navigation-repens | 6bf8a4cceb8b | master | 1/2 | EN ATTENTE |
| test/vanilla-windows-ui-driver-prototype | be87c00ea51a | main | 10/10 | EN ATTENTE |

Preuves détaillées : content-audit.json (chaque fichier, blobs source/cible,
ancêtres communs et cibles), pr-history.json, remote-cleanup-plan.json et
remote-cleanup-result.json, dans le dossier local de sauvegarde indiqué au §14.
Le bundle sauvegarde aussi les 44 branches conservées.

Les arbres de main/wx/qt/master distants sont inchangés : aucune nouvelle
exécution de tests ni CI requise pour une suppression de refs sans changement
de contenu. Les 55 tests par branche du lot Nomadhys ne sont pas présentés
comme qualification de ces travaux historiques.
Localement : Portable, tags, trois stashes, branches master/wx/qt et worktree
WIP Noethys-RC2-clean préservés. main reçoit uniquement cette note documentaire,
en second commit local non publié après e59f3400. Seul Portable reste non suivi.
Suite : revue par lots des différences restantes ; aucune suppression de
travail non qualifié ni réimportation métier implicite.


## 16. Élagage qualifié, lot documentaire et tests — 12/10/2026

Suite demandée par Franck ; publication des notes documentaires autorisée.
Les 44 branches restantes sont triées : sept sont qualifiées pour retrait,
37 restent en place car leur variante de code ou de comportement ne permet
pas un retrait automatique. Aucune fusion ni modification du runtime.

| Branche | SHA | Preuve de conservation |
| --- | --- | --- |
| audit/vanilla-black-ui-rex | bcee84abff892903d166d9cdcdd03627e972572b | Delta constitué uniquement de Markdown : originaux conservés octet pour octet dans docs/archives/branches-20261012. |
| diagnostic/vanilla-ui-black-surfaces | f7362db86d4775221822996b22dae96c2de49095 | Delta constitué uniquement de Markdown : originaux conservés octet pour octet dans docs/archives/branches-20261012. |
| feature/noe-060-reporting | dcfce29540113562a41dba0a254dabe42c17d06a | Delta constitué uniquement de Markdown : originaux conservés octet pour octet dans docs/archives/branches-20261012. |
| feat/noethys-sl-afas-previsionnel | 108dc5f5e61e27c9549ebd1aeaf70b5dc46fe809 | Moteur identique à main ; AST de toutes les assertions originales conservé ; garde réseau ajoutée. Tests ciblés réussis. |
| feat/noethys-sl-vacances-sportives | 77f2be447110ce245458427bb8b66c82821cd55d | Moteur identique à main ; AST de toutes les assertions originales conservé ; garde réseau ajoutée. Tests ciblés réussis. |
| chore/noethys-sl-requirements-documentation | d3964671af351c2ebc5f0bea999fb46290dc3866 | Tous les paquets source sont encore déclarés dans main, qui ajoute mailjet-rest. Ordre/commentaires historiques archivés. |
| chore/workflows-consolidation | f28861260cf2f23dd2027e9b20ca3a452a86fd42 | Lignes opérationnelles identiques à master ; seuls commentaires et noms affichés diffèrent. Original archivé sous docs/. |

AFAS : 8 tests réussis ; vacances : 10 tests réussis, avec une assertion
supplémentaire sur le samedi 31/10/2026 dans main. Toutes les assertions
historiques sont conservées. Runtime Python 3.10 Windows existant, sources
dans la copie isolée, APPDATA/LOCALAPPDATA temporaires, profil test vide,
réseau bloqué ; zéro tentative réelle. Le premier essai sous Python 3.11
n’avait pas pu importer la garde à cause de wxPython absent ; la qualification
réussie utilise ensuite le runtime Windows disponible, sans retrait de garde.

Les fichiers d’archive ne remplacent aucune documentation courante et
n’activent aucun workflow. Chaque blob source est revérifié au moment de la
copie et indexé dans provenance.json. Les historiques complets des sept
branches sont dans github-all-refs.bundle (session précédente), vérifié.
Ce commit prépare les archives avant toute suppression distante. Publication
envisagée en un push atomique : main avance seulement par documentation,
et les sept refs sont retirées avec contrôle de leurs SHA ; les noms et
têtes/bases de PR restent protégés. Le résultat réellement distant sera
consigné après vérification, sans présumer ici le succès du push.

Liste des 37 sources conservées dans qualification.json de la session du
12/10/2026 ; leurs SHA et différences détaillées restent dans content-audit.json
de la session précédente. Les 37 sources portent des variantes, outils,
protections ou fonctionnalités qui demandent une décision ciblée ; elles ne
sont pas déclarées absentes du moteur sur la seule différence de fichier.


### Résultat distant confirmé du lot du 12/10/2026

L’envoi atomique a réussi : publication des deux notes locales e59f3400,
aa74aa87 et du commit d’archives e9c9398fc544a5698753a3fda6e8dcf13c84822b
sur main, plus retrait effectif des sept branches du tableau ci-dessus.
Après cette opération : 51 branches distantes, dont 37 historiques conservées.
Toutes les autres têtes distantes sont inchangées ; huit PR ouvertes inchangées.
Aucun code runtime ni test modifié, aucune nouvelle branche ni force-push.
Les références locales obsolètes sont nettoyées par fetch --prune.

Vérifications finales : profils Portable, tags, trois stashes, branches locales
master/wx/qt et le worktree WIP Noethys-RC2-clean (diff binaire et inventaire
non suivi) inchangés. Le dossier principal ne présente que Portable comme
non suivi. Les 18 tests ciblés réussis, leurs logs, les empreintes des archives
et la liste des 37 branches conservées sont dans elagage-20261012 dans l’espace
de sauvegarde de cette session. Les sources archivées sont consultables dans
docs/archives/branches-20261012 ; aucune consigne historique n’est activée.
Cette confirmation est publiée comme commit documentaire séparé sur main.
CI distante : aucun succès revendiqué ; aucun packaging ni release demandé.
La poursuite implique une qualification de variantes de code, surtout réseau,
interventions, Qt et packaging ; aucune réintégration automatique autorisée.


## 17. Clôture du tri des 37 sources restantes — 12/10/2026

Toutes les 37 branches ont maintenant une décision de retrait motivée, et
non un simple comptage de commits ou statut de PR. Comparaison des blobs et
AST contre les 14 têtes protégées ; comparaison des changements propres
à chaque branche avec son ancêtre commun (imports, variables, définitions,
méthodes et suppressions). L’analyse distingue les divergences héritées
des apports réellement propres. Aucune décision métier implicite.

### Sept références qualifiées pour retrait

| Branche | SHA | Conservation |
| --- | --- | --- |
| audit/vanilla-deep-scan-20260826 | cacafa37eb31e35f60ae1b6eb2e96237274159c6 | No application runtime changes in the branch delta. No protected runtime/workflow/test references to the unique tool paths or modules across all 14 protected heads. Complete changed source files, tests and workflows retained as inert documentation archives and full Git history in verified bundle. |
| audit/vanilla-ui-command-inventory | eef718234412ddf98867a2a4bbdbf29241b18397 | No application runtime changes in the branch delta. No protected runtime/workflow/test references to the unique tool paths or modules across all 14 protected heads. Complete changed source files, tests and workflows retained as inert documentation archives and full Git history in verified bundle. |
| audit/vanilla-upstream-630ef | 58dcab19fd0e2b542ce3c06c28f60422742c79ed | No application runtime changes in the branch delta. No protected runtime/workflow/test references to the unique tool paths or modules across all 14 protected heads. Complete changed source files, tests and workflows retained as inert documentation archives and full Git history in verified bundle. |
| test/vanilla-windows-ui-driver-prototype | be87c00ea51a6fef8ad33cf2ae848eaa6b676a85 | No application runtime changes in the branch delta. No protected runtime/workflow/test references to the unique tool paths or modules across all 14 protected heads. Complete changed source files, tests and workflows retained as inert documentation archives and full Git history in verified bundle. |
| noe-042-rc-gate | 085115c40fa5b2072bfdabebdf2f099330945b76 | Gate conditions and shell commands are identical in protected branch, ignoring labels/comments/action version tags. Historical gate test blob is identical and passes on the preserved workflow. Workflow build additions differ and are archived; no release or package is executed. |
| refactor/ui-navigation-repens | 6bf8a4cceb8bdf0da6ea13cb20b5c98fc6402f04 | All five functions added/modified by this branch relative to its common ancestor have identical ASTs in protected branch. No source function deleted, module imports/globals unchanged by source. Test blob identical. Remaining file difference is ConfigurerGrille inherited from the common ancestor and subsequently delegated to Style.appliquer_grille in protected branch. |
| feat/rc2-reception-quotient | f48450935bb18125b3b46a4e5e5346bea7804076 | All branch-owned changes preserved in protected RC2 reference. Fourteen delta files have identical blobs; in remaining file Traitement.Traitement_pieces AST is identical. No own binding was removed. Quotient atomic-write and received-file regressions pass on synthetic/memory data with network blocked. Other file differences are inherited/evolved code, retained in full source archive. |

Les quatre outils ne sont appelés ni par le runtime, ni par les workflows,
ni par les tests des 14 références protégées (recherche des chemins et noms
de modules). Leurs originaux sont conservés, avec les tests et workflows,
dans docs/archives/branches-20261012-final ; le bundle préserve les historiques.
Le gate RC conserve les mêmes conditions et commandes de validation ;
la navigation conserve les cinq fonctions propres et les tests identiques ;
la réception de quotient conserve les 14 blobs identiques et la méthode
Traitement.Traitement_pieces au même AST dans la référence RC2 protégée.

Validation ciblée supplémentaire : gate RC 5 tests, navigation 4, quotients
12 (SQLite mémoire/fictif, atomicité, factures inchangées), réception pièces
4 (AST, dépendances factices) : **25 réussites**, aucune tentative réseau
réelle. Aucun build, interaction avec une base réelle ou recette GUI complète.

### Trente branches conservées avec motif précis

Conserver ces références ne signifie pas que leurs fonctionnalités sont
qualifiées en production. Leur code propre n’est pas démontré intégralement
repris : supprimer ou intégrer ces variantes requiert une décision sur leur
devenir. Le tri de retrait est achevé ; la qualification métier et les recettes
sont des travaux distincts. Les exemples ci-dessous sont des différences,
pas une annonce automatique de correctifs absents de main.

| Branche | SHA | Fichier/fonction motivant le maintien |
| --- | --- | --- |
| agent/windows-ci-audit | 7df621ea3a30 | .github/workflows/ci.yml ; docs/CI-WINDOWS-AUDIT.md |
| agent/windows11-pyinstaller | f85f77266eec | .github/workflows/ci.yml ; .github/workflows/windows-package.yml |
| audit/vanilla-final-undefined-names | 8ae3a36f9394 | .github/workflows/final-undefined-name-audit.yml |
| build/vanilla-windows-portable | 4d5dda48269b | .github/workflows/noethys-sl-windows.yml ; .github/workflows/vanilla-windows-package.yml |
| chatgpt/noethys-convention-ui-activites-20260929 | 7cd062c3f634 | .github/workflows/noethys-sl-windows.yml ; README.md |
| claude/noethys-windows-ci-audit-qy5m9t | 3b847c6b2957 | noethys/Dlg/DLG_Badgeage_interface.py : GetInfosActivite, CTRL_Interface.Procedure_enregistrer ; noethys/Dlg/DLG_Famille.py : Dialog.GetIDcomptePayeur, Dialog.MenuImprimerReleve |
| feat/noethys-sl-rc1-convention-finalise | f6cac3302a2f | docs/dev/CONVENTION_DOCX.md ; noethys/Dlg/DLG_Famille.py : CreateIDfamille, Notebook.__init__ |
| feature/extensions-registry | 9174ba32a45e | docs/EXTENSIONS.md ; noethys/Extensions/__init__.py |
| feature/noe-062-conventions | f85fd51ee404 | noethys/Utils/UTILS_Impression_convention.py ; tests/test_convention_engine_contract.py |
| feature/noe-062-mises-a-disposition | c69f3c80325e | docs/NOE-062-MISES-A-DISPOSITION.md ; docs/NOE-062C-PROGRAMMATION.md |
| feature/noe-062b-groupes-structures | 203fff34134c | noethys/Utils/UTILS_Tiers.py ; noethys/Utils/UTILS_Tiers_Schema.py |
| feature/noe-062b-roles-contacts | 177b4c3dcd1b | noethys/Utils/UTILS_Tiers.py ; noethys/Utils/UTILS_Tiers_Schema.py |
| feature/noe-063-portail-consolide | 55b2b129e67e | docs/NOE_063C_TARIFS_PORTAIL.md ; docs/NOE_063_PORTAIL_CONTENUS_DYNAMIQUES.md |
| feature/noe-063b-rss-atom-connecthys | 8f84f5edb72b | docs/NOE_063B_RSS_ATOM.md ; docs/NOE_063_PORTAIL_CONTENUS_DYNAMIQUES.md |
| feature/noe-063d-tarifs-ui | 20d5b15c1adb | docs/NOE_063B_RSS_ATOM.md ; docs/NOE_063C_TARIFS_PORTAIL.md |
| fix/noe-062b-hardening | 752645c5a772 | noethys/Dlg/DLG_Ecoles.py : from:Utils:0:UTILS_Interventions:None, import:GestionDB:None ; noethys/Dlg/DLG_Seances_sport_ecoles.py |
| fix/noethys-sl-aui-docking-minimize | aac763f24480 | noethys/Noethys.py : MainFrame.Initialisation, MyApp.OnInit ; tests/test_vanilla_aui_docking_lifecycle.py |
| fix/noethys-sl-aui-guides-fantomes | 7704ee753687 | docs/noethys_sl_wx_pr375_apparence_claire.md ; noethys/Chemins.py : assignment:Name(id='STATIC_IMAGE_ALIASES', ctx=Store()), GetStaticPath |
| fix/noethys-sl-light-only | ccdfb82bcf1b | .github/workflows/windows-package.yml ; noethys/Utils/UTILS_Interface.py : GetApparence, SetApparence |
| fix/noethys-sl-mailjet-consolidation | 51ee128a60de | noethys/Dlg/DLG_Mailer.py : Dialog.Envoyer |
| fix/noethys-sl-mailjet-email-confirmation | 9e0945b5d0a4 | noethys/Dlg/DLG_Mailer.py : Dialog.Envoyer ; noethys/Noethys.py : MainFrame.Initialisation, MyApp.OnInit |
| fix/rc2-network-stopgate-1 | cf5f9fbe6ccd | docs/audit/AUDIT_RESEAU_RC2.md ; docs/audit/CONTRAT_CONNECTHYS.md |
| fix/rc2-pr385-compatible | ba67c6b9a5fc | noethys/Dlg/DLG_Saisie_portail_demande.py : Traitement.Traitement_pieces |
| fix/vanilla-no-black | 7c39f16ab148 | .github/workflows/vanilla-release.yml ; .github/workflows/vanilla-windows-package.yml |
| fix/windows-installable-config | fbdebc8b6ef4 | .github/workflows/windows-package.yml ; noethys/Utils/UTILS_Fichiers.py : DeplaceFichiers |
| noe-041-portable-mode | 3cf6cbfe5d6f | .github/workflows/windows-package.yml ; noethys/Utils/UTILS_Fichiers.py : GetRepUtilisateur |
| noe-062-programmation-occurrences | 88904fc780a0 | noethys/Data/DATA_Programmations_Structures.py ; noethys/Utils/UTILS_Programmations_Structures.py |
| noe-062c-lieux-execution-seances | be059ccd4804 | noethys/Data/DATA_Structures.py : assignment:Name(id='DB_STRUCTURES', ctx=Store()) ; noethys/Utils/UTILS_Interventions_Execution.py : statement:Expr(value=Constant(value='Extension opérationnelle 1:1 des séances Noe-062C.\n\nLa séance canonique reste dans ``interventions``. Ce module ne duplique ni le\nréférentiel RH (Teamworks reste source de vérité), ni les lieux : il conserve\nuniquement leurs UID/IDs de référence et les écarts entre prévu et réalisé.\n')), GestionnaireExecutionInterventions.EnregistrerExecution |
| poc/qt-theme-isole | cba459cd62cb | .github/workflows/qt-prototype.yml ; docs/QT_MIGRATION_INVENTORY.md |
| refactor/ui-list-tools-repens | 52ed49bf888b | .github/workflows/ci.yml ; .github/workflows/windows-package.yml |

Le dossier publié dossier-conservation.json sous l’archive finale contient
les SHA complets, chaque fichier et définition concernés, les ancêtres,
cibles et preuves. Cela couvre notamment le prototype Qt, les extensions,
programmations/groupes/rôles/lieux, contenus/tarifs Portail, variantes de
réception réseau et Mailjet, AUI/Noedoc, packaging et configuration.
Ces sources restent en place ; aucune fusion générale, reprise automatique
de schéma, fermeture de PR ou abandon de travail unique.

Ce commit publie les archives avant retrait distant, en un envoi atomique
main + sept suppressions, avec contrôle des SHA et des huit PR ouvertes.
Si l’envoi réussit, il restera 44 branches : 14 protégées et 30 sources
conservées avec motifs. Le résultat réel sera vérifié et consigné ensuite.


### Résultat final réel : tri de retrait achevé

Le push atomique du lot final a réussi à main
f95636fc94122e67caa613e690550e5f2e0aa7aa : sept références retirées,
archives des 43 fichiers originales publiées avec blobs vérifiés, dossier de
maintien des trente autres sources publié. Après vérification : 44 branches
distantes, 14 références protégées et 30 variantes de code conservées avec
motifs explicites. Huit PR ouvertes, titres/descriptions/drafts et têtes/bases
inchangés ; les autres branches distantes restent aux mêmes SHA.

Bilan de tout l’élagage dans cette conversation : 19 branches distantes
retirées (5 + 7 + 7), trois branches locales intégrées retirées, un worktree
propre retiré, neuf fichiers locaux d’audit archivés. Les historiques Git
complets sont sauvegardés et vérifiés ; les sources particulières retirées
restent consultables dans les archives documentaires de main.

Contrôle final : runtime et tests de main inchangés depuis 694ccacc ; aucun
code métier migré implicitement, aucun packaging/release, nouvelle branche,
merge global ou force-push. Portable, tags, trois stashes, branches locales
master/wx/qt et worktree WIP Noethys-RC2-clean vérifiés inchangés. Seul Portable
reste non suivi dans le dossier principal. main est publié et aligné avec
origin/main après cette confirmation documentaire.

Les 37 sources ont toutes été examinées ; les trente maintiens sont des
décisions de conservation de variantes identifiées, pas une file de branches
encore non inventoriées. Leur intégration ou abandon demanderait de choisir
des comportements, protections ou fonctionnalités ; ce serait un chantier
métier distinct de l’élagage autorisé. La documentation ne revendique pas
une qualification fonctionnelle globale de ces variantes ni une CI verte.


## 18. Reprise réelle et requalification des stop-gates — 12/10/2026

Contrôle autonome après le tri déjà publié, sans reprendre un plan ancien.
Consignes AGENTS.md et présent document lus avant toute action. GitHub réel :
**44 branches, huit PR ouvertes, master toujours par défaut**. Point de départ
main `621b904f533ee0e20dec8657740634313c033167`, wx
`dcede8170874dd79cd9a5b5825bc3b4ed85feb62`, qt
`8902e655f93cebabdc84ff3ab8ea1f1ac89b73e0`, master
`b0be3c7ebdf2d69d6028eb4fd6fc08e340a68b9e`.

### Résultat du tri de retrait

**Zéro branche supprimée dans cette reprise ; zéro candidate sûre restante.**
Les 19 suppressions des lots précédents ne sont pas comptées comme opérations
de cette reprise. Les 30 branches conservées ont exactement les SHA du dossier
publié en section 17 ; les 13 autres têtes protégées sont inchangées et main
n'a ajouté que de la documentation depuis la comparaison `ee234ada`.
Relecture du dossier, vérification des blobs source et comparaison à chacune
des 14 têtes protégées actuelles : des variantes demeurent. Le maintien est
reconfirmé ; aucune différence de blob n'est à elle seule interprétée comme
fonctionnalité absente. Les analyses AST et décisions précédentes restent
applicables puisque leurs entrées runtime sont inchangées. La sauvegarde ne
constitue pas une autorisation d'abandonner un apport non intégré.

### PR et références protégées

Les huit PR suivantes restent ouvertes, avec leurs têtes et bases conservées :

| PR | Tête et SHA | Base |
| --- | --- | --- |
| #422 | rc/noethys-sl-0.1.0-rc.3 — `28c2294cead7aa09f6d04c3bbdd9339593377e5b` | rc/noethys-sl-0.1.0-rc.2 |
| #384 | feature/vanilla-entites-fonctions — `4e2c615bcbee669b08e12f1580e2e81fb4351295` | feature/vanilla-conventions |
| #369 | feature/session-attendance-consumer-2026-09-19 — `74410a3ef4ef8b618a2214487453d379ff596f3a` | master |
| #366 | docs/mkdocs-wiki — `e43492b156a92551579faa6c606333c98f2bf280` | master |
| #355 | noe-062-secure-secret-provider — `04f7886cfd8d5f62bc02b243f6d57ebfff8b6297` | master |
| #112 | design-form-density-standard — `f96fa35865462500f12ad2caee98027e488f3955` | master |
| #104 | dev-db-docker — `b7dc7c195022949626f8a7e9a55d2677e710d107` | master |
| #102 | docs/open-development-policy — `d218e2980fbc7ab5b6577ec50c74931aae836c93` | master |

Cela représente 14 références distinctes en comptant main/wx/qt et master.
Les PR ne sont ni fermées, ni fusionnées, ni reciblées. Les bases
feature/vanilla-conventions et RC2 restent notamment nécessaires.

### Conservation revérifiée

- `original-all-refs.bundle` : 57 749 065 octets, SHA-256
  `cbb419ae17192d7e05ff8b1f18b5349656480d86a6e86a0fbfbe80fb2b2c5e8d`.
- `github-all-refs.bundle` : 59 138 549 octets, SHA-256
  `1898e49973c9abf8832c3e6b01b816f7813df94e7d10e96d8cec3e89146890eb`.
- Empreintes identiques au manifeste précédent, `git bundle verify` réussi
  pour les deux. Les 30 SHA des sources maintenues figurent tous exactement
  dans les références du bundle GitHub. Bundles dans `elagage-20261011` de
  l'espace Codex ; aucune nouvelle sauvegarde contenant des données réelles.
- Les 48 fichiers indexés par les deux provenance.json des archives
  `branches-20261012` et `branches-20261012-final` sont identiques octet par
  octet aux blobs de leurs commits source et aux SHA-256 documentés.
- GitHub expose neuf tags et neuf releases ; les références locales possèdent
  aussi des tags historiques/archives. Aucune modification ni assimilation
  d'une release à la qualification de main. RC3 reste une préversion historique
  au commit `6ab134707ac48e16ee82001088234510657f1ab6`.
- Deux worktrees : principal sur main et Noethys-RC2-clean détaché sur
  `8b3789d9de1beeb3a47dbf6ed3be235a7df2cc12`, avec 32 fichiers suivis modifiés.
  WIP conservé, trois stashes conservés. Branches locales master/wx/qt distinctes
  des têtes distantes, conservées sans synchronisation implicite.
- Dossier principal : seul `noethys/Portable/` est non suivi. Aucun accès à son
  contenu, aucune modification des fichiers non suivis existants ou des données
  réelles. Pas de tests applicatifs, SMTP, base, build, packaging ou migration.

### Stop-gates et règle signal nouveau → requalification

1. **MAIL / signal utilisateur nouveau** : travail perdu et mails aux familles
   jamais reçus signalés dans cette conversation. Cause, dates et version exécutée
   non établies ; ne pas inférer une panne Mailjet ou une livraison depuis une CI.
   Les deux branches Mailjet `51ee128a60ded8dfb4d8bcf77f28219eb1f1f6f5` et
   `9e0945b5d0a411ef8d03a7179df5abb4a18919c1` restent conservées. DLG_Mailer
   a le même blob sur main/wx/qt (`3e1090cf8a5adf8d4bb84030dd1e9896aa825867`),
   différent des deux variantes. Diff revu : parent de progression et affichage
   d'erreurs Python 3 notamment ; le signal ne démontre pas leur causalité.
   Requalification requise : résultat par destinataire, erreurs/rejets, statut
   fournisseur et réception sur adresses de recette consenties ; aucun envoi
   réel aux familles ni accès à leurs données dans ce lot.
2. **CI wx rouge** : run [38171008248](https://github.com/fr4nck/Noethys-SL/actions/runs/38171008248)
   au SHA `dcede817`. 96 tests exécutés, une failure, deux skips.
   `test_deux_postes_simultanes_une_seule_adhesion` attend
   `('rien_a_faire', 'adhesion_deja_valide')` et reçoit
   `('rien_a_faire', None)`. Cause non requalifiée ; ne pas affaiblir l'assertion.
   Le dernier run main de code [38168522698](https://github.com/fr4nck/Noethys-SL/actions/runs/38168522698)
   réussit au SHA `694ccacc2d37ba71298b56e7ddb6901be6a55d2d` ; main n'a depuis
   changé que docs. Aucun run au HEAD documentaire main ou au HEAD qt dans les
   100 runs consultés : aucune CI verte revendiquée sur ces têtes.
3. **Non-régression interbranches** : main et wx/qt divergent (16 commits propres
   à main, cinq propres à chaque interface au départ). Les trois différences
   runtime exactes sont DLG_Noedoc.py, OL_Etiquettes.py, UTILS_Stats_modeles.py,
   avec leurs trois nouveaux tests présents seulement sur main. Correctifs
   main `e8d1e7ad` (secteur), `27b988f3` (delta), `bf69d3ca` (mode GetHTML) :
   ABSENTS sous cette forme sur wx/qt, à porter et tester par lots ciblés.
   Les sources et tests du correctif Nomadhys `694ccacc` sont identiques sur
   wx/qt après leurs adaptations `d95fb660` / `508d5f4f` ; aucune nouvelle
   propagation effectuée. Aucune fusion globale ni fast-forward possible
   présumé depuis la seule comptabilité de commits.
4. **master / SQL / métier** : master reste divergente (1 480 commits propres,
   271 côté main au départ), référence par défaut et base de six PR.
   Protections Noe-032 avancées, interventions/pointage/tiers, contrats et
   tests historiques restent à qualifier par thème ; recette MySQL/MariaDB
   synthétique et UI/Qt requise avant publication. Aucune suppression de master.
5. **30 sources non intégrées** : tableau ci-dessous ; conserver chaque ref
   jusqu'à preuve nouvelle de reprise des apports ou décision explicite de
   devenir. Le détail de provenance, ancêtres, définitions et comparaisons
   reste dans `docs/archives/branches-20261012-final/dossier-conservation.json`.

| Source conservée | SHA complet | Exemples de fichiers encore distincts |
| --- | --- | --- |
| agent/windows-ci-audit | `7df621ea3a3034819142c633f5f4c9149c17fa68` | .github/workflows/ci.yml ; docs/CI-WINDOWS-AUDIT.md |
| agent/windows11-pyinstaller | `f85f77266eec49ec02d6a24e0e130d463123b8d5` | .github/workflows/ci.yml ; .github/workflows/windows-package.yml |
| audit/vanilla-final-undefined-names | `8ae3a36f939460a36b9d7b4f86cfa1147208e1b0` | .github/workflows/final-undefined-name-audit.yml ; noethys/Dlg/DLG_Noedoc.py |
| build/vanilla-windows-portable | `4d5dda48269b8cc9313b3a6dc5a4442f0e5c7d2a` | .github/workflows/noethys-sl-windows.yml ; .github/workflows/vanilla-windows-package.yml |
| chatgpt/noethys-convention-ui-activites-20260929 | `7cd062c3f634cff137f20af469ff7ded5e407e42` | .github/workflows/noethys-sl-windows.yml ; README.md |
| claude/noethys-windows-ci-audit-qy5m9t | `3b847c6b2957a5d4a7d118ad7384f8bdc971baaf` | noethys/Dlg/DLG_Badgeage_interface.py ; noethys/Dlg/DLG_Famille.py |
| feat/noethys-sl-rc1-convention-finalise | `f6cac3302a2ff3946f1f389071accec151a5b542` | docs/dev/CONVENTION_DOCX.md ; noethys/Dlg/DLG_Famille.py |
| feature/extensions-registry | `9174ba32a45e8788a6ba456aae722360425371ae` | docs/EXTENSIONS.md ; noethys/Extensions/__init__.py |
| feature/noe-062-conventions | `f85fd51ee40429415819e01284bf9deba6406b13` | noethys/Utils/UTILS_Impression_convention.py ; tests/test_convention_engine_contract.py |
| feature/noe-062-mises-a-disposition | `c69f3c80325e6aeef27bdec82a03ef257ff552a8` | docs/NOE-062-MISES-A-DISPOSITION.md ; docs/NOE-062C-PROGRAMMATION.md |
| feature/noe-062b-groupes-structures | `203fff34134ceb7a9676f877e5901e0bb74dfc4f` | noethys/Utils/UTILS_Tiers.py ; noethys/Utils/UTILS_Tiers_Schema.py |
| feature/noe-062b-roles-contacts | `177b4c3dcd1b2055f4a595512c71ab6305a55b8b` | noethys/Utils/UTILS_Tiers.py ; noethys/Utils/UTILS_Tiers_Schema.py |
| feature/noe-063-portail-consolide | `55b2b129e67ed295f59b161ebb6896c06348a101` | docs/NOE_063C_TARIFS_PORTAIL.md ; docs/NOE_063_PORTAIL_CONTENUS_DYNAMIQUES.md |
| feature/noe-063b-rss-atom-connecthys | `8f84f5edb72b8becd3a58a44994fb23be0117630` | docs/NOE_063B_RSS_ATOM.md ; docs/NOE_063_PORTAIL_CONTENUS_DYNAMIQUES.md |
| feature/noe-063d-tarifs-ui | `20d5b15c1adb4a460d7ff0ed87ed22120ebec0dc` | docs/NOE_063B_RSS_ATOM.md ; docs/NOE_063C_TARIFS_PORTAIL.md |
| fix/noe-062b-hardening | `752645c5a772a822226b1494d908400d85a79c4a` | noethys/Dlg/DLG_Ecoles.py ; noethys/Dlg/DLG_Seances_sport_ecoles.py |
| fix/noethys-sl-aui-docking-minimize | `aac763f24480e98608cfd2ccc918d87ef26594db` | noethys/Noethys.py ; noethys/Utils/UTILS_AUI_Apparence.py |
| fix/noethys-sl-aui-guides-fantomes | `7704ee753687159ee7173e33f86f538bc483c75c` | noethys/Noethys.py ; noethys/Utils/UTILS_AUI_Apparence.py |
| fix/noethys-sl-light-only | `ccdfb82bcf1b1f5d4cd06a9d6382176cd91f6629` | .github/workflows/windows-package.yml ; noethys/Ctrl/CTRL_ObjectListView.py |
| fix/noethys-sl-mailjet-consolidation | `51ee128a60ded8dfb4d8bcf77f28219eb1f1f6f5` | noethys/Dlg/DLG_Mailer.py ; noethys/Dlg/DLG_Saisie_portail_demande.py |
| fix/noethys-sl-mailjet-email-confirmation | `9e0945b5d0a411ef8d03a7179df5abb4a18919c1` | noethys/Dlg/DLG_Mailer.py ; noethys/Dlg/DLG_Saisie_portail_demande.py |
| fix/rc2-network-stopgate-1 | `cf5f9fbe6ccd9472a061ceaf81ab6358effc00b3` | docs/audit/AUDIT_RESEAU_RC2.md ; docs/audit/CONTRAT_CONNECTHYS.md |
| fix/rc2-pr385-compatible | `ba67c6b9a5fc488ff8ba3c15d3cd6bd7826c12d8` | noethys/Ctrl/CTRL_Ephemeride.py ; noethys/Dlg/DLG_Saisie_portail_demande.py |
| fix/vanilla-no-black | `7c39f16ab1489ce4bcd96e2fc1b44995b8d237fa` | .github/workflows/vanilla-release.yml ; .github/workflows/vanilla-windows-package.yml |
| fix/windows-installable-config | `fbdebc8b6ef4ef906bfb8d23246be5eeb1820203` | .github/workflows/windows-package.yml ; noethys/Utils/UTILS_Fichiers.py |
| noe-041-portable-mode | `3cf6cbfe5d6fcd631f21fc821bbecc4988caa7b2` | .github/workflows/windows-package.yml ; noethys/Utils/UTILS_Fichiers.py |
| noe-062-programmation-occurrences | `88904fc780a052a90598f5bde23aa2dffd686a93` | noethys/Data/DATA_Programmations_Structures.py ; noethys/Utils/UTILS_Programmations_Structures.py |
| noe-062c-lieux-execution-seances | `be059ccd480468f76c2b50f3ee000200e2e9bb4f` | noethys/Data/DATA_Structures.py ; noethys/Utils/UTILS_Interventions_Execution.py |
| poc/qt-theme-isole | `cba459cd62cb2d71f43f89825287295d2ead6492` | .github/workflows/qt-prototype.yml ; docs/QT_MIGRATION_INVENTORY.md |
| refactor/ui-list-tools-repens | `52ed49bf888bc381d92e46a87eca7f6a5fc66e65` | .github/workflows/ci.yml ; .github/workflows/windows-package.yml |

**Opération de cette reprise :** ajout de ce constat documentaire sur la branche
existante main uniquement. Aucun runtime/test modifié, aucune branche créée,
suppression, réécriture d'historique, force-push, changement de défaut, tag ou
release. Les stop-gates ci-dessus empêchent une réduction honnête à main/wx/qt.
Preuves détaillées de la reprise dans `audit-reprise-20261012` de l'espace Codex.
Tout nouveau SHA, résultat CI ou signal métier invalide la décision concernée
jusqu'à sa requalification ; ne pas relancer un ancien plan de suppression.
