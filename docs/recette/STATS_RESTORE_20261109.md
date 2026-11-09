# STATS-RESTORE — lot initial de restauration (09/11/2026)

## Q3 — clôture du défaut MemoryFS natif, qualification partielle (09/11/2026)

- **Reproduction rouge :** [CI Windows #42655909784](https://github.com/fr4nck/Noethys-SL/actions/runs/42655909784), wx `3f3fccba` : les tests MemoryFS graphiques échouent malgré 100 actualisations internes, retour enfant Windows `0xC000041D`. Le test global compte 2 FAIL/2 274 tests et 49 SKIP, dont un FAIL Connecthys distinct.
- **Diagnostic causal A/B :** [#42661604488](https://github.com/fr4nck/Noethys-SL/actions/runs/42661604488), wx `da7a781d` : classe statique `wx.MemoryFSHandler` avec deux graphiques = PASS ; instance propre à chaque graphique = erreur/timeout. Les appels manuels directs à `__del__()` sont un scénario négatif non représentatif de la finalisation normale. Les méthodes VFS `AddFile` et `RemoveFile` sont statiques.
- **Correctif commun :** ne plus allouer de `wx.MemoryFSHandler()` dans chaque objet `HTML` ; `self.stockImages = wx.MemoryFSHandler`, gestionnaire global enregistré une seule fois ; tests de classe, de doublons, de destruction naturelle adaptés. Commits main `68bc99fe`, qt `66795742`, wx `fb1e320a`. Les interventions concurrentes sur wx sont conservées.
- **Vérification verte réelle :** [CI Windows ciblée #42662525508](https://github.com/fr4nck/Noethys-SL/actions/runs/42662525508) sur `fb1e320a`, **7/7 tests PASS**, processus terminé à code 0, incluant **100 actualisations**, **100 créations/libérations**, **202 consultations MemoryFS** et deux graphiques avec même code. Aucune preuve de consommation mémoire sur session très longue ni de recette de l'application installée.
- **Tests transversaux :** [CI rapide #42662525686](https://github.com/fr4nck/Noethys-SL/actions/runs/42662525686), job syntaxe Ubuntu PASS avec **33/33 tests STATS-RESTORE** (dont QF SQLite fictif, caches d'une connexion, inventaire, géographie). Son job Windows général a été **annulé après push concurrent Connecthys**, donc aucun PASS global sur ce SHA. Une nouvelle CI [#42662954493](https://github.com/fr4nck/Noethys-SL/actions/runs/42662954493) a été lancée sur `8e1aaf6e`, descendant de `fb1e320a` ; encore **en cours au contrôle**, donc résultat non préjugé.
- **Matrice 33 objets :** `STATS_Q3_MATRICE_20261109.md` répertorie 11 pages et 33 objets (inventaire AST PASS). Le banc VFS natif PASS concerne le composant graphique partagé, **pas chacun des 33 objets individuellement**, ni l'impression ou l'application installée.
- **Autres corrections qualifiées partiellement :** neuf caches par connexion, clé de cache géographique dépendant de l'origine et des destinations, suppression de `GetTitulaires()` inutile ; présentes dans les trois branches et testées avec fixtures sur Ubuntu. Le service de distances réseau demeure synchrone.
- **STOP-GATE RC maintenu :** politique métier QF multi-types et dates à confirmer, test SQL MySQL isolé absent, 33 objets SQL/graphique/impression non qualifiés individuellement, gel d'un traitement long, distances HTTP, stabilité du vrai HWND, impression/zoom sous Windows installé, CI globale non verte à la date du contrôle.
- Aucun jeu de données PMSL, migration, fichier utilisateur, installateur, tag ou release modifié ou produit durant ce chantier.

## Matrice détaillée Q3 — 33 objets

[Voir la matrice des 33 éléments](STATS_Q3_MATRICE_20261109.md). L'inventaire AST est PASS ; les colonnes SQL, métier, rendu, impression et Windows restent majoritairement NON TESTÉES à l'échelle de chaque objet. Ce document exclut tout faux GO par héritage d'un test transversal.

## Q3 — qualification autonome des caches et VFS natif (09/11/2026)

- **But :** qualifier le moteur Statistiques depuis ChatGPT classique par tests réels et isolés, sans Work/Codex et sans données PMSL. Ne pas assimiler ces essais à une recette de l'application installée.
- **CI initiale** [#42650313562](https://github.com/fr4nck/Noethys-SL/actions/runs/42650313562) sur wx `ecc226b0` : 2 273 tests exécutés, 1 FAIL (`tests.test_connecthys_situation.SituationConnecthysTests.test_raccordement_lecture_seule_de_la_fenetre_connecthys`) et 49 SKIP ; les tests STATS-RESTORE sont PASS. Ne pas ignorer ce FAIL dans le verdict global.
- **Épreuves ajoutées :** inventaire AST des 11 pages/33 objets, deux connexions SQL fictives avec même filtres, paramètres modifiés en place, stress de `wx.MemoryFSHandler` natif sous Windows (100 actualisations et 100 ouvertures/fermetures).
- **Test rouge probant** [#42654799081](https://github.com/fr4nck/Noethys-SL/actions/runs/42654799081) sur wx `3755fefe` : 30 tests ciblés, 28 PASS et 2 FAIL, démontrant contamination du cache `GetDictMembres` entre connexions et absence d'invalidation après mutation des paramètres.
- **Correction :** neuf caches répartis entre Individus et Familles sont attachés à la connexion de lecture, avec instantané des paramètres, et ne réutilisent plus un cache global commun. Références main `dd2fbf3f`, qt `7dfe1b1c`, wx `3f3fccba`. La CI [#42655909784](https://github.com/fr4nck/Noethys-SL/actions/runs/42655909784) a validé **30/30 tests ciblés** sur Ubuntu ; la partie Windows était encore en cours lors de cette consignation.
- **Cache géographique :** l'identité du cache inclut désormais l'origine, les destinations et les paramètres sur main `cc36bf43` et qt `3932ffa5` ; non encore reporté sur wx pour préserver la CI Windows en cours. L'appel réseau routier synchrone demeure ouvert.
- **Allègement de Coordonnées :** appel inutilisé `GetTitulaires()` supprimé sur main `2af709ed` et qt `6968bfb8` après lecture de sa définition (chargement complet de familles/individus/rattachements). Test fictif `tests/test_stats_restore_geographie.py` ajouté ; non encore qualifié en CI et non propagé sur wx. Le chargement initial des adresses et le service de distances synchrone restent ouverts.
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
