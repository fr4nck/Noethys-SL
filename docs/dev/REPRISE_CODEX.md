# Reprise du chantier Noethys-SL — état au 08/10/2026

## Recherche d'anomalies au démarrage — RC10.3 candidate (29/10/2026)

- Signalement : perte du plein écran pendant la recherche d'anomalies à l'ouverture. À la demande de l'utilisateur, rapprochement avec #432 Connecthys : le gel de la boucle wx et l'iconisation réelle ont été mesurés ; le mécanisme Windows Ghost a été reproduit mais l'origine exacte de l'action sur le poste reste non prouvée. Aucune maximisation compensatrice ajoutée.
- Prévol distant : main `4ba283557efde79cdd576d98ac6568ba87385b2b`, wx `8e4fcb2481eef20887c2bd63754789412615aa60`, qt `3b2e60336f80ab8712be8cfc6f3f63bdcd07e58e`. Arbre wx propre avant modification. Ancien chemin : les 18 contrôles et toutes leurs lectures occupent le thread wx, BusyInfo ne fait pas tourner la boucle pendant SQL.
- Correctif wx : connexion et lectures dans un même thread de recherche ; nom de fichier capturé avant ce thread, pas de consultation de widgets par le contrôle MySQL8. Même BusyInfo et mêmes textes. Boucle wx native et fenêtres désactivées pendant l'attente pour empêcher une seconde action ; timer sans propriétaire arrêté avant destruction. Connexion fermée et statut effacé même après exception. Requêtes et règles de détection conservées.
- Tests : comparaison des requêtes et résultats avec la méthode RC10.2 figée ; panne SQL, fermeture de connexion, MySQL8 sans lecture wx, textes inchangés et absence de restauration forcée. Recette graphique réservée au runner Windows isolé (consigne #432) : ancien blocage contre candidat, états maximisé/fenêtré/plein écran, géométrie, propriétaire Win32, battements, réactivation et erreur de worker. Résultats Windows et publication à qualifier avant toute annonce de version disponible ; aucune fenêtre de recette locale ni accès à la production.
- Validation locale : 58 tests, 56 PASS et 2 recettes graphiques réservées à la CI. Le test de démarrage par extraction AST, auparavant absent de ces sélections CI, omettait le diagnostic dans son faux environnement : ajout du mock manquant, sans modifier ses assertions ni le démarrage applicatif. Les contrats du changelog, de publication et de sauvegarde RC10.2 restent verts.
- Élargissement demandé par l'utilisateur aux passages individus/familles : neuf appels sans parent explicite corrigés (sept fiches, deux dialogues de rattachement), dans les deux compositions, l'archivage et deux listes d'anomalies. Aucun texte, style, ordre de sauvegarde ou règle métier modifié. Garde AST de tous les appels de fiches runtime et recette native des créations/modifications/retours, famille maximisée et fenêtrée ; comparaison à RC10.2 figée.
- Premier candidat `04d948b3` non publiable : build `40840003014` FAIL (1166 tests, 4 échecs) : deux attentes d'identité restées sur RC10.2, observation BusyInfo par proxies wx non concluante et arrêt fatal du sous-processus après panne simulée. Remplacement de cette observation par les HWND du seul thread de test, arrêt/détachement explicite des timers et destruction de l'application avant finalisation ; maintien des assertions de propriétaire et de sortie normale. Lecture simulée lente : candidat déjà réactif (47 ms) et géométrie inchangée dans le journal de panne, sans valeur de qualification complète. Capture du chemin local sur le thread wx pour éviter aussi le Customize consulté indirectement depuis GetRepData dans un worker SQLite.
- Deuxième candidat `355ee891`, build `40841378901` : recette courte FAIL, deux gardes BusyInfo natives ; sortie normale après panne désormais OK. Ancien blocage mesuré 1297 ms, candidat 47 ms ; la fenêtre et sa géométrie restent inchangées. Les 12 transitions famille/individu passent, sans perte de géométrie (le parent Python était absent, mais wx choisissait déjà le bon owner Win32 dans ce banc : aucune causalité terrain affirmée).
- **Cause commune vérifiée dans wxWidgets 3.2** : [busyinfo.cpp](https://github.com/wxWidgets/wxWidgets/blob/v3.2.8/src/generic/busyinfo.cpp) crée un wxFrame STAY_ON_TOP sans FRAME_FLOAT_ON_PARENT ; [msw/toplevel.cpp](https://github.com/wxWidgets/wxWidgets/blob/v3.2.8/src/msw/toplevel.cpp) impose alors un HWND parent nul. Le parent logique ne suffit donc pas. La contre-épreuve historique exige désormais cette absence native, et le candidat exige un propriétaire réel ; le test n'est pas simplement assoupli.
- Attente commune `UTILS_Attente.BusyInfo` : même panneau, message littéral, centrage, bordure, marges et minimum client 400x80 que wxBusyInfo ; propriétaire visible, FRAME_FLOAT_ON_PARENT, pas de STAY_ON_TOP, ShowWithoutActivating. Création/actualisation/destruction de widgets uniquement sur wx, y compris appel depuis un worker. Remplacement mécanique de 86 appels dans 58 modules, sans déplacer les traitements SQL/métier de ces autres appels. Cela corrige la gestion de leurs fenêtres, sans prétendre supprimer tous leurs calculs synchrones. Tests natifs du focus, owner, état, taille et captures comparatives du seul message fictif ; les attentes restent interdites en dehors de l'API commune par garde AST.
- Reprise après pause : wx distant `74a92014`, main `94cc7721`, qt `3b2e6033`. Le nouvel écran ALSH a été ajouté entre-temps ; **l'utilisateur demande explicitement son inclusion dans RC10.3**. WIP sauvegardé par stash conservé, fast-forward `355ee891 -> 74a92014`, réapplication ciblée sans conflit ni perte du menu ajouté. Deux suites ALSH ajoutées aux barrières CI. Les lectures SQL de cet écran utilisent la même attente réactive (connexion créée/fermée dans le worker, paramètres capturés avant), sans changer le calcul. Autodéconnexion retenue pendant une attente modale désactivant la fenêtre pour éviter une réentrée.
- Matrice : orchestration de l'interface wx = candidate sur wx ; main/qt NON APPLICABLE à cette livraison wx (aucun changement des règles métier partagées). Les correctifs de sauvegarde communs qualifiés précédemment restent présents. Pas de fusion globale, migration SQL ou changement de profil utilisateur.

## RC10.2 — correction limitée et retour à l’interface existante (28/10/2026)

- Retour utilisateur explicite : RC10.1 ouvrait la console Windows de mysqldump ; les changements de libellés et de parcours de dossier n’étaient pas demandés. Retrait du choix/mémorisation de dossier ajouté en RC10.1 et rétablissement des libellés traduits de RC10 (fixture de référence). Les données et préférences existantes de l’utilisateur ne sont ni supprimées ni modifiées par cette reprise.
- Correctif technique : CREATE_NO_WINDOW au lancement direct du client sous Windows ; sorties et diagnostics toujours redirigés, surveillance et nettoyage conservés. Trois tests de lancement (dont un véritable enfant Windows), garde des textes historiques et des styles de progression. Les tests du parcours retiré sont remplacés avec la fonctionnalité à la demande de l’utilisateur, pas pour masquer un échec de CI.
- Prévol : main `8504fea4`, wx `a21705c1`, qt `fa299114`. Correctif commun porté de façon ciblée sur les trois branches. Seul wx change d’identité publique pour livrer RC10.2 ; version interne inchangée. Aucune manipulation du processus de sauvegarde en cours ou de la production.
- **Validation locale** : 88 tests ciblés PASS sur chaque branche ; sur wx, 106 tests PASS avec la garde de publication RC10.2 et le changelog. Les textes traduits des deux modules de sauvegarde et les styles de progression sont comparés à RC10 ; un véritable enfant Windows est vérifié sans fenêtre console.
- **Candidat Windows qualifié** : wx `7456667913251e89d93ce298bdbf69e3955f36c7`. [CI rapide 40767372318](https://github.com/fr4nck/Noethys-SL/actions/runs/40767372318) SUCCESS (1530 tests, 0 échec, 40 ignorés conditionnels). [Build Windows 40767372422](https://github.com/fr4nck/Noethys-SL/actions/runs/40767372422) SUCCESS : contrats 1154 tests/0 échec/15 ignorés ; recette MySQL explicite 12 tests PASS/0 SKIP ; gros BLOB synthétique PASS ; inventaire du moteur, démarrage wx et deux démarrages portables avec profil conservé PASS. Artefact immuable `12852430895`, digest `3244adc74ff80c4893e1422e3366a5c6aef861a4c14766524d81a810350a17bc`. Publication ponctuelle préparée sur ce SHA et ces deux runs exacts, sans reconstruction ni remplacement de RC10/RC10.1. Aucun autre changement d’écran ou de texte fonctionnel demandé.
- **Publication vérifiée** : [RC10.2](https://github.com/fr4nck/Noethys-SL/releases/tag/noethys-sl-0.1.0-rc.10.2), préversion publique du 28/10/2026 à 21:14:15 UTC ; [publication 40770194104](https://github.com/fr4nck/Noethys-SL/actions/runs/40770194104) SUCCESS. Tag au candidat `74566679`, publication `32434ce9`, aucun binaire reconstruit. Setup 105 678 745 octets / SHA-256 `1a2c6471ea67650c902a86b3ec1b8cb7af4960ada70ab916ffcc86cce1dd5e55` ; portable 147 680 564 octets / SHA-256 `1c41cbcf1aed65fd91bda792bfc410f5a486ba0bf40b2023181d8e0b4913abf9`. Après téléchargement public : manifeste concordant, CRC ZIP, clients MySQL et provenance vérifiés, aucun profil ou identifiant embarqué. Fichiers livrés dans le dossier Téléchargements RC10.2 ; aucune installation automatique, aucun arrêt du Noethys actif et aucune manipulation de production.

| Correction applicable RC10.2 | main `4ba28355` | wx `74566679` | qt `3b2e6033` |
|---|---|---|---|
| Client MySQL sans fenêtre, textes et parcours antérieurs rétablis, protections techniques conservées | VALIDÉ : 88 tests ciblés locaux | VALIDÉ : 88 tests ciblés locaux, 106 avec publication/changelog, CI et runtime Windows ci-dessus | VALIDÉ : 88 tests ciblés locaux |
| Paquet public Windows RC10.2 | NON APPLICABLE | VALIDÉ : release et fichiers publics vérifiés | NON APPLICABLE ; aucun paquet Qt annoncé |


## RC10.1 publiée — sauvegardes Windows (28/10/2026)

- **Release publique** : [Noethys SL 0.1.0 RC10.1](https://github.com/fr4nck/Noethys-SL/releases/tag/noethys-sl-0.1.0-rc.10.1), préversion publiée le 28/10/2026 à 20:34:38 UTC. Tag léger et artefacts au commit qualifié `cfeccd499927319583b263b5361d9abbedeb6963`, pas au commit de publication `fbb6fa9d401924915cdec33afa7a0e6e98b764e2`. [Publication 40764456778](https://github.com/fr4nck/Noethys-SL/actions/runs/40764456778) SUCCESS, sans reconstruction. RC10 et les anciennes releases conservées.
- **Qualification** : [CI rapide 40762579606](https://github.com/fr4nck/Noethys-SL/actions/runs/40762579606) SUCCESS ; [build Windows 40762579762](https://github.com/fr4nck/Noethys-SL/actions/runs/40762579762) SUCCESS sur le même SHA. Exécutable, moteur inclus, clients MySQL 5.7 livrés, progression wx réelle, gros BLOB synthétique restauré, démarrages installable et portable, profil portable conservé, Setup/ZIP/empreintes validés. Les 4 nouveaux contrôles du workflow ponctuel ont aussi passé localement.
- **Assets vérifiés après publication et téléchargement** : Setup 105 696 644 octets / SHA-256 `5142e8e18eabda7bbdeaf13fbe06a48ce28741136d61666e4cecefdcb2166755` ; portable 147 679 430 octets / SHA-256 `8aa18246ba5037e2c26c6e43b74da7ef5e2af8142983b1190f0d7d9c2036b024` ; `SHA256SUMS.txt` présent et concordant. ZIP CRC, marqueur Portable, provenance `cfeccd49` et absence de Config.json/identifiants embarqués revérifiés sur les fichiers publics.
- **Portage du complément** : main `8504fea4220e5b81e2b71fedc70f3c302e91ea5a`, qt `fa299114069486e26e3a04af9f33ef6fbd7db8fd`, wx candidat `cfeccd499927319583b263b5361d9abbedeb6963` : moteur et choix de dossier identiques, 91 tests ciblés locaux sur chaque branche. Identité et paquet RC10.1 propres à wx ; aucune version Qt ou main annoncée installée.
- **Exploitation** : l'utilisateur installe volontairement RC10.1. Si l'ancien dossier est absent, choix d'un dossier existant puis mémorisation propre au poste après succès. L'agent n'a installé aucun binaire sur le profil réel, modifié aucune base de production ni lancé de restauration en production. Runtime, traces et téléchargement local restent hors Git ; aucune sauvegarde ou donnée des familles publiée. Issue #437 non fermée : l'ancien déclencheur serveur/réseau reste non attribué et le retour utilisateur sur la nouvelle version reste distinct des preuves techniques.


## RC10.1 / #437 — choix local du dossier et qualification Windows (28/10/2026)

- Demande explicite de fabrication et publication d'une nouvelle version Windows. Prévol : main `9ef81817`, wx `17b6e1d`, qt `b38c4cba`. Pas de fusion globale ni de modification des précédentes releases.
- Nouveau correctif partagé : si le dossier de la procédure est absent, choix explicite d'un dossier existant ; préférence propre au poste, mémorisée après succès dans le profil local, sans modifier le dossier SQL partagé. Écriture immédiate du profil car la fermeture générale l'enregistre avant les sauvegardes automatiques. Annulation/échec sans mémorisation ni purge. Le dossier réellement choisi dans l'interface optionnelle est celui mémorisé.
- Diagnostic de l'export : le code MySQL et la fin du diagnostic nettoyé sont visibles dans le message d'erreur, en plus du rapport JSON ; conservation de la vérification des secrets. Régressions de destination, annulation, réussite, persistance locale, dossier final et isolation des autres postes ajoutées aux tests et à la CI rapide.
- `wx` seul porte identité et notes RC10.1, nouveau workflow Windows et script portable distincts. Les notes historiques et la version interne `1.3.4.4` restent inchangées. `concurrent.futures.thread` explicitement embarqué et inventaire de l'exécutable exigé. Recette réelle avec progression wx et client livré, plus BLOB fictif >24 Mio sur MySQL 5.7.44 local jetable ; démarrages et persistance du portable conservés.
- Qualification locale du complément : **91 tests de sauvegarde PASS sur chacune des trois branches**, moteur/choix de dossier identiques. Sur wx, **9 tests réels PASS / 0 SKIP** sur MySQL 5.7.44 local jetable, dont vrai `wx.ProgressDialog`, authentification avec caractères spéciaux, refus d’identifiants, restauration et BLOB de 27 262 974 octets. Runtime de recette isolé (Python 3.10, mysqlclient 2.3.0, PyYAML 6.0.3) hors Git. Un défaut du lecteur de tests YAML sur une ligne vide a été corrigé sans retirer la comparaison PyYAML ni les gardes de publication.
- **Candidat Windows qualifié** : wx `cfeccd499927319583b263b5361d9abbedeb6963`. [CI rapide 40762579606](https://github.com/fr4nck/Noethys-SL/actions/runs/40762579606) SUCCESS (1518 tests, 0 échec, 39 ignorés conditionnels). [Build Windows 40762579762](https://github.com/fr4nck/Noethys-SL/actions/runs/40762579762) SUCCESS : contrats 1142 tests/0 échec/14 ignorés ; recette MySQL explicite 12 tests PASS/0 SKIP ; gros BLOB synthétique PASS ; moteur et exécuteur présents dans l'exécutable ; initialisation wx et deux démarrages portables avec profil conservé PASS ; Setup, ZIP et empreintes produits. Artefact immuable `12849222633`, digest `085214602c1e30db898a9b91b2174bd7364cd9baa89cecad6dcad543ce58cd37`. Publication ponctuelle préparée sur ce SHA et ces runs exacts, sans reconstruction ni remplacement de RC10.
- La fabrication est autorisée ; aucune installation ou restauration sur production par l'agent. Paquet en cours de qualification, aucune publication annoncée avant vérification du run, des assets et empreintes. Les nouvelles traces/archives de recette restent hors Git dans `sauvegarde-runtime-20261028`.


## #437 — sauvegarde complète après RC10 (28/10/2026)

- Prévol distant relu : main `7e874cba1f598621d82e5036b98519de87996b5c`, wx `2fb74017a9677540ecad72e434becf1762539ea1`, qt `6a70d59ba0b0ea071f8a2056920975e64485772a`, RC10 `d01566118f66775620d3df5e888bc50abfd4ecef`. Comparaison des fichiers : sauvegarde main/qt identique ; wx possède le watchdog `21ec1447` et les clients embarqués/identifiants quotés. `UTILS_Sauvegarde_auto` et `UTILS_SQL_Integrite` ont les mêmes blobs sur les trois. Portages ciblés, aucun merge global, aucune autre ligne de développement ni release remplacée.
- Moteur commun extrait de wx et renforcé : export direct borné, fichier de connexion explicite, gros BLOB en hexadécimal, options de filtrage refusées, fin de dump exigée, diagnostic exploitable sans secrets, dossier temporaire unique. Contrôle du dossier cible avant export, copie atomique et aucune purge après échec/annulation. Analyse longue hors du fil wx avec progression. Les méthodes de restauration de l'application restent inchangées.
- Blob commun `UTILS_MySQL_backup.py` : `337eada3c3f51d087150d8fcf01e34fa68c4c10d`. Tests Windows/Python 3.10.11 : main **84 PASS / 0 FAIL / 0 SKIP**, dont MySQL 5.7.44 réel local ; wx **83 PASS / 0 FAIL / 0 SKIP** ; qt **83 PASS / 0 FAIL / 0 SKIP**. Le moteur et ses tests communs sont byte-identiques sur les trois copies. Compilation ciblée et espaces contrôlés. CI distante à consulter séparément après enregistrement du lot ; aucun résultat de CI n'est présumé.
- Recette MySQL jetable : BLOB binaire de 27 262 974 octets, ancienne commande code 3/erreur 2020 ; nouvel export complet puis restauration avec même SHA-256. Garde hôte local/port 3407/datadir avant toute écriture SQL. Un vrai enfant Python bloqué est aussi arrêté et attendu sans réseau.
- Diagnostic opérationnel en lecture seule : dossier de la procédure absent du poste courant, attente illimitée RC10 confirmée. Le dossier absent explique un échec de copie, pas le blocage ancien d'un export. Les limites client/serveur ne démontrent pas la cause de l'ancien arrêt réseau. Les quatre éléments demandés ont été exportés, CRC/manifeste vérifiés puis restaurés uniquement sur le serveur jetable ; tailles, quantités et empreintes des documents comparées à la source et identiques. Aucune donnée, archive, connexion ou rapport privé dans Git.

| Correctif commun | main (prévol 7e874cba) | wx (prévol 2fb74017) | qt (prévol 6a70d59b) |
|---|---|---|---|
| Export, diagnostic, fin SQL et préservation des archives | VALIDÉ : 84 tests | VALIDÉ : 83 tests, même blob | VALIDÉ : 83 tests, même blob |
| Aller-retour du moteur sur MySQL 5.7.44 | VALIDÉ localement sur main | Même moteur ; import applicatif wx à qualifier | Même moteur ; UI Qt à qualifier |
| Nouveau paquet / déploiement d'une version Windows | EN ATTENTE | EN ATTENTE | NON APPLICABLE au lot |

- Sources et commandes : [guide sauvegarde #437](../diagnostics/SAUVEGARDE_MYSQL_437.md). Les fichiers opérationnels, preuves et runtime MySQL sont hors Git dans `sauvegarde-runtime-20261028`, à côté des copies de travail. Le serveur jetable est arrêté après recette, ses bases de restauration sont supprimées. Aucune modification de production, de profil ni de la procédure stockée, aucune restauration sur production, aucune migration, aucun tag/release/build. L'ancienne RC10 installée reste inchangée et son dossier de destination devra être choisi volontairement dans l'application. Issue #437 non fermée : la qualification graphique/packaging et l'attribution du blocage ancien sont distinctes de la sauvegarde obtenue.


## 28 octobre 2026 — mysqldump immobile pendant une sauvegarde de fermeture

- Incident terrain (5700X) : export de la base des documents interrompu ; SQL partiel d'environ 70 Mo, sans modification durant plus de 100 minutes. Les trois processus observes ont disparu. Aucune archive interrompue ne vaut sauvegarde restauree.
- Defaut confirme dans le code RC10 : lancement via cmd.exe, attente sans limite sur subprocess.communicate(). L'origine MySQL/reseau du blocage reste INCONNUE.
- Correctif candidat apres RC10 sur wx : invocation directe mysqldump avec les options historiques, suivi toutes les 2 secondes, abandon apres 600 secondes sans octets nouveaux ou 7200 secondes au total, arret du client avant nettoyage, suppression du ZIP partiel et des identifiants temporaires. Pas de changement SQL, de schema, de base PMSL ou de release RC10 deja publiee.
- Quatre tests AST fictifs : succes du ZIP, progression longue, processus immobilise, limite totale. CI rapide wx et candidat Windows verifies separement. Propagation vers main/qt reste a qualifier sur source et tests, sans merge global. Tests reel MySQL sur serveur jetable et recette Windows restent indispensables avant nouvelle publication.



## 2026-10-28 — Candidat cumulatif RC10 Windows wx (en attente de build)

- **Référence de diffusion** : RC9.1 `noethys-sl-0.1.0-rc.9.1`, commit `0eccac4acbda263e068ce1b007e27734a7b0af60`, publiée le 26/10/2026. Aucun remplacement du tag ni de la release RC9.1.
- **Branches prévol 28/10** : `main` `92ea80dc5ee6006ef0d285cd539b6be3582451e6`, `wx` `2104c352e5ec00f00233e113ca22b193dd8bdb9c`, `qt` `a830589b946c7c61d30bb4e8988ad8d36bda423c`. Le composant `UTILS_Suivi_fiches.py` est identique entre `main` et `wx` au SHA blob `53c035ed0e267f51e9f3db168dc2f133828fe0ac` : les rubriques médicales ne sont plus détaillées dans l'historique général. Les tests MySQL simulés et contrats B4 sont aussi sur wx. Ne pas fusionner globalement les prototypes de pointage de main.
- **Packaging** : nouvelle identité `Noethys SL 0.1.0 RC10`, nouvelles notes dans `Versions.txt` en tête, moteur numérique interne `1.3.4.4` inchangé. Nouveau workflow `noethys-sl-rc10-windows.yml` et script de recette portable `verify_windows_portable_rc10.ps1`, sans modifier le workflow historique RC9.1. Production de `Setup.exe`, `Windows-portable.zip` et `SHA256SUMS.txt` seulement après tests Windows ; déploiement interdît avant qualification.
- **Tests / sécurité** : tests de publication du workflow RC9.1 préservés ; contrôle de non-publication sur push et garde manuelle `publier=true` pour RC10 ; suites AEEH B3/B4, questionnaires repas #433 et Connecthys #435 ajoutées aux contrats du build complet. Téléchargement MySQL 5.7 pour banc CI uniquement avec SHA-256 figé ; aucun moteur OCR livré. Le traitement OCR local des fiches demeure EN ATTENTE DE QUALIFICATION et n'est pas indiqué comme disponible dans RC10.
- **Matrice** : `main` : règles communes AEEH/privacy qualifiées sur CI précédente ; `wx` : composants communs + interface + packaging RC10 CANDIDAT, CI rapide et build RC10 à vérifier sur SHA final ; `qt` : interfaces RC10 ABSENTES/non applicables à ce paquet. **Aucune version RC10 n'est réputée installable ou déployée avant la réussite du workflow complet et une recette graphique sur données fictives.**



## #436 B4 — sécurité historique et simulation des deux pilotes (28/10/2026)

- **B3 qualifié CI :** `main` #40654939570 SUCCESS et `wx` #40655529299 SUCCESS, mais ni recette graphique Windows, ni connexion MySQL réelle.
- **Risque découvert :** `OL_Historique` affiche les catégories et les textes d'action ; il n'a pas été prouvé que ses accès soient identiques à ceux de l'onglet Médical. Le service `UTILS_Suivi_fiches` garde désormais la **quantité** de rubriques parentales déclarées dans l'événement #41, mais plus leurs noms sensibles (PAI, allergies, traitements, vaccinations). L'événement demeure distinct d'une preuve sanitaire.
- **Nouveaux tests :** `tests/test_noethys_sl_suivi_fiches_mysql.py` : 10 scénarios SQL sous adaptateur **MySQL simulé** sans réseau, dont `FOR UPDATE`, paramètres `%s`, rollback et isolation. `tests/test_noethys_sl_suivi_fiches_wx_events.py` : 16 contrôles dynamiques des événements des boutons, sans `wx.App`, base ni impression.
- **Frontières :** pas de changement des tables, périodes AEEH existantes, droits, portail Connecthys hébergé, données PMSL, profil Portable, fiches PDF originales ni de Qt. La qualification d'un serveur MySQL fictif isolé, des habilitations historiques et l'ouverture réelle du dialogue wx demeure obligatoire avant production.
- **CI B4 :** résultats à suivre sur les HEAD exacts après publication (ne pas les annoncer PASS avant confirmation).



## #436 B3 — droits AEEH contrôlés et suivi des fiches parentales (28/10/2026)

- **Audit du code existant** : `aeeh_periodes` est le stockage canonique des périodes, `UTILS_AEEH_Periodes.ValiderPeriode` refuse déjà les chevauchements ; `DLG_Individu_medical`, `OL_Vaccins`, `OL_Vaccins_obligatoires` et `OL_Pb_sante` assurent déjà la saisie sanitaire. `historique` stocke date/heure/utilisateur/individu, sans nouveau champ. Aucun doublon médical ni seconde table AEEH.
- **Correction CI B2** : huit erreurs `NameError: VALEURS_AEEH` dues à l'extraction AST des méthodes du dialogue dans les tests, corrigées par récupération de la constante source au commit `0cd248bc`. La CI [#40653752294](https://github.com/fr4nck/Noethys-SL/actions/runs/40653752294) **SUCCESS**. Le précédent run [#40650814814](https://github.com/fr4nck/Noethys-SL/actions/runs/40650814814) reste bien marqué FAILURE historique.
- **Moteur commun main** : `754242e5` (testées localement : 22 vérifications SQLite fictives) ajoute `UTILS_Suivi_fiches`, le contrôle AEEH sur connexion commune et deux catégories de l'historique (40 période vérifiée ; 41 confirmation parentale reçue) sans migration de schéma. Une période AEEH n'est créée qu'après justificatif explicitement vérifié ; verrouillage de la ligne enfant et transaction commune avec l'audit ; en cas d'échec, rollback des deux écritures. Date sans terme uniquement si justificatif attestant explicitement un droit sans échéance ; `individus.aeeh` reste indépendant. La réception des rubriques parentales n'est pas une preuve de vaccination/PAI conforme ; aucune valeur médicale détaillée n'est journalisée.
- **UI wx ciblée** : une seule fenêtre déroulante `DLG_Reception_fiche_enfant` enrichie de deux boutons : enregistrement de la période justifiée et historisation de la fiche parentale signée après confirmation explicite. Source Pièces/papier, acteur et date de signature parentale distincts de la date de traitement. Réutilisation de l'onglet Médical et de la liste des périodes ; aucun OCR, aucun formulaire tiers. `tests/test_noethys_sl_suivi_fiches_wx.py` (11 contrôles statiques) ajouté à la CI rapide avec les 22 tests SQLite nouveaux.
- **Frontières** : main = service partagé, wx = service + UI, qt non raccordé. Aucune modification des branches par fusion globale, Connecthys tiers, dossier PMSL réel, profil Portable, réservation #435, modèles de PDF, schéma ni migration. Test MySQL réel et recette graphique Windows **non réalisés** ; résultats de CI B3 à lire après publication, ne pas annoncer de version déployée.




### #436 B2 - audit de l'existant et controle de dates AEEH (28/10/2026)

- **Audit avant code** : `DLG_Individu_medical` contient deja les vaccins (`OL_Vaccins`, `OL_Vaccins_obligatoires`), traitements et informations de sante (`OL_Pb_sante`). `DLG_Saisie_pb_sante` sait modifier dates, traitements et consignes, sous les permissions existantes. Pas de refonte de la vaccination ni de deuxieme dossier medical. La validite calculee du vaccin est differente de la verification parentale d'un justificatif. Aucun flux PAI valide et distinct n'a ete prouve. `UTILS_AEEH_Periodes` lit et valide les periodes, mais aucun editeur wx specifique de ces periodes n'a ete qualifie dans l'audit.
- **Lacune precise corrigee** : le dialogue wx `DLG_Reception_fiche_enfant` affichait seulement le nombre de periodes AEEH. Il affiche desormais leurs dates en lecture seule ; l'agent peut comparer des dates facultatives depuis la fiche recue avec les periodes deja stockees (controles `CTRL_Saisie_date.Date` existants et `ComparerPeriodeAEEH` partage). En cas de chevauchement/nouvelle periode, avertissement et arbitrage manuel, **aucune ecriture des periodes**. Un bouton ouvre directement l'onglet Medical de la fiche individuelle ; aucune validation des vaccins/PAI n'est realisee par ce bouton.
- **Protection de la saisie** : dates partielles et fin sans debut refusees ; relecture explicite exigee pour dates communiquees ; aucune alteration par defaut de l'AEEH si la question parentale est vide. La reponse AEEH explicite reste reportee dans le controle Identite et sauvegardee uniquement avec le bouton Ok existant.
- **Modification limitee a wx** : `noethys/Dlg/DLG_Reception_fiche_enfant.py`, `noethys/Dlg/DLG_Individu.py`, `tests/test_noethys_sl_reception_fiches_wx_periods.py` (12 tests sans wx.App), workflow rapide wx et `docs/metier/RECEPTION_FICHES_PARENTS_436.md`. Aucun changement des moteurs, de main/qt, des schemas, de Connecthys tiers, de la base PMSL ou du profil Portable.
- **CI avant ce sous-lot** : [main 40644787561](https://github.com/fr4nck/Noethys-SL/actions/runs/40644787561) **SUCCESS** ; [wx 40645096216](https://github.com/fr4nck/Noethys-SL/actions/runs/40645096216) **SUCCESS**. **CI de ce nouveau commit B2 et recette graphique Windows a confirmer**, aucune version publique annoncee.
- **Matrice de diffusion** : main = moteur B1, B2 non applicable (carrosserie wx) ; wx = B1 valide CI, B2 en qualification ; qt = raccordement absent et non touche.


### #436 - reception des fiches enfants, controle wx (28/10/2026)

- **Branche wx** initiale `70fa4a7ea44d053c0ec4b338643947b0ae05612b`. **Main** contient le noyau commun `cf447a6b221b357284b84d27ffcf11e1366f134b`. Pas de merge global, pas de nouvelle branche. Propagation ciblée sur wx du moteur d'accueil commun du premier lot #436 et de son test (33 cas), du moteur de contrôle de réception (18 cas) et de son test. Changements wx propres dans `noethys/Dlg/DLG_Individu.py` et `noethys/Dlg/DLG_Reception_fiche_enfant.py` avec 6 garde-fous statiques.
- **Audit réel** : Connecthys d'Ivan Lucas hébergé par un tiers reçoit déjà PDF/JPG/PNG dans « Pièces » ; `DLG_Saisie_portail_demande.Traitement_pieces` télécharge, déchiffre puis enregistre la pièce. Cela n'actualise pas les informations médicales ou AEEH de la fiche.
- **Raccordement wx de première étape** : depuis la fiche individuelle d'un enfant existant, `Outils → Contrôler une fiche enfant reçue`. L'opérateur doit consulter le PDF papier/portail dans l'onglet Pièces, confirmer l'enfant concerné et recopier explicitement Oui/Non/Non renseigné. Le dialogue compare à `individus.aeeh` via le contrôle Identité existant ; il ne fait AUCUN write SQL. C'est le bouton Ok habituel de la fiche individuelle qui enregistre. Les périodes AEEH sont lues comme référence et jamais modifiées ici ; les vaccins, allergies, traitements, PAI et consignes sont rappelés comme **à vérifier dans Médical**.
- **Tests locaux** : 18 PASS Python 3.13, compilation du dialogue wx PASS ; les 6 tests statiques wx compilent. Sur CI wx, exécuter les 33 + 18 + 6 tests et toute la recette rapide existante ; **résultat du nouveau run à vérifier séparément**. La fenêtre graphique n'a PAS été ouverte en local et une recette visuelle Windows demeure requise avant diffusion.
- **Non touchés** : bases réelles PMSL, profil Portable, portail Connecthys hébergé, synchronisation, tables, migrations, documents Pêle-Mêle originaux, réservations #435, facturation. Aucune promesse de classification automatique des PDF ni d'actualisation des périodes.
- **Matrice** : main = contrat commun en place ; wx = contrat commun ciblé + interface wx en qualification ; qt = interface Qt ABSENTE, contrat partagé à propager avant recette. Ne déclarer aucune release prête tant que la CI/recette de la version utilisée ne sont pas qualifiées.


## UI-432G — finalisation du lanceur de recette (27/10/2026)

- **Branche `wx`**, base `a24e1dd5` ; commit `6514740a` (lanceur + tests + CI). `main`/`qt` non modifiees. Moteur de synchro et correctif `dff8a13f` **non modifies** ; aucun benchmark relance ; aucune execution de Noethys, aucune base PMSL, aucun Connecthys.
- **Faux succes corrige** : l'ancien lanceur annoncait « CRITERES RESPECTES » des qu'aucun gel n'etait journalise, meme sans synchronisation. Nouveaux verdicts : REUSSIE (0) seulement si au moins une synchro terminee (`Temps upload_data`, imprime uniquement apres reponse `True` du serveur), sortie 0, diagnostic de la fenetre principale actif, aucune valeur hors schema ; NON RESPECTEE (10) gel >= 5 s (`retard_boucle`, `blocage_thread` ou `operation.sans_evenements_ms`) ou `ne_repond_pas=True` ; A REVOIR (11) iconisation de cause inconnue (`-IconisationVolontaire` a l'analyse) ; NON CONCLUANTE (12) sinon ; refus 2. Gels situes pendant/hors synchro (ordre `URL syncdown` -> `Temps upload_data`, sans copier l'URL).
- **Defauts corriges en plus** : regex de cle excluant les chiffres (`win32_*` auraient ete masques, decouvert par les tests) ; appels natifs git/python sous PowerShell 5.1 avec `ErrorAction Stop` ; format decimal dependant de la culture ; valeurs non typees (`true`, valeur collee a une autre ligne) desormais masquees.
- **Mode `-Analyser <dossier>`** : analyse seule, sans depot, Python, profil ni base ; sert aux tests et a la reanalyse.
- **Tests** `tests/test_ui432g_lanceur_recette.py` : 26 tests, journaux synthetiques (9 cas demandes + seuil 5000, gel hors synchro, journal absent, diagnostic inactif), refus sur depots git temporaires (depot absent, branche, correctif absent, modification locale conservee), contrat source (ASCII, aucune commande git destructive, pas de `Set-ExecutionPolicy`, ordre verification/lancement, diagnostic restaure). Local : **OK sous Windows PowerShell 5.1.26100 et PowerShell 7.6.9**. Ajoute a la CI rapide. CI `6514740a` : run [40512031029](https://github.com/fr4nck/Noethys-SL/actions/runs/40512031029) **SUCCESS, 1256 tests, 0 FAIL/ERROR, 32 SKIP (inchange), les 26 tests du lanceur executes sur le runner Windows**. Fiche/checkpoint `6c46c55d`.
- **Environnement** : `.venv` Python 3.11.9 / wx 4.2.5 / SQLAlchemy **2.0.52** (banc 2.0.55) : les 10 tests du correctif (dont export reel `Upload_data` compare aux sources, base fictive) **OK en 2.0.52** ; aucune mise a jour imposee.
- **Non execute par l'agent** : passage `-VerifierSeulement` du lanceur sur le depot reel (sonde `.venv`, controle des processus, profil) - refus anterieur du classifieur, non contourne ; chemin positif complet (sonde Python + marqueurs + lancement) non teste automatiquement. Premier pas du bloc utilisateur.
- **Matrice** : lanceur = outil de recette `wx` seulement (NON APPLICABLE main/qt) ; correctif du gel reel **EN ATTENTE DE RECETTE UTILISATEUR**. #434 (synthese des prestations) hors perimetre, non commence.
- **Prochaine action exacte** : l'utilisateur colle le bloc de `docs/recette/UI_432/RECETTE_UI432G.md` ; analyser l'extrait transmis (verdict, gels pendant/hors synchro, `point`).

## UI-432G — checkpoint du 27/10/2026 : gel pendant la synchro Connecthys

- **Branche `wx`**, base `9c2168f3` ; commits `191c9828` (banc) puis `dff8a13f` (correctif ; HEAD code `dff8a13fdc36cc0e7a913c0cef22497be0e6616e`). `main=f6f5ccdf`, `qt=f2316046` non modifiees. Aucune fenetre sur le poste utilisateur ; mesures locales sans fenetre (Python 3.10.11, wx 4.3.1) avec un venv isole SQLAlchemy **2.0.55** (version de la CI et du build Windows ; le Python local a 1.4.54, **non representatif** : l'ORM 1.4 emet un INSERT par ligne). Aucune base PMSL, aucun acces Connecthys, aucun email.
- **Banc** `tools/ui432_bench_upload.py` : vrai `Synchro.Upload_data` dans un thread `Noethys-Connecthys-synchro`, base Noethys SQLite fictive (`--familles N`), schema Connecthys de reference `tests/fixtures/connecthys_models_reference.py` (schema public GPL, sans donnees), hebergement local, syncup sur 127.0.0.1. Mesure : traitements wx du thread principal (500 appels = tick leger ; 100 000-200 000 appels = traitement de 0,2-0,25 s type grille), sonde GIL, phases, profil, empreinte complete de l'export. Pieges evites : le banc historique patchait `time.sleep` global (sonde en attente active) ; la mesure SQLAlchemy 1.4 n'est pas celle du produit.
- **Cause demontree (mecanisme)** : effet convoi GIL. wxPython relache le GIL a chaque appel ; pendant le Python pur du worker (construction ORM, un INSERT par ouverture/consommation, commit monolithique), chaque appel wx du thread principal attend le GIL. Micro-mesure : appel wx 0,0012 -> 0,32 ms sous worker CPU. Banc SA 2.0.55, 1000 familles (140 722 consommations, 25 320 ouvertures) : Upload_data 12,3 s ; traitement wx de 0,25 s -> **max 5,17 s**, ticks legers p95 578 ms / max 1 353 ms. Pistes rejetees mesurees : reduire `sys.setswitchinterval` (0,5 ou 0,2 ms) affame le worker (Upload_data 18 -> 107 s) ; insertion groupee seule = gain partiel (max 3,6 s).
- **Correctif `dff8a13f`** : (1) ouvertures et consommations construites par le modele telecharge puis `bulk_save_objects` par lots de 2000 ; (2) `noethys/Utils/UTILS_Priorite_ui.py` : ping `wx.CallAfter` ; si non traite en 50 ms, pause sans GIL jusqu'a son traitement (plafond 2 s puis tranche de 0,2 s garantie) ; inactif sur le thread principal et sans wx.App ; (3) `flush` tous les 500 `session.add` dans la meme transaction, commit final inchange. Download_data non concerne (volume = nouvelles demandes).
- **Mesures apres** (banc simule, SA 2.0.55, 1000 familles) : Upload_data 12,3 -> 6,3 s (interface libre) ; traitement de 0,25 s : mediane 1,14 -> 0,33 s, p95/max 5,17 -> 0,50/1,18 s ; ticks legers p95 578 -> 81 ms, max 1 353 -> 172 ms. Interface saturee en continu : la synchro s'allonge (25 s, 15 s de pauses), par conception. **Vraie boucle wx sur runner** (CI [#40496953017](https://github.com/fr4nck/Noethys-SL/actions/runs/40496953017), 400 familles, reference 206 ms) : avant mediane 316 / max **1 895 ms** ; apres mediane 238 / p95 405 / max **714 ms** ; Upload_data 7,5 -> 15,9 s sous interface saturee.
- **Equivalence de l'export** : 32 tables comparees ancien/nouveau (100 familles) : 30 identiques, 2 (`portail_individus`, `portail_users`) differentes aussi entre deux executions de l'ancien code (chiffrement a IV aleatoire/jetons) ; ouvertures et consommations conformes ligne a ligne aux sources (identifiants 1..N, ordre, valeurs). Aucune operation dupliquee : meme nombre de lignes par table, un seul fichier d'export, une seule requete syncup.
- **Tests** : `tests/test_connecthys_ui432_upload_cooperatif.py` (10 unitaires/integration + 1 vraie boucle wx reserve a `GITHUB_ACTIONS=true` sur Windows). Local SA 1.4 et 2.0 : 92 tests Connecthys cibles, seule erreur `psutil` environnementale connue. CI `dff8a13f` : **SUCCESS 1230 tests, 1198 PASS, 32 SKIP, 0 FAIL/ERROR, code 0**.
- **Limites** : le gel reel de 21-23 s n'est pas reproduit a cette amplitude ; le banc reproduit le mecanisme et une amplification x5-x20 d'un traitement d'interface concurrent. Le volume PMSL, MySQL (fetchall C) et la duree des traitements d'interface reels restent inconnus. Un `fetchall` C de ~0,25 s et des segments non instrumentes subsistent (max residuel 0,7-1,2 s).
- **Matrice** : wx = correctif VALIDE (banc + CI), recette reelle EN ATTENTE (`docs/recette/UI_432/RECETTE_UI432G.md`) ; main/qt = **ABSENT** (meme `session.add` par ouverture, pas de `UTILS_Priorite_ui`), propagation EN ATTENTE, distincte du portage logo, sans fusion globale. Issue #432 ouverte.
- **Lanceur de recette** `tools/ui432g_recette.ps1` (`a3d8a600`, fiche `1ed7384d`) : verifications (branche, correctifs dans HEAD, arbre propre, `.venv` = seul interpreteur avec mysqlclient : Python 3.11.9 / wx 4.2.5 / SQLAlchemy 2.0.52 / dateutil 2.9, code charge depuis le depot avec marqueurs, aucune autre instance) puis lancement avec diagnostic pour ce seul processus ; journaux sous `%LOCALAPPDATA%\NoethysSL-recette\`. Syntaxe validee par le parseur PowerShell ; **execution a blanc non faite par l'agent** (refus du classifieur sur `-ExecutionPolicy Bypass`) : premier passage `-VerifierSeulement` a faire par l'utilisateur.
- **Prochaine action exacte** : recette utilisateur ciblee (synchro automatique normale, NOETHYS_SL_UI_DIAG=1, criteres de la fiche) ; selon le journal, instrumenter les segments residuels (`point_synchro`). Ne pas relancer les mesures deja consignees.

## UI-432F — checkpoint du 27/10/2026 (session Claude Code locale)

- **Branche `wx`**, base `d4c2ee7d` ; commits `0ca53486` (campagne CI sur demande), `bb7dc1b6` (timer du diagnostic), `378673e3` (logo sans wx.Bitmap dans le worker + banc de signatures), `d3ac2113` (indicateurs fantome + isolation du test logo). `main=f6f5ccdf`, `qt=f2316046` non modifiees. Aucune fenetre wx ouverte sur le poste utilisateur : toutes les recettes graphiques tournent sur runner GitHub Windows isole (consigne permanente) ; local = tests sans fenetre (Python 3.10.11, wx 4.3.1).
- **Crash 0xC0000005 a la sortie — cause demontree, corrige.** Campagne [#40485960660](https://github.com/fr4nck/Noethys-SL/actions/runs/40485960660) (`tools/ui432_campagne_sortie.py`, `-X faulthandler`, scenario fictif `--corrige`) : base 3/30, veille neutralisee 0/30, veille jointe 2/30, `os._exit` 2/30 ; crash toujours dans `MainLoop` apres la mesure et avant le retour du scenario (donc pas la finalisation Python), veille inactive dans `Event.wait`. Trace (campagne v2) : `_on_destruction` est appele mais `event.GetEventObject() is self.fenetre` vaut **False 20/20** (autre proxy wxPython a la destruction) => le `wx.Timer(fenetre)` du diagnostic n'etait jamais arrete et visait une fenetre detruite. Correctif `bb7dc1b6` : timer sans proprietaire + arret si la fenetre n'existe plus. Campagne v2 [#40487850505](https://github.com/fr4nck/Noethys-SL/actions/runs/40487850505) : **0/60 base, 0/20 trace** (avant : 7/90 avec veille). Le CI push `0ca53486` (#40485947860, sans correctif) avait encore 2 sorties en 0xC0000005. Perimetre : diagnostic uniquement (`NOETHYS_SL_UI_DIAG=1`).
- **Audit des appels wx du worker Connecthys** : seule violation documentee = `wx.Bitmap` (objet GDI) cree/detruit dans le thread de synchro via `UTILS_Organisateur.GetDonnees(...).ConvertToBitmap()` puis `SaveFile`, a chaque synchro si un logo existe. Correctif `378673e3` : `GetDonnees(..., logoBitmap=False)` pour le worker (wx.Image, PNG direct) ; autres appelants inchanges. Mesure sur logos fictifs : transparence et pixels opaques identiques ; seuls les pixels semi-transparents differaient (perte d'arrondi de la premultiplication GDI, ecart compose <= 1 niveau) ; le PNG envoye est desormais identique a l'image recadree. Non corriges car non demontres nocifs : lectures `wx.GetApp().GetTopWindow()/GetName()` depuis le worker (`GestionDB.GetNomFichierDefaut`, `UTILS_Customize`). Aucun lien demontre entre ce bitmap et le gel reel.
- **Signatures du diagnostic (banc `tests/test_connecthys_ui432_signatures.py`, frame jamais affichee, run 40487836338)** : `wx` (sommeil thread wx 3 s) : retard 3000 ms, `veille_retard` 0, `point_synchro=aucune` ; `gil` (`PyDLL kernel32.Sleep` dans un thread de synchro) : `veille_retardee` 3000 ms + `point_synchro` present ; `sql` (attente de verrou dans `GestionDB.ExecuterReq`) : `point=GestionDB.py:ExecuterReq:280`, veille 15 ms ; `suspension` (NtSuspendProcess 3 s) : `veille_retardee` 3000 ms, aucun thread de synchro, pas de `blocage_thread`. **Limite** : `veille_retardee` seule ne distingue pas GIL et suspension/planification ; seule la presence simultanee d'un thread de synchro actif (`point_synchro`) oriente vers le GIL, sans le prouver.
- **Iconisation (H2)** : `d3ac2113` ajoute `ne_repond_pas` (IsHungAppWindow) et `fantome` (premier plan de classe `Ghost`) aux `blocage_thread`, et un cas CI `fantome` (frame visible gelee 9 s, reduction du fantome par le parent). **Reproduit sur runner** (CI [#40489318483](https://github.com/fr4nck/Noethys-SL/actions/runs/40489318483)) : apres ~7 s de gel, Windows cree une fenetre `Ghost` (`ne_repond_pas=True`, 1 fantome) ; le parent la reduit (`WM_SYSCOMMAND/SC_MINIMIZE`) ; apres le gel la vraie MainFrame est **iconisee** (`win32_iconise=True`, assertion du test). C'est le meme etat que le journal reel (`win32_iconise=True` pendant un gel de 23 s). Conclusion : l'iconisation est tres probablement une **consequence** du gel (action sur le fantome ou bouton de barre des taches), sans code Noethys en cause ; ce n'est pas prouve pour le poste reel (l'auteur de l'action reste inconnu). `fantome` (premier plan Ghost) est reste False sur runner alors qu'un fantome existait : indicateur faible ; `ne_repond_pas` est fiable. Aucun `Maximize(True)` ajoute : supprimer le gel reste la seule correction legitime.
- Tests locaux : `test_connecthys_ui3_diagnostic` 17 OK ; `test_connecthys_ui432_logo_worker` OK (comparaison en sous-processus). Le run push `378673e3` (#40487836338) affichait 1216 tests OK mais **code de sortie 1 sans trace** ; hypothese : `wx.App` persistante creee par le test logo dans le processus partage — test isole en sous-processus dans `d3ac2113` (2 SKIP supplementaires attendus dans le processus parent).
- **CI `d3ac2113`** [#40489318483](https://github.com/fr4nck/Noethys-SL/actions/runs/40489318483) : **SUCCESS, 1219 tests, 1187 PASS, 32 SKIP, 0 FAIL/ERROR, code de sortie 0** (le code 1 sans trace n'est pas reapparu : hypothese wx.App persistante compatible, 1 seule observation). Signatures confirmees (sql veille 0 + point GestionDB ; wx veille 0 ; gil veille 2500 + point_synchro ; suspension veille 3000 sans synchro).
- **Matrice** : wx = crash de sortie du diagnostic VALIDE corrige (0/80) ; bitmap GDI du worker VALIDE corrige (equivalence mesuree) ; diagnostic fantome VALIDE ; **gel reel ABSENT (non corrige)** ; iconisation = mecanisme reproduit, non corrige en tant que tel. main/qt : diagnostic UI = NON APPLICABLE (`UTILS_Diagnostic_ui.py` absent) ; correctif logo du worker = **ABSENT** sur `main` (f6f5ccdf) et `qt` (f2316046), verifie : meme `GetDonnees(tailleLogo=(200, 200))` ligne 622 et `ConvertToBitmap` ligne 88 ; propagation EN ATTENTE (adaptation ciblee et test, sans merge global). Issue #432 ouverte. Pas de ZIP, release, migration, synchro ni envoi reel.
- **Prochaine action exacte** : le gel reel (21-23 s pendant la synchro automatique, `upload_data` 18,6 s) reste a attribuer. Le diagnostic `d3ac2113`+ (NOETHYS_SL_UI_DIAG=1) discrimine desormais wx / SQL / GIL+synchro / suspension et signale `ne_repond_pas`. Sans nouvelle synchro reelle, piste suivante sur donnees fictives : profiler `Upload_data` sur une base SQLite fictive volumineuse dans un thread nomme pour mesurer la contention GIL effective (cpu Python pur) sur le thread wx. Ne pas relancer les campagnes de sortie deja qualifiees.

## UI-432E — checkpoint du 27/10/2026 (session Claude Code locale)

- **Branche `wx`**, local = distant après fast-forward `c4df895f -> f6cb2cdc` (3 commits UI-432C/D d'une autre session, aucun commit local perdu), puis code `3971396b3d7a74d2f1b1b3d15b4bcfcab1ca1445`. `main=f6f5ccdf`, `qt=f2316046` non modifiees. Non suivis conserves : `.venv/`, `artifacts-rc5..7/`.
- **Rattrapage de consignation** : `69792e68` (synchro manuelle `DLG_Portail_config` hors thread wx) CI [#40468378336](https://github.com/fr4nck/Noethys-SL/actions/runs/40468378336) SUCCESS 1173 PASS/30 SKIP ; `225e7fcf` (veille de pile UI) CI #40469725373 FAIL (casse `normcase`, test seul) ; `f6cb2cdc` correctif CI [#40474351455](https://github.com/fr4nck/Noethys-SL/actions/runs/40474351455) **SUCCESS : 1205 tests, 1175 PASS, 30 SKIP, 0 FAIL/ERROR**.
- **Recette reelle utilisateur a `c4df895f` : FAIL** (issue #432, 27/10 08:14) : retards wx 5,5 / 21,3 / 23,2 / 22,3 s ; MainFrame reellement iconisee pendant le pic (`win32_iconise=True`) ; `upload_data = 18,6 s` ; erreurs SQL 1267 (collations) repetees, incident SQL distinct, sans migration.
- **Analyse UI-432E (code, sans execution reelle)** : la synchro automatique tourne dans `CTRL_Portail_serveur.Serveur` (thread) ; les rappels `SetImage/EcritLog/SetGauge/SetEtatSynchro/MAJ_bouton` sont deja deportes par `wx.CallAfter`. Aucun appel `Iconize`/`ShowWindow` dans Noethys : l'iconisation n'a pas d'origine applicative identifiee. Hypotheses **non demontrees** : (H1) appel C conservant le GIL dans le thread de synchro (ex. `fetchall` mysqlclient d'un gros resultat), gelant aussi le thread wx — **affaiblie** : interface MySQL par defaut `mysqldb` (mysqlclient), dont `query`/`store_result` liberent le GIL et dont la conversion de lignes appelle des convertisseurs Python ; (H2) action Windows/utilisateur sur une fenetre « ne repond pas » (clic sur le bouton de barre des taches d'une fenetre active = minimisation) ; (H3) le thread wx attend une requete MySQL ralentie ou verrouillee pendant la synchro (signature attendue : `point=GestionDB.py:ExecuterReq` sans `veille_retardee`). Ecarts constates mais non qualifies comme cause : le thread de synchro touche wx (`GestionDB.GetNomFichierDefaut -> GetTopWindow`, `UTILS_Organisateur.GetDonnees -> wx.Image/ConvertToBitmap`, `logo.SaveFile`).
- **Commit `3971396b`** (diagnostic seulement, inactif sans `NOETHYS_SL_UI_DIAG=1`) : veille UI mesure son propre retard (`evenement=veille_retardee veille_retard_ms=`) et ajoute `point_synchro=fichier.py:fonction:ligne` du thread `Noethys-Connecthys-synchro`/`-manuel` ; le thread automatique est nomme. Tests locaux Python 3.10.11/wx 4.3.1 : 62 tests cibles, 61 PASS, 1 ERROR environnementale (`psutil` absent localement, test PASS en CI). CI [#40476188799](https://github.com/fr4nck/Noethys-SL/actions/runs/40476188799) tentative 1 : **FAIL** (1208 tests, 1 FAIL, 30 SKIP) : les 3 nouveaux tests PASS ; `test_contre_epreuve_etapes_gui_et_proprietaires` echoue car le sous-processus `--corrige` sort en `0xC0000005` (3221225477) **apres** avoir produit une mesure conforme (`retard_max_ms=359`, maximisee, geometrie et owner OK) — plantage pendant la destruction wx/interpreteur, veille diagnostic active. Lien avec `3971396b` ni demontre ni exclu. Tentative 2 (meme SHA, job relance une fois) : **SUCCESS, 1208 tests, 1178 PASS, 30 SKIP, 0 FAIL/ERROR**. Le plantage a la sortie est donc **intermittent** (1/2 sur ce SHA, absent des 4 runs anterieurs du test) : risque ouvert, cause non qualifiee. Piste si recidive : arreter et joindre explicitement la veille daemon avant la finalisation (atexit / destruction de la frame), puis comparer ; ne pas relancer a l'identique une troisieme fois.
- **Lecture du prochain journal reel** : `veille_retardee` eleve + `point_synchro` dans Noethys => H1 (GIL), corriger dans le thread de synchro (lecture par lots) ; `blocage_thread point=<fichier wx>` sans veille retardee => code bloquant sur le thread wx, corriger a ce point ; ni l'un ni l'autre => piste Windows/DWM.
- **Matrice** : wx = diagnostic `3971396b` VALIDE par CI (tentative 2) avec risque de sortie intermittente, correction du gel reel ABSENTE ; main/qt = NON APPLICABLE (diagnostic wx). Issue #432 ouverte. Pas de ZIP, release, migration, synchro ni envoi reel.
- **Prochaine action exacte** : jalon UI-432E commente sur #432 (ne pas dupliquer) ; obtenir une execution reelle normale avec `NOETHYS_SL_UI_DIAG=1` au SHA `3971396b` ou suivant (action utilisateur, hors poste de recette automatisee). Ne pas relancer cette CI ni redemander le meme commentaire.

## UI-432B — instrumentation des lectures individuelles (27/10/2026)

- **Branche wx uniquement**, base `3eeda62964dc12073f489af4e5279cbdd58aef14`, code `6c42d4c02b7b6d76170f411ff424e3e09301d42f`. Refs `main=f6f5ccdf` et `qt=f2316046` verifiees non modifiees. Aucune fusion ou branche supplementaire.
- Ajout de chronometrage **par etape nommee, allowlist et sans donnee personnelle**, uniquement avec `NOETHYS_SL_UI_DIAG=1`. Lectures de la grille, remplissage, calcul et affichage sont distingues. L'etape de calcul du remplissage et celle d'affichage ont des ticks wx distincts. Aucune requete SQL, fermeture de connexion, ecriture, transaction, email, jeton UI-3C.1 ou logique de traitement modifies.
- Tests ajoutes : journalisation inactive et anonymisee ; contre-epreuve d'une lecture artificielle de 3,465 s exigeant une mesure `etape=grille.activites`. Tests existants de modalite, proprietaire Win32, equivalence de grille et absence de reseau conserves. [CI rapide Windows #40460682032](https://github.com/fr4nck/Noethys-SL/actions/runs/40460682032) : SUCCESS sur le SHA du code, 1201 tests en 311,599 s, 1171 PASS, 30 SKIP, 0 FAIL/ERROR. Fenetre fictive maximisee et geometrie preservee, intervalle wx maximal 3609 -> 360 ms sur 21 appels, owner modal correct ; lecture individuelle fictive de 3465 ms : 3516 ms de blocage. Le test nomme l'etape fautive, sans supprimer ce gel.
- Une lecture SQL ou calcul individuel lent **reste bloquant** sur le thread wx ; le chronometrage le rend attribuable mais ne le rend pas asynchrone. `GetDictRemplissage` lit toutes les consommations de l'activite sur la periode, necessaires notamment aux calculs de remplissage : ne pas supprimer ce perimetre sans preuve metier et qualification. Le scenario entier de la video n'est pas rejoue. Pas de ZIP, tag, release, donnees PMSL, synchronisation ni email reel.
- **Matrice** : wx = instrumentation UI-432B VALIDEE par CI, recette graphique complete EN ATTENTE, main/qt = NON APPLICABLE pour cette instrumentation wx. L'issue #432 doit rester ouverte. Jalon suivant : analyser les etapes lentes mesurees sur fixture representative, verifier les phases traitement/calcul/sauvegarde/actualisation et la geometrie/focus du parcours complet avant de decider d'une mitigation non bloquante et d'un ZIP candidat.

## Issue #432 — amelioration ciblee, sous reserve (27/10/2026)

- Base distante verifiee : wx `2bf7dbe644e1672e44dd4df9b09f5d5b959c98a0`, main `f6f5ccdf6a491025db052b7759aa6facc01b2eca`, qt `f2316046f9f22ed59aeba33f9f8c090d3667ca06`, pas de master distant. Seul wx modifie, sans fusion ; travaux repas preserves.
- Diagnostic attache aussi a MainFrame, roles fermes principale/demande, enfants ignores, etat wx et Win32 distinct. Aucune maximisation corrective. Chargement automatique de la grille cachee fractionne sur le thread wx par attente modale, memes lectures et frontieres de connexion ; aucun worker SQL, ecriture ou email deplace.
- [Rapport P0 et contre-epreuves](../recette/UI_432_20261027.md) : retard maximal 3516 -> 343 ms pour 21 blocs fictifs (20 lectures et affichage), frame maximisee et geometrie identique, proprietaire Win32 correct. Vraies grilles SQLite artificielles identiques, dump SQL inchange pendant le chargement. 82 tests P0 PASS, puis 67 tests ciblant aussi les emails PASS (selections non disjointes), Python 3.11.9 / wx 4.2.5. Contre-qualification Python 3.10.11 : 13 PASS, intervalle maximal 3656 -> 360 ms. Compilation, diff et comparaison des methodes metier initiales PASS.
- **Limite reproduite** : une lecture fictive unique de 3465 ms produit encore 3500 ms entre battements. Verdict amelioration locale PASS, resolution complete NON DEMONTREE ; parcours complet video non qualifie. L'activation Computer Use a restaure la fenetre apres la mesure ; ne pas confondre cet effet de recette avec une action Connecthys. Aucun ZIP, tag, release, migration, acces PMSL, sync ou email reel.
- Matrice : wx = correction UI ciblee VALIDEE par CI sous limites, recette complete EN ATTENTE ; main et qt = NON PROPAGES, conformement au perimetre exclusif de cette session. UI-3C.1, suivis emails et metier preserves. L'issue #432 reste ouverte. Prochaine etape : qualifier la distribution des lectures et les phases calcul/sauvegarde/actualisation sur fixture representative, avant binaire candidat.
- Code pousse sur wx : `9edcc7dd57b807949f91888eac1b2153db394209` puis `80660c94cddbff431658d71fd2503c2f3449c906` (interruption du chargement refusee). Apres la derniere garde : 48 tests cibles locaux PASS. [CI finale #40456802574](https://github.com/fr4nck/Noethys-SL/actions/runs/40456802574) SUCCESS : 1200 tests en 297,473 s, **1170 PASS, 0 FAIL, 0 ERROR, 30 SKIP** ; les 4 tests graphiques nouveaux PASS. Sur ce runner : intervalle 3594 -> 344 ms ; lecture unique lente 3500 ms, toujours bloquante. Le run initial #40456232808 est annule par la concurrence, pas revendique comme qualifie. Resultats consignes sur l'issue #432 (commentaire 6434739150 et complement CI).
- WIP hors Git dans le miroir du projet : journaux `ui432-*.log`, processus de recette termines ; aucune modification du profil reel. Aucun packaging lance. La mise a jour documentaire suivante porte `[skip ci]`, sans modification de l'arbre executable qualifie.


## Lot 2C-3A — prévol financier / audit des tarifs sans écriture (26/10/2026)

- Base initiale `wx` `96bd9d40df3711ae36ed5b1b65d0bc5ddb7d3be5`, CI #40373448184 SUCCESS (1179 tests, 0 FAIL, 30 SKIP). `main`, `qt` et la release RC9.1 préservées.
- Audit du moteur `CTRL_Grille` : `tarifs` + `tarifs_lignes` + `combi_tarifs`/`combi_tarifs_unites`, prix pouvant être groupé sur plusieurs unités ; `prestations` liées par `IDtarif` et `IDfacture` ; paiements via `ventilation`. `unites.repas=1` indique repas inclus, sans prouver un prix repas distinct.
- Contrat additionnel `noethys/Utils/UTILS_Repas_tarifs_audit_2c.py` : `AuditerTarifsALSH` lecture SQL SELECT exclusivement et rapport sans personnes ; `ValiderAccordTarifSepare` refuse crédit/combinaisons/absence d'approbation ou de dates ; `SimulerNouvellePrestationPanier` garde zéro repas et accueil inchangé en exigeant une source datée, sans toucher aux écritures déjà facturées/ventilées. Tests sur base SQLite artificielle.
- **STOP-FINANCE** : non intégré à `CTRL_Grille` ou au cycle réel `MemorisePrestation`, aucune exonération comptable actuellement active. Manquent tarifs ALSH réels, source d'exception persistée par date, autorisations opérateur et recettage financier. Données fournies à ce jour MAD et pas ALSH.
- La qualification CI et les notes finales doivent être rattachées à l'issue #433 après publication ; aucune nouvelle RC automatiquement diffusée.



## Lot 2C-2 / 2C-3 — intégration panier familial sur wx (26/10/2026)

- Base `wx` `0eccac4a`, source 2C-1 `main` `f6f5ccdf`, `qt` non modifié. Moteur pur copié à l'identique, pas de fusion globale.
- Colonnes repas : quatrième choix facultatif (opt-in), « Repas apporté par la famille » hors commande ; présence méridienne déduite des horaires de journée/demi-journée, sans réservation repas des parents ; heures invalides ou partielles bloquantes ; standard par défaut uniquement si repas PMSL normalement prévu ; modèles trois choix conservés.
- Test de recette fictif : 30 présents, 24 standards, 3 sans porc, 2 végétariens, 1 panier, 29 repas fournisseur ; contrôles des combinaisons et totaux sans compter les paniers comme repas à commander.
- Module financier **pur seulement** : 0 € sur la composante repas séparée, tarif alternatif approuvé obligatoire pour journée incluant le repas, factures déjà émises non modifiées. **Ne fonctionne pas dans la facturation réelle : STOP avant usage métier, profils tarifaires ALSH non qualifiés**. Exceptions ponctuelles en mémoire seulement ; stockage par date encore à construire.
- Aucun changement à `CTRL_Grille`, aux prestations SQL, aux factures, à la déclaration CAF/AFAS, aux postes et profils PMSL ou à la release RC9.1. Après publication du lot, noter SHA, tests et matrice ; avertir que ce code est encore un candidat, pas une version à envoyer au comptable.
- Détails : `docs/metier/REPAS_LOT_2C_WX.md`, issue #433.


## RC9.1 — Correction ciblée du packaging Windows (26/10/2026)

- Diagnostic vérifié : le run de construction [40358267921](https://github.com/fr4nck/Noethys-SL/actions/runs/40358267921), SHA `9a91e9f9`, s'arrête au test `test_marqueur_visible_depuis_un_processus_neuf` de CE-4/CE-5 : `ModuleNotFoundError: No module named '_garde_reseau'` dans le subprocess ; 734 tests, 1 FAIL, 11 SKIP.
- La CI rapide [40358267781](https://github.com/fr4nck/Noethys-SL/actions/runs/40358267781) du même SHA est PASS (1139 tests, 0 FAIL, 30 SKIP). Sa différence causale est le `PYTHONPATH` Windows (`noethys`, `tests`, racine) absent dans le job `build` du packaging.
- Correctif : paramétrer le job Windows de construction avec la même variable que la CI rapide. Ajouter un test de garde comparant les deux workflows ; aucune modification à la logique Connecthys, aux tests métier, aux données ou à l'historique des notes de versions.
- Relancer uniquement le candidat `[candidate rc9.1]` sur `wx`, sans publication automatique. Vérifier le packaging intégral, le MySQL fictif, les démarrages, les artefacts et leurs empreintes avant déclaration PASS. Le bilan de recette Windows sur copie fictive reste indépendant et nécessaire avant usage comptable.
- Matrice : `main` et `qt` non modifiées ; `wx` seul concerné par la correction de CI ; la release RC9 demeure intacte.


## RC9.1 wx — Préparation de candidat du 26/10/2026

- Base ciblée : `wx` 21c4fc2a0b440d91d18d7fa582d91a9989fd982b (candidate RC9 Windows PASS, test rapide Windows 1139 PASS, 0 FAIL, 30 SKIP) ; `main` f6f5ccdf6a491025db052b7759aa6facc01b2eca ; `qt` f2316046f9f22ed59aeba33f9f8c090d3667ca06.
- RC9 officielle tag `noethys-sl-0.1.0-rc.9` conservee sans changement. Difference wx vs release RC9 : 17 commits (Connecthys UI, SMTP/Mailjet, protections relecture, regimes alimentaires Lots 1/2A/2B).
- RC9.1 : mise a jour de l'identite publique `noethys/Identite.py`, changelog d'application et notes de release, tests et workflow candidat, recette utilisateur. Version interne numerique du logiciel et historiques Noethys inchanges.
- Construction automatique sur push de workflow marque `[candidate rc9.1]`, sans tag ni release ; publication exige `workflow_dispatch` sur wx avec `publier=true` et apres succes integral. L'issue #433 du panier familial n'est **PAS LIVREE** : le lot pur 2C-1 n'est pas integre a wx, pas de tarif exonere, AFAS V1 toujours masque.
- Matrice : main (2C-1 contrat pur seulement), wx (regimes alimentaires Lots 1/2A/2B + Connecthys wx, version RC9.1 candidate), qt (pas d'UI repas Qt). Aucune fusion globale, aucune migration, aucune copie locale utilisateur modifiee.
- Verifier le SHA de publication, les jobs GitHub et les artefacts de recette avant le verdict candidat ; les operations manuelles sur base fictive et les garanties financieres restent a qualifier.
- Fiche `docs/recette/RC9_1_FICHE_RECETTE.md`, notes `docs/releases/noethys-sl-0.1.0-rc.9.1.md`.


## Restauration #430 — report des Lots 1, 2A et 2B sur `wx` (26/10/2026)

- **Base** : `wx` `769159452f3542416612c0c98ce96a9f09b59968` ; source `main` `887aec2469503713ad43bd6e7f75689a5ce414c8` (Lots `9be6dd91`, `0ef1f626`, `887aec24`) ; `qt` `f2316046f9f22ed59aeba33f9f8c090d3667ca06` non modifiée. Report ciblé par patch (diff `77c7efe2..887aec24` hors CI rapide et reprise), sans fusion globale.
- **Comparaison** : les 8 fichiers modifiés étaient identiques sur `wx` et sur `main` avant le Lot 1 (aucune adaptation `wx` écrasée) ; 6 fichiers nouveaux ; après application, 14 fichiers identiques à `main` ; seule la liste de la CI rapide `wx` reçoit les 4 nouveaux modules de test. Parcours email propre à `wx` (`DLG_Mailer`, `UTILS_Envoi_email`) non modifié et testé (brouillon simulé sans SMTP).
- **Tests locaux** : 321 tests OK (4 SKIP : MySQL sans serveur local, SMTP Python 3.12) — restauration, contrôle, PDF, brouillon, Mailjet/SMTP, contrats.
- **Matrice #430 (régimes)** : `main` VALIDÉ (`887aec24`, CI rapide 40335141950, MySQL 40335159437) ; `wx` voir CI du présent report ; `qt` EN ATTENTE (aucun écran Qt de commande de repas ; non déclaré fonctionnel).
- **Limites** : préférences non historisées (Lot 3) ; adultes à classer manuellement ; recette visuelle Windows EN ATTENTE ; aucune release.

## UI-3C.1 — barriere durable apres reservations incertaines (26/10/2026)

- Base reelle `wx` : `9c601b3f4e6be74bc4d05ee1862b85988d221a02`. Lire la [preuve CE-4/CE-5 et la procedure de reconciliation](../recette/UI_3C1_RECONCILIATION.md).
- Quatre contre-epreuves sur copie `git archive` du HEAD initial : **4 FAIL metier** (quantites doublees CE-4/CE-5, rejeu apres exception Save_grille, validation malgre retour False). Meme fichier de tests sur le correctif : **4 PASS** ; suite nouvelle **19 PASS**, UI-3C.1/UI-3C/UI-3B **35 PASS** et non-regressions ciblees **96 PASS** (Windows, donnees fictives).
- `UTILS_Portail_reconciliation` commite un jeton avant tout appel metier de reservation dans `parametres`, categorie dediee `noethys_sl_reservations_tentatives`, sans migration. Tentative incomplete/exception/lecture impossible : **aucun retraitement, aucune validation UI, aucun email**, reconciliation requise meme apres reouverture/processus neuf. Ni expiration ni reutilisation du suivi emails RC9.
- Resultat complet connu : reprise locale de la seule finalisation SQL UI-3C, suivis RC9 conserves apres refus ; retrait du jeton seulement apres commit confirme et actualisation, ou annulation manuelle avant Save_grille. Le retour False de sauvegarde est maintenant propage et refuse dans les deux modes.
- Matrice : `wx` **VALIDÉ par CI Windows** sur `ba5b71fda4c44bf76081ad049d1fcd39f75b87ef` ; `main` **ABSENT** (`77c7efe2b96bc2272f1130745a7a4aa5b832c0ed`) ; `qt` **ABSENT** (`f2316046f9f22ed59aeba33f9f8c090d3667ca06`). Fichiers de dialogue main/qt relus et identiques, aucune modification/synchronisation de ces branches.
- Limites : erreurs historiques masquees sans exception/False, tentatives anciennes sans marqueur, concurrence d'anciens clients ou SQL externe, moteur MySQL reel et recette graphique non qualifies. **STOP-GATE STABLE/release maintenu**. Aucun build, tag, release, deploiement, migration, donnees PMSL ni service de messagerie reel.
- Suite rapide locale Windows Python 3.10.11 / wx 4.2.5 : **1076 tests, 1049 PASS, 0 FAIL, 0 ERROR, 27 SKIP** ; compilation PASS. WIP local : copie du HEAD initial et journaux de tests hors depot ; six erreurs de nettoyage SQLite sous Python 3.11 reproduites sur ce HEAD, sans affaiblir de tests. Prochaine etape apres ce lot : recette graphique et qualification MySQL sur environnement fictif explicitement autorise.
- **Cloture CI** : code pousse uniquement sur `wx`, commit `ba5b71fda4c44bf76081ad049d1fcd39f75b87ef`, [CI rapide #40321502745](https://github.com/fr4nck/Noethys-SL/actions/runs/40321502745) **SUCCESS**, syntaxe et job Windows ; journaux : **1076 tests, 1049 PASS, 0 FAIL, 0 ERROR, 27 SKIP**, 316 s, dont les **19 nouveaux tests UI-3C.1 PASS**. CE-4/CE-5 FAIL sur le HEAD initial puis PASS dans cette CI. **PASS AUTOMATISE SOUS LIMITES**, aucun verdict STABLE. Une mise a jour documentaire seule avec `[skip ci]` suit cette qualification, sans modifier l'arbre executable teste.

## Cloture du lot UI-3C — 26/10/2026

- Derniere qualification du code : `wx` `c4dbc275a43e45a1f86a07070b5c2804a1f63aae`. CI rapide Windows [#40312052510](https://github.com/fr4nck/Noethys-SL/actions/runs/40312052510) SUCCESS, 1030 PASS, 0 FAIL, 0 ERROR, 27 SKIP.
- Seul le point de reprise est actualise ensuite en documentation avec `[skip ci]`, sans changer l'arbre executable valide. Les 3 branches ne sont pas fusionnees.
- Reprise technique suivante : stabiliser le cas fermeture forcee/redemarrage en presence d'une grille appliquee mais d'un statut `portail_actions` non valide ; etudier un marqueur persistant de tentative/reconciliation avant d'autoriser des relances, sans compromettre RC9 ni reutiliser les categories d'emails. En attendant, ce cas exige une verification humaine et bloque toute declaration STABLE.


## UI-3C — etat des demandes Connecthys apres echec SQL (26/10/2026)

- **Matrice inter-branches de ce correctif** : `wx` = VALIDÉ par CI rapide Windows sur `c4dbc275a43e45a1f86a07070b5c2804a1f63aae` ([run 40312052510](https://github.com/fr4nck/Noethys-SL/actions/runs/40312052510)) ; `main` = ABSENT (`77c7efe2b96bc2272f1130745a7a4aa5b832c0ed`) ; `qt` = ABSENT (`f2316046f9f22ed59aeba33f9f8c090d3667ca06`). Les fichiers historiques `noethys/Dlg/DLG_Saisie_portail_demande.py` de `main` et `qt` ont le meme blob `6a0d1d7e50b96463018d011f160279568ce7f983` : `track.Refresh()` y precede la requete `DB.ReqMAJ("portail_actions", ...)`. Le risque d'etat affiche non confirme persiste sur ces deux branches. Pas de fusion automatique ; STOP-GATE pour declaration de stabilite inter-branches.

- **BASE** : `wx` `c397fd4fd72246b2f36ce9f23c7c39f94a62c15e`, `main` `77c7efe2b96bc2272f1130745a7a4aa5b832c0ed`, `qt` `f2316046f9f22ed59aeba33f9f8c090d3667ca06`. Uniquement `wx` ; aucun changement aux autres branches ni a la preversion RC9.
- **DEFECT CONFIRME SUR LE CODE ANTERIEUR** : `Dialog.Sauvegarde` mettait a jour `track.etat/reponse/traitement_date` et appelait `track.Refresh()` **avant** le commit SQL. En cas de refus de `UPDATE portail_actions`, la base revenait a `attente` mais le track et le bandeau continuaient d'afficher `validation`. `Dialog.Traitement` ne lisait pas le booleen de `Sauvegarde` ; relancer `Traitement_reservations` pouvait rejouer `Save_grille` deja execute.
- **CORRECTIF WX** : `Sauvegarde` calcule l'etat souhaite sans muter le track ; seule une reponse SQL `True` autorise ensuite l'actualisation du track, des boutons et du bandeau. Un refus SQL restaure radio/date/reponse a l'etat connu du track (dernier etat charge ou sauvegarde par ce dialogue), sans faux `Refresh` annonceur de succes. `EnregistrerDemande` conserve son `UPDATE`, son `rollback()` et l'effacement transactionnel des suivis d'emails complets **strictement apres validation** ; aucune migration, aucun SQL additionnel.
- **PAS DE DOUBLE TRAITEMENT APRES ECHEC DE FINALISATION** : apres un retour metier `etat=True`, une fiche en attente conserve la reponse/date/IDaction figees. Une nouvelle tentative `Automatique`/`Manuel`, une fermeture ou une navigation retentent **uniquement** `EnregistrerDemande`, sans rappeler `Traiter`, `Appliquer_reservations` ou `Save_grille`. Les boutons sont proteges contre le second clic modal et les finalisations imbriquees. Si SQL refuse toujours, fermeture/navigation sont retenues pour conserver la reprise locale. Une simple saisie non persistable, sans traitement metier en attente, peut etre abandonnee apres restauration du track connu.
- **TESTS PERMANENTS** : `tests/test_connecthys_ui3c_sauvegarde.py`, vrai `EnregistrerDemande` sur SQLite temporaire, refus `UPDATE` injecte, comparaison avec `SELECT`, faux widgets wx, re-tentatives apres echec, absence de nouvelle execution de traitement, fermeture et navigation, rollback des suivis RC9 complets/partiels, reprise apres retour SQL. Aucun fichier `.nod`, email reel, reseau ni acces aux donnees PMSL.
- **LIMITES DE PREUVE** : l'etat restaure est le dernier etat *connu de la fiche*, suppose identique a SQL en l'absence d'ecriture concurrente d'un autre poste ; aucune relecture SQL supplementaire n'est engagee. La protection anti-double-traitement est **locale au dialogue ouvert** : apres crash/fermeture forcee/reouverture, les reservations deja appliquees peuvent demander une reconciliation manuelle. Les erreurs/effets partiels pendant `Save_grille` avant retour `etat=True` sont hors perimetre. **STOP-GATE pour release** tant que ces cas et la recette Windows sur le focus ne sont pas qualifies.
- **Resultat CI** : commit `c4dbc275a43e45a1f86a07070b5c2804a1f63aae` publie uniquement sur `wx` ; run [40312052510](https://github.com/fr4nck/Noethys-SL/actions/runs/40312052510) SUCCESS (1057 tests, **1030 PASS, 0 FAIL, 0 ERROR, 27 SKIP**). Contre-epreuves SQL/track/widget, refus multiples puis reprise, navigation/fermeture et suivi emails RC9 toutes PASS. **PASS AUTOMATISE SOUS RESERVES** : aucune recette de focus sur poste Windows, aucune idempotence durable apres crash/reouverture, aucun controle d'ecriture concurrente externe. Aucun build installateur, tag, release, migration SQL, envoi reel ou deploiement.


## Point de reprise — 26/10/2026

- Branche `wx` : code UI-2C/UI-2D qualifie sur `e7d8749e772d658d22dce846bc0a0bcb4366cb8f` par les CI [40306564973](https://github.com/fr4nck/Noethys-SL/actions/runs/40306564973) et [40307779012](https://github.com/fr4nck/Noethys-SL/actions/runs/40307779012). La documentation post-qualification ne change aucun code executable ; aucun build correctif, tag, release, envoi reel ou deploiement.
- Matrice UI-2C/2D : `wx` **VALIDÉ par CI** ; `main` **NON APPLICABLE** aux dialogues wx (SHA `77c7efe2b96bc2272f1130745a7a4aa5b832c0ed`) ; `qt` **NON APPLICABLE** aux dialogues wx (SHA `f2316046f9f22ed59aeba33f9f8c090d3667ca06`). Aucune fusion inter-branches n'a ete executee.
- Reste a prouver : comportement du premier plan sur une session graphique Windows avec candidat build du SHA final ; reactivite des traitements des reservations synchrones et validation du retour d'erreur lorsque l'enregistrement de `portail_actions` echoue. Les donnees PMSL restent hors recette.
- Prochain lot envisage : tester de maniere contradictoire `Dialog.Sauvegarde` et `Dialog.Traitement` : l'etat de `track` est actualise avant le commit SQL et `Traitement()` n'utilise pas le booleen renvoye par `Sauvegarde()`. Ne pas modifier cet enchainement sans tests de rollback et de non-double-traitement.


## UI-2D — renvoi unitaire SMTP/Mailjet apres reponse incertaine (26/10/2026, wx)

- Base de developpement UI-2C : `a2390f77e6c5fe65c48378683e184ac2a401bdcb` ; nouveaux changements exclusivement dans le Mailer wx. Les branches `main`/`qt` et la RC9 ne sont pas touchees.
- Risque code reproduit par contre-epreuve : l'ancien `_EnvoyerMessageUnique` offrait `Reessayer` apres une erreur generique pendant une emission et utilisait le parametre implicite `relancer_deconnexion=True`, y compris apres une reponse de SMTP ou Mailjet perdue. Un envoi accepte pouvait etre transmis de nouveau.
- Correction : `relancer_deconnexion=False` sur le worker unitaire ; seul un refus de Mailjet explicite HTTP 4xx ou une exception SMTP indiquant clairement un refus permet `Reessayer` manuellement. Les autres erreurs d'envoi/interruptions sont classees incertaines, avec seul bouton Terminer et sans repetition ; les erreurs de connexion ne sont pas considerees acceptees.
- `_envoi_en_cours` bloque le second clic pendant le Mailer unitaire ; le `finally` libere la garde et les images temporaires. Une panne d'historisation apres acceptation affiche un avertissement sans changer la reponse reussie ni reemettre l'email.
- Tests fictifs `tests/test_mailer_unique_uncertain.py` (SMTP et Mailjet, timeout apres DATA, refus certain, interruption UI, echec de connexion) et controles wx du bouton unitaire/historique dans `tests/test_vanilla_dlg_mailer_progress_parent.py`. Aucun email, base PMSL, secret, donnees reelles ou media.
- **Qualification obtenue** : commit `e7d8749e772d658d22dce846bc0a0bcb4366cb8f`, [CI Windows #40307779012](https://github.com/fr4nck/Noethys-SL/actions/runs/40307779012) SUCCESS : 1046 tests, 1019 PASS, 0 FAIL, 0 ERROR, 27 SKIP. Les simulations timeout apres DATA, Mailjet HTTP 400, historique indisponible, interruptions et double clic sont PASS. Le moteur historique `SmtpV2.Envoyer_lot` appele directement depuis d'autres ecrans reste hors de ce correctif ; ne pas annoncer de resolution complete des gels de fenetre avant recette graphique Windows.


## UI-2C — lots Mailjet visibles sans blocage HTTP (26/10/2026, wx)

- Base `wx` `56b3d19a647de0de9ef1f252585fa10c91ffac22` (UI-3B valide), `main` `77c7efe2b96bc2272f1130745a7a4aa5b832c0ed`, `qt` `f2316046f9f22ed59aeba33f9f8c090d3667ca06`. Lot wx uniquement ; ne pas annoncer de synchronisation des trois branches.
- Dans `DLG_Mailer.Dialog.Envoyer`, les lots Mailjet avec editeur visible et plus d'un destinataire utilisent le worker `_EnvoyerLotMailjetHorsUI` : connexions et requetes HTTP hors thread wx ; progression et historique sur wx. Les confirmations Connecthys avec editeur cache gardent leur chemin deja qualifie.
- Les choix interactifs `Reessayer` (seulement apres refus explicite), `Continuer`, `Continuer et ne plus signaler les erreurs` et `Arreter` restent disponibles pour les lots visibles. Une reponse perdue ou une exception apres une emission rend le resultat **incertain** : pas de reemission automatique de l'adresse concernee, conservation de la liste d'incertitudes et du bilan complet. Le mode silence saute les boites d'erreur suivantes mais continue a enregistrer leurs anomalies.
- `_envoi_en_cours` protege contre un second clic pendant un lot et sa liberation est dans `finally`. La fermeture de progression et la suppression des images temporaires sont conservees ; aucun changement de SQL, schema, regle de validation de demande ou empreinte de document.
- Contre-tests : `tests/test_connecthys_mailjet_lot_asynchrone.py` (acceptation, timeout, refus certain, silence, arret, worker interrompu), `tests/test_vanilla_dlg_mailer_progress_parent.py` (editeur visible et proprietaire, vrais controles wx, double clic). Ces scenarios utilisent seulement les donnees fictives `example.test`, jamais l'API reelle. **Commit `a2390f77e6c5fe65c48378683e184ac2a401bdcb` : [CI Windows #40306564973](https://github.com/fr4nck/Noethys-SL/actions/runs/40306564973) SUCCESS — 1037 tests, 1010 PASS, 0 FAIL, 0 ERROR, 27 SKIP.**
- Hors lot : `Mailjet.Envoyer_lot` appele directement par d'autres modules reste synchrone ; le chemin visible a un seul destinataire garde son propre parcours, cible du lot UI-2D pour les erreurs incertaines. Le focus et les longues sauvegardes de grille necessitent la recette Windows `docs/recette/UI_FOCUS_WINDOWS.md`.


Le verrou anti-reentrance UI-3B est publie dans `56b3d19a647de0de9ef1f252585fa10c91ffac22`, [run 40299997190](https://github.com/fr4nck/Noethys-SL/actions/runs/40299997190) SUCCESS : 1030 tests, 1003 PASS, 0 FAIL, 0 ERROR, 27 SKIP. Cela ne prouve pas la reactivite des sauvegardes synchrones sur poste utilisateur.

## UI-3B — protection contre la reentree Connecthys (26/10/2026, wx)

- Qualification de la base UI-2B : run [40297166024](https://github.com/fr4nck/Noethys-SL/actions/runs/40297166024), 1025 tests, 997 PASS, 1 FAIL (ancienne assertion statique sur le nombre de routes d'envoi), 0 ERROR, 27 SKIP. Le commit concurrent `57b9105` remplace le comptage fragile par des assertions sur les branches. La contre-qualification du correctif `57b9105` est [SUCCESS sur le run 40298190887](https://github.com/fr4nck/Noethys-SL/actions/runs/40298190887) : 1025 tests, 998 PASS, 0 FAIL, 0 ERROR, 27 SKIP. UI-3B peut etre publie puis qualifie separement.

- Baseline : `wx` `57b910565fdb37cf3a5850a59c28cd16fb89c229` ; `main` `77c7efe2b96bc2272f1130745a7a4aa5b832c0ed` ; `qt` `f2316046f9f22ed59aeba33f9f8c090d3667ca06`. Changement exclusivement wx ; aucune fusion et aucune synchronisation implicite.
- Un appel a `Dialog.Traitement` pendant un autre traitement sur le meme dialogue renvoie `False` immediatement ; la garde est liberee dans `finally` meme en cas d'erreur. Cela empeche la relance dans une boucle modale wx sans toucher aux operations metier.
- Test contradictoire `tests/test_connecthys_ui3_reentrance.py` : avec le meme corps de methode, 2 executions sans garde contre 1 seule avec la garde ; tests egalement de restitution du resultat, exception et reprise. Pas de bases, d'emails ou de données de familles.
- Limites : cette protection n'empeche pas un clic traite **apres** la fin du premier traitement. Elle ne deplace aucune sauvegarde synchronique, ne garantit pas la reactivite Windows et n'augmente pas artificiellement le focus. Qualifier avec la CI Windows du SHA pousse avant verdict.
- Publication uniquement par commit sur `wx` apres la qualification du lot UI-2B concurrent ; aucun tag, release ou deploiement.


## UI-2B — lots SMTP depuis l'editeur visible (26/10/2026, wx seulement)

- Baseline UI-3A `d7c9d031da9931afbfa94fc544237ddeb3ad8f41`. Correction ciblee : `DLG_Mailer.Dialog.Envoyer` passe aussi par `_EnvoyerLotSmtpHorsUI` pour les lots SMTP de plus d'un destinataire lorsque l'editeur est ouvert. Le moteur Mailjet visible reste sur `Envoyer_lot` historique (encore synchrone, UI-2C non qualifie).
- Connexion, transmission et temporisations SMTP en worker. Progression modale visible appartenant au Mailer. Historisation de chaque adresse acceptee sur le thread UI, pas de nouvel essai automatique apres resultat incertain, confirmations partielles et resume d'envoi conserves.
- Protections : `_envoi_en_cours` interdit le second clic pendant le lot; retour de l'etat a la fin meme en cas d'exception. Aucune transaction metier, aucune base de production et aucun mail reel dans les tests.
- Tests permanents avec moteur SMTP factice : deux destinataires, proprietaire de la progression, preuve de threads distincts du thread wx, anti double clic et maintien de l'affichage de l'editeur; AST du chemin conserve. La contre-qualification finale du routage SMTP visible et des tests de non-doublons est obtenue au commit `57b910565fdb37cf3a5850a59c28cd16fb89c229` (run [40298190887](https://github.com/fr4nck/Noethys-SL/actions/runs/40298190887), 1025 tests, 998 PASS, 0 FAIL, 0 ERROR, 27 SKIP).
- Limites a la date du lot UI-2B : Mailjet visible multi et les appelants directs de `Envoyer_lot` restaient synchrones. Le premier est cible dans UI-2C ; les appels directs demeurent hors perimetre.


## UI-3A — mesures optionnelles de la reactivite Connecthys (26/10/2026)

- Nouveau `UTILS_Diagnostic_ui.py` dans la seule branche `wx` ; inactif par defaut. Pour des mesures locales volontaires uniquement : `NOETHYS_SL_UI_DIAG=1` au demarrage de l'application. Aucun fichier n'est ouvert par le diagnostic ; lignes techniques dans la console seulement lorsque l'option est active.
- Mesure les etapes strictement techniques `demande.traitement`, `demande.enregistrement`, `demande.actualisation`, `reservations.initialisation_grille`, `reservations.calcul`, `reservations.sauvegarde`. Estime la duree de non-traitement des evenements wx a partir du battement de 250 ms ; trace activation, maximisation, taille de fenetre et iconisation sans identifiant.
- Journalisation a schema ferme : operation technique, duree, gap UI, type d'exception et booleens d'etat. Aucun identifiant, contenu de reservation, nom, adresse, montant, email, secret ou SQL n'est collecte.
- Aucun changement du moteur des consommations, aucune creation de thread SQL, ni `wx.Yield`. Mesures de recette sur Windows reel : **non qualifiees** a ce stade.
- Tests synthetiques permanents : `tests/test_connecthys_ui3_diagnostic.py`, inclus dans la CI rapide. Le commit `d7c9d031da9931afbfa94fc544237ddeb3ad8f41` a obtenu run [40295946780](https://github.com/fr4nck/Noethys-SL/actions/runs/40295946780) SUCCESS : 1022 tests, 995 PASS, 0 FAIL, 0 ERROR, 27 SKIP. Recette Windows sur poste reel encore non qualifiee.


## UI-1B — owner Win32 des alertes communes (26/10/2026, wx)

- `DLG_Messagebox.Dialog` retrouve la premiere fenetre visible en remontant ses parents. Un dialogue associe ne prend plus les styles `wx.STAY_ON_TOP` et `wx.DIALOG_NO_PARENT` : son owner Win32 est la fenetre visible. Les alertes reellement sans owner conservent leur style ancien.
- Contre-qualifications prevues sous Windows reel : `GW_OWNER`, dialog avec parent masque et ancetre visible, maintien du flag maximise. Tests dans `tests/test_vanilla_dlg_mailer_progress_parent.py`. **Run [40294795518](https://github.com/fr4nck/Noethys-SL/actions/runs/40294795518) SUCCESS** : 1015 tests, 988 PASS, 0 FAIL, 0 ERROR, 27 SKIP ; le focus en usage reel demeure non qualifie.
- Ce changement ne touche ni Mailjet, ni les tables SQL, ni les dossiers locaux, ni les regles de confirmation RC9.


## UI-2A — SMTP masque hors boucle wx (26/10/2026, branche wx)

- Baseline: UI-1 `c28f319af8b33da7596b928214388c648e0ad056`.
- Les confirmations Connecthys sans editeur utilisent desormais `_EnvoyerLotSmtpHorsUI` lorsque le moteur n'est pas Mailjet : Connexion/SMTP/fermeture sur un worker avec progression modale rattachee a la fenetre Connecthys visible ; preparation des messages, historique et boites d'erreur sur le thread UI.
- Une connexion SMTP est reconstruite pour chaque message ou essai, sans reutiliser la socket fermee. La temporisation entre messages et par quota SMTP demeure hors thread UI. Pas de deuxieme tentative automatique en cas de reponse incertaine pendant l'envoi (notamment SMTPServerDisconnected) ; conservation de `listeSucces` et `listeIncertains` pour le suivi Connecthys RC9. Un simple echec avant l'envoi peut etre retente explicitement par l'utilisateur.
- Au moment du lot UI-2A, les envois interactifs de plusieurs destinataires utilisaient encore `Envoyer_lot` synchrone. Depuis le commit UI-2B `e553cc3`, le lot SMTP visible emprunte un worker ; cette extension garde une qualification distincte. Mailjet visible multi reste synchrone. Les tests UI-2A utilisent uniquement des messages fictifs ; aucune connexion ni email reel.
- Tests cibles : `tests/test_connecthys_smtp_lot_asynchrone.py`, `tests/test_vanilla_dlg_mailer_progress_parent.py`, `tests/test_connecthys_ui1_dialog_owner.py`; CI et recette Windows doivent etre verifiees sur le SHA final. Pas de release.


## UI-1 : proprietaires des dialogues (26/10/2026, wx)

Base: wx 54482ba6c64faecf1603b6ab3fc73ad391719220. Corrige l'ouverture involontaire du Mailer cache lors des erreurs de validation; utilise une fenetre affichee comme proprietaire des alertes et de la progression. Le traitement des reservations rattache son avertissement a Connecthys. Le bilan Mailjet accepte un parent facultatif, compatible avec les appels existants. Aucun code SQL, aucune regle d'acceptation, aucune migration, aucune donnee reelle modifies.

Tests de contrat: tests/test_connecthys_ui1_dialog_owner.py. Les comportements du gestionnaire de fenetres et les blocages UI prolonges exigent encore une recette Windows; ne pas confondre CI et validation humaine. UI-2/3/4 non termines.

## RC9 — lot 7 : vérification du paquet existant et recette (24/10/2026, wx uniquement)

- **Candidat conservé** : `ed30b3c90d1472328a5ad760fc7a43395fa64fd9`, run [40101261780](https://github.com/fr4nck/Noethys-SL/actions/runs/40101261780) ; aucune reconstruction, aucun tag ni release.
- **Inspection du binaire préparée, NON EXÉCUTÉE** (récupération de l'artefact hors de l'autorisation reçue) : `scripts/inspecter_paquet_rc9.py` (tailles et SHA-256 contre les empreintes consignées ; présence dans l'archive PYZ de `Noethys.exe` des modules des correctifs, avec marqueurs propres à la version construite ; chargement au démarrage d'après les journaux de diagnostic du build) et workflow `.github/workflows/noethys-sl-rc9-inspection.yml` (lancement manuel, `contents: read`, `actions: read`, lecture des artefacts du run indiqué, PyInstaller 6.22.3 pour la lecture, aucun programme du paquet exécuté). Marqueurs validés sur les sources : 0/27 manquant pour `ed30b3c`, 24/27 manquants pour RC8.1 `00f53db` (les marqueurs distinguent la version). Procédure locale équivalente : récupérer l'artefact `Noethys-SL-0.1.0-rc.9-Windows-candidat` et les diagnostics, `pip install pyinstaller==6.22.3`, puis `python scripts/inspecter_paquet_rc9.py <dossier_artefact> <dossier_diagnostics>`.
- **Persistance depuis l'application** (réglage modifié dans l'interface, fermeture normale, relance) : aucune automatisation graphique disponible ; contrôle laissé à la recette manuelle (fiche, A.1).
- **Fiche de recette** réordonnée : `docs/recette/RC9_FICHE_RECETTE.md` (parcours ordinaires A.1 à A.5, essais de panne et de concurrence sur copie isolée B, réserves Connecthys C).

## RC9 — lot 6 : qualification MySQL et candidat Windows de recette (24/10/2026, wx uniquement)

- **Autorisation** du 24/10 : qualification MySQL sur machines GitHub (MySQL 5.7.44 officiel, empreinte vérifiée, base fictive jetable) puis build candidat `publier=false`. Aucun téléchargement sur poste utilisateur, aucune base PMSL, aucun email réel.
- **Révision** : depuis `21986c4`, uniquement documentation et notes jusqu'à `fb71d98`. Ajouts ensuite : `0ce9321` (tests MySQL Connecthys `tests/test_connecthys_reprises_mysql.py`, 7), `2834078` et `ed30b3c` (corrections des scénarios de test MySQL, voir ci-dessous), `e93b2bc` (`BUILD-INFO.txt` du build aligné sur le contenu réel de RC9 : l'ancienne ligne « création automatique des cotisations toujours suspendue » était inexacte). Aucun code applicatif modifié depuis `21986c4`. **SHA construit : `ed30b3c90d1472328a5ad760fc7a43395fa64fd9`** (contient `Versions.txt` et notes finales ; n'est pas identique à `21986c4`). `2ed884b` ajoute ensuite seulement la fiche `docs/recette/RC9_FICHE_RECETTE.md` (hors paquet).
- **Qualification MySQL** (`noethys-sl-rc9-qualification.yml`, lancement manuel) :
  - run [40099435437](https://github.com/fr4nck/Noethys-SL/actions/runs/40099435437) sur `0ce9321` : 25 tests, 2 FAIL dus aux scénarios — panne de commit injectée sur la validation préalable de lecture faite sous MySQL avant toute écriture (message « Rien n'a été modifié » alors exact) ; paramètre `type_2` orphelin dans la fixture, repris sans écriture par la création (ID 2). Corrigé dans `2834078` (autre type réel, panne sur le commit qui suit les écritures, état inchangé vérifié).
  - run [40100224576](https://github.com/fr4nck/Noethys-SL/actions/runs/40100224576) sur `2834078` : 24 PASS, 1 FAIL (requête de contrôle sans filtre comptant l'autre type ajouté) ; corrigé dans `ed30b3c`.
  - **run [40100719254](https://github.com/fr4nck/Noethys-SL/actions/runs/40100719254) sur `ed30b3c` : SUCCESS, 25 tests, 25 PASS, 0 FAIL, 0 ERROR, 0 SKIP** : 7 historiques (adhésions/inscriptions 4, concurrence 2, activités 1), `test_noethys_sl_type_cotisation_mysql` 10 PASS + 1 contrôle de sélection, `test_connecthys_reprises_mysql` 6 PASS + 1 contrôle de sélection. Archive MySQL : « SHA-256 conforme ».
- **CI rapide** : `ed30b3c` run [40100716304](https://github.com/fr4nck/Noethys-SL/actions/runs/40100716304) SUCCESS, 997 tests, 970 PASS, 0 FAIL, 0 ERROR, 27 SKIP (dont 17 tests MySQL sans serveur dans ce workflow).
- **Build candidat** : run [40101261780](https://github.com/fr4nck/Noethys-SL/actions/runs/40101261780) (`workflow_dispatch`, `publier=false`) sur `ed30b3c` : job build SUCCESS (permissions `contents: read`), **job de publication ignoré** ; aucun tag ni release `noethys-sl-0.1.0-rc.9` (API : 404 pour les deux). Contrôles du paquet :
  - contrats du candidat : 589 tests, 581 PASS, 0 FAIL, 8 SKIP, dont les suites RC9 connecthys_reprises 16, confirmation_partielle 15, mailjet_lot_asynchrone 9, piece_quotient_dialog 8, type_cotisation_saisie 4, type_cotisation_erreurs 23, impression_depot_perimetre 13 (tous PASS) — exécutés depuis le code source sur le runner ;
  - identité publique `Noethys SL` / `0.1.0-rc.9` / `0.1.0 RC9` ; version interne relevée par le binaire au démarrage : `1.3.4.4` ;
  - sauvegarde/restauration MySQL 5.7.44 jetable avec les clients livrés : 11 PASS ;
  - exécutable installable : `ETAPE oninit_fin` à 0,87 s, aucune exception ;
  - ZIP portable (binaire) : profil créé par le binaire au premier lancement (2 s), `Config.json` conforme ; **valeur de contrôle écrite par un script Python externe** (`UTILS_Config` du code source, non par le binaire) ; second lancement du binaire (10 s) : valeur toujours présente (le binaire n'a pas réinitialisé la configuration ; la relecture par le binaire n'est pas prouvée) ; aucun profil créé ni modifié hors `Portable/` (vrai profil Windows surveillé) ;
  - modules des derniers correctifs : non inspectés dans le binaire ; inclusion déduite de l'analyse des imports par PyInstaller (non vérifiée directement).
- **Artefacts de recette (non publiés, rétention jusqu'au 23/11/2026)** : `Noethys-SL-0.1.0-rc.9-Setup.exe` SHA-256 `4868cb4c8bc6be9da02e71941c5b36915a6a1cef56634996a954587a4883fddf` ; `Noethys-SL-0.1.0-rc.9-Windows-portable.zip` SHA-256 `93fd107ccfbd45371ab242eef9dd75b1ccfe68bda2ee0bbd3ceb9044d9a0d9c8` ; artefact GitHub `Noethys-SL-0.1.0-rc.9-Windows-candidat` (ID 12562843285, 251 479 079 octets, empreinte `sha256:ce21d075b06595ffeb0743e01ee75b1b3b169e070dd54ca8b97bc4886ace69e4`) ; diagnostics `Noethys-SL-0.1.0-rc.9-diagnostics-demarrage` (ID 12562718915, 14 997 octets). Tailles unitaires du Setup et du ZIP non relevées (artefacts non téléchargés).
- **Qualification Connecthys obtenue** : MySQL (6 tests) — verrou nommé d'une même confirmation entre deux connexions, suivi conservé sur panne après suppression, validation de `portail_actions` et nettoyage du suivi complet dans la même transaction (rollback vérifié), envoi partiel puis complet, deux traitements simultanés (un seul envoi) ; SQLite local — même jeu (16) en CI Windows. Transporteur factice uniquement : Mailjet et SMTP réels non exercés.
- **Verdict** : **CANDIDAT PRÊT POUR RECETTE** (non prêt pour production). Fiche : `docs/recette/RC9_FICHE_RECETTE.md`.

## RC9 — NO-GO, lot 5 : clôture transactionnelle (24/10/2026, wx uniquement)

- **Type de cotisation, reproduit sur `cbbdd46`** (4 FAIL métier, `tests/test_noethys_sl_type_cotisation_erreurs.py` rejoué sur une copie `git archive`) : le mode était écrit après `DB.Commit()`/`DB.Close()` par `EnregistrerModeAssociation` (autre connexion) ; son échec laissait type et unités enregistrés (création avec « Participations », changement de mode avec unités modifiées) ; valeur inconnue supprimée puis recréée ; mode devenu invalide depuis l'ouverture sans effet sur l'écriture du type.
- **Correctif `dc9a3fa`** : type, unités et mode sur la même connexion, dans une transaction ouverte avant toute écriture par `UTILS_Adhesions.VerrouillerParametrageType` (SQLite : `BEGIN IMMEDIATE` ; MySQL : `types_cotisations`, `unites_cotisations`, `parametres` InnoDB exigées avant écriture sinon `TransactionsNonSupportees` sans conversion, verrou nommé par type existant, `START TRANSACTION`). `_EcrireMode` : ligne valide identique non réécrite, valeur inconnue mise à jour en place, doublons réduits à la première ligne, ce seul type. Signature (type, unités, mode) relue à l'ouverture et sous verrou : modification faite ailleurs refusée sans écriture. Échec du commit ou du rollback : issue « indéterminée » (jamais « Rien n'a été modifié »), nouvelle validation bloquée jusqu'à réouverture. `EnregistrerModeAssociation` n'est plus appelé par le dialogue (inchangé pour les autres usages). Contrat « service sans DELETE » de `UTILS_Adhesions` conservé.
- **Tests type** : `test_noethys_sl_type_cotisation_erreurs` 23 (dont commit/rollback en échec, deux fenêtres concurrentes, verrou tenu, MyISAM simulé refusé) ; `_saisie` 4 (adaptés : l'échec du mode n'enregistre plus rien) ; contrat `_adhesions_inscriptions_wx` adapté.
- **MySQL préparé, NON EXÉCUTÉ** : `tests/test_noethys_sl_type_cotisation_mysql.py` (10 : sauvegarde complète, création, panne à chaque étape avec état identique, échec du commit, réparation d'un doublon et panne pendant la réparation, fenêtres concurrentes, verrou tenu par une autre connexion, deux créations simultanées, table MyISAM refusée sans conversion) ajouté à la commande du workflow `noethys-sl-rc9-qualification.yml` (+ test permanent vérifiant cette sélection). Workflow non lancé (autorisation distincte requise ; téléchargement de MySQL 5.7.44).
- **Connecthys, reproduit sur `cbbdd46`** (6 FAIL métier, `tests/test_connecthys_reprises.py`, classe `ReprisesTests` limitée à l'API commune) : suivi perdu par une panne entre effacement et réinsertion ; suivi effacé à l'envoi complet avant l'enregistrement de la demande (renvoi à toutes les adresses) ; relance après réponse perdue et après interruption (adresse acceptée renvoyée) ; suivi corrompu lu comme vide ; deux traitements simultanés. Reprise après redémarrage : déjà correcte.
- **Correctif `21986c4`** : suivi JSON v2 (acceptées, incertaines, empreinte, complet ; ancien format liste relu) écrit en une transaction ; `LireSuivi` lève `SuiviIllisible` (jamais « vide ») ; suivi conservé après l'envoi complet et effacé par `EffacerConfirmationsCompletes` uniquement s'il est complet, dans la transaction de `EnregistrerDemande` (UPDATE `portail_actions` contrôlé, erreurs non masquées) ; acceptation incertaine (`DLG_Mailer.listeIncertains`, Mailjet hors UI) ou envoi interrompu : adresses marquées incertaines, aucune relance automatique, diagnostic journalisé ; empreinte du document (réponse : modèle + texte ; reçu : règlement ; facture : numéro, dates, total) : document modifié = nouvel envoi légitime ; éditeur d'emails toujours disponible ; `Reserver` : un seul traitement par confirmation (processus ; `GET_LOCK` en MySQL). Aucun état, réponse ou paramètre `portail` modifié.
- **Limites Connecthys** : pas de garantie « exactement une fois » ; une panne du poste entre l'acceptation par le serveur et l'écriture du suivi reste possible (l'historique des emails de DLG_Mailer en garde trace) ; l'incertitude n'est détectée que sur le chemin Mailjet hors UI (SMTP : échec = non accepté, comportement historique) ; en SQLite multi-postes (partage réseau), la réservation ne protège que le poste courant ; empreintes du reçu et de la facture limitées aux champs listés.
- **CI rapide** : `dc9a3fa` run [40097847411](https://github.com/fr4nck/Noethys-SL/actions/runs/40097847411) SUCCESS 963 tests, 952 PASS, 0 FAIL, 11 SKIP ; `21986c4` run [40098487463](https://github.com/fr4nck/Noethys-SL/actions/runs/40098487463) **SUCCESS 990 tests, 969 PASS, 0 FAIL, 0 ERROR, 21 SKIP** (connecthys_reprises 16/16, confirmation_partielle 15/15, type_cotisation_erreurs 23/23, _saisie 4/4, impression_depot_perimetre 13/13, type_cotisation_mysql 1 PASS + 10 SKIP sans serveur). Build candidat et workflow MySQL : ignorés. Aucun tag ni release.
- **Candidat final (préparé, non construit)** : code figé à `21986c4` (commits suivants : documentation seule). Les suites RC9 (connecthys_mailjet_lot_asynchrone, confirmation_partielle, reprises, piece_quotient_dialog, type_cotisation_saisie, type_cotisation_erreurs, impression_depot_perimetre) figurent dans la liste du build `noethys-sl-windows.yml`. Lancement prévu, sur autorisation : `workflow_dispatch` sur `wx`, `publier=false` ; contrôles : démarrage réel jusqu'à `oninit_fin`, deux lancements du ZIP portable avec persistance de `Config.json`, empreintes SHA-256. Le paquet de diagnostic du run 40072909737 (`1ab469e`) ne contient aucun correctif des lots 2 à 5.
- **Réserves ouvertes** : qualification MySQL (workflow à autoriser) ; build candidat final (à autoriser) ; recettes manuelles Windows : écran type de cotisation (messages d'échec, d'issue incertaine, de modification concurrente), confirmations Connecthys réelles en environnement de test, pièce + quotient illimité, aperçu/impression d'un dépôt (13 colonnes, pagination), ZIP portable.

## RC9 — NO-GO, lot 4 : impression des règlements d'un dépôt (24/10/2026, wx uniquement)

- **Comparaison (lecture du code)** : RC8.1 (`00f53db`) imprimait la grille elle-même (13 colonnes métier dans l'ordre affiché, titre « Liste des règlements »), mais l'aperçu sortait vide. Le correctif `b2e0d9f` (instantané `_VueImpressionDepot`, conservé) imprimait 8 colonnes (perte d'Avis, Compte, Différé, Attente, Quittancier), dans l'ordre de `donnees` et non dans le tri affiché (la liste trie sa propre copie), avec un titre ne distinguant pas une liste filtrée par compte ou mode (fenêtre d'ajout au dépôt). Le total était déjà calculé sur les lignes de la liste, en flottants. Défaut établi par lecture du code et par l'ancien test (8 colonnes attendues) ; les nouveaux tests n'ont pas été rejoués sur l'ancien code (wx réel requis, non disponible hors CI).
- **Colonnes** : 13 colonnes métier (Date, Mode, Émetteur, N° pièce, Famille, Payeur, Montant, Avis, Compte, Différé, Attente, Quittancier, Observations). Non imprimés : l'ID technique (largeur nulle) et les icônes (mode, émetteur) ; l'icône « avis non envoyé à une famille abonnée » devient le texte « Non envoyé ». Largeurs réparties pour le paysage, textes longs à la ligne.
- **Ordre et périmètre** : lignes = `GetFilteredObjects()` (ordre et filtre de la grille). Titre « Règlements du dépôt - Dépôt complet » / « Règlements disponibles - Liste complète » ou « … - Vue filtrée » ; conclusion : périmètre, filtre compte/mode, « N règlement(s) imprimé(s) sur M » et total (Decimal, au centime) des seules lignes imprimées. Filtre sans résultat : message, aucun aperçu. Liste vide : message d'origine conservé. Aucune écriture en base.
- **Tests** : `test_noethys_sl_impression_depot_perimetre` (13 : colonnes et valeurs, montants positifs/négatifs/nuls/absents, libellés longs et accents dessinés, tri croissant/décroissant, dépôt complet, vue filtrée à plusieurs, un et zéro résultat, règlements disponibles, document multipage avec en-têtes sur chaque page et toutes les lignes dans l'ordre, dépôt verrouillé et non verrouillé, aucune mutation de la base, aperçu vide interdit) ; `test_noethys_sl_impression_depot` mis à jour (13 colonnes). Ajoutés à la CI rapide et, avec les tests RC9 des lots 2 et 3, à la liste du build candidat.
- **Qualification CI** : CI rapide [40094216727](https://github.com/fr4nck/Noethys-SL/actions/runs/40094216727) sur `584d372` **SUCCESS** — 949 tests, 938 PASS, 0 FAIL, 0 ERROR, 11 SKIP (dont type_cotisation_erreurs 9/9, type_cotisation_saisie 4/4, impression_depot 9/9, impression_depot_perimetre 13/13). Run précédent [40093531294](https://github.com/fr4nck/Noethys-SL/actions/runs/40093531294) sur `71c2c77` : 1 FAIL d'assertion de test (total attendu `8460.0` au lieu de `8460.00`), corrigé dans `584d372`. Run sur `d6c0da1` annulé par la concurrence (couvert par les suivants). Build candidat : job ignoré ; aucun tag ni release RC9 (API : 404).
- **Réserves ouvertes** : MySQL (concurrence, rollback, réparation du mode) non qualifié ; frontières transactionnelles Connecthys (mémoire des adresses acceptées hors transaction avec l'envoi) non clôturées ; recette visuelle Windows (aperçu réel d'un dépôt, lisibilité de 13 colonnes, impression papier, écran type de cotisation, confirmations Connecthys, pièce + quotient illimité) ; qualification du paquet final (nouveau diagnostic de démarrage réservé au candidat).

## RC9 — NO-GO, lot 3 bis : contre-épreuve et pannes SQL du type de cotisation (24/10/2026, wx uniquement)

- **Méthode** : `tests/test_noethys_sl_type_cotisation_erreurs.py` exécute les vraies méthodes `Importation` / `OnBoutonOk` sur un hôte sans fenêtre et une base SQLite fictive ; pannes SQL injectées au curseur de GestionDB (ReqInsert renvoie `None`, ReqMAJ/ReqDEL n'émettent rien). Rejoué sans modifier les références Git sur deux copies `git archive` : `a0d8f6e` (avant correctif) et `00c97ed` (premier correctif).
- **Défauts reproduits sur `a0d8f6e`** (6 FAIL, 3 ERROR, tous métier) : unité insérée deux fois au second OK ; suppression rejouée (2 DELETE) ; ouverture impossible (`ConfigurationAdhesionInvalide` dans `Importation`) ; faux succès quand la base refuse la création du type (unités écrites avec `IDtype_cotisation` nul), l'insertion, la modification ou la suppression d'une unité.
- **Défauts encore reproduits sur `00c97ed`** (5 FAIL) : les quatre faux succès ci-dessus, aggravés pour l'insertion (unité marquée enregistrée alors qu'elle ne l'était pas) ; réparation du mode interrompue après la suppression des doublons : une ligne arbitraire restait et devenait un mode valide en silence.
- **Correctif** : type, unités et remplacement d'un mode signalé invalide écrits dans **une seule transaction** par écritures contrôlées (`_Ecrire`, curseur direct, erreurs non masquées) ; en cas d'erreur, rollback, message « Rien n'a été modifié », fenêtre ouverte, liste des unités inchangée. Identifiants et états des unités réécrits seulement après validation. Le remplacement du mode cible `categorie='noethys_sl_adhesions_activites' AND nom='type_<ID>'` uniquement ; `UTILS_Adhesions` reste sans DELETE. Aucune écriture sur `cotisations` ni `prestations` (vérifié à chaque test).
- **Résultats** : 9/9 PASS sur le code corrigé (banc wx simulé) ; `test_noethys_sl_adhesions` 36, `_inscriptions` 14, `_inscriptions_wx` 4 PASS. Concurrence et rollback MySQL : **NON QUALIFIÉS** (workflow MySQL non lancé ; sur tables MyISAM, pas de rollback possible).

## RC9 — NO-GO, lot 3 : saisie des types de cotisation (24/10/2026, wx uniquement)

- **Anomalies traitées (audit différentiel)** : n°4 (unités insérées une seconde fois quand `EnregistrerModeAssociation` échoue puis qu'on revalide : les identifiants insérés n'étaient pas réécrits dans la liste) ; n°11 (mode d'association en double ou invalide : `LireModeAssociation` levait dans `Importation`, type impossible à ouvrir et seule réparation possible par SQL) ; n°10 (effet du mode par défaut « inscriptions » sur les types existants non documenté).
- **Correctif** : `DLG_Saisie_type_cotisation.OnBoutonOk` réécrit l'identifiant de chaque unité insérée, remet son état à `None` et oublie l'identifiant d'une unité supprimée ; une nouvelle validation ne rejoue ni insertion ni suppression. `Importation` capture `ConfigurationAdhesionInvalide`, mémorise l'erreur (`mode_association_invalide`) et la signale après ouverture (`wx.CallAfter`) ; la validation ne garde alors qu'une ligne de paramétrage de ce type (`SupprimerDoublonsModeAssociation`, table `parametres`, catégorie `noethys_sl_adhesions_activites`, aucune autre table touchée) puis `EnregistrerModeAssociation` y écrit le mode choisi. La suppression reste hors de `UTILS_Adhesions` (contrat « service sans DELETE » conservé) ; si elle échoue, `EnregistrerModeAssociation` refuse encore le doublon et la fenêtre reste ouverte avec le message d'erreur. Sans validation explicite, le double paramétrage reste refusé et la création automatique des adhésions de ce type reste bloquée. `Versions.txt` et notes RC9 : effet du mode par défaut documenté.
- **Non traité** : pas de contrainte d'unicité (pas de migration) ; deux postes MySQL peuvent encore créer un doublon simultané, désormais signalé et réparable depuis l'écran. Réparation non exécutée sur MySQL réel (workflow MySQL non déclenché).
- **Tests** : `test_noethys_sl_type_cotisation_saisie` (nouveau, wx réel, CI rapide), `test_noethys_sl_adhesions_inscriptions` (+1 : valeur inconnue remplacée par le mode validé), contrat de `test_noethys_sl_adhesions_inscriptions_wx` mis à jour.
- **Qualification CI** : CI rapide [40084104995](https://github.com/fr4nck/Noethys-SL/actions/runs/40084104995) sur `12febd7` **SUCCESS** — 927 tests, 916 PASS, 0 FAIL, 11 SKIP (Windows, wx réel), dont les 4 tests du dialogue. Échec des nouveaux tests sur l'ancien code non démontré en CI (raisonnement seulement). Aucun build candidat, tag ni release. Reste : recette Windows de l'écran (paramétrage, message d'avertissement, nouvel OK), réparation non exécutée sur MySQL réel.

## RC9 — NO-GO, lot 2 : confirmations Mailjet/Connecthys (24/10/2026, wx uniquement)

- **Anomalies traitées (audit différentiel)** : sémantique incohérente d'une confirmation partielle (SMTP : validée ; Mailjet : refusée) et renvoi aux adresses déjà acceptées lors d'un nouvel essai ; moteur Mailjet message par message appliqué à tous les lots, y compris depuis l'éditeur affiché ; tests Mailjet asynchrone et pièce/quotient absents de toute CI.
- **Correctif** : `DLG_Mailer.envoi_complet` défini pour tous les chemins (faux pour un message de test) ; `EnvoiEmailFamille` renvoie vrai seulement si toutes les adresses sont acceptées. Confirmations Connecthys sans éditeur (réponse, reçu, facture) : clé de suivi par demande et document, adresses acceptées mémorisées localement (`Utils/UTILS_Emails_acceptes.py`, table native `parametres`, catégorie `noethys_sl_emails_acceptes`, JSON, sans migration) ; un nouvel essai n'envoie qu'aux adresses restantes, la mémoire est effacée quand la confirmation est complète. Chemin Mailjet hors UI réservé au Mailer caché ; l'éditeur affiché retrouve `Mailjet.Envoyer_lot` (RC8.1).
- **Compatibilité Connecthys (I. Lucas)** : aucun nouvel état de demande, réponses et `email_date` inchangés, aucun paramètre de catégorie `portail` ; la synchronisation ne lit pas la nouvelle catégorie (test).
- **Défaut révélé par la mise en CI de `test_piece_quotient_dialog`** : la validité illimitée de pièce + quotient (RC9) n'avait jamais été exécutée. Le premier run a bloqué la CI Windows 20 min sur une boîte modale ; une garde de test (MessageBox/MessageDialog/ShowModal → échec explicite) a donné le message réel (run [40080174235](https://github.com/fr4nck/Noethys-SL/actions/runs/40080174235)) : « La date que vous venez de saisir semble trop élevée ». Cause : `DLG_Saisie_quotient.ctrl_date_fin` est un `Date2` borné par défaut au 01/01/2030 ; la fin 2999-01-01 transmise par la pièce était refusée (pièce enregistrée, quotient non). Correctif : borne `date_max="01/01/2999"` sur ce seul champ ; test direct de saisie du quotient illimité ajouté. La borne 2030 des autres `Date2` n'est pas modifiée (hors périmètre, à examiner).
- **Tests** : `test_connecthys_confirmation_partielle` (nouveau), `test_connecthys_mailjet_lot_asynchrone` (contrats mis à jour), `test_piece_quotient_dialog` désormais en CI rapide ; ancrage de `test_audit_reseau_emails` mis à jour (contrat « reçu non envoyé → attente » inchangé).
- **Qualification CI** : CI rapide [40080770764](https://github.com/fr4nck/Noethys-SL/actions/runs/40080770764) sur `add1b62` **SUCCESS** — 922 tests, 911 PASS, 0 FAIL, 11 SKIP (Windows, wx réel). Aucun build candidat lancé, aucun tag ni release RC9 (API : 404). Reste : recette manuelle Windows d'une confirmation Connecthys partielle (SMTP et Mailjet) et de la réception pièce + quotient illimité ; borne 2030 des autres champs `Date2` à examiner.

## RC9 — NO-GO, lot 1 : publication sécurisée et diagnostic du démarrage (24/10/2026, wx uniquement)

- **Contexte** : audit différentiel RC8.1 → wx du 24/10, verdict NO-GO accepté. Aucun build candidat RC9 réussi (`5424d52` ×2, `8010d48`, `04eb507`) ; sur les deux derniers, le ZIP portable extrait reste vivant 120 s sans créer `Portable/Temp`, `Config.json` ni `journal.log` : `main()` n'est pas atteint (RC8.1 : profil créé en 22 s). **Cause non déterminée** ; l'hypothèse PyInstaller (`pyinstaller-hooks-contrib` 2026.8 → 2026.9, seul écart d'outillage relevé) n'est pas démontrée.
- **Workflow `noethys-sl-windows.yml`** : un lancement manuel ou un commit `[candidate rc9]` ne produit que des artefacts de recette. Publication dans un job `publish` séparé, seul à avoir `contents: write`, exécuté uniquement sur `workflow_dispatch` depuis `wx` avec `publier=true` (défaut `false`), après réussite du job `build` (`needs`), avec revérification des empreintes. Le marqueur `[publish rc9]` ne publie plus. Permissions globales et du build : `contents: read`.
- **Diagnostic de démarrage** (`Utils/UTILS_Diagnostic_demarrage.py`, inactif sauf `NOETHYS_DIAGNOSTIC_DEMARRAGE=<fichier>`) : imports horodatés, étapes (`imports_termines`, `main_debut`, `profil`, `repertoires_utilisateur`, `app_creation`, `oninit_*`, `mainframe_*`, `mainloop`), exceptions non interceptées (y compris threads), piles de tous les threads toutes les 20 s. Le smoke « runner isolé » exige `ETAPE oninit_fin` au lieu d'un processus simplement vivant ; le script portable inventorie les fenêtres du processus (boîte d'erreur masquée) et surveille le vrai profil Windows (`appdirs` ignore `%APPDATA%`) ; diagnostics publiés en artefact même en échec.
- **Tests** : `test_noethys_sl_workflow_publication_rc9` (aucun scénario de diagnostic ne publie, permissions, ordre des barrières ; échoue sur l'ancien workflow), `test_noethys_sl_diagnostic_demarrage` (sous-processus réels). Ajoutés à la CI rapide et au build candidat.
- **Build non autorisé déclenché par erreur** : le corps du message de `1dfa7d1` contenait le marqueur de build candidat ; le job build a tourné (run [40059146221](https://github.com/fr4nck/Noethys-SL/actions/runs/40059146221), ~8 min, archive MySQL téléchargée), la publication a été **ignorée** (garde vérifiée en conditions réelles). Aucun artefact de candidat produit (échec au smoke).
- **Cause du blocage établie par ce diagnostic** : exception à l'import, avant `main()`, `AttributeError: module 'zoneinfo' has no attribute 'reset_tzpath'` dans `dateutil/tz/_tzpath.py` (chaîne `DLG_Effectifs` → … → `CTRL_Saisie_date` → `dateutil.parser`). `python-dateutil` non épinglé : 2.9.0.post0 au build RC8.1, **3.0.0** aux builds RC9. Mécanisme reproduit localement sur disposition synthétique avec le vrai `Chemins.py` : l'insertion de chaque sous-dossier du répertoire de l'exécutable en tête de `sys.path` fait de `dateutil/zoneinfo` le module `zoneinfo`, qui masque le module standard importé par dateutil 3. Dans le paquet réel (modules dans l'archive PyInstaller), ce mécanisme précis reste à confirmer par le prochain diagnostic.
- **Correction appliquée** : `python-dateutil==2.9.0.post0` (version du build RC8.1 qui démarrait), test `test_noethys_sl_dependances_demarrage`. Diagnostic enrichi : `sys.path` après `Chemins` et origine des modules cités par une exception. **Non qualifiée sur paquet** tant qu'un build candidat de diagnostic n'est pas autorisé. Correction de fond proposée (non appliquée) : ne plus insérer les sous-dossiers de bibliothèques tierces avant la bibliothèque standard dans `Chemins.py`.
- **Build de diagnostic autorisé (24/10)** : lancement manuel `publier=false` sur `1ab469e`, run [40072909737](https://github.com/fr4nck/Noethys-SL/actions/runs/40072909737) **SUCCESS**, job de publication **ignoré**, aucun tag ni release `noethys-sl-0.1.0-rc.9` (API : 404). python-dateutil 2.9.0.post0 installé ; contrats du candidat 501 tests OK (8 SKIP) ; MySQL 5.7.44 jetable 11 OK ; exécutable installable : toutes les étapes jusqu'à `oninit_fin` en 0,8 s ; ZIP portable : profil initialisé en 2 s puis 10 s, `Config.json` persistant, aucun profil Windows externe (vrai profil surveillé). `sys.path` figé relevé : les dossiers de bibliothèques tierces (`tzdata`, `pytz`, `wx`…) sont insérés avant l'archive des modules, ce qui conforte le mécanisme de masquage.
- **Artefacts de recette (non publiés)** : `Noethys-SL-0.1.0-rc.9-Setup.exe` SHA-256 `41b65b25f22c8d2c06c74a39f7b218509903cbffa1d6fd4d53af6353c430df2b` ; `Noethys-SL-0.1.0-rc.9-Windows-portable.zip` SHA-256 `acb1e972acb8634a484fd4551a3c3bd2126794051af6c527270a2524eb519468` (rétention 30 jours).
- **Reste** : recette manuelle du ZIP sur poste Windows ; correction de fond de `Chemins.py` (proposée) ; lots Mailjet/Connecthys, cotisations, impression. RC9 non publiée (NO-GO maintenu tant que ces lots ne sont pas traités).

## RC9 — Bouton « CAF / AFAS » masqué provisoirement (23/10/2026, wx uniquement)

- **Décision utilisateur** du 23/10 : masquer le bouton « CAF / AFAS » de l'état global sur `wx` (base `f1fe871`) après l'audit contradictoire AFAS (P0 reproduits : couples activité/groupe, doubles comptages, séparation péri/extra, statuts). Mesure temporaire, ne remplace pas les corrections de fond.
- **Périmètre** : `DLG_Etat_global.py` (bouton créé puis masqué, `Bind` vers `OnAFAS` retiré, sizer des boutons ramené à 4 colonnes) ; `OnAFAS`, `DLG_AFAS_Actualisation.py` et `UTILS_AFAS*.py` conservés sans modification ; aucun calcul de l'état global modifié. `Versions.txt` (section RC9), `docs/releases/noethys-sl-0.1.0-rc.9.md`, consigne RC8/RC8.1 `docs/incidents/2026-10-23-afas-v1-bouton-masque.md`.
- **Branches** : `main` et `qt` non modifiés (le bouton reste présent sur `main`, où les corrections AFAS P0/P1 reprennent, sans report automatique sur `wx`). Aucun tag, installateur ni publication RC9.
- **Reste à faire** : recette visuelle Windows de l'état global (bouton absent, Aide/Aperçu/Fermer intacts, aperçu PDF et profils fonctionnels).

## RC9 — Associations automatiques inscriptions (22/10/2026, moteur qualifié / recette UI à faire)

- **Décision fonctionnelle** : par type de cotisation individuelle, mode par défaut `inscriptions` (toutes inscriptions au statut `ok` qui chevauchent l'adhésion) ; alternative `participations`. Un seul tarif et une seule échéance. Les nouvelles inscriptions complètent uniquement les adhésions automatiques déjà créées, sans prestation nouvelle ; les adhésions manuelles restent inchangées et aucun lien historique n'est supprimé.
- **Moteur commun publié** : `main` [cf30a6e](https://github.com/fr4nck/Noethys-SL/commit/cf30a6e9a3033d41f4710f8a7ea69dc2bbdf9a6a), `wx` [6e8d310](https://github.com/fr4nck/Noethys-SL/commit/6e8d310da1865377b23fe72dec7ec03a12122369), `qt` [7f38d33](https://github.com/fr4nck/Noethys-SL/commit/7f38d333de453d6f1ebc6d26366408aca1d01d97). Blob moteur `b6d7465bb3f49ab0a7ec7d584290bdb709a34310` identique sur les trois ; option stockée par type dans `parametres` (schéma inchangé). Le moteur de création est toujours conditionné à la participation et à la validation RC8.1.
- **wx** : choix dans `DLG_Saisie_type_cotisation`, hook après commit dans `DLG_Inscription`, garde sur la suppression de liens `cotisations_activites` limitée à `IDcotisation_activite` pour ne plus retirer le même type d'autres activités.
- **Tests ajoutés au manifeste CI** : `tests/test_noethys_sl_adhesions_inscriptions.py` (13 scénarios fictifs SQLite), `tests/test_noethys_sl_adhesions_inscriptions_wx.py` (4 contrats statiques UI wx uniquement) et `tests/test_noethys_sl_adhesions_inscriptions_mysql.py` (4 cas réels MySQL 5.7 jetable). Aucun accès aux bases PMSL ni envoi réseau.
- **Statut d'exécution** : accord explicite utilisateur pour CI le 22/10. [CI Windows](https://github.com/fr4nck/Noethys-SL/actions/runs/39803880546) : **863 exécutés, 853 PASS, 0 FAIL, 10 SKIP**, tests multi-activités inclus ; [MySQL local 5.7.44](https://github.com/fr4nck/Noethys-SL/actions/runs/39804841036) : **7 PASS / 0 FAIL / 0 SKIP**, dont quatre scénarios métiers et trois contrats de concurrence/transactions. Première exécution MySQL [39803879767](https://github.com/fr4nck/Noethys-SL/actions/runs/39803879767) : trois FAIL des anciennes fixtures MySQL (table `parametres` fictive absente), corrigés dans `tests/test_noethys_sl_adhesions_concurrence.py` ; la seconde est verte. **Aucune release, aucun tag, installateur ni publication RC9.** Workflow MySQL de recette sans packaging ajouté dans `.github/workflows/noethys-sl-rc9-qualification.yml`.
- **Barrière obligatoire** : les tests CI et les téléchargements des seules machines GitHub sont autorisés et passés. Restent l'inspection réelle de l'écran de paramétrage et du flux d'inscription wx, la recette sur un profil / une base fictive Windows, l'absence de double facturation et les scénarios limites (passage de groupe, changement de type, verrouillage). Publication d'une candidate RC9 séparée, seulement après qualification. Une adaptation de l'écran Qt natif reste à faire lorsque l'édition Qt sera disponible.
- **Spécification** : `docs/metier/ADHESIONS_MULTI_ACTIVITES_RC9.md`. Les correctifs précédents Mailjet, impression des dépôts et Entrée/fiche famille restent présents sur `wx`.

## P1 — Entrée n'ouvre plus la fiche après recherche d'un individu (22/10/2026)

- **Signal utilisateur** : sur l'écran quotidien « liste/recherche des individus », saisir un nom et laisser un seul individu visible ne permet plus d'ouvrir sa fiche famille avec Entrée ; cela fonctionnait en Vanilla. Aucune donnée de famille produite ici.
- **Code de la RC8.1 et main/wx/qt avant correctif** : `Ol/OL_Individus.py` possède encore `BarreRecherche.OnEnter` et `OuvrirFiche`. La liaison `wx.EVT_TEXT_ENTER` est conservée, mais un événement non livré par le champ natif wx ou le timer de filtrage en attente peuvent empêcher l'ouverture. Cause physique exacte à contre-vérifier sur Windows.
- **Correctif interface wx** : [021eaf4](https://github.com/fr4nck/Noethys-SL/commit/021eaf4a1140a3050b87b51a6c0f3b65abd41896) conserve le chemin métier unique `OuvrirFicheFamille(track)`, intercepte `EVT_CHAR_HOOK` dans la barre de recherche, reconnaît Entrée et Entrée numérique, synchronise le filtre sans attendre le timer, évite la réouverture pendant le dialogue modal, ne modifie ni ID, ni DB, ni permissions, ni traitement des familles à rattachements multiples.
- **Tests** : `tests/test_noethys_sl_recherche_individus_entree.py` ajouté à la CI rapide. Touche Entrée/numpad, autres touches, 1 résultat avec timer en cours, 0 résultat, événement réentrant et garde après exception, contrat de raccordement événementiel. Aucune base réelle, aucun message envoyé. [CI Windows](https://github.com/fr4nck/Noethys-SL/actions/runs/39785197180) **PASS** : CI Python et Windows réussies, 846 tests exécutés, 836 PASS / 0 FAIL / 10 SKIP, dont les 7 nouveaux tests PASS. Recette physique au clavier non effectuée.
- **Branches** : `wx` : PRESENT `021eaf4`, CI Windows PASS, recette clavier réelle à qualifier ; `main` : ABSENT `76ef824` (correction GUI spécifique) ; `qt` : NON APPLICABLE au widget wx (raccourci UX analogue à spécifier dans l'interface Qt), SHA `bd564a0`. Tag RC8.1 `00f53db` inchangé ; aucune nouvelle branche, aucun packaging.
- **Recette avant prochain candidat** : sous Windows, vérifier l'ouverture par Entrée depuis le champ de recherche dès qu'une seule ligne reste affichée, avec et sans temporisation, ainsi que zéro résultat, plusieurs familles rattachées, absence de droits, clavier numérique et Ctrl/Shift+doubles-clics. Ne pas annoncer une livraison RC avant cet essai métier.

## P1 — Aperçu des règlements d'un dépôt vide à l'impression (22/10/2026)

- **Signal de recette** : dans Règlements > Gestion des dépôts > modification d'un dépôt verrouillé > Outils > Aperçu avant impression, le titre et les métadonnées du dépôt s'affichent, mais pas les colonnes ni les lignes des règlements. Capture utilisateur ; cause graphique exacte non encore reproduite sur le poste Windows.
- **Constat sur le code** : le parcours `DLG_Saisie_depot -> OL_Reglements_depots -> UTILS_Printer -> Outils/ListCtrlPrinter` imprime directement la grille wx/OLV et ses 14 colonnes. L'ancien test d'impression remplaçait ces colonnes par deux colonnes et validait seulement l'existence de pixels non blancs : un titre suffisait à le faire passer.
- **Correctif wx uniquement** : commit [b2e0d9f](https://github.com/fr4nck/Noethys-SL/commit/b2e0d9f5c8ecbc869444620bae6444e0b6fcaa8e), puis réparation de l'indentation du test [3844e84](https://github.com/fr4nck/Noethys-SL/commit/3844e84a32d98de7d73c3d1403cfaa0b79b16e37), et de l'assertion total/montant de ligne [fde1576](https://github.com/fr4nck/Noethys-SL/commit/fde1576b1a49ae70a68f976d4832cc422b7a9739). `Ol/OL_Reglements_depots.py` construit un instantané immuable de huit colonnes métier (date, mode, émetteur, pièce, famille, payeur, montant, observations) pour le moteur d'impression ; données affichées/DB inchangées. Aucun aperçu vide silencieux lorsqu'aucune ligne n'est rattachée. Adaptateur minimal en lecture seule, sans nouveau backend ni migration.
- **Tests** : `tests/test_noethys_sl_impression_depot.py` vérifie la sélection de ce snapshot par aperçu/impression, 49 règlements fictifs, le vrai passage des intitulés et montants au rendu mémoire wx, le contrat d'absence de règlements, l'absence de changement DB. Aucun document imprimé, PDF, email ou base PMSL utilisé.
- **Qualification** : syntaxe Python PASS sur la [CI](https://github.com/fr4nck/Noethys-SL/actions/runs/39777345654) de `3844e84` ; test Windows 838 PASS / 1 FAIL / 10 SKIP (échec d'assertion de test : le total `3259.75` n'appartient pas à une ligne, laquelle vaut au maximum `859.75`). Les preuves de valeurs de lignes et d'en-têtes étaient PASS. Assertion corrigée en `fde1576`; [nouvelle CI Windows](https://github.com/fr4nck/Noethys-SL/actions/runs/39778499412) **EN ATTENTE** lors de cette passation. La CI précédente `b2e0d9f` a échoué sur une indentation du test, corrigée en `3844e84`. Rendu réel Windows, orientation et lisibilité du relevé **NON QUALIFIÉS** : recette pilote obligatoire avant release.
- **Branches (contrat)** : `main` `76ef824` : ABSENT, adaptation d'interface wx ; `wx` `fde1576` : code présent, recette EN ATTENTE ; `qt` `bd564a0` : NON APPLICABLE au parcours wx. Tag RC8.1 `00f53db` immuable. Aucun merge global, aucune écriture métier ni suppression de donnée.
- **Prochain contrôle** : laisser la CI rapide finir puis reproduire sur une copie/fichier fictif contenant réellement des règlements, y compris un dépôt verrouillé ; vérifier que la grille montre N lignes et que l'aperçu imprime bien N lignes et le total ; conserver un visuel avant/après sans information bancaire ni noms réels. Ne pas déclarer le correctif publié en version Windows tant que ce parcours n'a pas passé la recette.

## P1 #426 — audit RC7 renforcé et préparation de recette RC8.1 (21/10/2026)

- Correctif limité à l'inventaire : `UTILS_Audit_cotisations`, lecteur autonome explicite SQLite/MySQL local, export HTML/JSON/CSV et fiche comptable vide. Aucune régularisation, aucun appel de création financière, aucune donnée PMSL.
- Trois lacunes reproduites sur l'audit publié : prestation absente hors filtre temporel omise ; prestation présente sans date confondue avec une absence ; date de fin invalide interrompant le rapport.
- Contrôles : facture référencée vs pièce présente, ventilations détaillées même à somme nulle, règlements référencés, dates invalides, liens partagés et incohérences de payeur. Totaux dédupliqués par prestation ; validité future n'atteste pas de présence réelle.
- Qualification locale Linux : **31 PASS / 0 FAIL / 0 SKIP**, tables SQLite du schéma canonique ; interdiction des écritures, empreintes avant/après, exports et erreurs SQL couverts. Compilation des fichiers modifiés PASS.
- Exemple fictif : 9 automatiques examinées, 8 signalées, 6 prestations distinctes, 45,00 EUR ; aucune donnée PMSL. Guide et commandes : `docs/diagnostics/AUDIT_COTISATIONS_RC7_RECETTE_RC81.md`.
- Synchronisation ciblée préparée depuis main `0500ff0`, wx `f48cf15`, qt `7e9745a` : les blobs initiaux du service et de la fixture adhésions sont identiques. Les workflows et l'historique de cette passation sont conservés proprement à chaque branche, sans merge global.
- Matrice de qualification du contenu commun : main / wx / qt = correctif d'audit et tests communs présents dans ce lot, qualification Linux sur contenu commun PASS ; runtime Windows et UI Qt **EN ATTENTE**. Le test est ajouté aux futures CI rapides main/wx ; le workflow ne déclenche pas automatiquement sur qt.
- **CI distante non relancée** (`[skip ci]`) : aucun téléchargement/installation ni build de paquet déclenché dans ce lot. Les 465 tests Windows et 11 tests MySQL du 19/10 restent des preuves de l'ancienne release, pas du nouvel audit. Aucun pilote MySQL dans le conteneur ; nouveau lecteur MySQL non qualifié sur serveur réel.
- Recherche des sources actualisées : #426 et son seul commentaire restent datés du 19/10 ; release RC8.1 et passation wx récupérées, recherche d'issues actualisées et documentaire sans attestation terrain plus récente trouvée. Cela ne démontre pas une absence d'opérations locales.
- **Limites d'exploitation maintenues** : copie isolée identifiée indispensable, recette wx sur copie B jetable, validation comptable nominative. Ne pas modifier les tags/binaires RC7/RC8.1 ni fermer #426 ; aucun poste, production, profil utilisateur ou Connecthys modifié.


## P1 #426 — parcours facturation livré en RC8.1 (19/10/2026)

- **Cause des mentions « toujours suspendu » de RC8** : `noethys/Utils/UTILS_Adhesions_echeances.py` et l'étape `PreparerCotisationsPourApercu` de `DLG_Factures_generation.py` étaient sur `main`, mais **absents de `wx` et `qt`**. RC8 Windows utilisait donc encore le seul coupe-circuit de sauvegarde.
- **Correction technique** : report ciblé de `UTILS_Adhesions.py`, du service d'échéances, de l'assistant de facturation et des tests d'échéances sur `wx` (`004ee610`) et `qt` (`7e9745a`). `AUTO_CREATION_SUSPENDUE=True` maintenu pour `CTRL_Grille.Sauvegarde()` : **aucune création financière lors de la sauvegarde de réservations**.
- **Parcours utilisable** : Génération de factures > page 1 > prestations comportant « cotisation » > Suite. L'aperçu des cotisations est calculé depuis les participations passées non annulées, un consentement explicite précède toute création, le contrôle transactionnel vérifie l'état sous verrou, puis la page 2 relit les prestations pour l'aperçu. Les réservations futures ne déclenchent aucune adhésion.
- **Audit des anciennes anomalies RC7** : `UTILS_Adhesions_echeances.AuditerCotisationsAnticipees()` en lecture seule, signale adhésions futures et prestations antidatées, états facturés / ventilés ; tests de données fictives ; ne modifie ni ne supprime les cotisations existantes.
- **Release immuable** [RC8.1](https://github.com/fr4nck/Noethys-SL/releases/tag/noethys-sl-0.1.0-rc.8.1), tag pointant sur `00f53db463d812e31f0eee7e56e0db00835b8162` : installateur Windows et ZIP portable plus SHA256SUMS, préversion de recette, RC8 inchangée. Notes `docs/releases/noethys-sl-0.1.0-rc.8.1.md`.
- **CI** : [main](https://github.com/fr4nck/Noethys-SL/actions/runs/39264413992) SUCCESS 782 PASS / 6 SKIP ; [wx SHA final](https://github.com/fr4nck/Noethys-SL/actions/runs/39266359306) SUCCESS ; [build Windows intégral](https://github.com/fr4nck/Noethys-SL/actions/runs/39266358654) SUCCESS **465 tests / 0 FAIL / 7 SKIP** et **11 tests MySQL / 0 FAIL**. Tests UI wx simulés avant aperçu ajoutés ; MySQL 5.7 jetable, PyInstaller, smoke démarrage, Setup, ZIP portable et SHA256 contrôlés.
- **Empreintes release** : Setup 105473244 octets `6eba424d93848516a2d04a79e532346a5bfe6d0251e43546c2704c4705b8ed22` ; Portable ZIP 147375215 octets `c02add7f398ee6191a993047bf5bd8dc666a165d3a4850fb481a1e00eaa6673c`.
- **Barrière d'exploitation** : recettes pilotes réelles sur base fictive/copie ; audit lecture seule de la base PMSL avant toute régularisation ; aucune suppression de masse ; avoirs/régularisations comptables pour prestations déjà facturées/ventilées ; **pas de planificateur indépendant de clôture mensuelle** (le déclenchement se fait dans l'assistant de facturation). Ne pas clore l'issue #426 sans validation métier. Aucun poste PMSL n'a été modifié lors de cette intervention.

## Publication Noethys SL 0.1.0 RC8 — préversion Windows (19/10/2026)

- **Publication effective et vérifiée**, **prérelease**, pas version stable : [noethys-sl-0.1.0-rc.8](https://github.com/fr4nck/Noethys-SL/releases/tag/noethys-sl-0.1.0-rc.8). Date de publication GitHub : 19/10/2026 à 13:13:32 UTC. Tag cible exact `09dfa804133c4ca094c9da9708a54231e42df39d` sur `wx` ; aucun retag RC7 et aucun déploiement automatique.
- **Versions** : `noethys/Identite.py` affiche `0.1.0-rc.8` / `0.1.0 RC8`, `noethys/Versions.txt` contient la section RC8 en tête. **Version interne numérique conservée à `1.3.4.4`**, et tout l'historique maintenu à l'identique. `main` et `qt` ne reçoivent pas l'identité Windows RC8.
- **CI rapide wx RC8** : [39256895095](https://github.com/fr4nck/Noethys-SL/actions/runs/39256895095), **789 tests, 0 échec, 10 ignorés**. La même CI sur la source finale [39257658313](https://github.com/fr4nck/Noethys-SL/actions/runs/39257658313) est SUCCESS.
- **Build complet RC8** : [39257658370](https://github.com/fr4nck/Noethys-SL/actions/runs/39257658370) SUCCESS : **443 tests critiques, 0 échec, 7 ignorés** ; **11 tests MySQL 5.7.44 local jetable, 0 échec** ; compilation, PyInstaller, archive MySQL SHA épinglée, clients mysql/mysqldump, sauvegarde/restauration, smoke binaire Windows et ZIP extrait avec profil `Portable/`, fabrication Setup Inno, SHA256SUMS et upload PASS.
- **Livrables publics vérifiés**, noms, tailles et digests GitHub cohérents avec les journaux :
  - Setup `Noethys-SL-0.1.0-rc.8-Setup.exe`, 105 461 328 octets, SHA-256 `98a9c2556a40e17d11c24cc2fac9e4d44f03a33bbf4a1ea3a0f898981170b792`.
  - Portable `Noethys-SL-0.1.0-rc.8-Windows-portable.zip`, 147 369 923 octets, SHA-256 `357ceb7a8b5befdd22eb8c5da3716c2edfe6facf65009c71bf7e626d7c403d3f`.
  - `SHA256SUMS.txt` présent sur la release.
- **Aucune installation sur les postes PMSL**, aucune base réelle ouverte, aucune migration, aucun email envoyé.
- **Recette terrain restant obligatoire** avant déploiement : commande de repas sur base fictive/copie isolée, contrôle des questions et préférences sans porc manquantes, PDF et brouillon email, identifiants multisites, direction entre commandes distinctes ; anomalies P1 [#426](https://github.com/fr4nck/Noethys-SL/issues/426) (création auto adhésion **toujours suspendue**, refonte complète ouverte) et [#428](https://github.com/fr4nck/Noethys-SL/issues/428) (correctif inclus, validation poste pilote ouverte). Qt natif non qualifié.
- Notes destinées aux utilisateurs et limites : `docs/releases/noethys-sl-0.1.0-rc.8.md`. Issue métier #430 maintenue ouverte jusqu'à validation terrain.

## RC8 — Recette fictive des repas, PDF et email (19/10/2026)

**Statut** : développement poursuivi, **RC8 NON PUBLIEE**. Aucune migration SQL, sauvegarde PMSL, accès à la production, téléchargement de paquet, envoi SMTP ou construction d'installateur n'a été effectué dans ce lot.

**Points démontrés :**
- `test_noethys_sl_repas_sqlite_recette` : base SQLite **en mémoire**, données entièrement fictives, question individuelle « sans porc » explicite ; contrôle sur réservations / présences en doublon, absences, même unité dans plusieurs groupes, réponses non renseignées, questions famille refusées et absence d'écriture SQL.
- `test_noethys_sl_repas_pdf_mail_recette` : vrai PDF temporaire produit avec ReportLab ; récapitulatif par date/site/service, enfants moins de 6 ans, enfants 6 ans et plus, détail repas adultes animation/direction/autres, total **6 ans et plus adultes compris**, « dont sans porc » et total général. L'écran corrige les valeurs avant émission ; le PDF refuse une validation absente ou périmée.
- Préparation du brouillon d'email via le mécanisme `EnvoiEmailFamille` avec **mailer simulé** : même PDF, mêmes champs de fusion `{REPAS_TOTAL}`, `{REPAS_6_PLUS}`, `{REPAS_ADULTES}`, `{REPAS_SANS_PORC}`. Aucun SMTP ni destinataire réel.
- Si une préférence alimentaire manque, un avertissement et une confirmation explicite s'affichent avant l'émission.
- Rendu A4 de contrôle effectué sur un tableau synthétique sans débordement visible (contrôle visuel **hors application**, distinct de la recette utilisateur).

**Qualification traçable** :
- `main` code [9f6d3e1](https://github.com/fr4nck/Noethys-SL/commit/9f6d3e12026b6f108e09c305fa74f83178daa396) : [CI Windows 39238759686](https://github.com/fr4nck/Noethys-SL/actions/runs/39238759686), **765 tests / 0 FAIL / 6 SKIP**, PASS.
- `wx` report ciblé [199ff2a](https://github.com/fr4nck/Noethys-SL/commit/199ff2a88c8e6b512651508bd2a8507957af3574) : [CI Windows 39239363460](https://github.com/fr4nck/Noethys-SL/actions/runs/39239363460), **789 tests / 0 FAIL / 10 SKIP**, PASS.
- `qt` report ciblé [522236f](https://github.com/fr4nck/Noethys-SL/commit/522236ffe06050878bd38735f051824ca69c81f0) : mêmes blobs métier, **Qt natif non qualifié**.
- Correspondance SHA des fichiers partagés constatée pour le contrôleur des commandes, la prévalidation PDF/email, le dialogue de contrôle et les deux tests de recette ; aucune fusion globale et aucune création de branche.

**Barrières restantes** : une recette avec utilisateur sur poste Windows (base fictive, modèles et bon du restaurateur) ; gestion des préférences modifiées dans le temps **sans historique natif**, direction multisite partagée entre commandes distinctes **sans déduplication garantie**, questions/choix à configurer manuellement, et validation des autres P1 avant tout candidat RC8.

Voir `docs/metier/REPAS_RC8_VALIDATION.md` et le ticket #430.

## RC8 — repas sans porc et contrôle avant émission (19/10/2026)

- **Décision** : développer avant RC8 ; aucun tag, release, installateur, migration SQL, envoi d'email ni accès à la production.
- **Lot #430** : réponses alimentaires individuelles explicites via `questionnaire_questions`, `questionnaire_choix`, `questionnaire_reponses` ; aucun texte médical interprété. Les réponses ne sont pas historisées : impossible de rétablir le choix à une date passée sans autre stockage.
- **Décompte** : dates / site / service, effectifs enfants séparés à six ans, suggestions « dont sans porc » exclues des totaux additifs ; repas des animateurs, direction, autres adultes saisis séparément, puis tous regroupés dans 6 ans et plus. Absence de preuve d'absence de doublon entre **commandes multisites indépendantes**.
- **UI** : `DLG_Controle_repas.py` avant boutons PDF/email ; valeurs modifiables, recalcul de totaux, annulation empêche l'émission ; modèles typés invalides bloqués. Anciens modèles non typés conservent un avertissement et une confirmation explicite pour l'ancien flux. Aucun mail automatique envoyé.
- **Bilan source** : `main` lot métier validé au commit [7da9785](https://github.com/fr4nck/Noethys-SL/commit/7da97850f5d78b431e352b420e4872e08603f436), `wx` [5abdee4](https://github.com/fr4nck/Noethys-SL/commit/5abdee44f8cc0869970705a37b8b2cf5171c3762), `qt` [7dc1557](https://github.com/fr4nck/Noethys-SL/commit/7dc1557922709210bcf5317a1ff71ebdb4eafb5b). Fichiers métier/tests communs reportés par blobs SHA, sans merge global ; workflows de chaque branche conservés.
- **Tests** : [CI main 39235083395](https://github.com/fr4nck/Noethys-SL/actions/runs/39235083395) : **753 tests, 0 FAIL, 6 SKIP**, compilation PASS et suite Windows PASS. [CI wx 39235956725](https://github.com/fr4nck/Noethys-SL/actions/runs/39235956725) à qualifier par lecture de son verdict ; Qt natif non validé.
- **STOP-GATE** : recette complète sur base fictive dans l'interface Windows, comparaison PDF/brouillon d'email, préexistants modèles, préférence sans porc inconnue, changement de préférence pendant une période et direction multisite partagée. Ne pas qualifier RC8 sans ces points et résolution des P1 antérieurs.
- Détails : `docs/metier/REPAS_SANS_PORC_RC8.md`, `docs/metier/REPAS_RC8_VALIDATION.md` et issue #430.

## RC8 — commandes de repas et encadrement : développement poursuivi (18/10/2026)

- Décision utilisateur : **poursuivre le développement avant toute RC8**. Aucun tag/release, installateur, migration SQL ou déploiement effectué dans ce lot ; aucune donnée réelle lue ni modifiée.
- #430 : suggestion de +1 repas directeur détaché par site/date/service, direction multisite mutualisée par identifiant d'ensemble, repas facultatif d'adjoint ou directeur stagiaire. Option désactivée par défaut ; anti-doublon limité aux colonnes d'une même commande, **pas entre commandes indépendantes**. Le repas déjà compris dans les adultes doit rester explicitement exclu par l'opérateur.
- #429 : moteur sans interface dans un premier lot puis dialogue **Outils > Simuler les besoins en animateurs** dans les commandes de repas. Configuration explicite site/créneau/cadre/durée/PEDT, sous-effectifs <6 et >=6, prévisionnel (réservations + présents) ou réel (présents). Arrondi par tranche, adultes ignorés, doublons dédupliqués, âges inconnus signalés. **Lecture seule** ; aucune injection dans le bon PDF du restaurateur, aucune certification réglementaire.
- Sources partagées qualifiées à l'identique par SHA de blob : noethys/Dlg/DLG_Saisie_commande.py, noethys/Dlg/DLG_Encadrement.py, noethys/Utils/UTILS_Encadrement.py, tests/test_noethys_sl_encadrement_dialog.py, docs/metier/ENCADREMENT_RC8.md. Aucune fusion globale, aucune branche créée.
- **Matrice des commits de développement** : main **5a658703de8a4a743702290cb5df8b418fa9c2f7** ; wx **fd2b7d0df9e7297ef265acce709687133615dffb** ; qt **ca72dd0b653c34038a9b27f04c19d4c1e121fd08**. Workflows adaptes chacun sur sa branche ; variantes propres conservées.
- Tests sans wx local : **13 PASS / 0 FAIL** du moteur, plus syntaxe du dialogue. [CI Windows main 39164801226](https://github.com/fr4nck/Noethys-SL/actions/runs/39164801226) : **724 tests / 0 échec / 6 ignorés**, compilation et runtime wx PASS. [CI rapide wx 39165107741](https://github.com/fr4nck/Noethys-SL/actions/runs/39165107741) lancée, **conclusion à consulter avant qualification wx**. Qt natif non qualifié ; pas de paquet Qt construit.
- **Reste hors portée de ce lot** : reconnaissance fiable du choix alimentaire « sans porc » (#430) faute de source explicite qualifiée ; regroupement général des repas adultes dans les 6 ans et plus ; affectation permanente des sites et créneaux ; calcul des personnels réellement disponibles, direction/stagiaire dans le planning ; déduplication des repas entre plusieurs commandes ; recette fonctionnelle sur un poste Windows réel avec base fictive.
- **STOP-GATE RC8** : terminer les P1 de facturation/adhésion, vérifier les effectifs simultanés et la continuité des temps d'accueil, qualifier les postes de direction et les PDF en copie isolée. Aucune RC8 ne doit être publiée automatiquement.

## Candidat Windows RC7.5 fabriqué et vérifié (16/10/2026)

- Autorisation de Franck : « ok go » après proposition d'intégrer les corrections
  dans un nouvel installateur. Identité distincte RC7.5 ; RC7.4 conservée intacte.
- Source wx empaquetée : e6958884cfbc2432a36ec388fe948efb90be4cdb.
  Identité, changelog et workflow Windows seuls modifiés ; version interne 1.3.4.4
  et historique numérique inchangés. Test assiduité ajouté aux contrats critiques.
- Contient le catalogue indépendant et la sélection des groupes dans Aujourd'hui,
  ainsi que les taux de journées annulées/absences par famille et enfant.
  Le journal reste désactivé par défaut ; activation ADMINISTRATEUR explicite,
  pas de migration SQL implicite ni reconstitution de l'historique antérieur.
  Les correctifs RC7.4 Connecthys, impression/rappels, Mailjet et optimisations
  prudentes restent inclus. Cotisations automatiques toujours suspendues ;
  chantier RC8 repas directeur propre à main toujours exclu du candidat wx.
- Avant préparation : main 9f29ec67ea7ba6c56cd798e837141b79951b4e5f,
  wx 59e4f44df19369229070718038559a211aed43e3,
  qt 2539e26c13a6a2e96e6f767e0ea1685d15eb7362. Six fichiers communs (accueil,
  assiduité et tests) comparés identiques après normalisation des fins de ligne.
  Pas de fusion globale ni de propagation de l'identité Windows vers main/qt.
- Tests locaux : 61 réussis. CI wx 38939996600 sur source empaquetée : succès,
  722 tests / 10 ignorés prévus, log téléchargé et inspecté.
- Construction Windows 38939995981 : succès, 340 tests critiques / 7 ignorés prévus,
  puis 11 tests MySQL 5.7.44 local jetable sans ignoré. Sauvegarde/restauration
  du journal, déclencheurs après restauration et concurrence vérifiés ; démarrage
  binaire Windows puis ZIP extrait/profil Portable réussis sur runner isolé.
- Artefact 12062244984 : Noethys-SL-0.1.0-rc.7.5-Windows-candidat,
  250637060 octets, disponible jusqu'au 15/11/2026. Fichiers téléchargés dans
  qualification/rc75 (hors Git) et SHA256 recalculés conformes :
  Setup 105287660 octets :
  41a5dfa39e5209b44903d8a41538f988ca22ee0490953d96998659ec05f0ad2b
  Portable 147079667 octets :
  9786527a5c77205521a6277ecd37b08f9fe73439b04e40808a62273bb3cad38b
- BUILD-INFO et notes de versions vérifiés ; inspection statique du PYZ du binaire
  confirme Identite RC7.5, Dlg.DLG_Assiduite, Utils.UTILS_Assiduite, le nouveau
  read_catalog et les callbacks de chargement indépendants des réglages.
  Aucun exécutable lancé sur ce poste utilisateur. Logs/scripts hors Git :
  qualification/rc75-build.log, rc75-ci-wx.log, verifier-rc75.py,
  rc75/verification.json et SHA256SUMS.txt ; paquets RC7.3/RC7.4 préservés.
- Matrice : code commun VALIDÉ techniquement sur main/wx/qt aux SHA déjà documentés ;
  paquet Windows wx RC7.5 VALIDÉ techniquement. Qualification métier de déploiement
  EN ATTENTE sur copie isolée ; Qt natif EN ATTENTE et paquet Qt NON APPLICABLE ici.
- STOP-GATE conservé : candidat de recette, pas de tag/release stable, ni de
  déploiement ou d'activation du journal en production. Serveurs autres que MySQL
  5.7.44, recette terrain du journal et DPI restent à qualifier. Aucun email envoyé,
  aucune lecture ou modification de données réelles, aucune installation locale.

## Réglages Aujourd'hui — catalogue activités et groupes (16/10/2026)

- Signalement de Franck : tableau Programme et agenda vide malgré les activités
  ouvertes ; choix nécessaires dans les groupes ALSH et EMS (captures fournies).
- Défaut reproduit : read_day dépend de toutes les lectures du programme et son
  échec remet aussi activities à []. Le dialogue réutilisait exclusivement ce
  résultat. Aucune base réelle consultée : cause précise du déclenchement terrain
  non déterminée, aucune prétention de l'avoir vérifiée en production.
- Correction : lecture indépendante du catalogue activités/groupes/remplissage,
  trois SELECT seulement à l'ouverture des réglages, en tâche de fond sur une
  connexion explicitement liée au fichier courant et fermée dans tous les cas.
  Les callbacks d'un ancien fichier/génération ou d'un contrôle détruit sont ignorés.
  Échec signalé au lieu d'un faux tableau vide ; vraie liste vide explicitée.
- Hiérarchie activité > groupes avec Afficher et Ordre par groupe. Masquer une
  activité masque tous ses groupes ; M/A et unités restent configurés au parent.
  Préférences de groupes enregistrées dans le JSON personnel existant, sans
  migration SQL, en conservant les anciens groupes/préférences non affichés.
- Catalogue = activités valides y compris sans séance aujourd'hui + leurs groupes
  réels reliés par IDactivite. Bandeau = programme du jour seulement ; groupes
  masqués exclus sans mélanger les effectifs. Détection ALSH, règles M/A et
  comptage distinct des séances conservés. Toujours six SELECT par read_day.
- Tests locaux : 34 tests accueil/éphémérides sur chacune des trois branches,
  dont six nouveaux cas : échec consommations sans perte du catalogue, masquages
  ALSH/hors ALSH et priorité parent, période illimitée sur schéma canonique complet,
  persistance des groupes, chargement natif indépendant et callbacks obsolètes.
- Recette MySQL 5.7.44 synthétique 38918080699 : succès, quatre tests sans ignoré ;
  catalogue et programme comparés à SQLite et snapshots inchangés. Les recettes
  existantes journal/rollback/restauration et Mailjet synthétique restent vertes.
- CI finales vertes : main 38918081836 : 709 tests / 6 ignorés prévus ;
  wx 38918174695 : 722 tests / 10 ignorés prévus ; qt 38918189968 : 674 tests /
  6 ignorés prévus. Journaux téléchargés et inspectés. Matrice : correctif partagé
  VALIDÉ techniquement sur les trois sources ; rendu Qt natif et diffusion dans
  un candidat Windows EN ATTENTE. Aucun statut stable attribué.
- Sources : main 4110a7c9caef84fb18e0dfb28a79cdf14d0405c1,
  wx f3fb1636a5c1c26512f5f8f6204b824c4cf78549,
  qt c5e99968c1ea0e77598b85ac6f8b9d6b7898055a. Quatre fichiers communs comparés
  identiques après normalisation CRLF/LF ; propagation ciblée, aucune fusion.
- Preuves hors Git : qualification/accueil-groupes-mysql.log, accueil-groupes-ci-*,
  accueil-reglages-groupes.py/.png. Capture native RGB opaque, données fictives,
  aucun pixel pris dans la base/application utilisateur.
- STOP-GATE : source qualifié, absent du paquet RC7.4 construit sur 23419a6d.
  Aucun nouveau build, tag, release, déploiement ni lecture production. Rendu Qt
  natif et recette terrain sur copie isolée restent à qualifier. Ne pas annoncer
  cette correction comme présente dans l'installateur RC7.4 déjà distribué.

## Assiduité — annulations et absences par famille/enfant (16/10/2026)

- Demande de Franck : deux taux distincts, annulations ET absences ; choix explicite
  du suivi complet des nouvelles réservations plutôt qu'un indicateur de demandes
  Connecthys. L'ancien historique textuel/tronqué ne permet pas une reconstitution
  fiable : aucune fausse reprise ni ancien taux à zéro.
- Accès : Consommations > Liste des absences > Taux par famille / enfant.
  Filtres période/activités, agrégation enfant ou famille et détail par date.
- Grain explicite : enfant + date + activité ; les unités matin/repas/après-midi
  ne font pas compter trois journées. Cohorte annulations : journée ayant une
  nouvelle consommation créée après activation, puis confirmée en réservation.
  Taux = journées de cette cohorte sans consommation active restante et sans
  ancien pointage / journées réservées suivies. Situation actuelle : réinscrire
  la même journée retire l'annulation du taux ; un retrait partiel n'annule pas
  la journée. Les suppressions administratives sont incluses, pas attribuées aux
  parents. Une annulation tardive devenue absenti reste classée absence Noethys.
- Absences = journées entièrement absentes / journées entièrement pointées,
  sans date future. Justifiées/injustifiées séparées (injustifiée prioritaire si
  les deux motifs existent dans une journée entièrement absente). Présence sur
  une partie de journée : absence partielle, hors numérateur. Réservation encore
  non pointée : journée non pointée, hors dénominateur. Agrégats familiaux pondérés
  par nombres de journées, jamais moyenne des pourcentages individuels.
- Activation ADMINISTRATEUR explicite avec description du changement de schéma :
  table noethys_sl_assiduite_v1, deux index, trois triggers INSERT/UPDATE/DELETE.
  Aucun ajout automatique à l'ouverture ni à la lecture ; aucune modification
  de CTRL_Grille.Sauvegarde, des transactions/commits existants ni de GestionDB.
  Identifiants/états/dates uniquement dans le journal, aucun nom, montant ou mail.
  Les triggers suivent les écritures depuis les autres postes/clients aussi.
- SQLite et MySQL InnoDB (aucune conversion automatique). Les écritures de journal
  appartiennent à la transaction de la consommation ; rollback commun vérifié.
  Changements de montant sans changement d'état/contexte non journalisés. Lecture
  SQLite sur snapshot cohérent ; MySQL connexion dédiée et REPEATABLE READ.
  Activation verrouillée/idempotente ; rupture détectée -> calcul suspendu,
  réparation automatique refusée si elle masquerait une période sans historique.
- Contrôles locaux : 17 tests spécifiques ; sélection assiduité/repas/performance
  48 tests réussis sur les trois arbres. Copie SQLite puis nouveau déclenchement
  vérifiés. MySQL réel 5.7.44 jetable : run 38915319292, succès, 4 tests sans ignoré,
  concurrence quatre connexions, rollback, ancien hors suivi et mysqldump/mysql :
  journal restauré identique, triggers inventoriés par le contrôleur SQL existant,
  et nouvelles écritures capturées après restauration. Aucun test production.
- Échecs de qualification conservés : 38914452080 verrou trop long corrigé par
  SHA1 du nom de base ; 38914689652 snapshot après activation corrigé ;
  38915009265 fixture avec réservation ancienne du même enfant bloquant à raison
  une annulation complète, corrigée en séparant cet enfant fictif. Assertions
  conservées ; recette finale verte, pas d'affaiblissement des contrôles.
- CI finales : main 38915320274 : 703 tests / 6 ignorés ; wx 38915539613 :
  716 tests / 10 ignorés ; qt 38915638802 : 668 tests / 6 ignorés. Toutes vertes,
  logs téléchargés qualification/assiduite-ci-{main,wx,qt}.log. Les CI qt exercent
  les contrats communs et le dialogue wx hérité, pas un rendu Qt natif.
- Matrice : moteur/journal/dialogue partagé VALIDÉS techniquement sur les trois
  sources ci-dessous ; recette métier de déploiement et nouvel installateur
  EN ATTENTE sur wx ; rendu Qt natif EN ATTENTE. Aucun statut STABLE attribué.
- Sources partagées : main 1484a9fe80a46e30be19b00e660f2fa25a1eb1f2,
  wx f14e0a0eb3bb1e9ffb706eca59c3e7459f9aca4b,
  qt b3962dd1476202094d182b77c3c232dc090619df. Six fichiers communs comparés
  identiques après normalisation des fins de ligne ; spécificités conservées.
- Mesure strictement synthétique locale SQLite mémoire, médiane 3 passages de
  5000 insertions : 24,48 ms sans journal / 88,73 ms avec, lecture 50,21 ms.
  C'est un coût ajouté, pas un gain ni une mesure de serveur/terrain. Logs/scripts
  qualification/assiduite-* hors Git ; qualification/ précédent préservé.
- STOP-GATE : implémentation source, absente de l'installateur RC7.4 construit sur
  23419a6d. Aucun nouveau paquet, tag ou release fabriqué ici. Recette métier sur
  copie isolée et versions de serveur autres que MySQL 5.7.44 à qualifier ; Qt
  natif non qualifié. Avant prochain candidat, inclure le nouveau module de tests
  parmi les tests critiques du workflow Windows. Aucun suivi activé en production,
  aucune intervention sur données réelles, aucun email envoyé.

## Candidat Windows RC7.4 fabriqué et vérifié (16/10/2026)

- Autorisation de Franck : ajouter les correctifs Connecthys au prochain paquet.
  RC7.3 étant déjà distribuée, identité distincte RC7.4 ; aucune release/tag stable.
- Source empaquetée wx : 23419a6dc4c8753b33337bb8ade391b5a6bc27cc.
  Identité, notes de version et tests propres au candidat wx ; version interne
  numérique 1.3.4.4 inchangée, historique numérique conservé par test.
- Contient les repas dépendant de TOUTES les périodes demandées, priorité Journée
  face aux trois choix cumulés, rôles configurables ; garde des antécédents,
  cas ambigus/facturés/pointés/verrouillés à traiter manuellement. Contient aussi
  les créneaux distincts, fond wx compact et carte Connecthys au survol.
- Avant construction, têtes distantes relevées : main 98ec3d1e, wx 0791f515,
  qt 0edd1d02. Helper, dialogue de rôles et tests identiques sur les trois arbres,
  méthode Appliquer_reservations identique par comparaison AST ; protections wx
  conservées. RC7.4 ne change que packaging/identité/changelog/tests du candidat.
  Les travaux repas directeur RC8 propres à main restent exclus ; création
  automatique des cotisations toujours suspendue (AUTO_CREATION_SUSPENDUE=True).
- Vérifications locales : 71 tests réussis. CI wx 38911889621 sur source empaquetée :
  699 tests / 10 ignorés prévus, succès. Construction 38911888874 : succès ;
  317 tests critiques / 7 ignorés prévus puis 10 tests MySQL 5.7.44 local jetable,
  aucun ignoré. Démarrage binaire puis ZIP extrait/profil Portable : succès.
- Artefact 12050568222 : Noethys-SL-0.1.0-rc.7.4-Windows-candidat,
  250614555 octets, disponible jusqu'au 15/11/2026. Installateur et ZIP téléchargés
  dans qualification/rc74 (hors Git), empreintes recalculées conformes :
  Setup : d1a2bd347c899ed16c52b6ccc7ee3582811f354d0d8d4c3f0cd7e27dd2d9996e
  Portable : 1d5ece4ac33fd935412560f8820ecc2f1f23cc514be2dff6c0f81a9adb593b53
- BUILD-INFO, version embarquée et modules du PYZ inspectés sans exécution locale :
  nouveau helper et dialogues Connecthys, accueil et WordWrapRenderer présents.
  Logs qualification/rc74-build.log, rc74-ci-wx.log, rc74/verification.json hors Git.
- STOP-GATE : candidat technique uniquement ; recette métier sur copie isolée,
  configuration des rôles réels et DPI à vérifier. Aucune installation locale,
  intervention production, suppression de données ni envoi d'email effectués.
  Qualification Mailjet authentifiée et Qt natif restent en attente.

## Connecthys — repas liés aux accueils et priorité Journée (16/10/2026)

- Demandes explicites : repas non limité mais jamais confirmé lorsqu'une période
  d'accueil demandée reste en attente. Clarification de Franck : TOUTES les
  demi-journées demandées doivent être confirmées, pas seulement une ; règle
  identique pour la journée complète. Les parents sélectionnent Matin / Repas /
  Après-midi séparément. Matin seul + repas et repas + après-midi restent possibles.
- Demande complémentaire : si Journée + Matin + Après-midi sont cochés pour une
  même date/inscription, retenir Journée et écarter les deux choix redondants.
  Réponse générée : « Pour le [date], Journée ne peut pas être cumulée avec Matin
  et Après-midi. La formule Journée a été retenue ; les deux demi-journées ont
  été écartées car elles sont déjà incluses. » Journée retenue peut rester en
  attente ; ce texte ne prétend pas qu'elle a été confirmée. Pas de regroupement
  automatique des seules demi-journées quand Journée n'est pas demandée.
- Reproduction AVANT sur source 996d1b0e : deux scénarios / trois assertions en
  échec (repas traité avant un accueil en attente, deux variantes MAT/APM ; les
  quatre choix saisis au lieu de Journée + Repas). Aucun accès réel. Script/log
  qualification/portail-repas-avant.py/.log conservés hors Git et SHA épinglé.
- Nouveau helper pur UTILS_Portail_reservations : copie/normalisation des demandes,
  suppression des choix redondants uniquement parmi les ajouts, ordre stable
  des suppressions et accueil avant repas, contexte date + IDinscription dans
  l'activité/individu déjà fixé par la grille. Même inscription obligatoire pour
  reprendre une attente antérieure ; pas de mélange entre dates ou inscriptions.
- Les attentes déjà enregistrées sont aussi vérifiées lorsqu'une action ultérieure
  demande seulement un repas. Contrôle sur l'état réel de la grille après les
  suppressions du lot ; une attente annulée ne bloque plus. Les unités de repas
  incluses dans les formules d'accueil sont exclues de la recherche pour ne pas
  rendre le repas dépendant de lui-même. Pas de création de période non demandée.
- Contrat réel SaisieConso vérifié sur case fictive : mode='attente' seul remet
  une consommation unitaire existante en réservation à cause de etat par défaut.
  Le chemin repas lié transmet donc explicitement etat=mode. Pas de modification
  de SaisieConso générique, des tarifs ni des méthodes de sauvegarde/transactions.
  Une revalidation de la demande peut confirmer le repas quand les accueils le
  permettent ; pas de mécanisme de promotion en arrière-plan hors traitement.
- Précontrôle avant les saisies : repas facturé, pointé ou verrouillé → traitement
  manuel sans mutation du lot ; attente ancienne sans inscription identifiable,
  période fermée/inexistante ou unité repas Quantite/Evenement/Multihoraires → manuel.
  Support automatique repas unitaire/horaire. Une priorité Journée impliquant des
  demi-journées DÉJÀ enregistrées reste manuelle, même non facturées : pas de
  conversion/suppression silencieuse d'anciennes consommations. Deux formules
  Journée distinctes ambiguës ne sont jamais arbitrées automatiquement.
- Rôle de chaque choix dans Saisie d'une unité de réservation : Automatique,
  Autre choix indépendant, Matin, Repas, Après-midi, Journée complète. Noms usuels
  exacts reconnus avec accents/casse normalisés ; noms composés non devinés.
  Les libellés personnalisés se configurent explicitement. Stockage natif dans
  parametres / categorie noethys_sl_portail_roles_v1 / nom IDunite du portail,
  sans migration ni changement de portail_unites/protocole Connecthys. Un SELECT
  supplémentaire réutilise la connexion déjà ouverte par le traitement ; pas
  de connexion par ligne. Pas de lecture-écriture implicite des rôles à l'ouverture.
- 24 tests dédiés : véritable méthode Appliquer_reservations sur grille/DB fictives,
  cas MAT/APM/Journée, ordre d'arrivée, précédentes attentes, répétition/revalidation,
  annulation conservée, contexte date/inscription, zéro auto-dépendance, protections,
  règles ambiguës, vrais SaisieConso et dialogue wx de paramétrage (persistance mockée),
  helper pur et réentrant à quatre threads. 24 OK sur main/wx/qt. Suite ciblée plus
  large de 88 tests OK avant les derniers cas ; 33 ciblés finaux OK, puis CI ci-dessous.
- Départ : main 996d1b0e, wx 03f21ff8, qt e0dc317a. Code final :
  main **4d1189aa3e0c169cd61e9b8a15e6c7a374fc67bb**,
  wx **e18492286b809792affa32f89283908332d6a57f**,
  qt **44677fe918c67c22ee444661cbd8a12adf794b58**.
  Helper/paramétrage/tests identiques, et méthode Appliquer_reservations identique
  par SHA256 ab86988e65bfabbdaf0f207f139061fe1616456fad7a5cc7b652b37ecb39720d.
  Différence historique du reçu email wx conservée ; aucun merge global ni branche.
- CI main [38908786818](https://github.com/fr4nck/Noethys-SL/actions/runs/38908786818)
  SUCCESS : 686 tests / 6 ignorés ; wx
  [38908857188](https://github.com/fr4nck/Noethys-SL/actions/runs/38908857188)
  SUCCESS : 699 tests / 10 ignorés ; qt
  [38908879627](https://github.com/fr4nck/Noethys-SL/actions/runs/38908879627) SUCCESS : 651 tests / 6 ignorés, code commun wx ; UI Qt native non qualifiée.
  Les CI des lots intermédiaires 38907891890 / 38907989464 / 38908012930 étaient
  vertes ; le premier run main e2201647 a été remplacé et annulé par concurrence.
- Qualification : logique commune VALIDÉE par tests synthétiques sur les trois
  arbres ; recette UI Qt native, paramétrage réel des choix, grilles/tarifs du pilote,
  écritures MySQL de ce scénario et nouveau binaire empaqueté EN ATTENTE. Les tests
  ne prétendent pas remplacer la recette métier du prochain candidat distinct.
- Aucun email envoyé, synchronisation réelle, SQL de production ou réparation
  rétroactive. Annulations/délais existants et sauvegarde de la grille conservés.
  Cotisations automatiques toujours suspendues. Aucun nouvel installateur/tag/release ;
  la RC7.3 déjà fabriquée ne contient pas ce lot. Logs/scripts locaux dans qualification/
  hors Git ; prochaine étape : qualification pilote isolée puis candidat distinct si demandé.

## Carte Connecthys approuvée et captures opaques — 16/10/2026

- Clarification utilisateur : « tout est noir » concernait les captures, pas les
  polices. PNG wx capturés en 32 bits : alpha=0 sur le fond et le texte (vérifié
  par lecture de pixels RGBA), donc rendu noir dans certains afficheurs. Le script
  LOCAL qualification/accueil_preview.py capture désormais les composants dans
  wx.Bitmap(width,height,24). Nouveaux PNG vérifiés RGB sans transparence.
- L'agrandissement global de polices e4cfb6f7 (wx 5f6fae00 / qt c7c44849), issu du
  malentendu, a été annulé par commits de revert traçables, sans réécrire l'historique.
- Référence approuvée fournie : carte sombre arrondie, grand compteur, flèche ↗ en
  haut à droite, « demandes à traiter » dessous, état et heure puis message de
  synchronisation. Carte entière cliquable, curseur main, survol/focus plus clair
  et état pressé. Label accessible contenant le compte conservé ; zéro et compte
  inconnu distincts. Taille calculée pour le nombre ; minimum de hauteur 114 DIP
  évitant la coupure du texte. Boutons de synchronisation/outils conservés.
- État/journal compact rendu sans cadre natif, état et dernière heure sur une ligne,
  explication de l'état dessous. L'heure reste celle du dernier succès effectif,
  aucune nouvelle lecture/écriture DB ni changement du cycle de synchronisation.
  Ancien panneau non compact inchangé. Effectifs et créneaux du lot précédent conservés.
- Dernier code : main 8d3fe4773eb265b13e789de77dd120adcc37e5a4,
  wx 6847af908826070a5939a752eff4a5d9ac4db058,
  qt 97b3316fc8a239ed4a88c89b13e3320c261dedc3. Portages ciblés sans branche nouvelle.
- 28 tests ciblés natifs accueil + préférences OK sur main et rendu normal/survol
  inspecté, uniquement données fictives et DB mockée ; aucun client réseau lancé.
  CI rapide nouvelle main 38905557531 et wx 38905598688 EN COURS à la rédaction.
  Les CI vertes des sections antérieures ne qualifient pas cette nouvelle carte.
  UI Qt native / DPI / binaire empaqueté EN ATTENTE. Aucun nouvel installateur.
- Aperçus locaux fiables : qualification/connecthys-carte.png (composant seul) et
  qualification/accueil-wx-survol.png (vue globale), RGB opaques, hors Git. Les
  captures RGBA plus anciennes et la première annotation générée sur fond noir
  ne doivent pas être utilisées comme preuve du rendu natif. L'agent avait d'abord
  confondu ce défaut de capture avec un défaut de lisibilité ; ce diagnostic est corrigé.
- Prochaine étape : relever la fin des CI, puis qualification d'un candidat distinct
  si demandé. RC7.3 déjà fabriquée reste inchangée, ces retouches ne sont pas installées.

## Retours terrain RC7.3 — accueil, bouton et créneaux (16/10/2026)

- La capture fournie affiche RC7.3 sur le poste. Aucun lancement, accès à sa base,
  installation ni configuration de production effectués par l'agent.
- Demandes : supprimer l'effet de grand cadre blanc, réduire le vide, rendre le
  compteur Connecthys clairement cliquable et distinguer les créneaux EMS.
- Fond SYS_COLOUR_3DFACE repris par le bandeau ; marges réduites, titres alignés,
  colonne vacances compacte (240 DIP), agenda seul extensible, colonnes vides sans
  espace réservé. Préférences existantes conservées et agenda à défilement propre.
- Bouton demandes : bord arrondi visible, fond teinté, curseur main, surbrillance
  au survol et au focus, état pressé ; GenButton et sa navigation clavier/clic
  conservés, libellé multiligne avec nombre complet. Ancien panneau non compact
  inchangé. Aperçu natif isolé normal et survol inspecté, données strictement fictives.
- L'ancien total EMS était le nombre de personnes distinctes de la journée, pas
  un effectif simultané. Nouveau bandeau hors ALSH : une entrée par séance
  identifiée, ou unité/groupe/plage configurés ; horaire et nom de séance/unité
  affichés. Deux unités ou séances parallèles ne sont pas fusionnées parce que
  leurs heures coïncident. Une personne à deux séances compte une fois dans chacune.
  Dédoublonnage dans chaque créneau ; états attente/absence exclus ; ouvertures et
  séances vides conservent zéro. Groupes distincts séparés. Activités inactives exclues.
  Les heures des unités configurées servent de créneaux, à défaut celles des
  consommations ; une plage large configurée ne permet pas de déduire un effectif
  simultané maximal. Aucun calcul de pic d'occupation ni pointage en temps réel.
- Séance liée par IDevenement prioritaire sur la plage générique de l'unité.
  Consommation sans lien de séance alors que plusieurs existent sur cette unité :
  « horaire non renseigné », sans répartition arbitraire entre séances. Pas de règle
  de tarification, d'inscription, de facture, d'annulation ni d'écriture métier changée.
  ALSH conserve ses M/A par groupe, via unités de remplissage et conditions existantes.
- Toujours six SELECT, enrichis avec les métadonnées des ouvertures, événements et
  LEFT JOIN sur les clés des unités/événements. Aucun nouveau schéma ni connexion
  répétée par créneau. Quatre tests SQLite supplémentaires : créneaux distincts,
  dédoublonnage, mêmes horaires/séances distinctes, lien inconnu, groupes et unités
  parallèles, aucune écriture. Fixtures MySQL étendues sans données réelles.
- Dernier code : main **7ebe1cd985d84483c03ce2df3c387ca3311fd60c**,
  wx **9026ef5ce54091dcbfd622c4992ca9fa44b64b5c**,
  qt **6dd9f7bea23d2ed946185884f6a4a0078f9edb6f**.
  Neuf fichiers communs (code, tests, préparation serveur, workflows) comparés :
  identiques. Portages ciblés ; repas directeur RC8 et adaptations propres conservés.
- CI rapide main [38889769079](https://github.com/fr4nck/Noethys-SL/actions/runs/38889769079)
  SUCCESS : 662 tests / 6 ignorés ; wx
  [38889809868](https://github.com/fr4nck/Noethys-SL/actions/runs/38889809868) SUCCESS :
  675 tests / 10 ignorés ; qt
  [38889820013](https://github.com/fr4nck/Noethys-SL/actions/runs/38889820013) SUCCESS :
  627 tests / 6 ignorés, suite commune wx, pas une validation UI Qt native.
- Recette serveur du code FINAL
  [38889769125](https://github.com/fr4nck/Noethys-SL/actions/runs/38889769125) SUCCESS :
  MySQL 5.7.44 local réellement démarré sur runner isolé, 3 tests OK / aucun ignoré.
  Jeu fictif à deux créneaux d'une activité et deux séances simultanées identifiées :
  résultats SQLite/MySQL égaux et tables inchangées par read_day ; concurrence
  et actualisation conditionnelle du journal Mailjet conservées. Serveur stoppé,
  seule base unique de la recette détruite. Aucun appel API ni email.
- Recette indépendante sans packaging via workflow MySQL existant, entrée
  mode=accueil, appel du nouveau workflow réutilisable. La première tentative
  directe du nouveau nom était refusée car absent de master (branche par défaut
  historique). Le run 38889425498 a ensuite échoué AVANT les tests car le script
  préparateur n'existait que sur wx : copie identique partagée sur main/qt,
  run intermédiaire 38889670615 SUCCESS, puis run final ci-dessus. Aucun test
  ignoré/affaibli pour masquer cet échec. Runs rapides remplacés par nouveaux
  commits annulés par concurrence normale.
- Qualification : sources communes VALIDÉES sur les trois branches ; MySQL 5.7
  du code commun VALIDÉ sur main et blobs identiques wx/qt ; UI Qt native,
  configuration réelle EMS/ALSH, DPI et nouveau binaire empaqueté EN ATTENTE.
  Les 28 et 113 tests locaux intermédiaires sont antérieurs aux CI finales ;
  les CI finales font foi. Captures/logs fictifs dans qualification/ hors Git.
- Aucun nouvel installateur : le candidat RC7.3 du build 9a8cf664 reste inchangé
  et ne contient PAS ces retouches postérieures. Avant de reconstruire, attribuer
  une identité distincte au prochain candidat ; ne pas réutiliser RC7.3 pour un
  contenu différent. Cotisations automatiques toujours suspendues, issue #427
  non résolue par ces changements d'affichage. Prochaine étape : nouvelle recette
  visuelle du candidat distinct puis vérification des créneaux configurés du pilote.

## RC7.3 Windows fabriquée — preuves finales du 16/10/2026

- Candidat wx demandé par Franck, construit depuis **9a8cf664103d0e14fdaf0bcc83ccdbb7d535c630**.
  [Build 38884469875](https://github.com/fr4nck/Noethys-SL/actions/runs/38884469875) : SUCCESS.
  Identité publique 0.1.0-rc.7.3 ; compatibilité interne 1.3.4.4 conservée.
- [Artefact candidat 12039586320](https://github.com/fr4nck/Noethys-SL/actions/runs/38884469875/artifacts/12039586320),
  Noethys-SL-0.1.0-rc.7.3-Windows-candidat, 250592802 octets, expiration 15/11/2026.
  Deux livrables et SHA256SUMS.txt téléchargés et contrôlés localement sans installation :
  - Setup : 105263582 octets, SHA-256 `64d2d8e8cbdc609437a48d50e9bc2af1072c578500574e6ad67839cb0a7de19d`.
  - ZIP portable : 147058963 octets, SHA-256 `74ace81aacfab80b5f94b0324f5e3ca3a038a9ad852570148e3fbcff9e9f08cf`.
- Provenance BUILD-INFO conforme au SHA et au run ; notes RC7.3 présentes dans le ZIP.
  Table des modules du PYZ de Noethys.exe inspectée : CTRL_Accueil_compact,
  UTILS_Accueil_jour, DLG_Suivi_mailjet, UTILS_Suivi_mailjet, Outils.WordWrapRenderer
  réellement embarqués. Constantes Identite embarquées : RC7.3. Portable/README.txt présent.
- CI rapide wx [38884114272](https://github.com/fr4nck/Noethys-SL/actions/runs/38884114272) :
  SUCCESS, 671 tests / 10 ignorés. CI main cfa88af3eff44e55778dcbbee1a1b0c0a53c9bf6
  [38883974376](https://github.com/fr4nck/Noethys-SL/actions/runs/38883974376) : SUCCESS,
  658 tests / 6 ignorés. Aucun affaiblissement des tests.
- Contrats du build : 280 tests OK / 7 ignorés. Recette serveur MySQL 5.7.44 local
  **réel et jetable : 10 tests OK / aucun ignoré**, incluant sauvegarde/restauration
  avec les clients livrés, six SELECT de l'accueil identiques à SQLite sur jeu
  fictif (groupes, repas, heures, étiquettes), aucune écriture par ces lectures,
  GET_LOCK Mailjet réel, huit enregistrements concurrents / quatre threads sans
  doublon, Unicode hors BMP sur utf8 historique, actualisation conditionnelle
  empêchant une consultation ancienne d'écraser l'état livré. Aucun appel API.
- Smoke exécutable : processus encore actif après 12 secondes sur runner isolé.
  ZIP extrait démarré, profil créé dans Portable/ et aucune écriture de profil
  dans APPDATA/noethys. Setup fabriqué par Inno Setup. Les avertissements de
  nettoyage temporaire / ResourceWarning des tests ne sont pas des échecs de test ;
  ne pas annoncer pour autant une recette métier complète du binaire.
- Nouveau test de qualification commun : main cfa88af3, wx 1e705075,
  qt d9cadf38. Ce fichier est identique sur les trois branches ; exécution serveur
  prouvée sur wx seulement. Les identités / notes Windows restent propres à wx.
  Les modules communs accueil/Mailjet/adhésions étaient identiques au départ.
- INCLUS : accueil compact, bandeau configurable des effectifs PRÉVUS M/A par
  groupe ALSH, Connecthys compact, impression dépôts, arrondis rappels, suivi
  Mailjet volontaire, optimisation et profilage facultatif des consommations.
  EXCLU : chantier repas directeur multisite #430 réservé RC8 sur main.
  AUTO_CREATION_SUSPENDUE=True : protection P1 adhésions maintenue.
- STOP-GATE restant pour une utilisation habituelle : recette pilote isolée des
  unités M/A réellement paramétrées et de l'affichage DPI 125/150/200 %, parcours
  complets du binaire, API Mailjet authentifiée sur compte de recette. Pas de
  qualification MySQL 5.5 des nouveaux tests, de nouvelle optimisation des UPDATE
  ou des transactions, ni d'UI Qt native. Pas de gain terrain revendiqué.
- **Aucune installation terrain ni publication de release/tag**. RC7.2 sur le poste
  n'est pas devenue RC7.3 par cette fabrication. Aucun accès de production, email,
  impression physique ou donnée réelle. Logs et téléchargements conservés localement
  dans optimisation-consos-20261015/qualification/ hors Git. Les anciennes sections
  ci-dessous sont des états historiques ; la présente preuve fait foi pour le candidat.

## Fabrication RC7.3 autorisée — 16/10/2026

- Demande explicite de Franck : commencer à fabriquer RC7.3. Candidat wx uniquement,
  sans tag/release automatique ni installation sur un poste de production.
- Départ distant vérifié : main 7bc64844684598b8a1e418a5bec72dfdc45e8811,
  wx 90c1c0673b90007506a7a99938ea517ff119e08a,
  qt 8fe27d7285e5b47be68b89c4666aba7213d3770b.
  Comparaison des sept modules communs accueil / météo / Connecthys / Mailjet /
  adhésions : aucune différence. Le chantier repas directeur multisite #430,
  explicitement prévu RC8 et encore source candidate sur main, reste exclu de RC7.3 ;
  aucun correctif critique commun identifié dans cette différence fonctionnelle.
- Identité Windows 0.1.0-rc.7.3 ; version interne 1.3.4.4 préservée. Notes RC7.3
  ajoutées avant RC7.2, historique conservé. Cotisations automatiques toujours
  suspendues ; ni reprise automatique ni migration de schéma.
- Workflow Windows désormais volontaire seulement ; contrats du nouvel accueil,
  impression dépôt, rappels, Mailjet et performances inclus avant empaquetage.
  Serveur MySQL 5.7.44 jetable local existant réutilisé pour comparer les six SELECT
  de l'accueil à SQLite sur données fictives (deux groupes, repas, heures et tags),
  vérifier l'absence d'écriture et qualifier GET_LOCK / concurrence / Unicode /
  actualisation conditionnelle du journal Mailjet. Aucun appel API ni email.
- 80 tests locaux du candidat : OK / 4 ignorés (dont 3 exigeant ce serveur jetable).
  Ces tests serveur doivent réellement passer dans le build, ils ne sont pas encore
  qualifiés à la rédaction. Les autres contrôles pilote / DPI restent à faire.
- État : préparation, CI rapide puis fabrication à lancer. Aucun artefact RC7.3
  disponible à cet instant. Les sections historiques ci-dessous décrivent l'état
  aux étapes antérieures, pas une installation du nouveau candidat.

## Accueil compact — intégration demandée pour RC7.3, 16/10/2026

- Accord utilisateur : maquette Horizon ; météo quatre jours M/A, pluie en mm,
  vent en km/h avec flèche seule, clic sur tout le bloc pour les détails ;
  événements avec défilement indépendant et nombre configurable (0 = tous).
  Connecthys intégré à droite, demandes / état / progression / journal au clic.
  Quatre titres de même hauteur, date sur deux lignes « Vendredi 16 / Octobre 26 ».
- Bandeau sur toute la largeur : seulement activités programmées au jour affiché.
  Priorité ALSH par défaut, sélection et ordre personnel ; activités hors dates
  de validité exclues. Choisir M/A pour les accueils dont le nom ne permet pas
  l'identification automatique. Autres activités : total distinct de participants.
  Les effectifs sont PRÉVUS : pointage effectué après la journée selon l'utilisateur,
  aucune prétention de présence temps réel ni de contrôle automatique des absents.
- Départ vérifié : main `bb08cc752bdb4ca21a4719f73420f6444fd610fe` (avance repas
  conservée), wx initial `c9038741479b637397345d27e2b8fc435d4345d9`, qt initial
  `ec13651695a0f02ccc58136af335f00abf032edf`. Attention : les refs de suivi
  origin/wx `ca12e5a9` et origin/qt `31a2a5d9` étaient ANCIENNES ; ls-remote et
  FETCH_HEAD confirment les SHA précédents. Les quatre fichiers modifiés préexistants ont des blobs identiques
  sur les trois branches avant intervention. Aucun merge global / nouvelle branche.
- UTILS_Accueil_jour : six SELECT portables MySQL/SQLite, ouvertures / événements /
  consommations de la date, réservations et présences seulement, sets par personne.
  Attente et absences exclues ; personne de journée entière dans les deux périodes.
  Correspondance M/A indéterminée : « — », jamais un faux zéro. Heures MySQL timedelta
  et SQLite texte prises en charge. Aucune écriture métier / migration / tarification.
  Contrôle complémentaire de CTRL_Remplissage : les sites/tranches d'âge sont
  des GROUPES d'une même activité ALSH. Les lignes du bandeau ALSH sont donc
  séparées par IDgroupe (Bais −6 / Moutiers −6...), jamais agrégées entre sites.
  Test SQLite dédié : deux groupes, effectifs distincts, doublons inter-périodes.
  Contrôle supplémentaire : les deux compteurs réutilisent les associations des
  unités de remplissage MAT/APM (pas une coupure horaire à midi), leurs plages
  conditionnelles et étiquettes comme CTRL_Remplissage. Une réservation de repas
  à midi n'est pas une réservation d'après-midi sans association explicite.
  Préférences : unités matin/après-midi sélectionnables si les noms sont ambigus.
- Préférences : catégorie accueil_aujourdhui, identifiant utilisateur et base, comme
  la disposition historique ; choix des activités, M/A, ordre et nombre d'événements.
  Chargement dans le worker existant, résultat invalidé à fermeture/changement
  d'utilisateur. Rafraîchissement à cinq minutes, cache météo conservé à trente.
  Direction du vent : moyenne circulaire ; anciens caches sans direction → « — ».
- Connecthys : même instance client / mêmes commandes / cadence réseau inchangée.
  État basé sur le booléen réel de Synchro_totale, pas sur l'icône « on » ni l'heure
  de dernière tentative. Dernier succès distinct ; aucune remise à zéro des demandes
  si leur lecture échoue. Callbacks wx ignorés après destruction. Journal de session
  borné à 1000 lignes au clic ; destination historique du journal conservée.
- Recette synthétique native Windows : 77 tests initiaux (dont audit Connecthys) OK,
  54 ciblés finaux OK ; suite rapide locale 652 tests OK / 6 ignorés. Rendu natif
  isolé inspecté dans qualification/accueil-natif.png, puis largeur corrigée pour
  que Connecthys reste visible à droite à 1200 px. Maquette et captures ne sont
  pas des données de production ; qualification/ reste local hors Git.
- CI et portages finaux : VALIDÉS dans le tableau ci-dessous. EN ATTENTE :
  recette d'une base MySQL jetable et de la configuration des unités ALSH du pilote.
  UI Qt native non qualifiée. Aucun appel Connecthys réel, email, production ou
  installateur. Identités et Versions.txt inchangés : RC7.3 demeure une CIBLE,
  pas une version construite/installée. Coupe-circuit adhésions toujours actif.
- Première qualification CI main du lot `3622f28243c7fe47da3e7d22b99306391a5374ee` :
  [38875715124](https://github.com/fr4nck/Noethys-SL/actions/runs/38875715124) SUCCESS.
  Portages préparés et 55 tests ciblés OK sur wx/qt, non publiés à ce stade.
  La séparation par groupe ALSH est ajoutée ensuite, 41 tests ciblés OK avant
  nouvelle CI. Les différences repas présentes seulement sur main restent
  conservées ; ce lot n'affirme pas une synchronisation globale des trois branches.
- Recette native complémentaire : les libellés multilignes de GenButton étaient
  centrés comme une seule ligne, coupant le premier chiffre du nombre de demandes.
  BoutonDemandes utilise DC.DrawLabel multiligne ; rendu natif « 22 demandes »
  inspecté après correction, 18 tests ciblés OK. Derniers tests d'alignement : les
  quatre titres ont la même coordonnée Y et Connecthys reste dans le panneau.

### Qualification finale de l'accueil compact

Derniers commits de CODE (les commits de preuves suivants ne changent que ce document) :

| Branche | Code final | CI rapide |
| --- | --- | --- |
| main | `a31451d8f7b2ebfefe66b4af17fb09965eba2222` | [38878484485](https://github.com/fr4nck/Noethys-SL/actions/runs/38878484485) SUCCESS : 658 tests / 6 ignorés |
| wx | `c5c099390d19f7cef805fed25f5c060e89f6090e` | [38878617360](https://github.com/fr4nck/Noethys-SL/actions/runs/38878617360) SUCCESS : 671 tests / 10 ignorés |
| qt | `a45ffe9ebb915bd65a63c69f8c7e2ad027fa2031` | [38878631894](https://github.com/fr4nck/Noethys-SL/actions/runs/38878631894) SUCCESS : 623 tests / 6 ignorés, code commun wx |

- 17 nouveaux tests d'accueil compact : SQLite native éphémère, compteur distinct,
  plusieurs groupes d'une activité, repas seul non assimilé à l'après-midi,
  unités M/A explicites, conditions horaires et étiquettes, choix/ordre/activité
  inactive, direction circulaire, vrai wx (préférences, titres alignés et largeur,
  tous les pictogrammes), état Connecthys et échec conservant le compteur précédent.
  60 tests ciblés finaux OK sur chaque arbre ; suite locale antérieure aux trois
  derniers tests : wx 667 / 12 ignorés, qt 619 / 6 ignorés. Les CI ci-dessus font foi
  pour le CODE final, pas ces comptes locaux intermédiaires.
- Neuf fichiers communs de code et tests comparés par blob : identiques sur les
  trois SHA. Portages ciblés des seuls commits de ce chantier, aucun écrasement
  des variantes historiques ni du travail repas de main. Coupe-circuit adhésions
  toujours True sur les trois arbres. Les runs intermédiaires main remplacés par
  un nouveau push ont été annulés par la concurrence CI ; pas de test affaibli.
- VALIDÉ : lectures/sélections/dédoublonnages sur SQLite fictive, UI wx native,
  non-régression de la suite rapide, contrat de retour réel de synchronisation.
  EN ATTENTE : serveur MySQL jetable, correspondance des unités du poste pilote,
  recette DPI 125/150/200 %, UI Qt native et exécutable empaqueté.
- RC7.3 reste la cible autorisée, pas un candidat fabriqué. Aucun changement
  d'identité publique, de notes livrées, de tag/release, d'installation, de base
  de production ni d'envoi d'email. Vérifier les unités M/A avant usage opérationnel
  des compteurs pour l'encadrement ; « — » signifie correspondance à configurer.

## Impression du depot et rappels a 0 EUR — 15/10/2026

- Deux signalements terrain RC7.2 : les entrees Outils / apercu et imprimer
  de Saisie d'un depot ne donnent aucune fenetre (absence de parametres
  confirmee par Franck) ; des familles a jour figurent dans les candidats aux
  rappels avec 0,00 EUR. Pas de traceback du poste et aucune base reelle lue.
- Tetes reelles avant travail : main `1c6fd7a6fbc1ece8672949d86cdbe1df69e58794`,
  wx `2ce816bebf0fc78b114226fe789b1e9ddab6d98b`,
  qt `dd7633b93bd3bcb439a22a77e3cefc0cf1423665`.
  Fichiers compares avant modification ; seul UTILS_Printer differe entre
  main et wx sur six wx.Pen fixes a largeur 0 plutot que 0.25. Aucun ecart
  main/qt sur ce perimetre. Chemins de depot/menus/parametres identiques a
  ffd28de (candidat RC7.2) sur wx ; ne pas attribuer un correctif deja livre.
- Impression : Outils.ListCtrlPrinter importait WordWrapRenderer comme module
  global, resolu en sources via Chemins.sys.path, absent du namespace de
  package attendu par PyInstaller. Import relatif explicite, teste dans un
  sous-processus sans repertoire Outils sur sys.path. Defaut coherent avec
  l'absence des parametres ; confirmation binaire du poste encore necessaire.
- Suite du parcours reproduite sur vrai wx : TypeError wx.Pen avec epaisseur
  float (dont valeur utilisateur 0.25), puis DC.DrawRectangle avec coordonnees
  float. Largeurs converties a l'API wx (0 = trait fin), coordonnees converties
  uniquement au dessin dans les deux moteurs, calcul de mise en page inchange.
  Conservation des intros, totaux et pieds de page du moteur Noethys historique.
  Parametres rattaches a la fenetre de depot ; menus communs affichent une erreur
  et ecrivent le traceback dans journal.log plutot que laisser un clic muet.
- Recette synthetique : vraie liste de depot / menus wx ; deux actions routees
  vers leurs parcours respectifs, annulation sans impression, parametres et
  rendu multipage de 49 reglements fictifs dans wx.MemoryDC. Aucun spool,
  pilote, impression papier, email ni donnees de capture utilisateur utilises.
  Bitmap representatif de trois lignes, qualification/depot-synthetique.png,
  inspecte visuellement ; les 49 lignes sont couvertes par le test multipage.
- Rappels : SUM(.10 + .20) peut depasser .30 de quelques fractions de centime
  sur colonnes FLOAT ; Decimal(str(SUM)) conservait ce residu, solde<0 incluait
  le compte puis le format a deux decimales affichait 0.00. Arrondir la seule
  difference au centime avant son test, comme montant affiche ; aucune mise a
  jour de prestations, ventilations, factures, reglements ou rappels existants.
  Une dette reelle de 0.01 reste incluse ; zero, crediteur et compte solde exclus.
  Criteres de dates, activites, categories, exceptions et comptes inchanges.
- Contre-preuves avant correctif : reexecution de la version `1c6fd7a6` sur
  les donnees synthetiques renvoie la fausse dette (test en echec attendu) ;
  ancien import du moteur sans sys.path Outils leve ModuleNotFoundError
  WordWrapRenderer avant l'ouverture des parametres. Apres correctif, import
  et tests passent ; il ne s'agit pas d'une execution du binaire installe.
- Tests ajoutes a la CI rapide : test_noethys_sl_impression_depot (7),
  test_noethys_sl_rappels_solde (7). SQLite natif temporaire et montants Decimal
  de retour SQL simules, snapshots avant/apres des ecritures ; pilote Windows,
  serveur MySQL reel et parcours UI Qt natif non qualifies dans ce lot.
- STOP-GATE : aucun build, installation ni modification de production. Source
  corrigee ne signifie pas correction disponible dans la RC7.2 installee.
  Coupe-circuit P1 des adhesions et travaux Mailjet/performance conserves.
  Les preuves definitives par branche sont consignees apres les CI rapides.

### Preuves impression depot / rappels a zero

| Branche | Rappels (arrondi du solde) | Impression (dernier code) | CI rapide |
| --- | --- | --- | --- |
| main | `e15b7346a9872c694e2ab248a3aefa570c5835d1` | `67578569ff576fb39728fb891fbe9685e12671f1` | [38774271273](https://github.com/fr4nck/Noethys-SL/actions/runs/38774271273) SUCCESS, 629 tests / 6 ignores |
| wx | `dd09c8af79e5c201104b6d988b2ee51f2e321853` | `9a667e15186d9f1d6ffe7741d117b93bdd6f3a14` | [38775138685](https://github.com/fr4nck/Noethys-SL/actions/runs/38775138685) SUCCESS, 653 tests / 10 ignores |
| qt | `d05a330fbeb3e13bbc62b633248b9c94a4dd7880` | `4ced625974b1d35431a92eb219c9f1ae81100ec4` | [38775155967](https://github.com/fr4nck/Noethys-SL/actions/runs/38775155967) SUCCESS, 605 tests / 6 ignores, code commun wx uniquement |

Correctif complementaire independant : le moteur PrintPage renvoie "pages
restantes" (False a la derniere page), mais wx.Printout.OnPrintPage attend
"page rendue" ; False y annule le travail. Retour True apres rendu dans les
deux moteurs ; pagination et signal interne conserves. Contrat confirme dans
la [documentation wxPython](https://docs.wxpython.org/wx.Printout.html#wx.Printout.OnPrintPage).
Rendu reel de 49 lignes aussi exerce via le callback wx ; test de contrat
ajoute pour les deux moteurs (derniere page et page intermediaire).

| Branche | Dernier code (callback wx) | CI finale |
| --- | --- | --- |
| main | `85343b78dde07a6b640ebbbbeaefe1e29fbbcb71` | [38776091464](https://github.com/fr4nck/Noethys-SL/actions/runs/38776091464) SUCCESS, 630 tests / 6 ignores |
| wx | `20e160bae8a12b2f241e3c8fe0fe51557448a167` | [38776849847](https://github.com/fr4nck/Noethys-SL/actions/runs/38776849847) SUCCESS, 654 tests / 10 ignores |
| qt | `71ee00fcb1d73741ce3a9e75831e9fe4085c5eb0` | [38776863577](https://github.com/fr4nck/Noethys-SL/actions/runs/38776863577) SUCCESS, 606 tests / 6 ignores, code commun wx |

Lot initial : 13 nouveaux tests ; 58 tests cibles locaux OK / 1 ignore sur les trois
arbres ; suite rapide locale main 629 / OK / 6 ignores. Une premiere execution
locale avec PYTHONUTF8=1 impose a casse le decodage du stderr natif wx d'un
sous-processus de fermeture ; reexecution dans l'environnement Windows
d'origine OK, sans modifier ni affaiblir ce test. CI main confirme la suite.
Apres le correctif de callback : 14 tests nouveaux / OK sur les trois arbres.
Portages cibles prepares puis testes ; publication wx/qt apres CI main verte.
Meme code et memes tests sur les trois branches sur ce perimetre ; les six
corrections de largeur fixe deja presentes dans wx ont ete conservees et
portees dans main/qt, sans ecraser les autres differences des branches.

| Qualification | main | wx | qt |
| --- | --- | --- | --- |
| Rappel au centime / zero exclu / un centime conserve / snapshots SQLite | VALIDÉ | VALIDÉ | VALIDÉ code commun |
| Import par package / menus / proprietes / rendu wx.MemoryDC | VALIDÉ | VALIDÉ | VALIDÉ code commun wx |
| Cause sur binaire du poste, pilote physique, serveur MySQL reel | EN ATTENTE | EN ATTENTE | EN ATTENTE |
| UI Qt native | NON APPLICABLE | NON APPLICABLE | EN ATTENTE |
| Nouveau candidat / installation utilisateur | NON EFFECTUÉ | NON EFFECTUÉ | NON EFFECTUÉ |

Prochaine etape : qualification d'un candidat Windows distinct, sur profil
synthetique isole (dont import du moteur embarque), puis recette pilote de
l'apercu et des candidats aux rappels. Aucun build ni installation revendiques
ici. Logs et bitmaps dans qualification/ hors Git ; captures terrain non copiees
dans les tests. Les commits de preuves suivants ne changent que ce document,
pas les arbres de code qualifies par les runs cites.

## Suivi Mailjet dans Noethys — 15/10/2026

- Demande explicite de Franck : implementer la consultation des etats disponibles
  dans le portail Mailjet. Depart reel verifie : main `a597b478`, wx `ca12e5a9`,
  qt `31a2a5d9`. Comparaison des trois fichiers modifies avant portage : dialogs
  identiques ; protections supplementaires de UTILS_Envoi_email propres a wx
  (_ExigerAcceptation et retour None du PDF) a conserver par patch cible.
- Nouvel ecran **Suivi Mailjet** depuis Outils du Mailer ou bouton Historique,
  soumis au droit `outils_historique/consulter`. Compte d'expedition explicite,
  destinataire/sujet/etat/derniere verification, recherche, details. Ouverture
  sans HTTP ; verification volontaire de 1 a 50 lignes, HTTP hors thread wx.
  Fermer arrete les messages suivants et abandonne les resultats non conserves,
  sans callback wx depuis le travailleur ; timeouts HTTP bornes par requete.
- Journal partage dans la categorie reservee `noethys_sl_suivi_mailjet_v1`
  de la table native `parametres`, JSON versionne par compte/MessageID.
  JSON ASCII avec echappement Unicode pour conserver les emojis sur les
  anciens serveurs MySQL utf8 a trois octets, sans modifier leur encodage.
  Aucune migration implicite. Les nouvelles acceptations sont journalisees
  par destinataire To/Cc/Bcc, sans corps, piece jointe ou cle API ; les comptes
  sont identifies par SHA256 de la cle, les secrets restent dans leur configuration
  existante. Fichier capture sur thread UI avant l'envoi unitaire hors UI.
  Une panne du journal conserve le succes d'envoi et affiche un avertissement
  de ne pas renvoyer. Aucun renvoi automatique, SMTP inchange.
- Concurrence : enregistrement idempotent sous BEGIN IMMEDIATE SQLite ou
  GET_LOCK MySQL (liberation explicite), puis commit ; mise a jour conditionnee
  a l'ancienne valeur exacte du JSON (BINARY sur MySQL), sans ecraser une
  consultation concurrente. Erreur API : garder dernier etat et date verifies,
  afficher l'erreur de consultation separement. Journal corrompu : refuser,
  ne rien effacer. Lecture des 500 dernieres entrees du compte, pas de purge.
- Ancien historique : seules traces categorie 33 avec suffixe MessageID complet
  sont proposees ; reprise volontaire apres choix confirme du compte emetteur.
  Pas de recherche approximative par sujet/adresse. Le destinataire inconnu
  est retrouve par l'API ; les traces tronquees restent non recuperables ici.
- Consultation : exclusivement GET HTTPS api.mailjet.com, sans redirection,
  identifiant entier 64 bits conserve en texte, verification compte/ID/adresse.
  `/message/{ID}` fournit l'etat ; `/messagehistory/{ID}` les evenements observes
  (100 maximum), `/bouncestatistics/{ID}` le motif d'echec si disponible.
  401/403/404/429/5xx, JSON malforme et panne reseau ne sont jamais une livraison.
  401/403/429 arretent le reste du lot. Secrets masques dans les details.
- Semantique : accepte par Send API != livre ; sent/delivered signifie accepte
  par le serveur destinataire, pas presence garantie en boite de reception.
  opened = ouverture signalee, pas preuve de lecture. Sources officielles :
  [message](https://dev.mailjet.com/docs/email-api/getting-started/retrieve-sent-message),
  [historique](https://dev.mailjet.com/docs/email-api/getting-started/view-message-history),
  [etats](https://documentation.mailjet.com/hc/en-us/articles/360048398994-Email-statuses-all-metrics-explained).
- Tests `test_noethys_sl_suivi_mailjet` : 36, OK / 1 ignore (MySQL local non
  declare). SQLite natif jetable, vrai wx, API/Send simulees ; concurrence
  enregistrement/deux postes, CAS obsolete refuse, rollback, idempotence,
  parametres etrangers preserves, secrets, limites API, fermeture en cours,
  droits refuses avant lecture DB, envoi accepte malgre panne du journal.
  Test MySQL conditionnel sur base locale neuve via `_garde_reseau` ; aucune
  connexion production. Capture de recette locale sur quatre destinataires
  example.org, ecran verifie. Test ajoute aux CI rapides.
- STOP-GATE : pas d'appel authentifie Mailjet, test serveur MySQL reel EN ATTENTE,
  UI Qt native EN ATTENTE ; qualification pilote avec compte de recette avant
  de qualifier une livraison utilisateur. Aucun email reel, schema, donnee
  production, regle financiere, coupe-circuit d'adhesion ou installateur modifie.
  Aucun suivi automatique retroactif ni promesse de reception/lecture.
  Les preuves CI et commits de portage sont consignees apres qualification.

### Preuves du suivi Mailjet

Lot initial, avec compatibilite Unicode :

| Branche | Implementation | Compatibilite Unicode (dernier code) | CI rapide |
| --- | --- | --- | --- |
| main | `7390e38369bcc5f869632f7c3911180aac71293f` | `e3cc2e2b2a0b0364370546cd4bc0ac6e6dbc16e5` | [38751242315](https://github.com/fr4nck/Noethys-SL/actions/runs/38751242315) SUCCESS, 615 tests / 6 ignores |
| wx | `792ef1a24cf910dc2e7e7ff8bbc77a4abe11db86` | `47819c107599b5b4caafd1cca3ebcd0ea548d4e1` | [38752182475](https://github.com/fr4nck/Noethys-SL/actions/runs/38752182475) SUCCESS, 639 tests / 10 ignores |
| qt | `d902947ca8fac7d780b0378342bef5cd75ea3b2d` | `559b8acf99fed335019af8347ea796b933c068e4` | [38752201133](https://github.com/fr4nck/Noethys-SL/actions/runs/38752201133) SUCCESS, 591 tests / 6 ignores, code commun wx uniquement |

Dernier correctif independant : consommer le resultat SELECT RELEASE_LOCK
avant restitution d'une connexion MySQL non bufferisee au pool ; LIMIT 1 sur
le controle d'existant pour ne laisser aucun resultat multiple en attente.
Test protocole de curseur non bufferise ajoute (36 tests module, OK / 1 ignore,
sur les trois arbres) ; le test MySQL serveur reste conditionnel et non execute.

| Branche | Dernier commit code | CI finale |
| --- | --- | --- |
| main | `675420c271377671c9d1a7a10a58dc6b71359f9d` | [38752508891](https://github.com/fr4nck/Noethys-SL/actions/runs/38752508891) SUCCESS, 616 tests / 6 ignores |
| wx | `35990787fce2d2e9fbf11ec730b32a016d6921f0` | [38753841669](https://github.com/fr4nck/Noethys-SL/actions/runs/38753841669) SUCCESS, 640 tests / 10 ignores |
| qt | `925d1d2bd15fe68c3cb89cddce07c7c1e1576b97` | [38753857972](https://github.com/fr4nck/Noethys-SL/actions/runs/38753857972) SUCCESS, 592 tests / 6 ignores, code commun wx uniquement |

Publication main puis portages cibles apres CI main SUCCESS. Tests locaux :
suite rapide 614 / OK / 6 ignores avant le dernier test Unicode ; module
Unicode 35 / OK / 1 ignore, puis final 36 / OK / 1 ignore. Sur chaque portage : 96 tests cibles / OK / 1 ignore
(suivi, acceptation, erreurs, confirmations, cycle de progression, Mailer,
changelog). Deux dependances absentes du runtime local (xlrd et psutil) ont
ete installees dans qualification/dependances uniquement pour la suite large,
sans changer l'environnement utilisateur. Premier controle statique des
boutons ajuste en explicitant les ajouts au sizer, sans affaiblir le test.
Run main initial 38750725644 annule par concurrence GitHub au profit du
correctif Unicode ; il ne constitue pas une preuve de qualification.

Nouveaux moteur, dialog et tests identiques sur les trois branches ; blob
moteur final `ac33b0aa5ad5ac4b623270486a1e139fbc2e4c71`, dialog
`e0a05ef8c613f0944b661cf9c20f0a9c069423d4`. Dialogs historiques/Mailer
identiques ; les seuls ecarts du moteur d'envoi wx restent ses protections
anterieures (_ExigerAcceptation / PDF None), conservees apres comparaison.
Pas de merge global, nouvelle branche ni force-push.

| Qualification | main | wx | qt |
| --- | --- | --- | --- |
| API simulee / journal SQLite / concurrence / fermeture wx | VALIDÉ | VALIDÉ code commun | VALIDÉ code commun |
| Serveur MySQL reel / API Mailjet authentifiee de recette | EN ATTENTE | EN ATTENTE | EN ATTENTE |
| UI Qt native | NON APPLICABLE | NON APPLICABLE | EN ATTENTE |
| Installation utilisateur / nouveau candidat Windows | NON EFFECTUÉ | NON EFFECTUÉ | NON EFFECTUÉ |

Journaux/capture synthetiques et dependances locales sont dans qualification/
hors Git ; aucun fichier sources/ modifie. La prochaine etape est une recette
pilote isolee (serveur MySQL jetable et compte Mailjet de recette, sans email
reel), puis qualification d'un candidat distinct si demande. La RC7.2 deja
installee ne contient pas cette fonctionnalite. Les prochains commits de
preuve ne changent que ce document, pas le code qualifie par ces CI.

## Cotisations automatiques multi-activites — 15/10/2026 (#426)

- Demande precisee par Franck : une cotisation individuelle par beneficiaire,
  plusieurs activites associees dans `cotisations.activites`, sans nouvelle
  facturation ; ajout de l'activite declencheuse puis des autres activites
  du meme dispositif frequentees pendant sa validite. Le selecteur manuel
  existe deja dans DLG_Saisie_cotisation et utilise les IDs separes par `;`.
- Depart initial main d4210e77, wx fc80e29b, qt a5745b99 ; nouvelles tetes
  concurrentes conservees avant integration : main
  `4ee3aeb500a52617bd9ac31d807449382a757a02`, wx
  `84d9f96e4fd71009471f7bf26c2c1a693816283c`, qt
  `cd3c938af6012e8427ef8e5aeb1ea5b9f599fe1a` (changelog/version interne).
  Nouvelles consignes AGENTS.md lues. Moteur Adhesions identique avant portage.
- Correctif : GetParticipations expose IDactivite ; CreerAdhesion renseigne
  le champ natif. CompleterActivitesAutomatiques ajoute l'union sur une
  cotisation marquee [adhesion-auto], dans sa periode inclusive, pour les
  activites liees au meme type, jusqu'a la date de reference incluse
  (aucune seance posterieure a cette date).
  Reservation/present et prestation isolee suivent les criteres existants.
- Relire la liste sous verrou du titulaire/type, transaction SQLite IMMEDIATE
  ou MySQL GET_LOCK + SELECT FOR UPDATE ; update du seul champ activites et
  historique dans une meme transaction. Rollback sur erreur ; pas de perte
  d'ajout concurrent. Garder les rattachements existants, sans doublon ; ne pas
  les retirer apres annulation. Respecter les periodes verrouillees ; rejeter
  un format invalide ou plus de 450 caracteres, sans tronquer les donnees.
- Pas de modification des cotisations manuelles, des dates/montants,
  prestations, factures, ventilations ou reglements existants. Titulaire
  personne physique/structure et payeur de la participation conserves.
- Tests locaux : 90 executes, OK, 3 ignores faute de serveur MySQL local
  declare ; dont 17 nouveaux tests (16 executes, 1 MySQL conditionnel).
  Deux processus SQLite : A lit avant ecriture, B attend le verrou puis
  relit ; les deux activites restent associees. Tests : creation depuis
  conso/prestation, cumul sans double cotisation ni prestation, idempotence,
  dates/deux annees, structures/sections/payeur, manuel, annulations, rollback,
  periode verrouillee, format et limite, facturation/ventilation preservees.
  Syntaxe compilee ; CI main [38744861087](https://github.com/fr4nck/Noethys-SL/actions/runs/38744861087) SUCCESS au commit 55889bad.
- STOP-GATE : AUTO_CREATION_SUSPENDUE reste True et le hook de grille garde
  son retour P1. Ce lot ne reactive pas l'automatisme : cloture mensuelle,
  facture anticipee, apercu comptable et annulations controlees restent a
  terminer dans #426 ; serveur MySQL reel et UI Qt native EN ATTENTE.
  Aucun build, installation, nouvelle branche, suppression de donnees, email,
  intervention production ou alteration des notes de version livrees.

### Preuves du rattachement multi-activites

| Branche | Commit moteur/tests | CI rapide |
| --- | --- | --- |
| main | `55889badb2adc91ec1a4f0a43d75ef8ce6fe0b44` | [38744861087](https://github.com/fr4nck/Noethys-SL/actions/runs/38744861087) SUCCESS, 580 tests, 5 ignores |
| wx | `6cb8149c94b261c2935894b5be80ce8a9937038d` | [38746118910](https://github.com/fr4nck/Noethys-SL/actions/runs/38746118910) SUCCESS, 604 tests, 9 ignores |
| qt | `6fc8ce60bda1f8a088275059f21edee9ef007cd3` | [38746117092](https://github.com/fr4nck/Noethys-SL/actions/runs/38746117092) SUCCESS, 556 tests, 5 ignores ; code commun wx, pas UI Qt native |

Moteur identique (blob `9a739e2fca0b8e03026aedf19877ece53b7eb8eb`) et
deux fichiers de tests identiques sur les trois branches. Portages cibles
apres CI main, tests locaux 69 / OK / 3 ignores sur wx et qt ; leurs autres
changements, dont notes de version propres et version interne, conserves.
Pas de nouvelle branche ni force-push. Les commits de preuve suivants ne
changent que ce document ; aucune CI runtime distincte revendiquee dessus.

| Qualification | main | wx | qt |
| --- | --- | --- | --- |
| Activite declencheuse / union / non-double facturation / SQLite concurrent | VALIDÉ | VALIDÉ code commun | VALIDÉ code commun |
| MySQL reel : lecture sous verrou / union concurrente | EN ATTENTE | EN ATTENTE | EN ATTENTE |
| Activation auto apres cloture ou facture anticipee / annulations financieres | EN ATTENTE / STOP-GATE | EN ATTENTE / STOP-GATE | EN ATTENTE / STOP-GATE |
| UI Qt native | NON APPLICABLE | NON APPLICABLE | EN ATTENTE |

Le test MySQL supplementaire utilise exclusivement le serveur local de
recette autorise par `_garde_reseau`, une base `zz_test_adh_*` creee par le
test et deux processus ; il reste ignore sans NOETHYS_TEST_MYSQL_*.
Ce test conditionnel ne vaut pas preuve d'execution serveur.

Prochaine etape : qualifier ce test sur MySQL jetable et le nouveau
declenchement financier de #426 avec apercu avant validation, exclusion des
reservations futures et annulations controlees. Ne pas lever le coupe-circuit
de grille sur la seule presence du rattachement multi-activites. Pas de
modification en production, de lot retrospectif ou d'installateur dans cette
session ; les travaux #427 et les notes de version livrees restent conserves.

### Signalement Mailjet — verification en lecture seule

Franck souhaite retrouver dans Noethys les statuts accessibles sur le portail
Mailjet. Audit main : UTILS_Envoi_email.Mailjet conserve MessageID/MessageUUID
sur le message accepte ; DLG_Mailer.MemorisationHistorique ajoute les MessageID
au texte d'historique (categorie 33) pour les personnes retrouvees par adresse.
Aucun appel de consultation du statut ou de l'historique Mailjet trouve dans
les sources. Ne pas deduire la livraison de l'acceptation par Send API.

Documentation officielle verifiee :
[consulter un message](https://dev.mailjet.com/docs/email-api/getting-started/retrieve-sent-message),
`GET /v3/REST/message/{MessageID}`, et
[historique d'un message](https://dev.mailjet.com/docs/email-api/getting-started/view-message-history).
Piste a developper : conserver une correspondance durable par destinataire,
puis consulter et afficher les statuts fournisseur dans Noethys ; le texte
libre et borne de l'historique ne constitue pas a lui seul un registre exhaustif.
Cette consultation pourrait se faire depuis le poste, sans serveur de webhooks
obligatoire. Aucun code de suivi livre dans cette session, aucune connexion
authentifiee au compte Mailjet, aucune lecture des cles ni aucun email envoye.


## Reprise #427 — preparation client des consommations — 15/10/2026

- Depart distant verifie : main `0b2e2d47b2a899bc650cc6ec1090b67129897dbe`,
  wx `23a49c7d129d7ce7c6167437c6fb939eaa835e53`,
  qt `9f27a1378ce28c96f79e8ff5d080e2f3d77b45c1`. Fichiers grille, GestionDB et
  handlers OK identiques ; arbres globaux divergents, aucune fusion globale.
  CI precedentes 38724108383 (main f04e68a) et 38724128232 (wx 23a49c7) SUCCESS.
- Audit, protocole et mesures : [PERFORMANCE_CONSOMMATIONS_427.md](PERFORMANCE_CONSOMMATIONS_427.md).
  Vingt champs reecrits par UPDATE, connexions parametres, Commit historique,
  risque d'ecrasement concurrent et rafraichissement famille apres modal examines.
  Source officielle mysqlclient 2.2.7 reproduite sans serveur : 1/10/50 UPDATE
  donnent 1/10/50 appels transport, INSERT regroupe ; version RC7.2 non deduite.
- Lot runtime limite : ne preparer les vingt champs que si la consommation
  genere une ecriture. Suppressions implicites et multihoraires conservees.
  Aucun SQL, Commit, historique, tarif, facture, annulation ou adhesion change.
  Benchmark synthetique 10 000 lignes / une modification : mediane neuf essais
  33,073 -> 2,120 ms ; 50/50 modifications 0,426 -> 0,426 ms. Aucun gain terrain
  revendique, nombre d'acces SQL identique.
- Qualification locale : 67 tests Python 3.10/wx, OK, deux skips MySQL ; huit
  tests nouveaux dont SQLite deux connexions/deux threads et attente de verrou.
  Comparaison avant/apres 45 combinaisons : SQL/valeurs/historique/commits/erreurs
  identiques. Nouveau test ajoute a la CI rapide, CI main [38732132634](https://github.com/fr4nck/Noethys-SL/actions/runs/38732132634) SUCCESS au SHA 2aaa3046a6a4bd928eb8ad5d6f02b74c3851f87b.
- STOP-GATE : moteur Docker local indisponible, aucune recette serveur MySQL
  ni UI Qt effectuee. UPDATE groupes/champs reduits/pooling/transactions restent
  EN ATTENTE. RC7.2 ffd28de ne contient aucun lot #427. Aucun build/installation,
  production, email, donnees existantes ou references historiques touches.
- Copie isolee locale : `optimisation-consos-20261015` dans l'espace du projet ;
  `qualification/` contient sources de mesure et journaux synthetiques hors Git.
  Sources synchronisees et anciens WIP preserves. Publication main puis portages
  cibles wx/qt effectues ; trois CI SUCCESS, voir preuves finales ci-dessous.

### Preuves finales du lot #427 — 15/10/2026

| Lot / preuve | main | wx | qt |
| --- | --- | --- | --- |
| Preparation client #427 | VALIDÉ `2aaa3046a6a4bd928eb8ad5d6f02b74c3851f87b` | VALIDÉ `cc436b2c05ccedf30fc823dd82b332cb7324481b` | VALIDÉ code commun `ab23538919321fe721bf102e94eb56f086ccf68b` |
| CI rapide syntaxe + contrats Windows | [38732132634](https://github.com/fr4nck/Noethys-SL/actions/runs/38732132634) SUCCESS, 553 tests / 4 skips | [38732766252](https://github.com/fr4nck/Noethys-SL/actions/runs/38732766252) SUCCESS, 577 tests / 8 skips | [38732765420](https://github.com/fr4nck/Noethys-SL/actions/runs/38732765420) SUCCESS, 539 tests / 4 skips ; commun wx, pas UI Qt native |
| Tests locaux transports/profilage/nouveau lot | VALIDÉ, inclus dans 67 tests | VALIDÉ, 19 tests | VALIDÉ commun, 19 tests |
| Serveur MySQL / UPDATE groupes / pooling | EN ATTENTE / STOP-GATE | EN ATTENTE / STOP-GATE | EN ATTENTE / STOP-GATE |
| Recette interface Qt native | NON APPLICABLE | NON APPLICABLE | EN ATTENTE |

Les blobs CTRL_Grille.py (`0b92eaa09815b5bb3ad6385b1bfd3a712e88dbca`),
GestionDB.py (`c4ed9fd040430883609f7e2169240d484ede6352`), harnais, benchmark et
nouveau test sont identiques sur les trois commits de code. Chaque portage
a pour parent la tete initiale de sa branche. Les workflows sont adaptes
par ajout du seul nouveau test, sans perdre leurs autres contrats. Aucune
nouvelle branche, fusion globale ni force-push ; publication main apres
tests locaux, puis wx/qt apres CI main SUCCESS. Les notes de preuve ajoutees
ensuite ne changent que docs/dev/REPRISE_CODEX.md, sans nouvelle CI runtime.

L'issue [#427](https://github.com/fr4nck/Noethys-SL/issues/427) reste ouverte :
un cout client est reduit, le goulet terrain n'est pas mesure. Pas de nouvelle
qualification globale des differences entre branches, pas de release stable
revendiquee. RC7.2 ffd28de et l'installation Windows restent hors de ce lot.
Prochaine etape et STOP-GATE : serveur jetable synthétique, mesures SQL avec
pilote/version explicites et rafraichissement famille post-modal ; aucune
execution de recette sur production.


Document de transmission (Claude Code → Codex). Mettre à jour en fin de chaque session.


## Stabilisation Windows → candidat RC6 (wx) — 14/10/2026

- **Départ vérifié** : `wx = origin/wx = 556450a8` (RC5 déjà construite : anomalies devis, PHOTOS et pièces jointes) ; `main` local `2e7aa965`, `origin/main = b52aa6eb` ; `qt` local `bd3eae39`, `origin/qt = 2146ad13`. PMSL-Arch `main = cbe3e6e`. Artefacts RC4/RC5 conservés intacts (`artifacts-rc5/`, hors Git).
- **Commits sur `wx`** (push fast-forward non forcé `556450a8..f571f650`) :
  - `194bcaeb` fix(sauvegarde) : `mysql-client/bin` livré prioritaire ; fichier d'identifiants quoté/UTF-8, création exclusive 0600 (un mot de passe contenant `#` était tronqué : `ERROR 1045` reproduit avec mysql 5.7.44) ; dump soumis à `AnalyserDumpSQL` avant scellement.
  - `4e056e4d` fix(recus) : `Envoyer_lot` n'accepte plus un retour 0/None ; erreur `doc.build` du reçu plus avalée (`TypeError` Python 3) ; `CreationPDF` renvoie False sans PDF ; `EnvoiEmailFamille` sans PDF n'envoie rien ; saisie de règlement : plus de dialogue détruit réutilisé, échec signalé ; portail manuel par Email validé seulement si l'envoi a été accepté.
  - `d9713c69` build(windows) : clients mysql/mysqldump 5.7.44 (archive Oracle SHA-256 `aed661fe…e70e`, sources GPLv2 `d03d8ff6…d919`), runtime VC++ cohérent, contrôle DLL ; recette réelle CI ; **ZIP portable corrigé** (RC4/RC5 sans dossier `Portable/` : profil écrit dans `%APPDATA%`).
  - `f571f650` build : identité 0.1.0-rc.6.
- **Tests** : `test_noethys_sl_mysql_client_embarque` (7, dont aller-retour réel) et `test_noethys_sl_recus_envoi` (9, SMTP de capture local). Contre-épreuves sur code précédent : 6/6 et 5/9 en échec. Local : 67 tests sauvegarde/SQL et 147 email/reçus OK ; aller-retour réel OK contre MySQL 5.7.44 jetable `127.0.0.1:3399` (scratchpad, arrêté).
- **CI** : [wx #38534018279](https://github.com/fr4nck/Noethys-SL/actions/runs/38534018279) **SUCCÈS** au SHA `f571f650` : 151 tests de contrats, aller-retour réel exécuté (non ignoré), démarrage du ZIP extrait avec `%APPDATA%` vide (profil créé dans `Portable/`). Artefacts (rétention 30 jours, copie locale `artifacts-rc6/`, hors Git) :
  - `acec19be20ac0a1516f2bcb0e448ff47302df7c6de8d98d9c6eca4c54825e2a3  Noethys-SL-0.1.0-rc.6-Setup.exe`
  - `912e9475b865a64d626071cbe6d5898b995c3a91ba605a9d614e6d006c80a82e  Noethys-SL-0.1.0-rc.6-Windows-portable.zip`
- **Préexistant, hors lot** : `test_noethys_sl_etat_global_calcul.BugPorteeUniteNTests` échoue déjà à `556450a8`.
- **Non réalisé** : test sur un Windows propre et recette manuelle (`docs/recette/RECETTE_RC6_WINDOWS.md`) : **EN ATTENTE**. Aucune release ni tag. Publication : joindre ou référencer les sources MySQL 5.7.44 (GPLv2).
- **Restant à reproduire / corriger** : doublon après coupure SMTP post-DATA (EMAIL-03), refus partiel ignoré (EMAIL-05), pièce commune doublée au 2e clic (EMAIL-09), succès partiel multi-adresses compté comme envoyé, variable `email_envoye` morte dans `DLG_Saisie_reglement`, chemins non ANSI passés aux clients MySQL (échec détecté, pas de faux succès ; non testé).

| Correctif | `main` | `wx` | `qt` |
| --- | --- | --- | --- |
| Lot A sauvegarde (`194bcaeb`) | ABSENT / EN ATTENTE | VALIDÉ (CI #38534018279) | ABSENT / EN ATTENTE |
| Lot B reçus (`4e056e4d`) | ABSENT / EN ATTENTE | VALIDÉ (CI #38534018279) | ABSENT / EN ATTENTE |
| Packaging Windows (`d9713c69`) | NON APPLICABLE | VALIDÉ (CI) ; Windows propre EN ATTENTE | NON APPLICABLE |

Prochaine étape : recette manuelle RC6 sur VM Windows propre et copie Docker, avec SMTP de capture ; puis report ciblé de `194bcaeb` et `4e056e4d` vers `main` et `qt` (cherry-pick testé, sans fusion globale).

### Prérelease RC7 publiée — 14/10/2026

- Publication expressément autorisée. `34ff3faa` identité 0.1.0-rc.7 ; premier build [#38539258158](https://github.com/fr4nck/Noethys-SL/actions/runs/38539258158) en ÉCHEC aux contrats (App wx détruite par un module voisin, `PyNoAppError`), avant tout packaging, donc rien publié ; `e8488e71` corrige les deux tests (production inchangée).
- Build [#38539592015](https://github.com/fr4nck/Noethys-SL/actions/runs/38539592015) **SUCCÈS** au commit `e8488e715642fc357a68b150355599ad2e74ea83` ; tag annoté `noethys-sl-0.1.0-rc.7` sur ce commit.
- [Release Noethys SL 0.1.0 RC7](https://github.com/fr4nck/Noethys-SL/releases/tag/noethys-sl-0.1.0-rc.7) : Pre-release, non « Latest » (Latest reste `vanilla-1.3.4.2-r2`). Fichiers revérifiés après téléchargement depuis GitHub :
  - `acb98190079f97502060f43debb613196cf88f801964fa46405c9a504ff3fc1b  Noethys-SL-0.1.0-rc.7-Setup.exe`
  - `0f229b5ead42728c9c4101d99dbba0bdede6dd7a918c4f3309d21e27b8efa27f  Noethys-SL-0.1.0-rc.7-Windows-portable.zip`
  - `d03d8ff688862c40da3488451072a4b2178a86b53b4a7546ee5f864bb15cd919  mysql-5.7.44.tar.gz` (sources GPLv2 jointes)
- Restent à faire : recette manuelle des exécutables, photos sans base `_photos` (différé), report vers `main`/`qt`.

### Retours de recette RC6 réelle — 14/10/2026

- `530a0cf4` fix(impression) : `UTILS_Printer.py`, six `wx.Pen(wx.BLACK, 0.25, wx.SOLID)` → largeur `0` (troncature historique de 0.25, trait le plus fin). Test `test_noethys_sl_printer_pen`.
- `e73fa55e` fix(releve) : `ConvertCouleurPDFpourWX` renvoie des entiers ; `ColourSelect` reçoit `(204, 204, 255)`. Avec wx récent, `SetColour((204.0, 204.0, 255.0))` affichait aussi silencieusement du blanc. Test `test_noethys_sl_releve_couleur`.
- `c49da16f` ci : tests RC6 ajoutés à la CI rapide. [wx #38537544795](https://github.com/fr4nck/Noethys-SL/actions/runs/38537544795) **SUCCÈS** (wxPython 4.2.5, 552 tests). Contre-épreuve locale : 4 échecs sur le code précédent.
- Ces correctifs ne sont **pas** dans les artefacts RC6 du run #38534018279 : une nouvelle candidate (RC7) sera nécessaire, sur décision humaine.
- **`Unknown database 'pelemele_photos'` (investigation, aucune base touchée)** : Noethys ouvre `<fichier>_photos` (`GestionDB.DB(suffixe="PHOTOS")`) ; l'erreur 1049 signifie que la base n'existe pas sur ce serveur (un défaut de droits donnerait 1044). `Noethys.py:1543` ne crée pas PHOTOS (ni DOCUMENTS) pour un fichier « Serveur internet » ; une restauration de `.nod` ne contenant que `pelemele_data.sql` produit le même état. Lectures sans effet (photos absentes, journal bruyant) ; en revanche, **l'ajout d'une photo est silencieusement ignoré** (`CTRL_Photo.py:268`, sans message). Vérification en lecture seule à faire par l'administrateur : `SHOW DATABASES LIKE 'pelemele%';`. Création éventuelle : procédure existante `A9079`, sur copie d'abord, après décision ; non exécutée.


## Lot limité Noe-032 — ZIP partiel sur fichier absent — 10/10/2026

- **Départ vérifié** : `main = wx = qt = 025112dd55744988989f0c3f321e76557f0fe11d` ; `master = b0be3c7ebdf2d69d6028eb4fd6fc08e340a68b9e`, toujours branche par défaut. [CI wx #38033543533](https://github.com/fr4nck/Noethys-SL/actions/runs/38033543533) : succès au SHA antérieur `32841c42`. Consignes lues : `AGENTS.md`, ce document, PMSL-Arch `main` (`cbe3e6e65b53d98783a5192846979aedbe375465`), politique de développement, ADR-006/010 et gouvernance Actions.
- **Code : `4b5dc5103d8af14e5eab1500368be43e55061415`**. Deux lignes ferment puis suppriment le ZIP temporaire lorsqu'un fichier local manque. Test historique `test_missing_local_file_closes_zip_and_removes_partial_archive` repris avec assertions intactes et harnais AST isolé ; deux cas ajoutés : absence après une première entrée avec destination existante préservée, sauvegarde complète réussie. Test inclus en CI rapide ; restauration SQL inchangée.
- **25 tests historiques inchangés réutilisés** (`test_noe_032_backup_integrity.py`, `test_noe_032_restore_flow.py`) : 25/25 sur le module `master`, mocks et données fictives. Sur `main` initial : 5 succès / 5 échecs / 15 erreurs ; candidat : 6 succès / 5 échecs / 14 erreurs. Seul le test du lot passe de défaut à succès ; les 19 écarts préexistants hors lot (SQL, exceptions sous-processus, nettoyage email…) restent EN ATTENTE. Journaux hors Git dans l'espace Codex : `tmp/qualification-noe032/main-before.log` et `main-after.log`.
- **Qualification** : verrou ZIP Windows reproduit avant correction ; 15 tests ciblés réussis après, compilation et diff contrôlés. [CI main #38036079406](https://github.com/fr4nck/Noethys-SL/actions/runs/38036079406) : SUCCÈS syntaxe Ubuntu et 96 tests Windows, réseau isolé, sans packaging. CI wx : [wx #38036255934](https://github.com/fr4nck/Noethys-SL/actions/runs/38036255934), SUCCÈS Ubuntu et Windows au même SHA de code.
- **Propagation prouvée** : les trois branches étaient identiques, sans commit propre à perdre. Après CI main, push atomique fast-forward non forcé de `wx`/`qt` vers `4b5dc510`, HEAD distants revérifiés. Une seule note documentaire pour ce lot, également propagée par fast-forward.

| Périmètre au commit de code `4b5dc510` | `main` | `wx` | `qt` |
| --- | --- | --- | --- |
| ZIP partiel, 3 tests | VALIDÉ + CI | VALIDÉ, arbre identique + CI wx | VALIDÉ code commun ; UI Qt EN ATTENTE |
| Gardes réseau/fermeture ZIP antérieures, 12 tests conservés | VALIDÉ + CI | CODE IDENTIQUE + CI wx | CODE IDENTIQUE ; UI Qt EN ATTENTE |
| Protections SQL avancées / restauration MySQL réelle | EN ATTENTE / STOP-GATE | EN ATTENTE / STOP-GATE | EN ATTENTE / STOP-GATE |

- **PR #104 examinée, non dupliquée** : HEAD `bbbddddec529074729acc1bed5f947361b3ee4a9`, MySQL 5.5.62 épinglé par digest, `127.0.0.1:3308`, `.env` hors Git, scripts start/import/reset. README : ancienne ADR-004 à remplacer par ADR-006 ; comptage de tables insuffisant pour qualifier la restauration. Inventaire Docker en lecture seule : seul `noethys-mysql57` actif (`127.0.0.1:3307`), laissé intact.
- **Suite / limite** : aucune recette SQL réelle dans ce lot indépendant. Réutiliser #104 sur environnement isolé et données 100 % synthétiques pour qualifier dumps complets/tronqués, manifeste, marqueur et postconditions avant portage SQL. Aucune base existante touchée, migration, nouvelle branche, fusion globale, suppression ou force-push ; `master` et PR préservées.

## Synchronisation et durcissement Noe-032 — 10/10/2026

- **Non-régression interbranches** : invariant ajouté dans `AGENTS.md` et matrice initiale documentée par le commit `edc014bc9de286cee24c5f19d32c743763246eca`. Les anciennes références `wx` (`98af4873`) et `qt` (`6deee441`) étaient des ancêtres stricts de `main`, avec respectivement 0 commit unique ; chacune a été avancée par fast-forward non forcé vers `edc014bc`, sans perte ni conflit. Run [wx #38032993554](https://github.com/fr4nck/Noethys-SL/actions/runs/38032993554) : Ubuntu et tests Windows **SUCCÈS**.
- **Lot indépendant Noe-032** : le commit `c6130084c04e023a5a014bdd51b694176f76d1ee` reprend uniquement cinq appels `fichierZip.close()` avant les retours d'annulation ou d'erreur dans `Restauration`, présents historiquement dans `master`. Le test `tests/test_noethys_sl_restore_network_config.py` couvre les chemins locaux/réseau factices et vérifie statiquement les six retours précoces. Aucune restauration SQL, migration ni base réelle.
- **Qualification des tests** : run [main #38033235384](https://github.com/fr4nck/Noethys-SL/actions/runs/38033235384) **ÉCHEC DU TEST FICTIF UNIQUEMENT** : entrée sans suffixe `.sql` n'activant pas le chemin d'annulation réseau. Commit `32841c42d8f45f34ff96d4f8737c8ecf546b995c` : correction d'une seule ligne dans la donnée de test ; le code de production `c6130084` reste inchangé. Run [main #38033397162](https://github.com/fr4nck/Noethys-SL/actions/runs/38033397162) : Ubuntu et tests Windows **SUCCÈS**.
- **Propagation contrôlée** : `main`, `wx` et `qt` ont été vérifiées au même SHA `32841c42d8f45f34ff96d4f8737c8ecf546b995c` après deux fast-forwards non forcés des branches `wx` et `qt`. CI de requalification `wx` : [#38033543533](https://github.com/fr4nck/Noethys-SL/actions/runs/38033543533), **SUCCÈS (tests Ubuntu et Windows)**.
- **Matrice actualisée de non-régression au SHA `32841c42` :**

| Périmètre commun / interface | `main` | `wx` | `qt` |
| --- | --- | --- | --- |
| Deux garde-fous réseau Noe-032, tests `a09df2cc` et `64f68c0e` | VALIDÉ (CI main) | CODE IDENTIQUE, SUCCÈS (tests Ubuntu et Windows) | CODE IDENTIQUE ; recette Qt EN ATTENTE |
| Fermeture ZIP sur annulations/erreurs, `c6130084` et `32841c42` | VALIDÉ (CI main #38033397162) | CODE IDENTIQUE, SUCCÈS (tests Ubuntu et Windows) | CODE IDENTIQUE ; recette Qt EN ATTENTE |
| Résolution `ObjectListView`, `eab750f6` | VALIDÉ | CODE IDENTIQUE, SUCCÈS (tests Ubuntu et Windows) | CODE IDENTIQUE ; recette Qt EN ATTENTE |
| Restaurations MySQL/MariaDB réelles et protections SQL avancées de `master` | NON INTÉGRÉ / EN ATTENTE | NON INTÉGRÉ / EN ATTENTE | NON INTÉGRÉ / EN ATTENTE |
| Interface Qt native | NON APPLICABLE | NON APPLICABLE | NON QUALIFIÉE |

- **Environnement de recette existant** : la PR [#104](https://github.com/fr4nck/Noethys-SL/pull/104) contient déjà `dev/db/compose.yml` (MySQL 5.5.62 épinglé, port `127.0.0.1:3308` par défaut) et scripts PowerShell de démarrage. Elle n'est **ni fusionnée ni qualifiée localement dans cette session** ; ne pas dupliquer son travail. Ce serveur ancien doit être lancé uniquement en environnement jetable isolé, avec données synthétiques et secrets hors Git.
- **Stop-gates / suite** : 25 tests Noe-032 historiques `master` réussis sur mocks (run #35826834598) mais **non requalifiés sur `main`**. Aucun serveur réel MySQL/MariaDB de recette accessible dans cette session : manifeste SQL, marqueur terminal, postconditions et restauration d'une base fictive demeurent bloqués. `master` reste la branche GitHub par défaut, le contenu divergent est préservé, huit PR ouvertes. Aucune branche créée, aucun force-push, PR close ou suppression de branche ; aucun packaging lourd.
- **Prochaine action** : qualifier la PR #104 ou un environnement équivalent sur une machine de recette, lancer sauvegarde puis restauration sur **données 100 % synthétiques**, requalifier les 25 tests contre le candidat `main`, puis intégrer les protections avancées sous preuve avant une éventuelle bascule de branche par défaut.

## Non-régression interbranches — contrôle initial du 10/10/2026

- **Source de vérité :** comparer les SHA et arbres Git du dépôt `fr4nck/Noethys-SL` ; ne pas déduire l'équivalence du simple nom des branches.
- **SHA avant synchronisation :** `main` = `28ebcaf7aa096001f49c354486e38f641914a746`, `wx` = `98af487389c4a1fd392f3b1fc2c75186066e6edc`, `qt` = `6deee441050fb653c95901a8ae4dd1145c4ed96e`. `master` = `b0be3c7ebdf2d69d6028eb4fd6fc08e340a68b9e`, toujours branche GitHub par défaut, à conserver.
- **Comparaisons prouvées :** `wx` est ancêtre strict de `main` (12 commits seulement sur `main`, zéro commit propre à `wx`) ; `qt` est également ancêtre strict (14 commits seulement sur `main`, zéro commit propre à `qt`). Pas de merge global requis. Ces chiffres sont ceux **avant** le commit de cette politique et doivent être revérifiés immédiatement avant un éventuel fast-forward.
- **Protection permanente :** invariant de non-régression maintenant dans `AGENTS.md`. Pour chaque future publication, vérifier la propagation des correctifs communs et les comportements propres aux interfaces. Une ascendance Git seule ne vaut pas recette Windows/Qt.
- **Matrice au point de contrôle (avant propagation)** :

| Ensemble testé / correctif | `main` | `wx` | `qt` |
| --- | --- | --- | --- |
| Noe-032 — refus sauvegarde réseau sans connexion (`a09df2cc`, CI #37981580013) | VALIDÉ | ABSENT, à propager | ABSENT, à propager |
| Noe-032 — refus restauration réseau sans connexion (`64f68c0e`, CI #37982029069) | VALIDÉ | ABSENT, à propager | ABSENT, à propager |
| `ObjectListView` — résolution imports (`eab750f6`, CI #37972096356 puis #37979402584) | VALIDÉ | ABSENT, à propager | ABSENT, à propager |
| Restauration MySQL/MariaDB réelle, manifeste SQL, postconditions | EN ATTENTE (non intégré) | EN ATTENTE | EN ATTENTE |
| Parcours UI spécifiques Qt | NON APPLICABLE à ce stade (code actuel wx) | NON APPLICABLE | EN ATTENTE (aucune recette Qt) |

- **Propagation prévue :** mettre `wx` et `qt` au HEAD du socle commun par fast-forward avec vérification de SHA, puis constater réellement les nouvelles références. Cette section constitue l'état *avant* l'opération : ne pas conclure que la propagation a eu lieu sur cette seule documentation.
- **Stop-gates inchangés :** MySQL/MariaDB jetable requis avant qualification réelle des restaurations et avant reprise des protections SQL avancées ; recette UI Windows et Qt nécessaire avant leur publication. Aucune nouvelle branche, aucun force-push, suppression ou modification des données de production.

## Lot Noe-032 qualifie — 09/10/2026

- **Branche et code vérifiés** : `main` à `64f68c0eaae13a2771944ff49cbb556810123849` avant cette note. `master` n'a pas été modifiée ; GitHub conserve `master` comme branche par défaut.
- **TERMINÉ / VALIDÉ — Sauvegarde réseau sans paramètres** : commit `a09df2cc386c6321ae9db7682436dbb0b551a0f3`. `Sauvegarde` refuse les fichiers réseau lorsque `dictConnexion is None` avant toute création de ZIP, y compris en mode mixte local + réseau. Trois tests unitaires isolés dans `tests/test_noethys_sl_backup_network_config.py` (réseau seul, mixte, chemin local conservé), ajoutés à la CI rapide. Run [#37981580013](https://github.com/fr4nck/Noethys-SL/actions/runs/37981580013) : succès syntaxe Ubuntu et tests Windows.
- **TERMINÉ / VALIDÉ — Restauration réseau sans paramètres** : commit `64f68c0eaae13a2771944ff49cbb556810123849`. `Restauration` refuse le réseau sans `dictConnexion`, ferme le ZIP et s'arrête avant toute extraction locale, même en restauration mixte. Trois tests unitaires isolés dans `tests/test_noethys_sl_restore_network_config.py` (archive factice, refus réseau et mixte, parcours local conservé), ajoutés à la CI rapide. Run [#37982029069](https://github.com/fr4nck/Noethys-SL/actions/runs/37982029069) : succès syntaxe Ubuntu et tests Windows.
- **Portée exacte** : deux gardes de refus et six tests, sans modification de schéma, de formats `.nod/.noc`, de code de restauration SQL exécutée, de production ou de données réelles. Aucune branche créée, aucune branche ni PR supprimée/fermée, aucun force-push ni packaging lourd. Vérification de tests sur GitHub Actions ; aucune recette MySQL réelle ni tests intégrés locaux de toute l'application lors de cette passe.
- **CONFIRMÉ SUR `master`, NON RÉIMPORTÉ** : le run historique [#35826834598](https://github.com/fr4nck/Noethys-SL/actions/runs/35826834598) réussissait les 25 tests Noe-032 (10 intégrité de backup, 15 flux restauration) contre des simulations MySQL. Les blobs des deux fichiers de test et du module du commit testé sont identiques à ceux du HEAD `master` contrôlé. Ceci ne valide PAS leur exécution sur `main`.
- **BLOQUÉ / STOP-GATE** : transfert du manifeste SHA-256 SQL, analyse de dump tronqué, marqueur terminal, postconditions MySQL (tables, vues, événements, fonctions) et nettoyage des secrets sans preuve d'une recette contre un serveur MySQL/MariaDB jetable. L'environnement de cette session ne possède pas de serveur ou client MySQL/MariaDB ni Docker/Podman et ne peut pas accéder à GitHub par `git clone` local. Aucun test de restauration sur une base existante, ni publication.
- **PROCHAINE ACTION CONCRÈTE** : sur une machine/runner de qualification disposant de MySQL ou MariaDB, créer des bases **entièrement fictives et jetables**, sans profil Portable ni accès réseau de production ; qualifier à la fois dumps complets, tronqués, hérités sans manifeste, échecs de sous-processus et restauration partiellement réussie ; requalifier les 25 tests historiques sur le candidat `main` sans affaiblir les assertions ; porter ensuite les protections Noe-032 par petits lots et mesurer les postconditions.
- **Bascule de branche par défaut : NON FAITE**. `master`, `wx`, `qt`, RC et les huit PR restent des références à préserver tant que les travaux uniques ne sont pas qualifiés.

## Poursuite consolidation — 09/10/2026 (soir)

- **Inventaire confirmé** : `master` reste divergente. Fonctions sauvegarde/restauration MySQL et contrôles Noe-032 présents dans `master` mais pas dans `main` : ne pas fusionner intégralement ni effacer `master` avant qualification ciblée. Exemples : `_AjouterManifesteIntegriteSQL`, `_VerifierPostconditionRestaurationMySQL` ; tests `tests/test_noe_032_backup_integrity.py` et `tests/test_noe_032_restore_flow.py` restés sur `master`.
- **Correction isolée appliquée sur `main`** : commit `05022fae5946a4db486b3ed973b9d70453b0abaf`, `UTILS_Sauvegarde.GetListeFichiersZIP` ferme l'archive ZIP avec `with`, comme dans `master` ; test sans base réelle `tests/test_noethys_sl_backup_zip_lifecycle.py`. Commit `b0d71728fe44e52e2483e1353299eb35744ca282` ajoute ce test à la CI rapide.
- **CI** : run de qualification du dernier commit [#37979402584](https://github.com/fr4nck/Noethys-SL/actions/runs/37979402584), en attente du résultat au moment de la rédaction. Le run précédent a été annulé par la concurrence automatique.
- **Aucune autre modification** : aucun `master`/RC/WIP modifié, aucune création ou suppression de branche, aucun force-push, aucun schéma SQL modifié. La branche par défaut demeure `master`. Ne pas confondre CI rapide et qualification complète de restauration réseau.
- **Suite** : porter le lot Noe-032 uniquement après revue des 2 suites de tests, des contrats historiques `.nod/.noc` et d'une restauration réelle sur base fictive isolée. Puis traiter les domaines tiers, interventions et synchronisation sans réactiver implicitement d'anciens comportements Repens.

## Mise à jour de consolidation — 09/10/2026

- **But confirmé :** `main` sera la branche par défaut après qualification. Seules les branches de développement `main`, `wx`, `qt` seront conservées à terme ; aucune nouvelle branche ne doit être créée. Consignes applicables dans `AGENTS.md`.
- **Opérations Git réalisées :** `main` a avancé par fast-forward depuis `6deee441050fb653c95901a8ae4dd1145c4ed96e` jusqu'au HEAD `wx` `98af487389c4a1fd392f3b1fc2c75186066e6edc` (deux commits CI seulement). Ensuite, ajout du déclenchement rapide sur `main` par `b36f037ce9934d508f71bdbbff8466e663e54845`, puis ajout des règles `AGENTS.md` via `f8f889ba98145f47f5d6c37d9711751f7779c087`.
- **Non effectués :** aucune création/suppression de branche, aucune fusion de `master`, aucun force-push, aucun changement de branche par défaut, aucune modification SQL ou du code métier, aucun test sur la base réelle.
- **Références au moment du contrôle :** `wx` = `98af4873` ; `qt` = `6deee441` ; `master` = `b0be3c7e`. `master` est toujours la branche par défaut sur GitHub et doit être préservée : son arbre diverge fortement de `main` (modules Repens, synchronisations, interventions, autres code/tests/docs). Ne jamais inférer d'un nombre de commits que tout le code correspondant est absent ou présent.
- **Qualification du 09/10 :** premier run [#37971043856](https://github.com/fr4nck/Noethys-SL/actions/runs/37971043856) : syntaxe OK, trois échecs Windows sur un import `ObjectListView` masqué par `sys.path`. Correctif ciblé `eab750f65c6674edcf4068f922c034bde28d18cb` (`Chemins.py` et test), correction de l'alias du test `7b3a0307147116f0f8e348390fb1cb50a5b8dbe6`. Run [#37972096356](https://github.com/fr4nck/Noethys-SL/actions/runs/37972096356) sur `7b3a0307` : **succès Ubuntu et tests Windows**, sans packaging lourd. Ceci ne remplace ni recette Windows complète ni validation Connecthys réelle.
- **Prochaine étape :** classer les différences métier encore utiles de `master` et des branches RC/WIP, ne réimporter que les correctifs prouvés, requalifier sur la ligne cible, puis changer la branche par défaut dans les paramètres GitHub après l'accord de publication. Ne pas effacer `master` ni fermer une PR non intégrée avant préservation vérifiée.


## 1. Dossier, branches, commits

- Dossier principal : `C:\Users\Ordi\Documents\GitHub\Noethys` (poste 5700x), dépôt `fr4nck/Noethys-SL`.
- Invariant PMSL-Arch : trois branches seulement, `main` (moteur), `wx`, `qt`. Au 08/10/2026 elles pointent sur le même commit (tout le code actuel est wx ; la séparation moteur/UI n'est pas commencée).
- Base de `main` : ligne RC2/RC2.1 en service (`fea13ce7`, tag `noethys-sl-0.1.0-rc.2.1`), puis :
  - fusion des deux commits divergents `integration/rc2-convention-recovery-20261004` (`cc39c887`) ;
  - fusion de la ligne de secours `rescue/noethys-sl-20261004` / `d9b70c2b` (`7be696f9`) ;
  - reprise thématique du travail non commité de `Noethys-RC2-clean` (instantané de diagnostic `d08e37fb`, objet local non référencé) ;
  - corrections listées ci-dessous.
- Worktrees existants (non supprimés) : `Noethys-RC2` (`integration/rc2-convention-recovery-20261004`, propre, intégrée) et `Noethys-RC2-clean` (HEAD détaché `8b3789d9`, **modifications non commitées conservées** ; éléments volontairement non repris : `DialogFondu`/`UTILS_Transitions`, ancienne variante Word, suppression du Toaster d'accueil).
- PMSL-Arch : `main` porte `66e5e06` (registre TRV-016/031/032) et `9dc3f97` (règle du titulaire de l'adhésion). La branche locale de travail de ce dépôt reste `docs/profil-poste-5700x-2026-09-24`.

## 2. Corrections terminées et preuves

| Sujet | Commits | Preuve |
|---|---|---|
| Boutons Mode / Émetteur de la saisie d'un règlement (TAILLE_IMAGE float refusé par Phoenix) | `c17fdf27` | `tests/test_noethys_sl_parametrage_reglement.py` (échoue sans correctif) ; artefact : dialogues ouverts par Paramétrage > Comptabilité, ajout + persistance en base fictive ; RC2.1 publiée : aucune fenêtre |
| Adhésions : chevauchement refusé, au plus une adhésion à venir | `746bbd6e` | `test_noethys_sl_adhesions.py` |
| Adhésions : signalement « à vérifier » (fenêtre ou historique) | `9eac1977` | `test_noethys_sl_adhesions_signalement.py` ; simulation portail (sans Connecthys) |
| Adhésions : sauvegardes simultanées (SQLite `BEGIN IMMEDIATE`, MySQL `GET_LOCK` + InnoDB exigé), aucune écriture partielle | `aee1626e` | `test_noethys_sl_adhesions_concurrence.py` : deux processus, SQLite et MySQL 5.7 local ; ancien code = 2 adhésions + 2 prestations |
| Adhésions : titulaire (structure personne morale / chaque personne d'une famille) | `7f56aecf` | `test_noethys_sl_adhesions_titulaire.py` (6/8 échouent avec l'ancien code) |
| Sortie Word : écriture atomique, refus des mots-clés inconnus | `f0d90147`, doc `200e148f` | `test_vanilla_convention_docx.py` |
| Devis d'une famille sans adresse (None refusé par wx) | `cdf8ecc5` | `test_noethys_sl_devis_adresse_incomplete.py` ; PDF de devis contrôlés (avec/sans adresse, règlement non ventilé) |
| Noedoc : blocs flottants des conventions sans débordement | `d16d907c`, `e6c9f2de` | `test_noethys_sl_noedoc_ecoulement.py` ; captures Windows 3 modèles × 2 tailles |
| Garde des tests (production) | `4a3739f7`, `03b56fca`, `aee1626e`, `b9c8b386` | suite complète + 72 modules seuls : 0 connexion au pilote MySQL |
| Module `etat_global` exécuté par unittest | `da8cd8ec` | 40 tests, 1 échec attendu documenté |
| Incident et diagnostics | `5dafe288`, `9f0f007f` | voir § 9 |
| Procédure de recette et fichier fictif | `169a93b0` | `docs/recette/RECETTE_CANDIDAT_2026-10-08.md` |

Résultat global au commit `e6c9f2de` : 661 tests OK (1 échec attendu), sous garde réseau et avec le MySQL local.

## 3. Modifications non commitées

Aucune dans `Noethys` hors éléments locaux ignorés volontairement (jamais à committer) : `local-diff.txt`, `local-status.txt`, `portable-inventory.txt`, `tracked-files.txt` (inventaires préexistants) et `noethys/Portable/` (**profil réel pointant vers la base de production**).

## 4. Commandes

Depuis `C:\Users\Ordi\Documents\GitHub\Noethys` :

```powershell
# Suite complète (garde réseau incluse dans chaque module)
.venv310\Scripts\python.exe -m compileall -q noethys tests
.venv310\Scripts\python.exe -m unittest discover -s tests
# Avec le serveur MySQL local de test (voir § 5)
$env:NOETHYS_TEST_MYSQL_HOST="127.0.0.1"; $env:NOETHYS_TEST_MYSQL_PORT="3307"
$env:NOETHYS_TEST_MYSQL_USER="root"; $env:NOETHYS_TEST_MYSQL_PASSWORD="<mot de passe du conteneur>"
.venv310\Scripts\python.exe -m unittest tests.test_noethys_sl_adhesions_concurrence
```

Build portable (reproduit `.github/workflows/noethys-sl-windows.yml`) dans un environnement propre :

```powershell
python -m venv <build>\venv
<build>\venv\Scripts\python.exe -m pip install -r requirements.txt   # sans la ligne « pyttsx »
<build>\venv\Scripts\python.exe -m pip install pyttsx3 wxPython==4.2.5 "pyinstaller>=6,<7"
<build>\venv\Scripts\pyinstaller.exe --noconfirm --clean packaging/vanilla-noethys.spec
# puis BUILD-INFO.txt et Compress-Archive -Path dist/Noethys (voir le workflow)
```

`.venv310` ne contient ni pytest ni PyInstaller ; Inno Setup (Setup.exe) n'est pas installé sur le poste.

## 5. MySQL Docker de test

- Conteneur `noethys-mysql57`, MySQL 5.7.44, InnoDB par défaut, `127.0.0.1:3307`, utilisateur `root` ; mot de passe connu de Franck, **jamais dans Git**.
- Bases existantes à ne pas modifier : `docker_mad*`, `docker_mairies*`, `docker_pelemele_*`.
- Les tests créent puis suppriment uniquement des bases `zz_test_adh_<aléa>` ; `_garde_reseau.ServeurMySQLDeTest()` n'autorise que l'hôte local déclaré.

## 6. Artefact portable existant (candidat local non publié)

- `C:\Users\Ordi\Documents\GitHub\Noethys\dist\Noethys-SL-0.1.0-rc.2+e6c9f2de-local-Windows-portable.zip`
- Commit `e6c9f2deb172b9f0041bc6d1a9c11b29b717ebe2` ; SHA-256 `5967EDADC68DE302D14B62A3640F2A1449EBCBAA25E36F4973B6CB06AB362FE8`.
- Bytecode des 29 modules modifiés depuis RC2.1 identique au commit. Titre affiché encore « RC2 » ; `BUILD-INFO.txt` porte le commit.

## 7. Sauvegarde

`C:\Users\Ordi\Documents\Sauvegardes-Noethys\Noethys-avant-consolidation-20261008-112618.tar` (1,58 Go, Noethys + Noethys-RC2 + Noethys-RC2-clean, `.git` commun ; `git fsck` propre sur extraction). Seule copie de l'état d'origine de `Noethys-RC2-clean` hors du worktree.

## 8. Processus et ressources temporaires

- Processus actifs : `C:\Noethys\Noethys.exe` (instance de l'utilisateur, **ne pas toucher**) ; conteneur `noethys-mysql57`. Aucune instance de test restante.
- Temporaires (scratchpad Claude Code, supprimables) : environnement de build, environnement pywinauto, copie extraite de l'artefact avec profil Portable fictif et fichier `Recette`, RC2.1 publiée téléchargée, captures et scripts de recette.

## 9. Incident du 08/10/2026 (production)

Rapport : `docs/incidents/2026-10-08-tests-base-reseau.md` ; famille TRV-032 dans PMSL-Arch `docs/AUDIT_BUGS_TRANSVERSAUX.md`. Quatre exécutions de la suite avant la garde, 31 connexions chacune ; au plus une écriture possible (`parametres` email/timeout vide) ; **aucune écriture confirmée**. Contrôle en lecture seule : `docs/diagnostics/diagnostic_adhesions.sql`, requêtes 9 et 9 bis.

## 10. Règle métier des adhésions

Référence : PMSL-Arch `docs/REGLES_ADHESION_ACTIVITES.md` ; implémentation `docs/metier/ADHESIONS_AUTOMATIQUES.md`.

- Structure (association, école/collectivité, organisme, entreprise : personne morale titulaire de la famille) : **une adhésion pour la structure**, quelles que soient ses sections, activités ou représentants.
- Famille de personnes physiques : **une adhésion par personne qui participe**, couvrant toutes ses activités, jamais commune à la famille.

## 11. Tâches restantes (par priorité)

**P0**
1. Diagnostic réel d'Arthur (famille 688) **non effectué** : exécuter en lecture seule `docs/diagnostics/diagnostic_adhesions.sql` (identification par rattachement, puis par IDindividu) ; ne corriger aucune donnée.
2. **Validé en recette fictive par Codex** : boutons Mode / Émetteur depuis la saisie d'un règlement dans le portable, avec création effective des deux éléments. La recette par le comptable sur données fictives reste possible ; ne jamais ouvrir la production avec le candidat.
3. Contrôle en lecture seule de la ligne `parametres` de l'incident (requêtes 9 / 9 bis).

**P1**
4. Recette **125 % et 150 %** effectuée : règlement et devis accessibles ; crash Noedoc au double-clic isolé et corrigé. Nouveau portable à retester graphiquement ; voir § 13 pour les limites exactes.
5. **Corrigé et validé** : crash à la fermeture après « Rappel de sauvegarde ». Arrêt des timers du bandeau avant destruction (commit source `db27767b`) ; nouveau portable testé sur Recette, fermeture normale avec code 0. Voir § 12.
6. **Aucune recette Connecthys réelle** : seul le traitement d'une demande de réservation a été simulé localement (grille, adhésion, signalement).
7. Avant publication officielle : numéro de version (RC3), notes de version, reciblage du workflow `noethys-sl-windows.yml` (déclencheur actuel `release/noethys-sl-0.1.0`), Setup via la CI.

**P2 — à préserver, ne rien supprimer sans décision de Franck**
8. Ligne **Upgrade** `origin/master` (1 478 commits propres, non intégrée à `main`).
9. 144 branches distantes non intégrées à `main` (10 déjà intégrées : `integration/rc2-…`, `release/noethys-sl-0.1.0`, `maintenance/vanilla`, etc.).
10. Trois **stashes** du 25/09/2026 (dépôt commun) à examiner avant toute résorption.
11. Worktrees `Noethys-RC2` et `Noethys-RC2-clean` : résorption après recette et accord sur les éléments non repris.
12. Famille de défauts « valeur par défaut évaluée à l'import » (`GenerationNomDoc`, 14 occurrences) : à ratisser.


## 12. Reprise Codex — 08/10/2026

- Push vérifié : `main`, `wx`, `qt` sur `a66e404a` ; PMSL-Arch `main` sur `9dc3f97`.
- Portable e6c9f2de testé dans une extraction dédiée avec le fichier SQLite fictif
  **Recette**, sans profil réel. Parcours fiche famille > saisie d'un règlement :
  bouton Mode, création `MODE RECETTE CODEX`, bouton Émetteur, création
  `EMETTEUR RECETTE CODEX` ; les deux éléments apparaissent dans leurs listes.
  Le règlement de test a été annulé ; aucune base réelle touchée.
- Crash reproduit dans ce portable : exception Windows `0xc0000005` dans
  `wxbase32u_vc140_x64.dll`. Reproduit aussi depuis les sources sans fichier
  ouvert et sans Noedoc. La piste Noedoc n'explique pas ce cas.
- Isolation : sans le panneau éphéméride, la fermeture réussit ; arrêter le
  seul timer de défilement avant la fermeture suffit aussi. Désinstaller le
  gestionnaire AUI seul ne suffit pas. Correctif : arrêter le bandeau et son
  timer de pause après acceptation de la fermeture, avant destruction wx.
- Nouveau test `test_noethys_sl_fermeture_windows.py` : fermeture réelle de
  l'accueil dans un sous-processus Windows, profil temporaire, réseau interdit.
  Succès après correctif, zéro tentative de connexion réseau.
- Le portable e6c9f2de existant **ne contient pas** ce nouveau correctif tant
  qu'un nouveau build n'a pas été produit et vérifié.
- Restent : DPI 125 % / 150 %, confirmation des données réelles d'Arthur,
  recette Connecthys réelle et résorption des anciens travaux après validation.
- Deux instances de l'installation réelle ont été constatées. Celle lancée
  à 14:23 semble provenir du premier essai de lancement du portable via
  Computer Use. Aucune interaction métier ni fermeture sur ces instances.

Validation du correctif : suite `python -m unittest discover -s tests` terminée
avec code 0. Des avertissements de nettoyage de bases temporaires et les
exceptions volontairement simulées restent imprimés par les tests existants.


Nouveau portable local construit avec le commit source `db27767b` :
`C:\Users\Ordi\Documents\GitHub\Noethys\dist\Noethys-SL-0.1.0-rc.2+db27767b-local-Windows-portable.zip`.
SHA-256 : `8ca961a436cc73ae5e5233de91e593293fb4cc702e3caf89b48715ab8c5ebc05`.
Intégrité ZIP vérifiée ; aucun profil Portable ni base inclus dans l'archive.
Le nouvel exécutable démarre et propose l'ouverture du fichier fictif Recette.
Après identification manuelle par Franck, la fermeture graphique du nouveau
portable sur le fichier fictif Recette a été validée : croix de la fenêtre,
« Pas maintenant » au rappel de sauvegarde, processus terminé avec code 0.
La fermeture depuis les sources est également validée par le test.
Le titre reste RC2 : aucune nouvelle version publique ni release créée.


## 13. Recette DPI et crash au double-clic Noedoc — 08/10/2026

Écran Windows 2560 × 1440 ; mise à l'échelle 125 %, puis 150 %, vérifiée
dans les Paramètres. Candidat `db27767b`, fichier SQLite fictif Recette.
Aucune donnée réelle ni aucun profil de production utilisé.

- À 125 % : fiche famille, saisie de règlement, boutons Mode et Émetteur
  ouverts et fermés ; commandes accessibles. Devis fictif généré et ouvert
  dans Adobe Reader malgré un règlement de 50 € non ventilé. Deux messages
  Windows « Font Capture », exception `0xc06d007e`, sont apparus pendant
  l'ouverture de l'aperçu ; Franck les a fermés. Causalité non établie.
- À 150 % : mêmes parcours règlement/Mode/Émetteur accessibles ; devis
  fictif généré et ouvert dans Reader sans nouveau message Font Capture.
  L'éditeur Noedoc s'ouvre et se ferme via le bouton Modifier.
- Au double-clic sur « Facture par défaut », le portable s'arrête à 125 %
  et à 150 % : événements Windows 1000, `0xc0000005` puis `0xc000041d`,
  module `_core.cp310-win_amd64.pyd`. Reproduction depuis le code source
  sur une copie temporaire de Recette avec garde réseau.
- Trace faulthandler : `FloatCanvas.GetHitTestColor`, appelé depuis
  `GUIMode.OnLeftUp`, lit le point `(289, 257)` dans un tampon `(20, 20)`
  avant le premier dessin. AlphaPixelData n'effectue pas de contrôle des
  bornes ; le relâchement du double-clic provoque la lecture native invalide.
- Correctif isolé `027ffe7e` : CanvasNoedoc contrôle l'existence et les
  dimensions du tampon de sélection avant lecture. Hors tampon : aucune
  sélection ; dans le tampon : comportement FloatCanvas conservé.
- Vérification graphique du code corrigé à 150 % : double-clic depuis la
  liste des modèles, dessin complet, sélection d'un bloc et affichage des
  propriétés, Annuler puis fermeture de la liste et de l'accueil ; code 0.
- Cinq tests ciblés passent : trois `test_noethys_sl_noedoc*.py`, un
  `test_noedoc_texte_ui.py`, un `test_noethys_sl_fermeture_windows.py`.
  Le nouveau test exerce dans un sous-processus les coordonnées négatives,
  les bords et le point réel du crash, les pixels valides, la priorité du
  tampon de premier plan et l'absence de tampon. Réseau interdit.

Nouveau portable local (correctifs fermeture + Noedoc), commit source
`027ffe7e98faa67478934db3bdca1919bf8658d7` :
`C:\Users\Ordi\Documents\GitHub\Noethys\dist\Noethys-SL-0.1.0-rc.2+027ffe7e-local-Windows-portable.zip`.
SHA-256 : `778485c3ba9aa36317604f0b2afc3f33dd8b954834ca2d728fa270bc27bdd998`.
Build terminé, intégrité ZIP vérifiée, aucun profil Portable dans l'archive.
Un profil fictif séparé a été préparé dans l'extraction de recette.

Validation graphique du nouveau portable `027ffe7e` terminée :
- À 150 % : double-clic sur le modèle, dessin complet, sélection d'un bloc,
  propriétés affichées, Annuler puis fermeture des fenêtres et du processus.
  Aucun crash observé ; code de sortie non recueilli pour cette exécution.
- À 125 % : même parcours, puis fermeture de l'accueil ; code de sortie 0
  recueilli sur le processus conservé depuis son lancement.

La recette DPI est ciblée : elle ne valide pas exhaustivement l'éditeur,
les autres écrans ou toutes les résolutions. Les messages Font Capture
restent une anomalie non attribuée. L'affichage Windows est actuellement
à 125 % ; la valeur habituelle de Franck reste à confirmer pour restauration.
Arthur réel, contrôle de l'incident et recette Connecthys réelle restent
en attente. Aucun tag, release ou déploiement ; anciens travaux préservés.


## 14. Propagation ciblée Nomadhys — 11/10/2026

Périmètre : seul correctif de validation des catégories/actions/états importés,
commit source `694ccacc2d37ba71298b56e7ddb6901be6a55d2d`, confirmé comme tête
distante de main avant intervention. Cherry-pick avec provenance (-x), sans
fusion générale, nouvelle branche distante ni réécriture d'historique.
Une trace documentaire séparée accompagne chaque correctif.

### Matrice des preuves

| Correctif | main | wx | qt |
| --- | --- | --- | --- |
| Validation Nomadhys | VALIDÉ : 694ccacc2d37ba71298b56e7ddb6901be6a55d2d | VALIDÉ : d95fb660de4fc226603d3a9e36a54946455eb1fc | VALIDÉ : 508d5f4f119542e954d3744f06287a46d5f06c5a |
| Rail 1, quarantaine, TLS Connecthys et contrat vaccins | VALIDÉ dans les tests ciblés de ce lot | VALIDÉ dans les tests ciblés de ce lot | VALIDÉ dans les tests ciblés de ce lot |
| Secteur famille sans titulaire, déplacement Noedoc sans delta, mode statistiques invalide | Présents dans l'arbre main ; EN ATTENTE de réexécution de leurs tests dans cette session | ABSENTS ; hors périmètre Nomadhys | ABSENTS ; hors périmètre Nomadhys |

Têtes avant intervention : main `694ccacc2d37ba71298b56e7ddb6901be6a55d2d`,
wx `5538488b0ff03edcef81198a4f97998b675e2ef6`,
qt `6d0c84e78efbe3497e8d2100bc9b6250b8e635fb`.
Parent du correctif source : `b5aa605b916c556885d3d3ed36271c6973746b89`.
Ancêtre commun main/wx et main/qt : `44fd8096506f7362706bb95ef1fbee3dae790a59`.
Les arbres wx et qt initiaux sont identiques. Par rapport au parent source,
ils diffèrent sur les trois protections citées et leurs trois fichiers de tests
(six fichiers, 231 lignes absentes). Ces écarts existants sont conservés.
Le delta de chaque cherry-pick est strictement celui des deux fichiers Nomadhys
(63 insertions, 10 suppressions), sans perte d'autres apports de la cible.

### Empreintes Git identiques pour wx et qt

| Fichier | Avant cherry-pick | Après cherry-pick, identique à main |
| --- | --- | --- |
| noethys/Dlg/DLG_Synchronisation_donnees.py | d31f6d221664600e850c936b9772879a6375c462 | 32d7a32979e1a3cbcb903e68c1b82af95cbacf8c |
| tests/test_audit_reseau_nomadhys.py | 64e43f1914b2d86006f7d06187b22e0fc3d7847d | 95aa7b8d8441be1f66e8fc8d53e2de328f421f85 |

### Validation et publication

Python 3.11 Windows : 55 tests réussis sur chacune des trois têtes de correctif,
165 exécutions au total, aucun échec ni test ignoré :
audit réseau Nomadhys 37, format chiffrement 7, quarantaine 1,
isolation TLS Connecthys 5, contrat vaccins 5.
Garde réseau explicite sur connect/connect_ex/create_connection/getaddrinfo :
zéro tentative réelle. Tests AST, dépendances factices et fichiers temporaires ;
copie isolée sans profil Portable, aucune base de production utilisée.
Diff et empreintes vérifiés avant/après ; contrôle des espaces Git réussi.
La trace documentaire ne modifie aucun fichier de runtime ni de test.

Publication autorisée uniquement après ces contrôles, en fast-forward non forcé
sur les seules refs existantes wx et qt, avec vérification des SHA attendus
et envoi atomique. Le résultat distant et les SHA de documentation seront
confirmés dans le compte rendu de session ; cette note ne présume pas le succès
du push. main, master, branches historiques, tags/releases et PR ne sont pas
modifiés. PR ouvertes relevées : #422, #384, #369, #366, #355, #112, #104, #102 ;
aucune n'a wx ou qt comme tête ou base.

Dépôt original conservé sur main : ses 11 fichiers non suivis sont inventoriés
avec SHA-256 pour comparaison finale, sans copie de profils dans les tests.
Stashes et worktrees historiques conservés. Logs et preuves détaillées gardés
dans l'espace de travail local de la session (nomadhys-evidence.json et logs).
CI distante : aucun résultat revendiqué ici ; aucun build de packaging demandé.
Qualification globale wx/qt : EN ATTENTE / STOP-GATE pour une release, compte
tenu des écarts ci-dessus et des recettes réseau/Windows restant hors de ce lot.
Prochaine étape : qualifier séparément les correctifs communs manquants et
les parcours métier réels avant de déclarer une branche stable.

## 2026-10-27 — Noethys #435, arbitrage Connecthys et navigation wx

Décision terrain : une même demande Connecthys doit être rejouable sans double
quantité, avec priorité Journée lorsque disponible ; sinon seules les
demi-journées encore disponibles sont retenues. Si facture, pointage, conflit
persisté, attribution ou disponibilité incertaine : arbitrage de l'opérateur,
jamais écrasement silencieux. L'issue #435 est l'autorité de suivi :
https://github.com/fr4nck/Noethys-SL/issues/435

**Travail publié sur la seule branche wx depuis 11b85461 :**
- c877a577 : planificateur pur Journée / demi-journées ;
- 2b5c1e1e : 15 tests purs ;
- d75fdc27 : cumul persisté Journée + demi-journée => arbitrage ; doublon de demande évité ;
- 494ad6f7 : 2 tests métier supplémentaires ;
- c24e778a : aide de décision Quantite (créer/existant/requalifier), sans écriture ;
- 699e2338 : 8 tests quantité ;
- 8723f0ab : navigation/fermeture d'une demande incertaine sans
  sauvegarde ni alerte modale répétée ; marqueur conservé ;
- 18267956 : 2 tests wx de navigation/fermeture.

**Qualification au point de reprise :** 27 nouveaux tests ajoutés au dépôt,
CI Windows sur 18267956 =
https://github.com/fr4nck/Noethys-SL/actions/runs/40579210562 ;
syntaxe Python PASS, contrats métier Windows **en cours** au relevé.
Le paquet préliminaire `noethys435_lot_dev_non_deployable.zip` avait 41 tests
isolés PASS hors dépôt, mais **son installateur est obsolète** (SHA 11b85461)
et ne doit pas être exécuté sur la nouvelle wx.

**État et limites :** le planificateur et la décision Quantite sont publiés,
mais PAS ENCORE RACCORDÉS au parcours réel d'application des réservations.
Le marqueur de réconciliation existe toujours ; la reprise manuelle avec
preuve du delta et contrôle multi-postes reste à coder et qualifier. La
navigation sans mutation est seule modification fonctionnelle active.
Ne déclarer ni correctif métier complet, ni installation, ni release stable.
Aucune base réelle, aucun profil Portable, email réel, tag ou release modifié.

Matrice au jalon : wx = moteur pur et navigation partiellement VALIDÉS
(syntaxe PASS, tests Windows EN ATTENTE) ; main = NOUVELLES MODIFICATIONS ABSENTES ;
qt = NOUVELLES MODIFICATIONS ABSENTES. Ne pas propager le lot tant que le
contrat métier multi-postes et la séparation wx/Qt ne sont pas qualifiés.
Rappel : worktrees utilisateur conservés intentionnellement : Noethys-SL
(sur wx) et Noethys-SL-qt (sur qt), anciens rc2/travail retirés.

**Suite de travail :** lire les résultats CI et conserver les tests CE-4/CE-5.
Intégrer la décision quantité au précontrôle *avant toute écriture* puis
rejouer les essais de sauvegarde partielle/crash. Développer le formulaire
« Vérifier et reprendre » avec confirmation visible, comparaison durable
et absence de rejeu des emails acceptés. Qualifier SQLite + MySQL isolé et
Windows réel. Installation seulement après cette qualification.

## 27/10/2026 — UI-435 : campagne Windows PASS, stop-gate production conservé

**Code qualifié** : `wx` `4e1d782fd37cba9ba55472aef1db48e66a52b660`.
GitHub Actions [40583234323](https://github.com/fr4nck/Noethys-SL/actions/runs/40583234323)
**SUCCESS** : compilation Python PASS ; **1 289 tests, 1 257 PASS, 0 FAIL,
0 ERROR, 32 SKIP**. Les nouveaux tests #435 sont désormais exécutés par
`.github/workflows/noethys-sl-fast.yml`. Les cas CE-4/CE-5 et le rejeu
`Quantite` ont été contrôlés dans les logs Windows.

Première campagne `40581168121` : trois FAIL de contrat des tests et de
libellé, corrigés en `6c35dde5` et `4e1d782f` ; succès final ci-dessus.
Le document détaillé est `docs/recette/UI_435_QUALIFICATION.md`.
Les commits documentaires postérieurs à `4e1d782f` ne modifient pas
les sources, les tests ni le workflow qualifiés.

**STOP-GATE de production maintenu** : pas de recette graphique sur le
Windows de l'association, pas de contre-épreuve réelle de concurrence MySQL
multi-postes, 32 tests ignorés à expliciter. La revue manuelle ne rend pas
la séquence de sauvegarde inter-postes atomique. Aucun tag, release,
packaging, profil Portable ni base PMSL modifié.
`main` et `qt` restent inchangés ; pas de propagation mécanique.
L'archive ancienne du lot #435 n'est pas installable sur ce nouveau SHA.

Prochaines opérations autorisées : qualification MySQL sur serveur isolé,
scénarios de deux opérateurs, contrôle des factures/pointages,
réouverture de la fiche et recette graphique réelle. Puis seulement une
décision d'installation explicitement confirmée.

## 27/10/2026 — UI-435 contre-qualification finale MySQL 5.7 et CI Windows

**Code et tests qualifiés :** `wx` `130324ca6dfe2173515d41d3d0680b9fbd3f001a`.
Les commits de documentation suivants ne modifient aucun source Python
ni test déjà qualifié.

- CI rapide Windows [40585542706](https://github.com/fr4nck/Noethys-SL/actions/runs/40585542706) :
  **SUCCESS** ; compilation PASS ; **1 293 tests exécutés, 1 257 PASS,
  0 FAIL, 0 ERROR, 36 SKIP**.
- CI vraie MySQL 5.7.44 jetable Windows
  [40585542910](https://github.com/fr4nck/Noethys-SL/actions/runs/40585542910) :
  **SUCCESS** ; **29 PASS, 0 FAIL, 0 ERROR, 0 SKIP**, dont quatre nouveaux
  tests #435 du marqueur et du GET_LOCK sur deux connexions.
- La CI rapide ignore les essais MySQL faute de serveur : 30 SKIP MySQL,
  et six essais conditionnels. Ils ne contredisent pas le PASS MySQL dédié.
- Historique : première campagne Windows `40581168121` (3 FAIL),
  puis `40583234323` (1 289, 0 FAIL) après correction des tests et du
  libellé d'arbitrage.

Dossier de preuve : `docs/recette/UI_435_QUALIFICATION.md` et issue #435.
**STOP-GATE sur données PMSL inchangé** : l'interface wx interactive
et le parcours manuel complet concurrent sur deux postes n'ont pas
été qualifiés (les primitives de verrou SQL seules le sont).
Aucune installation, tag, release, migration ni modification du profil
Portable ; `main` et `qt` inchangés. Reprise sur code `130324ca`,
puis contre-épreuve de deux opérateurs et recette terrain avant décision
de publication/installation.

## 2026-10-28 — Questionnaire repas : preparation visible et idempotente #433

**Mission utilisateur :** ne plus laisser d'incertitude sur l'existence
du questionnaire « Type de repas ». Le code ne peut pas prouver
l'existence de cette question dans la base PMSL sans installer et ouvrir
une application sur cette base ; il fournit désormais un diagnostic
explicite et une creation idempotente sous confirmation.

- `wx` : code et tests du sous-lot en HEAD
  `f12c207a7f22cc3bace254de7febaddf58519639`.
  Commit documentaire suivant `ac714c09` sans modification de sources.
- `noethys/Utils/UTILS_Repas_questionnaire.py` : diagnostique les
  questionnaires individuels « Type de repas » / « Régime repas », valide
  les 4 réponses visibles à choix unique, ne convertit aucun historique ;
  écrit uniquement sur confirmation via l'UI ; transactions SQLite
  `BEGIN IMMEDIATE` et MySQL `GET_LOCK` pour les appels homologues.
- `noethys/Dlg/DLG_Questionnaires.py` : état PRÊT / ABSENT / À CORRIGER
  en lecture seule, action « Préparer Type de repas » uniquement pour
  le type Individu.
- `noethys/Dlg/DLG_Saisie_commandes_colonne.py` : même vérification
  et remplissage automatique des quatre IDs dans le modèle de
  commande de repas, à enregistrer normalement.
- **Tests nouveaux** : 14 SQLite, 8 sur le menu Questionnaires, 5 sur
  le bouton de modèle, intégrés à la CI rapide. Compilation Python
  sur `f12c207a` PASS ; tests Windows
  [run 40634463963](https://github.com/fr4nck/Noethys-SL/actions/runs/40634463963)
  **en cours au dernier relevé**. Ne pas écrire SUCCESS sans conclusion.
- Notice : `docs/metier/REPAS_QUESTIONNAIRE_PREPARATION.md`.
  Issue : [#433](https://github.com/fr4nck/Noethys-SL/issues/433).

**Matrice branches** : `wx` = PREPARATION CODEE / CI WINDOWS EN
ATTENTE ; `main` = NON PORTE pour ce sous-lot ;
`qt` = NON PORTE pour ce sous-lot. Pas de merge global ni de
nouvelle branche. Aucun dossier `Portable`, base PMSL, données
des familles, modèle historique, facture, installateur, tag/release ou
portail web n'a été modifié.

**STOP-GATE** : une CI verte ne crée pas la question dans la base,
ni ne prouve sa visibilité sur un portail parent. Le volet panier
familial à 0 EUR de facturation reste explicitement bloqué
tant que la tarification 2C-3 n'est pas raccordée et qualifiée.
Recette graphique Windows sur base fictive et contrôle MySQL jetable
à effectuer avant installation terrain.
