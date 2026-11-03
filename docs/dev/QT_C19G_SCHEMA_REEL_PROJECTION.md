# Noethys-SL Qt — C19g : projection des vraies tables sur MySQL fictif

Date : 03/11/2026 · Branche `qt` · Ticket [#440](https://github.com/fr4nck/Noethys-SL/issues/440).

**Statut : expérience autonome de lecture, aucune facturation ni écriture métier.**

## Pourquoi C19g

Le banc C19f validé à 24/24 tests sur MySQL 5.7 et 8.0 emploie des
tables fictives préfixées `c19f_` et des montants textuels. C'est une
preuve des propriétés de son propre schéma, **pas** des tables de Noethys.

Une lecture du dictionnaire historique
[`noethys/Data/DATA_Tables.py`](../../noethys/Data/DATA_Tables.py),
blob Git `6b25f2584382812493905a9fa9e968ffa7fcad99`, et du générateur
[`DLG_Factures_generation_selection.py`](../../noethys/Dlg/DLG_Factures_generation_selection.py)
met en évidence :

- `prestations` possède directement `IDprestation`, `IDactivite`,
  `IDindividu`, `IDfamille`, `IDcompte_payeur`,
  `IDfacture`, `forfait`, les dates de forfait et `montant`.
- `factures` est une table distincte, avec `IDfacture`, `numero`,
  `IDcompte_payeur`, `total`, `regle`, `solde` et des dates.
  Le générateur wx insère une facture puis affecte son identifiant aux
  prestations retenues.
- `comptes_payeurs`, `inscriptions`, `consommations`,
  `ventilation` et `periodes_gestion` portent les rattachements et
  restrictions à contrôler avant une opération de facturation.
- **Problème de précision important** : les champs monétaires
  `prestations.montant`, `factures.total/regle/solde` et
  `ventilation.montant` sont déclarés en **`FLOAT`**, et non en
  `DECIMAL(12,2)`. Il serait faux de garantir un montant au centime,
  un arrondi fixe ou la conservation exacte de `12.005` en partant
  seulement de ces types. **Aucune correction de données ou migration
  de type n'est autorisée par C19g.**

## Projection source, pas copie des données de production

`experimental/qt_c19g_schema_lab/schema_contract.py` :

- lit `DB_DATA` par `ast.parse` + `ast.literal_eval`, **sans importer
  ni exécuter le code Noethys** ;
- exige, sur 7 tables et leurs 47 colonnes retenues, les noms et types
  déclarés ; toute dérive bloque la recette ;
- génère un **sous-ensemble de DDL InnoDB** avec ces types, seulement
  pour un MySQL fictif ; aucun index ni contrainte de clé étrangère
  supplémentaire n'est présumé ;
- ne prétend pas reproduire les autres colonnes, les index, les
  migrations, les personnalisations ou le schéma réellement présent sur
  un poste PMSL.

`experimental/qt_c19g_schema_lab/mysql_projection.py` :

- ne se connecte que sur le runner **GitHub Actions / dépôt
  fr4nck/Noethys-SL / branche qt**, avec les valeurs exactes
  `127.0.0.1:33068`, `qt_c19g`, base `qt_c19g_lab` et garde
  `C19G_DISPOSABLE_MYSQL=yes` ;
- **refuse une base non vide** à l'initialisation ; crée les sept tables
  de projection et le marqueur `c19g_marker`, uniquement avec des
  identités et données fictives ;
- ne réinitialise que les lignes des tables explicitement autorisées
  après vérification du marqueur et de la liste complète des tables ;
  ne contient ni `DROP DATABASE`, ni profil PMSL, ni restauration ;
- inspecte une sélection exacte de prestations avec
  **`START TRANSACTION READ ONLY`**, relit marqueur et rattachements
  `prestations` → `comptes_payeurs`/`factures`, vérifie chaque
  `consommations` → `inscriptions`, compte les `ventilation` sans
  produits cartésiens, signale les périodes verrouillées ;
- ne multiplie jamais le montant d'une prestation par ses
  consommations, ne calcule pas de facture et impose
  `SourceAudit.executable=False`.

**Différence assumée avec C19f** : les lectures C19g confrontent les
colonnes et types source, mais le banc transactionnel C19f reste le
seul endroit où des factures *purement inventées* sont insérées. Le
lien entre transactions C19f et véritable modèle métier Noethys n'est
**pas encore qualifié**.

## Oracles et CI

- 10 tests du dictionnaire source, du drift de types, des champs exacts
  et de l'absence d'exécution de `DATA_Tables.py`.
- 17 tests MySQL de la projection, dont conservation d'une seule
  prestation malgré deux consommations, une ventilation distincte,
  factures déjà liées, incohérences famille/payeur/individu/activité,
  montants flottants, périodes verrouillées, marqueur et une tentative
  d'écriture refusée à l'intérieur d'une transaction `READ ONLY`.
- Workflow distinct `.github/workflows/qt-c19g-schema-isolated.yml`
  : matrice **MySQL 5.7.44 et 8.0.40** dans des conteneurs éphémères,
  **27 tests attendus par serveur**, installation de PyMySQL + RSA
  seulement dans les runners. Les tests ne sont pas ajoutés à
  `tests_qt` : le seuil de 584 tests graphiques reste inchangé.

**Résultat C19g confirmé :** le run
[41694695411](https://github.com/fr4nck/Noethys-SL/actions/runs/41694695411)
a terminé **2/2 jobs en succès** sur le commit de code
`332967f5144d`. **27/27 tests PASS sur MySQL 5.7.44**
(0,293 seconde) et **27/27 PASS sur MySQL 8.0.40**
(0,558 seconde), sans erreur ni échec. La transaction
`READ ONLY` interdit l'insertion de prestation et les liens
entre familles, consommations, factures et ventilations restent contrôlés
dans le schéma fictif. Ce résultat ne qualifie ni le schéma présent en
production ni une facturation réelle.

Le lot C19e est validé 584/584 tests
[ici](https://github.com/fr4nck/Noethys-SL/actions/runs/41686340299),
et C19f est validé 24/24 sur chaque version
[ici](https://github.com/fr4nck/Noethys-SL/actions/runs/41688434727).

## Suites ouvertes

1. Comparer les contraintes et index effectivement utilisés par
   `GestionDB`, puis confronter les effets de la génération wx dans
   une base **totalement fictive** ; ne pas supposer son atomicité.
2. Expliciter l'arrondi, la précision et les règles tarifaires au moyen
   d'oracles wx, notamment les forfaits et prestations partagées.
3. Étudier les droits et périodes **dans les transactions réelles**
   sous isolation, avec concurrence sur des prestations et comptes
   payeurs distincts, sans accès à la production.
4. Ne préparer un port métier Qt qu'après ces qualifications et une
   recette de restauration isolée.

**STOP-GATE :** aucune donnée PMSL, aucune migration, aucun changement
de `main`/`wx`, aucun déploiement ou droit de facturer. L'incident
sauvegarde i5-10400 (#437) reste différé.
