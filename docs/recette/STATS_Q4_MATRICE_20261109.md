# STATS-RESTORE Q4 — matrice nominative des 33 objets (09/11/2026)

**Périmètre :** branche `wx`, qualifications sur données entièrement synthétiques. Cette matrice complète l'[inventaire Q3](STATS_Q3_MATRICE_20261109.md) sans réécrire ses preuves historiques.

## Preuves exécutées

- **Q4-A / Q4-B1 :** [CI isolée #42695747529](https://github.com/fr4nck/Noethys-SL/actions/runs/42695747529), SHA `113b72f2`, **9/9 tests PASS sous Ubuntu ET Windows** : vrai SQL SQLite exécuté par `MAJ()` des deux objets « Nombre de familles » et des deux tableaux « Caisses »/« Nombre de membres », comparé à des oracles indépendants.
- **Q4-B2 :** première campagne [#42696058544](https://github.com/fr4nck/Noethys-SL/actions/runs/42696058544) rouge à cause de la doublure qui écrasait `MODELES.LireCacheStats`, puis correction du **banc seul**. [CI corrigée #42696252158](https://github.com/fr4nck/Noethys-SL/actions/runs/42696252158), SHA `2a548a41`, **12/12 tests PASS Ubuntu ET Windows**. Elle exécute les vrais `MAJ()` des deux graphes « Caisses »/« Nombre de membres », avec SQLite synthétique, mais utilise un **axe Matplotlib fictif** : seules les données transmises au rendu sont contrôlées.
- **Q4-B3 :** [CI SQL isolée #42696950452](https://github.com/fr4nck/Noethys-SL/actions/runs/42696950452), SHA `4b756f2f`, **17/17 PASS Ubuntu + 17/17 PASS Windows**. Deux vrais `MAJ()` du groupe Individus/Nombre exécutés sur SQLite fictif avec contrôles `COUNT(DISTINCT IDindividu)` independants, doubles consommations, activites, statuts, annulations et periodes.
- **MemoryFS :** CI transversale native [#42662525508](https://github.com/fr4nck/Noethys-SL/actions/runs/42662525508), 7/7 PASS ; ne transforme pas un rendu individuel en PASS.
- **Matrice :** 33/33 classes présentes (AST). **Huit objets ont un niveau SQL/métier partiel documenté**, quatre avec texte/tableau produit, deux avec données de graphes capturées ; **zéro objet totalement validé** de bout en bout (MySQL, rendu, impression, Windows installé).
- Les noms des objets du tableau suivent **exactement** l'inventaire de `DLG_Stats.py` ; les niveaux ne sont pas transférés aux autres objets partageant un calcul.

## Etat par objet

| # | Page | Objet | Inventaire | SQL et métier | Cache | Rendu texte/tableau/graphique | Impression de l'objet | Windows installé |
|---:|---|---|---|---|---|---|---|---|
| 1 | individus / Nombre | `Texte_nombre_individus` | PASS AST | PARTIEL : SQL et MAJ SQLite PASS | NON TESTÉ | PARTIEL : texte/lignes, HTML non teste | NON TESTÉ | NON TESTÉ |
| 2 | individus / Nombre | `Tableau_nombre_individus` | PASS AST | PARTIEL : SQL et MAJ SQLite PASS | NON TESTÉ | PARTIEL : texte/lignes, HTML non teste | NON TESTÉ | NON TESTÉ |
| 3 | individus / Nombre | `Graphe_nombre_individus` | PASS AST | NON TESTÉ | NON TESTÉ | NON TESTÉ | NON TESTÉ | NON TESTÉ |
| 4 | individus / Ancienneté | `Tableau_nouveaux_individus` | PASS AST | NON TESTÉ | NON TESTÉ | NON TESTÉ | NON TESTÉ | NON TESTÉ |
| 5 | individus / Ancienneté | `Graphe_nouveaux_individus` | PASS AST | NON TESTÉ | NON TESTÉ | NON TESTÉ | NON TESTÉ | NON TESTÉ |
| 6 | individus / Ancienneté | `Graphe_arrivee_individus` | PASS AST | NON TESTÉ | NON TESTÉ | NON TESTÉ | NON TESTÉ | NON TESTÉ |
| 7 | individus / Ancienneté | `Tableau_anciens_individus` | PASS AST | NON TESTÉ | NON TESTÉ | NON TESTÉ | NON TESTÉ | NON TESTÉ |
| 8 | individus / Genre | `Tableau_repartition_genre` | PASS AST | NON TESTÉ | NON TESTÉ | NON TESTÉ | NON TESTÉ | NON TESTÉ |
| 9 | individus / Genre | `Graphe_repartition_genre` | PASS AST | NON TESTÉ | NON TESTÉ | NON TESTÉ | NON TESTÉ | NON TESTÉ |
| 10 | individus / Âge | `Tableau_repartition_ages` | PASS AST | PARTIEL : fixtures âges | NON TESTÉ | NON TESTÉ | NON TESTÉ | NON TESTÉ |
| 11 | individus / Âge | `Graphe_repartition_ages` | PASS AST | NON TESTÉ | NON TESTÉ | NON TESTÉ | NON TESTÉ | NON TESTÉ |
| 12 | individus / Âge | `Tableau_repartition_annees_naiss` | PASS AST | PARTIEL : fixtures âges | NON TESTÉ | NON TESTÉ | NON TESTÉ | NON TESTÉ |
| 13 | individus / Âge | `Graphe_repartition_annees_naiss` | PASS AST | NON TESTÉ | NON TESTÉ | NON TESTÉ | NON TESTÉ | NON TESTÉ |
| 14 | individus / Âge | `Tableau_repartition_tranches_ages` | PASS AST | PARTIEL : fixtures âges | NON TESTÉ | NON TESTÉ | NON TESTÉ | NON TESTÉ |
| 15 | individus / Coordonnées | `Tableau_repartition_villes` | PASS AST | NON TESTÉ | NON TESTÉ | NON TESTÉ | NON TESTÉ | NON TESTÉ |
| 16 | individus / Coordonnées | `Graphe_repartition_villes` | PASS AST | NON TESTÉ | NON TESTÉ | NON TESTÉ | NON TESTÉ | NON TESTÉ |
| 17 | individus / Scolarité | `Tableau_repartition_ecoles` | PASS AST | NON TESTÉ | NON TESTÉ | NON TESTÉ | NON TESTÉ | NON TESTÉ |
| 18 | individus / Scolarité | `Graphe_repartition_ecoles` | PASS AST | NON TESTÉ | NON TESTÉ | NON TESTÉ | NON TESTÉ | NON TESTÉ |
| 19 | individus / Scolarité | `Tableau_repartition_niveaux_scolaires` | PASS AST | NON TESTÉ | NON TESTÉ | NON TESTÉ | NON TESTÉ | NON TESTÉ |
| 20 | individus / Scolarité | `Graphe_repartition_niveaux_scolaires` | PASS AST | NON TESTÉ | NON TESTÉ | NON TESTÉ | NON TESTÉ | NON TESTÉ |
| 21 | individus / Profession | `Tableau_activites_professionnelles` | PASS AST | NON TESTÉ | NON TESTÉ | NON TESTÉ | NON TESTÉ | NON TESTÉ |
| 22 | individus / Profession | `Graphe_activites_professionnelles` | PASS AST | NON TESTÉ | NON TESTÉ | NON TESTÉ | NON TESTÉ | NON TESTÉ |
| 23 | familles / Nombre | `Texte_nombre_familles` | PASS AST | PARTIEL : SQL et MAJ SQLite PASS | NON TESTÉ | PARTIEL : texte/lignes, HTML non teste | NON TESTÉ | NON TESTÉ |
| 24 | familles / Nombre | `Tableau_nombre_familles` | PASS AST | PARTIEL : SQL et MAJ SQLite PASS | NON TESTÉ | PARTIEL : texte/lignes, HTML non teste | NON TESTÉ | NON TESTÉ |
| 25 | familles / Nombre | `Graphe_nombre_familles` | PASS AST | NON TESTÉ | NON TESTÉ | NON TESTÉ | NON TESTÉ | NON TESTÉ |
| 26 | familles / Caisse | `Tableau_repartition_caisses` | PASS AST | PARTIEL : SQL et MAJ SQLite PASS | PARTIEL : cache par connexion/filtre | PARTIEL : texte/lignes, HTML non teste | NON TESTÉ | NON TESTÉ |
| 27 | familles / Caisse | `Graphe_repartition_caisses` | PASS AST | PARTIEL : SQL + MAJ graphe PASS | PARTIEL : donnees partagees par cache teste | PARTIEL : donnees d'axe, PNG/HTML natifs NON TESTES | NON TESTÉ | NON TESTÉ |
| 28 | familles / Composition | `Tableau_nombre_membres` | PASS AST | PARTIEL : SQL et MAJ SQLite PASS | PARTIEL : cache par connexion/filtre | PARTIEL : texte/lignes, HTML non teste | NON TESTÉ | NON TESTÉ |
| 29 | familles / Composition | `Graphe_nombre_membres` | PASS AST | PARTIEL : SQL + MAJ graphe PASS | PARTIEL : donnees partagees par cache teste | PARTIEL : donnees d'axe, PNG/HTML natifs NON TESTES | NON TESTÉ | NON TESTÉ |
| 30 | familles / Quotient familial | `Tableau_qf_tarifs` | PASS AST | PARTIEL : moteur QF SQLite | NON TESTÉ | NON TESTÉ | NON TESTÉ | NON TESTÉ |
| 31 | familles / Quotient familial | `Graphe_qf_tarifs` | PASS AST | PARTIEL : moteur QF SQLite | NON TESTÉ | NON TESTÉ | NON TESTÉ | NON TESTÉ |
| 32 | familles / Quotient familial | `Tableau_qf_defaut` | PASS AST | PARTIEL : moteur QF SQLite | NON TESTÉ | NON TESTÉ | NON TESTÉ | NON TESTÉ |
| 33 | familles / Quotient familial | `Graphe_qf_defaut` | PASS AST | PARTIEL : moteur QF SQLite | NON TESTÉ | NON TESTÉ | NON TESTÉ | NON TESTÉ |

## Garde-fous d'interpretation

- **PASS ciblé** : exécution de méthodes source `MAJ()`, requêtes réelles SQLite en mémoire, données/étiquettes contrôlées indépendamment pour les huit objets listés. L'exécution de tests sur runner Windows n'est **pas** une recette de Noethys installé.
- **PARTIEL** dans la colonne « SQL et métier » : la portabilité MySQL 5.7 et certains cas limites restent à qualifier. Les doublons de consommations, comptes payeurs multiples, annulations, filtres, caisses inconnues, mutations de paramètres et isolations de connexions sont échantillonnés par le banc.
- **PARTIEL** pour les graphes : axe `pie()` capturé, pas de rendu Matplotlib, image MemoryFS, HTML ni aperçu réel. Le nombre de graphiques effectivement rendus et certifiés dans l'exe reste **0/15**.
- **QF :** aucun choix automatique de `IDtype_quotient` n'a été validé ; les quatre objets QF (#30–33) restent NON TESTÉS individuellement (fixtures de calcul partagé seulement). Ne pas assimiler `a_verifier` à zéro.
- **Aucun** parcours imprimé ou zoomé en application installée n'est qualifié. `#432` : réactivité/focus/maximisation encore soumis à recette sur poste.
- **STOP-GATE RC** maintenu. Aucune base PMSL, migration, installateur, publication, tag ou release touché dans ces épreuves.
