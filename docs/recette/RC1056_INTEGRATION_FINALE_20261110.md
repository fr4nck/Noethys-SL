# RC10.56 — coordination de l'intégration finale (10 novembre 2026)

**Ticket central : [#443 — Intégration finale](https://github.com/fr4nck/Noethys-SL/issues/443).**

**Statut : STOP-GATE / AUCUNE publication autorisée par cette note.**
Dernière release publique contrôlée au prévol : RC10.55. Source de référence initiale : branche unique `wx`, SHA `eaf24a03525372d26761e922f237da3b598b2a16`. **Ce SHA n'est pas figé** et doit être revérifié au moment de toute recette ou publication.

## Organisation — deux chantiers, un seul point d'intégration

- **Statistiques/QF** ([#442](https://github.com/fr4nck/Noethys-SL/issues/442)) : responsable de ses modèles SQL et de ses tests. Les 33 objets du moteur historique ont des preuves SQLite ciblées ; les 15 graphiques disposent de preuves Matplotlib Agg et wx.MemoryFS natif. Le prototype QF travaillé dans une autre conversation doit être **effectivement intégré au dépôt** puis qualifié : ne pas assimiler les tests de prototype aux tests de Noethys-SL.
- **Fenêtres/traitements longs** ([#432](https://github.com/fr4nck/Noethys-SL/issues/432)) : responsable des corrections Win32, workers SQL/PDF, propriétaires de dialogues, tests GUI/installés et interactions Connecthys. Les 43 tests UI ciblés et le rendu PDF de recette installée ont été validés séparément ; le parcours **Connecthys installé** restait en échec au run [#42845391947](https://github.com/fr4nck/Noethys-SL/actions/runs/42845391947). Le commit `eaf24a03` prépare une nouvelle contre-épreuve, pas un PASS déjà obtenu.
- **Sécurité des opérations** : [#437](https://github.com/fr4nck/Noethys-SL/issues/437) sauvegarde **DATA + DOCUMENTS restaurable** sur MySQL isolé (PHOTOS facultatif), et [#426](https://github.com/fr4nck/Noethys-SL/issues/426) facturation/adhésions, choix humains, contre-test MySQL.
- **Intégration** : seule responsable de l'évolution de cette note et du ticket #443 ; relit les commits, identifie les fichiers partagés, reprend les validations sur **le même SHA** et prépare la décision de RC.

## Compatibilité entre chantiers

Risque majeur : `UTILS_Stats_individus.py`, `UTILS_Stats_familles.py`, `UTILS_Stats_modeles.py`, `DLG_Stats.py`, les workers `UTILS_Stats_*` et les dialogues wx/Noedoc. Ne pas remplacer un fichier entier par un état d'une conversation parallèle sans comparaison avec le dernier `wx`.

- SQL, connexions MySQL/SQLite et préparation DTO **dans un worker indépendant** lorsque qualifié ; jamais de widget wx, `wx.Bitmap` ou `wx.MemoryFSHandler` dans ce worker.
- Réintégration des données dans les objets graphiques **sur le thread wx**, avec annulations et fermeture sans callback tardif vers fenêtre détruite.
- Maintenir les décisions statistiques QF déjà validées par la direction : **Présents**, période sélectionnée, présences validées avant édition des factures, catégories historiques même à zéro ou supprimées, graphiques barres + secteurs, exports Excel + CSV **agrégés sans noms**, synthèse générale + détail par site, **pas de doublon familial** dans la synthèse. L'arbitrage réellement manquant sur les `IDtype_quotient` distincts doit rester visible dans #442.
- **Aucun** résultat « PASS » hors périmètre : un PNG Agg réussi ne prouve pas l'impression dans Noethys installé ; un PDF enfant réussi ne prouve pas la disparition du problème de maximisation.

## Marche à suivre avant RC

1. Les chantiers terminent leurs modifications sur `wx` avec commits courts, tests et notes de preuve ; ils lient leurs résultats à #443. Ne pas ajouter d'autre tag ni activer le workflow de release.
2. L'intégration compare le HEAD courant aux références, réconcilie les fichiers communs et établit la **liste réelle** des changements QF + GUI + facturation + sauvegardes inclus.
3. Tester les 33 objets / 11 pages avec SQLite et MySQL 5.7 jetables, les 15 graphiques, les exports et les calculs QF attendus indépendamment ; contrôler l'interface, l'impression et l'absence de gel/retour fenêtré.
4. Repasser Connecthys/PDF installé, sauvegarde/restauration DATA+DOCUMENTS, facturation, puis **CI générale Windows verte sur un commit unique**.
5. Figer le SHA validé ; vérifier deux paquets (Setup + portable), diagnostics et SHA-256 ; demander le **GO de publication préversion** après vérification du ticket #443. Toute modification sur `wx` entre qualification et build impose de requalifier le nouveau SHA.

La dernière tentative officielle [RC10.56 #42705268198](https://github.com/fr4nck/Noethys-SL/actions/runs/42705268198) a échoué avant fabrication : pas d'autorisation implicite de repartir sur ce build. Les tests de démarrage `freeze_support()` ont depuis été adaptés ; seule une nouvelle recette complète du SHA final peut lever ce volet.

**Sans preuve de qualification de l'exécutable installé et sans suppression des blocages #432, #437 et #442, la RC10.56 reste suspendue.**
