# Noethys SL 0.1.0 RC9 — préversion Windows de recette

**Préversion de recette uniquement. Ne pas installer sur les postes PMSL de production sans validation pilote et sauvegarde vérifiée.**

RC9 rassemble les correctifs présents sur la branche Windows `wx` depuis RC8.1, notamment :
- Correctif du sélecteur « État des consommations » dans l'état global CAF/AFAS : les quatre statuts existants (réservation, présent, absence justifiée, absence injustifiée) sont sélectionnables par cases à cocher sans création de nouveaux états.
- Évolutions de l'association des inscriptions et cotisations introduites après RC8.1, sous réserve de la qualification RC9.
- Conservation des protections de facturation des adhésions anticipées de RC8.1.

Les tests automatiques vérifient la compatibilité du code, les contrats métiers et le démarrage Windows. Le rendu réel du sélecteur devra être confirmé en recette manuelle sur Windows.

**Aucune migration ni intervention automatique sur la base de données n'est demandée pour ce correctif d'interface.**
