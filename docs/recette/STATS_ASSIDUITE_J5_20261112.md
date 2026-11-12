# Q445 / J5 — Précontrôle anonyme du périmètre multisite

Date : 12 novembre 2026 — branche `stats/assiduite-candidat`.
Statut : **CANDIDAT NON HOMOLOGUÉ**, aucun changement de base ni facturation.

## Objectif
Préparer la qualification manuelle des véritables activités, unités d'accueil et groupes
par site. **Le code ne déduit jamais le site à partir du nom de l'activité**, ne transforme
pas le champ `unites.repas` en preuve qu'une unité est « repas uniquement », et ne
suppose pas que l'absence de données sur une période garantit la complétude historique.

## Fonctionnement technique
- Nouveau module `UTILS_Stats_assiduite_perimetre.py`.
- Quatre `SELECT` uniquement : catalogue des activités ; catalogue des unités ;
  catalogue des groupes ; volumes de consommations regroupés par activité, unité,
  groupe et état. Aucun `IDindividu` ni `IDfamille` n'est lu ou exporté.
- Dates ISO et identifiants d'activités explicitement validés ; seules les règles
  `Configuration` / `RegleSite` proposées par un opérateur déterminent les sites.
- Les lignes observées hors unités d'accueil approuvées restent affichées sous
  `UNITE_EXCLUE_A_VERIFIER`, **sans** les forcer dans un site.
- Les règles invalides, les groupes ou unités inconnus, les statuts inattendus et les
  activités absentes sont signalés. Les incohérences bloquent la candidature.
- `candidat_a_approbation_humaine` signifie seulement qu'aucune anomalie
  structurelle bloquante n'a été constatée pour la période observée.
- `homologue = false` dans **tous** les résultats : il faut encore la confirmation
  explicite de la direction et une recette sur copie autorisée.
- Aucune activation dans l'interface de production ni configuration PMSL injectée.

## Recette isolée
`tests/test_stats_assiduite_perimetre.py` : 13 cas SQLite fictifs couvrant
lecture seule, ambigüités, unités non approuvées, groupes manquants, contrôles
catalogue, activité absente, périodes vides et absence de faux GO.
`tests/test_stats_assiduite_mysql57.py` : deux tests de comparaison
SQLite/MySQL 5.7 jetable du nouveau précontrôle (mêmes tables fictives).

Le résultat exact des CI sera ajouté après exécution, sur le SHA testé.

## Convergence QF / Assiduité
Les PR #444 (QF) et #445 (assiduité) modifient toutes deux
`noethys/Dlg/DLG_Stats.py`. Leurs CI vertes distinctes **ne démontrent
pas** une intégration combinée. Exiger une fusion résolue et une qualification
sur un SHA commun, sans écraser les ajouts réciproques et sans fusion automatique.

## Annulations #446
Les anciennes suppressions de `consommations` ne prouvent pas une
annulation de réservation. Cette étape ne crée **aucun journal**, aucune
migration, aucun compteur inventé. Le journal #446 devra distinguer acte
explicite d'annulation et correction administrative, conserver une provenance
vérifiable et gérer transaction/rollback/idempotence. En attendant :
`annulations.nombre = null` dans les statistiques historiques.

## Ce qui reste
Validation d'un mapping de sites **réel et autorisé**, voie d'affichage du
précontrôle dans l'interface, recette Windows installé, arbitrage et validation
du journal #446 puis consolidation avec QF #444 dans la RC.
