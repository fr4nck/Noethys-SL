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
| Périscolaire = semaines où les enfants vont à l'école, sauf samedis sans école et dimanches | `UTILS_AFAS2_Calendrier.ModeDate` | PERI Bais et PERI La Guerche, art. 1.1, p. PDF 4 (5/19) |
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

## Interprétations retenues (à valider par la direction)

Ces points ne sont pas tranchés par le texte des conventions ; le module les rend visibles et paramétrables au lieu de les décider en silence.

1. **Plage d'accueil périscolaire** : la plage retenue est la plage horaire de l'unité Noethys (`unites.heure_debut` / `heure_fin`). Une unité sans plage bloque le calcul. Les conventions ne fixent aucune plage.
2. **Amplitude d'ouverture effective (option 2)** : l'amplitude d'un jour est l'étendue (première heure d'ouverture → dernière heure de fermeture) des plages des unités d'accueil ouvertes ce jour-là (`ouvertures`) pour les groupes de l'équipement déclaré. Une journée sans ouverture ou sans plage bloque le calcul.
3. **« Figurant sur les factures »** : une consommation est facturée si sa prestation porte un `IDfacture` dont la facture n'est pas annulée. Une même prestation n'est comptée qu'une fois. Le statut retenu pour le facturé est un second filtre configurable.
4. **Samedis** : un samedi hors vacances est traité comme « samedi sans école » (extrascolaire), sauf si le preset déclare des samedis avec école.
5. **Moutiers** : les deux conventions de La Guerche couvrent la structure « La Guerche-Moutiers » (couverture, p. PDF 1). Le formulaire des lieux d'implantation n'étant pas fourni, le rattachement de Moutiers doit être confirmé dans le référentiel avant toute validation d'export.
6. **Minicamps** : ils ne sont comptés en séjour (10 h/journée réalisée) que s'ils figurent dans le registre des séjours qualifiés (dates, nuits, déclaration, intégration au projet éducatif) ; leur équipement de rattachement doit être choisi dans le référentiel.
7. **Garderies** : affichées séparément (matin, soir, total) et non ajoutées aux heures CAF, sauf choix explicite du preset.
8. **Arrondi du complément inclusif** : la présence effective brute et la valeur arrondie à l'heure supérieure par jour sont toutes deux restituées ; le mode retenu par la Caf (addendum) reste à confirmer.

## Pièces manquantes

- Addenda des quatre conventions (modalités de calcul « à l'appui du barème », plafond de développement Ctg, pourcentage d'écrêtement) — cités à l'art. 3.
- Formulaires des lieux d'implantation (art. 1 : « leurs lieux d'implantation désignés dans le formulaire prévu à cet effet »).
- Grilles tarifaires (preuve d'une facturation exclusivement à la journée / demi-journée en extrascolaire).
- Avenants éventuels et copies signées par le gestionnaire.
- Conventions ALSH Ados (hors périmètre de cette version).
