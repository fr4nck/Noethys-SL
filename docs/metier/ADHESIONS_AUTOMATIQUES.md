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

## Contrôle non coercitif avant facturation (10 novembre 2026)

À l'étape 1 de la génération, les cotisations proposées ne sont **jamais une obligation
automatique de paiement** : l'opérateur visualise les bénéficiaires et choisit
individuellement les cotisations à créer. Les titulaires décochés ne produisent
**aucune** écriture (ni cotisation, ni prestation), ni changement de statut.
L'exclusion n'est valable que pour le traitement courant : elle n'est pas une
exonération permanente, n'est pas déduite d'un métier, d'une parenté ou d'un
statut de salarié, et aucune justification personnelle n'est demandée.

Une adhésion gratuite durable reste possible **par décision humaine** avec
le formulaire natif « Saisie d'une cotisation », en décochant « Facturer ».
Une telle cotisation manuelle valide couvre le titulaire pour sa période
sans créer de prestation financière ; ce parcours n'en fabrique pas une
automatiquement.

En présence d'un choix partiel, seules les cotisations cochées sont revalidées
sous les contrôles métier habituels (service Executer, argument
selection_titulaires), puis les propositions résiduelles sont mémorisées pour
la durée de l'assistant. Avant la validation **effective** des factures
sélectionnées, un nouveau contrôle compare les cotisations des comptes payeurs
concernés à l'aperçu. En cas de nouvelle proposition ou d'anomalie, il faut
reprendre la préparation pour actualiser l'aperçu ; aucun paiement n'est forcé.

Si le serveur est indisponible, un contournement est toujours possible,
mais **sur deux décisions explicites** : continuer jusqu'à l'aperçu, puis
accepter l'émission avec les seules prestations déjà enregistrées.
L'opérateur peut refuser sans écriture. Une erreur SQL n'est jamais
assimilée à une absence de cotisation due. La relance de connexion MySQL 2005
est unique, en lecture seule, vers le **même** serveur ; une résolution DNS
durablement défaillante reste à corriger sur le poste ou le réseau.

Protection de la vie privée : les noms de titulaires servent uniquement
à l'interface locale. Aucun motif d'exonération, lien familial, statut de
salarié ou liste nominative d'exceptions n'est enregistré par cette
fonctionnalité ni publié dans le dépôt. Les exceptions peuvent reparaître
au traitement suivant, sauf cotisation manuelle de couverture valide.

**Limites :** le contrôle porte sur les activités et le type de cotisation
configurés, pas sur une obligation juridique générale. Les nouvelles écritures
tierces entre le dernier contrôle et l'insertion de facture restent un cas
concurrent à qualifier sur MySQL en recette. Le correctif source n'est pas
une publication de RC ; exiger tests automatiques et recette Windows sur base
fictive avant tout installateur.

Tests de référence : tests/test_noethys_sl_adhesions_dns_2005.py,
tests/test_noethys_sl_facturation_selection_humaine.py,
tests/test_noethys_sl_facturation_cotisations_erreur.py.
