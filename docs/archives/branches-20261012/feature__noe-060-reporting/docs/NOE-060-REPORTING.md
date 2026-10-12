# Noe-060 — Rapports métier fiables et prédéfinis

## Problème métier

Noethys contient déjà les données et des écrans statistiques puissants, mais certains bilans récurrents restent dépendants d'une succession de choix manuels : période, activité, unités, états de réservation, commune, export, etc. Cette procédure est lente et peut produire des résultats divergents selon la casse d'un libellé, une sélection oubliée ou une adresse modifiée en cours d'année.

Le chantier Noe-060 ne vise donc pas à ajouter un énième écran statistique configurable. Il vise à transformer les besoins récurrents en **rapports métier prédéfinis** dont les règles sont explicites, centralisées et testables.

## Principe d'architecture

> Une donnée source → une règle de calcul canonique → plusieurs sorties.

Un indicateur ne doit être calculé qu'à un seul endroit. L'écran, l'export tableur et l'édition imprimable réutilisent le même résultat.

## Première cible : Mairies partenaires ALSH

Le premier rapport doit permettre d'obtenir sans paramétrage technique, pour une année scolaire ou une période libre :

- nombre d'enfants distincts par commune ;
- réservations connues ;
- fréquentation réalisée ;
- ventilation par site et/ou tranche d'âge lorsque nécessaire ;
- projection de fin de période, explicitement distincte du réalisé ;
- base de calcul du financement communal ;
- export à partir du même jeu de résultats.

### Choix métier visibles

L'utilisateur ne devrait avoir à choisir que ce qui relève réellement d'une décision de gestion :

- année scolaire / année civile / dates libres ;
- mercredis / vacances / tout ;
- une commune / toutes les communes ;
- éventuellement un site ou une tranche d'âge.

Les détails techniques de jointures, états de consommations ou colonnes statistiques ne doivent pas être exposés.

## Fiabilisation territoriale

### Normalisation des communes

Les comparaisons territoriales ne doivent pas dépendre d'un libellé saisi en texte brut. Avant toute comparaison, les valeurs doivent être normalisées au minimum sur :

- espaces de début/fin et espaces multiples ;
- casse ;
- accents lorsque la comparaison l'exige ;
- variantes historiques ou aliases connus.

À terme, une clé territoriale stable est préférable au texte libre.

### Changement d'adresse en cours de période

Le calcul du financement communal ne peut pas se contenter de l'adresse actuelle de l'individu si le besoin métier est de rattacher une présence à la commune de résidence valable à la date de cette présence.

Le moteur doit donc prévoir une résolution temporelle de la résidence :

- commune valable à la date de consommation ;
- historique conservé lorsque l'adresse change ;
- comportement explicite pour les anciennes bases ne disposant pas encore de cet historique.

Aucune migration implicite ne doit être introduite dans le sas de stabilisation de la première RC.

## Indicateurs canoniques initiaux

Les définitions suivantes doivent être écrites et testées avant d'être utilisées dans plusieurs sorties :

- `enfants_distincts` : individus distincts satisfaisant les critères de fréquentation du rapport ;
- `reservations_connues` : consommations réservées/validées selon la règle métier retenue ;
- `frequentation_realisee` : consommations effectivement réalisées selon les états reconnus par Noethys ;
- `projection` : estimation calculée à partir d'une méthode documentée, jamais additionnée silencieusement au réalisé ;
- `financement_communal` : quantité éligible × tarif/règle valable pour la période.

Les noms SQL ou les états techniques utilisés pour implémenter ces notions doivent rester internes au moteur.

## Réutilisation du code existant

Le chantier doit examiner et réutiliser en priorité les briques existantes au lieu de réimplémenter leurs règles :

- `Dlg/DLG_Stats.py` ;
- `Dlg/DLG_Stats_parametres.py` ;
- `Dlg/DLG_Synthese_conso.py` ;
- `Dlg/DLG_Liste_prestations_villes.py` ;
- `Dlg/DLG_Remplissage.py` ;
- `Dlg/DLG_Financement.py` ;
- les utilitaires géographiques et de périodes existants ;
- les exports déjà utilisés par Noethys.

## Découpage

### Noe-060A — Moteur d'indicateurs partagé

- inventorier les calculs déjà présents ;
- définir les indicateurs canoniques ;
- extraire les règles réutilisables dans une couche sans dépendance UI ;
- ajouter des tests de non-régression métier.

### Noe-060B — Rapport Mairies partenaires ALSH

- interface métier simple ;
- tableau multi-communes ;
- distinction réalisé / réservé / projection ;
- drill-down vers le détail si nécessaire pour contrôler un chiffre.

### Noe-060C — Résidence territoriale fiable

- normalisation des libellés existants ;
- détection des incohérences de communes ;
- conception d'un historique de résidence daté ;
- compatibilité des bases anciennes.

### Noe-060D — Sorties cohérentes

- CSV/XLSX ;
- édition imprimable/PDF ;
- mêmes valeurs que l'écran ;
- métadonnées de période et méthode de calcul conservées avec le rapport.

## Critère de réussite

Pour produire un bilan récurrent, l'utilisateur ne doit plus avoir à se souvenir d'une combinaison de cases à cocher.

Une anomalie doit devenir traçable :

1. donnée source incorrecte ;
2. règle métier incorrecte ;
3. bug de calcul couvert ensuite par un test.

Elle ne doit plus provenir d'une procédure manuelle fragile et non reproductible.
