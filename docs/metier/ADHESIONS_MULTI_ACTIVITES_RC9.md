# Noethys-SL — Association automatique multi-activités (candidat RC9)

Date : 22 octobre 2026. **État : code préparé ; recette et publication RC9 suspendues.**

## Contrat métier validé

Une adhésion automatique individuelle couvre toutes les **activités ayant une
inscription valide** qui chevauche sa période de validité (bornes inclusives).
Le type de cotisation possède une option :

- **Inscriptions valides** (défaut) : statuts \`ok\`, \`date_inscription <= date_fin_cotisation\`,
  \`date_desinscription IS NULL OR date_desinscription >= date_debut_cotisation\`.
  Tous les IDactivite distincts correspondants sont ajoutés à
  \`cotisations.activites\` au format natif \`1;2;3\`, y compris si l'activité
  n'est pas requise par \`cotisations_activites\` : cette dernière table borne
  *le droit au déclenchement de l'adhésion*, pas sa liste descriptive.
- **Participations constatées** : comportement historique, pour les
  réservations/présences ou prestations de consommation effectivement
  qualifiées, jamais une simple inscription.

Une **inscription sans participation** ne crée ni \`cotisations\`, ni
\`prestations\`. La création financière conserve le parcours à confirmation
explicite avant aperçu de facturation de RC8.1 (issue #426), le verrou
transactionnel et \`AUTO_CREATION_SUSPENDUE=True\` sur la sauvegarde de grille.
Une seule adhésion et une seule prestation financière pour le titulaire.

## Inscription ajoutée en cours d'année

Après la sauvegarde *confirmée* d'une nouvelle inscription ou d'une modification
sur wx, \`ActualiserActivitesApresInscription(IDinscription)\` effectue une
actualisation **uniquement sur des adhésions automatiques déjà en cours**.
Aucune création financière ni renouvellement. Modifier le groupe d'une
inscription dans la même activité ne duplique pas l'association.

La liste ne détruit **jamais** automatiquement un ancien lien déjà inscrit
dans une cotisation : elle conserve la traçabilité des activités historiques
même si une inscription est annulée ensuite. Une inscription non valide ne
peut en revanche jamais être *nouvellement* ajoutée. Une désinscription
avant le début, une inscription après la fin ou un statut différent de \`ok\`
n'ajoutent aucune activité.

Les adhésions manuelles sont strictement inchangées. Les montants, dates,
prestations, ventilations, factures, comptes payeurs et règlements ne sont pas
recalculés. Les associations ajoutées sont tracées dans \`historique\`.

Les structures adhérentes (personne morale titulaire) regroupent les
inscriptions de leurs sections et personnes rattachées : le rapprochement
du compte payeur et de la famille est obligatoire afin de ne pas propager
une inscription d'une autre structure.

## Paramétrage et stockage

Dans l'interface historique : Paramétrage > Types de cotisations > Modifier un
type individuel > Options > « Activités associées automatiquement ».

Valeurs :
- **Toutes les inscriptions valides (conseillé)** ;
- **Participations constatées uniquement**.

Le choix est stocké **par IDtype_cotisation**, sous
\`parametres(categorie='noethys_sl_adhesions_activites',
nom='type_<IDtype_cotisation>', parametre='inscriptions|participations')\`.
Absence = \`inscriptions\`, sans créer d'entrée lors d'une simple lecture.
Valeur inconnue ou doublon = **erreur explicite**, jamais un choix implicite.
La table existe dans le schéma natif : **aucune migration SQL**.

## Périmètre, branches et contrôles

- **main** : moteur \`UTILS_Adhesions\`, jeu de tests SQLite fictif.
- **wx** : moteur commun, écran de réglage, hook de sauvegarde des inscriptions,
  et correction de suppression ciblée dans \`cotisations_activites\`.
- **qt** : même moteur métier ; adaptation du dialogue Qt natif à réaliser
  lorsque l'édition d'une inscription sera disponible dans Qt.

Tests conçus :
- aucune création financière avec une seule inscription ;
- créations existantes déclenchées par participation et associations multi-activités ;
- admission en cours d'année sans nouveau montant, date, prestation ni facturation ;
- mode alternatif, paramétrage par type, mode corrompu/dupliqué ;
- inscription future/hors période, refus, frontière inclusive ;
- structures distinctes sans fuite, cotisations manuelles inchangées ;
- périodes verrouillées, idempotence et absence d'appel à CreerAdhesion
  par le hook d'inscription ;
- contrats de l'interface wx et non-destruction des associations des autres
  activités lors du décochage d'une cotisation requise.

**Barrières avant RC9** : tests effectivement exécutés et chiffrés
(PASS/FAIL/SKIP) sur CI Windows, MySQL jetable, recette de la vraie fenêtre
avec base de test et contrôle du comportement financier RC8.1. Pas de
publication de release, tag, installeur ni déploiement sans ces preuves.
Aucune lecture ni modification des bases PMSL de production.
