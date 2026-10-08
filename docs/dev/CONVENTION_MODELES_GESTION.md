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

## Affichage des blocs flottants dans Noedoc

Dans un modèle Convention, un bloc de texte dont l'ancrage est situé dans le **cadre principal** est « flottant » : le générateur PDF le fait couler dans le cadre, dans l'ordre du modèle, sur autant de pages que nécessaire, quelle que soit sa position exacte.

Depuis le 08/10/2026, l'éditeur Noedoc présente ces blocs de la même façon : empilés depuis le haut du cadre, repliés à la largeur du cadre lorsqu'ils n'ont pas de largeur propre. Ce qui ne tient pas sur la première page est tronqué ou masqué à l'écran et signalé par une mention de suite ; l'aperçu PDF montre le document complet.

Cet affichage ne modifie pas le modèle : à l'enregistrement, un bloc non déplacé garde son ancrage d'origine et son texte complet. Un bloc déplacé à la main garde la position choisie ; le sortir du cadre principal le rend à position fixe (règle inchangée du générateur).

## Sortie Word (.docx) et modèles personnels

La génération d'une convention modifiable depuis un modèle Word applique deux garanties (depuis le 08/10/2026) :

1. **Refus des mots-clés inconnus.** Tout mot-clé de la forme `{NOM_DU_CHAMP}` présent dans le modèle Word et que Noethys ne sait pas remplir arrête la génération. Le message liste les mots-clés en cause. Auparavant, un mot-clé inconnu restait imprimé tel quel dans le document.
   - Conséquence pour un **modèle personnel** existant : s'il contient un mot-clé mal orthographié ou absent de Noethys, il faut le corriger (ou le retirer) dans Word, en s'aidant de la liste des champs de Noedoc, puis relancer la génération.
   - Les accolades présentes dans les **valeurs** insérées (nom d'une structure, par exemple) ne sont jamais prises pour des mots-clés : seul le texte du modèle est contrôlé.
2. **Écriture atomique.** Le document est préparé entièrement, écrit dans un fichier temporaire du même dossier, puis substitué en une seule opération. En cas d'échec (modèle invalide, mot-clé inconnu, document de destination ouvert dans Word, disque plein), un document existant portant le même nom reste intact et aucun fichier partiel n'est laissé.

Aucun modèle Word n'est livré avec Noethys SL : ces garanties concernent uniquement les modèles fournis par l'utilisateur.
