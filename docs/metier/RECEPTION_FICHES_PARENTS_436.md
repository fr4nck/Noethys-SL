# #436 — Réception des fiches Pêle-Mêle déjà transmises

État du 28 octobre 2026 : moteur de contrôle manuel, sans écriture, qualifié localement.
La réception des PDF/jpg existe déjà dans Connecthys ; aucune nouvelle collecte ou
modification du serveur hébergé par Ivan Lucas n'est demandée.

## Circuit existant vérifié

- Connecthys, page « Pièces » : téléchargement des formulaires types et envoi
  facultatif de documents PDF/JPG/PNG sous réserve des réglages de l'instance.
- Noethys-SL : synchronisation des actions `categorie=pieces` ; traitement
  dans `Dlg/DLG_Saisie_portail_demande.py.Traitement_pieces` ; déchiffrement,
  ajout de la pièce via `DLG_Saisie_piece`, puis validation de la demande.
- Les fiches papier restent recevables via le même dossier enfant/famille.
- Ce circuit garantit la **réception d'une pièce**, pas l'exactitude ou la mise à jour
  des informations figurant dans ses pages.
- Les documents Pêle-Mêle « Fiche Enfant » et « Fiche Famille » originaux restent les
  uniques modèles ; aucun nouveau PDF n'est introduit.

## Ce que fait le moteur commun

`Utils/UTILS_Reception_fiches.py` ne lit aucun document et n'écrit aucune donnée :

1. Comparaison d'une réponse **explicitement lue par un opérateur** sur la fiche
   enfant (« Oui » / « Non » / pas de réponse) avec la valeur
   `individus.aeeh` (`NULL/0/1`). Une case vide n'est **jamais** traitée
   comme « Non », ni comme demande de supprimer le champ déjà rempli.
2. Proposition uniquement après confirmation de lecture : « identique »,
   « à reporter », « relecture requise » ou « non renseigné sur la pièce ».
   Le résultat contient **toujours `ecriture_autorisee=False`** : aucune
   modification automatique.
3. Comparaison des périodes **déclarées** avec les périodes **déjà enregistrées**
   dans `aeeh_periodes` : doublon exact, nouvelle période, chevauchement
   nécessitant arbitrage, ou dates absentes ; aucune création de droit.
4. Rappel séparé des vérifications « vaccinations, allergies, traitements,
   PAI, consignes de sortie ». La réception ou relecture d'une fiche
   **ne vaut pas** vérification d'un vaccin, justificatif, protocole ou traitement.

Ces contrôles conservent la séparation de l'AEEH (allocation) et des besoins
de santé/handicap. Ils ne requalifient jamais « pas d'AEEH » en « pas de handicap ».

## UX prévue puis livraison wx isolée

Depuis la fiche individuelle, **Outils → Contrôler la fiche enfant reçue** :
ouvrir d'abord le document depuis l'onglet « Pièces », s'assurer de l'identité
de l'enfant, saisir Oui/Non uniquement lorsqu'une case est effectivement cochée,
puis confirmer l'examen. Le résultat peut être reporté dans le contrôle AEEH
**de l'onglet Identité**, jamais directement en SQL. L'opérateur conserve la
sauvegarde habituelle de la fiche et peut annuler. Pas d'accès supplémentaire
ni de modification des contrôles médicaux. La vérification des périodes reste
séparée : l'assistant ne les enregistre pas.

Important : cette fonction wx n'est considérée livrée qu'après un commit wx
distinct, CI Windows et recette graphique. Le présent contrat est indépendant
de wx/Qt et n'active ni wx, ni Qt, ni portail à lui seul.

## Sécurité et non-régressions

- Aucune ouverture du serveur Connecthys, aucun changement de synchronisation,
  de `portail_actions`, des réservations #435 ou de l'enregistrement des pièces.
- Pas de parsing OCR du PDF, pas de diagnostic dans un log ou une action de suivi.
- Pas de nouvelle table/questionnaire AEEH, pas de migration, pas de modification
  automatique des périodes ou des vaccins.
- Pas de traitement de données PMSL réelles et aucun changement du profil Portable.
- 18 tests du moteur sur données fictives, y compris contradiction, preuve de
  relecture, refus d'un identifiant invalide, périodes chevauchantes, dates
  incorrectes et séparation des contrôles médicaux.
- La réception de la fiche famille est déjà traitée comme pièce familiale ;
  aucun enrichissement familial n'est lancé dans ce sous-lot.
- La future collecte numérique structurée et les signatures restent réservées
  au portail PMSL ultérieur ; Connecthys d'Ivan Lucas reste inchangé.

## Suites restant à faire

- Vérifier en recette le parcours wx : réception pièce → onglet Pièces →
  contrôle AEEH → sauvegarde explicite → onglet Médical.
- Construire plus tard le contrôle des périodes avec interface dédiée,
  provenance datée et historisation, sur données et migrations fictives.
- Vérifier les habilitations héritées et les accès de lecture, sans modifier
  la version hébergée de Connecthys.
