# Lot C — Fiche Club ados (03/11/2026)

## Source et choix de modèle

Modèle PMSL fourni : `Fiche Ados.pdf` (2 pages A4) et
`Fiche Ados.doc` (source bureautique). Le PDF de référence comporte :
- Page 1 : année, classe, identité, deux responsables légaux,
  cinq lignes d'accompagnants, rappel d'actualisation,
  dernière vaccination DT Polio, médecin.
- Page 2 : maladies / allergies / PAI / traitements / AESH / AEEH /
  régime alimentaire, cinq autorisations **Photos, Maquillage, Baignade,
  Activités physiques, Transport**, puis l'autorisation **distincte** de
  repartir seul du Club ados à la fin des activités prévues, et signature.

Cette édition est distincte de la fiche enfant : elle **ne remplace pas**
celle-ci. En particulier, le départ seul de la fiche ados se trouve sur
la seconde page, et le transport est un cinquième choix explicite.

## Implémentation wx

- Ouvrir la fiche enfant existante puis cliquer
  `Ouvrir la fiche ados du même enfant`. Il s'agit du **même individu**
  Noethys, sans nouvelle table ni nouvelle fiche de données.
- Le dialogue « Fiche ados » propose par défaut le périmètre
  `Club ados 2026-2027` et la version de texte signé
  `Fiche Ados 2026-11`. Le périmètre reste modifiable par l'opérateur.
- Les données d'identité, de responsables légaux, d'accompagnants,
  de scolarité, de vaccination et de santé proviennent des lectures
  existantes de la fiche enfant ; aucun nouveau questionnaire créé.
- Les autorisations `transport_ados` et `depart_seul` sont **deux**
  réponses indépendantes (Non renseigné / Oui / Non) dans le registre
  `accueil_autorisations`, avec la même historisation et le même
  fonctionnement d'enregistrement signé que les autres droits.
  Une autorisation ALSH sous un périmètre différent n'est pas réutilisée
  automatiquement pour le Club ados.
- `UTILS_Accueil_impression.GenererPDFAdos` produit un PDF A4 de deux
  pages. Le formulaire enfant utilise toujours `GenererPDF` et garde
  sa grille de quatre autorisations d'origine.
- Un document non renseigné ne pré-coche ni Transport, ni Départ seul.
  Une réponse expirée ou à vérifier ne donne jamais lieu à une case Oui
  pré-cochée.

## Qualification

Tests fictifs `test_noethys_sl_accueil_ados.py` (format 2 pages, rubriques,
cinq autorisations, texte de départ seul, non mutation des données),
`test_noethys_sl_accueil_autorisations.py` (deux décisions distinctes,
périmètre Club ados), `test_noethys_sl_accueil_wx.py` (dialogue,
enregistrement signé, préparation du PDF ados).
La CI Windows rapide inclut le nouveau module de tests.

**État** : code candidat sur `wx`, pas de mise à jour automatique
d'une installation Windows. Recette complète de la CI et contrôle visuel
du rendu généré par l'application nécessaires avant livraison.
La fiche famille fera l'objet d'un sous-lot séparé, avec récupération
des responsables, enfants, régime CAF/MSA et signature familiale.

Aucune migration de base PMSL, aucun changement de facturation.
