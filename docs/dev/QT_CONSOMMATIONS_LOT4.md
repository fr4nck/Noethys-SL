# Lot Qt C4 - laboratoire transactionnel fictif

Date : 27 octobre 2026. Le chantier prépare le remplacement progressif
des composants graphiques wx, sans autoriser des écritures financières Qt
avant démonstration de la parité métier.

## Sources métier et constat

- wx 11b8546, CTRL_Grille.py, blob f653316, Sauvegarde vers les
  lignes 5364-5705 : sauvegarde des prestations, déductions,
  ventilations, consommations, historique et traitement d'adhésions.
- La routine appelle DB.Commit après les consommations, puis de nouveau
  après l'historique. Certaines fonctions de GestionDB ont également
  des commits par défaut. L'existence de ces séquences ne constitue
  pas une transaction unique prouvée.
- wx CTRL_Grille_cases.py, blob 46b1e02 : périodes, droits, forfaits,
  verrouillages, factures, ventilations et recalculs doivent continuer
  à conditionner toute modification.
- main f6f5ccd et wx 11b8546 sont restées hors modification dans C4.

## Réalisation strictement isolée

Le fichier tests_qt/test_consumptions_c4_transactions.py fournit seul
le banc de test, non importé par les modules de production noethys_qt.

- Fixture SQLite créée par TemporaryDirectory, sans possibilité de
  fournir une base externe, un profil de production ou une connexion.
  Les chemins et le marqueur de base synthétique sont contrôlés.
- Cinq tables artificielles nommées lab_* : leur contenu et leurs
  opérations ne reflètent pas des écritures comptables. Aucun règlement
  ni facture réel, aucune création d'adhésion.
- Une transaction BEGIN IMMEDIATE regroupe cinq opérations fictives.
  Injection d'erreur après chacune, rollback de toutes les tables,
  échec sur contrainte SQL et restauration d'une copie locale par
  l'API de sauvegarde SQLite.
- Refus systématique des exemples facturés, ventilés (même montant
  nul), verrouillés, forfaitaires, clôturés, interdits, orphelins,
  des états non canoniques et des passages entre familles tarifantes.
- Contrôle de rejeu, sélection périmée, et contre-exemple montrant
  pourquoi un commit intermédiaire ne peut pas être annulé ensuite.
- Aucun module Qt de consultation/précontrôle C1-C3, schéma réel,
  moteur financier ou code wx n'est modifié.

## Conclusions et limites

La preuve de transaction n'atteste que de la mécanique SQLite sur
une **fixture totalement inventée**. Elle ne démontre ni l'équivalence
des writes wx/Qt, ni l'atomicité de la sauvegarde historique wx, ni
les droits utilisateurs ou les verrous de période réels, ni MySQL.
Les tests CI Windows compilent et exécutent du code hors écran ;
ce n'est pas une recette métier ni un installateur Qt prêt à livrer.

**STOP-GATE** maintenu pour la saisie Qt : aucune opération métier
UPDATE/INSERT/DELETE n'est activée dans noethys_qt. Le C5 devra
évaluer le protocole de qualification des écritures réelles sur
**copies jetables**, tarifs, adhésions, historiques et erreurs,
avant toute réutilisation du moteur transactionnel.

## Matrice à l'ouverture

| Branche | SHA | Position |
| --- | --- | --- |
| main | f6f5ccd | NON APPLICABLE, inchangée |
| wx | 11b8546 | source auditée, inchangée par C4 |
| qt | 8ff9bfc | base C4, CI du commit final à consigner |
