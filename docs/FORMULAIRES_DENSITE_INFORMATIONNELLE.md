# Noethys — formulaires métier et densité informationnelle

**Statut : norme applicative dérivée de PMSL-Arch ADR-005.**

## Positionnement

Ce document complète `DESIGN_SYSTEM_UI_UX.md`, `WXPYTHON_UI_RULES.md` et `DASHBOARD_MODERNISATION.md`.

Noethys est une application métier desktop : la cible est une **productive UI**, pas une interface marketing espacée ni une interface tassée. La densité doit servir la lecture, la saisie répétitive et la réduction des erreurs.

## Dimensionnement des champs

La taille d'un champ doit refléter la donnée attendue.

Catégories à centraliser progressivement :

```text
FIELD_XS
FIELD_CODE
FIELD_POSTAL_CODE
FIELD_DATE
FIELD_TIME
FIELD_NUMBER
FIELD_PERCENT
FIELD_MONEY
FIELD_PHONE
FIELD_NIR
FIELD_SIRET
FIELD_IBAN
FIELD_NAME
FIELD_CITY
FIELD_EMAIL
FIELD_ADDRESS
FIELD_TEXT
FIELD_LONG_TEXT
```

Exemples : un code postal, une heure ou une date restent compacts ; un téléphone, un NIR ou un SIRET ont une largeur calibrée sur leur format ; une adresse ou un email utilisent une largeur plus importante ; un mémo est réellement extensible.

Les métriques doivent dépendre de la police et du DPI plutôt que de tailles historiques fixées en pixels.

## Règle de layout

`wx.EXPAND` n'est pas le comportement par défaut des contrôles courts.

Il reste adapté aux listes, tableaux, recherches longues, adresses, mémos et zones de travail. Un sizer organise les relations entre contrôles mais ne doit pas transformer automatiquement chaque champ en pleine largeur.

Les couples naturels peuvent partager une ligne : code postal/ville, date début/date fin, heure début/heure fin, téléphone/portable, montant/unité. Aucun rapprochement ne doit être fait uniquement pour remplir l'espace disponible.

## Densité productive

- limiter les grands espaces morts ;
- ne pas créer de cartes ou cadres géants pour quelques valeurs ;
- privilégier les espacements du design system ;
- utiliser l'espace écran supplémentaire pour afficher davantage d'information utile ;
- conserver une navigation clavier rapide ;
- préserver la lisibilité aux différents niveaux de zoom/DPI.

La densité se mesure par la quantité d'information utile aisément parcourue, pas par la quantité de pixels occupés.

## Labels, aides et erreurs

- label persistant ;
- placeholder jamais utilisé comme seul libellé ;
- labels au-dessus par défaut sur les formulaires hétérogènes ;
- labels à gauche possibles sur les grilles administratives très régulières ;
- aide de format uniquement lorsqu'elle prévient une erreur réelle ;
- validation complète à l'enregistrement et contrôles intermédiaires non agressifs ;
- erreur proche du champ concerné, explicite et actionnable ;
- information jamais portée uniquement par la couleur.

## Composants communs avant écrans

La logique de mise en œuvre est :

`donnée métier -> rôle de champ -> métriques communes -> widget`

et non :

`écran -> largeur locale -> exception de sizer`.

Lorsqu'un défaut est transversal, chercher d'abord dans les composants communs, helpers de layout, contrôles de saisie et règles de scaling avant de modifier un dialogue particulier.

## Dashboard

Les gadgets, panneaux et widgets d'accueil appartiennent au dashboard. Ils ne doivent pas rester visibles au-dessus des écrans métier ni être intégrés au layout global de l'application.

Leur visibilité doit être gérée par le conteneur du dashboard, jamais par une succession de `Hide()` ajoutés dans les écrans.

## Priorités

1. P0 — fenêtres ou dialogues qui plantent ou ne s'ouvrent pas ;
2. P1 — primitives, sizing sémantique, sizers et frontière dashboard ;
3. P2 — migration progressive des formulaires historiques ;
4. P3 — finitions locales.

Une fenêtre inaccessible est un blocage fonctionnel et reste prioritaire sur la cosmétique.

## Références

- PMSL-Arch : `docs/ADR/ADR-005-formulaires-densite-informationnelle.md`
- `docs/DESIGN_SYSTEM_UI_UX.md`
- `docs/DASHBOARD_MODERNISATION.md`
- Bastien & Scapin
- Fluent 2
- Carbon Design System
- RGAA / pratiques DSFR / GOV.UK / USWDS
