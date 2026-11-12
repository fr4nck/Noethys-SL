# Noethys-SL — Statistiques d'assiduite, jalon J4 (12 novembre 2026)

## Statut
**CANDIDAT, PR #445 en brouillon, STOP-GATE #443 maintenu.**
Aucune fusion dans `wx`, aucune installation ni mutation de base de production.
Les résultats de CI doivent être relus pour le commit final du présent jalon.

## Fonctionnalite
- Conservation des bilans d'annee civile existants.
- Ajout d'un regroupement par **annee scolaire francaise (1er septembre - 31 aout)** avec bornes exactes et annees a zero.
- Nouvelles vues `annees_scolaires` et `sites_annees_scolaires` : le regroupement temporel s'applique a la meme base d'observations validées.
- Quatrieme page statistique wx : tableau et graphique par annee scolaire, ajoutés sans supprimer les pages historiques.
- Nouveau classeur Excel : onglets `Annees scolaires` et `Sites scolaires`, avec graphiques. CSV et ZIP par site incluent aussi cette periode.
- Colonne **Couverture** : `Partielle`, `En cours` ou `Complete`. Une période demandee qui contient toutes les dates d'une annee future n'est plus presentee comme une annee deja terminee. Le critere couvre les bornes de selection, pas la preuve d'une base historique exhaustive.
- Le statut `annulations.nombre = null` n'est pas modifie : l'historique des suppressions n'est pas un journal d'annulations fiables.

## Recette synthetique
Tests ajoutes : `tests/test_stats_assiduite_scolaire.py`.
Verifications : 31 aout / 1er septembre, annees entieres et partielles, date d'observation explicite, periodes vides, parite sites, annulations non reconstructibles, 1 SELECT, contenu et integrite CSV / Excel / ZIP. 
Banc Windows reel : quatrieme page et impression HTML du tableau/graphique scolaires.
MySQL 5.7 jetable : ajout des structures annuelles scolaires au comparateur exact SQLite/MySQL.

## Blocages avant RC
- Correspondance reelle sites/groupes/unites d'accueil PMSL non homologuee.
- Pas de journal d'annulations anciennes. Ne pas inventer zero.
- Pas de recette du Setup RC installe sur un poste utilisateur.
- La nouvelle page de statistiques annuelles ne permet pas de conclure a la completude du stock historique.
- Eviter la fusion simultanee de #444 (QF) et #445 (assiduite) sans integration controlee de `DLG_Stats.py` et recette de non-regression. Une fusion directe risquerait d'ecraser le raccordement de l'autre PR.
