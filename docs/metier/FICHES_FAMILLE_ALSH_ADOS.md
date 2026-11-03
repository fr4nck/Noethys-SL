# Lot C — Fiche famille commune ALSH / Club ados (03/11/2026)

## Décision PMSL

Deux documents source ont été fournis :
- `Fiche Famille(1).docx` : ALSH La Guerche, Moutiers, Bais, tableau « ENFANTS À INSCRIRE », deux pages et signatures ;
- `Fiche Famille club ados.docx` : Club ados Bais, tableau « ADOS À INSCRIRE », deux pages avec une **case CAFPRO supplémentaire** et sa clause de renouvellement.

Ils avaient d'abord été intégrés en deux modèles PDF. Après arbitrage métier, l'exploitation utilisera **un seul formulaire famille pour le foyer**, même lorsque ses enfants fréquentent plusieurs accueils. Les fiches *individuelles* enfant et ado restent distinctes.

## Version unifiée dans Noethys-SL wx

Le dossier famille propose maintenant **Outils → Éditer la fiche famille Pêle-Mêle (PDF)** (une seule entrée dans le menu). Une édition produit **deux pages A4 et une signature familiale**.

- Page 1 : en-tête commun, deux responsables légaux, régime CAF/MSA/autre, numéro d'allocataire, **case CAFPRO incluse mais non précochée**, y compris lorsque la base contient une valeur historique.
- Page 2 : tableau **ENFANTS / ADOS À INSCRIRE** de quatre lignes, avec nom, prénom, sexe, naissance, école/classe et **accueil/site de chacun**, puis les engagements issus des formulaires fournis et la signature.
- L'opérateur choisit d'abord les enfants du foyer concernés, puis **pour chacun** un ALSH (La Guerche, Moutiers, Bais) et/ou le Club ados (Bais). Deux accueils sont possibles pour le même jeune, sans supposer une inscription à partir de son âge.
- Les coordonnées, les données CAF/MSA et la scolarité sont lues en **lecture seule** du dossier Noethys existant. Les affectations d'accueil servent uniquement au PDF ; **elles ne créent pas d'inscriptions**.
- La fonction pure `UTILS_Accueil_familles.AffecterAccueils` vérifie la présence d'un choix pour chaque enfant, l'unicité du site ALSH et que seuls les enfants de la famille sélectionnée sont affichés.
- Les anciennes variantes techniques `modele=alsh` et `modele=ados` sont temporairement conservées pour compatibilité et tests de non-régression, **mais ne sont plus proposées au menu**. La nouvelle voie utilise `modele=famille`.

## Points de contrôle

La case CAFPRO **ne constitue pas une autorisation enregistrée** tant que le représentant n'a pas signé ; aucune donnée familiale n'est modifiée par l'édition. Les demandes d'autorisations de départ seul et de transport propres aux fiches individuelles sont maintenues séparément.

Tests fictifs dans `tests/test_noethys_sl_accueil_familles.py` et `tests/test_noethys_sl_accueil_familles_impression.py`, inclus dans la CI rapide `wx` : fratrie mixte, enfant fréquentant deux accueils, refus de plusieurs ALSH pour un enfant, clause CAFPRO, deux pages PDF, conservation de la source. La validation finale sur Windows et le contrôle visuel du formulaire sont requis avant publication d'une version installable.

Aucune écriture dans la base de production, aucun changement des tarifs ou des commandes fournisseurs.
