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

1. **Référentiel…** : relier chaque site (Bais +6 ans, Bais -6 ans, Moutiers, La Guerche-de-Bretagne, Minicamps 6/8, Minicamps 8/10) à son groupe Noethys. Le nom du groupe est mémorisé et revérifié à chaque ouverture (groupe supprimé, renommé, permuté ou d'une autre activité : refus). Choisir l'équipement des minicamps. Confirmer le rattachement de Moutiers après vérification du formulaire d'implantation. Enregistrer les séjours qualifiés (dates, nuits, conditions).
2. **Preset** : nom (sans année ni phase), mode, équipement, sites, **classement explicite de chaque unité** (accueil, journée, demi-journée, garderie matin/soir, repas, séjour, annexe, exclue, à qualifier), statuts retenus pour le réalisé (défaut : présent) et pour le facturé (défaut : présent, absence justifiée, absence injustifiée — sous réserve d'une facture non annulée), samedis avec école, repas méridien, garderies.

## Calcul

- **Périscolaire** (Bais, La Guerche-Moutiers) : pour chaque enfant et chaque jour scolaire, union des plages des unités où il est présent, plafond 9 h ; présence physique (horaires de la consommation) restituée séparément ; heures facturées non applicables.
- **Extrascolaire** (option n°2) : réalisé = présence effective ; facturé = journées et demi-journées figurant sur une facture non annulée, converties selon l'amplitude d'ouverture de l'équipement ce jour-là (8 h / 4 h, ou amplitude et moitié) ; séjours qualifiés : 10 h par journée réalisée, jamais cumulées avec l'option 2.
- **AEEH** : jour par jour selon `aeeh_periodes` ; complément inclusif brut et arrondi à l'heure supérieure par jour.
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

Chaque anomalie indique date, individu, IDconso, activité, groupe, site, unité, nature et conséquence. Bloquantes : calendrier de vacances absent, jour sans ouverture, statut inconnu ou vide, pointage en attente sur une date passée, unité non classée ou à qualifier, doublon, même enfant sur deux sites, facturation supérieure à une journée, amplitude absente ou inférieure à 2 h, séjour non qualifié, unité horaire facturée en extrascolaire, présence sans horaires. Les données ne sont jamais corrigées par le module.

## Validabilité et exports

Une déclaration est **validable** si aucune anomalie n'est bloquante, si une convention couvre l'année entière, si Moutiers est confirmé (quand il est déclaré) et si chaque minicamp a un équipement. L'export déclaratif (synthèse, détail, jours, anomalies, instantané JSON) n'est possible que pour une déclaration validable ; il est archivé dans l'historique avec ses empreintes. L'export de contrôle est toujours possible.

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

## Décisions et pièces encore attendues

Voir `TRACABILITE_CONVENTIONS_2025_2027.md` (interprétations à valider, pièces manquantes). En particulier : plages d'accueil réelles par unité, amplitude d'ouverture, traitement des absences facturées, mode d'arrondi du complément inclusif, rattachement de Moutiers et des minicamps, ventilation des heures de séjour dans la déclaration AFAS, statuts retenus.
