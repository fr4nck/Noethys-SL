# Noethys SL Qt — C16 : planning, tarifs, états sélectionnables et journal protégé

28 octobre 2026 — branche canonique `qt`.
**Statut final : VALIDÉ TECHNIQUEMENT sur données fictives uniquement.**
Code testé : `b8fd944327878590076032bfaa797a14a677e470`.
CI Windows [40664569734](https://github.com/fr4nck/Noethys-SL/actions/runs/40664569734)
`completed/success`, aucune aptitude à la production.

## Origine et non-régression entre branches

SHA à l'ouverture du lot :
- `main 4a663fc4f1a0c07da6882e764a85cfb28bd4e2ec`
- `wx 883bf008119bd729fdb238849344fbe6663e68d7`
- `qt ffa1657d770db035ffa26b97c226b57734533eda`

L'ancêtre Qt C15 validé est `6eea2cada4aae67622df5dbd4e0e0f72c23dc0a9` :
CI Windows [40659547120](https://github.com/fr4nck/Noethys-SL/actions/runs/40659547120),
**355 PASS/0 FAIL**, captures C6–C15 PASS, 30 PNG/2 JSON C15.
Une mise à jour indépendante du moteur commun de pointage
(`ffa1657d`) est déjà présente sur `qt` au démarrage C16 ;
elle ne doit pas être écrasée. Aucun merge global, ni suppression,
ni copie aveugle de fichiers de `main`/`wx`.

## Périmètre C16 : 4 modules de plus

| Entrée Qt | Contenu réellement affiché | Source historique |
| --- | --- | --- |
| Planning / événements | Ouvertures et événements enregistrés | `DLG_Ouvertures.py` : tables `ouvertures`, `evenements` |
| Tarification enregistrée | Tarifs et lignes tarifaires, valeurs source | `DLG_Liste_tarifs.py`, `CTRL_Tarification_calcul.py` |
| États des consommations | `COUNT(*)` des consommations par codes d'état sélectionnés | `noethys_qt/consumptions_core.py` et `consumptions_calendar_core.py` |
| Journal de badgeage | Actions de badgeage déjà stockées | `OL_Badgeage_log.py` ; accès **bloqué sur profil normal** |

La coque C16 étend 18 à **22 entrées** lorsque `c16_enabled=True`,
dont une entrée de journal désactivée tant que les droits et la
confidentialité ne sont pas vérifiés. Elle conserve 14 entrées
historiques C12/C14 et 18 entrées C15 sur les anciennes fixtures,
sans les tables C16. En profil normal :
`c16_enabled=True`, `badge_logs_enabled=False`.
Seul le démonstrateur à données inventées active
`badge_logs_enabled=True`.

Les listes ne disposent d'**aucun mécanisme d'écriture**.
Elles utilisent le connecteur SELECT-only C14, limites 250 + 1,
requêtes statiques, filtres SQL par ID exact et plages annuelles
paramétrées. Les liens depuis Planning/Tarifs vers les inscriptions
réutilisent `IDactivite`, jamais un nom approximatif.
Les montants, catégories et QF enregistrés ne sont ni
recalculés ni certifiés. Les saisies de badgeage ne sont
ni modifiées ni purgées par Qt.

## États des consommations sélectionnables

Le nouveau service pur `consumptions_status_core.py`, sans
import wx ni PySide6, **réutilise les sept catégories** de
`consumptions_core.py` :
`reservation`, `attente`, `refus`, `present`,
`absentj`, `absenti`, `__autres__`.
La dernière regroupe les codes historiques non reconnus
et les NULL, sans les ignorer. Le widget Qt expose sept
cases à cocher **directement** et deux commandes Tout/Aucun,
un filtre par année et un filtre par ID d'activité exact.

Le service exécute une seule requête de regroupement SQL
paramétrée et **bornée à sept catégories**, sans lire la
liste paginée de 300 consommations. En sélection vide,
**aucune connexion SQL n'est ouverte**. Le total est la
somme exacte du nombre de lignes `consommations` de
l'année/activité et des états choisis. Aucun total
financier n'est calculé.

**Limite réglementaire obligatoire** : le nom
« États des consommations » correspond ici à un
**aperçu technique brut**, pas à l'état officiel CAF/AFAS,
aux heures facturables, aux présences uniques ni à une
attestation des jours réalisés. Le composant ne déclenche
pas les services d'écriture ou de rapprochement et n'est
pas qualifié pour produire une déclaration réelle.
Le problème d'interface wx des états ne peut pas être
déclaré corrigé par cette nouvelle vue Qt.

## Décloisonnement du moteur — orientation C16

Ce chantier réutilise `CatalogRepository` et
`ConsumptionRepository` déjà présents, tandis que le
service de regroupement est indépendant du framework
graphique mais encore hébergé dans `noethys_qt`.
Cela constitue une **première séparation interne des
calculs de présentation**, pas une extraction effective
dans `main`. Avant de rendre ce service commun à wx et Qt,
il faudra fixer le contrat de valeurs et les droits sur
`main`, comparer les SQL et les règles avec les historiques
wx (particulièrement l'état officiel des consommations),
puis ajouter des tests de parité sur fixtures communes.
Aucune règle d'écriture n'a été déplacée et la base
PostgreSQL n'est pas concernée.

## Validation sur données fictives

`tools/qt_c16_fixture.py` étend la base inventée C15
dans le même `TemporaryDirectory` après contrôle des
marqueurs successifs C8, C13, C14, C15. Les colonnes
et valeurs C16 sont exclusivement synthétiques :
ouvertures, événements, tarifs, lignes, badgeage et
quelques consommations 2027 dont états NULL/inconnus.

`tests_qt/test_modules_c16_readonly.py` ajoute
**27 tests** : tables exactes, ID d'activité, dates,
précision décimale, SQL SQLite/MySQL paramétré,
états multiples, valeurs inconnues, absence d'accès
à SQL sans sélection, lien vers les inscriptions,
drapeau de confidentialité badgeage, lecture seule
et vérification de la base `dump()` inchangée.
Garde de découverte : **382 tests** (355 C15 + 27 C16).
Répartition prévue : trois shards Windows, sans perte
de couverture ; les tests C15 et C16 sont équilibrés
sur les shards 2 et 0.

Démonstration `tools/Noethys-Qt-C16-Demo.cmd` ;
`tools/qt_c16_native_demo.py --smoke` sur profils
clair 100 % et sombre 150 % :
**18 captures par profil, 36 PNG + 2 JSON** attendus,
plus tous les parcours C6–C15 inchangés. Vérification
du dump de la fixture avant/après la navigation.

**CI C16 vérifiée le 28/10/2026** sur le code SHA
`b8fd944327878590076032bfaa797a14a677e470` :
[run Windows 40664569734](https://github.com/fr4nck/Noethys-SL/actions/runs/40664569734)
`completed/success`, **382 tests réussis, 0 erreur, 0 échec**
sur les trois shards (193 tests en 343,42 s ; 75 tests
en 141,32 s ; 114 tests en 425,21 s). Quatre jobs
Windows conclus `success`, dont les captures C6–C16.

**C16_MODULES_PASS** sur les profils clair 100 % et sombre
150 % : **18 étapes chacun**, 36 PNG + 2 JSON,
sept cases de statut testées par clic, Tout/Aucun,
`sqlite_unchanged=true`, cinq tables C16 et aperçu
`COUNT(*)` par états. Les parcours graphiques
C12/C13/C14/C15 restent PASS sur leurs fixtures fictives.
Artefact `qt-c16-planning-etats-fictifs`, ID **12805421531**,
523 363 octets, SHA-256
`57c77b491c879e6ba7f9ae2f41a7965d538afaac500f2c0483fa5ecf141d638c`,
expiration GitHub annoncée le 11 novembre 2026.

**SHA observés après CI** :
`main 1179e5799cc1ac6a9a7557896751069bfc7feb7f`,
`wx 82cc9a641af40f9ca6ef7831f988a631ace33a14`,
`qt b8fd944327878590076032bfaa797a14a677e470`
(avant publication documentaire finale).
Les changements communs sur `main` et `wx` ont avancé
indépendamment. Toute parité interbranches métier,
permissions, MySQL réel et statut prêt à publier
demeurent **EN ATTENTE**. Le journal sensible n'est
pas activé hors fixture.

## STOP-GATE

- Écritures des consommations, pointages, adhésions,
  facturation, paiements, tarifs, ouvertures et événements
  non qualifiées, donc interdites par C16.
- Journal nominatif non accessible depuis le lancement
  normal avant preuve des habilitations et de la politique
  de conservation. Son rendu sur des noms fictifs ne
  qualifie pas les permissions en production.
- Données familiales réelles, `.nod`, `Config.json`,
  comptes MySQL, sauvegardes, exports comptables,
  attestations, AFAS, portail et packaging exclus.
- Succès des tests fictifs ne signifie jamais
  « prêt à publier » ni « utilisable en production ».

## Suite proposée

C17 : audit de parité du moteur pur (référentiels
d'état, titularité, tarification, contrôles d'accès)
avant extraction dans `main` et adaptation wx/Qt.
Continuer l'intégration des modules manquants dans
la coque sans sacrifier la séparation du moteur.
