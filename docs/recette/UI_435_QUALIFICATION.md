# UI-435 — qualification du traitement des réservations Connecthys

Date : 27 octobre 2026. Périmètre : branche canonique `wx` uniquement.

## Verdict

**PASS — qualification automatisée Windows sur base fictive, avec STOP-GATE de production.**

- Code, tests et workflow qualifiés : `4e1d782fd37cba9ba55472aef1db48e66a52b660`
- GitHub Actions : [run 40583234323](https://github.com/fr4nck/Noethys-SL/actions/runs/40583234323) — **SUCCESS**
- Windows `windows-latest`, Python 3.10, wxPython 4.2.5, dépendances du dépôt.
- Syntaxe Python : **PASS**.
- Suite métier rapide et wxPython : **1 289 tests, 1 257 PASS, 0 FAIL, 0 ERROR, 32 SKIP**, durée 518,283 secondes.
- La CI rapide inclut explicitement `tests.test_connecthys_priorites_435` depuis le commit `bb163145`.

La première campagne [40581168121](https://github.com/fr4nck/Noethys-SL/actions/runs/40581168121) avait échoué sur trois assertions : deux nouveaux tests vérifiaient incorrectement `True` alors que `Dialog.Traitement()` retourne historiquement `None` après réussite ; une assertion vérifiait l'ancien libellé « Plusieurs formules Journée ». Corrections ciblées `6c35dde5` et `4e1d782f`, suivies de la réussite ci-dessus. Les nouveaux tests vérifient désormais l'état SQL réellement validé, **pas seulement un retour de fonction**. Les contre-épreuves existantes n'ont pas été affaiblies.

## Comportements couverts

1. **Priorité des créneaux** : Journée disponible prioritaire sur Matin et Après-midi ; si Journée complète, retenir seulement les demi-journées disponibles ; demandes successives du même enfant/inscription/date ; annulations conservées.
2. **Pas de doublons Quantite** : une demande identique retraitée ne doit pas ajouter `+1` ni réécrire une quantité légitime différente de 1 ; l'attribution à une autre inscription, le pointage, la facturation et les cas ambigus exigent une revue.
3. **CE-4 / CE-5** : sauvegarde partielle et exception après sauvegarde, sans rejouer l'application des consommations.
4. **Marqueur de réconciliation** : lecture d'un jeton durable unique, refus des marqueurs illisibles ; finalisation SQL distincte du rejeu du traitement.
5. **Parcours opérateur** : navigation et fermeture possibles sans persister une demande incertaine ; dialogue `Vérifier et reprendre`, bouton d'application de la demande neutralisé, confirmation explicite ; aucun envoi automatique d'email lors de cette reprise.
6. **Contrats existants** : tests historiques de repas, de grille, d'emails, de facturation et de réseaux fictifs inclus dans la CI.

Les cas sont qualifiés par tests unitaires et d'intégration avec simulations. **La réussite ne prouve pas un parcours interactif sur un poste Windows réel connecté au serveur de l'association.**

## Contre-qualification MySQL 5.7 réelle et isolée

- Code et tests : `130324ca6dfe2173515d41d3d0680b9fbd3f001a`
  (ajout uniquement de quatre tests SQL au code déjà qualifié sur Windows).
- Campagne : [GitHub Actions 40585542910](https://github.com/fr4nck/Noethys-SL/actions/runs/40585542910) — **SUCCESS**, serveur MySQL **5.7.44** local jetable, archive officielle et SHA-256 vérifiés.
- Résultat : **29 tests PASS, 0 FAIL, 0 ERROR, 0 SKIP**, dont quatre nouveaux contrôles #435 exécutés sur deux connexions réelles :
  - marqueur d'une tentative unique et récupération du jeton après connexion ;
  - `GET_LOCK` détenu par une autre connexion empêche une seconde tentative ;
  - mauvais jeton refusé sans supprimer le marqueur ;
  - marqueur nettoyable après validation SQL, sans réappliquer la grille.
- La campagne rapide Windows sur le code métier précédent était verte ; une nouvelle CI rapide est lancée sur `130324ca` pour vérifier également l'intégration du nouveau fichier de tests.

**Portée** : cette contre-épreuve valide les primitives SQL et leur sérialisation courte. Elle **ne valide pas** une transaction atomique couvrant la durée d'un formulaire ouvert puis `Save_grille` sur deux postes concurrents. Ce dernier scénario reste STOP-GATE de production.

## Limites et conditions de levée du STOP-GATE

- **Concurrence MySQL multi-postes non qualifiée** : les deux lectures du jeton avant correction détectent des changements déjà visibles, mais ne rendent pas atomique la séquence finale `LireReprise → Save_grille → EnregistrerDemande → Terminer`. Deux opérateurs simultanés restent un scénario à contre-qualifier avec un serveur et deux clients isolés. Aucune promesse d'idempotence transactionnelle universelle.
- **Vraie base réseau** : pas d'essai sur les données PMSL ; les tests MySQL locaux nécessitant les variables `NOETHYS_TEST_MYSQL_*` sont ignorés lorsque leur serveur jetable n'est pas configuré. Les 32 tests ignorés par la campagne doivent être inventoriés avant une déclaration de release.
- **Recette graphique réelle** : sélectionner une demande incertaine, constater la navigation, ouvrir `Traitement manuel`, vérifier la grille, accepter/refuser, contrôler la reprise, les factures et les confirmations déjà acceptées, puis refermer et rouvrir Noethys.
- **Cas métiers sensibles** : demi-journée déjà pointée/facturée, journée et demi-journée déjà persistées, quantité supérieure à 1, prestations ou états contradictoires, annulations successives et changements entre postes.
- **Déploiement** : aucun installateur, tag, release, migration, modification de `noethys/Portable` ou de la base de production dans ce lot. L'archive provisoire `noethys435_lot_dev_non_deployable.zip` est **obsolète** ; ne pas l'exécuter.
- **Branches** : le travail spécifique `wx` n'a pas été propagé vers `main` ou `qt`. Conserver les deux dossiers voulus `Noethys-SL` et `Noethys-SL-qt`.

## Reprise

Issue principale : [#435](https://github.com/fr4nck/Noethys-SL/issues/435).

Pour toute qualification complémentaire : cloner ou mettre à jour le dépôt **dans un environnement isolé**, relever le HEAD, exécuter les contre-épreuves sur bases fictives, contrôler la concurrence MySQL avec deux connexions distinctes et l'UI Windows manuelle **avant** installation de production. Ne pas supprimer un marqueur de réconciliation pour faire simplement disparaître le message. Ne pas confondre la CI verte et une recette métier de production validée.
