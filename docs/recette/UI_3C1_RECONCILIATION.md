# UI-3C.1 — reservations incertaines : preuve et reprise

26/10/2026, developpement sur `wx` uniquement. Aucun candidat, build,
tag, release, deploiement, migration ou utilisation des donnees PMSL.

## Base et contre-epreuves

HEAD distant releve avant intervention : `wx`
`9c601b3f4e6be74bc4d05ee1862b85988d221a02` ; `main`
`77c7efe2b96bc2272f1130745a7a4aa5b832c0ed` ; `qt`
`f2316046f9f22ed59aeba33f9f8c090d3667ca06`.
Les dialogues de `main` et `qt`, relus via GitHub, sont identiques et
ne contiennent pas cette protection. Ces branches restent inchangees.

Les quatre tests ci-dessous ont ete executes sur une copie `git archive`
du HEAD initial, puis sur le correctif. Meme fichier de tests, SHA-256
`afed44e30a21199bf699f3e292a6bb4895ba4caa283cf3e229c1ba41552d1951`.
Ce sont les vraies methodes `Dialog.Traitement`, `Traitement.Traiter`,
`Traitement_reservations`, `Appliquer_reservations`, `Save_grille` et
`DLG_Badgeage_grille.CTRL.SaisieConso`, avec grille/cases fictives et
SQLite temporaire. La sauvegarde fictive ecrit effectivement les quantites
en SQLite avant l'erreur injectee. `Verifier_ventilation` est remplace par
un double, notamment pour injecter CE-5. Les widgets sont des doubles.

| Contre-epreuve | HEAD initial | Correctif |
| --- | --- | --- |
| CE-4 : 1re unite appliquee, 2e refusee, reponse vide, sauvegarde partielle puis relance | FAIL : quantite 1 -> 2 | PASS : quantite 1, un seul Save_grille |
| CE-5 : Save_grille termine puis exception dans Verifier_ventilation | FAIL : les deux quantites 1 -> 2 | PASS : quantites 1, un seul Save_grille |
| Save_grille leve apres une ecriture | FAIL : deux sauvegardes | PASS : une seule sauvegarde |
| Save_grille renvoie False apres une ecriture | FAIL : portail_actions valide a tort | PASS : demande en attente, reprise bloquee |

Reproduction depuis la copie du HEAD initial, avec le fichier de tests
du correctif copie dans `tests/` :

```powershell
python -m unittest -v `
  tests.test_connecthys_ui3c1_reconciliation.ReconciliationTests.test_ce4_application_partielle_ne_rejoue_pas_quantite `
  tests.test_connecthys_ui3c1_reconciliation.ReconciliationTests.test_ce5_exception_post_save_ne_rejoue_pas_quantite `
  tests.test_connecthys_ui3c1_reconciliation.ReconciliationTests.test_save_grille_exception_ne_rejoue_pas `
  tests.test_connecthys_ui3c1_reconciliation.ReconciliationTests.test_save_grille_false_ne_valide_pas_la_demande
```

## Protection et perimetre

- Avant d'appeler le metier pour une reservation, un jeton par `IDaction`
  est commite dans `parametres`, categorie privee
  `noethys_sl_reservations_tentatives`, nom `action_<IDaction>`.
  Ni nouvel etat Connecthys, ni categorie `portail`, ni reutilisation des
  categories ou cles des emails RC9. Aucun changement de schema.
- Une ligne existante, meme dupliquee ou illisible, ou une lecture/ecriture
  impossible interdit le nouveau traitement. L'etat SQL reel doit encore
  etre `attente` : un track perime ne peut pas rejouer une demande validee.
- Creation serialisee par `BEGIN IMMEDIATE` sous SQLite et verrou nomme
  court `GET_LOCK` sous MySQL. Le marqueur commite, pas le verrou, couvre
  ensuite toute la tentative et survit a la fermeture ou au crash.
- Retour metier incomplet, retour False de Save_grille ou exception avant
  resultat complet : marqueur conserve, pas de finalisation automatique.
  Automatique, Manuel, validation et emails sont bloques avec le message
  « Reconciliation requise », y compris dans une autre fiche/processus.
- Resultat complet connu dans le dialogue ouvert : la reprise UI-3C
  retente uniquement `EnregistrerDemande`. Aucune reservation ni aucun
  email ne sont rejoues. Le marqueur n'est retire qu'apres commit confirme
  de `portail_actions` et actualisation de l'affichage. Une panne apres
  commit garde le contexte local et, si encore present, le marqueur durable.
- Seule autre suppression normale : annulation manuelle explicite avant
  tout appel a Save_grille. Pas d'expiration ni bouton de deblocage aveugle.
- RC9 conserve son nettoyage des seules confirmations completes dans la
  transaction de validation. Les suivis partiels/incertains sont conserves.

## Tests et verdict

- `test_connecthys_ui3c1_reconciliation` : **19 PASS** sous Windows/wx 4.2.5.
  Reouverture de fiche, processus Python neuf, deux connexions SQLite,
  marqueur avant premiere saisie, commit accepte avec reponse perdue,
  INSERT refuse, marqueur corrompu/duplique, fermeture, refus d'email,
  SQL seul apres echec, Refresh/nettoyage apres commit et annulation manuelle.
- UI-3C.1 + UI-3C + UI-3B : **35 PASS**. Les suites ciblees RC9/Connecthys,
  SMTP/Mailjet, progression, diagnostic et repas : **96 PASS**.
- Premier essai de la suite rapide sous Python 3.11 : 1076 tests,
  1042 PASS, 1 FAIL, 6 ERROR, 27 SKIP. Le FAIL est la protection Git
  contre le proprietaire du clone ; les six ERROR sont des fichiers SQLite
  temporaires encore ouverts au nettoyage. Ces memes six ERROR sont
  reproduits sur le HEAD initial (14 tests, 8 PASS, 6 ERROR).
  Aucun test existant n'a ete affaibli pour les masquer.
- Suite rapide sous Python 3.10.11 / wx 4.2.5, comme la CI Windows :
  **1076 tests, 1049 PASS, 0 FAIL, 0 ERROR, 27 SKIP**, en 135 s.
  Compilation du code/tests/scripts/outils : PASS. Qualification distante
  liee au SHA effectivement pousse dans `docs/dev/REPRISE_CODEX.md`.
- **CI distante Windows SUCCESS** sur
  `ba5b71fda4c44bf76081ad049d1fcd39f75b87ef`,
  [run 40321502745](https://github.com/fr4nck/Noethys-SL/actions/runs/40321502745) :
  syntaxe PASS, **1076 tests, 1049 PASS, 0 FAIL, 0 ERROR, 27 SKIP**,
  316 s. Les 19 nouveaux tests, dont CE-4/CE-5, sont PASS dans les journaux.

## Reconciliation et limites

Un marqueur ne prouve ni succes ni absence d'effet. Ne pas le supprimer
pour simplement « reessayer ». Suspendre les traitements de cette demande
sur tous les postes ; conserver les preuves ; comparer chaque reservation
aux consommations, quantites, prestations et confirmations deja acceptees.
Un operateur habilite doit determiner et corriger seulement les ecarts
manquants, puis confirmer le statut/reponse de la demande sans rejouer le
lot ni les emails. Retirer uniquement le marqueur de cette demande et de
ce jeton apres controle durable de cette reconciliation. Si l'absence de
tout effet est prouvee, une nouvelle tentative peut etre explicitement
autorisee apres ce meme controle. Au moindre doute, conserver la barriere.
Ce lot ne fournit aucun outil automatique d'effacement/reparation SQL.

La preuve porte sur le parcours wx et les erreurs observables. Le retour
historique `None` de la grille reste compatible ; les erreurs SQL masquees
par des couches historiques sans exception/False ne sont pas detectees ici.
Les ecritures metier ne deviennent pas une transaction unique/idempotente.
Les tentatives anterieures au correctif n'ont pas de marqueur retrospectif.
La concurrence avec un ancien client qui ignore la barriere, les editions
SQL externes, la perte/restauration de parametres et le moteur MySQL reel
ne sont pas qualifies. MySQL est teste ici par curseur fictif uniquement.
Pas de socket/service reel dans les nouveaux tests, aucun email reel ;
la suite historique contient ses propres serveurs SMTP fictifs en loopback.
La recette graphique focus/reactivite Windows demeure hors preuve.
**PASS cible sous ces limites ; STOP-GATE pour declaration STABLE/release.**
