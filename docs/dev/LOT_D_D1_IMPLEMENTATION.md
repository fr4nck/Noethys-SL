# Lot D1 — Annuaire des partenaires : livraison moteur et recette isolée

**Date :** 03/11/2026. **Périmètre :** moteur Python sans wx/Qt et DDL séparés. **Aucune migration de production.**

## Fichiers livrés

- `noethys/Utils/UTILS_Partenaires_D1.py` : API DB-API pour créer, modifier, lister et archiver des structures et contacts ; relier/révoquer explicitement un identifiant Noethys historique ; journaliser les écritures.
- `noethys/Data/Migrations/partenaires_d1_sqlite.sql` : quatre nouvelles tables SQLite (pas d'altération des tables historiques).
- `noethys/Data/Migrations/partenaires_d1_mysql57.sql` : DDL InnoDB compatible visé MySQL 5.7, **non testé sur serveur MySQL dans ce lot**.
- `tests/test_partenaires_d1.py` : tests SQLite `:memory:` sans profil ni connexion réseau.

## Contrats métier D1

1. Catégories : association, école, collectivité, établissement, autre. Une fiche possède sa clé `IDpartenaire` propre. **Aucune fusion ou unicité sur le nom**, aucune réutilisation de `compta_tiers` comme annuaire.
2. Contacts : plusieurs par partenaire, un seul contact principal actif possible ; archivage non destructif. Pas de suppression de fiche.
3. Liens vers l'existant : `famille`, `compte_payeur`, `tiers_comptable`, **uniquement à la demande explicite**. Vérification de l'existence de l'identifiant par callback injecté (sans lecture automatique de la production) ; au plus un lien actif par partenaire/type et par identifiant externe/type. Révocation historisée, puis nouveau rapprochement possible. Aucun nom utilisé pour rapprocher des fiches.
4. Sécurité : tous les accès passent par `autoriser(acteur, action)` fourni par l'intégration ; en l'absence de ce contrôle, **lecture et écriture refusées**. Chaque écriture ajoute un événement avec acteur et liste de champs modifiés ; les valeurs de contact ne sont pas recopiées dans le journal.
5. Une opération de mutation produit un `commit` ou un `rollback` de sa connexion. L'appelant doit fournir une **connexion DB-API dédiée**, hors transaction étrangère, et sélectionner explicitement SQLite ou MySQL. Aucune création de base ni migration implicite ; l'interface de saisie reste à intégrer.
6. Pour SQLite, l'appelant doit activer `PRAGMA foreign_keys=ON` ; les tests l'activent. MySQL utilise des contraintes InnoDB. Les deux dialectes utilisent des requêtes paramétrées ; identifiants SQL fixes et validés.

## Vérification locale réalisée

Depuis une copie isolée des quatre fichiers (Python 3.13, SQLite mémoire) :

```sh
python -m unittest discover -s tests -p test_partenaires_d1.py -v
python -m compileall -q noethys/Utils/UTILS_Partenaires_D1.py tests/test_partenaires_d1.py
```

Les tests contrôlent notamment les structures homonymes, les catégories, les contacts multiples, le contact principal unique, les droits d'accès, les liens actifs uniques, la révocation et l'absence d'effet sur `familles` et `compta_tiers` fictives. Les conventions, consommations, prestations et factures historiques ne sont pas touchées.

## Migration et déploiement — **BLOQUÉS**

Les deux scripts de création sont **non idempotents par conception** (échec si les tables existent). Il n'existe pas de migration ascendante automatique ni d'outil de restauration livré dans D1. Ne jamais les exécuter sur une base réelle.

Avant toute installation : sauvegarde/restauration vérifiées sur copie, inventaire des tables du site cible, contrôle des permissions et du profil, qualification de MySQL 5.7 local jetable et tests Windows de l'application. **MySQL DDL est auto-commit** : une restauration de copie est nécessaire pour récupérer un éventuel échec partiel. Aucun `DROP` destructif fourni.

## Statut et prochaine étape

- **D1 moteur métier et tests SQLite : PUBLIÉS sur `main`** (18/18 tests locaux PASS, 0 FAIL, Python 3.13). Les cinq fichiers ont été comparés à leurs empreintes Git, identiques à celles des sources testées. Commits de création : `677687e`, `fcc29ec`, `e9a3b6d`, `b917eea`, `558a868`.
- **D1 MySQL 5.7, UI wx, UI Qt et intégration permissions applicatives : NON QUALIFIÉS.**
- **D2-D5 : non développés dans cette livraison.**

**Provenance/limites :** prévol initial main `c13d150`, wx `103a8ee`, qt `6b11611` ; la rédaction a été effectuée uniquement sur `main`, cinq commits non forcés, sans merge. Aucune CI/qualification Windows ni recette MySQL 5.7 revendiquée. Aucun accès ni changement à la base de production ; archive locale de livraison hors Git, aucun secret ni donnée de la sauvegarde dans les commits.

Conserver les branches existantes `main`, `wx`, `qt` sans merge global. Le code métier D1 va sur `main` ; propagation contrôlée vers les interfaces après leur qualification, selon `AGENTS.md`.
