# Noethys SL 0.1.0 RC10.3 — recherche d'anomalies au démarrage

- Les lectures de la recherche d'anomalies s'exécutent en arrière-plan afin de
  laisser l'interface répondre pendant l'attente SQL.
- La fenêtre d'attente, les textes et la présentation sont conservés. Aucun
  redimensionnement ou retour forcé au plein écran n'est ajouté.
- Les attentes communes des listes, fiches et traitements sont désormais
  rattachées à leur fenêtre Windows et affichées sans activation. Leur message
  et leur disposition sont conservés, sans premier plan global.
- Les requêtes et les règles de détection sont conservées ; la connexion est
  ouverte et fermée dans le même thread, y compris en cas d'erreur.
- Les fiches famille/individu et le dialogue d'ajout sont rattachés explicitement
  à la fenêtre d'origine : compositions graphique et liste, archivage et listes
  d'anomalies de prestations. Les retours de fenêtres sont vérifiés sous Windows.
- Les corrections de sauvegarde RC10.2 et la version interne `1.3.4.4` sont conservées.
- À la demande de l'utilisateur : écran « Situation des communes (ALSH) »,
  fréquentation, participations communales et exports de synthèse PDF/CSV/Excel.
  L'import SQL est en lecture seule, sous attente réactive ; les résultats
  dépendent des conventions et vérifications de périmètre saisies dans l'écran.

Cette correction traite le blocage identifié dans la recherche. Le maintien
de la géométrie et de l'état de la fenêtre est vérifié sur Windows isolé ;
la reproduction exacte du changement d'état sur le poste utilisateur reste
distincte de cette qualification.

Le Setup et le portable sont issus du même candidat vérifié.
