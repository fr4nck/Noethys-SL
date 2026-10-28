# Questionnaire « Type de repas » — préparation contrôlée (wx)

**Portée :** Noethys-SL, branche `wx`, sous-lot de l'issue [#433](https://github.com/fr4nck/Noethys-SL/issues/433). La fonctionnalité est présente dans les sources, **pas nécessairement installée sur les postes ni activée dans leur base**.

## Question individuelle reconnue

Une **seule question à liste déroulante (choix unique)**, visible dans le questionnaire de la **fiche individuelle**, sans réponse par défaut enregistrée dans la question elle-même.

| Réponse | Rôle métier |
| --- | --- |
| Standard | `standard` |
| Sans porc | `sans_porc` |
| Végétarien | `vegetarien` |
| Repas apporté par la famille (sans repas PMSL) | `sans_repas_pmsl` |

Le quatrième choix **ne signifie pas « enfant absent »** : la présence du midi reste celle déduite de la journée/demi-journée et de ses horaires. La commande fournisseur n'inclut pas le panier apporté. Dans les modèles **nouveaux et explicitement opt-in**, l'absence de réponse peut devenir Standard uniquement si la formule couvre le midi et prévoit normalement un repas PMSL ; les anciens modèles conservent leur logique « non renseigné ».

## Avant la première utilisation

1. Installer et qualifier une version wx contenant le lot ; **ne pas lancer les anciens scripts Samantha ou un paquet provisoire #435**.
2. Dans **Paramétrage → Questionnaires**, choisir le type **Individu**.
3. Lire l'état du questionnaire : **PRÊT**, **ABSENT**, **À CORRIGER** ou **vérification impossible**.
4. Si **PRÊT**, ne rien recréer. Si **ABSENT**, cliquer **Préparer « Type de repas »** et **confirmer une fois** la création. La question et les quatre choix sont créés dans **la base actuellement ouverte par Noethys**.
5. Si **À CORRIGER**, ne rien effacer. Une question « Régime repas » incomplète (trois choix), masquée, à choix multiple ou dupliquée nécessite un arbitrage pour protéger les réponses existantes ; aucun rattrapage, doublon ou migration automatique.

Le diagnostic seul est en lecture seule. La préparation est une transaction SQLite `BEGIN IMMEDIATE` ou MySQL `GET_LOCK` + transaction : un deuxième lancement **réutilise les mêmes identifiants**, un échec annule les inserts. Le verrou MySQL couvre les appels à **ce préparateur**, pas une intervention manuelle simultanée dans un autre outil.

## Associer la question au modèle de commande

Dans le paramétrage d'une **colonne de commande de repas** : sélectionner la catégorie de régime appropriée, puis cliquer **Préparer / vérifier « Type de repas »**. La liste déroulante et les **quatre correspondances d'IDs** sont renseignées dans cette page. Renseigner les unités, site, service, plages du midi et l'offre PMSL de cette colonne selon les règles du lot 2C. **Enregistrer normalement le modèle** : préparer la question ne modifie pas silencieusement les anciens modèles.

La famille répond dans le questionnaire individuel du logiciel. L'exposition et la validation de ce champ sur un **portail parent** (Noethysweb / Connecthys) restent un contrat distinct : ne pas les présumer de la seule création locale.

## Ce que le bouton ne fait pas

- Il ne lit ni ne réécrit les réponses des familles, allergies ou PAI.
- Il ne remplace pas une question historique de trois choix, ne crée pas de valeurs par défaut universelles et ne modifie pas les anciennes commandes sans enregistrement explicite.
- Il **n'exonère pas automatiquement** la prestation de restauration sur une facture PMSL. La facturation réelle du panier familial reste sous **STOP-GATE 2C-3** en raison des tarifs forfaitaires, prestations historiques et exceptions datées.
- Il ne modifie pas les heures CAF/AFAS, ni le nombre de présents à midi.

## Qualification

- `tests/test_noethys_sl_repas_questionnaire_setup.py` : 14 contre-épreuves SQLite (idempotence, correspondances, rollback, concurrence locale).
- `tests/test_noethys_sl_repas_questionnaire_dialog.py` : 8 contre-épreuves du menu Questionnaires avec wx simulé.
- `tests/test_noethys_sl_repas_regimes_ui.py` : 5 contre-épreuves supplémentaires du bouton dans le modèle.
- Ces modules sont inclus dans la CI rapide `noethys-sl-fast.yml` sur la branche `wx`.

**La CI automatisée ne remplace pas** une recette interactive de la création dans une base fictive avec le runtime Windows, une vérification MySQL du stockage réel et le contrôle de l'export vers le portail. Aucune donnée PMSL réelle n'est modifiée pendant le développement.
