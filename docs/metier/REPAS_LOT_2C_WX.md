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


## Lot 2C-3A — Audit tarifaire en lecture seule

Le module `UTILS_Repas_tarifs_audit_2c` (à partir du commit 2C-3A) expose trois opérations explicites :

1. `AuditerTarifsALSH(base, [IDactivite, ...])` : récupère uniquement les tarifs de ces activités, leurs combinaisons d'unités, le nombre de lignes de prix et des **comptages agrégés** de prestations, factures et ventilations/règlements. Aucune famille, aucun nom d'enfant, aucun diagnostic, aucune écriture SQL. Le drapeau `unites.repas=1` est seulement un **indice de repas inclus**, jamais une preuve de prix séparé.
2. `ValiderAccordTarifSepare(rapport, decision)` : exige l'identification d'un tarif journalier dédié à une seule unité repas, une plage de dates couverte par le tarif, l'activité, le site, le service, les identifiants du questionnaire, un approbateur, une preuve de tarif et deux confirmations humaines explicites : **repas distinct** et **accueil facturé indépendamment**. Les combinaisons, crédits ou données ambiguës sont refusés.
3. `SimulerNouvellePrestationPanier(accord, reponse_datee, accueil, repas)` : accepte uniquement un **choix daté et tracé**, un périmètre correspondant et l'absence de prestation/facture/règlement préexistant. Propose « ne pas créer de prestation repas payante », prix repas 0 €, prix accueil inchangé, en lecture seule. Un questionnaire *actuel* sans historique n'est pas une preuve de préférence passée et est refusé.

**STOP-GATE MAINTENUE :** aucun bouton d'activation ou chemin automatique depuis `CTRL_Grille`, aucune écriture dans `prestations`, `factures`, `ventilation`, `consommations` ou `questionnaire_reponses`. Les signatures humaines de cet audit ne sont pas une authentification intégrée à Noethys. L'accord `PREVOL_MANUEL_NON_ACTIF` et la proposition `SIMULATION_SANS_ECRITURE` sont *des sorties de test*. Ne pas annoncer zéro facturation automatique aux familles. Un audit anonymisé des **vrais tarifs ALSH**, sur copie isolée, est la condition de la connexion et de la recette financière complète.

Tester avec `python -m unittest tests.test_noethys_sl_repas_tarifs_audit_2c -v` dans le projet avec le chemin `noethys` chargé. Les cas de tests SQLite sont fictifs. Aucun export d'information personnelle.
