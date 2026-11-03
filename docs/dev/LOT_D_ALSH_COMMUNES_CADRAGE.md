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

## État détaillé et nominatif de fréquentation par enfant

**Exigence métier complémentaire du 03/11/2026 :** pouvoir fournir à chaque commune, en pièce justificative de sa situation annuelle, **la liste nominative et datée des fréquentations de ses enfants**. Ce n'est ni une nouvelle activité, ni une nouvelle réservation : cet état lit les `consommations` existantes de Noethys.

L'écran **Facturation → Situation des communes (ALSH)** proposera trois niveaux du **même calcul** :

1. **Synthèse communale** : période, commune, site(s), enfants distincts **ayant résidé dans cette commune pendant les jours concernés**, journées et demi-journées réellement réalisées, équivalents journées-enfants retenus par la convention, montants, acomptes et solde. Un même enfant peut figurer dans plusieurs synthèses communales de la même année ; la somme des enfants distincts par commune n'est donc pas nécessairement le nombre d'enfants distincts global.
2. **Récapitulatif par enfant** : nom/prénom, identifiant interne de traçabilité, **adresse complète du domicile retenu** (numéro et voie, complément éventuel, code postal, commune, pays si nécessaire), commune de rattachement, **dates de validité du domicile**, site(s), nombre de journées complètes, demi-journées, équivalents-journées éligibles et montant de participation attribuable. Une ligne par **enfant × commune × période de résidence × périmètre contractuel** ; si l'enfant revient dans une commune au cours de l'année, conserver chaque période distincte et pouvoir les regrouper pour le total de cette commune. Total strictement égal à la synthèse.
3. **Annexe détaillée datée** : une ligne par enfant, **adresse complète du domicile applicable à la date**, date de fréquentation, centre ALSH, activité/groupe, unité (journée, matin, après-midi, etc.), état réel (présent, absence, annulation, etc.), quantité source, équivalent-journée retenu, éligibilité communale, éventuel motif d'exclusion et référence `IDconso`. Permet de justifier chaque total, de voir une journée en détail et de répondre à une contestation.

## Attribution temporelle : déménagements successifs et partage entre communes

**Règle métier confirmée le 03/11/2026 : un enfant peut être rattaché à plusieurs communes pendant une même année.** Ce n'est pas un doublon : chacune participe **uniquement aux présences éligibles comprises dans ses périodes de résidence**, selon sa convention et son tarif applicables à ces dates.

- Constituer, pour chaque enfant (`IDindividu`), une **chronologie de domiciles** : adresse complète, commune, `date_debut` incluse, `date_fin` exclue (ou période ouverte), origine de l'information, date/acteur de validation. Plusieurs déménagements, y compris un retour dans une commune déjà quittée, sont permis.
- Attribuer chaque consommation ALSH effective à **une seule commune de domicile valide le jour de sa présence**. En cas de dates contradictoires, de trou dans l'historique, de résidence alternée non arbitrée ou de déménagement le jour même sans date certaine : marquer **À vérifier / non liquidable**, sans choisir automatiquement la commune actuelle ou celle du payeur.
- Un changement de commune **ne transfère pas rétroactivement** les journées déjà réalisées. Lorsqu'une situation est arrêtée, figer chaque ligne `IDconso` avec l'`IDindividu`, la date, l'adresse complète, la commune retenue, la convention et le tarif appliqué. Une correction ultérieure nécessite une révision contrôlée, pas un remplacement silencieux.
- **Conservation** : la table Noethys `individus` expose actuellement `rue_resid`, `cp_resid`, `ville_resid` et `adresse_auto`, mais **pas de dates d'effet suffisantes pour reconstituer automatiquement les anciens domiciles**. Le module devra donc conserver un historique de domiciliation daté, collecter les preuves des changements antérieurs disponibles et soumettre les périodes incertaines à validation. Ne jamais déduire les dates de déménagement de la seule adresse actuelle.
- Vérifier les invariants : **pour une journée/unité éligible d'un enfant, au plus une commune débitrice** ; la somme des journées-enfants sur toutes les communes est égale au total global éligible, sans duplication ni perte ; le nombre d'enfants distincts global est calculé séparément des comptes par commune. Un changement d'adresse n'impose aucune nouvelle inscription ni aucune nouvelle activité Noethys.

**Exemple fictif :** même enfant, 12 journées éligibles pendant sa résidence à Bais de janvier à mars, 18 journées pendant sa résidence à Moutiers d'avril à août, puis 9 à La Guerche de septembre à décembre. Les trois annexes mentionnent **le même enfant**, mais chacune contient uniquement ses journées et son **adresse de la période correspondante**. Les participations sont calculées séparément aux trois tarifs contractuels, et le total intercommunal est de **39 journées-enfants**.

**Statut :** règle de calcul et conservation historique à **implémenter et tester**, sans création automatique de données de résidence supposées et sans modification de la base MAD.

**Filtres** : commune, année ou dates libres, site(s), activité/groupe, éventuellement uniquement les présences éligibles ou la totalité des lignes annotées. Prévoir recherche d'un enfant, tri par nom ou date et ouverture du détail depuis le récapitulatif.

**Export** : PDF imprimable (synthèse et annexe nominative) et tableur Excel ou CSV pour les vérifications. L'édition doit afficher la commune, la période, la date d'édition, le site et les règles de calcul utilisées ; les totaux de l'export doivent correspondre à ceux visibles à l'écran. Un export sans noms doit être disponible pour les bilans statistiques.

**Calculs et intégrité** :
- La **présence effective** et la **facturation familiale** sont deux notions distinctes : une prestation payée ne prouve pas une présence et n'est pas automatiquement éligible à la participation communale.
- Les deux demi-journées d'un même enfant le même jour ne doivent pas créer deux journées complètes ; les repas, garderies et unités superposées ne doivent jamais être additionnés comme des journées ALSH. La conversion en journée-enfant dépend des termes de la convention.
- Dédupliquer par `IDconso` et contrôler les chevauchements enfant/date/site/unité ; mettre en évidence les anomalies au lieu de masquer les cas ambigus.
- **Adresse complète et commune du domicile de l'enfant** : contrôler la résidence applicable à chaque période (numéro, rue, complément, code postal, commune, pays si nécessaire). Ne pas utiliser par défaut l'adresse de facturation ou celle du payeur. Si plusieurs responsables ont des domiciles distincts, si l'enfant est en résidence alternée, ou si l'adresse est absente/incomplète, signaler le cas pour validation humaine sans affectation automatique à une commune. Conserver dans la situation validée **l'adresse complète effectivement retenue**, sa période d'application, la commune et la convention, afin qu'un déménagement ultérieur ne réécrive pas les justificatifs déjà arrêtés.
- Une situation finalisée garde une **trace des consommations sources et des critères** ; une correction crée une révision explicite, jamais une modification silencieuse des pièces transmises.

**Confidentialité** : annexe nominative et **adresses complètes** accessibles aux personnels habilités et exportées uniquement pour la commune concernée et le besoin justifié par la convention. Limiter les données transmises à l'identité, au domicile retenu et aux présences nécessaires (pas de PAI, données médicales, téléphones, courriels, autres coordonnées des responsables ni détails financiers familiaux), permettre l'export agrégé sans identité et sans adresse, et journaliser les éditions nominatives.

**Statut** : spécification validée comme besoin, **non implémentée**. Recette requise sur copie ALSH représentative : rapprochement des trois niveaux, plusieurs centres, demi-journées, annulations, absences, enfants de communes différentes, multi-residence, changement d'adresse et écart de total. Aucune écriture sur MAD ou la production.

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
