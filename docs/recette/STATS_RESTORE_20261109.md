# STATS-RESTORE — lot initial de restauration (09/11/2026)

## Q3 — qualification autonome des caches et VFS natif (09/11/2026)

- **But :** qualifier le moteur Statistiques depuis ChatGPT classique par tests réels et isolés, sans Work/Codex et sans données PMSL. Ne pas assimiler ces essais à une recette de l'application installée.
- **CI initiale** [#42650313562](https://github.com/fr4nck/Noethys-SL/actions/runs/42650313562) sur wx `ecc226b0` : 2 273 tests exécutés, 1 FAIL (`tests.test_connecthys_situation.SituationConnecthysTests.test_raccordement_lecture_seule_de_la_fenetre_connecthys`) et 49 SKIP ; les tests STATS-RESTORE sont PASS. Ne pas ignorer ce FAIL dans le verdict global.
- **Épreuves ajoutées :** inventaire AST des 11 pages/33 objets, deux connexions SQL fictives avec même filtres, paramètres modifiés en place, stress de `wx.MemoryFSHandler` natif sous Windows (100 actualisations et 100 ouvertures/fermetures).
- **Test rouge probant** [#42654799081](https://github.com/fr4nck/Noethys-SL/actions/runs/42654799081) sur wx `3755fefe` : 30 tests ciblés, 28 PASS et 2 FAIL, démontrant contamination du cache `GetDictMembres` entre connexions et absence d'invalidation après mutation des paramètres.
- **Correction :** neuf caches répartis entre Individus et Familles sont attachés à la connexion de lecture, avec instantané des paramètres, et ne réutilisent plus un cache global commun. Références main `dd2fbf3f`, qt `7dfe1b1c`, wx `3f3fccba`. La CI [#42655909784](https://github.com/fr4nck/Noethys-SL/actions/runs/42655909784) a validé **30/30 tests ciblés** sur Ubuntu ; la partie Windows était encore en cours lors de cette consignation.
- **Cache géographique :** l'identité du cache inclut désormais l'origine, les destinations et les paramètres sur main `cc36bf43` et qt `3932ffa5` ; non encore reporté sur wx pour préserver la CI Windows en cours. L'appel réseau routier synchrone demeure ouvert.
- **Ce qui n'est pas qualifié :** vrai `wx.MemoryFSHandler` tant que la partie Windows de la CI n'est pas terminée ; 11 pages exécutées dans l'application installée ; comportement du dialogue principal, du zoom et de l'aperçu lors de cycles réels ; gels SQL/réseau ; validité métier du choix d'un QF à la date de référence ; MySQL réel ; issue #432.
- **Décision : STOP-GATE maintenu**, aucun installateur ni release publié, aucun test sur base utilisateur, aucune migration, aucun nettoyage destructif.

## R2 — intégrations vérifiées le 09/11/2026

- **Branches** : main `e8102100`, qt `7d13e38a`, wx `ecc226b0` (références de la session ; contrôler les HEAD avant poursuite).
- **Âges** : décennies entières, zéro distinct de l'inconnu, tri des valeurs manquantes ; tests ciblés PASS sur CI Linux wx.
- **Quotients** : tranches tarifaires exclusives ; modes Présents/Inscrits ; photographie des QF valides à la fin de la période des Présents, ou au jour courant pour les Inscrits. Plusieurs valeurs actives contradictoires -> catégorie « QF à vérifier » ; zéro reste numérique. Les cinq titres QF affichent la date. Cette politique exige une **recette métier** car plusieurs types de QF peuvent coexister.
- **QF tests** : test historique en Python et test SQL réel sur SQLite synthétique, sans base PMSL. La CI ciblée #42648922381 a révélé cinq erreurs (comparaison de l'étiquette avec un nombre + fixture AST sans datetime), corrigées sur les trois branches ; CI #42649372360 : job syntaxe et tests STATS-RESTORE **PASS** ; job Windows annulé par un autre push.
- **Images** : UUID par objet ; un seul enregistrement global du gestionnaire MemoryFS ; conversion avant remplacement de l'image ; tentative de libération à la destruction ; l'aperçu conserve une référence au moteur de graphiques. Tests isolés PASS sur la CI Linux, mais **fuites et comportement wx natif non qualifiés**.
- **Impression** : calcul uniquement des pages cochées et sélection effective des objets enfants ; tests isolés PASS.
- **Caches** : état validé seulement après réussite, copie des paramètres, fermeture SQL/figures sur les chemins corrigés ; test ajouté `tests/test_stats_restore_cache.py` sur trois branches ; CI Windows courante #42650313562 au moment de cette consignation : job syntaxe PASS, Windows encore en cours.
- **Concurrence GitHub** : changements Connecthys/Facturation sur wx observés et préservés ; aucun merge global ni force-push. CI précédente #42643880363 : un FAIL de contrat Connecthys sur 2 261 tests, indépendant de STATS-RESTORE ; à qualifier sur HEAD final.
- **Hors qualification** : 11 pages en application installée, impression/zoom wx réel, cycles de 100 ouvertures, mémoire, longueurs SQL, requête HTTP distances et stabilité de la fenêtre principale #432. STOP-GATE de publication maintenu. Aucune base réelle, migration, installateur ou release.


## État vérifié
- Audit statique sur les sources, aucune exécution de l'application Windows ou base de production.
- HEAD au prévol : main 07d672a2, wx bcc8a450, qt b6bc25ba.
- Commits : main a64cfa02 + 768fc03d + 7c102dc2 ; qt 0102723c + bb6cb702 ; wx c775c3a6 + b7cfa5e0.
- Fast-forward sans force, sans branche supplémentaire, aucun tag, migration, binaire ou release.

## Correctifs candidats, non qualifiés
1. Âges : classement entier 0–9, 10–19, etc., 0 distinct de l'inconnu, et tri compatible None. Test tests/test_stats_restore_ages.py.
2. VFS : nom d'image UUID distinct par objet pour prévenir la collision entre dialogues ; mise à jour du même objet conserve son propre nom. Test tests/test_stats_restore_vfs.py.
3. QF : partition exclusive des plages tarifaires imbriquées et réactivation de la branche « Inscrits ». Test tests/test_stats_restore_quotients.py.
Les trois changements de moteur ont été propagés à main, wx, qt sans écraser les adaptations wx.

## Limites restantes / STOP-GATE
- Les trois fichiers de tests existent dans GitHub, mais n'ont pas été exécutés sur les sources du dépôt dans cette intervention.
- Contrôles Python isolés réussis sur l'arithmétique des découpages QF et âges ; ils ne remplacent aucune recette SQL ni GUI.
- **QF historiques :** sélection du QF selon la période toujours non déterministe ; aucune règle métier inventée. Les 244 familles déduites de la capture restent conditionnelles.
- **VFS :** durée de vie et libération des ressources des anciens dialogues/aperçus pas encore assurées. Ne pas annoncer absence de fuite mémoire.
- **UI :** SQL individuel et rendus de graphiques peuvent toujours bloquer wx ; impression et réseau des distances restent synchrones ; issue #432 ouverte.
- Dernière CI étudiée #42599928647 sur ancien SHA : 2 FAIL / 2 248 ; aucune CI du candidat actuel exécutée.
- Suite : tests de régression ciblés puis CI Windows rapide, 11 pages, stress VFS natif, SQL synthétique, modèle QF historique, impression, HWND et non-régression Connecthys/factures.
- Aucun GO pour publication RC ; absence de test ne doit pas être assimilée à PASS.
