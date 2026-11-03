# Lot D — Gestion des partenaires : audit et contrat de développement

**État au 03/11/2026 : audit technique initial, sans déploiement ni migration.**

## 1. Périmètre

D1. Annuaire des partenaires et contacts (associations, écoles, collectivités, établissements).
D2. Conventions pluriannuelles ou saisonnières et tarifs contractuels historisés.
D3. Interventions : activité, public/groupe, lieu, éducateur, durée, état, remplacement et annulation.
D4. Programmations et exceptions calendaires, puis export de l'annexe prévisionnelle.
D5. Suivi mensuel et transmission contrôlée au moteur historique des prestations/factures.

Le Lot D concerne les **conventions de prestations avec des partenaires**. Il ne doit pas confondre celles-ci avec les conventions de financement Caf gérées par UTILS_AFAS2_Conventions.

## 2. Inventaire vérifié du code

- Le dialogue DLG_Generation_convention crée actuellement un document à partir d'une fiche Famille identifiée par IDfamille. Il est **en lecture seule pour les données métier**, les corrections de champs étant uniquement des surcharges de génération. L'impression du planning réutilise UTILS_Impression_reservations.GetDonnees et son rendu.
- UTILS_Convention_champs déduit représentants, tarifs et périodes à partir des rattachements, consommations et prestations. Un tarif ambigu est laissé à la saisie manuelle. Le modèle ne persiste **pas** une convention signée ni sa version tarifaire.
- UTILS_Convention_modeles utilise le moteur Noedoc et documents_modeles/documents_objets ; conserver ce mécanisme et la sortie Word distincte.
- DLG_Tiers / DLG_Saisie_tiers / OL_Tiers manipulent **compta_tiers**, dont la fiche est essentiellement un nom et des observations. Il s'agit du référentiel comptable historique, **pas** d'un annuaire de partenaires opérationnels.
- Les tables historiques **contrats/modeles_contrats** concernent des contrats individuels et les inscriptions ; ne pas les recycler pour les conventions partenaires.
- Les données de réservation/presence sont dans consommations, les lignes financières dans prestations, et les factures dans factures, liées aux comptes payeurs. Réutiliser les moteurs historiques, sans « seconde facturation ».

La sauvegarde Noethys du 10/09/2026 a été examinée **hors production, en lecture seule**, uniquement pour vérifier des schémas. Aucune donnée nominative, contenu de sauvegarde ni clé d'accès ne doit être commité.

## 3. Découpage des responsabilités

| Objet métier Lot D | Identifiant autonome | Référence historique facultative | Règle |
| --- | --- | --- | --- |
| Partenaire | IDpartenaire | IDfamille, IDcompte_payeur, éventuellement IDtiers comptable | Aucune fusion implicite des structures et des personnes |
| Contact partenaire | IDcontact_partenaire | Contact historique, si explicitement rapproché | Plusieurs contacts et fonctions par partenaire |
| Convention | IDconvention_partenaire | Document Noedoc / modèle Word | Version signée et clauses figées, dates, état, avenants |
| Tarif conventionnel | IDtarif_convention | Aucun tarif Noethys requis | Catégorie, période de validité, montant Decimal, provenance |
| Programmation | IDprogrammation | Activité/groupe/unité Noethys facultatifs | Créneau récurrent, dates, exceptions, site |
| Intervention | IDintervention | Consommation(s) Noethys si rapprochement vérifié | Séance prévue, tenue, annulée ou reportée ; intervenant et motif |
| Rapprochement financier | IDrapprochement | IDprestation / IDfacture existants | Un lien traçable, sans montant de facture dupliqué |

La correspondance Famille/Partenaire doit être **explicite et révocable**, et ne doit jamais dépendre d'un nom ressemblant. Ne pas traiter compta_tiers comme source maître du partenaire.

## 4. Contrat fonctionnel

1. La saisie d'une convention constitue une **définition métier persistée** ; l'impression Noedoc ou Word est un export de cette définition et non l'enregistrement de celle-ci.
2. Toute convention en vigueur garde sa propre version des tarifs et clauses. Une hausse du tarif général ou le renouvellement de saison ne modifie jamais l'historique.
3. Les créneaux récurrents génèrent des séances prévisionnelles selon le calendrier sélectionné ; vacances, jours fériés, fermetures, séances exceptionnelles et changements d'horaires sont des exceptions **explicites** et consultables.
4. Une réservation ou une séance simplement programmée ne vaut **jamais** justification d'une facture. Chaque séance candidate à la facturation comporte une décision de réalisation et de facturabilité, un tarif applicable et une durée contrôlée.
5. Une annulation comporte un motif, une origine et une décision de facturation fondée sur la convention. En cas d'ambiguïté, la décision reste à valider ; elle ne se résout pas par un tarif automatique.
6. Les remplacements ne créent pas une seconde séance facturable. Ils conservent la trace des éducateurs et l'état réel de la séance.
7. Une facture mensuelle est préparée par **lignes de prestations issues de séances validées**, puis utilise le chemin de facturation Noethys existant. La relance/reprise est idempotente : aucune prestation ou facture en double.
8. La génération d'une convention et de son annexe de programmation ne modifie ni consommations, ni prestations, ni factures, ni les rattachements familiaux.
9. Les états « prévu », « réalisé », « non facturable », « à arbitrer » et « facturé » sont distincts dans les restitutions.
10. Les coûts/heures prévisionnels et constatés sont calculés séparément ; ne jamais déduire les heures réellement faites d'un montant financier.

## 5. Proposition de stockage — non appliquée

Créer des tables **préfixées partenaires_** pour ce domaine, sans modifier au départ les 171 tables héritées : partenaires_structures, partenaires_contacts, partenaires_conventions, partenaires_tarifs, partenaires_programmations, partenaires_interventions et partenaires_rapprochements.

Précautions :
- conventions reliées à une structure, avec versions et avenants non destructifs ;
- dates et heures au format explicite, montants en DECIMAL dans le SQL neuf (pas de flottant métier) ;
- chaque programmation produit un identifiant d'occurrence stable pour empêcher les doublons en cas de régénération ;
- chaque intervention conserve le créneau prévu, le créneau effectif, un état métier, son motif/acteur/date de validation, et une référence de tarif figée ;
- rapprochements financiers dotés d'une unicité sur l'intervention et la ligne de prestation afin de rejouer une génération sans double comptage ;
- journal d'audit des changements significatifs et droit de lecture/écriture par rôle ;
- aucune suppression en cascade d'une convention avec interventions, paiements ou documents historiques ;
- migration SQL séparée, transactionnelle lorsque possible, réversible/avec sauvegarde ; d'abord sur copie jetable MySQL 5.7, jamais automatiquement sur la production.

**Ce modèle est proposé, pas encore un schéma autorisé pour migration.** Valider les intégrations réelles aux prestations et aux comptes payeurs avant de fixer les DDL.

## 6. Critères de recette avant livraison

- D1 : deux structures de même nom ne sont pas fusionnées ; annuaire multi-contact ; distinction claire du tiers comptable et du compte payeur.
- D2 : école et association utilisent des clauses/modèles distincts ; plusieurs tarifs simultanés possibles ; historique signé et avenants préservés.
- D3 : séance 1 h / 1 h 30, présence, annulation justifiée/non justifiée, remplacement et report sans double facturation.
- D4 : périodes scolaires, semaines de vacances, exceptions horaires et lieux multiples ; annexe identique au calendrier validé, sans séance inventée.
- D5 : prévisionnel/constaté différents ; aucune ligne issue d'une simple réservation ; contrôle de la provenance tarifaire ; reprise idempotente après interruption ; lien jusqu'à facture et prestation réelles.
- Compatibilité : tests existants Noedoc, Réservations, prestations, cotisations, AFAS, profils Famille, sauvegarde/restauration, conformité des branches main/wx/qt.
- Qualification requise sur un jeu fictif séparé et sous Windows avant publication d'un paquet.

## 7. Branches et arrêt de sécurité

Prévol du 03/11/2026 : main 6afe5e0, wx e6da221, qt 3b2e603. Les branches ont des travaux divergents. Les composants de conventions et de tiers consultés ont les mêmes empreintes sur les trois branches, **mais cette concordance ciblée ne prouve pas une synchronisation générale**.

Le présent lot commence sur main pour les spécifications et futur moteur commun. Adapter ultérieurement les interfaces sur wx/qt, sans fusion globale. Aucun changement en production, aucune migration, aucun packaging, aucun test Windows ni qualification de release ne sont revendiqués par ce seul audit.

**Prochain ordre de travail :** D1 schéma/migration sur copie fictive et annuaire, D2 conventions persistantes, D3-D4 séances/calendrier, D5 raccordement financier avec preuve anti-doublon.
