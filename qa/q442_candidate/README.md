# Q442 — Candidat statistique QF (J3 + J4, NON ACTIVE)

Date : 2026-11-10. Base de lecture d'origine : branche `wx`, commit `e86fabedece82f6cc1cade70074207291f8d9dfb`.

Ce répertoire permet de **rejouer** le banc autonome sur **SQLite fictif en mémoire**. Les trois modules candidats `noethys/Utils/UTILS_Stats_qf_lecture.py`, `UTILS_Stats_qf_sites.py` et `UTILS_Stats_qf_objets.py` ne sont **pas enregistrés dans `DLG_Stats.py`** : aucun écran ni comportement métier de production ne change avec ce candidat.

## Rejouer (dans un environnement jetable)

Python 3.10+ et paquets `matplotlib`, `Pillow`, `numpy` :

```sh
python qa/q442_candidate/run_j4.py --output /tmp/q442-j4-preuves-nouvelles
```

Choisir un nouveau chemin vide. Le lanceur refuse d'écraser des preuves. Sous Windows, choisir un dossier de travail explicitement dédié, jamais la racine `C:\`.

Le banc contient 75 tests J4 + 60 tests J3 et leurs fixtures SQLite strictement fictives. Il dispose d'adaptateurs de test autonomes, notamment un substitut `UTILS_Stats_modeles` non graphique ; **cela ne constitue pas une recette de l'application installée**. Il est intentionnellement placé hors de `tests/` pour ne pas interférer avec les tests globaux existants ni forcer l'import de wx au cours de cette qualification.

Les résultats de qualification du 10 novembre 2026 sont 135/135 PASS, 0 échec, 0 erreur, 0 skip ; 9 familles et 11 enfants dans la fixture multisite. Les catégories tarifaires historiques attestées sont **0**. Les graphiques et exports issus du banc sont **indicatifs**, sans données nominatives.

## STOP-GATE

- Site réel ↔ activité/groupe/unité : mapping **non homologué** ; ne jamais réutiliser les ID fictifs.
- Historique : `prestations.IDtarif` n'atteste pas `tarifs_lignes.IDligne` appliquée ; aucun recalcul du passé n'est admis comme preuve d'une catégorie historique.
- Envoi ou calcul de facture : aucun appel autorisé dans le lecteur ; SELECT uniquement.
- MySQL 5.7 réel et Windows installée : non qualifiés pour ce candidat.
- Les exports .xlsx et l'interface wx ne sont pas livrés/activés.
- Le STOP-GATE de l'[issue #442](https://github.com/fr4nck/Noethys-SL/issues/442) demeure jusqu'à approbation métier et recette isolée de la RC.

Documents : [`STATS_Q442_J3_20261110.md`](../../docs/recette/STATS_Q442_J3_20261110.md) et [`STATS_Q442_J4_20261110.md`](../../docs/recette/STATS_Q442_J4_20261110.md).
