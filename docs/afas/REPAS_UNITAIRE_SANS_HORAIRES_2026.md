# AFAS V2 — repas unitaire sans horaires (audit ALSH 22/10/2026)

## Fait observé dans la sauvegarde

Source privée : `Noethys_20261022_1444.nod` / `pelemele_data.sql`,
analyse strictement en lecture seule. L'unité `Repas` (ID 2,
activité ALSH ID 1) est de type **Unitaire** et ne contient ni
`heure_debut` ni `heure_fin`. Les unités `Journée` (ID 1),
`Matin` (ID 3), `Après-midi` (ID 4) ont respectivement les plages
08:30–17:30, 08:30–12:30, 13:30–17:30.

Sur les groupes La Guerche (ID 1), Bais +6 (2), Moutiers (3) et Bais −6
(27), entre le 01/01 et le 30/09/2026 : **4 339** lignes repas à
l'état `present` (La Guerche 1 296 ; Bais +6 1 085 ; Moutiers 916 ;
Bais −6 1 042). Ventilation agrégée des **4 339** repas présents, par enfant/jour/groupe :
**4 044** accompagnent une journée complète présente ; **196** un
matin seul ; **96** un après-midi seul ; **3** ne sont accompagnés
d'aucune unité Journée, Matin ou Après-midi présente. Les **295** cas
hors journée complète exigent une vérification particulière des horaires
de repas et des pointages. Ce décompte n'est pas une durée CAF.

## Confirmation métier du 03/11/2026 et repas sans accueil

La direction confirme la plage **12:30–13:30** de l'unité `Repas` (ID 2,
type Unitaire). Cette valeur peut être inscrite **dans les presets
de recette AFAS V2**, sans écriture dans la base MySQL de production.
Les plages `12:00–13:30` utilisées dans certains tests sont fictives
et ne remplacent pas l'horaire réel.

**Contrôle supplémentaire :** un repas `present` sans consommation
`present` et qualifiée d'une unité principale (`accueil`, `journee`
ou `demi_journee`) du **même site, même enfant, même date** devient
une anomalie bloquante, sans heure de repas comptabilisée.
Une garderie, une réservation, une absence ou un accueil sur un autre
site ne suffit pas à valider le repas isolé. Les trois cas identifiés
dans la sauvegarde doivent être vérifiés avant déclaration.

## Règle corrective sur wx

- Les catégories horaires classiques continuent d'exiger la **concordance
  entre la plage déclarée dans le preset AFAS et les horaires Noethys**.
- **Seule exception** : unité de type `Unitaire`, classée `repas`,
  sans AUCUN horaire (`heure_debut` et `heure_fin` absents).
  Une plage `HH:MM-HH:MM` **explicitement saisie dans le preset**
  est acceptée même sans heures dans l'unité d'origine. Elle doit être
  vérifiée par l'organisateur avant utilisation.
- **Sans plage dans le preset, plage mal formée, horaire Noethys partiel
  ou type d'unité incompatible : calcul bloquant.** Aucune heure de repas
  n'est choisie ni déduite automatiquement.
- En périscolaire, la plage déclarée se combine avec celle de
  `Journée` par union d'intervalles, sans la compter deux fois.
  En extrascolaire, une présence de repas sans horaires de pointage peut
  utiliser cette plage vérifiée pour le décompte physique ; le
  facturé reste soumis aux règles de factures et de journées/demi-journées.
- Rien n'est écrit automatiquement dans la sauvegarde ou dans MySQL ;
  l'administrateur doit vérifier et enregistrer volontairement son preset.
- La direction a confirmé le 03/11/2026 la plage **12:30-13:30**
  pour le repas sur la base ALSH étudiée. La plage `12:00-13:30`
  des tests demeure fictive ; aucune valeur n'est écrite dans MySQL.
- Un repas présent **sans autre unité d'accueil présente sur le même
  site et le même jour** produit une anomalie bloquante. Le calcul
  numérique peut rester visible pour contrôle, mais ne peut pas faire
  l'objet d'une déclaration CAF validable tant que le pointage
  correspondant n'est pas vérifié.

## Recette restant nécessaire

1. Sur une **copie isolée** de la base ALSH, confirmer par la direction
   les horaires réels des repas de Bais et de La Guerche–Moutiers,
   ainsi que leur éventuelle variation selon les périodes.
2. Dans `Consommations > Déclarations AFAS > Unités`, classer `Repas`
   comme tel, puis renseigner la plage uniquement après confirmation.
3. Rejouer le contrôle interne `arrete_septembre`, examiner les
   anomalies par site et par jour, puis vérifier les cas repas + journée,
   repas + demi-journée et repas seul.
4. Ne pas publier d'extrait individuel ou de sauvegarde sur GitHub ;
   ne déclarer aucune heure CAF avant recette et validation métier.

Cette évolution ne règle pas d'éventuels écarts historiques des anciens
états globaux, qui ne sont pas une référence CAF V2 qualifiée.
