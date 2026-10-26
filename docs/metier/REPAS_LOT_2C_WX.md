# Lot 2C-2 et garde tarifaire 2C-3 — panier familial

**Développement sur wx après RC9.1, pas encore version publique.** Le modèle de repas opt-in avec un quatrième choix `Repas apporté par la famille / sans repas PMSL` sert au calcul du fournisseur. La journée ou demi-journée réservée contient la présence midi si les **horaires explicites** du site/service en couvrent intégralement la plage. Aucun parent ne réserve une présence au repas séparée.

## Configuration de la commande

Configurer sur un nouveau modèle de commandes des colonnes régime habituelles et **une colonne « Panier apporté par la famille (hors commande) »**. Chaque colonne partage les mêmes quatre identifiants de réponse, site, service, unités de journée/demi-journée, horaires midi `HH:MM`, et le booléen explicite « La formule inclut normalement un repas PMSL ». Aucun texte du questionnaire n'est interprété comme un diagnostic/allergie. Les valeurs manquantes ou incohérentes bloquent la suggestion. Le mode nouveau exclut les paniers de la commande au restaurateur et des sous-totaux fournisseurs, sans effacer les présences.

En opt-in seulement, une absence de réponse signifie standard **si la formule fournit normalement un repas**. Sans offre, le logiciel refuse de présumer un repas ; seul un panier explicitement choisi est recevable. Les anciens modèles à trois choix conservent le statut « non renseigné ». Les enfants sont comptés au plus une fois par site/service. L'ajustement des colonnes enfants en fonction des paniers n'est automatique que si leurs unités correspondent exactement aux unités du nouveau modèle ; sinon aucune suggestion automatique.

## Facturation — barre de sécurité P0

Le module `UTILS_Repas_tarification_2c` **simule**, au centime, la composante repas à 0 € : 
- **repas séparé** : tarif d'accueil inchangé, composante repas à 0 € pour le panier ;
- **journée avec repas inclus** : tarif journée sans repas **distinct et approuvé requis**, aucun rabais implicite ;
- **prestation déjà facturée ou réglée** : arrêt et régularisation humaine ;
- tous les anciens tarifs et états CAF/AFAS sont laissés inchangés.

**Attention : cette politique n'est PAS raccordée à la création des prestations ni aux factures. Il est interdit de considérer que les paniers familiaux sont automatiquement exonérés sur une facture réelle à ce jalon.** La grille de tarification Noethys combine éventuellement plusieurs unités. L'activation exige la qualification des tarifs de chaque accueil PMSL et une méthode historique datée évitant les changements rétroactifs. Aucune migration ni correction automatique de factures ; le bouton CAF/AFAS V1 reste masqué.

## Tests

- Tests purs 2C-1 reportés à l'identique depuis `main`.
- Tests du calcul de composante financière, du refus des forfaits non approuvés et des factures existantes.
- Tests synthétiques SQLite des demi-journées, paniers hors fournisseurs, régimes hérités et contrôle de commande. Aucune donnée réelle ni email.

## Reste pour livraison métier

2C-3 : implémenter le raccordement tarifaire effectif, le prix sans repas des forfaits, les exceptions datées persistées et leur audit sur copie de base ALSH ; qualifier les factures avec/sans repas (y compris les factures existantes). Puis recette graphique Windows. RC9.1 publiée ne contient aucune de ces modifications.
