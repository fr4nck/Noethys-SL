# Noethys-SL Qt — C19f : premier banc transactionnel MySQL isolé

Date : 03/11/2026 · Branche `qt` · Ticket [#440](https://github.com/fr4nck/Noethys-SL/issues/440).

**Statut : expérimentation de sécurité, NON importée par l'application, NON
qualifiée pour la production.** Une facture de test créée dans ce laboratoire
n'est **pas** une facture Noethys : aucun numéro légal, aucune comptabilité,
aucun tarif, aucune cotisation ni aucun dossier réel.

## Périmètre matériel

Le nouveau code d'écriture est placé **exclusivement** sous
`experimental/qt_c19f_mysql_lab/`, hors de `noethys_qt` et de `noethys`.
Aucun bouton Qt, service wx, commande de migration ni point d'entrée
utilisateur ne permet de l'exécuter.

Le connecteur refuse toute ouverture SQL sauf si toutes les conditions sont
vérifiées : GitHub Actions, dépôt `fr4nck/Noethys-SL`, branche `qt`,
variable de garde explicite `C19F_DISPOSABLE_MYSQL=yes`, hôte
`127.0.0.1`, port `33067`, utilisateur `qt_c19f` et base strictement
nommée `qt_c19f_lab`. Il contrôle ensuite le marqueur
`NOETHYS_C19F_FAKE_MYSQL_ONLY_20261103` dans la transaction.

L'initialiseur CI **refuse une base non vide** avant de créer uniquement
les tables préfixées `c19f_`. Les tests effacent uniquement les lignes
de ces tables, sur la base marquée ; aucune commande `DROP DATABASE`,
connexion à `SERVEURPMSL`, chargement de profil Noethys ou accès à une
sauvegarde `.nod` n'existe dans le laboratoire. Les identifiants du
conteneur sont des chaînes de test sans rapport avec des secrets réels.

Le workflow
[`.github/workflows/qt-c19f-mysql-isolated.yml`](../../.github/workflows/qt-c19f-mysql-isolated.yml)
prépare deux conteneurs CI distincts (**MySQL 5.7.44** et **8.0.40**),
démarre des runners Ubuntu éphémères et installe **PyMySQL uniquement dans
les runners**. Les données et les conteneurs disparaissent avec les jobs.
MySQL 5.7 est maintenu ici **pour compatibilité historique uniquement**,
pas recommandé pour une nouvelle production.

## Ce que mesure réellement C19f

Le module `transaction_lab.py` utilise, sur des tables de test **inventées** :

- `BEGIN` / `COMMIT` / `ROLLBACK` InnoDB, marqueur de provenance,
  simulation de session non révoquée et non expirée ;
- verrous `SELECT ... FOR UPDATE` sur session, compte payeur, droits et
  prestations, lecture des périodes verrouillées dans **la même transaction** ;
- droit déclaré `facturation_factures/creer` **pour chaque activité**, liste
  non vide d'activités et de prestations, cohérence exacte des activités
  couvertes et du couple famille/compte payeur ;
- unique référence `idempotency_key` liée à l'empreinte de toute la
  proposition ; en-tête fictif et rattachement de toutes les prestations
  atomiques, `UPDATE ... WHERE invoice_id IS NULL` + unicité des lignes ;
- injections de panne après l'en-tête et après la première ligne ;
- **deux processus distincts** visant les mêmes prestations avec soit la
  même clé idempotente, soit deux clés différentes : état final contrôlé
  pour empêcher les doubles attributions ;
- préservation des chaînes de montants bruts comme `12.005`, `-1.005`,
  `1000.0003`. **Aucun calcul de total, arrondi, solde ou TVA**.

Cette simulation choisit volontairement un verrou de compte payeur,
sécurisant la concurrence dans **ce schéma inventé** mais ne démontrant
ni les performances ni les verrous du schéma Noethys réel. Les snapshots
de session et de droits sont eux aussi **inventés** ; ils ne représentent
aucune session PMSL authentifiée.

## Recette

`tests_mysql/test_c19f_mysql_disposable_transactions.py` :
**24 tests** de privilèges, reconnaissance du marqueur, vérification des
droits à chaque activité, révocation/expiration de session, verrous aux
bornes, prestation introuvable ou déjà facturée, multi-familles,
défaillances en transaction, idempotence, conservation des montants et
deux tentatives réelles à deux processus.

La CI se déclenche par `push` sur `qt` seulement lorsque les fichiers
de ce laboratoire ou du workflow évoluent. Les tests MySQL sont **hors du
répertoire `tests_qt`** : ils ne modifient ni le compteur ni la logique
des **584 tests Qt C19e**, dont la qualification Windows reste un gate
indépendant. Pas de demande de téléchargement ni de conteneur sur les PC
5700X/i5-10400.

**Qualification CI confirmée sur le code C19f** : après correction
du client MySQL 8.0 (support RSA ajouté uniquement sur runner au commit
`4fc4eb8779`), le run
[41688434727](https://github.com/fr4nck/Noethys-SL/actions/runs/41688434727)
est **completed/success avec les deux jobs verts** :
**24/24 tests PASS sur MySQL 5.7.44** et **24/24 PASS sur MySQL 8.0.40**,
zéro erreur ni échec. Les deux scénarios impliquant deux processus
concurrents sont réussis sur chaque version.

Le premier run
[41688234238](https://github.com/fr4nck/Noethys-SL/actions/runs/41688234238)
avait réussi sous MySQL 5.7, mais échoué en 8.0 avant les tests, faute
de `cryptography` pour `caching_sha2_password`. Cette anomalie
d'outillage est corrigée. Ces preuves ne concernent que le laboratoire
fictif, pas le schéma ni la facturation Noethys réels.

## Étapes encore ouvertes avant une quelconque écriture réelle

1. **Autorisations réelles** : authentification, droit métier sur chaque
   activité, politique absente = refus, périmètre complet provenant du SQL
   courant et révocation pendant l'opération.
2. **Modèle Noethys** : reprise et tests des tables réelles sous MySQL
   **jetable**, dates des forfaits, tarifs, cotisations, prestations
   partagées, acomptes, ventilations, régies et numérotation.
3. **Concurrence adversariale** : deux utilisateurs et deux services
   indépendants, reprises après crash/reconnexion, verrous expirés,
   contrôle multi-périodes et changement de compte payeur concurrent.
4. **Qualification d'un véritable adaptateur métier**, entièrement
   isolé des interfaces Qt/wx, puis recette humaine sur une base fictive.

**STOP-GATE :** C19f est un *banc*, pas un moteur. Il ne peut facturer ni
des familles réelles ni une copie de leur base. Pas de version Qt de
production, pas de migration ni de modification de `main`/`wx`, et la
sauvegarde du i5-10400 (#437) reste différée.
