# AFAS V2 — traçabilité des règles conventionnelles ALSH 2025-2027

Ce document relie chaque règle implémentée dans `noethys/Utils/UTILS_AFAS2_*.py` à la convention d'objectifs et de financement (Caf d'Ille-et-Vilaine / association Pêle-Mêle Sports et Loisirs) dont elle provient. Les quatre conventions ont été lues intégralement à partir des PDF numérisés fournis le 23/10/2026. « p. PDF » désigne la page du fichier, suivie de la pagination imprimée.

## Conventions fournies

| Code interne | Fichier | Structure (couverture) | Mode | Durée (art. 9) | Signature Caf | Bonus Ctg (art. 3) |
|---|---|---|---|---|---|---|
| `PERI_BAIS_2025_2027` | PERI_BAIS_.pdf (21 p.) | ALSH Peri Ass Bais | Périscolaire | 01/01/2025 – 31/12/2027 (p. PDF 18) | 06/03/2025 | 14 115 h ; 0,15 €/h |
| `PERI_LA_GUERCHE_MOUTIERS_2025_2027` | PERI_LA_GUERCHE.pdf (21 p.) | ALSH périscolaire La Guerche-Moutiers | Périscolaire | 01/01/2025 – 31/12/2027 (p. PDF 18) | 06/06/2025 | 19 200 h ; 0,60 €/h |
| `EXTRA_BAIS_2025_2027` | EXTRA_BAIS.pdf (20 p.) | ALSH Extra Ass Bais | Extrascolaire | 01/01/2025 – 31/12/2027 (p. PDF 18) | 03/03/2025 | 14 690 h ; 0,15 €/h |
| `EXTRA_LA_GUERCHE_MOUTIERS_2025_2027` | EXTRA_LA_GUERCHE.pdf (20 p.) | ALSH Extrascolaire La Guerche-Moutiers | Extrascolaire | 01/01/2025 – 31/12/2027 (p. PDF 18) | 06/03/2025 | 23 111 h ; 0,60 €/h |

Les volumes Ctg sont des données contractuelles de l'équipement : ils ne sont jamais comparés ni mêlés aux heures individuelles calculées. Les copies fournies ne portent pas la signature du gestionnaire (champ « à compléter »).

## Règles implémentées

| Règle | Implémentation | Source |
|---|---|---|
| Périscolaire = semaines où les enfants vont à l'école, sauf samedis sans école et dimanches | `UTILS_AFAS2_Calendrier.ModeDate` (calendrier complet + samedis avec école datés) | PERI Bais et PERI La Guerche, art. 1.1, p. PDF 4 (5/19) |
| Présence périscolaire = durée totale de la plage d'accueil dès lors que l'enfant y a été présent | `UTILS_AFAS2_Conventions.PresencePeriscolaireJour` (union des plages) | PERI, art. 2-2, p. PDF 7 (8/19) |
| Plafond 9 h par jour et par enfant | `PLAFOND_PERISCOLAIRE_JOUR` | PERI, art. 2-2, p. PDF 7 (8/19) |
| Temps de repas de la pause méridienne financé intégralement | option du preset `inclure_repas_meridien` (vrai par défaut en périscolaire), sans double comptage grâce à l'union des plages | PERI, art. 1.5, p. PDF 6 (7/19) |
| Pas d'heures facturées en périscolaire (actes = heures de présence) | indicateur « Heures facturées CAF » marqué non applicable | PERI, art. 2-2 et 6.3, p. PDF 7 et 16 |
| Extrascolaire = vacances scolaires, samedis sans école, dimanche uniquement pour les séjours ≤ 5 nuits / 6 jours | `UTILS_AFAS2_Calendrier.ModeDate` | EXTRA Bais et EXTRA La Guerche, art. 1.1, p. PDF 4 (5/21) |
| Actes réalisés = heures de présence effective ; actes facturés = heures facturées aux familles | `UTILS_AFAS2_Calcul` (réalisé physique, facturé option 2) | EXTRA, art. 2-2, p. PDF 6 (7/20) |
| Option n°2 retenue : journée = 8 h et demi-journée = 4 h si amplitude ≥ 8 h ; sinon journée = amplitude et demi-journée = moitié | `UTILS_AFAS2_Conventions.DureeJourneeOption2` | EXTRA, tableau art. 2-2 p. PDF 7 (8/20) ; encadré p. PDF 8 (9/21) |
| Durée minimale de 2 h par journée de fonctionnement | anomalie bloquante si amplitude < 2 h | EXTRA, art. 2-1, p. PDF 5 (6/20) |
| Séjours accessoires (1 à 4 nuits) et séjours de 5 nuits / 6 jours : 10 h par journée réalisée et par enfant, sous conditions | registre des séjours qualifiés (`UTILS_AFAS2_Referentiel`) + `SEJOUR_JOURNEE` | EXTRA, art. 2-1 p. PDF 6 (7/20) ; tableau séjours p. PDF 8 (9/21) |
| Complément inclusif : heure de présence effective, éventuellement arrondie à l'heure supérieure, enfants bénéficiaires de l'AEEH uniquement | indicateurs AEEH calculés jour par jour selon les périodes de droit ; arrondi fourni à part | PERI art. 1.5 p. PDF 6 ; EXTRA art. 1.3 p. PDF 5 |
| Conventions valables du 01/01/2025 au 31/12/2027, jamais étendues | `ResoudreConventionAnnee` lève `ConventionNonApplicable` hors période | art. 9 des quatre conventions |

## Décisions de la direction sur les interprétations (23/10/2026)

Les huit points que les conventions ne tranchent pas ont été arbitrés par la direction. Version des règles : `2025-2027.2`.

| # | Décision | Implémentation | Tests permanents |
|---|---|---|---|
| 1 | **Plages périscolaires** : les horaires de l'unité Noethys ne sont utilisés que s'ils correspondent aux plages réellement organisées et déclarées ; jamais déduits d'une unité quelconque ni de la durée de pointage ; plage entière si présent, plafond 9 h ; blocage si horaires absents ou incohérents. | Plage réellement organisée déclarée par unité dans le preset (`plages_declarees`, obligatoire pour accueil, journée, demi-journée, repas, garderies) et comparée à chaque calcul aux horaires Noethys (`Calculateur._preparer_unite`). | `test_afas2_calcul.PlagesDeclareesTests`, `test_afas2_presets.test_plages_declarees_obligatoires_et_coherentes` |
| 2 | **Amplitude extrascolaire** = ouverture effective ; première ouverture → dernière fermeture seulement pour une ouverture continue ; plages disjointes ou implantations différentes jamais combinées ; plages utilisées affichées ; cas ambigus signalés ; équivalences de l'option 2 strictes. | Amplitude calculée par site (couple activité-groupe) sur l'union des unités d'accueil, journée, demi-journée et repas ouvertes ; union discontinue = anomalie bloquante ; amplitudes différentes entre sites = anomalie de contrôle ; plages retenues exportées (`_jours.csv`). | `test_afas2_calcul.AmplitudeTests`, `test_deux_demi_journees_equivalent_journee` |
| 3 | **Facturation** : facture non annulée = première preuve, insuffisante si un avoir ou une régularisation annule l'unité ; une remise ne retire pas l'unité ; jamais d'heures déduites d'un montant ; chaque journée ou demi-journée justifiée par la facturation ; blocage si la quantité est indéterminable. | Justification « journée P<prestation> F<facture> » par jour ; blocage : prestation négative, forfait, quantité ≠ 1, prestation d'un autre enfant ou partagée entre jours/enfants, prestation couvrant deux unités journée/demi ; prestations négatives non rattachées (avoirs, régularisations) recherchées jusqu'à 3 mois après la période et bloquantes tant qu'elles ne sont pas qualifiées dans le référentiel (consommations annulées ou aucune, pièce justificative). | `test_afas2_calcul.FacturationTests`, `test_afas2_declaration.test_regularisations_recherchees_apres_la_periode`, `test_afas2_referentiel_donnees.test_regularisations_non_rattachees` |
| 4 | **Samedis** : samedis sans école = extrascolaire ; samedis avec école identifiés par un calendrier daté ; pas de booléen permanent dans le preset. | Preset format 2 : règle générique `regle_samedis = calendrier_date` ; dates tenues dans le référentiel par année scolaire (liste éventuellement vide) ; année non saisie = samedi hors vacances bloquant ; migration des presets format 1 (case cochée = dates à saisir). | `test_afas2_calendrier.ModeDateTests`, `test_afas2_calcul.SamedisTests`, `test_afas2_presets.MigrationTests` |
| 5 | **Statuts** : réalisé = présent uniquement (présence attestée) ; facturé = présent, absence justifiée ou injustifiée quand une journée/demi-journée admissible figure réellement sur la facture ; réservation jamais comptée ; une absence facturée ne devient jamais une présence. | `ETATS_REALISE_ADMIS = ("present",)`, `ETATS_FACTURE_ADMIS` sans réservation ; contrôlés par le preset et le moteur ; interface limitée aux statuts admissibles. | `test_afas2_calendrier.test_realise_presence_attestee_uniquement`, `FacturationTests.test_absence_facturee_jamais_presence` |
| 6 | **AEEH** : présence brute (droit vérifié par date) et heures arrondies conservées ; aucun indicateur arrondi retenu automatiquement tant que la modalité Caf n'est pas confirmée. | Indicateur arrondi qualifié « hypothèse » dans la synthèse ; mention explicite dans l'export déclaratif. | `test_afas2_declaration.test_nature_des_indicateurs_dans_la_synthese` |
| 7 | **Séjours** : 1 à 4 nuits accessoires, 5 nuits / 6 jours sous conditions ; 10 h par journée réalisée et par enfant ; indicateur spécifique conservé et intégré aux actes ouvrant droit sans double comptage ; rubrique AFAS inconnue = seule la validation déclarative est bloquée, l'export de contrôle reste possible. | Heures de séjour ajoutées aux heures réalisées et facturées (« dont séjours ») ; séjour et accueil le même jour bloquant ; `RUBRIQUE_SEJOURS_CONFIRMEE = False` rend non validable toute déclaration comportant des heures de séjour. | `SejoursTests.test_14_*`, `test_sejour_et_accueil_meme_jour_sans_double_comptage`, `test_afas2_declaration.test_sejours_integres_mais_rubrique_non_confirmee` |
| 8 | **Moutiers** : « La Guerche-Moutiers » retenu comme référence contractuelle provisoire, formulaire d'implantation à vérifier avant toute validation définitive. **Minicamps** : rattachement à l'équipement organisateur réellement déclaré, jamais déduit du nom du groupe ni d'une préférence. | Référentiel format 2 : justificatif (référence du formulaire d'implantation ou de la déclaration) obligatoire pour Moutiers (en plus de la confirmation) et pour chaque minicamp ; sans justificatif, le site n'est pas validable. | `test_afas2_referentiel_donnees.test_28_*`, `test_minicamp_sans_justificatif_non_validable`, `test_afas2_declaration.test_28_*` |

**Calendrier scolaire** : une année scolaire n'est couverte que si chacune des cinq périodes de vacances (Toussaint, Noël, hiver, printemps, été) est saisie dans `vacances` (fenêtres larges couvrant les trois zones, contrôle de cohérence et non règle Caf). Une période manquante n'est jamais présumée scolaire : les dates de l'année sont inconnues et bloquantes, l'anomalie nomme les périodes manquantes (`Calendrier.PeriodesManquantes`).

**Garderies** : affichées séparément (matin, soir, total) et non ajoutées aux heures CAF, sauf choix explicite du preset (inchangé).

## Pièces manquantes

- Addenda des quatre conventions (modalités de calcul « à l'appui du barème », plafond de développement Ctg, pourcentage d'écrêtement) — cités à l'art. 3.
- Formulaires des lieux d'implantation (art. 1 : « leurs lieux d'implantation désignés dans le formulaire prévu à cet effet »).
- Grilles tarifaires (preuve d'une facturation exclusivement à la journée / demi-journée en extrascolaire).
- Confirmation par la Caf de la rubrique AFAS recevant les heures de séjours et de la modalité d'arrondi du complément inclusif.
- Avenants éventuels et copies signées par le gestionnaire.
- Conventions ALSH Ados (hors périmètre de cette version).
