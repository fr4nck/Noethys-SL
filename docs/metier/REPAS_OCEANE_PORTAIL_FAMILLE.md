# Import autonome des menus Océane vers Noethys-SL et Connecthys (03/11/2026)

## Besoin PMSL

À partir du fichier Excel transmis par Océane de Restauration, obtenir en quelques clics les menus des mercredis sur **Gestion des menus** et, si demandé, sur **le portail famille Connecthys**. Les documents de commandes fournisseurs, quantités, grammages, coûts et informations nominatives sont exclus de la publication aux familles.

## Source et structure reconnues

Source de recette : `Menus CLSH 5 él période 2.xlsx`.

- `Menus Mat & prim` (table détaillée datée) : entrée, plat, garniture, laitage, dessert ; plusieurs propositions peuvent coexister.
- `Semaine NN` : affichages hebdomadaires ; date du mercredi en G6, composantes G7 à G16. Les commentaires de composition G8 sont conservés avec l'entrée G7.
- Les semaines vides ne deviennent pas de faux menus.
- Le classeur peut contenir des mois distincts ; **l'opérateur sélectionne les dates**. Seuls les mercredis sélectionnés peuvent être publiés.

## Workflow utilisateur

1. Ouvrir **Restauration → Gestion des menus**, sélectionner le restaurateur Océane déjà déclaré.
2. Cliquer sur **Importer menus Océane (ou déposer XLSX)...**, ou **glisser-déposer le classeur Excel sur le bouton**.
3. Vérifier la liste de mercredis et sélectionner les dates à importer. Les prochains mercredis sont présélectionnés, jamais l'ensemble de l'historique.
4. Lire l'aperçu et les écarts. L'import natif est **idempotent** (répéter le même import n'ajoute aucun doublon) et ne remplace **jamais** une valeur de menu différente déjà saisie manuellement. Les cinq catégories existantes sont réutilisées si identifiables. Une catégorie nouvelle n'est créée qu'avec la confirmation.
5. Après l'import, choisir **Oui** à la proposition de préparer la publication sur le portail. L'éditeur **natif Connecthys → bloc Blog** s'ouvre prérempli ; choisir sa page, contrôler le texte, la date de fin d'affichage, la couleur, puis enregistrer.
6. La publication utilise ensuite la **synchronisation habituelle du portail**. Aucun accès distant, aucun mail ou upload ne part du convertisseur lui-même.

L'éditeur du portail garde le texte en **RichText XML** pour réédition et le contenu public en **HTML échappé**. Le HTML n'embarque ni images distantes, ni liens, ni scripts. Les dates, recettes et ingrédients affichables proviennent uniquement du classeur fournisseur.

Un bloc du même titre est refusé plutôt que de créer des publications en double : l'opérateur peut l'ouvrir dans la configuration du portail pour le modifier.

## Fichiers intégrés

- `noethys/Utils/UTILS_Repas_oceane_menus.py` et `UTILS_Oceane_xlsx.py` : lecture et extraction sans reconstruire les dessins Excel.
- `noethys/Utils/UTILS_Repas_oceane_publication.py` : sélection de dates, aperçu texte, HTML échappé et préparation des catégories.
- `noethys/Utils/UTILS_Repas_oceane_import_db.py` : écriture dans les **tables natives** `menus_categories` et `menus` après confirmation explicite, transaction, refus des conflits.
- `noethys/Dlg/DLG_Menus.py` : bouton et glisser-déposer, choix des dates, aperçu, confirmation et éditeur de bloc Blog existant.

## Sécurité et limites

- Aucune publication automatique au simple glisser-déposer.
- Aucune récupération des régimes alimentaires individuels, des PAI, ni de données relatives aux enfants : menus **collectifs seulement**.
- Aucun nouveau schéma SQL ou fichier à installer manuellement.
- Un menu déjà importé identique est ignoré ; un menu différent sur une date existante provoque un refus plutôt qu'un écrasement silencieux.
- Les changements apportés à la base par l'import sont atomiques sous SQLite et MySQL, dans les limites des moteurs transactionnels utilisés.
- L'éditeur du portail est validé **fonctionnellement** par son code et les tests de construction ; la première synchronisation avec une instance réelle Connecthys doit encore être qualifiée en recette avant mise en production.
- Aucun changement aux commandes déjà validées et aucun envoi fournisseur.

## Recettes

`tests/test_noethys_sl_oceane_portail.py` vérifie notamment la sélection manuelle, l'absence de menu vide, le rendu HTML sûr, le réemploi des catégories, l'idempotence, les conflits et le rollback des insertions fictives, ainsi que la présence des contrôles d'interface.

Les tests sont inclus dans la CI rapide `wx` sur Linux sans interface (pure) et Windows.
