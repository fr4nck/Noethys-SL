# Gestion des modèles Convention

Le dialogue **Générer une convention** utilise exclusivement le moteur Noedoc historique et les tables `documents_modeles` / `documents_objets`.

Le bouton **Gérer les modèles...** permet :

- modifier le modèle sélectionné dans Noedoc ;
- dupliquer un modèle sans recopier son statut de modèle par défaut ;
- renommer un modèle ;
- définir l'unique modèle par défaut de la catégorie `convention` ;
- supprimer un modèle lorsqu'il est marqué `supprimable` ;
- installer idempotemment les modèles d'exemple embarqués, dont le modèle scolaire.

Lorsqu'aucun modèle Convention n'existe, les exemples embarqués sont installés automatiquement à la première ouverture du dialogue. Aucun modèle utilisateur existant n'est écrasé par cette initialisation.

Les correctifs antérieurs de sélection initiale, de dimensionnement responsive et de récupération des modèles mal encodés restent indépendants de ce lot.
