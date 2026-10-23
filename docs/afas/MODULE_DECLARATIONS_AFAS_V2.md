# Module « Déclarations AFAS » (V2) — ALSH périscolaire et extrascolaire

Statut : développé sur `main`, **non intégré à `wx` / RC9**, en attente de recette Windows et des validations listées ci-dessous. Aucun envoi automatique à la Caf ; aucune compatibilité d'import AFAS n'est annoncée (format officiel non fourni ni testé).

## Accès

Menu **Consommations → Déclarations AFAS**. Le module est indépendant de l'état global ; le bouton AFAS V1 de l'état global n'est pas réactivé.

## Architecture

| Module | Rôle | wx / base |
|---|---|---|
| `Utils/UTILS_AFAS2_Conventions.py` | Règles des quatre conventions 2025-2027, validité, sources (article, page) | aucun |
| `Utils/UTILS_AFAS2_Calendrier.py` | Mode d'accueil d'une date depuis la table `vacances` ; statuts | base pour `ChargerCalendrier` seulement |
| `Utils/UTILS_AFAS2_Referentiel.py` | Matrice des sites ALSH, lien site → groupe Noethys vérifié, équipement, Moutiers, séjours qualifiés | base pour la persistance seulement |
| `Utils/UTILS_AFAS2_Calcul.py` | Moteur : heures conventionnelles, physiques, facturées (option 2), séjours, AEEH, garderies, anomalies | aucun |
| `Utils/UTILS_AFAS2_Donnees.py` | Lecture des consommations, ouvertures, unités, AEEH par couples exacts | base |
| `Utils/UTILS_AFAS2_Presets.py` | Presets permanents, validation, persistance, duplication, migration | base pour la persistance seulement |
| `Utils/UTILS_AFAS2_Declaration.py` | Phases, prévision, validabilité, empreintes, historique, exports | via les modules ci-dessus |
| `Dlg/DLG_AFAS2_Declarations.py` | Interface wxPython | wx |

Le moteur V1 (`UTILS_AFAS*.py`) n'est pas utilisé par le calcul V2 ; seul `UTILS_AFAS.GetCycleAFAS` / `EstimerPeriode` est réutilisé pour les phases.

## Paramétrage initial (une fois)

1. **Référentiel…** (format 2) : relier chaque site (Bais +6 ans, Bais -6 ans, Moutiers, La Guerche-de-Bretagne, Minicamps 6/8, Minicamps 8/10) à son groupe Noethys. Le nom du groupe est mémorisé et revérifié à chaque ouverture (groupe supprimé, renommé, permuté ou d'une autre activité : refus). Choisir l'équipement des minicamps et **référencer le justificatif** (déclaration de l'accueil désignant l'équipement organisateur). Confirmer le rattachement de Moutiers **et référencer le formulaire d'implantation**. Saisir, par année scolaire, les **samedis avec école** (« 2026 : 2026-11-28 » ou « 2026 : aucun »). Enregistrer les séjours qualifiés (dates, nuits, conditions) et **qualifier les régularisations** signalées par le calcul (consommations dont elles annulent la facturation, ou aucune, avec la pièce justificative). Un référentiel format 1 est migré sans perte à la lecture (calendrier des samedis et justificatifs vides : à compléter).
2. **Preset** (format 2) : nom (sans année ni phase), mode, équipement, sites, **classement explicite de chaque unité** (accueil, journée, demi-journée, garderie matin/soir, repas, séjour, annexe, exclue, à qualifier) et **plage réellement organisée** de chaque unité à plage horaire (HH:MM-HH:MM ; le bouton « Reprendre les horaires Noethys » ne remplit que les plages vides, après vérification), statuts retenus pour le réalisé (présent uniquement) et pour le facturé (présent, absence justifiée, absence injustifiée — jamais la réservation), repas méridien, garderies. Un preset format 1 est ouvert comme brouillon à compléter (plages, samedis datés si la case était cochée, statuts retirés), puis enregistré au format 2 sous le même identifiant.

## Calcul

- **Calendrier** : une année scolaire n'est connue que si ses cinq périodes de vacances sont saisies ; les samedis hors vacances sont classés par le calendrier daté du référentiel.
- **Périscolaire** (Bais, La Guerche-Moutiers) : pour chaque enfant et chaque jour scolaire, union des plages déclarées des unités où il est présent (plage Noethys identique exigée), plafond 9 h ; présence physique (horaires de la consommation) restituée séparément, jamais substituée à la plage ; heures facturées non applicables.
- **Extrascolaire** (option n°2) : réalisé = présence effective ; facturé = journées et demi-journées justifiées par une prestation (une unité, un jour, un enfant) figurant sur une facture non annulée et non annulée par une régularisation qualifiée, converties selon l'amplitude d'ouverture **continue du site de l'enfant** ce jour-là (8 h / 4 h, ou amplitude et moitié) ; séjours qualifiés : 10 h par journée réalisée, intégrées aux heures réalisées et facturées (« dont séjours »), jamais cumulées avec une journée d'accueil.
- **AEEH** : jour par jour selon `aeeh_periodes` ; complément inclusif brut (contrôle) et arrondi à l'heure supérieure par jour (hypothèse, jamais retenue automatiquement).
- **Garderies** : matin, soir, total, non ajoutés aux heures CAF sauf choix explicite.

## Phases

| Phase | Réalisé | Prévision |
|---|---|---|
| Prévisionnel annuel | — | 01/01 – 31/12 |
| Actualisation de juin | 01/01 – 30/06 | 01/07 – 31/12 |
| Actualisation de septembre | 01/01 – 30/09 | 01/10 – 31/12 |
| Réel annuel | 01/01 – 31/12 | — |

Prévision : même période de N-1 ajustée aux jours d'ouverture programmés (refusée si l'historique est vide ou comporte des anomalies bloquantes) ou saisie manuelle contrôlée.

## Anomalies

Chaque anomalie indique date, individu, IDconso, activité, groupe, site, unité, nature et conséquence. Bloquantes : calendrier de vacances incomplet (périodes manquantes nommées), samedi hors vacances sans calendrier daté, samedi avec école pendant des vacances, jour sans ouverture, statut inconnu ou vide, pointage en attente sur une date passée, unité non classée ou à qualifier, plage non déclarée ou différente des horaires Noethys, doublon, même enfant sur deux sites, facturation supérieure à une journée, facturation indéterminable (prestation négative, forfait, quantité, autre enfant, prestation partagée ou couvrant deux unités), régularisation négative non qualifiée, journée facturée sur deux sites, ouverture discontinue, amplitude absente ou inférieure à 2 h, séjour non qualifié, séjour et accueil le même jour, unité horaire facturée en extrascolaire, présence sans horaires. Non bloquantes (contrôle) : dimanche hors séjour, amplitudes différentes selon les sites. Les données ne sont jamais corrigées par le module.

## Validabilité et exports

Une déclaration est **validable** si aucune anomalie n'est bloquante, si une convention couvre l'année entière, si la période réalisée est terminée, si Moutiers est confirmé avec son formulaire d'implantation référencé (quand il est déclaré), si chaque minicamp a un équipement justifié et si elle ne comporte aucune heure de séjour tant que la rubrique AFAS des séjours n'est pas confirmée par la Caf. L'export déclaratif (synthèse, détail, jours, anomalies, instantané JSON) n'est possible que pour une déclaration validable ; il est archivé dans l'historique avec ses empreintes. L'export de contrôle est toujours possible.

## Correspondance des tests d'acceptation

| N° | Scénario | Test |
|---|---|---|
| 1 | Bais péri, plage 1 h 15 | `test_afas2_calcul.PeriscolaireTests.test_01_bais_plage_1h15` |
| 2 | Plusieurs plages, 9 h max | `test_02_plusieurs_plages_plafond_9h`, `test_02b_trois_plages_additionnees` |
| 3 | La Guerche péri | `test_03_la_guerche_meme_regle` |
| 4-7 | Option 2 (9 h, 6 h ; journée, demi-journée) | `ExtrascolaireTests.test_04` … `test_07`, `test_afas2_conventions.ExtrascolaireOption2Tests` |
| 8 | Absence facturée sans présence | `test_08_absence_facturee_sans_presence` |
| 9 | Réservation non pointée | `test_09_reservation_non_pointee_passee_bloquante`, `test_09b` |
| 10-12 | Mercredi scolaire, mercredi de vacances, samedi sans école | `test_10`, `test_11`, `test_11b`, `test_12`, `test_afas2_calendrier.ModeDateTests` |
| 13-15 | Dimanche de séjour, séjour 10 h, séjour non admissible | `SejoursTests.test_13`, `test_14`, `test_15`, `test_afas2_referentiel_donnees.SejoursTests` |
| 16 | Garderies sans double comptage | `test_16_garderies_separees_sans_double_comptage`, `test_16b` |
| 17 | Repas méridien | `test_17_repas_dans_une_plage_deja_retenue`, `test_17b` |
| 18 | Sortie facturée en supplément | `test_18_sortie_supplement_sans_heures_ni_suppression` |
| 19 | Deux consommations simultanées | `AnomaliesTests.test_19`, `test_19b` |
| 20 | Droit AEEH ouvert ou fermé en cours d'année | `AEEHTests.test_20_*` |
| 21 | Preset réutilisé de 2025 à 2027 | `test_afas2_declaration.PhasesTests.test_21_meme_preset_de_2025_a_2027` |
| 22 | Preset pour les quatre phases | `test_22_meme_preset_pour_les_quatre_phases` |
| 23 | Ni année ni phase dans le preset | `test_afas2_presets.ValidationTests.test_23_*`, `test_afas2_interface.test_annee_et_phase_jamais_dans_le_preset` |
| 24 | Persistance après redémarrage | `test_afas2_presets.PersistanceTests.test_24_*` (relecture par un autre processus), `test_afas2_interface.test_preset_rouvert_identique_apres_fermeture` |
| 25 | Groupe supprimé ou renommé | `test_afas2_referentiel_donnees.ReferentielTests.test_25_*` |
| 26 | Calendrier absent | `AnomaliesTests.test_26_calendrier_absent_bloquant`, `test_afas2_calendrier` |
| 27 | Bais / La Guerche mélangés | `test_afas2_presets.test_27_*`, `test_afas2_declaration.test_site_non_relie_ou_autre_equipement` |
| 28 | Moutiers sans rattachement confirmé | `test_afas2_referentiel_donnees.test_28_*`, `test_afas2_declaration.test_28_*` |
| 29 | Export avec empreinte et instantané | `test_afas2_declaration.ExportsEtHistoriqueTests.test_29_*` |
| 30 | Non-régression de l'état global | suites historiques inchangées ; `test_afas2_interface.test_bouton_afas_v1_non_reactive` |

## Cas contradictoires convertis en tests permanents (décisions du 23/10/2026)

| Cas | Résultat attendu | Test |
|---|---|---|
| Une période de vacances + l'été seulement | année inconnue, périodes manquantes nommées | `test_afas2_calendrier.test_une_periode_et_l_ete_ne_suffisent_pas`, `test_26b_*` |
| Samedi sans calendrier daté / samedi avec école daté / ancien booléen | bloquant / périscolaire / ignoré | `test_afas2_calcul.SamedisTests` |
| Horaires Noethys modifiés après déclaration de la plage | bloquant | `PlagesDeclareesTests.test_horaires_noethys_modifies_bloquants` |
| Pointage plus long que la plage | plage seule retenue | `PlagesDeclareesTests.test_duree_de_pointage_jamais_substituee_a_la_plage` |
| Matin et après-midi ouverts sans plage intermédiaire | ouverture discontinue bloquante | `AmplitudeTests.test_ouverture_discontinue_bloquante` |
| Matin ouvert sur un site, après-midi sur un autre | amplitudes non combinées | `AmplitudeTests.test_implantations_jamais_combinees` |
| Amplitudes différentes selon les sites | chaque site valorisé avec la sienne, signalement unique | `AmplitudeTests.test_amplitudes_differentes_par_site` |
| Avoir non rattaché, avoir familial, avoir d'une autre famille | bloquant, bloquant, ignoré | `FacturationTests.test_regularisation_*`, `test_avoir_familial_bloquant` |
| Régularisation qualifiée (annulant ou non) | journée retirée du facturé / conservée | `FacturationTests.test_regularisation_qualifiee_*` |
| Remise, montant nul ou variable | unité conservée, heures indépendantes du montant | `FacturationTests.test_remise_*`, `test_montant_jamais_converti_en_heures` |
| Forfait, quantité 2, prestation d'un autre enfant, prestation sur deux jours, une prestation pour deux demi-journées | bloquant | `FacturationTests.test_quantite_indeterminable_bloquante`, `test_prestation_partagee_*`, `ExtrascolaireTests.test_prestation_couvrant_deux_demi_journees_indeterminable` |
| Réservation ou absence dans les statuts du réalisé ; réservation dans le facturé | refusé | `test_afas2_calendrier.test_realise_*`, `test_facture_*`, `ContexteTests` |
| Séjour + journée le même jour ; séjour seul | bloquant ; 10 h réalisées et facturées, déclaration non validable (rubrique) | `SejoursTests`, `test_afas2_declaration.test_sejours_integres_mais_rubrique_non_confirmee` |
| Moutiers confirmé sans formulaire ; minicamp sans justificatif | non validable | `test_28_*`, `test_minicamp_sans_justificatif_non_validable` |

## Qualification

- **SQLite** (CI rapide) et **MySQL 5.7.44** (workflow manuel « Noethys SL - AFAS V2 MySQL fictif ») : `tests/test_afas2_qualification_bases.py` sur le jeu fictif `tests/afas2_base_fictive.py`, résultats attendus calculés à la main, comparaison MySQL / SQLite (indicateurs, anomalies, jours, empreinte), persistance des presets, de l'historique et d'un texte accentué de 27 000 caractères.
- **Recette visuelle Windows** et **rapprochement chiffré** sur extrait pseudonymisé : `docs/recette/RECETTE_AFAS2_WINDOWS.md`, outils `tests/recette_afas2.py` (`peupler`, `extraire`, `rapprocher`).

## Décisions et pièces encore attendues

Voir `TRACABILITE_CONVENTIONS_2025_2027.md` (décisions du 23/10/2026, pièces manquantes). Restent à obtenir : formulaires d'implantation (Moutiers, minicamps), confirmation Caf de la rubrique AFAS des séjours et de l'arrondi du complément inclusif, grilles tarifaires, addenda.
