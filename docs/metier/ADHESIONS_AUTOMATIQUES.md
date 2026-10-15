# Adhésions automatiques — titulaire et règles

Règle métier transversale : PMSL-Arch, `docs/REGLES_ADHESION_ACTIVITES.md`.
Implémentation : `noethys/Utils/UTILS_Adhesions.py`.

> **Mesure d'urgence P1 — 15/10/2026 (issue #426).** La création automatique
> par sauvegarde de la grille est **suspendue** (`AUTO_CREATION_SUSPENDUE=True`),
> car la RC7 facturait des réservations futures. La sauvegarde des consommations,
> les cotisations manuelles et la facturation des prestations existantes restent
> disponibles. Cette suspension **ne corrige pas** les cotisations déjà produites
> par la RC7. Ne réactiver qu'après qualification de l'émission mensuelle,
> de la facturation anticipée, des annulations et de l'audit non destructif.
> Le code source mis à jour ne protège pas les postes RC7 tant qu'un exécutable
> corrigé n'a pas été installé.

## Titulaire de l'adhésion

| Situation | Titulaire | Nombre d'adhésions |
|---|---|---|
| Structure adhérente (association, collectivité, organisme, entreprise) | la structure | **une** pour la période, quelles que soient les sections, activités ou représentants qui participent |
| Famille de personnes physiques | chaque personne qui participe (enfant ou adulte) | **une par personne**, couvrant toutes ses activités ; jamais commune à la famille, jamais multipliée par activité |

## Correspondance avec les structures existantes de Noethys

Aucun modèle parallèle n'est créé :

- une **structure adhérente** est une famille dont un titulaire rattaché (`rattachements.titulaire = 1`) est un individu **personne morale** : civilité de la rubrique « AUTRE » de `Data/DATA_Civilites.py` (6 Collectivité, 7 Association, 8 Organisme, 9 Entreprise). C'est la même convention que les conventions d'encadrement (titulaire sans prénom = la structure) ;
- les **sections**, activités et représentants sont les individus rattachés à cette famille ;
- la famille d'une participation est celle de son **payeur** (compte payeur de la consommation ou de la prestation, sinon de l'inscription, sinon l'unique famille de rattachement) ;
- l'adhésion est une **cotisation individuelle** du type par défaut (`types_cotisations.type = 'individu'`, `defaut = 1`) portée par l'individu titulaire : la personne morale pour une structure, la personne qui participe sinon. Sa prestation est facturée au compte payeur de la famille de la participation.

## Contrôles appliqués au titulaire

- **couverture** : une adhésion du titulaire valide à la date de la participation (bornes incluses) suffit, quelle que soit la section ou l'activité ;
- **chevauchement** : aucune création si la période recouvrirait une adhésion existante ou future du titulaire ; situation « à vérifier » ;
- **au plus une adhésion à venir** par titulaire, saisies manuelles comprises ;
- **sauvegardes simultanées** : contrôle et création sont protégés ensemble par un verrou propre au titulaire (SQLite : `BEGIN IMMEDIATE` ; MySQL : `GET_LOCK`, tables InnoDB exigées) ;
- **titulaire ambigu** (plusieurs personnes morales titulaires dans la même famille) ou **payeur indéterminable** : aucune création, situation « à vérifier ».

Les situations « à vérifier » sont affichées après la sauvegarde lorsqu'un opérateur est présent, et tracées dans l'historique du titulaire pour la borne de badgeage et la synchronisation Nomadhys.

## Limites connues

- Une cotisation d'un **autre type** (par exemple une cotisation de type « famille » saisie à la main) n'est pas prise en compte comme adhésion existante.
- Un individu rattaché à plusieurs familles relève du titulaire de la famille de son payeur, participation par participation.
- Aucune adhésion existante n'est modifiée ni supprimée : la règle s'applique aux créations futures. Les adhésions déjà créées par section doivent être examinées manuellement (voir `docs/diagnostics/diagnostic_adhesions.sql`).

Tests : `tests/test_noethys_sl_adhesions*.py`, notamment `test_noethys_sl_adhesions_titulaire.py`.
