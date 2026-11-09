# STATS-RESTORE Q3 — matrice honnête des 33 éléments (09/11/2026)

**Dépôt :** `fr4nck/Noethys-SL`, branche `wx` ; inventaire des classes à partir de `noethys/Dlg/DLG_Stats.py` sur `ee15528108e4`.

**Convention :** le test `tests/test_stats_restore_inventory.py` vérifie la présence de **11 pages et 33 classes** et a obtenu PASS sur CI Ubuntu #42655909784 (candidat `3f3fccba`). Un PASS AST n'est ni une exécution SQL ni une recette Windows. Les tests QF sur SQLite synthétique et les tests d'âges sont partiels ; ils n'ont pas exécuté tous les objets graphiques en situation réelle.

| # | Page | Objet | Inventaire | SQL et métier | Cache de l'objet | Rendu graphique/HTML | Impression de l'objet | Runtime Windows installé |
|---:|---|---|---|---|---|---|---|---|
| 1 | individus / Nombre | `Texte_nombre_individus` | PASS AST | NON TESTÉ | NON TESTÉ | NON TESTÉ | NON TESTÉ | NON TESTÉ |
| 2 | individus / Nombre | `Tableau_nombre_individus` | PASS AST | NON TESTÉ | NON TESTÉ | NON TESTÉ | NON TESTÉ | NON TESTÉ |
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
| 23 | familles / Nombre | `Texte_nombre_familles` | PASS AST | NON TESTÉ | NON TESTÉ | NON TESTÉ | NON TESTÉ | NON TESTÉ |
| 24 | familles / Nombre | `Tableau_nombre_familles` | PASS AST | NON TESTÉ | NON TESTÉ | NON TESTÉ | NON TESTÉ | NON TESTÉ |
| 25 | familles / Nombre | `Graphe_nombre_familles` | PASS AST | NON TESTÉ | NON TESTÉ | NON TESTÉ | NON TESTÉ | NON TESTÉ |
| 26 | familles / Caisse | `Tableau_repartition_caisses` | PASS AST | NON TESTÉ | NON TESTÉ | NON TESTÉ | NON TESTÉ | NON TESTÉ |
| 27 | familles / Caisse | `Graphe_repartition_caisses` | PASS AST | NON TESTÉ | NON TESTÉ | NON TESTÉ | NON TESTÉ | NON TESTÉ |
| 28 | familles / Composition | `Tableau_nombre_membres` | PASS AST | NON TESTÉ | PARTIEL : GetDictMembres | NON TESTÉ | NON TESTÉ | NON TESTÉ |
| 29 | familles / Composition | `Graphe_nombre_membres` | PASS AST | NON TESTÉ | PARTIEL : GetDictMembres | NON TESTÉ | NON TESTÉ | NON TESTÉ |
| 30 | familles / Quotient familial | `Tableau_qf_tarifs` | PASS AST | PARTIEL : moteur QF SQLite | NON TESTÉ | NON TESTÉ | NON TESTÉ | NON TESTÉ |
| 31 | familles / Quotient familial | `Graphe_qf_tarifs` | PASS AST | PARTIEL : moteur QF SQLite | NON TESTÉ | NON TESTÉ | NON TESTÉ | NON TESTÉ |
| 32 | familles / Quotient familial | `Tableau_qf_defaut` | PASS AST | PARTIEL : moteur QF SQLite | NON TESTÉ | NON TESTÉ | NON TESTÉ | NON TESTÉ |
| 33 | familles / Quotient familial | `Graphe_qf_defaut` | PASS AST | PARTIEL : moteur QF SQLite | NON TESTÉ | NON TESTÉ | NON TESTÉ | NON TESTÉ |

## Contrôles transversaux et limites

- **Nombre d'objets :** 33, **pages :** 11, **rubriques :** 2. PREUVE : contrat AST, pas de recette UI intégrale.
- **QF :** sélection à la date de référence et catégories exclusives validées sur fixtures, **politique multi-types et période métier NON QUALIFIÉE**. Ne pas déduire le total réel de familles de la capture seule.
- **Caches :** deux tests rouges reproduisaient la contamination entre connexions ; verts après correction, dont un sur `GetDictMembres`. Les huit autres caches n'ont pas encore de tests indépendants de contamination.
- **Images :** vraie épreuve VFS Windows en cours de qualification. Un test enfant a signalé un arrêt `0xC000041D`, après appels manuels de `__del__()` ; le correctif du banc doit être requalifié avec destruction naturelle. Cela ne vaut pas certification générale de la fermeture wx.
- **Impression :** tests de sélection PASS avec doublures, mais rendu et aperçu Windows réels NON TESTÉS par élément.
- **Performances et UI :** gels d'un objet SQL/Matplotlib, service de distances réseau, stabilité plein écran et issue #432 ouverts ; aucune observation de l'application installée.
- **SQL :** MySQL synthétique NON TESTÉ ; SQLite exécuté réellement uniquement pour le moteur QF synthétique.
- **STOP-GATE** : aucune RC ni installateur publiés, et aucun GO tant que la qualification Windows et les parcours métier critiques ne sont pas établis.

Chaque élément marqué NON TESTÉ doit faire l'objet d'une preuve avant de devenir PASS. Ne pas transformer automatiquement un résultat transversal en PASS individuel.
