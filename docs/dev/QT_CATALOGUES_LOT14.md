# Noethys SL Qt — Lot C14 : grands modules administratifs

État : 28 octobre 2026, branche canonique `qt`, qualification technique C14
sur SQLite temporaire entièrement fictif. **Ni version distribuable, ni
validation de production, ni parité fonctionnelle complète avec wx.**

## 1. C13 préalablement qualifié

La référence C13 n'est plus la CI 40558968795 indiquée « en cours » :
[run Windows 40560772284](https://github.com/fr4nck/Noethys-SL/actions/runs/40560772284),
sur `qt 2f97b75cb02c1e38f4492500bb3745cd7ba4a9d3` :
`completed/success`, 301 tests PASS, zéro échec, C12_NATIVE_PASS et
C13_FINANCE_PASS (deux profils chacun), données fictives inchangées.
Artefact `qt-c13-finances-fictives`, ID 12761142180, SHA-256
`b14446cb13ad5b72d31a0f5d244488176d4f67a6de4832eab26e1d08718e7b74`.
Le détail est conservé dans [QT_FINANCE_LOT13.md](QT_FINANCE_LOT13.md).

## 2. Inventaire à partir des listes wx historiques

La coque Qt C13 comportait déjà : accueil, recherche Individus/Familles,
éditeur isolé Activités, Inscriptions, Consommations (consultation),
Facturation (factures/prestations), Règlements (règlements/ventilation),
Comptabilité (trésorerie/dépôts). Elle ne contenait pas les entrées
administratives ci-dessous :

| Rubrique native C14 | Listes intégrées | Sources wx examinées |
| --- | --- | --- |
| Cotisations | Cotisations, Types de cotisations | `OL_Liste_cotisations.py`, `OL_Types_cotisations.py` |
| Contrats | Contrats | `OL_Contrats.py` |
| Quotients familiaux | Quotients, Types de quotients | `OL_Quotients.py`, `OL_Liste_quotients.py` |
| Locations | Locations, Demandes de location | `OL_Locations.py`, `OL_Locations_demandes.py` |
| Commandes | Commandes | `OL_Commandes.py` |
| Devis | Devis | `OL_Devis.py` |

**Toujours absents ou incomplets de la coque** (non exhaustif) :
adhésions et échéances, gestion des cotisations manquantes,
types d'unités et validités complexes, contrats PSU/saisie, factures
et relances générées, gestion des droits et période comptable,
ventilation et écritures, pointage/badgeage et toutes les écritures
de consommations, commandes de repas éditables et contrôle des repas,
déductions/forfaits, statistiques, états AFAS, attestations, contrats
scolaires, transports, planning locations, Portail/Connecthys,
Nomadhys, synchronisation PMSL Équipe, courriers/impressions,
extensions et utilitaires. Les anciennes listes wx ne constituent
pas des moteurs autonomes : elles mélangent présentation, calculs,
données et écritures. C14 ne les importe donc pas telles quelles.

## 3. Architecture C14

- `noethys_qt/catalog_readonly_core.py` : neuf domaines déclarés
  statiquement, aucun identifiant SQL fourni par l'utilisateur ;
  `CatalogRepository` réutilise uniquement la connexion Qt déjà
  existante et le convertisseur d'affichage financier C13.
- `noethys_qt/catalog_readonly_ui.py` : modèle Qt, tableaux
  non éditables, filtres, worker facultatif, retour famille et
  accès aux inscriptions par identifiant historique.
- `noethys_qt/noethys_native.py` : six entrées supplémentaires dans
  **la coque native existante**, sous la navigation C13 ; menus,
  accueil et Ctrl+F, actualisation et historique de navigation.
- `noethys_qt/people_details.py` : cinq raccourcis famille pour
  cotisations, contrats, quotients, locations et devis.
- Compatibilité C12/C13 : `catalog_enabled=False` dans leurs
  anciennes fixtures et lanceurs, afin de ne jamais consulter
  des tables C14 absentes. La navigation comporte 14 entrées
  connues, même si les six nouvelles sont désactivées dans ces
  deux modes de recette historiques.
- Les boutons d'édition, de paiement, de comptabilisation, de
  suppression et d'export sont **absents** de C14.

Liaisons :
`cotisations.IDfamille`, `quotients.IDfamille`,
`locations.IDfamille`, `locations_demandes.IDfamille`,
`devis.IDfamille` et
`contrats.IDinscription → inscriptions.IDfamille`.
L'identité du contrat est conservée depuis `contrats.IDindividu`
et l'accès à la fiche Inscriptions résout `IDinscription` dans
le résolveur SELECT-only existant. Un contrat orphelin
reste sans famille : aucun rattachement reconstruit sur un nom,
sur `categories_travail`, ou sur une ligne sélectionnée.

Les dates affichées sont les dates **stockées** :
un filtre « année » ne signifie ni « exercice comptable »,
ni « année scolaire », ni « validité sur période ».
Quotient et revenu, total/réglé/solde d'un devis restent
des champs enregistrés, jamais recalculés ou validés.
Plafond de lecture : **250 lignes plus un témoin de troncature**,
sans total global artificiel. Les recherches échappent `%`,
`_`, `!`, utilisent des paramètres `?` / `%s`,
et les années des bornes [N-01-01, N+1-01-01).

## 4. Isolation et vérifications C14

Fixture `tools/qt_c14_catalog_fixture.py` : extension du C13
100 % inventé dans `TemporaryDirectory`, chemins et marqueurs
vérifiés avant les modifications *de la seule fixture*.
Aucune base utilisateur, `.nod`, `Config.json`, profil portable,
secret, famille réelle ou connexion réseau n'entre dans le parcours.

Tests `tests_qt/test_catalog_c14_readonly.py` :
neuf domaines, filtres exacts par famille, année, recherches littérales,
orphan contrats, montant de précision non altérée, refus des IDs
invalides **avant connexion**, SQL paramétré, connexions fermées,
troncature, intégrité avant/après et navigation Qt réelle.
Les tests historiques C12/C13 et leur capture hors écran sont maintenus.

Démonstration :
`tools/Noethys-Qt-C14-Catalog-Demo.cmd` ou
`python tools/qt_c14_native_catalog_demo.py --theme light`.
CI Windows (sans packaging) : `.github/workflows/qt-prototype.yml`,
deux parcours C14 `--smoke` (clair 100 %, sombre 150 %), 14 vues
chacun, PNG + JSON publiés seulement si les parcours réussissent,
avec vérification de `dump()` de la base fictive.

**Statut de CI C14 au moment de la première rédaction** :
EN ATTENTE d'exécution et vérification sur commit publié.
Ne jamais assimiler la compilation ou les tests sur données
inventées à une qualification d'accès MySQL réel, de droits,
d'écritures ou à une recette Windows manuelle.

## 5. Référence des branches avant travaux

| Branche | SHA avant C14 | Qualification C14 |
| --- | --- | --- |
| `main` | `f6f5ccdf6a491025db052b7759aa6facc01b2eca` | NON APPLICABLE — inchangée |
| `wx` | `ba9271339ac14ac159e3ab62af70ddfcaa3ab721` | NON APPLICABLE — inchangée |
| `qt` | `2f97b75cb02c1e38f4492500bb3745cd7ba4a9d3` | EN QUALIFICATION sur données fictives |

Les trois branches ont des historiques divergents : aucun merge
global ou synchronisation de moteur n'a été engagé. Les changements
C14 sont spécifiques à la coque et aux tests Qt. Les traitements
historiques et correctifs communs non intégrés restent à qualifier.

## 6. STOP-GATE

- **Toutes les écritures métier** : création ou modification de
  cotisations, contrats, revenus/quotients, locations et demandes,
  commandes, devis, rattachements, pointages, prestations,
  règlements, ventilation et écritures comptables.
- Contrôle réel des permissions, concurrence, verrouillages,
  intégrité des données historiques, bases MySQL et production.
- Validité tarifaire, montants, années scolaires, cotisations
  acquittées, quotients CAF, audit réglementaire et historiques.
- Packaging, activation dans `Noethys.exe`, export comptable
  et diffusion utilisateurs.

## 7. Suite

Lot C15 recommandé : raccordement en consultation des
**Adhésions / Échéances et des États / Statistiques métier utiles**,
après qualification de leurs contrats SQL et réutilisation des moteurs
purs déjà présents. Les éventuelles écritures seront ensuite
qualifiées domaine par domaine, pas ouvertes par l'ajout d'un
bouton dans Qt.

## 8. Cible de décloisonnement wx/Qt (décision du 28/10/2026)

Le futur `main` devra porter un **moteur métier commun pur**, ni wxPython ni
PySide6 : contrats de données, règles métier, validations, opérations
transactionnelles et moteurs de calcul testés. `wx` et `qt` deviendront
progressivement deux adaptateurs graphiques de ce même moteur.

**C14 ne réalise pas encore cette extraction** : il réutilise la connexion
et les contrats de consultation existants et laisse les écritures
historiques dans wx sans les modifier. Les futures extractions doivent
commencer par cartographier les importations wx, définir les interfaces
de services, reproduire les invariants avec tests fictifs et comparer
les comportements avant tout redirection de l'interface historique.

La base PostgreSQL envisagée est un chantier distinct du découplage
graphique : aucune migration de moteur SQL implicite et aucun basculement
des données de production n'est autorisé par C14.
