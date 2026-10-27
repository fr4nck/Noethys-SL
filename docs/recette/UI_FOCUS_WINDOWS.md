# Noethys-SL wx — recette focus, fenêtres et réactivité (après RC9)

**Ce document concerne les commits correctifs en développement sur `wx`, et NON
le paquet RC9 déjà publié.** Aucun exécutable correctif n'est annoncé ici.
Aucune base PMSL, aucune adresse réelle, aucun envoi à des destinataires réels.

## Préparation (poste Windows de recette exclusivement)

- Utiliser un candidat Windows construit pour le SHA exact à tester, sur une
  machine de recette autorisée. Ne pas utiliser l'installateur RC9 existant
  pour prétendre valider les correctifs UI ultérieurs.
- Profil portable isolé, base fictive et comptes/adresses de test
  `contact-001@example.test`, `contact-002@example.test`.
- Transport réseau entièrement factice/intercepté et sans sortie SMTP ou
  HTTP Mailjet. Ne pas couper un serveur réel.
- Journal facultatif `NOETHYS_SL_UI_DIAG=1` : mesures de durée, retards de
  boucle wx, événements activation/maximisation/taille/iconisation. Laisser
  désactivé pour les utilisateurs ordinaires. Ne conserver que les
  événements techniques dépourvus de données personnelles.

## Scénarios

| ID | Parcours sur données fictives | Attendu |
|---|---|---|
| WIN-UI-01 | Noethys maximisé, dialogue Connecthys, avertissement de réservations | Fenêtre avertissement avec propriétaire Connecthys, aucun dialogue orphelin |
| WIN-UI-02 | Mailer masqué, erreur de validation de l'objet ou expéditeur | Message appartenant à Connecthys ; Mailer masqué ne s'ouvre jamais |
| WIN-UI-03 | Mailer masqué, deux adresses SMTP fictives, délais 3/8/15 s | Boucle wx réactive, une progression visible, aucun double traitement |
| WIN-UI-04 | Mailer visible, plusieurs adresses SMTP fictives | Barre d'attente réactive, éditeur reste visible, contrôle de double clic |
| WIN-UI-05 | Acceptation SMTP partielle puis timeout sans preuve de refus | Aucune répétition de l'adresse déjà acceptée, état incertain conservé |
| WIN-UI-06 | Mailjet masqué, deux adresses fictives ; refus explicite vs timeout | Suivi par message, pas de répétition automatique sur timeout |
| WIN-UI-07 | Traitement automatique de réservations, grille fictive | Diagnostic des phases ; pas de fausse annonce de sauvegarde terminée |
| WIN-UI-08 | Répéter les scénarios sur une fenêtre initialement maximisée | `IsMaximized` et dimensions inchangés après fermeture des dialogues |

## Contrôles complémentaires

- Relever séparément les événements `EVT_ACTIVATE`, `EVT_SIZE`,
  `EVT_MAXIMIZE` et `EVT_ICONIZE`. Un passage d'une autre application
  au premier plan n'implique pas que la fenêtre Noethys soit démaximisée.
- Pour les boîtes de dialogue Windows, inspecter le vrai `GW_OWNER` du
  `HWND` et la visibilité de l'ancêtre propriétaire ; un simple
  `GetParent()` wx ne suffit pas.
- Vérifier la possibilité d'interagir avec les contrôles pendant une
  requête réseau factice, sans réentrer dans une opération de sauvegarde.
- Un échec de `Sauvegarde()` ne doit jamais se présenter visuellement comme
  une réussite. Tester uniquement sur des bases de recette.
- Conserver les captures uniquement avec noms, emails et montants
  artificiels. Ne joindre ni fichier de base, ni vidéo, ni trace
  contenant des données d'adhérents.

## Rendu de qualification

Point du 27/10/2026 : voir [les mesures #432 et leurs limites](UI_432_20261027.md).
Le diagnostic distingue maintenant `fenetre=principale` de `fenetre=demande`
et compare les flags wx et Win32. Le chargement automatique de la grille
est fractionne sur le thread wx, sans decouper les ecritures. Une lecture
individuelle longue reste bloquante : aucune resolution complete revendiquee.

Consigner : SHA du candidat, version de Windows, environnement de recette,
scénario, PASS/FAIL/SKIP, état du focus avant/après, géométrie avant/après,
retard maximal des événements wx et type d'erreur technique uniquement.

**NON QUALIFIÉ tant qu'une session graphique Windows n'a pas exécuté ces
scénarios** : les tests de contrats, même sur runner Windows, ne prouvent
pas à eux seuls la reproduction des pertes de premier plan.
