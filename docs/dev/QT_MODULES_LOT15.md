# Noethys SL Qt — Lot C15 : nouvelles consultations métier

Date : 28 octobre 2026. Branche de développement : \`qt\`.
État initial : **EN QUALIFICATION** tant que le run Windows C15 n'est
pas achevé et vérifié sur son SHA de code. Pas de version distribuable.

## Reprise et vérifications préalables

Branches au lancement du lot :
- \`main\` : \`754242e5357198afc530dc8b0d7ff95ea8c5dc5\`,
- \`wx\` : \`bb2914ab40e715a9ab4b0e824bf62a501a192e0b\`,
- \`qt\` : \`1e1530e1d56a4342d576036929d1d73e318fb01f\`.

La CI éclatée en trois shards a d'abord échoué sur le run
[40656390406](https://github.com/fr4nck/Noethys-SL/actions/runs/40656390406)
à cause de l'exécution du lanceur en fichier (chemin des imports
Python absent). Le commit \`a4fb04adfff03c07ac9eeb9559c54c755659ab48\`
lance le module avec \`python -m tools.qt_ci_test_runner\`, sans
supprimer de test. Le run
[40657764926](https://github.com/fr4nck/Noethys-SL/actions/runs/40657764926)
a confirmé **332 PASS / 0 échec** :
shard 0 = 166, shard 1 = 75, shard 2 = 91 et parcours graphiques
C6–C14 conservés, tous jobs \`success\`.
Ces tests sont réalisés sur des bases inventées, jamais en production.

## Périmètre C15 : quatre grandes rubriques, huit listes supplémentaires

| Nouvelle rubrique Qt | Listes Qt | Références wx |
| --- | --- | --- |
| Échéances d'adhésion | Dates de fin enregistrées ; unités de cotisation | \`UTILS_Adhesions.py\`, \`UTILS_Adhesions_echeances.py\`, \`OL_Liste_cotisations.py\` |
| Attestations | Historique des attestations stockées | \`OL_Attestations.py\` |
| Paramètres d'activités | Unités ; groupes ; catégories tarifaires | \`OL_Unites.py\`, \`OL_Groupes.py\`, \`OL_Categories_tarifs.py\` |
| Effectifs bruts | Comptages des lignes d'inscriptions ; comptages des lignes de consommations | \`DLG_Effectifs.py\`, \`DLG_Stats.py\`, tables \`inscriptions\` et \`consommations\` |

La coque Qt passe **de 14 à 18 entrées** lorsqu'elle active C15.
Les nouveaux modules s'intègrent directement dans la navigation,
les menus, les boutons d'accueil et les liens contextuels.
Les fiches Familles ouvrent les échéances et attestations
par clé \`IDfamille\` exacte ; les unités, groupes, catégories
et comptages ouvrent les inscriptions filtrées par \`IDactivite\` exact.
Retour au module d'origine et sélection conservés.

**Ce que les titres signifient réellement :**
- « Échéances » = date \`cotisations.date_fin\` enregistrée,
  **pas** une proposition d'adhésion, pas une échéance à payer,
  pas une validation de la personne titulaire ni de la couverture.
  \`UTILS_Adhesions_echeances.Proposer/Executer\` n'est **pas appelé** :
  ses invariants de titularité, participation, historique et verrous
  de facturation nécessitent une qualification métier distincte.
- « Attestations » = historique \`attestations\` avec montants
  tels qu'enregistrés ; **aucune génération, émission ou impression**.
- « Paramètres » = valeurs source, aucun calcul de tarif,
  capacité disponible, accès à des prestations ou modification.
- « Effectifs bruts » = \`COUNT(*)\` des lignes inscrites et
  des consommations, plus les valeurs \`statut='ok'\` et
  \`etat='present'\` stockées. Ces compteurs ne sont **pas**
  les effectifs réglementaires, présences uniques, jauges,
  états CAF/AFAS, fréquentations certifiées, ni des soldes.

## Architecture et barrières techniques

\`noethys_qt/catalog_c15_specs.py\` fournit huit contrats
SQL déclarés en dur, alimentant le lecteur
\`noethys_qt/catalog_readonly_core.py\` déjà utilisé en C14.
Aucun nom de table ou colonne n'est construit à partir des entrées.
Le filtrage \`IDactivite\` et \`IDfamille\` est paramétré,
les recherches échappent les caractères LIKE spéciaux,
les plages d'année sont explicites et la limite
d'affichage est **250 + 1 témoin de troncature**.

La coque réutilise \`CatalogHubPage\` et \`CatalogTableModel\`,
avec un filtre d'activité numérique visible uniquement lorsque
le schéma le permet et un lien vers la liste d'inscriptions.
Le lecteur continue à utiliser la connexion existante,
\`PRAGMA query_only=ON\` sur SQLite et les SELECT sans édition.

**Compatibilité et confidentialité :**
- Les fenêtres historiques C12–C14 ouvrent les **14 entrées
  historiques** et leurs fixtures propres, grâce au drapeau
  \`c15_enabled=False\` par défaut. Les requêtes C15 ne
  s'exécutent pas dans leurs jeux fictifs.
- Le lancement natif principal active les entrées C15
  mais n'est **pas qualifié pour une base réelle** et ne
  peut pas être présenté comme release.
- La fixture \`C15FictiveModulesDatabase\` prolonge la fixture
  temporaire C14 après contrôle du chemin et du marqueur ;
  les colonnes et données ajoutées sont inventées.
  Aucun profil Noethys/Connecthys, \`.nod\`, \`Config.json\`,
  donnée familiale réelle ni accès réseau n'est utilisé.
- Toutes les nouvelles interfaces sont **en lecture seule**.
  Les écritures métier restent interdites et aucun moteur
  de calcul financier wx n'est reproduit dans Qt.

## Tests et démonstration

\`tests_qt/test_modules_c15_readonly.py\` : 23 tests nouveaux
sur les huit SELECT, filtres famille/activité exacts,
années historiques, précision monétaire, cas non valides
rejetés avant connexion, comptes bruts (sans sémantique officielle),
liaisons vers les inscriptions et retours, absence d'écriture
et non-régression C13/C14.

Le démonstrateur \`tools/Noethys-Qt-C15-Modules-Demo.cmd\`
ouvre une base éphémère entièrement fictive. La CI exécute
deux parcours \`tools/qt_c15_native_modules_demo.py --smoke\`,
clair 100 % et sombre 150 %, avec **15 vues par profil**
et une comparaison intégrale de la base avant/après.
Les PNG/JSON sont seulement publiés si les captures et
contrôles réussissent.

La protection des trois shards demande désormais un minimum
de **355 tests découverts** (332 antérieurs + 23 C15).
La somme exacte et les résultats Windows C15 doivent
être confirmés avant de classer le lot VALIDÉ.

## Matrice de qualification interbranches

| Branche | C15 | Justification |
| --- | --- | --- |
| \`main\` | NON APPLICABLE à l'interface ; correctifs communs EN ATTENTE | Aucun moteur partagé modifié, historique divergent |
| \`wx\` | NON APPLICABLE à la coque ; correctifs communs EN ATTENTE | Interface historique conservée sans intégration forcée |
| \`qt\` | EN QUALIFICATION sur fixture fictive | Nouvelles listes et tests, CI Windows à vérifier |

La disparition de wxPython du **moteur partagé** reste l'objectif
architectural. C15 ajoute des adaptateurs consultatifs Qt,
il ne prouve aucune parité d'écriture avec wx.
Le projet PostgreSQL est séparé et n'est pas lancé.

## STOP-GATE et suite

Aucune aptitude à la production : droits utilisateurs,
MySQL réel, verrouillage, calcul de cotisation, prévision
d'échéance, attestation générée, statistiques certifiées,
AFAS, comptabilité, migration de base, consommations modifiées,
portail, distribution Windows, consentement ou conservation
de données personnelles. Aucun de ces sujets ne peut être
débloqué par un succès fictif en CI.

Après C15 : rapprocher les interfaces de services communs
sur \`main\`, choisir ensuite les états et le pointage à
reproduire en lecture seule avec qualification de leurs
invariants ; conserver les écritures à part.
