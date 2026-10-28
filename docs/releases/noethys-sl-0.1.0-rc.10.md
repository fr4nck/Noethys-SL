# Noethys SL 0.1.0 RC10 — candidat cumulatif Windows wx

**Date : 28 octobre 2026 — préversion de recette, sans déploiement en production.**

Base de comparaison : [RC9.1 du 26 octobre](https://github.com/fr4nck/Noethys-SL/releases/tag/noethys-sl-0.1.0-rc.9.1), tag `noethys-sl-0.1.0-rc.9.1` (commit `0eccac4a`). La RC10 conserve cette version publiée et sa possibilité de repli. Identité publique `0.1.0-rc.10`, sans modification de la version **interne** `1.3.4.4` requise par Noethys, ses migrations et Connecthys.

## Principales évolutions depuis RC9.1

### Demandes et synchronisation Connecthys — #432, #435

- Traitement des créneaux Journée/Matin/Après-midi : contrôle des disponibilités, priorité de la Journée si elle est réellement disponible, repli ciblé sur les demi-journées, garde de quantité, reprise contrôlée des demandes ambiguës et traçabilité.
- Prévention des réapplications de consommation lors de reprises et neutralisation des doubles quantités indues, sous les réserves de concurrence interpostes documentées dans `docs/recette/UI_435_QUALIFICATION.md`.
- Synchronisation et interface wx : opérations longues coopératives, diagnostic facultatif de réactivité, accès aux informations de traitement et garde-fous supplémentaires.
- Aucun changement imposé au serveur Connecthys d'Ivan Lucas.

### Questionnaires et repas — #430, #433

- Préparation/reconnaissance du questionnaire individuel `Type de repas` depuis l'écran Questionnaires et le paramétrage des commandes ; refus des doublons et des réglages ambigus.
- Réutilisation des modes standard / sans porc / végétarien, et préparation explicite des modèles pouvant distinguer un panier apporté par la famille.
- Pour un panier familial, le calcul fournisseur peut exclure le repas commandé tout en conservant la présence réelle. **L'exonération automatique à 0 € n'est PAS livrée** : les forfaits, tarifs et historiques restent sous STOP-GATE, sans action sur les factures réelles.

### Fiches enfant / AEEH et santé — #436

- Réception des fiches originales Pêle-Mêle conservée, sur papier ou via les pièces Connecthys ; pas de nouvelle fiche ni de questionnaire parallèle.
- Depuis une fiche enfant existante, contrôle manuel de la réponse AEEH (Oui/Non/Non renseigné), comparaison des dates parentales avec les périodes enregistrées, signalement des doublons et chevauchements.
- Une période de droit ne peut être créée qu'après vérification explicite d'un justificatif et confirmation de l'agent, avec événement d'historique dans la même transaction.
- Historisation de la réception d'une fiche signée, sans inscription des détails d'allergies, traitements ou PAI dans le texte de l'historique général ; consultation des dernières réceptions.
- Accès à l'onglet Médical déjà présent pour vérifier vaccinations, allergies, traitements, PAI et consignes de sortie. Une déclaration parentale ou un calcul de validité des vaccins **ne certifie pas** la conformité réglementaire.

## Ce qui n'est pas livré

- **OCR des fiches : NON DISPONIBLE dans RC10.** Le traitement 100 % local/hors ligne, la détection des cases cochées et la relecture humaine constituent un chantier distinct, non qualifié. Aucun service cloud/IA distante ni moteur téléchargé silencieusement n'est ajouté.
- **CAF/AFAS V1 :** bouton encore masqué, résultats non qualifiés pour déclaration.
- **Facturation zéro euro des paniers familiaux :** non activée ; aucun tarif ni facture antérieure corrigés.
- **Qt :** pas de portage de ces nouvelles interfaces, qui sont propres à wx.
- **Pointage interdomaines :** nouveaux modules techniques présents dans le HEAD wx, sans activation opérationnelle ni recette métier de production qualifiée dans ce candidat.
- **Production :** concurrence MySQL multiposte des demandes Connecthys, recette graphique avec écrans et formulaires fictifs, qualification du stockage AEEH sur serveur MySQL jetable et des nouveaux boutons restent nécessaires avant déploiement.

## Construire, tester et diffuser

Un nouveau workflow `.github/workflows/noethys-sl-rc10-windows.yml` produit un **candidat Windows wx** sur des ressources de recette : `Noethys-SL-0.1.0-rc.10-Setup.exe`, `Noethys-SL-0.1.0-rc.10-Windows-portable.zip`, `SHA256SUMS.txt`, tous dérivés du même SHA du dépôt.

Garde-fous : compilation, contrats métier (en particulier #433/#435/#436), build PyInstaller, ressources et version, sauvegarde/restauration MySQL jetable, test d'initialisation wx, démarrage du portable deux fois, conservation de `Config.json`, absence de profil externe, empreintes. Le workflow ne publie aucune release sur un push : **seul un lancement manuel depuis wx avec `publier=true` peut activer un job distinct après succès de la construction.** Une CI verte ne valide pas l'environnement PMSL.

Recette opérateur avec données fictives : `docs/recette/RC10_FICHE_RECETTE.md`. Ne pas installer sur la base ou le profil PMSL avant qualification et sauvegarde contrôlée.
