# Noethys-SL Qt — C19b : parcours opérateur en consultation

Date : 03/11/2026. Branche de travail : `qt`. Ticket : [#440](https://github.com/fr4nck/Noethys-SL/issues/440).

**Statut : CODE PUBLIE / RECETTE WINDOWS EN ATTENTE / AUCUNE MISE EN PRODUCTION.**

## Objectif et limites

Un parcours utile, sans recréer de nouveaux catalogues :

**Famille → Inscriptions de la famille → Consommations de l'inscription → Factures enregistrées de la famille → retours contextuels.**

Ceci n'est PAS un rapprochement comptable de la consommation vers une facture :
- la famille provient de l'identifiant exact `inscriptions.IDfamille` renvoyé par `InscriptionRepository.resolve_link` ;
- les consommations sont filtrées simultanément par `IDindividu` et `IDinscription` ;
- l'écran final affiche **toutes** les factures enregistrées sur le compte payeur de cette famille, sans attribuer une facture précise aux consommations ;
- aucun montant, état de présence, paiement ou droit CAF/AFAS n'est recalculé ;
- l'écran de consultation financière existant reste en lecture seule.

L'individu seul, même relié à plusieurs familles, ne suffit jamais à choisir une famille. Sans inscription résolue avec un `IDfamille` exact, le raccourci facture n'est pas présenté. Le retour arrière restaure les filtres individu/inscription/famille de la consultation et, auparavant, la sélection de l'inscription.

## Garde d'accès

`noethys_qt/c19b_operational_guard.py` autorise ce **raccourci nouveau uniquement sur la fixture de démonstration** :
- `read_only_demo=True`, `finance_enabled=True` ;
- fichier local `C8_DEMONSTRATION_FICTIVE.sqlite` dans `TemporaryDirectory` préfixé `noethys-qt-c8-fictif-`, sans symlink ;
- deux marqueurs SQL C8 et C13 exacts, vérifiés via SQLite `mode=ro` ;
- en l'absence de preuve ou à la moindre erreur : **raccourci désactivé**.

Ce garde-fou n'est **pas** une habilitation de production. Le lancement Qt normal n'active pas ce nouveau raccourci : les vrais contrôles de droits / de visibilité financière et leur vérification côté serveur restent à qualifier.

Avant tout affichage des factures, `NoethysQtWindow._consumption_family_invoices_requested` relit `resolve_link(IDinscription)` : les trois clés de la fiche (inscription, individu, famille) doivent encore correspondre. Une inscription réaffectée est **refusée**, sans navigation vers une ancienne famille.

## Tests de qualification

- `tests_qt/test_c19b_inscription_consumption_invoices.py` : 7 tests Qt sur C13 fictif : parcours complet, autre famille, individu sans famille déduite, identifiants invalides, inscription réaffectée, effacement du contexte par navigation globale, finance indisponible.
- `tests_qt/test_c19b_operational_guard.py` : 4 tests de refus/acceptation de fixture et d'absence d'ouverture SQL hors périmètre.
- Seuil de découverte `tools/qt_ci_test_runner.py` : **491** (480 avant C19b + 11 tests nouveaux) ; aucun test historique retiré.
- CI : `.github/workflows/qt-prototype.yml`, 3 shards Windows et démonstrations antérieures C6–C19 conservées.

La dernière preuve indépendante préalable est le run C18
[40705023144](https://github.com/fr4nck/Noethys-SL/actions/runs/40705023144) :
**439 tests PASS** et deux profils graphiques C18, **sur données fictives**.
Il ne qualifie ni C19b, ni les corrections AFAS ultérieures.

## Barrière de publication

La recette graphique Windows C19b, les contrôles d'habilitation réels, les autorisations de facturation et les travaux de sauvegarde #437 restent ouverts.
Aucune migration, restauration de production, accès aux bases PMSL, nouveau build Qt ou remplacement de Noethys-SL wx n'a eu lieu.
Aucune fusion globale ni nouvelle branche n'a été créée.

**Prochaine étape** : récupérer le résultat CI Windows du SHA précis, corriger toute défaillance puis éprouver la chaîne sur un poste Windows isolé avec une copie intégralement fictive. Ne pas activer ce lien pour des données réelles sans garde d'habilitation reconnue.
