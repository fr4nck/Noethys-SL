# Recette AFAS V2 — visuelle Windows et rapprochement chiffré

Module : Consommations → **Déclarations AFAS** (branche `main`, non intégré à `wx` / RC9). Données **fictives** uniquement pour la recette visuelle ; le rapprochement chiffré se fait sur un **extrait pseudonymisé** produit localement par la structure, jamais transmis.

## 1. Recette visuelle Windows sur fichier fictif

### Préparation (poste de recette, environnement Python du projet)

```
python tests/recette_creer_fichier_fictif.py . <copie>/Noethys/Portable
python tests/recette_afas2.py peupler <copie>/Noethys/Portable/Data/Recette_DATA.dat
```

Le second script ajoute l'activité fictive « ALSH (fictif AFAS) » (groupes Bais +6 ans, Bais -6 ans, Moutiers, La Guerche, Minicamps 6/8, Minicamps 8/10), ses unités, un calendrier complet de vacances inventé, 7 enfants fictifs, consommations, prestations, factures (dont une annulée) et un avoir non rattaché. Option `--parametrer` : enregistre aussi le référentiel et les trois presets (pour vérifier l'affichage sans tout ressaisir). Identifiant administrateur fictif : `recette2026`.

### Parcours à exécuter (cocher PASS / FAIL, capture d'écran pour chaque FAIL)

| # | Action | Résultat attendu | PASS/FAIL |
|---|---|---|---|
| V1 | Ouvrir Consommations → Déclarations AFAS | Dialogue ouvert ; aucune case « samedis avec école » ; statuts du réalisé : « Présent » seul ; statuts du facturé sans « Pointage en attente » | |
| V2 | Référentiel… : relier les six sites à leurs groupes | Équipement Bais / La Guerche-Moutiers affiché pour les sites documentés ; choix de l'équipement pour les minicamps | |
| V3 | Minicamps 6/8 : équipement Bais, justificatif « Déclaration fictive de l'accueil n° 0000-FICTIF » ; Minicamps 8/10 sans équipement | Enregistrement accepté | |
| V4 | Samedis avec école : `2024 : aucun`, `2025 : aucun`, `2026 : aucun` | Accepté ; `2026 : 2026-11-27` refusé (pas un samedi) | |
| V5 | Ajouter le séjour « Minicamp fictif de la Toussaint », Minicamps 6/8, 2026-10-21 → 2026-10-23, 2 nuits, intégré au projet éducatif | Accepté ; 6 nuits refusé | |
| V6 | Qualifier la régularisation : prestation `90090`, consommations annulées `92005`, pièce « Avoir fictif n° A-1 » | Ligne « Prestation 90090 — annule 92005 — … » | |
| V7 | Preset « Bais périscolaire (fictif) » : périscolaire, Bais, site Bais +6 ans ; Classer les unités : Péri matin/soir = accueil, Péri repas = repas, Garderie matin = garderie du matin ; bouton « Reprendre les horaires Noethys » ; Enregistrer | Plages 07:30-08:45, 16:30-18:30, 12:00-13:30, 07:00-07:30 ; preset enregistré | |
| V8 | Effacer la plage de « Péri soir » puis Enregistrer | Refus : plage réellement organisée à déclarer | |
| V9 | Année 2026, Réel annuel, Calculer | VALIDABLE ; voir tableau A | |
| V10 | Preset « Bais extrascolaire (fictif) » : extrascolaire, Bais, sites Bais +6 et -6 ; Journée = journée, Matinée et Après-midi = demi-journée, Repas vacances = repas, Sortie = annexe ; Calculer 2026 réel | VALIDABLE ; voir tableau B | |
| V11 | Retirer la qualification de la régularisation (Référentiel), recalculer | NON VALIDABLE ; anomalie « Régularisation négative non rattachée à une consommation (prestation 90090 …) » | |
| V12 | Preset « Bais extrascolaire avec minicamps (fictif) » (ajouter Minicamps 6/8, Minicamp = séjour) ; Calculer | Séjours 50,00 ; NON VALIDABLE : « rubrique AFAS des séjours non confirmée » ; Exporter le contrôle possible, Exporter la déclaration refusé | |
| V13 | Dans Noethys, modifier l'horaire de l'unité « Journée » (17:30 → 18:00), recalculer V10 | Anomalie bloquante « horaires Noethys … différents de la plage déclarée 08:30-17:30 » ; remettre 17:30 | |
| V14 | Exporter la déclaration (V10) puis Historique… | Fichiers synthèse (colonne Nature), détail (IDprestation, IDfacture), jours (plages d'ouverture, justification), anomalies, instantané ; archive « Intégrité : vérifiée » | |
| V15 | Fermer, rouvrir, recharger chaque preset | Contenu identique ; ni année ni phase dans le preset | |
| V16 | Affichage 100 % / 125 % / 150 % | Aucun contrôle tronqué ni bouton hors fenêtre | |

### Tableau A — périscolaire Bais, réel 2026 (heures décimales)

| Indicateur | Attendu | Détail |
|---|---|---|
| Heures de présence conventionnelles CAF | 6,00 | Alix 03/03 : matin 1,25 + soir 2,00 ; Basile 03/03 : 1,25 ; Alix 05/03 : repas 1,50 |
| Dont heures réalisées AEEH | 1,25 | Basile (AEEH depuis le 01/01/2026) |
| Heures de présence physique | 5,08 | 50 min + 1 h 30 + 30 min ; 45 min ; 1 h 30 |
| Complément inclusif brut / arrondi (hypothèse) | 0,75 / 1,00 | |
| Garderie matin / total | 0,50 / 0,50 | non ajoutée aux heures CAF |
| Heures facturées, séjours | non applicable | |

### Tableau B — extrascolaire Bais, réel 2026

| Indicateur | Attendu | Détail |
|---|---|---|
| Heures facturées CAF | 28,00 | Alix 19/10 journée 8 ; Basile 19/10 matinée 4 (ouverture continue 08:30-17:30 avec le repas) ; Capucine absence facturée 8 ; Dorian facture annulée 0 ; Elsa annulée par l'avoir qualifié 0 ; Alix 20/10 journée à 0 € (remise) 8 ; sortie : annexe |
| Dont facturées AEEH | 4,00 | Basile |
| Heures de présence conventionnelles CAF | 39,00 | 8,50 + 3,50 + 0 + 9 + 9 + 9 |
| Dont réalisées AEEH | 3,50 | |
| Complément inclusif brut / arrondi (hypothèse) | 3,50 / 4,00 | |
| Séjours | 0,00 (50,00 avec le preset minicamps ; réalisé 89,00, facturé 78,00) | |

Ces valeurs sont aussi vérifiées automatiquement (`tests/test_afas2_qualification_bases.py`, SQLite à chaque CI, MySQL 5.7 par le workflow manuel « Noethys SL - AFAS V2 MySQL fictif »).

## 2. Rapprochement chiffré avec une année réelle pseudonymisée

À faire **par la structure**, sur un poste interne, à partir d'une **copie** de la base (jamais la base de production ouverte en écriture ; une copie MySQL restaurée sur un serveur local est lue par la même commande avec la chaîne GestionDB `port;hôte;utilisateur;mdp[RESEAU]base`).

1. **Extraction minimale** (lecture seule de la source, nouveau fichier) :
   `python tests/recette_afas2.py extraire <copie>.dat <extrait>.dat --annee 2025`
   Copie uniquement : activités, groupes, unités, ouvertures, vacances, consommations de 2024-2025, prestations liées et prestations négatives (avoirs) jusqu'à fin mars 2026, factures (numéro remplacé par l'identifiant, état conservé), périodes AEEH, référentiel et presets AFAS. Enfants renommés « ENFANT n° ID », libellés supprimés, montants réduits à leur signe (−1, 0, 1). Aucune adresse, date de naissance, coordonnée, règlement ni document.
2. **Paramétrage** : ouvrir l'extrait dans Noethys (ou utiliser les presets déjà présents) et vérifier référentiel, plages déclarées, samedis datés, justificatifs ; qualifier les régularisations signalées.
3. **Références** : créer `attendus.csv` avec les heures déclarées à la Caf pour cette année (une ligne par indicateur), par exemple :
   ```
   indicateur;heures
   heures_realisees;12345,50
   heures_facturees;9876
   heures_realisees_aeeh;120
   ```
4. **Rapprochement** :
   `python tests/recette_afas2.py rapprocher <extrait>.dat --annee 2025 --phase reel --preset "<nom du preset>" --attendus attendus.csv --sortie <dossier>`
   Produit : `rapprochement_2025_indicateurs.csv` (calculé, référence, écart en heures et en %), `rapprochement_2025_mois_sites.csv` (réalisé, facturé et jours-enfants par mois et par site) et l'export de contrôle complet (détail, jours, anomalies).
5. **Analyse** : expliquer chaque écart supérieur au seuil fixé par la direction à partir de la ventilation mensuelle et des anomalies (calendrier incomplet, plages, régularisations, forfaits, séjours). Aucun chiffre réel n'est versé dans le dépôt.

Outils testés sur le jeu fictif : extraction sans modification de la source (empreinte SHA-256 identique), pseudonymisation, résultats identiques avant et après extraction, rapprochement et ventilation (`OutilsRecetteTests`).
