# Recette utilisateur ciblée — UI-432G (gel pendant la synchro Connecthys)

Objet : vérifier sur le poste réel que l'interface ne se fige plus pendant la
synchronisation **automatique** Connecthys, après le correctif
« synchro Connecthys sans contention GIL prolongée » (branche `wx`).

## Ce qui a été corrigé (et prouvé sur banc)

- Cause démontrée sur banc fictif (SQLAlchemy 2.0.55, version livrée) : la
  préparation de l'export (`Upload_data`) exécutait des secondes de Python pur
  (un objet et un INSERT par ouverture/consommation, puis un commit d'un bloc).
  wxPython rendant le GIL à chaque appel, tout traitement d'interface lancé en
  même temps (ouverture d'une grille, d'une fiche, etc.) était ralenti 5 à 20 fois.
- Correctif : insertion groupée, écriture par tranches dans la même
  transaction, et pause automatique de la synchro dès que l'interface est occupée.
- Mesures banc (1000 familles, 140 722 consommations fictives) : traitement
  d'interface de référence 0,25 s → **max 5,17 s avant, 1,18 s après** ;
  `Upload_data` 12,3 s → 6,3 s ; export identique.
- **Non démontré sur le poste réel** : volumes PMSL, MySQL et durée réelle de
  vos traitements d'interface diffèrent du banc.

## Lanceur

`tools/ui432g_recette.ps1` réalise toutes les vérifications puis lance Noethys
depuis les sources (`.venv` du dépôt, seul interpréteur du poste disposant de
`mysqlclient`), avec `NOETHYS_SL_UI_DIAG=1` pour cette exécution seulement.
Il refuse si : branche différente de `wx`, correctif absent de HEAD, fichiers
suivis modifiés sous `noethys\`, dépendance absente, SQLAlchemy < 1.4,
dateutil ≥ 3, wx < 4.2, code chargé hors du dépôt ou sans les marqueurs du
correctif, autre instance de Noethys ouverte. Journaux dans
`%LOCALAPPDATA%\NoethysSL-recette\UI432G-<date>\` : sortie complète (locale,
à ne pas diffuser) et extrait anonymisé (à transmettre). Le lanceur ne lit ni
ne modifie le profil, les bases ou `journal.log` ; il compare seulement les
empreintes SHA-256 de `Config.json` et `Customize.ini` avant/après.

## Préalables (sans risque pour les données)

1. `git pull --ff-only origin wx` puis vérifier le SHA (au moins celui du
   correctif cité dans l'issue #432).
2. Lancer Noethys normalement avec le diagnostic : `NOETHYS_SL_UI_DIAG=1`.
3. Aucune action particulière sur Connecthys : laisser la synchronisation
   **automatique** se produire comme d'habitude (ne pas forcer de synchro
   supplémentaire pour la recette).

## Scénario

1. Pendant qu'une synchronisation automatique est en cours (icône/état
   « Synchronisation… »), utiliser Noethys comme lors du gel observé :
   traitement des demandes Connecthys, ouverture de la grille de réservation,
   navigation dans les fiches.
2. Noter l'heure approximative de la synchro et des actions.

## Critères d'acceptation

| Critère | Attendu |
|---|---|
| `evenement=retard_boucle` pendant la synchro | aucun retard ≥ 5 000 ms (avant : 5 484 / 21 297 / 23 156 / 22 250 ms) |
| `evenement=blocage_thread ... ne_repond_pas=True` | absent |
| `win32_iconise=True` non demandé | absent |
| Fenêtre principale | reste maximisée, au premier plan sauf action volontaire |
| Synchro | se termine normalement (« À jour ») ; elle peut durer un peu plus si l'interface est très sollicitée (pauses volontaires) |

## Journal à transmettre (sans données personnelles)

Uniquement les lignes `NOETHYS_UI_DIAG` (durées, booléens, `point=fichier.py:fonction:ligne`)
et les lignes Connecthys de durée (`Temps upload_data = …`). Ne pas joindre de
base, de sauvegarde, de nom de famille ni d'adresse email.

## Si un gel persiste

Relever la ligne `blocage_thread` la plus longue : `point`, `point_synchro`,
`veille_retard_ms`, `ne_repond_pas`. Elle indique si le thread wx attend la base
(`GestionDB.py:ExecuterReq`), exécute un code précis, ou si la synchro est en
cause (`point_synchro` dans `UTILS_Portail_synchro.py`).
