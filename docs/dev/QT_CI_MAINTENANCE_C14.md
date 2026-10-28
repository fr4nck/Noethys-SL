# CI Qt C14 — maintenance du 28 octobre 2026

## État initial vérifié

Run Windows 40638033811, SHA de code `3fc6d793918c655cdaf5a8058b1208f9e65a7bc8` :
328 tests PASS, 0 échec, 877,273 s pour les tests, CI entière ~16 minutes,
parcours C12, C13 et C14 fictifs validés, deux profils de capture C14.
Les anciens artefacts restent des preuves de recette, pas de production.

Problème de maintenance : une seule suite de tests séquentielle consomme
presque toute la limite de temps du job de 20 minutes. Les suites lentes
observées sont C12 (~228 s), C13 (~161 s), C14 (~104 s), avant même les
captures. Avertissement Node.js 20 des actions checkout@v4,
setup-python@v5 et upload-artifact@v4 ; modernisation à qualifier
séparément, pas de changement aveugle des versions.

## Correction apportée

- Aucun test métier, capture ou garde de protection supprimé.
- Les tests sont répartis sur **trois jobs Windows indépendants**,
  de façon déterministe par module : C12, C13 et C14 sur des
  shards différents ; les autres fichiers sont affectés par SHA-256.
- Découverte `unittest` **complète dans chaque job**, sans liste
  d'inclusion manuelle ; un fichier ajouté est automatiquement
  attribué, les imports en échec ne sont pas exclus.
- Protection `MINIMUM_TOTAL_TESTS = 328`, détection des doublons
  et de shards vides, résultats détaillés et tests les plus lents
  dans le récapitulatif GitHub ; quatre tests de contrat de répartition.
- Les captures C6–C14 sont maintenues dans un job Windows distinct,
  en parallèle des suites SQL/Qt. Résultat global du workflow
  `success` uniquement si chaque shard et le job de captures
  réussissent.
- Le checkout ne conserve pas les identifiants Git.
- Une nouvelle exécution sur la branche `qt` remplace une exécution
  antérieure encore en cours pour cette même branche.
- Les dépendances Python et les actions GitHub restent inchangées
  dans cette première correction pour isoler l'effet du parallélisme
  et éviter d'introduire plusieurs variables en même temps.

## Barrières

Aucune donnée familiale réelle, aucun `.nod`, aucun `Config.json`,
aucune connexion réseau ni écriture métier qualifiée. Le code `main`
et `wx` est hors périmètre. Le passage des tests fictifs ne constitue
pas une aptitude à la production.

## Qualification

**EN ATTENTE** de la CI Windows sur le SHA de la correction.
Le nombre attendu passe de 328 à 332 tests après ajout des
quatre tests de répartition. Vérifier chaque shard, la somme
des tests et toutes les captures avant de classer VALIDÉ.
