# Noethys SL Qt — C17 : moteur d'états commun et suivi transversal d'activités

Date : 28 octobre 2026. **Qualification Qt : EN ATTENTE du run
Windows C17.** La qualification du moteur pur sur `main` a réussi.
Aucune étape n'autorise une utilisation sur les bases des familles réelles.

## Périmètre et provenance

Prévol GitHub avant C17 :
- `main 647483e55914d845dd83ed89dc4dba5c7686c421`
- `wx d01566118f66775620d3df5e888bc50abfd4ecef`
- `qt fe827e8771de116eac7ca34efd845b7ddd0b039d`

Les trois branches ont des histoires **divergentes** ; elles ne
doivent pas être fusionnées automatiquement. Les changements Qt
postérieurs à C16 (administration des corrélations `session_uid`)
sont conservés, sans conflit de fichier avec ce lot. Aucun
force-push, aucune branche nouvelle, aucune modification de
`wx`, aucune migration de base.

**Socle de départ** : C16 validé sur SHA
`b8fd944327878590076032bfaa797a14a677e470`
(run [40664569734](https://github.com/fr4nck/Noethys-SL/actions/runs/40664569734),
382 tests PASS et 36 captures fictives). Clôture documentaire C16
`e5a0be5ad122cb737cc2d489345f5ef4fd6448a0`.

## Livrable 1 — extraction du moteur pur dans le socle commun

`noethys/Utils/UTILS_Consumption_StateCounts.py` est un service
**sans dépendance à wx, Qt, GestionDB, réseau ou fichiers utilisateurs**.
Il porte désormais :
- Référentiel `STATES` et `OTHER` partagé, sept catégories
  de consultation en incluant `__autres__` ;
- contrat `stored-consumption-state-counts/1` ;
- `validate_state_selection` : année, activité et codes ;
- `build_state_summary_statement` : un unique `SELECT COUNT(*)`
  groupé par état, placeholders `?` / `%s`, plage annuelle
  `[01-01,01-01 N+1[` et activité exacte, sélection vide
  sans requête ;
- `make_status_summary` : résultat typé, catégories absentes
  explicitement à zéro, rejet des doublons, des états inattendus
  et des comptages invalides.

Ce contrat a été publié sur `main` au commit
[`53052ed5075c9b8336f380f7db1a1ca2daa5b595`](https://github.com/fr4nck/Noethys-SL/commit/53052ed5075c9b8336f380f7db1a1ca2daa5b595).
La CI [40689720991](https://github.com/fr4nck/Noethys-SL/actions/runs/40689720991)
est `completed/success`, jobs Syntaxe Linux et contrats
Windows verts. **12 nouveaux tests de moteur partagé PASS** dans
le job syntaxe : SQLite fictif, SELECT-only, codes NULL/inconnus,
années, placeholders et entrées malformées.
Ce succès ne qualifie pas les calculs officiels wx/AFAS.

Sur `qt`, `consumptions_core.py` réexporte les mêmes
constantes de code, sans copie. `consumptions_status_core.py`
ne garde que la connexion consultative SQL et délègue
requêtes, normalisation et résultat au module commun.
`consumptions_status_ui.py` reste la carrosserie Qt.
Il n'y a donc plus **de deuxième implémentation du moteur
d'états C16 dans Qt** ; les tests d'identité des fonctions
et types empêchent de réintroduire une copie divergente.

`wx` ne consomme pas encore ce contrat : **EN ATTENTE**
de la comparaison complète du calcul historique des états
et des droits métier. Ne pas substituer ce lecteur brut à un
calcul officiel ni réorganiser les écritures du pointage.

## Livrable 2 — Suivi transversal des activités dans la coque Qt

Nouvelle **23e entrée** en C17 lorsque `c17_enabled=True` :
`Suivi transversal des activités`. Le tableau réutilise
`CatalogRepository` / `CatalogHubPage`, sans formulaire
d'édition ni dépendance wx. Il regroupe les valeurs stockées
pour chaque `IDactivite` :
- lignes d'inscriptions, dont `statut='ok'` (technique) ;
- lignes de consommations, dont `etat='present'` (technique) ;
- ouvertures, événements et tarifs enregistrés.

Ces compteurs **ne sont pas des effectifs uniques, une capacité
disponible, un taux de présence, une preuve de facturation
ou un bilan CAF/AFAS**. Ils sont tous périodes confondues
et ne doivent pas être affichés comme chiffres réglementaires.

SQL : sous-requêtes `COUNT(*)` corrélées par clé SQL exacte,
sans multiplication de lignes due à des jointures,
recherche littérale échappée, filtrage `IDactivite`,
plafond **250 résultats + 1 témoin de troncature**.
Aucun total monétaire et aucune interprétation de tarification.

Dans le tableau, sélectionner une ligne par clic permet
d'ouvrir directement :
- les **inscriptions** enregistrées de l'activité ;
- le **planning** (ouvertures/événements) ;
- les **tarifs enregistrés** ;
- les **états des consommations** du moteur commun.

Les quatre passages transmettent l'**ID numérique de l'activité**
enregistrée, jamais son libellé ; ils sont réversibles et
préservent la sélection du tableau. Le retour par menu global
réinitialise les filtres d'activité afin de ne jamais présenter
un sous-ensemble précédent comme un état général.
Seules les destinations explicitement autorisées
`planning`, `tariff_records`, `consumption_reports` et
le lien inscription natif sont accessibles. Les modules
de badgeage restent désactivés dans le démarrage normal.

## Jeux et tests C17

`tests_qt/test_c17_shared_activity_overview.py` :
**27 tests supplémentaires**, dont vérification que l'UI
utilise exactement le **même objet Python** pour les constantes,
les classes et fonctions du moteur partagé, et non une copie.
Comptages sur les fixtures intégralement inventées C16,
cas d'activité vide, validation SQL avant connexion,
vérification du dump SQLite inchangé, navigation Qt et
retours, protection du journal, non-régression C13/C15/C16.

Tests C16 conservés mais bornés sur la photographie exacte
des domaines C16 pour ne pas inclure accidentellement le
nouveau domaine C17. Le garde de découverte est porté
de **382 à 409 tests Qt** ; le nouveau fichier est affecté au
shard Windows 1 sans supprimer les tests anciens.

`tools/qt_c17_native_demo.py` et
`tools/Noethys-Qt-C17-Demo.cmd` :
**deux scénarios de 15 étapes** (clair 100 % et sombre
150 %), 30 PNG + 2 rapports JSON **attendus** sur une
fixture C16 en `TemporaryDirectory`. Journal nominatif
délibérément non montré, éditeur d'activité désactivé,
réinitialisation du contexte et comparaison `dump()`
avant/après. Aucune capture issue d'une base privée.

**Qualification Qt C17 : EN ATTENTE** de la CI Windows
sur le SHA exact, des trois shards (409 tests attendus),
de la recette graphique C6–C17 et des deux marqueurs
`C17_OVERVIEW_PASS`. Ne pas cocher validé avant
d'avoir contrôlé ces éléments.

## Matrice des branches et barrières

| Périmètre | main | wx | qt |
| --- | --- | --- | --- |
| Contrat d'états pur C17 | VALIDÉ sur SQLite fictif (53052ed) | EN ATTENTE d'intégration et parité | EN QUALIFICATION |
| Coque « Suivi transversal » | NON APPLICABLE | NON APPLICABLE | EN QUALIFICATION |
| Moteurs de mutation, pointage, facturation | INCHANGÉS par C17 | INCHANGÉS par C17 | INCHANGÉS par C17 |

**STOP-GATE** : aucune habilitation réelle, aucun état CAF/AFAS,
aucune règle de prise en charge ou de facturation, aucun dossier
familial réel ni base `.nod`, aucune migration MySQL/PostgreSQL,
aucun transfert de logique d'écriture, aucun accès au journal
nominatif, aucune livraison Windows utilisable en production.

Un test sur SQLite fictif ne démontre pas la parité de calcul
avec les traitements wx historiques ni l'aptitude du produit
à son exploitation réelle.

## Suite C18

Intégrer les autres modules manquants de Noethys en réutilisant
les services communs déjà qualifiés, puis documenter par couples
wx/Qt leurs entrées/sorties et préconditions. Le déplacement
de la logique de tarification et de titulaires restera subordonné
à un audit de parité dédié, distinct de la coque.
