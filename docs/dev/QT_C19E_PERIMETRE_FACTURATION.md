# Noethys-SL Qt — C19e : périmètre complet de facturation (sans autorisation d'écriture)

Date : 03/11/2026 · Branche `qt` · Ticket [#440](https://github.com/fr4nck/Noethys-SL/issues/440).

**C19e n'est ni un nouveau moteur de facturation ni une version publiable.**
L'objectif est de rendre mesurable le contrat multi-activités, la provenance
des prestations et les propriétés minimales d'une transaction, **sans
brancher de commandes d'écriture dans Noethys-SL**.

## Source métier identifiée dans wx

`noethys/Dlg/DLG_Factures_generation_parametres.py` vérifie
`VerificationDroitsUtilisateurActuel("facturation_factures", "creer", IDactivite=IDactivite)`
**pour chaque activité sélectionnée**. En revanche, une sélection d'activités
vide peut être confirmée et la boucle de droits n'est alors pas exécutée.
`noethys/Dlg/DLG_Factures_generation_selection.py` insère un en-tête dans
`factures`, puis rattache des `prestations` par leurs identifiants.
Ces extraits ne prouvent **ni atomicité, ni idempotence, ni résistance aux
concurrences, ni validation des droits côté service**.

C19d avait laissé `invoice_creation` à `INCONNU` par sécurité.
C19e reconnaît désormais le nom du droit observé dans wx, **sans convertir
un droit déclaré en authentification ni en permission d'exécuter**.

## Deux contrats et une source réellement fictive

`noethys_qt/invoice_scope_contract.py` : vérifie une proposition de facturation
contenant une liste non vide et sans doublons d'activités et de prestations.
Toutes les activités réellement représentées par les prestations doivent
correspondre exactement au périmètre déclaré. Chaque activité doit posséder
une règle `facturation_factures / creer` déclarée. Une interdiction sur une
seule activité contredit l'ensemble. La résolution de groupes doit être
complète ; aucune règle absente, mal formée ou ambiguë ne devient un accord.
Le compte payeur, la famille, la date et l'identifiant de chaque prestation
sont comparés ; une facture existante est signalée. Le montant est conservé
au format brut : `12.005`, `-1.005`, `0.00`, `1000.0003` ne sont pas arrondis.

Les dates sont contrôlées par la barrière de périodes C19d. Il s'agit d'une
interprétation conservatrice des verrous prestations/factures, **pas d'une
parité du générateur wx**. Une date absente ou un inventaire de périodes non
qualifié refuse implicitement toute autorisation.

`noethys_qt/invoice_scope_fixture_repo.py` : relit les prestations
sélectionnées avec un unique `SELECT` SQL sur la **fixture temporaire C8+C13**,
en `mode=ro`, `PRAGMA query_only=ON`, puis revalide les deux marqueurs dans
la même connexion. Les usages d'une prestation par plusieurs consommations
ne sont **pas** multipliés par le nombre de séances. Un lien à **plusieurs
activités** est ambigu et donc bloquant ; une prestation absente reste
explicitement dans le périmètre de contrôle comme anomalie, jamais omise.
Aucune base réelle ne doit être proposée : le dépôt ne fournit aucune
fonction d'écriture ni intégration de ce lecteur dans la coque de production.

`InvoiceScopeReport.executable` est **toujours faux** et son forçage à
`True` lève une exception. La présence de règles déclarées favorables
reste insuffisante : la session authentifiée, les droits du service, la
transaction SQL et les règles de numérotation/tarification manquent.

## Banc transactionnel hors logiciel

`tests_qt/test_c19e_inmemory_transaction_oracle.py` contient une
**simulation expérimentale, strictement en SQLite `:memory:`**, non importée
par l'application. Elle teste : `BEGIN IMMEDIATE`, rollback après panne,
relecture des droits et périodes dans une même transaction, exclusivité
des prestations, clé d'idempotence liée au périmètre exact, refus d'une
reprise ambiguë et conservation des montants bruts (même négatifs).

**Ce banc N'EST PAS une implémentation de service transactionnel Noethys.**
Il ne simule pas encore deux processus concurrents, la sémantique transactionnelle
de MySQL 5.7, les tarifs, la numérotation légale, les ventilations, les
cotisations ou les sessions réellement authentifiées. Il ne crée aucune
facture réelle, uniquement des lignes inventées en mémoire qui disparaissent
après chaque test.

## Critères de recette

- 26 tests `test_c19e_invoice_scope_contract.py` (Python pur).
- 16 tests `test_c19e_invoice_scope_fixture_repo.py` (fichier temporaire
  fictif, marqueurs et schéma synthétiques, SQLite en lecture seule).
- 13 tests `test_c19e_inmemory_transaction_oracle.py` (SQLite uniquement
  en mémoire, transaction/rollback/idempotence expérimentale).
- **55 nouveaux tests**, seuil de collecte Qt **529 → 584** ; aucun test
  supprimé, sauté ou attendu en échec.
- Nouveau workflow `.github/workflows/qt-c19e-scope.yml` sur Windows
  et Linux, sans installer PySide6 ; intégration des 55 tests au workflow
  ciblé Windows C19b–C19e et à la suite globale.
- Ne pas revendiquer le PASS avant résultats CI réels par SHA. Le dernier
  résultat pleinement vérifié de C19d reste 22/22 Linux et Windows et
  53/53 de recette Windows ciblée ; la suite C19d de 529 tests a été
  lancée et son verdict doit être contrôlé séparément.

## Barrières ouvertes

1. **Session réelle** : source de vérité de l'identité utilisateur, validité
   temporelle de session, droits complets résolus, absence de contournement.
2. **Port métier réel** : interface de lecture/écriture avec contrôles d'accès,
   même transaction pour droits, verrous, attribution, numérotation et
   finalisation ; tests adversariaux de concurrence et reprise.
3. **Équivalence wx/MySQL** : tarifs, dates, prestations partagées, forfaits,
   cotisations, écritures comptables, facture et ventilation ; banc sur
   MySQL jetable avec oracle indépendant avant adoption.
4. **Restauration isolée** : aucun déploiement avant qualification complète,
   et incident de sauvegarde #437 toujours différé.

**STOP-GATE absolu :** aucun passage à une source PMSL, aucun service
d'écriture branché, aucune émission de facture, aucune migration ni diffusion
Qt 0.2.0. Le banc en mémoire ne constitue pas une permission d'écriture.
