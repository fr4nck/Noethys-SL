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
