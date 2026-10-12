# Noe-042 — Sas Release Candidate

La fabrication d'une RC est désormais prévue comme une action **manuelle et bloquée par défaut**.

Workflow : `.github/workflows/release-candidate.yml`

## Conditions imposées

Le workflow refuse de continuer si :

- il n'est pas déclenché depuis `master` ;
- la recette Noe-030 sur une copie réelle n'est pas explicitement confirmée `YES` ;
- le tag ne suit pas une forme RC (`v1.3.5.0-rc.1`, préfixe `v` facultatif) ;
- le tag existe déjà.

Il rejoue ensuite les tests métier et audits cœur avant de fabriquer quoi que ce soit.

## Fabrication

Sur Windows, le workflow :

1. installe les dépendances de build ;
2. compile les sources ;
3. vérifie les piles optionnelles, PDF Unicode et ressources ;
4. construit le bundle PyInstaller ;
5. vérifie le layout historique des ressources ;
6. active le mode `Portable/` ;
7. écrit un `BUILD-INFO.txt` avec tag, commit et preuve de passage par le sas ;
8. crée l'archive RC ;
9. extrait puis exécute le vrai `Noethys.exe` sans environnement Python externe ;
10. vérifie qu'il n'écrit pas dans le profil utilisateur pendant le smoke test.

## Publication prudente

Si tout est vert, GitHub crée une **release en brouillon** avec l'archive attachée. Rien n'est publié automatiquement auprès des utilisateurs : le brouillon doit encore être relu puis publié volontairement.

Cette séparation évite qu'une simple réussite CI transforme accidentellement `master` en version distribuée.

## Dernier verrou avant déclenchement

Avant de sélectionner `YES`, conserver le résultat de :

```bash
python scripts/rc_db_preflight.py ...
```

et réaliser le parcours métier décrit dans `NOE-030-RECETTE-BASE-EXISTANTE.md` sur une copie jetable.
