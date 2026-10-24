# Noethys SL 0.1.0 RC9 — préversion Windows de recette

**Préversion de recette uniquement. Ne pas installer sur les postes PMSL de production sans validation pilote et sauvegarde vérifiée.**

RC9 rassemble les correctifs présents sur la branche Windows `wx` depuis RC8.1, notamment :
- Correctif du sélecteur « État des consommations » dans l'état global CAF/AFAS : les quatre statuts existants (réservation, présent, absence justifiée, absence injustifiée) sont sélectionnables par cases à cocher sans création de nouveaux états.
- Évolutions de l'association des inscriptions et cotisations introduites après RC8.1, sous réserve de la qualification RC9.
- Conservation des protections de facturation des adhésions anticipées de RC8.1.

Les tests automatiques vérifient la compatibilité du code, les contrats métiers et le démarrage Windows. Le rendu réel du sélecteur devra être confirmé en recette manuelle sur Windows.

**Aucune migration ni intervention automatique sur la base de données n'est demandée pour ce correctif d'interface.**

- Confirmations Connecthys (réponse à une demande, reçu, facture) envoyées à plusieurs adresses : la demande n'est validée que si toutes les adresses ont été acceptées par le serveur d'envoi, quel que soit le moteur (SMTP ou Mailjet). Un nouvel essai n'envoie le message qu'aux adresses qui ne l'ont pas encore reçu. Les états et réponses transmis au portail Connecthys sont inchangés. Les envois par lot depuis l'éditeur d'emails retrouvent le moteur Mailjet de RC8.1 (progression, arrêt, « ne plus signaler les erreurs »).
- Correction de la saisie conjointe d'une attestation et d'un quotient familial : l'option « Validité illimitée » est désormais acceptée, avec conservation de la convention interne de date du 01/01/2999.
- Adhésions individuelles automatiques : pour les types de cotisation existants, l'absence de réglage vaut « Toutes les inscriptions valides ». Après mise à jour, chaque inscription enregistrée complète la liste des activités des adhésions automatiques en cours (aucune prestation créée). Pour conserver l'ancien comportement, choisir « Participations constatées uniquement » dans le type de cotisation.
- Saisie d'un type de cotisation : après une erreur d'enregistrement du mode d'association, une nouvelle validation n'insère plus les unités en double. Un mode enregistré en double ou invalide n'empêche plus d'ouvrir le type : il est signalé, et la validation de la fenêtre le corrige (la création automatique des adhésions de ce type reste bloquée jusque-là).

## Bouton « CAF / AFAS » masqué provisoirement

Le bouton « CAF / AFAS » de l'état global est masqué dans RC9. Son calcul (AFAS V1) n'est pas qualifié pour une déclaration CAF : l'audit contradictoire du 23/10/2026 a reproduit des heures comptées hors périmètre, des doubles comptages et des statuts de consommation non distingués. Les autres fonctions de l'état global (paramètres, options, profils, aperçu PDF) sont inchangées. Le code AFAS est conservé et sera réactivé uniquement après correction et requalification.

**Utilisateurs de RC8 et RC8.1 :** le bouton « CAF / AFAS » y est encore visible. Ses résultats ne doivent pas être utilisés pour une déclaration CAF sans contrôle manuel indépendant. Voir [la consigne détaillée](../incidents/2026-10-23-afas-v1-bouton-masque.md).
