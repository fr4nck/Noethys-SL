# Noethys SL Qt — C18 : scolarité, produits et pièces

Date : 28 octobre 2026. Branche canonique : `qt`.
**État initial : EN QUALIFICATION** avant validation CI sur SHA C18.
Aucune release ni aptitude à la production.

## Prérequis et historique

Au début du lot :
- `main 53052ed5075c9b8336f380f7db1a1ca2daa5b595` ;
- `wx 61130f7eecafce9469611d6de267f56f95fccdac` ;
- `qt a0bfcfb985419bb1bb7d167a45322f3eb4dd927a`.

C17 a été qualifié sur le code Qt
`e3f0f1e01203d2743c12c02fc79e8b4d644ff87f` :
[CI 40691411571](https://github.com/fr4nck/Noethys-SL/actions/runs/40691411571),
**409 tests Windows PASS**, 30 captures C17. Le moteur pur
`UTILS_Consumption_StateCounts.py` a été ajouté au socle `main`
et réutilisé par Qt ; aucun retour en wx ni production validé.

Les trois historiques et la préversion wx RC10 restent préservés.
Aucun force-push ni intégration globale ; travaux locaux extérieurs à
GitHub impossibles à inventorier depuis ce connecteur.

## C18 : cinq rubriques nouvelles et huit domaines SELECT-only

| Rubrique C18 | Domaines/onglets | Source historique Noethys |
| --- | --- | --- |
| Écoles, classes et niveaux | `schools`, `school_classes`, `school_levels` | `OL_Ecoles.py`, `OL_Scolarite.py` et `DATA_Tables.py` |
| Parcours de scolarité (restreint) | `school_history` | `OL_Scolarite.py`, `DLG_Individu_scolarite.py` |
| Produits et ressources | `product_inventory`, `product_categories` | `OL_Produits.py`, `OL_Categories_produits.py` |
| Référentiel de pièces | `document_types` | `OL_Types_pieces.py` |
| Pièces enregistrées (restreint) | `documents_metadata` | `OL_Pieces.py`, `OL_Pieces_fournies.py` |

Coque **23 → 28 entrées** lorsque C18 est activé. Les modules
restreints sont visibles comme entrées **désactivées** en
configuration normale ; la coque n'instancie pas leurs pages.

**Lecture des informations source uniquement** :
- classes et scolarité = dates et relations stockées, pas un statut
  scolaire, une inscription effective ou un certificat de présence ;
- produits = quantités déclarées, sans calcul du stock disponible
  (locations, chevauchements, partage ou réservations) ;
- pièces = métadonnées (type, titre, dates, IDs) sans téléchargement
  ni lecture des contenus binaires. Aucune vérification de validité,
  d'obligation ou de complétude documentaire.

Les colonnes proviennent du schéma `noethys/Data/DATA_Tables.py`
et des listes wx citées, sans importer `wx`. Les requêtes
sont déclarées en dur dans `catalog_c18_specs.py`, utilisent le
même `CatalogRepository`, pagination 250 + 1 témoin de
troncature et recherche SQL échappée. Les montants saisis restent
affichés sans calcul de taxe ni prix de location.

## Garde sur données personnelles et navigation

Les modules `school_history` et `document_records` sont
refusés par défaut jusque dans `CatalogRepository.search()`
avant toute ouverture SQL. `c18_sensitive_enabled=True`
nécessite simultanément :
- `read_only_demo=True` et `c18_enabled=True` ;
- chemin éphémère `C8_DEMONSTRATION_FICTIVE.sqlite` dans
  un dossier temporaire `noethys-qt-c8-fictif-*` non symlink ;
- marqueurs C16 **et C18** contrôlés sur SQLite en `mode=ro`.

Ce garde-fou **ne constitue pas un système d'habilitations**.
L'accès aux dossiers réels reste explicitement interdit.
Le lancement Qt normal garde `c18_sensitive_enabled=False`.

Extension du lecteur commun Qt : filtre `individual_id`
paramétré par clé SQL exacte ; pour les pièces, deux filtres
`IDfamille` et `IDindividu` distincts qui se combinent
par **ET**. Aucune inférence par les rattachements (risque
de faux positif), aucun rapprochement de noms.
La fiche Individu fictive offre des liens directs vers
le parcours scolaire et les pièces de son propre ID,
la fiche Famille vers les pièces de `IDfamille` stocké.
Sélection et retour au contexte conservés.

Le travail renforce le lecteur Python indépendant de PySide6
(`catalog_readonly_core.py`) et sa composition native ;
il ne prouve pas encore une extraction du catalogue dans
le moteur commun `main`. Celle-ci reste à qualifier avec
des tests de parité wx/Qt, notamment sur les droits.

## Tests, démonstration et preuve attendue

`tools/qt_c18_fixture.py` étend C16 **uniquement** dans le
répertoire temporaire déjà marqué C8→C16. Ajout d'écoles,
classes, niveaux, scolarité, catégories de produits, champs
complémentaires produits, types de pièces et pièces :
**toutes les personnes et familles sont inventées**.
Aucun profil, sauvegarde, `.nod`, réseau ou fichier médical réel.

`tests_qt/test_c18_schools_products_documents.py` :
**30 tests** sur SQL, sécurité, filtrage personnel, clés exactes,
dates, montants, garde de droits, navigation et non-régression.
Protection anti-perte attendue : **439 tests Qt** au total
(409 C17 + 30 C18) sur trois shards Windows.
Conservation de tous les tests antérieurs et parcours C6–C17.

`tools/qt_c18_native_demo.py` et
`tools/Noethys-Qt-C18-Demo.cmd` : deux profils hors écran
(clair 100 %, sombre 150 %), **18 captures chacun** et
deux traces JSON, avec comparaison du dump SQLite avant/après
consultations. Le journal de badgeage C16 reste désactivé.
Artefact GitHub C18 attendu uniquement après succès du job.

**État CI Windows C18 : EN ATTENTE**. À remplacer seulement
après preuve d'un run `completed/success` sur le SHA précis,
439 PASS, deux marqueurs `C18_REGISTRIES_PASS` et 36 PNG.

## Interdictions maintenues

Aucune écriture de scolarité, de famille, produit, stock,
pièce, pièce jointe, reçu, courrier, règlement ou consommation.
Aucun traitement réel de pièces médicales ou justificatifs.
Aucune qualification CAF/AFAS ou de validité documentaire.
Aucun module rendu disponible aux familles en production.
Aucun changement des branches `wx` et `main` réalisé
par C18, ni migration PostgreSQL.

## Suite

C19 : étendre les référentiels de fonctionnement, poursuivre la
décomposition des contrats communs sur `main`, et préparer la
vérification des habilitations réelles avant d'ouvrir les
dossiers scolaires et les pièces dans Qt.
