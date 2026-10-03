# Préparer l'actualisation AFAS de septembre

Dans **Consommations → État global**, sélectionner les activités d'un équipement CAF et charger/configurer le profil de calcul du réalisé (coefficients ou temps réels), les états de consommation, les jours scolaires/vacances et les éventuels plafonds. Cliquer sur **CAF / AFAS**.

1. Choisir l'année (2026 pour la déclaration actuelle), nommer l'équipement et cocher ses groupes. Plusieurs activités peuvent être réunies ; ne pas mélanger deux équipements CAF, ni le périscolaire et l'extrascolaire d'une même structure.
2. Le réalisé est calculé du **01/01 au 30/09 inclus**. Les consommations du 01/10 au 31/12 ne sont jamais incluses dans ce réalisé.
3. Le prévisionnel concerne uniquement le **01/10 au 31/12**. Choisir :
   - le même trimestre de N-1, au ratio heures / jours ouverts multiplié par les jours ouverts programmés de ce trimestre en N ; cette estimation est une méthode Noethys, pas une règle imposée par la CAF ;
   - la saisie manuelle des quatre indicateurs, y compris les sous-totaux AEEH. Saisir explicitement zéro si nécessaire ; un champ vide n'est pas interprété comme zéro.
4. **Calculer**, contrôler les quatre lignes, puis **Exporter CSV**. L'export conserve le périmètre, le profil, les filtres, la méthode et les bases historiques avec les trois colonnes : réalisé, prévision restante, total annuel actualisé.

Les heures réelles, facturées, et leurs parts AEEH sont distinctes. « Dont AEEH » est déjà inclus dans le total. Les prestations communes entre groupes sont dédupliquées par le moteur ; les jours ouverts sont comptés une seule fois pour l'équipement. Le facturé reprend `prestations.temps_facture`, sans ajouter le forfait du midi. Vérifier que la facturation est à jour jusqu'à septembre et que les réservations incluses par le profil correspondent bien aux données à déclarer.

Le réalisé AEEH utilise les droits enregistrés dans `aeeh_periodes` actifs au 30 septembre ; l'historique utilise ceux actifs au 31 décembre N-1. Il ne découpe pas chaque journée selon les changements de droits. Vérifier ces droits avant déclaration. Les formules `uniteN`, encore affectées par un défaut d'isolation entre individus dans l'état global, sont refusées dans cet écran afin de ne pas produire un réalisé incorrect.

Un calendrier futur ou historique manquant bloque l'estimation automatique et propose la saisie manuelle. Une activité nouvelle ou renommée avec de nouveaux IDs ne retrouve pas automatiquement l'historique de son prédécesseur : utiliser une prévision manuelle dans ce cas.

Cet écran prépare **les heures d'activité**. Les données financières (charges, produits, budget actualisé), les autres rubriques et les identifiants CAF doivent être renseignés et contrôlés à partir de la comptabilité et des consignes de l'équipement. Le CSV n'est pas un fichier d'import CAF ; aucune déclaration n'est transmise automatiquement.
