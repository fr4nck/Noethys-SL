# Inventaire de la lignée `master` et statut de reprise

> **Statut au 13/10/2026.** Les corrections (A) ci-dessous ont été reprises
> dans `main`, puis propagées à l'identique dans `wx` et `qt`, chacune avec un
> test de non-régression qui échoue sans le correctif (recette rapide : 516
> tests OK sur les trois branches). Les ensembles B, C et D restent archivés
> et sont listés dans [Fonctionnalités reportées](FONCTIONNALITES_REPORTEES.md).
> **Archiver n'est pas intégrer.**

| Code | Source master | main | Statut (main, wx, qt) |
|---|---|---|---|
| A01 | `0753bf71` | `c6a09be3` | VALIDÉ |
| A02 | `f0256647` | `813b4763` | VALIDÉ |
| A03 | `299dbcc3` | `52bdc088` | VALIDÉ |
| A04 | `b2ce3aef` | `f336847e` | VALIDÉ |
| A05 | `910cc8f5` | `4b90122d` | VALIDÉ (adapté : `chardet` facultatif via `FonctionsPerso.DecoderTexteFichier`) |
| A06 | `a6a960bf`, `8bef9bf1` | `05490888` | VALIDÉ |
| A07 | `8afab828` | `12d73be3` | VALIDÉ |
| A08 | `d27b43fa` | `06448f9e` | VALIDÉ |
| A09 | `25ad1e95` | `f4fc0f11` | VALIDÉ |
| A10 | `ee99d698` (partiel) | `ac0de04b` | VALIDÉ (script de qualification de master non repris) |
| A11 | `08baa60e` | `ea189072` | VALIDÉ |
| A12 | `6f7eb0a9` | `f7127d8b` | VALIDÉ |
| A13 | `b829f184` | `7790d86b` | VALIDÉ |
| A14 | `1ec5c6dd` | `93a0030c` | VALIDÉ |
| A15 | `9a0b010f` | `ba3f6fd5` | VALIDÉ |
| A16 | `523a9a6d` | `5e3eafeb` | VALIDÉ |
| A17 | `cae2d2a7` | `aea41bf1` | VALIDÉ |
| A18 | `e2accc5f` | `78fbf915` | VALIDÉ |
| A19 | `16621848` | `60c49ef9` | VALIDÉ |
| A20 | `ce979bbd` (partiel) | — | NON APPLICABLE pour `isAlive` : `UTILS_Adaptations` de main rétablit l'alias sous Python 3 ; les quatre gardes IndexError du même commit restent EN ATTENTE (non vérifiées) |
| A21 | `9f9a39c2` | `78873ba2` | VALIDÉ |
| A22 | `b5298150`, `e67c1a7b`, `3b21e965`, `94187a5b`, `4046e240`, `7df20c7d` | — | EN ATTENTE : `ast.literal_eval` refuserait des valeurs déjà stockées qui ne sont pas des littéraux ; contrôle préalable sur copie de base |
| A23 | `1bd709d7` (partiel) | `77d1fa42` | VALIDÉ (contrôle d'upload déjà présent dans main) |
| A24 | `fa4d3ca1` | `52aba5ab` | VALIDÉ |
| A25 | `d1d8b70b`, `85d42ba5` | `dbf699b5`, `b7dd8f7c` | VALIDÉ |
| A26 | `89fe8f70` | — | EN ATTENTE : changement de liaison du double-clic de grille, recette Windows sur poste isolé requise |
| A27 | `e801bb3a`, `ba6dea4c`, `79680bda` | `f2ce3a95`, `4b51f4c5`, `7f52c480` | VALIDÉ (79680bda porté à la main : écrit sur l'interface Repens) |
| A28 | `80b0e127` | `41d6bb36` | VALIDÉ |

Tests associés : `test_master_sql_strict`, `test_master_exports_encodage`,
`test_master_exports_internes`, `test_master_imports`, `test_master_portail_tipi`,
`test_master_gardes_runtime`, `test_saisie_adresse_homonymes`, `test_villes`,
`test_individu_rattachement_hardening`, `test_branch_contracts_batch_16/17/19`,
`test_tarification_track_filter_delete`, `test_badgeage_evenement_contract`,
`test_composition_filiation_layout`, `test_portail_payment_ventilation_contract`,
`test_importation_individus_contracts` (outils `scripts/audit_*` repris de master).

---

_Généré le 12/10/2026 en lecture seule. Références : `origin/main` 3e02f5ca, `origin/wx` 0a11e66a, `origin/qt` 7742df06, `origin/master` b0be3c7e, `upstream/master` 630ef437, `merge-base master/main` 630ef437._

## 1. Méthode

- Comparaison par **contenu**, pas par SHA : pour chaque fichier de code (hors `docs/`) dont la version de `origin/master` diffère de `main`, `wx` **et** `qt`, on compte les lignes non vides et non commentaires absentes de l'union des trois branches canoniques (même chemin, comparaison après suppression des espaces).
- Chaque ligne unique est attribuée au dernier commit master-only qui l'a ajoutée, puis les commits sont regroupés en ensembles fonctionnels (messages, fichiers, PR).
- Pour les correctifs : les lignes « défaut » (supprimées) et « correction » (ajoutées) sont recherchées dans `main`, `wx`, `qt`, puis le contexte de `git show origin/main:<fichier>` est relu. Un correctif n'est classé « absent de main » qu'après cette vérification ; les numéros de ligne cités sont ceux de `origin/main` 3e02f5ca (identiques dans wx et qt pour les lignes citées).
- Totaux : 856 fichiers portent des lignes uniques, soit 53111 occurrences de lignes (dont 27125 sous `noethys/`, le reste en tests, scripts et CI). Sur 1480 commits master-only, 825 portent encore du contenu absent des branches canoniques ; les autres ont été absorbés, réécrits ou écrasés. L'écart avec l'estimation de ~22 000 lignes vient du périmètre (ici : tous les fichiers de code, occurrences et non lignes distinctes).

Classement : **A** correction validée à reprendre · **B** fonctionnalité utile intégrable (sans migration SQL) · **C** prototype / évolution non qualifiée à archiver et reporter · **D** obsolète (remplacé par main ou version antérieure).

## 2. Tableau des ensembles

| Code | Ensemble | Classement | Lignes uniques (dont tests) | Fichiers | Commits | Période | Dépendance SQL |
|---|---|---|---|---|---|---|---|
| E01 | Outils d'audit statique et de qualification (scripts/audit_*, qualify_*, modernize_*) | C | 4882 (1505) | 62 | 78 | 2026-08-02 -> 2026-09-04 | aucune |
| E02 | CI, packaging PyInstaller, hooks runtime figés, lanceur dev Windows, installateur Vanilla+ | D | 4446 (508) | 61 | 110 | 2026-08-02 -> 2026-09-23 | aucune (scripts de recette lisent des bases en lecture seule) |
| E03 | SQL strict (ONLY_FULL_GROUP_BY) et audit d'index (Noe-001 à Noe-004) | A+C | 1065 (395) | 8 | 11 | 2026-08-19 -> 2026-08-28 | aucune (requêtes de lecture) |
| E04 | Sécurité : suppression des eval(), chargement des extensions, SFTP/FTPS portail | A+B+C | 360 (0) | 26 | 22 | 2026-08-15 -> 2026-08-15 | aucune |
| E05 | Écritures transactionnelles (« atomiser » : commit=False + rollback) | B | 1428 (0) | 69 | 61 | 2026-08-15 -> 2026-08-17 | aucune (changement de sémantique transactionnelle uniquement) |
| E06 | Python 3 : encodages, frontières bytes/texte, dates ISO, géométries wx | A+D | 292 (2) | 170 | 28 | 2026-08-14 -> 2026-08-23 | aucune |
| E07 | Robustesse des imports/exports (NoethysWeb, documents, badgeage, vacances, portail) | A | 76 (18) | 10 | 9 | 2026-08-15 -> 2026-09-01 | aucune |
| E08 | Correctifs UI ponctuels (double-clic ObjectListView/menus, bouton, Mailer) | A?+B+D | 72 (0) | 4 | 4 | 2026-08-20 -> 2026-08-21 | aucune |
| E09 | Durcissement Vanilla+ / passe anti-bugs #98 / cycle de vie wx | A+D | 1582 (1260) | 248 | 25 | 2026-08-22 -> 2026-09-07 | aucune |
| E10 | Contrats de branches conditionnelles (#219-#262, #297-#349) et petits correctifs | A+B | 3651 (2857) | 127 | 67 | 2026-08-16 -> 2026-09-03 | aucune |
| E11 | Sauvegarde/restauration Noe-032 (variante master #352) | D | 1042 (483) | 5 | 6 | 2026-08-14 -> 2026-09-04 | aucune table ; restauration MySQL |
| E12 | Migration contrôlée d'une base vers une base neuve (UTILS_Migration_base) | C | 939 (246) | 9 | 15 | 2026-08-17 -> 2026-08-21 | écrit toutes les tables cœur d'une base cible |
| E13 | Noe-062 : tiers/structures, contacts, groupes/rôles, relations contractuelles, payeurs, conventions versionnées, documents | C | 4228 (1443) | 25 | 13 | 2026-08-20 -> 2026-09-02 | crée structures, structures_contacts, structures_roles_contacts, structures_categories(_li |
| E14 | Noe-062 : programmations annuelles, matérialisation en séances, séances sport écoles, lieux, prévu/réalisé | C | 2424 (726) | 16 | 6 | 2026-08-27 -> 2026-09-02 | crée interventions, lieux, interventions_execution, structures_programmations, structures_ |
| E15 | Noe-062 : inter-domaines (enveloppe, mailbox pull, inbox du réalisé) | C | 795 (472) | 5 | 3 | 2026-09-02 -> 2026-09-04 | crée interventions_execution_inbox |
| E16 | Synchronisation PMSL (pull/simulation/application/ACK, export retour, passerelle HMAC) | C | 1000 (284) | 10 | 23 | 2026-08-16 -> 2026-08-31 | écrit ouvertures ; lit activites, groupes, unites, unites_groupes, interventions |
| E17 | Commande de repas automatique (points de livraison, animateurs, réservations réelles) | B | 373 (41) | 8 | 13 | 2026-08-15 -> 2026-08-25 | aucune (lecture) |
| E18 | Refonte UI « Repens » (fenêtres, listes, surfaces, typographie, cockpit) | C | 6619 (1489) | 128 | 188 | 2026-08-20 -> 2026-08-26 | aucune |
| E19 | Thème, échelle d'interface, mode sombre, design system, icônes modernes/Fluent, AUI responsive | C | 6057 (621) | 88 | 143 | 2026-08-15 -> 2026-09-07 | aucune |
| E20 | Tableau de bord : panneau Aujourd'hui, planning Teamworks, messagerie optionnelle, registre de modules | D+C | 1217 (171) | 13 | 20 | 2026-08-20 -> 2026-08-28 | aucune |
| E21 | Recherche tolérante aux accents et fautes (UTILS_Recherche) | B | 184 (87) | 3 | 5 | 2026-08-20 -> 2026-09-07 | aucune |
| E22 | Couples ville/code postal (UTILS_Villes) et communes homonymes | A | (inclus E10) | 3 | - | - | aucune |
| E23 | Chargement différé de la liste des consommations (DLG_Impression_conso_differe) | B | (inclus E10) | 2 | - | - | aucune |

## 3. Détail par ensemble

### E01 — Outils d'audit statique et de qualification (scripts/audit_*, qualify_*, modernize_*)  
**Classement : C**

Outillage écrit pour l'arbre de master (inventaires, baselines, qualifications de branch_assignment_gap). Aucun effet runtime. Les baselines sont calées sur le code de master : non transposables telles quelles à main. Archiver ; reprendre au cas par cas un audit utile (ex. audit_wx_lifecycle, audit_sql_strict) en le recalant sur main.

- Lignes uniques : 4882 (dont 1505 en tests) ; 62 fichiers ; 78 commits ; PR : PR #88, #89, #100, #216, #217, #218, #315-#349
- Dépendance SQL : aucune
- Fichiers principaux : `scripts/audit_wx_lifecycle.py` (325), `scripts/audit_branch_assignment_gaps.py` (319), `scripts/qualify_branch_assignment_gaps.py` (302), `scripts/audit_semantic_traps.py` (283), `scripts/audit_pre_rc.py` (201), `scripts/audit_unbound_after_try.py` (191), `scripts/audit_ui_layout.py` (179), `scripts/audit_silent_exception_handlers.py` (173)
- Commits représentatifs : `31cee641` 2026-08-28 Audit — rendre la couverture des sources explicite et bloquante (#216); `bbf49d33` 2026-08-28 Audit — fiabiliser l’analyse des affectations conditionnelles (#218); `ce979bbd` 2026-08-25 Hardening : passe globale anti-bugs avant RC (#98); `d5c18ac0` 2026-08-28 Audit — importer les signatures de défauts découvertes dans Teamworks (#217); `e016bb8b` 2026-08-25 Audit sémantique — pièges Python et asymétries métier (#100)

### E02 — CI, packaging PyInstaller, hooks runtime figés, lanceur dev Windows, installateur Vanilla+  
**Classement : D**

main possède sa propre chaîne (workflows noethys-sl-fast.yml, noethys-sl-windows.yml, vanilla-*.yml, packaging/vanilla-installer.iss, packaging/vanilla-noethys.spec, crashreports locaux Vanilla #196). Les workflows de master (ci.yml, windows-package.yml, release-candidate.yml, actions-history-maintenance.yml) et les hooks runtime_* ciblent l'arbre master. Idées éventuellement réutilisables : runtime_crashlog/runtime_perf (diagnostic de gel), config_profile.py (export/import de profil) — à requalifier, jamais à copier.

- Lignes uniques : 4446 (dont 508 en tests) ; 61 fichiers ; 110 commits ; PR : PR #324, #333, #354, #357
- Dépendance SQL : aucune (scripts de recette lisent des bases en lecture seule)
- Fichiers principaux : `scripts/recette_existing_db_readonly.py` (308), `packaging/runtime_crashlog.py` (270), `.github/workflows/windows-package.yml` (267), `.github/workflows/ci.yml` (259), `scripts/audit_runtime_patterns.py` (232), `scripts/rc_db_preflight.py` (232), `scripts/audit_runtime_hardening.py` (198), `packaging/runtime_perf.py` (195)
- Commits représentatifs : `ce979bbd` 2026-08-25 Hardening : passe globale anti-bugs avant RC (#98); `758efc3b` 2026-09-02 Windows — reconstruire l’installateur et préserver la configuration (#324); `acedfa58` 2026-08-19 Noe-030: prepare safe recipe on an existing database copy; `c254d955` 2026-08-19 Noe-030: unify real-database RC preflight; `5636c933` 2026-08-20 Diagnostic perf : fenêtres, MySQL WAN et faux gels

### E03 — SQL strict (ONLY_FULL_GROUP_BY) et audit d'index (Noe-001 à Noe-004)  
**Classement : A+C**

Deux correctifs de requêtes encore absents de main (OL_Reglements, export Quadra/Cerig : voir A01, A02) ; l'outillage d'audit SQL/index est C.

- Lignes uniques : 1065 (dont 395 en tests) ; 8 fichiers ; 11 commits ; PR : PR #41
- Dépendance SQL : aucune (requêtes de lecture)
- Fichiers principaux : `scripts/audit_sql_strict.py` (338), `scripts/audit_db_indexes.py` (262), `tests/test_noe_003_export_compta_sql.py` (159), `tests/test_noe_002_ol_reglements_sql.py` (96), `scripts/audit_sql_group_by.py` (70), `tests/test_noe_004_index_audit.py` (48), `tests/test_noe_003_cotisation_invariant.py` (47), `tests/test_noe_001_sql_audit.py` (45)
- Commits représentatifs : `f89b74bd` 2026-08-19 Noe-001: close out strict SQL audit inventory; `cb6d2384` 2026-08-19 Noe-004: add read-only index plans and timings; `5869fe52` 2026-08-19 Noe-003: add export compta SQL regression tests; `330475aa` 2026-08-19 Noe-002: add SQL regression test for OL_Reglements; `f024c282` 2026-08-19 Noe-004: add read-only database index audit tool

### E04 — Sécurité : suppression des eval(), chargement des extensions, SFTP/FTPS portail  
**Classement : A+B+C**

main contient encore 58 appels eval() hors commentaires (master : 1). Les remplacements par ast.literal_eval de données sérialisées (paramètres, filtres, commandes, profils) et le durcissement de DLG_Extensions sont des correctifs ponctuels (A22, A21). Les formules métier (CTRL_Grille, DLG_Etat_global, DLG_Saisie_formule, OL_Suivi_budget, OL_Etat_nomin_resultats, filtres ObjectListView) dépendent du nouvel évaluateur UTILS_Expressions.py (136 lignes, sans test dédié sur master) : B. Les eval de pages (setattr(... eval(ctrlPage))) sont un refactor sans gain de sécurité. Mémorisation de clé hôte SFTP et FTPS (75c034ac, 7ecb6cfd) : réseau, C. Le chargement isolé de models.py (5a1c3cc6) est déjà repris dans main (a139b766).

- Lignes uniques : 360 (dont 0 en tests) ; 26 fichiers ; 22 commits ; PR : -
- Dépendance SQL : aucune
- Fichiers principaux : `noethys/Utils/UTILS_Expressions.py` (117), `noethys/Utils/UTILS_Portail_synchro.py` (41), `noethys/Dlg/DLG_Portail_config.py` (34), `noethys/Ctrl/CTRL_Saisie_transport.py` (31), `noethys/Dlg/DLG_Filtres_listes.py` (19), `noethys/Dlg/DLG_Extensions.py` (18), `noethys/Ctrl/CTRL_Grille.py` (16), `noethys/Dlg/DLG_Famille.py` (12)
- Commits représentatifs : `2c7e323c` 2026-08-15 security: étendre l'évaluateur sûr aux filtres booléens; `7fb3abd8` 2026-08-15 security: supprimer deux eval mécaniques supplémentaires; `d85f4648` 2026-08-15 security: supprimer eval du formulaire transport; `429bd8b2` 2026-08-15 security: ajouter un évaluateur arithmétique sûr; `6975937a` 2026-08-15 security: supprimer eval des notebooks famille et individu

### E05 — Écritures transactionnelles (« atomiser » : commit=False + rollback)  
**Classement : B**

61 commits du 15-17/08/2026 rendant atomiques les écritures (règlements, prestations, factures, PES/SEPA, inscriptions, contrats PSU, locations, portail...). Prérequis : GestionDB de master (ReqDEL/ReqMAJ/Executermany/MAJimage renvoient True/False et font rollback : commits dd056f3e, 88a124ea, af36b076, 63f00830). main:noethys/GestionDB.py ne renvoie ni booléen ni rollback (ReqMAJ L444, ReqDEL L471) ; main compte 51 usages de commit=False contre 320 sur master. Aucun test dédié sur master. Intégrable sans migration SQL mais touche les flux financiers : reprise par lots testés + recette sur copie.

- Lignes uniques : 1428 (dont 0 en tests) ; 69 fichiers ; 61 commits ; PR : -
- Dépendance SQL : aucune (changement de sémantique transactionnelle uniquement)
- Fichiers principaux : `noethys/Ol/OL_PES_pieces.py` (86), `noethys/Dlg/DLG_Saisie_contrat.py` (73), `noethys/Dlg/DLG_Saisie_aide.py` (49), `noethys/Ol/OL_Prelevements_sepa.py` (45), `noethys/Ol/OL_Prelevements_national.py` (42), `noethys/Dlg/DLG_Activite.py` (41), `noethys/Ctrl/CTRL_Tarification.py` (41), `noethys/Dlg/DLG_Saisie_depot_cotisation.py` (36)
- Commits représentatifs : `8e3b56cd` 2026-08-17 fix: atomiser les lots PES et leurs règlements; `6cb53946` 2026-08-15 fix: atomiser les suppressions famille et activité; `4e3b30dd` 2026-08-16 fix: atomiser la sauvegarde des contrats PSU; `4c5fa39b` 2026-08-16 fix: atomiser la sauvegarde des aides; `e77dafaa` 2026-08-16 fix: sécuriser dépôts et cotisations

### E06 — Python 3 : encodages, frontières bytes/texte, dates ISO, géométries wx  
**Classement : A+D**

Les vrais défauts encore présents dans main sont repris en A03-A05 et A06 (exports Corail/JVS/PES et export texte). Le reste est de la modernisation sans changement de comportement (date.fromisoformat, encoding='utf-8' dans des outils de développement de FonctionsPerso, littéraux bruts) : D/optionnel. Les géométries flottantes wx ont été traitées dans main par 50df5a10 pour les cas qualifiés.

- Lignes uniques : 292 (dont 2 en tests) ; 170 fichiers ; 28 commits ; PR : -
- Dépendance SQL : aucune
- Fichiers principaux : `noethys/Utils/UTILS_Adaptations.py` (20), `noethys/FonctionsPerso.py` (19), `noethys/Ol/OL_Activites.py` (12), `noethys/Outils/mail/module_loading.py` (8), `noethys/Utils/UTILS_Envoi_email.py` (7), `noethys/Utils/UTILS_Internet.py` (6), `noethys/Outils/wxSchedulerPaint.py` (6), `noethys/Noethys.py` (5)
- Commits représentatifs : `46204e6a` 2026-08-14 fix: moderniser les constructions de dates ISO simples; `8a4b7491` 2026-08-14 fix: moderniser les derniers motifs de dates simples; `910cc8f5` 2026-08-15 fix: expliciter les derniers encodages texte; `59d09942` 2026-08-14 fix: convertir les géométries wxPython en entiers; `381eff48` 2026-08-15 refactor: supprimer l'import dynamique des assistants activité

### E07 — Robustesse des imports/exports (NoethysWeb, documents, badgeage, vacances, portail)  
**Classement : A**

Correctifs ponctuels avec défaut vérifié dans main : A12-A15, A23. 8f545e4a et 871bc89b sont déjà repris.

- Lignes uniques : 76 (dont 18 en tests) ; 10 fichiers ; 9 commits ; PR : PR #305
- Dépendance SQL : aucune
- Fichiers principaux : `noethys/Utils/UTILS_Export_noethysweb.py` (20), `tests/test_export_compta_batch_22.py` (18), `noethys/Dlg/DLG_Badgeage_importation.py` (10), `noethys/Dlg/DLG_Export_compta.py` (8), `noethys/Utils/UTILS_Export.py` (5), `noethys/Utils/UTILS_Portail_synchro.py` (4), `noethys/Dlg/DLG_Export_noethysweb.py` (4), `noethys/Dlg/DLG_Importation_vacances.py` (4)
- Commits représentatifs : `871bc89b` 2026-09-01 Fix — fiabiliser deux chemins de l’export comptable (#305); `6f7eb0a9` 2026-08-15 fix: ne plus annoncer un export NoethysWeb en échec comme réussi; `9a0b010f` 2026-08-15 fix: sécuriser les imports Excel et CSV de badgeage; `b829f184` 2026-08-15 fix: protéger les exports contre les données absentes; `8bef9bf1` 2026-08-15 fix: durcir les erreurs des exports génériques et web

### E08 — Correctifs UI ponctuels (double-clic ObjectListView/menus, bouton, Mailer)  
**Classement : A?+B+D**

CTRL_Menus (89fe8f70) : défaut présent, à confirmer en recette Windows (A26). Double-clic ObjectListView global (ef88a717, 80 lignes) : B à qualifier. Bouton (31229aa2) et Mailer (12703e35) : corrigent du code propre à master, D.

- Lignes uniques : 72 (dont 0 en tests) ; 4 fichiers ; 4 commits ; PR : -
- Dépendance SQL : aucune
- Fichiers principaux : `noethys/Utils/UTILS_Adaptations.py` (60), `noethys/Ctrl/CTRL_Recherche_individus.py` (5), `noethys/Ctrl/CTRL_Bouton_image.py` (5), `noethys/Ctrl/CTRL_Menus.py` (2)
- Commits représentatifs : `ef88a717` 2026-08-20 Fix ObjectListView double-click activation globally; `12703e35` 2026-08-21 Fix UI: préremplit le Mailer via son API actuelle; `31229aa2` 2026-08-20 Fix wxPhoenix button enable state on Windows; `89fe8f70` 2026-08-20 Fix menu grid double-click editing

### E09 — Durcissement Vanilla+ / passe anti-bugs #98 / cycle de vie wx  
**Classement : A+D**

La plupart ont été rétroportés dans main par la lignée Vanilla (#124-#205, #359/#360) : déjà repris (iCalendar, modaux, pauses, conversions, titulaires, étiquettes, PES inconnu, dons aux œuvres, durées, mutables). Restent dans main : DLG_Updater.isAlive() et 4 gardes IndexError de #98 (A20). Découplages GetGrandParent (86814b0f, dd93f248, 5e7eb0b0, 9eb3386b) : utiles seulement avec la hiérarchie de fenêtres Repens, D. b55df62c : main transmet déjà l'IDfacture (CTRL_Numfacture.py L160).

- Lignes uniques : 1582 (dont 1260 en tests) ; 248 fichiers ; 25 commits ; PR : PR #90, #98, #100, #101, #103-#123, #358, #360
- Dépendance SQL : aucune
- Fichiers principaux : `tests/test_utils_dates_duration_contract.py` (73), `tests/test_unbound_after_try_audit.py` (66), `tests/test_remplissage_dialog_dates_contract.py` (63), `tests/test_utils_dates_branch_assignment_contract.py` (63), `tests/test_utils_icalendar_contract.py` (62), `tests/test_semantic_modal_destroy_contract.py` (62), `tests/test_nonblocking_ui_callbacks_contract.py` (57), `tests/test_silent_exception_handlers_audit.py` (55)
- Commits représentatifs : `ce979bbd` 2026-08-25 Hardening : passe globale anti-bugs avant RC (#98); `0224957b` 2026-08-25 Hardening UI — sécuriser les contrôles tarifaires partagés (#101); `f777c6cf` 2026-09-07 Vanilla — afficher directement la liste et verrouiller le thème clair (#358); `678f0560` 2026-08-29 Fix — sécuriser les conversions et arrondis horaires (#227); `0b3e18dc` 2026-09-07 Vanilla — réparer Affichage et Liste d’attente sur dates Python 3 (#360)

### E10 — Contrats de branches conditionnelles (#219-#262, #297-#349) et petits correctifs  
**Classement : A+B**

Série issue de l'audit branch_assignment_gap : la majorité rend explicites des if/elif sur des domaines finis (ValueError au lieu d'UnboundLocalError sur entrée impossible) — durcissement défensif optionnel (B, avec tests). Une douzaine corrigent un défaut atteignable, vérifié dans main : A07-A11, A16-A19, A24-A27. Déjà repris : tarifs famille horaires (1bf1208b, ccdb53b7, 28764006), #302, #297, #311, #314, #330, #334, GetHTML (#329 ~ bf69d3ca), #230. Contient aussi UTILS_Villes (E22) et le chargement différé des consommations (E23).

- Lignes uniques : 3651 (dont 2857 en tests) ; 127 fichiers ; 67 commits ; PR : PR #219-#262, #297-#349, #350, #351
- Dépendance SQL : aucune
- Fichiers principaux : `noethys/Dlg/DLG_Impression_conso_differe.py` (224), `tests/test_ventilation_regroupement_contract.py` (188), `tests/test_ctrl_grille_family_hourly_recalculation.py` (113), `tests/test_nbre_inscrits_gauge_color_contract.py` (99), `tests/test_ctrl_grille_family_count_tariffs.py` (97), `tests/test_activity_filter_branch_contract.py` (91), `tests/test_ctrl_grille_family_hourly_unmatched_range.py` (90), `tests/test_sepa_reglement_history_contract.py` (87)
- Commits représentatifs : `96ec3f7c` 2026-08-21 Fix: charger la liste des consommations par étapes; `35dc5e38` 2026-08-29 Fix — durcir les regroupements de ventilation (#226); `ccdb53b7` 2026-09-03 Fix: neutraliser les tarifs famille hors tranche horaire; `fabc99bf` 2026-08-30 Fix — clarifier les états couleur de la jauge inscriptions (#238); `0bc85e4f` 2026-08-29 Fix — sécuriser les filtres d’activité (#235)

### E11 — Sauvegarde/restauration Noe-032 (variante master #352)  
**Classement : D**

Remplacé par l'implémentation de main, plus récente et qualifiée (UTILS_SQL_Integrite.py, manifeste SQL V1, analyse syntaxique des dumps, refus des dumps vides, bac à sable MySQL 5.5 — commits du 09-12/10/2026). main:noethys/Utils/UTILS_Sauvegarde.py L174 appelle UTILS_SQL_Integrite.AjouterManifesteIntegriteSQL. Les 20 fonctions privées de master (_AnalyserDumpSQL, _AjouterMarqueurTerminalSQL...) peuvent servir de comparaison, pas de source.

- Lignes uniques : 1042 (dont 483 en tests) ; 5 fichiers ; 6 commits ; PR : PR #33, #327, #352
- Dépendance SQL : aucune table ; restauration MySQL
- Fichiers principaux : `noethys/Utils/UTILS_Sauvegarde.py` (346), `tests/test_noe_032_restore_flow.py` (294), `scripts/qualify_noe032_mysql.py` (212), `tests/test_noe_032_backup_integrity.py` (189), `noethys/Utils/UTILS_Sauvegarde_auto.py` (1)
- Commits représentatifs : `d9dd279e` 2026-09-04 Fix: sécuriser l'intégrité des sauvegardes et restaurations (#352); `f8cd03fe` 2026-08-19 Noe-032: repair and test backup restoration; `b6af1092` 2026-09-02 Audit: liquider les reliquats de flot dans UTILS_Sauvegarde (#327); `c2f92cc8` 2026-08-15 fix: signaler les sauvegardes non copiées; `f5c0fabf` 2026-08-14 fix: fiabiliser les fichiers texte internes

### E12 — Migration contrôlée d'une base vers une base neuve (UTILS_Migration_base)  
**Classement : C**

Moteur de migration de dossiers (analyse/plan/exécution transactionnelle sur cible). Migration de données : hors publication sans qualification sur copies, sauvegarde/rollback.

- Lignes uniques : 939 (dont 246 en tests) ; 9 fichiers ; 15 commits ; PR : -
- Dépendance SQL : écrit toutes les tables cœur d'une base cible
- Fichiers principaux : `noethys/Utils/UTILS_Migration_base.py` (496), `tests/test_migration_base.py` (234), `noethys/Dlg/DLG_Active_prelevement.py` (107), `noethys/Dlg/DLG_Activite_calendrier.py` (37), `noethys/Ctrl/CTRL_Agenda.py` (26), `tests/test_common_ui_modernization_contract.py` (12), `noethys/Ctrl/CTRL_Saisie_releve_bancaire.py` (10), `noethys/Ctrl/CTRL_Profil.py` (9)
- Commits représentatifs : `48882430` 2026-08-17 feat: fiabiliser les références du migrateur DB; `e2059598` 2026-08-17 feat: compléter les références des dossiers; `effa48f9` 2026-08-21 ui: migrate automatic debit dialog to Repens shell; `985f41da` 2026-08-17 feat: ajouter le moteur transactionnel de migration; `25f35eda` 2026-08-17 feat: préparer le plan et le mapping de migration

### E13 — Noe-062 : tiers/structures, contacts, groupes/rôles, relations contractuelles, payeurs, conventions versionnées, documents  
**Classement : C**

Prototype schéma-dépendant. main a choisi un autre modèle pour les conventions (génération Noedoc/Word sans nouvelle table : UTILS_Convention_champs.py, UTILS_Convention_docx.py, DLG_Generation_convention.py) et les adhésions (UTILS_Adhesions.py).

- Lignes uniques : 4228 (dont 1443 en tests) ; 25 fichiers ; 13 commits ; PR : PR #212, #213, #215, #298, #300, #301, #306, #308, #309
- Dépendance SQL : crée structures, structures_contacts, structures_roles_contacts, structures_categories(_liens), structures_tags(_liens), structures_groupes, structures_relations, structures_payeurs, structures_conventions (DATA_Structures.py, DATA_Conventions_Structures.py)
- Fichiers principaux : `noethys/Utils/UTILS_Programmations_Structures.py` (532), `noethys/Utils/UTILS_Relations_Structures.py` (402), `noethys/Utils/UTILS_Conventions_Structures.py` (353), `noethys/Utils/UTILS_Conventions_Structures_Documents.py` (275), `tests/test_noe_062_conventions_avenants.py` (268), `noethys/Utils/UTILS_Tiers.py` (258), `tests/test_noe_062_relations_contractuelles.py` (230), `noethys/Utils/UTILS_Tiers_Schema.py` (199)
- Commits représentatifs : `91c20d63` 2026-09-01 Noe-062 : conventions versionnées et avenants figés (#301); `a6d1fe81` 2026-09-01 Noe-062E : persister les programmations annuelles et créneaux; `1aba223d` 2026-09-01 Noe-062 : relations contractuelles, adhésion et payeurs (#300); `db7a9a05` 2026-09-01 Noe-062 : générer les documents depuis les snapshots figés; `6226a68e` 2026-08-27 Noe-062A — poser le référentiel tiers et contacts

### E14 — Noe-062 : programmations annuelles, matérialisation en séances, séances sport écoles, lieux, prévu/réalisé  
**Classement : C**

Prototype schéma-dépendant (interventions/séances). Touche le pointage (prévu/réalisé) : hors publication.

- Lignes uniques : 2424 (dont 726 en tests) ; 16 fichiers ; 6 commits ; PR : PR #214, #249, #310, #312, #322
- Dépendance SQL : crée interventions, lieux, interventions_execution, structures_programmations, structures_programmations_creneaux, interventions_programmations
- Fichiers principaux : `noethys/Utils/UTILS_Programmations_Interventions.py` (331), `noethys/Utils/UTILS_Interventions_Actual_Inbox.py` (262), `tests/test_noe_062_programmations_persistantes.py` (247), `noethys/Dlg/DLG_Seances_sport_ecoles.py` (244), `tests/test_noe_062_materialisation_interventions.py` (228), `noethys/Utils/UTILS_Interventions.py` (208), `tests/test_noe_062c_execution.py` (180), `noethys/Utils/UTILS_Interventions_Execution.py` (156)
- Commits représentatifs : `70af4911` 2026-09-01 Noe-062E : matérialiser les programmations validées en séances; `8d40cec5` 2026-08-31 Noe-062C : lieux canoniques et prévu/réalisé des séances; `fd7c3940` 2026-08-27 Noe-062B — séances de sport pour les écoles; `6a126dc5` 2026-09-02 Noe-062 : recevoir le réalisé validé par UID de séance; `a6d1fe81` 2026-09-01 Noe-062E : persister les programmations annuelles et créneaux

### E15 — Noe-062 : inter-domaines (enveloppe, mailbox pull, inbox du réalisé)  
**Classement : C**

Réseau + pointage + nouvelle table : hors publication.

- Lignes uniques : 795 (dont 472 en tests) ; 5 fichiers ; 3 commits ; PR : PR #318, #325, #353
- Dépendance SQL : crée interventions_execution_inbox
- Fichiers principaux : `tests/test_noe_062_session_actual_inbox.py` (232), `noethys/Utils/UTILS_Interdomain_Mailbox_Client.py` (171), `noethys/Utils/UTILS_Interdomain_Delivery.py` (152), `tests/test_noe_062_inter_domain_mailbox_client.py` (131), `tests/test_noe_062_inter_domain_delivery.py` (109)
- Commits représentatifs : `c51712e0` 2026-09-04 Noe-062 : ajouter le client pull de mailbox inter-domaines; `45f4fd48` 2026-09-02 Noe-062 : vérifier l’enveloppe inter-domaines avant le réalisé (#325); `6a126dc5` 2026-09-02 Noe-062 : recevoir le réalisé validé par UID de séance

### E16 — Synchronisation PMSL (pull/simulation/application/ACK, export retour, passerelle HMAC)  
**Classement : C**

Client réseau (urllib + HMAC) qui écrit dans ouvertures ; écran DLG_PMSL_Synchronisation et entrée de menu. Réseau non qualifié.

- Lignes uniques : 1000 (dont 284 en tests) ; 10 fichiers ; 23 commits ; PR : -
- Dépendance SQL : écrit ouvertures ; lit activites, groupes, unites, unites_groupes, interventions
- Fichiers principaux : `noethys/Dlg/DLG_PMSL_Synchronisation.py` (266), `noethys/Utils/UTILS_PMSL_Openings.py` (151), `tests/test_pmsl_openings.py` (125), `noethys/Utils/UTILS_PMSL_NoethysBridge.py` (95), `tests/test_pmsl_sync.py` (94), `noethys/Utils/UTILS_PMSL_Export.py` (93), `noethys/Utils/UTILS_PMSL_Sync.py` (66), `tests/test_pmsl_export.py` (65)
- Commits représentatifs : `5c984dca` 2026-08-16 feat(pmsl): ajouter l'écran de synchronisation Noethys; `c2025af6` 2026-08-16 feat(pmsl): simuler et appliquer les ouvertures PMSL; `07e268c9` 2026-08-16 feat(pmsl): ajouter le client de passerelle native; `07fceb67` 2026-08-16 test(pmsl): couvrir la sémantique Noethys des groupes d'unité; `138022e4` 2026-08-16 feat(pmsl): exporter le référentiel et calendrier Noethys vers PMSL

### E17 — Commande de repas automatique (points de livraison, animateurs, réservations réelles)  
**Classement : B**

CTRL_Commande_repas_auto.py (lecture seule : consommations, modeles_commandes_colonnes, unites, activites, groupes) enveloppe CTRL_Commande_repas ; DLG_Saisie_commande_auto.py / DLG_Saisie_commandes_colonne_layout.py. Test tests/test_pmsl_meal_orders.py. Sans migration ; à recetter.

- Lignes uniques : 373 (dont 41 en tests) ; 8 fichiers ; 13 commits ; PR : PR #46
- Dépendance SQL : aucune (lecture)
- Fichiers principaux : `noethys/Ctrl/CTRL_Commande_repas_auto.py` (262), `tests/test_pmsl_meal_orders.py` (41), `noethys/Dlg/DLG_Saisie_commandes_colonne_layout.py` (38), `noethys/Dlg/DLG_Saisie_commande_auto.py` (15), `noethys/Dlg/DLG_Saisie_commandes_colonne.py` (8), `noethys/Dlg/DLG_Commandes.py` (5), `noethys/Ctrl/CTRL_Commande_repas.py` (2), `noethys/Dlg/DLG_Saisie_commande.py` (2)
- Commits représentatifs : `1d40b199` 2026-08-20 Add contextual meal suggestion details; `30e74407` 2026-08-20 Fix meal orders from actual reservations; `bfe519ee` 2026-08-20 Split automatic meal columns when activity has multiple groups; `2abbfa5f` 2026-08-20 Commandes repas : points de livraison, animateurs et dates réelles; `996f3308` 2026-08-20 Fix expandable meal-order selectors

### E18 — Refonte UI « Repens » (fenêtres, listes, surfaces, typographie, cockpit)  
**Classement : C**

Refonte transverse non qualifiée. main a explicitement verrouillé l'apparence claire historique (aa88f53a #375, f39aa30f). À archiver.

- Lignes uniques : 6619 (dont 1489 en tests) ; 128 fichiers ; 188 commits ; PR : PR #73-#79, #85
- Dépendance SQL : aucune
- Fichiers principaux : `noethys/Ctrl/CTRL_OutilsListeRepens.py` (244), `noethys/Ctrl/CTRL_Remplissage_Repens.py` (227), `noethys/Dlg/DLG_Saisie_rib.py` (225), `noethys/Ctrl/CTRL_FenetreRepens.py` (198), `noethys/Utils/UTILS_StyleRepens.py` (196), `noethys/Ctrl/CTRL_Calendrier_Repens.py` (189), `noethys/Dlg/DLG_Remplissage_Repens.py` (180), `noethys/Ctrl/CTRL_ActionRepens.py` (171)
- Commits représentatifs : `c81bb5a5` 2026-08-23 UI : consolider la refonte transverse Repens; `b90bfde7` 2026-08-21 UI: remplace le rendu historique de fréquentation par Repens; `2b7a1178` 2026-08-21 ui: rebuild RIB dialog on shared Repens shell; `04f53427` 2026-08-21 UI: reconstruit la navigation du calendrier en Repens; `c8e21c5e` 2026-08-21 ui: add shared Repens window shell

### E19 — Thème, échelle d'interface, mode sombre, design system, icônes modernes/Fluent, AUI responsive  
**Classement : C**

Évolution d'apparence non qualifiée, incompatible avec le choix de main (apparence claire verrouillée). Le pack d'icônes Style B (3d8aa3fa) suit le même sort.

- Lignes uniques : 6057 (dont 621 en tests) ; 88 fichiers ; 143 commits ; PR : PR #47, #50, #112, #191
- Dépendance SQL : aucune
- Fichiers principaux : `noethys/Utils/UTILS_Interface.py` (346), `noethys/Utils/UTILS_Icones_modernes.py` (269), `noethys/Utils/UTILS_Aui.py` (256), `noethys/Dlg/DLG_Echelle_interface.py` (210), `noethys/Ctrl/CTRL_TableauResponsive.py` (197), `noethys/Utils/UTILS_DesignSystem.py` (188), `noethys/Ctrl/CTRL_Recherche_individus.py` (172), `noethys/Ctrl/CTRL_Saisie_date.py` (171)
- Commits représentatifs : `97b30b83` 2026-08-20 UI : design system, composants communs et préférences d’apparence (#50); `35068bcf` 2026-08-20 Affichage : échelle globale et apparence système/clair/sombre; `f6161a2c` 2026-08-20 UI: ajoute un pack d'icônes modernes générées à la volée; `3d8aa3fa` 2026-08-26 Design — brancher le pilot pack Style B; `713016aa` 2026-08-20 UI: modernise la sélection des activités et groupes

### E20 — Tableau de bord : panneau Aujourd'hui, planning Teamworks, messagerie optionnelle, registre de modules  
**Classement : D+C**

Le panneau Aujourd'hui de main vient de RC2 (1de8c06b) : la version master est remplacée (D). Lecteur Teamworks et messagerie dockable : C (source externe, non qualifiés).

- Lignes uniques : 1217 (dont 171 en tests) ; 13 fichiers ; 20 commits ; PR : -
- Dépendance SQL : aucune
- Fichiers principaux : `noethys/Ctrl/CTRL_Ephemeride.py` (318), `noethys/Ctrl/CTRL_Planning_semaine.py` (234), `scripts/audit_teamworks_signatures.py` (219), `noethys/Ctrl/CTRL_Messagerie.py` (127), `noethys/Utils/UTILS_Teamworks_Planning.py` (116), `tests/test_teamworks_derived_signatures.py` (58), `tests/test_teamworks_week_planning_contract.py` (31), `noethys/Utils/UTILS_Modules.py` (30)
- Commits représentatifs : `d5c18ac0` 2026-08-28 Audit — importer les signatures de défauts découvertes dans Teamworks (#217); `a94f9602` 2026-08-20 Dashboard: ajoute la vue Semaine équipe Teamworks; `9055114d` 2026-08-20 Dashboard: ajoute un lecteur read-only du planning Teamworks; `a6bcb9d6` 2026-08-20 UI: remplace l'éphéméride par un panneau Aujourd'hui utile; `06a7043c` 2026-08-20 UI: prépare le panneau dockable de messagerie optionnelle

### E21 — Recherche tolérante aux accents et fautes (UTILS_Recherche)  
**Classement : B**

Module pur (re, unicodedata) + tests/test_recherche_tolerante.py ; intégration master dans CTRL_Recherche_individus (Repens) à réécrire pour main.

- Lignes uniques : 184 (dont 87 en tests) ; 3 fichiers ; 5 commits ; PR : -
- Dépendance SQL : aucune
- Fichiers principaux : `noethys/Utils/UTILS_Recherche.py` (97), `tests/test_recherche_accueil_ui_contract.py` (52), `tests/test_recherche_tolerante.py` (35)
- Commits représentatifs : `a2a6fb36` 2026-08-20 UI: ajoute une recherche tolérante accents et petites fautes; `f777c6cf` 2026-09-07 Vanilla — afficher directement la liste et verrouiller le thème clair (#358); `d057e7cf` 2026-08-20 Tests: garde un chemin ASCII pour la recherche tolérante; `b6eab718` 2026-08-20 Tests: verrouille le module de recherche search-first; `085ce128` 2026-08-20 Recherche: évite les faux positifs sur prénoms très courts

### E22 — Couples ville/code postal (UTILS_Villes) et communes homonymes  
**Classement : A**

e801bb3a (module pur 55 lignes + tests/test_villes.py) et 79680bda : main:noethys/Ctrl/CTRL_Saisie_adresse.py L199 contient encore `nbreCodes = self.listeNomsVilles.count(villeSelect)` : la perte de focus peut remplacer le code postal choisi par celui d'un homonyme. Voir A27.

- Fichiers : `noethys/Utils/UTILS_Villes.py`, `noethys/Ctrl/CTRL_Saisie_adresse.py`, `tests/test_villes.py`

### E23 — Chargement différé de la liste des consommations (DLG_Impression_conso_differe)  
**Classement : B**

96ec3f7c (270 lignes) + routage Dlg/__init__.py. main a traité la cause racine du crash des listes autrement (64d15533, arrêt des timers). Gain de performance à requalifier sur main.

- Fichiers : `noethys/Dlg/DLG_Impression_conso_differe.py`, `noethys/Dlg/__init__.py`

## 4. Corrections candidates (A)

Chaque entrée a été vérifiée dans le contenu de `origin/main` ; le même défaut est présent aux mêmes lignes dans `origin/wx` et `origin/qt` (contrôlé par recherche de la ligne fautive). Statut matrice pour les trois branches : **ABSENT** tant que la reprise n'est pas faite.

| Code | Commit source | Fichier(s) | Défaut dans main | Test master |
|---|---|---|---|---|
| A01 | `0753bf71` (2026-08-19) | `noethys/Ol/OL_Reglements.py` | main:noethys/Ol/OL_Reglements.py L182 `GROUP BY reglements.IDreglement` avec `SUM(ventilation.montant)` + LEFT JOIN ventilation (échec MySQL ONLY_FULL_GROUP_BY) | tests/test_noe_002_ol_reglements_sql.py (330475aa) |
| A02 | `f0256647` (2026-08-19) | `noethys/Dlg/DLG_Export_compta.py` | main:noethys/Dlg/DLG_Export_compta.py L894 et L1252 `LEFT JOIN cotisations ON cotisations.IDprestation = prestations.IDprestation` + GROUP BY prestations.IDprestation | tests/test_noe_003_export_compta_sql.py (5869fe52) |
| A03 | `299dbcc3` (2026-08-14) | `noethys/Dlg/DLG_Saisie_lot_tresor_public_corail.py`<br>`noethys/Utils/UTILS_Corail.py`<br>`noethys/Utils/UTILS_Jvs.py` | main:noethys/Dlg/DLG_Saisie_lot_tresor_public_corail.py L452-454 `open(..., "w")` puis `f.write(doc.toprettyxml(indent="  ", encoding="UTF-8"))` : octets écrits dans un fichier texte -> TypeError sous Python 3. Même motif (code non appelé) dans UTILS_Corail.py | — |
| A04 | `b2ce3aef` (2026-08-15) | `noethys/Dlg/DLG_Saisie_lot_tresor_public_jvs.py`<br>`noethys/Utils/UTILS_Prelevements.py`<br>`noethys/Dlg/DLG_Traductions.py` | main:noethys/Dlg/DLG_Saisie_lot_tresor_public_jvs.py L450-456 `open(cheminFichier, "w")` + `f.write(doc.toxml())` (sans encodage : cp1252 sous Windows, sans déclaration d'encodage). UTILS_Prelevements.EnregistrerXML L772-774 même motif (non appelé). | — |
| A05 | `910cc8f5` (2026-08-15) | `noethys/Dlg/DLG_Saisie_lot_tresor_public_pes.py` | main:noethys/Dlg/DLG_Saisie_lot_tresor_public_pes.py L492-498 `open(cheminFichier, "w")` puis, en Python 3, `f.write(doc.toxml())` : encodage local et déclaration ISO-8859-1 perdus. | — |
| A06 | `a6a960bf + 8bef9bf1` (2026-08-14/15) | `noethys/Utils/UTILS_Export.py` | main:noethys/Utils/UTILS_Export.py L157 `f = open(cheminFichier, "w")` sans encodage (cp1252 sous Windows : UnicodeEncodeError possible, fichier non UTF-8) ; aucune gestion d'OSError. | — |
| A07 | `8afab828` (2026-08-28) | `noethys/Dlg/DLG_Individu.py` | main:noethys/Dlg/DLG_Individu.py L427-430 : la boucle construit texteNoms puis l'écrase par `listeNomsTitulaires[-2] et [-1]` (seuls les deux derniers titulaires affichés). | tests/test_individu_rattachement_hardening.py |
| A08 | `d27b43fa` (2026-08-31) | `noethys/Utils/UTILS_Utilisateurs.py` | main:noethys/Utils/UTILS_Utilisateurs.py L125 `mode, listeID = code.split(":")` puis int() sans garde : ValueError si la restriction est vide ou mal formée. | tests/test_branch_contracts_batch_16.py |
| A09 | `25ad1e95` (2026-09-03) | `noethys/Dlg/DLG_Saisie_tarification.py` | main:noethys/Dlg/DLG_Saisie_tarification.py L434 `if self.toolbook.GetPage("conditions") != None :` exécute ReqDEL sur questionnaire_filtres même quand track_tarif est fourni (la base n'est fermée que si track_tarif == None, L440). | tests/test_tarification_track_filter_delete.py |
| A10 | `ee99d698` (2026-08-28) | `noethys/Dlg/DLG_Saisie_portail_demande.py` | main:noethys/Dlg/DLG_Saisie_portail_demande.py L1260-1264 : `if texte[0] == "F"` / `"P"` sans else (un préfixe inconnu réutilise le type précédent ou lève UnboundLocalError ; une virgule finale lève IndexError). | tests/test_portail_payment_ventilation_contract.py |
| A11 | `08baa60e` (2026-08-17) | `noethys/Dlg/DLG_Saisie_portail_demande.py` | main:noethys/Dlg/DLG_Saisie_portail_demande.py L1299 `IDcompte_bancaire = DB.ResultatReq()[0][0]` (IndexError si la facture n'a pas de régie). | — |
| A12 | `6f7eb0a9` (2026-08-15) | `noethys/Dlg/DLG_Export_noethysweb.py`<br>`noethys/Utils/UTILS_Export_noethysweb.py` | main:noethys/Dlg/DLG_Export_noethysweb.py L257 ignore le résultat de Export_all ; UTILS_Export_noethysweb n'expose pas resultat/erreur_export. | — |
| A13 | `b829f184` (2026-08-15) | `noethys/Utils/UTILS_Export_noethysweb.py`<br>`noethys/Utils/UTILS_Export_documents.py` | main:noethys/Utils/UTILS_Export_noethysweb.py L1271 `ResultatReq()[0][0]`, L1501 `ResultatReq()[0]` ; UTILS_Export_documents.py `nom, categorie, ... = listeDonnees[0]` sans garde. | — |
| A14 | `1ec5c6dd` (2026-08-15) | `noethys/Dlg/DLG_Importation_vacances.py`<br>`noethys/Dlg/DLG_Importation_individus.py` | main:noethys/Dlg/DLG_Importation_vacances.py L380 `cp, ville = DB.ResultatReq()[0]` (IndexError). | — |
| A15 | `9a0b010f` (2026-08-15) | `noethys/Dlg/DLG_Badgeage_importation.py` | main:noethys/Dlg/DLG_Badgeage_importation.py L24-27 `try: import xlrd / except: pass` puis usage de xlrd (NameError si absent). | — |
| A16 | `523a9a6d` (2026-08-31) | `noethys/Utils/UTILS_Archivage.py` | main:noethys/Utils/UTILS_Archivage.py L391 crée dlgAttente dans une branche conditionnelle, L475 `del dlgAttente` inconditionnel (UnboundLocalError). | tests/test_branch_contracts_batch_17.py |
| A17 | `cae2d2a7` (2026-09-01) | `noethys/Dlg/DLG_Badgeage_interface.py` | main:noethys/Dlg/DLG_Badgeage_interface.py L637 `if dictQuestions[IDquestion]["type"] == "individu" :` sans else ; listeReponses non défini ensuite (UnboundLocalError ou KeyError si la question a disparu). | tests/test_branch_contracts_batch_19.py |
| A18 | `e2accc5f` (2026-08-29) | `noethys/Dlg/DLG_Badgeage_grille.py` | main:noethys/Dlg/DLG_Badgeage_grille.py L208 et L297 `evenement = ... else None` puis poursuite du traitement avec None. | tests/test_badgeage_evenement_contract.py |
| A19 | `16621848` (2026-08-29) | `noethys/Ctrl/CTRL_Composition.py` | main:noethys/Ctrl/CTRL_Composition.py L842-846 : posCentrale défini seulement pour 1 à 5 liens (UnboundLocalError au-delà). | tests/test_composition_filiation_layout.py |
| A20 | `ce979bbd (partiel)` (2026-08-25) | `noethys/Dlg/DLG_Updater.py`<br>`noethys/Ctrl/CTRL_Detail_aides.py`<br>`noethys/Dlg/DLG_Famille_factures.py` … | main:noethys/Dlg/DLG_Updater.py L591 `self.downloader.isAlive()` (AttributeError Python >= 3.9 ; les autres isAlive ont été corrigés par Vanilla #162) ; gardes IndexError absentes : CTRL_Detail_aides.py L120, DLG_Famille_factures.py L85, DLG_Saisie_prelevement | tests/test_runtime_lookup_guards.py (master) |
| A21 | `9f9a39c2` (2026-08-15) | `noethys/Dlg/DLG_Extensions.py` | main:noethys/Dlg/DLG_Extensions.py L110-111 `sys.path.append(GetRepExtensions())` + `importlib.import_module(nom_fichier)` (nom non validé, sys.path pollué). | — |
| A22 | `b5298150, e67c1a7b, 3b21e965, 94187a5b, 4046e240, 7df20c7d` (2026-08-15) | `noethys/Utils/UTILS_Parametres.py`<br>`noethys/Dlg/DLG_Filtres_listes.py`<br>`noethys/Dlg/DLG_Saisie_commandes_colonne.py` … | main : UTILS_Parametres.py L75-79 et L152-155, DLG_Filtres_listes.py L35, DLG_Saisie_commandes_colonne.py L347/427/486/691/708, CTRL_Commande_repas.py L430/452, DLG_Saisie_commande.py L399/419, DLG_Saisie_modele_commandes.py L124/285, CTRL_Profil.py L277 : eva | — |
| A23 | `1bd709d7 (partiel)` (2026-08-15) | `noethys/Utils/UTILS_Portail_synchro.py` | main:noethys/Utils/UTILS_Portail_synchro.py L2046 `raise()` (TypeError). La vérification du résultat d'upload est déjà dans main (L1577-1584). | — |
| A24 | `fa4d3ca1 (branche refactor/ui-list-tools-repens)` (2026-08-23) | `noethys/Utils/UTILS_Fichiers.py` | main:noethys/Utils/UTILS_Fichiers.py L41-58 `os.mkdir(chemin)` sur appdirs.user_data_dir/site_data_dir (échec si les parents n'existent pas, ex. ~/.local/share sur une session Linux neuve). | tests/test_noe_041_portable_paths.py (branche) |
| A25 | `d1d8b70b + 85d42ba5 (branche refactor/ui-list-tools-repens)` (2026-08-23) | `noethys/Utils/UTILS_Config.py` | main:noethys/Utils/UTILS_Config.py L151 `valeur = defaut` (None remonte jusqu'à GestionDB quand Config.json n'existe pas encore). | tests/test_config_empty_database_contract.py (branche) |
| A26 | `89fe8f70` (2026-08-20) | `noethys/Ctrl/CTRL_Menus.py` | main:noethys/Ctrl/CTRL_Menus.py L236 `self.GetGridWindow().Bind(wx.EVT_LEFT_DCLICK, ...)` + calcul manuel de la cellule. | — |
| A27 | `e801bb3a + 79680bda` (2026-08-21) | `noethys/Utils/UTILS_Villes.py`<br>`noethys/Ctrl/CTRL_Saisie_adresse.py` | main:noethys/Ctrl/CTRL_Saisie_adresse.py L199 `nbreCodes = self.listeNomsVilles.count(villeSelect)`. | tests/test_villes.py |
| A28 | `80b0e127` (2026-08-28) | `noethys/Dlg/DLG_Importation_individus.py` | main:noethys/Dlg/DLG_Importation_individus.py L55-142 déclare `"format":"codepostal"` mais la sélection du convertisseur ne connaît que "cp" (converter non défini ou hérité de la colonne précédente). | tests/test_importation_individus_contracts.py |

#### A01 — Noe-002: OL_Reglements compatible GROUP BY strict

- Commit source : `0753bf71` (2026-08-19)
- Fichiers : `noethys/Ol/OL_Reglements.py`
- Preuve dans main : main:noethys/Ol/OL_Reglements.py L182 `GROUP BY reglements.IDreglement` avec `SUM(ventilation.montant)` + LEFT JOIN ventilation (échec MySQL ONLY_FULL_GROUP_BY)
- Test sur master : tests/test_noe_002_ol_reglements_sql.py (330475aa)
- Remarque : MySQL uniquement ; recette sur copie.

```diff
-        SUM(ventilation.montant) AS total_ventilation,
+        ventilation_totaux.total_ventilation,
-        LEFT JOIN ventilation ON reglements.IDreglement = ventilation.IDreglement
+        LEFT JOIN (SELECT IDreglement, SUM(montant) AS total_ventilation FROM ventilation GROUP BY IDreglement) ventilation_totaux ON ...
-        GROUP BY reglements.IDreglement
```

#### A02 — Noe-003: exports Quadra et Cerig compatibles SQL strict

- Commit source : `f0256647` (2026-08-19)
- Fichiers : `noethys/Dlg/DLG_Export_compta.py`
- Preuve dans main : main:noethys/Dlg/DLG_Export_compta.py L894 et L1252 `LEFT JOIN cotisations ON cotisations.IDprestation = prestations.IDprestation` + GROUP BY prestations.IDprestation
- Test sur master : tests/test_noe_003_export_compta_sql.py (5869fe52)
- Remarque : Le commit jumeau 8f545e4a est déjà repris dans main.

```diff
-        LEFT JOIN cotisations ON cotisations.IDprestation = prestations.IDprestation
+        LEFT JOIN (SELECT IDprestation, MIN(IDcotisation) AS IDcotisation FROM cotisations WHERE IDprestation IS NOT NULL GROUP BY IDprestation) cotisation_unique ...
+        LEFT JOIN cotisations ON cotisations.IDcotisation = cotisation_unique.IDcotisation
-        GROUP BY prestations.IDprestation
```

#### A03 — Export Corail : écrire le XML en binaire

- Commit source : `299dbcc3` (2026-08-14)
- Fichiers : `noethys/Dlg/DLG_Saisie_lot_tresor_public_corail.py`, `noethys/Utils/UTILS_Corail.py`, `noethys/Utils/UTILS_Jvs.py`
- Preuve dans main : main:noethys/Dlg/DLG_Saisie_lot_tresor_public_corail.py L452-454 `open(..., "w")` puis `f.write(doc.toprettyxml(indent="  ", encoding="UTF-8"))` : octets écrits dans un fichier texte -> TypeError sous Python 3. Même motif (code non appelé) dans UTILS_Corail.py L542, UTILS_Jvs.py L522, UTILS_Pes.py L488.
- Test sur master : aucun — à écrire lors de la reprise
- Remarque : Ajouter un test d'écriture sur fichier temporaire.

```diff
-        f = open(os.path.join(rep_temp, nom_fichier + ".xml"), "w")
+        f = open(os.path.join(rep_temp, nom_fichier + ".xml"), "wb")
```

#### A04 — Export JVS : XML UTF-8 binaire déclaré

- Commit source : `b2ce3aef` (2026-08-15)
- Fichiers : `noethys/Dlg/DLG_Saisie_lot_tresor_public_jvs.py`, `noethys/Utils/UTILS_Prelevements.py`, `noethys/Dlg/DLG_Traductions.py`
- Preuve dans main : main:noethys/Dlg/DLG_Saisie_lot_tresor_public_jvs.py L450-456 `open(cheminFichier, "w")` + `f.write(doc.toxml())` (sans encodage : cp1252 sous Windows, sans déclaration d'encodage). UTILS_Prelevements.EnregistrerXML L772-774 même motif (non appelé).
- Test sur master : aucun — à écrire lors de la reprise
- Remarque : Vérifier l'accent dans un nom de débiteur.

```diff
-        f = open(cheminFichier, "w")
+        f = open(cheminFichier, "wb")
-            if six.PY2: f.write(doc.toxml(encoding="UTF-8"))
-            else: f.write(doc.toxml())
+            f.write(doc.toxml(encoding="UTF-8"))
```

#### A05 — Export PES : conserver le contrat ISO-8859-1

- Commit source : `910cc8f5` (2026-08-15)
- Fichiers : `noethys/Dlg/DLG_Saisie_lot_tresor_public_pes.py`
- Preuve dans main : main:noethys/Dlg/DLG_Saisie_lot_tresor_public_pes.py L492-498 `open(cheminFichier, "w")` puis, en Python 3, `f.write(doc.toxml())` : encodage local et déclaration ISO-8859-1 perdus.
- Test sur master : aucun — à écrire lors de la reprise
- Remarque : Le reste du commit (FonctionsPerso, outils dev) est de la modernisation.

```diff
-        f = open(cheminFichier, "w") ... f.write(doc.toxml())
+        with open(cheminFichier, "wb") as f:
+            f.write(doc.toxml(encoding="ISO-8859-1"))
```

#### A06 — Export texte des listes en UTF-8 et erreurs d'écriture signalées

- Commit source : `a6a960bf + 8bef9bf1` (2026-08-14/15)
- Fichiers : `noethys/Utils/UTILS_Export.py`
- Preuve dans main : main:noethys/Utils/UTILS_Export.py L157 `f = open(cheminFichier, "w")` sans encodage (cp1252 sous Windows : UnicodeEncodeError possible, fichier non UTF-8) ; aucune gestion d'OSError.
- Test sur master : aucun — à écrire lors de la reprise
- Remarque : Changement visible : le fichier devient UTF-8 (prévenir les utilisateurs Excel).

```diff
-    f = open(cheminFichier, "w")
+    try:
+        with open(cheminFichier, "w", encoding="utf-8") as f:
+            f.write(texte)
+    except OSError as err: ... return False
```

#### A07 — Rattachements : libellé des familles à plus de deux titulaires (#224)

- Commit source : `8afab828` (2026-08-28)
- Fichiers : `noethys/Dlg/DLG_Individu.py`
- Preuve dans main : main:noethys/Dlg/DLG_Individu.py L427-430 : la boucle construit texteNoms puis l'écrase par `listeNomsTitulaires[-2] et [-1]` (seuls les deux derniers titulaires affichés).
- Test sur master : tests/test_individu_rattachement_hardening.py

```diff
-                texteNoms = _(u"%s et %s") % (dictFamilles[IDfamille]["listeNomsTitulaires"][-2], dictFamilles[IDfamille]["listeNomsTitulaires"][-1])
+                texteNoms = u", ".join(dictFamilles[IDfamille]["listeNomsTitulaires"][:-1])
+                texteNoms = _(u"%s et %s") % (texteNoms, dictFamilles[IDfamille]["listeNomsTitulaires"][-1])
```

#### A08 — Droits : refuser proprement une restriction utilisateur mal formée (#261)

- Commit source : `d27b43fa` (2026-08-31)
- Fichiers : `noethys/Utils/UTILS_Utilisateurs.py`
- Preuve dans main : main:noethys/Utils/UTILS_Utilisateurs.py L125 `mode, listeID = code.split(":")` puis int() sans garde : ValueError si la restriction est vide ou mal formée.
- Test sur master : tests/test_branch_contracts_batch_16.py
- Remarque : Refus fermé (fail-closed).

```diff
-            mode, listeID = code.split(":")
+            try : mode, listeID = code.split(":", 1)
+            except ValueError : return False
```

#### A09 — Tarification : ne pas supprimer les filtres en base en mode track

- Commit source : `25ad1e95` (2026-09-03)
- Fichiers : `noethys/Dlg/DLG_Saisie_tarification.py`
- Preuve dans main : main:noethys/Dlg/DLG_Saisie_tarification.py L434 `if self.toolbook.GetPage("conditions") != None :` exécute ReqDEL sur questionnaire_filtres même quand track_tarif est fourni (la base n'est fermée que si track_tarif == None, L440).
- Test sur master : tests/test_tarification_track_filter_delete.py

```diff
-        if self.toolbook.GetPage("conditions") != None :
+        if self.track_tarif == None and self.toolbook.GetPage("conditions") != None :
```

#### A10 — Portail : analyse stricte de la ventilation d'un paiement en ligne (#219)

- Commit source : `ee99d698` (2026-08-28)
- Fichiers : `noethys/Dlg/DLG_Saisie_portail_demande.py`
- Preuve dans main : main:noethys/Dlg/DLG_Saisie_portail_demande.py L1260-1264 : `if texte[0] == "F"` / `"P"` sans else (un préfixe inconnu réutilise le type précédent ou lève UnboundLocalError ; une virgule finale lève IndexError).
- Test sur master : tests/test_portail_payment_ventilation_contract.py
- Remarque : Flux financier : recette sur copie.

```diff
+def ParseVentilationPaiement(ventilation):
+    types = {"F": "facture", "P": "periode"}
+    ... raise ValueError(u"entrée de ventilation vide")
```

#### A11 — Portail : compte bancaire du paiement TIPI absent

- Commit source : `08baa60e` (2026-08-17)
- Fichiers : `noethys/Dlg/DLG_Saisie_portail_demande.py`
- Preuve dans main : main:noethys/Dlg/DLG_Saisie_portail_demande.py L1299 `IDcompte_bancaire = DB.ResultatReq()[0][0]` (IndexError si la facture n'a pas de régie).
- Test sur master : aucun — à écrire lors de la reprise

```diff
-            IDcompte_bancaire = DB.ResultatReq()[0][0]
+            resultat_compte = DB.ResultatReq()
+            if resultat_compte: IDcompte_bancaire = resultat_compte[0][0]
```

#### A12 — Export NoethysWeb : ne plus annoncer un échec comme une réussite

- Commit source : `6f7eb0a9` (2026-08-15)
- Fichiers : `noethys/Dlg/DLG_Export_noethysweb.py`, `noethys/Utils/UTILS_Export_noethysweb.py`
- Preuve dans main : main:noethys/Dlg/DLG_Export_noethysweb.py L257 ignore le résultat de Export_all ; UTILS_Export_noethysweb n'expose pas resultat/erreur_export.
- Test sur master : aucun — à écrire lors de la reprise

```diff
-        UTILS_Export_noethysweb.Export_all(...)
+        export = UTILS_Export_noethysweb.Export_all(...)
+        if not export.resultat: ... return False
```

#### A13 — Exports : données absentes (logo, règlement, modèle)

- Commit source : `b829f184` (2026-08-15)
- Fichiers : `noethys/Utils/UTILS_Export_noethysweb.py`, `noethys/Utils/UTILS_Export_documents.py`
- Preuve dans main : main:noethys/Utils/UTILS_Export_noethysweb.py L1271 `ResultatReq()[0][0]`, L1501 `ResultatReq()[0]` ; UTILS_Export_documents.py `nom, categorie, ... = listeDonnees[0]` sans garde.
- Test sur master : aucun — à écrire lors de la reprise

```diff
-                    logo = self.parent.DB.ResultatReq()[0][0]
+                    liste_logo = self.parent.DB.ResultatReq()
+                    logo = liste_logo[0][0] if liste_logo else None
```

#### A14 — Importation des vacances sans coordonnées d'organisateur

- Commit source : `1ec5c6dd` (2026-08-15)
- Fichiers : `noethys/Dlg/DLG_Importation_vacances.py`, `noethys/Dlg/DLG_Importation_individus.py`
- Preuve dans main : main:noethys/Dlg/DLG_Importation_vacances.py L380 `cp, ville = DB.ResultatReq()[0]` (IndexError).
- Test sur master : aucun — à écrire lors de la reprise

```diff
-        cp, ville = DB.ResultatReq()[0]
+        liste_organisateur = DB.ResultatReq()
+        if not liste_organisateur: ... message ; return
```

#### A15 — Badgeage : import Excel sans xlrd

- Commit source : `9a0b010f` (2026-08-15)
- Fichiers : `noethys/Dlg/DLG_Badgeage_importation.py`
- Preuve dans main : main:noethys/Dlg/DLG_Badgeage_importation.py L24-27 `try: import xlrd / except: pass` puis usage de xlrd (NameError si absent).
- Test sur master : aucun — à écrire lors de la reprise

```diff
-except :
-    pass
+except ImportError:
+    xlrd = None
+        if xlrd is None: ... message ; return False
```

#### A16 — Archivage : del dlgAttente non défini (#262)

- Commit source : `523a9a6d` (2026-08-31)
- Fichiers : `noethys/Utils/UTILS_Archivage.py`
- Preuve dans main : main:noethys/Utils/UTILS_Archivage.py L391 crée dlgAttente dans une branche conditionnelle, L475 `del dlgAttente` inconditionnel (UnboundLocalError).
- Test sur master : tests/test_branch_contracts_batch_17.py

```diff
+        dlgAttente = None
-            del dlgAttente
+            if dlgAttente != None:
+                del dlgAttente
```

#### A17 — Badgeage : condition questionnaire non individuelle

- Commit source : `cae2d2a7` (2026-09-01)
- Fichiers : `noethys/Dlg/DLG_Badgeage_interface.py`
- Preuve dans main : main:noethys/Dlg/DLG_Badgeage_interface.py L637 `if dictQuestions[IDquestion]["type"] == "individu" :` sans else ; listeReponses non défini ensuite (UnboundLocalError ou KeyError si la question a disparu).
- Test sur master : tests/test_branch_contracts_batch_19.py

```diff
+                if IDquestion not in dictQuestions or dictQuestions[IDquestion]["type"] != "individu" :
+                    DB.Close()
+                    return False
```

#### A18 — Badgeage : unité Événement sans occurrence (#231)

- Commit source : `e2accc5f` (2026-08-29)
- Fichiers : `noethys/Dlg/DLG_Badgeage_grille.py`
- Preuve dans main : main:noethys/Dlg/DLG_Badgeage_grille.py L208 et L297 `evenement = ... else None` puis poursuite du traitement avec None.
- Test sur master : tests/test_badgeage_evenement_contract.py
- Remarque : À confirmer : impact exact de None en aval.

```diff
+            if not case.liste_evenements:
+                return _(u"Aucun événement disponible à cette date pour cette unité.")
```

#### A19 — Composition : plus de cinq liens de filiation (#237)

- Commit source : `16621848` (2026-08-29)
- Fichiers : `noethys/Ctrl/CTRL_Composition.py`
- Preuve dans main : main:noethys/Ctrl/CTRL_Composition.py L842-846 : posCentrale défini seulement pour 1 à 5 liens (UnboundLocalError au-delà).
- Test sur master : tests/test_composition_filiation_layout.py
- Remarque : Cas rare.

```diff
+def GetPositionsLiensFiliation(posSeparation, nbreLiensFiliation): ...
-            if nbreLiensFiliation == 5 : posCentrale = [...]
+            posCentrale = GetPositionsLiensFiliation(self.posSeparationCol1, nbreLiensFiliation)
```

#### A20 — Passe anti-bugs #98 : reliquats non repris

- Commit source : `ce979bbd (partiel)` (2026-08-25)
- Fichiers : `noethys/Dlg/DLG_Updater.py`, `noethys/Ctrl/CTRL_Detail_aides.py`, `noethys/Dlg/DLG_Famille_factures.py`, `noethys/Dlg/DLG_Saisie_prelevement_lot.py`, `noethys/Dlg/DLG_Saisie_reglement.py`
- Preuve dans main : main:noethys/Dlg/DLG_Updater.py L591 `self.downloader.isAlive()` (AttributeError Python >= 3.9 ; les autres isAlive ont été corrigés par Vanilla #162) ; gardes IndexError absentes : CTRL_Detail_aides.py L120, DLG_Famille_factures.py L85, DLG_Saisie_prelevement_lot.py L720, DLG_Saisie_reglement.py L1174.
- Test sur master : tests/test_runtime_lookup_guards.py (master)
- Remarque : Le reste de #98 (except: -> except Exception:, ~200 lignes) est de la modernisation ; le correctif mémos (> 0) est déjà dans main (DLG_Synchronisation_donnees L456).

```diff
-            downloadEnCours = self.downloader.isAlive()
+            downloadEnCours = self.downloader.is_alive()
-        temp, email_factures = listeDonnees[0]
+        if listeDonnees: ... else: temp, email_factures = None, None
```

#### A21 — Extensions : chargement confiné au répertoire Extensions

- Commit source : `9f9a39c2` (2026-08-15)
- Fichiers : `noethys/Dlg/DLG_Extensions.py`
- Preuve dans main : main:noethys/Dlg/DLG_Extensions.py L110-111 `sys.path.append(GetRepExtensions())` + `importlib.import_module(nom_fichier)` (nom non validé, sys.path pollué).
- Test sur master : aucun — à écrire lors de la reprise
- Remarque : Sécurité, faible exposition.

```diff
+        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", nom_fichier): ...
+        spec = importlib.util.spec_from_file_location(nom_module, chemin_module)
```

#### A22 — Sécurité : ast.literal_eval pour les données sérialisées

- Commit source : `b5298150, e67c1a7b, 3b21e965, 94187a5b, 4046e240, 7df20c7d` (2026-08-15)
- Fichiers : `noethys/Utils/UTILS_Parametres.py`, `noethys/Dlg/DLG_Filtres_listes.py`, `noethys/Dlg/DLG_Saisie_commandes_colonne.py`, `noethys/Ctrl/CTRL_Commande_repas.py`, `noethys/Dlg/DLG_Saisie_commande.py`, `noethys/Dlg/DLG_Saisie_modele_commandes.py`, `noethys/Ctrl/CTRL_Profil.py`
- Preuve dans main : main : UTILS_Parametres.py L75-79 et L152-155, DLG_Filtres_listes.py L35, DLG_Saisie_commandes_colonne.py L347/427/486/691/708, CTRL_Commande_repas.py L430/452, DLG_Saisie_commande.py L399/419, DLG_Saisie_modele_commandes.py L124/285, CTRL_Profil.py L277 : eval() sur des valeurs lues en base.
- Test sur master : aucun — à écrire lors de la reprise
- Remarque : Vérifier sur une base réelle (copie) qu'aucune valeur stockée n'est une expression non littérale. Pour e67c1a7b, ne reprendre que la ligne literal_eval (le reste du commit est une refonte UI).

```diff
-                    if type_parametre == dict : valeur = eval(valeur)
+                    if type_parametre == dict : valeur = ast.literal_eval(valeur)
```

#### A23 — Portail : type d'hébergement inconnu

- Commit source : `1bd709d7 (partiel)` (2026-08-15)
- Fichiers : `noethys/Utils/UTILS_Portail_synchro.py`
- Preuve dans main : main:noethys/Utils/UTILS_Portail_synchro.py L2046 `raise()` (TypeError). La vérification du résultat d'upload est déjà dans main (L1577-1584).
- Test sur master : aucun — à écrire lors de la reprise
- Remarque : Mineur.

```diff
-            raise()
+            self.log.EcritLog(_(u"[ERREUR] Type d'hébergement inconnu : %s") % ...)
+            return False
```

#### A24 — Répertoire de données : créer toute l'arborescence

- Commit source : `fa4d3ca1 (branche refactor/ui-list-tools-repens)` (2026-08-23)
- Fichiers : `noethys/Utils/UTILS_Fichiers.py`
- Preuve dans main : main:noethys/Utils/UTILS_Fichiers.py L41-58 `os.mkdir(chemin)` sur appdirs.user_data_dir/site_data_dir (échec si les parents n'existent pas, ex. ~/.local/share sur une session Linux neuve).
- Test sur master : tests/test_noe_041_portable_paths.py (branche)
- Remarque : Linux/macOS surtout.

```diff
-            os.mkdir(chemin)
+            os.makedirs(chemin)
```

#### A25 — Configuration absente : nomFichier vide plutôt que None

- Commit source : `d1d8b70b + 85d42ba5 (branche refactor/ui-list-tools-repens)` (2026-08-23)
- Fichiers : `noethys/Utils/UTILS_Config.py`
- Preuve dans main : main:noethys/Utils/UTILS_Config.py L151 `valeur = defaut` (None remonte jusqu'à GestionDB quand Config.json n'existe pas encore).
- Test sur master : tests/test_config_empty_database_contract.py (branche)
- Remarque : À confirmer : vérifier les appelants de GetItemConfig("nomFichier") dans main.

```diff
+            if key == "nomFichier" and defaut is None:
+                valeur = ""
```

#### A26 — Menus : double-clic d'édition de la grille

- Commit source : `89fe8f70` (2026-08-20)
- Fichiers : `noethys/Ctrl/CTRL_Menus.py`
- Preuve dans main : main:noethys/Ctrl/CTRL_Menus.py L236 `self.GetGridWindow().Bind(wx.EVT_LEFT_DCLICK, ...)` + calcul manuel de la cellule.
- Test sur master : aucun — à écrire lors de la reprise
- Remarque : À confirmer en recette Windows (EN ATTENTE : pas de test GUI sur le poste).

```diff
+        self.Bind(gridlib.EVT_GRID_CELL_LEFT_DCLICK, self.OnLeftDoubleClick)
-        self.GetGridWindow().Bind(wx.EVT_LEFT_DCLICK, self.OnLeftDoubleClick)
```

#### A27 — Saisie d'adresse : ne pas remplacer le code postal par celui d'un homonyme

- Commit source : `e801bb3a + 79680bda` (2026-08-21)
- Fichiers : `noethys/Utils/UTILS_Villes.py`, `noethys/Ctrl/CTRL_Saisie_adresse.py`
- Preuve dans main : main:noethys/Ctrl/CTRL_Saisie_adresse.py L199 `nbreCodes = self.listeNomsVilles.count(villeSelect)`.
- Test sur master : tests/test_villes.py
- Remarque : Retirer l'import CTRL_ActionRepens présent dans le contexte master.

```diff
+        if UTILS_Villes.CoupleExiste(self.listeVilles, villeSelect, self.ctrlCp.GetValue()):
+            event.Skip()
+            return
```

#### A28 — Importation individus : format de colonne « codepostal » non converti (#225)

- Commit source : `80b0e127` (2026-08-28)
- Fichiers : `noethys/Dlg/DLG_Importation_individus.py`
- Preuve dans main : main:noethys/Dlg/DLG_Importation_individus.py L55-142 déclare `"format":"codepostal"` mais la sélection du convertisseur ne connaît que "cp" (converter non défini ou hérité de la colonne précédente).
- Test sur master : tests/test_importation_individus_contracts.py

```diff
+                "cp" : Formate_cp,
+                "codepostal" : Formate_cp,
+            if format not in dictConverters : raise ValueError(...)
```

### Correctifs de master déjà présents dans main (sous la même forme ou une autre)

`c2f92cc8`, `8f545e4a`, `f8cd03fe`, `0224957b`, `cb02320f`, `7bba5bea`, `e54217a1`, `766fd727`, `4c5e12a4`, `aaa914b4`, `cbeebbe7`, `08cdb16d`, `add4b66a`, `c2b2628b`, `8ff0a2cd`, `c49b2bfc`, `1727b24e`, `ad468258`, `0545fe8d`, `871bc89b`, `9875f630`, `0456d2c7`, `e577f641`, `c8cb8b2a`, `b6af1092`, `c0436214`, `ccdb53b7`, `28764006`, `1bf1208b`, `2a1921c9`, `0b3e18dc` : lignes de correction retrouvées dans main (lignée Vanilla notamment).

- `5a1c3cc6` — chargement isolé de models.py : main a139b766 (UTILS_Portail_synchro.py L434-462)
- `05a340b6` — journal Connecthys / SMS en texte : main : plus de .encode('UTF-8') dans CTRL_Portail_serveur.py ni DLG_Envoi_sms.py
- `3d3ab0b0` — Annuler dans le planning transports : main:DLG_Planning_transports.py L171 `if dlg.ShowModal() == wx.ID_OK`
- `b55df62c` — ID exact de la facture au règlement : main:CTRL_Numfacture.py L160 `ReglerFacture(IDfacture)`
- `04f6c64d` — mode GetHTML : main bf69d3ca (UTILS_Stats_modeles.py L316)
- `f90d411b (DLG_Saisie_typesVaccins)` — jours/mois/années initialisés : main:DLG_Saisie_typesVaccins.py L233 `jours = 0`
- `1bd709d7 (upload)` — échec d'upload portail : main:UTILS_Portail_synchro.py L1577-1584

### Durcissements défensifs non retenus en A (B optionnel)

Série #219-#262 / #297-#349 restante (ex. 60606bef, 555bdd59, 0bc85e4f, 5a3dc7c4, e88764e9, ba0d405e, 44d28c33, e64307cd, 8f125bf6, dd99598b, 9600bd22, b599f8d9, 05044dd7, b8413eb0, 1a361165, 0ee16eac, e60e6968, 7df35b88, 35dc5e38) : transforment des if successifs sur des domaines finis en if/elif/else avec ValueError, sans défaut atteignable démontré. Défaut syntaxique encore présent dans main, mais gain faible ; à reprendre seulement par lots avec leurs tests.

Modernisations sans effet fonctionnel (non retenues) : 46204e6a, 8a4b7491, 7cb45bdc (dates ISO), 9e694ca6 (littéraux bruts), 88a124ea, f7b07b52, f9bc5db2, 0f4690f9, 8e8b401b (UTF-8 explicite sur des fichiers écrits en ASCII ou par la même machine), edadffbb/6aac171e/b47be081 (outils de développement de FonctionsPerso), 0d67b51b, dbc5bf10/ac933626 (diagnostic d'ImportError), de0dc583 (wx.SystemSettings_GetFont : alias déprécié encore fourni par wxPython 4 — à confirmer), 59d09942 (géométries flottantes dans des contrôles tiers).

## 5. Fonctionnalités reportées

Ces apports restent consultables dans l'historique de `origin/master` et des branches citées. Ils ne doivent pas être fusionnés : toute reprise passe par une nouvelle qualification sur `main` (tests, recette sur base fictive, sauvegarde/restauration et rollback pour tout changement de schéma).

| Chantier | Classement | Pourquoi reporté | Point d'entrée |
|---|---|---|---|
| Noe-062 tiers/structures, relations, payeurs, conventions versionnées (E13) | C | crée ~12 tables ; modèle concurrent des conventions Noedoc/Word de main | noethys/Data/DATA_Structures.py, noethys/Utils/UTILS_Tiers.py, UTILS_Conventions_Structures*.py ; PR #212-#215, #298-#309 |
| Noe-062 programmations, séances, lieux, prévu/réalisé (E14) | C | tables interventions/lieux/programmations ; touche le pointage | UTILS_Programmations_*.py, UTILS_Interventions*.py, UTILS_Lieux.py ; PR #214, #249, #310, #312 |
| Noe-062 inter-domaines, inbox du réalisé, pointage session-attendance, coffre de secrets (E15) | C | réseau + pointage + table interventions_execution_inbox | UTILS_Interdomain_*.py, UTILS_Interventions_Actual_Inbox*.py ; PR #318, #325, #353, #355, #369 |
| Synchronisation PMSL (E16) | C | client réseau HMAC écrivant dans ouvertures | UTILS_PMSL_*.py, DLG_PMSL_Synchronisation.py |
| Migration contrôlée de base (E12) | C | écrit une base cible complète ; aucune migration implicite autorisée | UTILS_Migration_base.py, tests/test_migration_base.py |
| Portail Connecthys Noe-063 : blocs dynamiques, RSS/Atom, tarifs | C | réseau / synchro portail non qualifiés ; PR fermées | branches feature/noe-063-portail-consolide, feature/noe-063b-rss-atom-connecthys, feature/noe-063d-tarifs-ui |
| Refonte UI Repens, thème sombre, échelle, design system, icônes (E18, E19) | C | main a verrouillé l'apparence claire historique (#375) | UTILS_StyleRepens.py, CTRL_*Repens.py, UTILS_Interface.py, UTILS_DesignSystem.py ; PR #47, #50, #73-#79 |
| Planning Teamworks, messagerie dockable, registre de modules (E20) | C | source externe / non qualifiés | UTILS_Teamworks_Planning.py, CTRL_Planning_semaine.py, CTRL_Messagerie.py, UTILS_Modules.py |
| Registre d'extensions | C | aucun consommateur | branche feature/extensions-registry (PR #64) |
| Outils d'audit statique (E01) | C | baselines calées sur master | scripts/audit_*.py, scripts/qualify_branch_assignment_gaps.py |
| Écritures transactionnelles (E05) | B | intégrable sans schéma mais touche les flux financiers ; prérequis GestionDB ; tests à écrire | commits dd056f3e, af36b076 puis lots 15-17/08/2026 |
| Évaluateur d'expressions sûr (E04) | B | remplace eval() des formules métier ; sans test dédié | noethys/Utils/UTILS_Expressions.py (429bd8b2, 2c7e323c, ba37c395) |
| Commande de repas automatique (E17) | B | lecture seule, testée ; recette métier nécessaire | CTRL_Commande_repas_auto.py, DLG_Saisie_commande_auto.py ; PR #46 |
| Recherche tolérante (E21) | B | module pur testé ; intégration à réécrire hors Repens | noethys/Utils/UTILS_Recherche.py, tests/test_recherche_tolerante.py |
| Chargement différé des consommations (E23) | B | performance ; à requalifier sur main | noethys/Dlg/DLG_Impression_conso_differe.py (96ec3f7c) |
| Double-clic ObjectListView global sous Windows (E08) | B | comportement global, recette Windows requise | ef88a717 (UTILS_Adaptations.py) |

### Obsolètes (D)

- E02 CI/packaging/hooks runtime master : remplacés par les workflows et l'installateur de main.
- E11 Sauvegarde Noe-032 variante master : remplacée par UTILS_SQL_Integrite et le manifeste SQL V1 de main.
- E20 panneau Aujourd'hui master : remplacé par le panneau RC2 repris dans main (1de8c06b).
- Branches feature/noe-062-conventions, feature/noe-062-mises-a-disposition, feature/noe-062b-groupes-structures, feature/noe-062b-roles-contacts, noe-062-programmation-occurrences, noe-062c-lieux-execution-seances : versions antérieures ou alternatives.

## 6. Branches dérivées de la lignée master

Lignes « encore uniques » = lignes ajoutées par les commits propres à la branche (hors master, main, wx, qt), toujours présentes dans la pointe de la branche et absentes du même fichier dans master, main, wx et qt.

| Branche | Commits propres | Lignes encore uniques | PR | Ensemble | Classement |
|---|---|---|---|---|---|
| `feature/noe-062-conventions` | 3 | 330 | - | E13 (conventions) | D |
| `feature/noe-062-mises-a-disposition` | 12 | 2067 | #61 (fermée) | E13/E14 | D |
| `feature/noe-062b-groupes-structures` | 4 | 234 | #220 (fermée, supersédée par #298) | E13 | D |
| `feature/noe-062b-roles-contacts` | 4 | 199 | #221 (fermée, supersédée par #298) | E13 | D |
| `fix/noe-062b-hardening` | 4 | 103 | aucune | E14 | C |
| `noe-062-programmation-occurrences` | 4 | 716 | #303 (fermée) | E14 | D |
| `noe-062c-lieux-execution-seances` | 9 | 18 | #248 (fermée) ; v2 fusionnée #249 | E14 | D |
| `feature/noe-063-portail-consolide` | 6 | 2409 | #72 (fermée) | Portail Connecthys Noe-063 | C |
| `feature/noe-063b-rss-atom-connecthys` | 23 | 989 | #66 (fermée) | Portail Connecthys Noe-063 | C |
| `feature/noe-063d-tarifs-ui` | 38 | 1832 | #69 (fermée) ; #68 (063C, fermée) | Portail Connecthys Noe-063 | C |
| `feature/extensions-registry` | 4 | 101 | #64 (fermée) | Extensions | C |
| `refactor/ui-list-tools-repens` | 42 | 144 | aucune (PR #73-#78 voisines) | E18 + A24/A25 | C (+A) |
| `feature/session-attendance-consumer-2026-09-19` | 10 | 1030 | #369 (fermée) | E15 (pointage) | C |
| `noe-062-secure-secret-provider` | 7 | 354 | #355 (fermée) | E15 (réseau) | C |

- **`feature/noe-062-conventions`** (D) : Moteur ReportLab dédié aux conventions sportives (UTILS_Impression_convention.py), remplacé dans main par le moteur Noedoc/Word (e52a7bdc, a900c7f7). Seule idée non reprise : champs de questionnaire famille formatés dans la convention (8f7103d2) — main:UTILS_Convention_champs.py ne lit pas les questionnaires.
- **`feature/noe-062-mises-a-disposition`** (D) : Première version (20-21/08) du socle conventions/mises à disposition/programmation annuelle (UTILS_Mises_a_disposition*.py), réécrite ensuite sur master (UTILS_Conventions_Structures, UTILS_Programmations_Structures). Archiver.
- **`feature/noe-062b-groupes-structures`** (D) : Groupes de structures : contenu consolidé dans #298 sur master ; l'écart restant est surtout des tests variants.
- **`feature/noe-062b-roles-contacts`** (D) : Rôles de contacts : consolidé dans #298 ; écart restant = tests variants.
- **`fix/noe-062b-hardening`** (C) : Durcissements des séances sport écoles (écritures/dates, droits, interdiction de supprimer une école ayant des séances) jamais fusionnés dans master. À reprendre seulement si le chantier E14 est réactivé.
- **`noe-062-programmation-occurrences`** (D) : Implémentation alternative de la programmation annuelle, remplacée par #310/#312 sur master (elles-mêmes C).
- **`noe-062c-lieux-execution-seances`** (D) : Ancien socle 062C : seulement 18 lignes non reprises par la v2 (#249).
- **`feature/noe-063-portail-consolide`** (C) : Blocs portail dynamiques + publication des tarifs (UTILS_Portail_tarifs*.py, CTRL_Portail_tarifs.py, DLG_Saisie_portail_bloc_core.py). Jamais intégré à master ni main. Touche la synchro Connecthys : non qualifié.
- **`feature/noe-063b-rss-atom-connecthys`** (C) : Contenus externes RSS/Atom du portail (UTILS_Portail_contenus*.py, CTRL_Portail_contenu_externe.py) : récupération réseau de flux, non qualifiée.
- **`feature/noe-063d-tarifs-ui`** (C) : Interface et actualisation automatique des tarifs portail ; superset de 063B. Lecture SQL des barèmes sans écriture ; publication via synchro portail : C.
- **`feature/extensions-registry`** (C) : Registre d'extensions explicite (≈60 lignes + test) sans consommateur. Archiver ; à rapprocher de A21 si un modèle d'extensions est un jour décidé.
- **`refactor/ui-list-tools-repens`** (C (+A)) : Essentiellement Repens (listes, ObjectListView). Contient deux correctifs runtime utiles et absents de main : A24 (os.makedirs du répertoire Data) et A25 (nomFichier vide sans configuration).
- **`feature/session-attendance-consumer-2026-09-19`** (C) : Consommateur du pointage terrain session-attendance/1 (nouvelle inbox + schéma). Pointage + réseau + table : hors publication.
- **`noe-062-secure-secret-provider`** (C) : Coffre de secrets Windows pour le client mailbox inter-domaines (UTILS_Interdomain_Secrets.py) + workflow Windows. Dépend de E15.

## 7. Incertitudes et limites

- Comparaison ligne à ligne : une réécriture équivalente dans main (autre nom de variable, autre fichier) peut faire apparaître une ligne master comme unique ; les ensembles C/D n'ont pas été relus ligne par ligne.
- A18, A25, A26 : défaut présent dans main mais impact à confirmer (recette ou lecture des appelants) ; A26 demande une recette Windows sur poste isolé (EN ATTENTE).
- A22 : `ast.literal_eval` refuse toute valeur stockée qui ne serait pas un littéral Python ; contrôler une copie de base réelle avant reprise.
- de0dc583 : wxPython 4 fournit encore `wx.SystemSettings_GetFont` comme alias déprécié (à confirmer sur la version embarquée) ; non classé A.
- Les tests cités « master » n'ont pas été exécutés ; ils sont à adapter à l'architecture de main lors de la reprise.
