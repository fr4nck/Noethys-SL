# Noethys SL Qt — C17 : moteur d'états commun et suivi transversal d'activités

Date : 28 octobre 2026. **C17 VALIDÉ TECHNIQUEMENT sur données fictives.**
Code Qt qualifié : `e3f0f1e01203d2743c12c02fc79e8b4d644ff87f`.
CI Windows [40691411571](https://github.com/fr4nck/Noethys-SL/actions/runs/40691411571)
`completed/success` ; quatre jobs verts, 409 tests Qt PASS et
30 captures C17 validées. Le moteur partagé a également réussi
la CI `main`. **Aucune aptitude à la production.**

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
150 %), **30 PNG + 2 rapports JSON validés** sur une
fixture C16 en `TemporaryDirectory`.  Journal nominatif
délibérément non montré, éditeur d'activité désactivé,
réinitialisation du contexte et comparaison `dump()`
avant/après. Aucune capture issue d'une base privée.

**Qualification Qt C17 : VALIDÉE sur fixtures fictives.**
Code SHA `e3f0f1e01203d2743c12c02fc79e8b4d644ff87f` ;
run Windows [40691411571](https://github.com/fr4nck/Noethys-SL/actions/runs/40691411571)
`completed/success`, les quatre jobs `success`.
Trois shards : **193 PASS (418,72 s)**,
**102 PASS (485,43 s)**, **114 PASS (286,40 s)**,
soit **409 tests Qt, zéro erreur, zéro échec**.
Le job graphique a validé tous les parcours C6–C16
et les marqueurs `C17_OVERVIEW_PASS` sur les deux profils.
Les **12 tests du moteur commun** ont également réussi
dans ce job et dans la CI `main` (run 40689720991).
Les 27 tests C17 nouveaux ne remplacent aucun ancien test.

**Artefact GitHub** `qt-c17-suivi-activites-fictifs`
(ID `12817502111`, **449 963 octets**, SHA-256
`7e5aa5d0548c99ec69a8d9b5f3ef1cb56963d8c5ec9d63f19e6bba3a26c457ff`) :
30 PNG + 2 JSON, `sqlite_unchanged=true`,
`badge_disabled=true` et moteurs communs utilisés.
Expiration annoncée le **11 novembre 2026**.

**Branches observées en clôture** :
`main 53052ed5075c9b8336f380f7db1a1ca2daa5b595`,
`wx 61130f7eecafce9469611d6de267f56f95fccdac`,
`qt e3f0f1e01203d2743c12c02fc79e8b4d644ff87f`
(avant clôture documentaire). `wx` a évolué de façon
indépendante ; la parité avec son moteur de calcul n'est
pas acquise. Un partage de code vérifié n'implique
aucune qualification des écritures ou des états officiels.

## Matrice des branches et barrières

| Périmètre | main | wx | qt |
| --- | --- | --- | --- |
| Contrat d'états pur C17 | VALIDÉ sur SQLite fictif (53052ed) | EN ATTENTE d'intégration et de parité | VALIDÉ sur fixture (e3f0f1e, CI 40691411571) |
| Coque « Suivi transversal » | NON APPLICABLE | NON APPLICABLE | VALIDÉ sur fixture, STOP-GATE production |
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
