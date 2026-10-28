# Fonctionnalités reportées

Inventaire consultable des travaux **archivés mais non intégrés** dans `main`,
`wx` ou `qt`. **Archiver n'est pas intégrer** : une fonctionnalité listée ici
n'existe pas dans le produit tant qu'elle n'a pas été reprise, testée et
qualifiée sur les branches canoniques.

## Où sont les archives

- Un `git bundle` autonome par branche supprimée, vérifié (`git bundle verify`,
  restauration réelle dans un dépôt vide au SHA exact, `git fsck`), empreintes
  SHA-256 dans `SHA256SUMS.txt`.
- Copie principale : `C:\Users\Ordi\Documents\Sauvegardes-Noethys\branches-supprimees-20261012\`
  (poste de développement) ; seconde copie hors poste :
  `OneDrive\Sauvegardes-Noethys\branches-supprimees-20261012\`.
- Les commits des pull requests restent aussi conservés par GitHub
  (`refs/pull/<numéro>/head`).
- Restauration d'une branche :

```bash
git fetch <fichier.bundle> "+refs/remotes/origin/*:refs/heads/*"
git push origin <branche>
```

La liste complète des branches archivées, avec SHA et empreintes, est dans
[Reprise et état des branches](REPRISE_CODEX.md) (§§ 31 à 33).

## Règles de reprise

1. Repartir de `main` et comparer le contenu (pas l'historique) avant tout portage.
2. Aucune migration SQL implicite : migration explicite, testée sur copie avec
   sauvegarde, restauration et rollback.
3. Chantiers réseau, pointage et rattachements : hors publication tant qu'ils
   ne sont pas qualifiés de bout en bout.
4. Recette graphique uniquement sur runner isolé ou machine virtuelle.

## Pull requests reportées

| Sujet | PR | Issue de reprise | Archive (branche @ SHA) | Dépendances |
|---|---|---|---|---|
| Fonctions des individus dans les entités (table `rattachements_fonctions`, type École) | #384 (empilée sur #370) | #423 | `feature/vanilla-entites-fonctions` @ `4e2c615b` ; `feature/vanilla-conventions` @ `c2c3e87a` | migration SQL additive ; feuille de route #382, #383 |
| `SecretProvider` Windows du client mailbox inter-domaines | #355 | #424 | `noe-062-secure-secret-provider` @ `04f7886c` | client mailbox de la lignée `master` |

## Reprises qualifiées depuis les archives

| Sujet | Archive | Reprise canonique | Limites restantes |
|---|---|---|---|
| Consommateur `session-attendance/1` (ancienne #369) | `feature/session-attendance-consumer-2026-09-19` @ `74410a3e` | repris sans Noe-062 E14 : `main` `4a663fc`, `wx` `883bf00`, `qt` `ffa1657` ; E2E Portails/Noethys-SL run `40661602931` SUCCESS | non activé en production ; corrélation de séance à alimenter ; lecteur participants à raccorder ; copie MySQL réelle à qualifier ; #355 secrets/client réseau toujours reporté |

| Coffre Windows + client mailbox #355 | `04f7886c` archive | repris sur moteur courant : `main cd15143e`, `wx 82cc9a6`, `qt 05ddada`; Windows Credential Manager run `40663326876` SUCCESS | aucun polling/URL/secret réel activé ; installation credentials et activation exploitation restent à décider |

## Packaging

| Sujet | Archive | Motif du report |
|---|---|---|
| ZIP livré avec un dossier `Portable` déjà présent (mode portable par défaut) | `noe-041-portable-mode` @ `3cf6cbfe` | décision du 12/10/2026 : conserver ZIP et Setup sans imposer un nouveau packaging ; activation manuelle documentée dans [Mode portable](../exploitation/MODE_PORTABLE.md) |
| Smoke test non interactif de l'exécutable gelé (Noe-040 : `eeaa998c`, `ca40c11c`, `6f1de516`, `2116562b`) | `noe-041-portable-mode` @ `3cf6cbfe` | outillage de qualification Windows à reprendre avec le prochain chantier de build (le workflow de `main` vérifie déjà le démarrage de l'exécutable) |

## Lignée `master` (inventaire du 12/10/2026)

Ces apports restent consultables dans l'historique de `origin/master` et des branches citées. Ils ne doivent pas être fusionnés : toute reprise passe par une nouvelle qualification sur `main` (tests, recette sur base fictive, sauvegarde/restauration et rollback pour tout changement de schéma).

| Chantier | Classement | Pourquoi reporté | Point d'entrée |
|---|---|---|---|
| Noe-062 tiers/structures, relations, payeurs, conventions versionnées (E13) | C | crée ~12 tables ; modèle concurrent des conventions Noedoc/Word de main | noethys/Data/DATA_Structures.py, noethys/Utils/UTILS_Tiers.py, UTILS_Conventions_Structures*.py ; PR #212-#215, #298-#309 |
| Noe-062 programmations, séances, lieux, prévu/réalisé (E14) | C | tables interventions/lieux/programmations ; touche le pointage | UTILS_Programmations_*.py, UTILS_Interventions*.py, UTILS_Lieux.py ; PR #214, #249, #310, #312 |
| Noe-062 inter-domaines, inbox du réalisé et coffre de secrets (E15 historique) | C | le pointage #369 a été réécrit et qualifié hors Noe-062 ; restent le réalisé historique, le client réseau et #355 | UTILS_Interdomain_*.py, UTILS_Interventions_Actual_Inbox*.py ; PR #318, #325, #353, #355 ; voir reprise #424 §34 |
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

### Obsolètes (D), abandon justifié

- E02 CI/packaging/hooks runtime master : remplacés par les workflows et l'installateur de main.
- E11 Sauvegarde Noe-032 variante master : remplacée par UTILS_SQL_Integrite et le manifeste SQL V1 de main.
- E20 panneau Aujourd'hui master : remplacé par le panneau RC2 repris dans main (1de8c06b).
- Branches feature/noe-062-conventions, feature/noe-062-mises-a-disposition, feature/noe-062b-groupes-structures, feature/noe-062b-roles-contacts, noe-062-programmation-occurrences, noe-062c-lieux-execution-seances : versions antérieures ou alternatives.

Corrections encore EN ATTENTE : A20 (gardes IndexError partielles), A22
(`ast.literal_eval`), A26 (double-clic de grille). Détail, branches dérivées
et preuves : [Inventaire de la lignée master](INVENTAIRE_MASTER.md).

## Prototypes

| Sujet | Archive | État |
|---|---|---|
| Prototype d'interface Qt (`noethys_qt/`, `tests_qt/`) | `poc/qt-theme-isole` @ `cba459cd` | réintégré isolé et non activé dans la branche `qt` (`docs/qt/README.md`), garde de données ; recette utilisateur et activation reportées |
