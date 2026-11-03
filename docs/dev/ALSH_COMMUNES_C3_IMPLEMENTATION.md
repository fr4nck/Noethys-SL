# ALSH-C3 — Consultation wx de fréquentation par enfant et commune

Date : 3 novembre 2026. **Prototype qualifié hors production, non déployé**.

## Fonctionnement

Le module C3 raccorde le moteur daté C1/C2 à une fenêtre wx Noethys. Il ne crée **ni activité**, **ni nouvelle facture**, **ni compte payeur**.

L'ancienne fenêtre wx `DLG_Frequentation_collectivites.py` (situation financière et acomptes) demeure accessible. Son ancien importation mensuelle s'appuie sur **les adresses actuelles**, donc n'est PAS une preuve de la résidence historique d'un enfant ayant déménagé. La nouvelle fenêtre `DLG_ALSH_Commune_C3.py` utilise les observations automatiques datées de C2.

- Un menu distinct **Facturation → Fréquentation par enfant et commune (ALSH)** ouvre C3, et un bouton depuis l'ancienne situation financière ouvre le même écran.
- Choix **profil ALSH**, date de début/fin, **commune (code INSEE)**. L'option « toutes les communes » est volontairement anonyme ; les noms et adresses ne sont affichés que lorsqu'une seule commune est sélectionnée.
- Quatre onglets : synthèse communale, récapitulatif par enfant avec adresse complète applicable à chaque période, détail des consommations datées, anomalies à vérifier.
- **Recalculer** relit les tables Noethys `consommations` et l'historique C2 via `FrequentationCommunesAuto.calculer_automatiquement`; les retours dans une commune et les changements de résidence du représentant (`adresse_auto`) sont pris en compte sans ressaisie.
- **Exports CSV** compatibles Excel : récapitulatif nominatif d'une commune, détail daté nominatif d'une commune, synthèse anonymisée toutes communes. Les deux exports nominatifs sont bloqués si une anomalie globale n'a pas été levée. Les exports nominatifs sont audités et n'écrasent aucun fichier existant.
- Boutons de paramétrage distincts : associer **CP + ville** au **code INSEE vérifié**, enregistrer une **nouvelle version de profil** (couples activité/groupe, qualification des unités J/M/A/exclu, clauses tarifaires datées et référence de convention signée) et corriger exceptionnellement avec justificatif une date d'effet d'un déménagement.

## Droits

`UTILS_ALSH_C3_Session.py` se fonde sur l'identité de l'utilisateur actuel Noethys, jamais sur un acteur inventé côté écran. Les administrateurs actifs ont tous les droits ; les autres doivent recevoir explicitement les droits sous la catégorie `facturation_situation_collectivites_alsh` :

- `consulter` : situation nominative et export **anonyme** ;
- `exporter` : exports nominatifs d'une seule commune ;
- `modifier` : correspondances communales, nouveau profil et correction exceptionnelle d'une date avec preuve.

**Refus par défaut** si un droit n'existe pas ou si l'identité Noethys n'est pas disponible. Les droits sont distincts des permissions familiales et comptables.

## Conditions d'installation

- Les migrations **C1 et C2 proposées** doivent avoir été appliquées **sur une copie sauvegardée et qualifiée** avant de lancer l'écran. Le code vérifie les tables et refuse l'accès si elles manquent. **Il ne lance jamais une migration automatiquement**.
- Le profil ALSH et les correspondances INSEE doivent être **créés par un gestionnaire habilité**. Aucun tarif de convention, code communal ou unité n'est deviné.
- Pour MySQL, une connexion dédiée, `autocommit OFF` et transactions explicites sont requis. La présence des DDL MySQL C1/C2 dans le dépôt **ne constitue pas** une recette MySQL 5.7.
- Avant la première date observée par les triggers, les domiciles ne sont pas reconstruits sans preuve. Une correction datée peut être faite sur une observation avec justificatif, sinon la présence reste en anomalie.
- Chaque résultat affiche **BROUILLON NON FACTURABLE**. Pas de validation de situation, de facture, de paiement ni de ventilation TVA.

## Qualification

**124/124 tests PASS** dans un laboratoire SQLite fictif (C1: 52, C2: 40, C3: 32) : mouvements de plusieurs communes, adresses de représentants, cas ambigus, tarifs, arrondis, exports par commune, contrôles d'accès, non-écrasement de fichiers et contrats UI.

**Non qualifiés :** exécution graphique sur Windows/wxPython, MySQL 5.7 en réel, montée en charge, données ALSH issues d'une copie MAD, notices/droits par profil sur vrais postes, génération PDF et XLSX nominative, gel des situations, acomptes et solde à partir du calcul C2, et intégration à la facturation historique. Le rapport mensuel historique wx conserve son propre calcul et ne doit pas être considéré comme une situation C2 validée.

## Sources

- `noethys/Utils/UTILS_ALSH_C3_Session.py` (cœur commun sur `main`, copié à l'identique vers `wx`)
- `noethys/Dlg/DLG_ALSH_Commune_C3.py` (écran wx uniquement sur branche `wx`)
- `noethys/Noethys.py` et `noethys/Dlg/DLG_Frequentation_collectivites.py` (points d'accès sur `wx`)
- `tests/test_alsh_communes_c3_session.py` et `tests/test_alsh_communes_c3_ui_contract.py`

Les migrations et les moteurs C1/C2 sont synchronisés **à empreinte identique** entre `main` et la branche `wx` ; aucune fusion globale de branche n'a été effectuée.
