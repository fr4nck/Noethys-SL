# Recadrage du Lot D : conventions ALSH et participation des communes


## Classification dans la fiche famille Noethys (decision metier du 03/11/2026)

La table `familles` est utilisee comme fiche de reference d'une **entite de dossier** :
famille, ecole, association, association sportive, commune/collectivite,
institution/organisme public, entreprise/organisme prive ou autre entite.
Ce classement est **fonctionnel**, independant des classifications fiscales
et du referentiel comptable Helios.

Un champ facultatif `familles.type_structure` est propose dans l'onglet
**Divers** de la fiche famille. `NULL` signifie `Famille / particulier`.
Aucune nouvelle famille, aucun nouveau tiers comptable, aucun compte payeur
n'est cree : identifiants, activites, inscriptions, reservations, consommations,
prestations et factures restent associes aux memes dossiers.

Le choix est **desactive** sur une base non migree. La migration SQL
SQLite/MySQL est a effectuer explicitement sur copie sauvegardee, puis
apres qualification ; elle n'est pas appliquee automatiquement a MAD.
Un type inconnu est preserve (selection desactivee), jamais remplace.

Fichiers :
- `noethys/Utils/UTILS_Type_structure.py` (codes et libelles).
- `noethys/Dlg/DLG_Famille_divers.py` (choix dans la fiche existante).
- `noethys/Data/DATA_Tables.py` (schema des nouvelles bases).
- `noethys/Data/Migrations/familles_type_structure_{sqlite,mysql57}.sql` (mise a jour facultative).
- `tests/test_type_structure_familles.py` (tests isoles).



## Séances sportives : s'appuyer sur Noethys et sur la base MAD

**Précision métier du 03/11/2026 :** les séances de sport ne justifient pas la création d'un moteur de programmation distinct. La base MAD utilise déjà les activités « Encadrements sportifs adultes », « Encadrements sportifs enfants » et « Encadrements sportifs scolaires ». La chaîne de référence est **activité Noethys → groupes/inscriptions → réservations/consommations → prestations/tarifs → facturation existante**.

Le code historique `noethys/Utils/UTILS_Convention_champs.py` récupère déjà les données de planning via les consommations/réservations et analyse les tarifs depuis les prestations ; `noethys/Dlg/DLG_Generation_convention.py` prépare les conventions et exploite ce moteur. Ces mécanismes doivent être la source unique pour les annexes et les calculs des conventions sportives.

Le prototype D3-D4 (tables `partenaires_programmations` et `partenaires_interventions`) **n'est pas à intégrer pour les séances sportives** : il ferait doublon avec les activités et réservations Noethys. Il est encore présent dans `main` comme prototype non raccordé ; examiner ses autres usages et dépendances avant toute suppression ciblée. **Ne pas migrer les données MAD** dans ce prototype.

Pour les collectivités, le besoin restant est le suivi financier des **conventions ALSH** à partir des consommations réelles, des règles d'éligibilité et des acomptes contractuels, en conservant le module de facturation Noethys. Ce besoin est indépendant du planning des séances sportives.


**Décision du 03/11/2026.** Le registre parallèle de facturation D5-D7 est retiré du dépôt après vérification du besoin de facturation des conventions ALSH aux communes. Cette suppression concerne le **code et les migrations non déployées**, et ne supprime aucune donnée. Les mécanismes de facturation historiques de Noethys restent inchangés.

## Pourquoi D5-D7 ne conviennent pas au besoin communal

- D5 calcule des **interventions d'éducateurs** (minutes effectives × tarif horaire, ou nombre de séances) et produit des bordereaux d'interventions. Il ne lit pas les **consommations ALSH par enfant**.
- D6 crée une nouvelle numérotation et un registre « factures partenaires ». D7 fabrique un Word lié à ce registre. Cela duplique le module de facturation existant et ne résout pas le calcul d'une participation communale.
- Les contrôles intéressants (montants décimaux exacts, version contractuelle datée, empreinte de validation, traçabilité et interdiction de doubler une ligne) seront **réimplémentés dans le bon flux**, sans conserver un modèle financier erroné.

## Flux métier visé — « Facturation → Situation des communes (ALSH) »

1. Choisir la **commune conventionnée**, le **site ALSH**, la période et la **version signée de convention**. Pour les conventions de collectivités, D1/D2 peuvent fournir l'annuaire, les contacts et l'historique contractuel ; aucun lien automatique avec \`compta_tiers\` ou \`comptes_payeurs\`.
2. Lire les **consommations / fréquentations réelles de Noethys**, et non les prestations ou règlements familiaux. Distinguer présents, absences injustifiées (prises en compte uniquement si la convention le permet), absences justifiées, annulations, refus et séances de garderie. Le fait de facturer une absence à la famille **ne la rend pas** automatiquement éligible à la participation de la commune.
3. Appliquer les **tarifs datés de la convention** à chaque journée-enfant éligible, avec calcul en \`Decimal\` à deux décimales. Aucun coefficient CAF inventé, aucun repas ou créneau compté deux fois.
4. Tenir un registre de **situation annuelle** : nombre de journées-enfants, montant conventionnel, acomptes réellement appelés/reçus, solde à régulariser, références documentaires et justificatifs. Ne jamais imputer automatiquement les acomptes aux factures des familles.
5. Produire une **situation contrôlable** (CSV, export et état imprimable), puis, seulement après l'audit d'intégration, utiliser **le module de facturation existant** pour l'émission/numérotation et l'édition de la facture destinée à la commune. Si l'architecture historique ne sait pas facturer un tiers sans compte familial, identifier et corriger ce point : **ne jamais créer une fausse famille** ni un second registre de factures.

## Paramètres conventionnels à qualifier

Les valeurs de travail recueillies précédemment sont **11,54 € par journée-enfant pour l'ALSH classique 2025-2026** et **19,55 € pour l'ALSH Ados Bais 2024-2026**. Elles ne sont **ni généralisables à tous les sites** ni automatiquement reconductibles pour 2026-2027 ; seule une convention applicable signée fait foi.

Pour les conventions ALSH classiques évoquées, les acomptes sont prévus en **mars, juin et septembre**, pour un total représentant **75 % de la participation de l'année précédente**, puis un solde fondé sur la fréquentation effectivement éligible. Ne pas supposer une répartition égale des acomptes sans clause le confirmant.

Sites/groupes à distinguer selon les conventions : **ALSH Bais, Moutiers, La Guerche**, et **ALSH Ados Bais / Club Ados** ; les conditions d'éligibilité communale doivent être définies par site, résidence et période, et vérifiées par rapport aux actes signés.

**Association loi 1901 : aucune gestion, déduction, ventilation ou calcul de TVA dans ce flux**, selon le fonctionnement déclaré par Pêle-Mêle Sports et Loisirs. Ne pas inventer une mention fiscale légale sur les éditions.

## Périmètre du nettoyage

- **Retirés** : D5 (moteur de bordereaux d'interventions), D6 (registre de factures parallèle), D7 (édition Word dépendante du registre), leurs deux migrations respectives D5/D6, leurs tests et documentations obsolètes.
- **Conservés** : D1 annuaire partenaires, D2 conventions et tarifs historisés, D3-D4 planning/interventions ; les protections transactionnelles MySQL ajoutées à D1-D4 et leurs tests sont conservés.
- **Nettoyé** : l'ancien verrou D5 dans D3-D4 est supprimé. Les tests MySQL simulés et les tests SQL statiques restant utiles sont renommés hors du namespace D7.
- **Historique Git conservé** : ce recadrage n'efface pas les anciens commits et n'applique aucune migration inverse. Si des tables D5/D6 ont été créées manuellement sur une base, elles doivent faire l'objet d'un inventaire séparé avant toute opération sur la base.

## Barrières avant mise en service

Audit de la convention signée par commune, requêtes réelles de consommations, rapprochement de plusieurs sites et catégories, validation sur copies anonymisées Bais et La Guerche, droits, non-régression de la facturation familiale, puis qualification SQL (dont MySQL 5.7) et UI wx/Qt. **La situation communale n'est pas encore implémentée ni déployée.**
