# Noethys SL Qt — C3 : précontrôle de changement d'état (27/10/2026)

## Décision et statut

Le chantier Qt ne dispose pas encore de la parité fonctionnelle du gestionnaire wx. C3 **ne** rend pas l'écriture des consommations disponible : il construit un précontrôle explicite, toujours bloquant, déclenché uniquement par l'utilisateur sur une consommation déjà sélectionnée. Pas d'ajout d'une nouvelle branche, pas d'installation ni de base réelle.

## Contrat métier vérifié dans les sources wx

- \`noethys/Ctrl/CTRL_Grille_cases.py\`, \`ModifieEtat\` (lignes environ 1690–1720, 2043–2076) : contrôle de période de gestion \`gestion.Verification("consommations", date)\` ; changement entre familles \`reservation/present/absenti\` et \`attente/refus/absentj\` impactant le traitement de facturation, avec protection si prestation déjà facturée. Cela ne suffit pas à déclarer une transition sans risque.
- \`ProtectionsModifSuppr\` (autour de 1020–1090) : verrouillage, forfait verrouillé, pointage, facture et ventilation sur règlement. Certains cas réclament confirmation humaine et retrait de ventilation. C3 ne reproduit pas ces mutations.
- La grille wx vérifie les permissions \`consommations_conso/modifier\` par activité, le type d'unité, les ouvertures, les inscriptions, les tarifs, la gestion des forfaits et l'historique. Une équivalence complète du service n'est pas encore démontrée.

## Implémentation isolée

- \`consumptions_preparation_core.py\` : \`ConsumptionPreflightRepository.inspect()\` relit en SELECT l'identité, l'état, la date, le lien d'inscription, le verrouillage, le forfait et la prestation d'une consommation précise. Il vérifie l'existence de la prestation, son lien à une facture et compte les lignes de ventilation, même si le total monétaire est nul.
- Comparaison de la sélection Qt avec le snapshot relu : si l'état, la date, l'activité, l'individu, la prestation ou l'événement ont changé, le précontrôle signale \`SELECTION_PERIMEE\`.
- \`assess_transition()\` : propose un diagnostic structuré \`Issue(code, message)\` et distingue les franchissements des deux familles historiques. Les droits, les clôtures de période, les recalculs financiers et **l'absence d'adaptateur d'écriture** restent des obstacles systématiques.
- \`TransitionPreview.executable\` reste toujours faux ; une tentative de l'instancier à vrai lève une erreur. Aucun code de production ne fait INSERT, UPDATE, DELETE ou n'écrit une prestation.
- \`ConsumptionPreparationPanel\` : choix de l'un des six états, bouton « Vérifier les protections », affichage de la simulation dans la vue calendrier C2. Aucun bouton Enregistrer. Le SQL n'est lu qu'au clic et en tâche Qt non bloquante sur Windows ; les résultats périmés sont ignorés.
- Les connexions SQLite de consultation passent en \`PRAGMA query_only=ON\` ; l'ouverture d'une base configurée conserve la garde existante. Les fixtures sont exclusivement synthétiques.

## Tests, compatibilité et limites

- Tests dédiés : disparition et ancienneté d'une sélection, changement de famille tarifante, non-opération, verrouillage, forfait, prestation orpheline, facture, ventilation à montant zéro, inscription absente, état inconnu, refus d'une cible non canonique, impossibilité d'activer une écriture, SQLite avant/après et parcours UI hors écran.
- Le protocole transactionnel de modification et ses effets sur \`prestations\`, \`ventilation\`, \`historique\`, calcul des tarifs et suivi d'assiduité **ne sont pas qualifiés** dans C3. Aucun mécanisme de mutation exploitable n'est ajouté.
- Non-régression \`main\` et \`wx\` : aucun code partagé touché. Le prochain lot de qualification doit comparer les écritures des scénarios wx contre Qt sur **base jetable**, incluant les cas facturés, clôturés, pointés, forfaits, erreurs et rollback. Tout écart implique STOP-GATE.
- Une CI Windows verte signifie tests automatisés hors écran, pas recette humaine ni homologation d'un outil de saisie. Aucun candidat Windows, aucune release ni base de production ne doivent être modifiés dans ce lot.

## Suivi branches à l'ouverture du lot

- main \`f6f5ccd\` : NON APPLICABLE à cette interface spécifique.
- wx \`a24e1dd\` : SOURCE de référence de la grille, aucune modification.
- qt \`ef36db0\` : base de développement C3. Le SHA du commit C3 et sa CI sont à consigner après exécution.
