# Noethys SL Qt — C19 : référentiels comptables, budgets, encaissements et organismes

**Date de reprise : 3 novembre 2026.** Branche de développement : `qt`.
**Qualification du nouveau code : EN ATTENTE** des quatre jobs Windows et de
leurs preuves graphiques. Ce lot n'est pas une release et ne valide pas la
production, les droits utilisateurs ou les calculs financiers.

## 1. Prévol et référence de non-régression

SHA relevés avant toute modification C19 :
- `main` : `29eed5b8a1f9d378b0a8aa10d4d5916c81dd8310` ;
- `wx` : `ce654667886bc55c3a7b05f3971b3b05ae9e90d2` ;
- `qt` : `6b11611347a254328344ddc36580b4a0fbcadc6f`.

`AGENTS.md` de `qt` relu : trois branches canoniques seulement,
aucun force-push, diffusion ciblée des changements communs,
protection des travaux WIP, aucune base réelle ni données familiales
dans les tests. Aucun merge global ni modification de `main`/`wx`
n'est requis pour ce lot purement consultatif Qt. Les évolutions
indépendantes de ces branches ne sont pas qualifiées ici.

**C18 vérifié a posteriori** : la CI Windows
[40705023144](https://github.com/fr4nck/Noethys-SL/actions/runs/40705023144)
a confirmé `completed/success` sur
`6a70d59ba0b0ea071f8a2056920975e64485772a` :
**439 tests réussis sans erreur ni échec** (223 + 125 + 91),
quatre jobs verts, démonstrations C18 clair 100 % et sombre 150 %
`C18_REGISTRIES_PASS` de 18 images chacune, source temporaire inchangée.
Artefact `qt-c18-scolarite-produits-pieces-fictifs`,
ID 12822524418, 529 357 octets, SHA-256
`bdaa7a87b0b6360491734a3f4b20ca0a6fb69b8a34c620e55a074d91dba23220`.
La page C18 était restée au statut « EN QUALIFICATION » malgré cette
preuve : corrigée dans la reprise C19, sans réécrire le code C18.

## 2. Quatre rubriques supplémentaires, douze lectures SQL

La coque passe de **28 à 32 entrées** quand `c19_enabled=True`,
avec les **12 domaines SELECT-only** suivants.

| Rubrique C19 | Onglets | Sources historiques |
| --- | --- | --- |
| Référentiels comptables | Exercices ; Postes analytiques ; Catégories ; Comptes comptables | `OL_Analytiques.py`, `OL_Categories_operations.py`, `DATA_Tables.py` |
| Budgets enregistrés | Budgets ; Catégories / valeurs-formules brutes | `OL_Budgets.py`, `OL_Categories_budgetaires.py` |
| Paramètres d'encaissement | Modes de règlement ; Intitulés de comptes bancaires ; Banques | `OL_Modes_reglements.py`, `OL_Comptes_bancaires.py`, `OL_Banques.py` |
| Organismes et secteurs | Régimes sociaux ; Caisses d'allocations ; Secteurs géographiques | `OL_Secteurs.py`, `DATA_Tables.py` |

Les noms de tables, colonnes et relations sont **déclarés en dur** dans
`noethys_qt/catalog_c19_specs.py`, à partir de `DATA_Tables.py`
et des listes wx existantes. Les écrans utilisent les mêmes
`CatalogRepository`, `CatalogHubPage` et `CatalogTableModel`
que C14–C18 : pas de grille wx intégrée et aucun moteur financier
dupliqué dans Qt.

**Budget par clé SQL exacte** : le filtre optionnel `budget_id`
est déclaré seulement pour `compta_categories_budget.IDbudget`,
validé avant toute connexion et paramétré sur SQLite/MySQL.
Sélectionner un budget et cliquer « Voir les catégories du budget »
ouvre l'onglet des lignes avec son ID exact. Le menu global efface
le contexte précédent ; le tableau d'origine conserve la sélection.
Aucun budget n'est « calculé » : `valeur` peut contenir une formule
stockée qui reste du **texte non exécuté**.

**Précision et limites** : les chaînes décimales sont conservées
sans somme ni arrondi métier ; l'interface montre les frais enregistrés,
jamais leur calcul effectif. Les exercices sont filtrés par année
de leur **date de début enregistrée**, pas par recouvrement
ou par clôture officielle. Les listes restent limitées à
250 lignes + 1 témoin de troncature. Ni solde de compte, ni
validité comptable, ni statut CAF/AFAS, ni capacité de paiement
ne sont déduits de ces tables.

## 3. Confidentialité renforcée

Trois rubriques — `accounting_settings`, `budget_settings`,
`payment_settings` — sont classées **restreintes**.
Le démarrage normal active C19 avec
`c19_sensitive_enabled=False` :
- leurs actions et entrées de navigation sont désactivées ;
- leurs pages ne sont pas instanciées ;
- le dépôt SQL refuse leurs **9 domaines** par
  `PermissionError` **avant l'ouverture d'une connexion**.

La rubrique `organisation_settings` et ses trois domaines ne
consultent pas de comptes de familles et restent visibles.
Le drapeau fictif n'est **pas une habilitation réelle** :
`require_c19_synthetic_source` exige `read_only_demo=True`,
`c18_enabled=True`, `c19_enabled=True`, le chemin éphémère
C8, le marqueur C18 et le marqueur C19 sur une connexion SQLite
`mode=ro`. Tout profil ordinaire est rejeté, même si le
drapeau est passé manuellement.

La consultation de `comptes_bancaires` ne sélectionne que
`IDcompte`, `nom`, `defaut`, `raison`. Elle **n'extrait
jamais** `numero`, `iban`, `bic`, clés RIB/IBAN, identifiants
de prélèvement ou autres secrets. Des sentinelles entièrement
inventées ont été insérées dans les champs bancaires secrets de
la fixture pour démontrer qu'elles n'apparaissent ni dans les
lignes de la vue ni dans les captures. Pas de lecture de ces
secrets dans un fichier exporté.

C18 (scolarité et pièces), C16 (badgeage) et les chantiers
d'écriture continuent d'avoir leurs gardes distinctes.

## 4. Validation technique prévue

`tools/qt_c19_fixture.py` prolonge la fixture C18, exclusivement
dans le `TemporaryDirectory` créé par C8. Contrôle C16/C18,
puis création des tables C19, ajouts de colonnes uniquement
sur les **tables C13 fictives** pour les comptes et les modes
de paiement ; toutes les données sont inventées.

`tests_qt/test_c19_financial_organisation_registries.py` :
**37 nouveaux tests** couvrant les 12 SELECT, année et budget
filtrés, échappement LIKE, SQL paramétré `?`/`%s`,
absence d'inférence financière, conservation des décimales,
garde hors fixture, absence de lecture de secrets bancaires,
navigation sur 32 rubriques, 12 onglets non éditables, retours,
intégrité du `dump()`, et non-régression C13/C16/C17/C18.
Les tests C18 sont figés sur leur périmètre exact, sans retirer
ni remplacer un seul test antérieur.

Le seuil de découverte de la CI passe de **439 à 480** :
37 nouveaux tests C19 et les quatre tests concurrents du contrôle
d'artefacts C18 ajoutés entre le prévol et la publication.
Le workflow préserve leur étape obligatoire de vérification PNG/JSON.
Le fichier C19 est affecté au shard 2, historiquement le moins
chargé ; limite Windows augmentée de 20 à 30 minutes pour
éviter un faux échec des shards C18 mesurés à 1037 s et 858 s.
Aucun `skip`, xfail, ou abaissement de contrôle.

`tools/qt_c19_native_demo.py --smoke` s'exécute en clair 100 %
et sombre 150 % avec **21 étapes et 21 PNG par profil**,
42 captures + 2 traces JSON attendues, source initiale/finale
strictement identique. Les démonstrations C6–C18 restent dans
le même workflow Windows, sans téléchargement de modèle ou
installation de données utilisateurs.

**Résultat CI C19 : EN ATTENTE**, à qualifier seulement à partir
du SHA du code, du run Windows, de ses 480 tests et des deux
marqueurs `C19_REGISTRIES_PASS`.

## 5. Matrice interbranches / STOP-GATE

| Périmètre | main | wx | qt |
| --- | --- | --- | --- |
| Catalogue C19 et nouveaux écrans | NON APPLICABLE à l'interface | NON APPLICABLE à l'interface | EN QUALIFICATION |
| Nouvelles règles de calcul ou de mutation | AUCUNE | AUCUNE | AUCUNE |
| Correctifs partagés récents extérieurs à C19 | PARITÉ NON QUALIFIÉE ICI | PARITÉ NON QUALIFIÉE ICI | PARITÉ NON QUALIFIÉE ICI |

**STOP-GATE production** : droits comptables et bancaires,
comptes et secrets réels, données familiales, calculs de
budget, recettes/dépenses, rapprochement, frais, génération
de factures, comptabilité générale, CAF/AFAS, paiements,
moteur de pointage, écritures métier, exports et migrations
de base restent interdits par ce lot. Une CI fictive verte
ne qualifie pas la production.

## 6. Suite

C20 : intégrer les derniers grands modules compatibles
avec la lecture seule (transports, messages/référentiels,
suivi de calendrier) et formaliser un contrat d'API
du catalogue réutilisable par le moteur commun `main`.
Avant de décloisonner les règles financières ou l'état
de consommation officiel, confronter aux chemins wx
en conditions et habilitations représentatives.
