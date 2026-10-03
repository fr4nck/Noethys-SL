# Préparer les déclarations AFAS par équipement

Dans **Consommations → État global**, sélectionner les activités d'un équipement CAF et charger/configurer le profil de calcul du réalisé (coefficients ou temps réels), les états de consommation, les jours scolaires/vacances et les éventuels plafonds. Cliquer sur **CAF / AFAS**.

Pour réutiliser un équipement enregistré, ouvrir directement **CAF / AFAS** et choisir sa configuration ; il n’est pas nécessaire de sélectionner à nouveau les activités dans l’état global.

Créer une configuration **par équipement CAF** (chaque ALSH, le club ados), avec le bouton de sauvegarde situé à côté de « Configuration enregistrée ». Elle mémorise le nom, les activités/groupes, les unités et options de calcul et la méthode. La catégorie de profils AFAS est distincte de celle de l’état global : elle ne modifie pas le profil « Caf - Périscolaire » existant. Les saisies manuelles sont conservées par année et déclaration ; elles ne sont pas reportées automatiquement sur une autre période ou année. Pour mettre à jour les règles de calcul, partir du profil corrigé dans l’état global et enregistrer une nouvelle configuration AFAS.

Choisir la déclaration :

| Déclaration | Réalisé | Prévision restante |
| --- | --- | --- |
| Prévisionnel annuel | Aucun | 01/01–31/12 |
| Actualisée (Juin) | 01/01–30/06 | 01/07–31/12 |
| Actualisée (Septembre) | 01/01–30/09 | 01/10–31/12 |
| Réel annuel | 01/01–31/12 | Aucune |

Pour l’échéance de septembre :

1. Choisir l'année (2026 pour la déclaration actuelle), nommer l'équipement et cocher ses groupes. Plusieurs activités peuvent être réunies ; ne pas mélanger deux équipements CAF, ni le périscolaire et l'extrascolaire d'une même structure.
2. Le réalisé est calculé du **01/01 au 30/09 inclus**. Les consommations du 01/10 au 31/12 ne sont jamais incluses dans ce réalisé.
3. Le prévisionnel concerne uniquement le **01/10 au 31/12**. Choisir :
   - le même trimestre de N-1, au ratio heures / jours ouverts multiplié par les jours ouverts programmés de ce trimestre en N ; cette estimation est une méthode Noethys, pas une règle imposée par la CAF ;
   - la saisie manuelle des quatre indicateurs, y compris les sous-totaux AEEH. Saisir explicitement zéro si nécessaire ; un champ vide n'est pas interprété comme zéro.
4. **Calculer**, contrôler les quatre lignes, puis **Exporter CSV**. L'export conserve le périmètre, le profil, les filtres, la méthode et les bases historiques avec les trois colonnes : réalisé, prévision restante, total annuel actualisé.

Les heures réelles, facturées, et leurs parts AEEH sont distinctes. « Dont AEEH » est déjà inclus dans le total. Les prestations communes entre groupes sont dédupliquées par le moteur ; les jours ouverts sont comptés une seule fois pour l'équipement. Le facturé reprend `prestations.temps_facture`, sans ajouter le forfait du midi. Vérifier que la facturation est à jour jusqu'à septembre et que les réservations incluses par le profil correspondent bien aux données à déclarer.

Le réalisé AEEH utilise les droits enregistrés dans `aeeh_periodes` actifs à la date de situation (30 juin, 30 septembre, ou 31 décembre selon la déclaration) ; l'historique utilise ceux actifs au 31 décembre N-1. Il ne découpe pas chaque journée selon les changements de droits. Vérifier ces droits avant déclaration. Les formules `uniteN`, encore affectées par un défaut d'isolation entre individus dans l'état global, sont refusées dans cet écran afin de ne pas produire un réalisé incorrect.

Un calendrier futur ou historique manquant bloque l'estimation automatique et propose la saisie manuelle. Une activité nouvelle ou renommée avec de nouveaux IDs ne retrouve pas automatiquement l'historique de son prédécesseur : utiliser une prévision manuelle dans ce cas.

Cet écran prépare **les heures d'activité**. Les données financières (charges, produits, budget actualisé), les autres rubriques et les identifiants CAF doivent être renseignés et contrôlés à partir de la comptabilité et des consignes de l'équipement. Le CSV n'est pas un fichier d'import CAF ; aucune déclaration n'est transmise automatiquement.
