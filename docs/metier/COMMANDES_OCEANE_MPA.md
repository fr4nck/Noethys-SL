# Commandes Océane : repas adultes en portions P (2026-11-03)

## Décision PMSL et fichiers source

- Menu fournisseur : `Menus CLSH 5 él période 2.xlsx`.
- Bordereau fourni : `Tableau de commandes CLSH VAC NB repas vierge(1).xlsx`.
- Règle donnée par PMSL : **les repas du personnel sont comptabilisés,
  mais facturés/commandés comme des portions « 6 ans et plus » (P)**.
  Il n'y a donc **aucune quantité en colonne adulte A du bordereau**.
- Le bordereau contient les onglets LGB (7011), MOUT (7012), Bais (7077).
  Les colonnes du mercredi sont I=M, J=P, K=A pour les deux blocs ;
  les lignes Entrée, Plat, Garniture, Laitage, Dessert sont 8:12 puis 33:37.
  Les lignes « Dont sans porc », « Dont sans viande (poisson autorisé) »,
  « Dont végétarien », « Dont sans allergène » sont 17:20 puis 42:45.

## Contrat de calcul

La fonction `TotauxRepas` de `UTILS_Repas_totaux` possédait déjà la règle
`repas_6_et_plus = enfants_6_et_plus + animateurs_repas + direction_repas +
autres_adultes_repas`. Le personnel est maintenu séparément dans le total
interne `total_adultes`; rien n'est déduit automatiquement d'un besoin
théorique d'encadrement.

Nouveau module pur `UTILS_Repas_oceane` :

- `RepartitionFournisseur(totaux)` produit M, P, A=0 et le nombre d'adultes
  **déjà inclus** dans P. Vérifie un éventuel récapitulatif périmé.
- `PreparerMercredi(ligne, bloc, composantes, variantes, ...)` prépare
  les **coordonnées exactes** des cases Océane et vérifie le site, le jour,
  le bloc de semaine, la plage de midi, les quantités non négatives,
  les sous-quantités et l'absence de colonne A.
- Les cinq composantes sont par défaut proposées à l'effectif M/P ; des
  quantités spécifiques par composante peuvent être fournies explicitement.
  Les **grammages restent à établir**, ils ne figurent pas dans ce bordereau.
- Les catégories alimentaires sont des **« dont » non additives**.
  Sans porc, sans viande et végétarien ne sont pas synonymes et une
  catégorie standard n'implique pas nécessairement un plat avec porc.
  Leur répartition M/P doit être explicite : elle n'est **pas inventée**
  à partir d'un seul total global ; les cases restent à compléter.
- Les repas sans allergène nécessitent la confirmation préalable de
  l'acceptation par la diététicienne, conformément au document transmis.

## Périmètre réel de ce lot

**Le nouveau module prépare des coordonnées et des valeurs** pour un
futur exporteur du classeur source ; il n'est pas encore raccordé à l'UI
des commandes et n'écrit pas d'Excel. Aucune édition, réservation,
commande ni email fournisseur n'est déclenché ici. La création de
l'export au format exact Océane, l'importation des menus, le suivi
des restes et l'optimisation des grammages sont **des travaux distincts
à qualifier ultérieurement**.

Qualification fictive : `tests/test_noethys_sl_repas_oceane.py` (25 enfants P
et quatre animateurs -> **29 P, 0 A**, trois sites, deux blocs de
mercredi, cinq composantes, variantes et allergènes).
Aucune modification du fichier fournisseur ni des données PMSL.
