# Noethys SL 0.1.0 RC10.3 — recherche d'anomalies au démarrage

- Les lectures de la recherche d'anomalies s'exécutent en arrière-plan afin de
  laisser l'interface répondre pendant l'attente SQL.
- La fenêtre d'attente, les textes et la présentation sont conservés. Aucun
  redimensionnement ou retour forcé au plein écran n'est ajouté.
- Les requêtes et les règles de détection sont conservées ; la connexion est
  ouverte et fermée dans le même thread, y compris en cas d'erreur.
- Les corrections de sauvegarde RC10.2 et la version interne `1.3.4.4` sont conservées.

Cette correction traite le blocage identifié dans la recherche. Le maintien
de la géométrie et de l'état de la fenêtre est vérifié sur Windows isolé ;
la reproduction exacte du changement d'état sur le poste utilisateur reste
distincte de cette qualification.

Le Setup et le portable sont issus du même candidat vérifié.
