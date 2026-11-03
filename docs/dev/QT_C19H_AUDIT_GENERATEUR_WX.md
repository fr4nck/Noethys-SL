# Noethys-SL Qt — C19h : contre-examen du générateur de factures wx

Date : 03/11/2026 · Branche `qt` · Ticket [#440](https://github.com/fr4nck/Noethys-SL/issues/440).

**Statut : contre-épreuves sur fonctions historiques wx et tables SQL
ENTIÈREMENT INVENTÉES ; ne doit jamais émettre une facture réelle.**

## Preuves dans le code source historique

- `noethys/Dlg/DLG_Factures_generation_selection.py`,
  `Panel.SauvegardeFactures`, lignes 214–300 : le prochain numéro AUTO
  est déterminé par `SELECT MAX(numero) FROM factures WHERE IDprefixe...`,
  puis incrémenté ; la lecture utilise une connexion ouverte et refermée
  AVANT une seconde connexion qui insère l'en-tête et affecte
  `IDfacture` aux prestations. Il n'y a pas de séquence ni de
  verrou dans ce passage. En mode manuel, la validation du numéro
  précède également l'enregistrement.
- `noethys/GestionDB.py`, `DB.ReqInsert` et `DB.ReqMAJ`
  (lignes 338 et 448 environ) : leur argument `commit` vaut
  **`True` par défaut**. Une insertion peut donc être validée
  indépendamment des modifications suivantes. `ReqMAJ` attrape les
  erreurs SQL et les **affiche sans les relancer** : son appelant ne
  reçoit ni exception ni décompte de lignes effectivement modifiées.
  La fonction de génération wx n'emploie pas `commit=False`
  et ne vérifie pas la réussite des affectations de prestations.
- `noethys/Data/DATA_Tables.py` : `factures.numero` est un `BIGINT`,
  `IDprefixe` un entier nullable ; `DB_INDEX` ne déclare pas de
  clé unique `(IDprefixe, numero)`. **Ce constat ne prouve pas**
  l'absence d'un index ajouté par une migration ou directement
  sur une base déployée. Une contrainte `UNIQUE(prefixe,numero)`
  nullable ne suffirait de toute façon pas à interdire les
  doublons avec `IDprefixe IS NULL` dans MySQL.
- `noethys/Utils/UTILS_Decimal.py`, `FloatToDecimal` : la conversion
  utilise `decimal.Decimal("%.2f" % montant)`. L'option
  `plusProche=True` appelle `quantize` sans réaffecter son
  résultat. La facture wx repasse les totaux calculés
  en `float(total)`, `float(regle)`, `float(solde)`; le
  dictionnaire historique déclare ces champs en **FLOAT**.
  Les modes d'arrondi et le stockage monétaire exact doivent donc
  être qualifiés avant tout portage.
- `noethys/Utils/UTILS_Facturation.py`, `GetDonnees` : le calcul
  exclut une prestation de catégorie `cotisation` lorsque
  `inclure_cotisations_si_conso` est activé et que le
  compte payeur n'a pas de consommation éligible dans le périmètre.
  Les champs `forfait_date_debut` et `forfait_date_fin` sont
  utilisés dans la représentation des prestations. Ces
  règles observées ne constituent **pas** un calcul tarifaire
  exhaustif ni une équivalence de facturation.

## Expériences C19h

1. `tests_mysql/test_c19h_wx_original_semantics.py` extrait par
   **AST les véritables fonctions** `SauvegardeFactures`, `ReqInsert`,
   `ReqMAJ` et `FloatToDecimal`, sans importer wx, GestionDB ni
   aucune configuration PMSL. Il exécute ces fonctions contre
   **SQLite `:memory:`**, avec l'interface remplacée par des
   objets artificiels. Un trigger injecte une erreur sur le
   deuxième rattachement : le banc doit identifier la facture
   déjà validée et la première prestation liée, tandis que la
   seconde demeure sans facture alors que le générateur signale
   un résultat de succès. L'étude inclut un entrelacement
   déterministe de deux `MAX(numero)+1` et la vraie condition
   de sélection des cotisations. **14 tests** prévus.
2. `tests_mysql/test_c19h_mysql_wx_replay.py` reprend les
   **mêmes fonctions wx extraites par AST**, en utilisant leur
   branche MySQL originale sur les tables synthétiques
   `factures` et `prestations`, dans la base
   `qt_c19h_lab` sur **127.0.0.1:33069**. Le connecteur
   exige un runner GitHub Actions `fr4nck/Noethys-SL`,
   `refs/heads/qt`, les paramètres CI exacts et le marqueur
   `C19H_WX_MYSQL_FAKE_ONLY_20261103`.
   La base est initialement vide ; aucune lecture d'un profil
   local ou ouverture vers `SERVEURPMSL` n'est possible.
   Un trigger simule un échec du deuxième lien ; des threads
   synchronisés rejouent deux générateurs en parallèle sur
   les mêmes prestations. Un autre oracle vérifie qu'une
   contrainte unique dont le préfixe est `NULL` peut tolérer
   des numéros identiques. **8 tests** prévus par moteur MySQL.

## Portée et limites des preuves

Ce laboratoire **n'exécute PAS le programme wx intégral**, ni
`UTILS_Facturation.Facturation.GetDonnees` : la sélection des
prestations, les tarifs, les forfaits et les droits sont fournis
par les fixtures. Ce sont les **vraies fonctions d'enregistrement
et de conversion** qui sont extraites/exécutées. Les tables sont
des sous-ensembles fictifs du schéma ; les incidents observés
sont des preuves de possibilités au niveau de ces méthodes et
de ces schémas, pas un comptage d'anomalies PMSL.

Aucun correctif n'est appliqué au moteur wx de production.
Même si les oracles reproduisent un défaut, C19h **ne désactive pas**
le générateur historique et **n'active aucune facturation Qt**.
Les suites C19g et C19f sont des prérequis indépendants, déjà
qualifiés sur MySQL 5.7/8 ; la suite Qt C19e
[584/584](https://github.com/fr4nck/Noethys-SL/actions/runs/41686340299)
reste inchangée.

## Livrables et suites

- Recette Windows + Linux, pure bibliothèque standard :
  `.github/workflows/qt-c19h-wx-source.yml`.
- Recette MySQL éphémère 5.7.44 + 8.0.40 :
  `.github/workflows/qt-c19h-mysql-replay.yml`.
- Avant tout développement de facturation réelle : définir une
  allocation **transactionnelle** et non ambiguë des numéros
  (y compris préfixe nul), une vérification des droits/périodes
  **à l'instant du commit**, un contrôle du nombre de prestations
  effectivement liées, des reprises idempotentes, puis des
  règles monétaires/arrondis/forfaits assorties d'oracles métier.
- Toute adaptation du schéma réel, même le passage d'un champ
  `FLOAT` vers `DECIMAL`, doit faire l'objet d'une migration
  distincte, évaluée sur base isolée, sans modification silencieuse
  de données historiques.

**STOP-GATE :** aucun accès PMSL, aucune création de facture réelle,
aucune modification de `main`/`wx`, aucune publication Qt 0.2.0.
Le diagnostic de sauvegarde i5-10400 (#437) reste différé.
