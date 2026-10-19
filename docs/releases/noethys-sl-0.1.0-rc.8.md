# Noethys SL 0.1.0 RC8 — préversion Windows

**Release Candidate de recette, non validée pour la production.**

Cette RC8 actualise la branche **wxPython**. Elle conserve la version interne de compatibilité `1.3.4.4` utilisée pour les migrations et Connecthys ; aucune migration automatique du schéma de données n'est ajoutée.

## Principales nouveautés

- Commandes de repas : comptage suggéré **« sans porc »** à partir d'une réponse individuelle explicitement configurée, sans déduction depuis les informations médicales. Le nombre « sans porc » reste un *dont*, jamais un supplément au total.
- Répartition des enfants de moins de 6 ans et de 6 ans et plus, des **animateurs prenant un repas**, de la direction et des autres adultes. Les repas adultes sont ajoutés **après calcul** aux repas « 6 ans et plus » destinés au restaurateur.
- **Étape de vérification et correction avant PDF ou email**, avec récapitulatif non nominatif par date, site et service. Une modification des quantités après confirmation impose une nouvelle validation.
- PDF restaurateur enrichi d'un récapitulatif : effectifs enfants, adultes détaillés, « 6 ans et plus, adultes compris », « dont sans porc » et total général.
- Le brouillon d'email utilise les **mêmes quantités validées** et la pièce jointe correspondante. Aucun email n'est envoyé automatiquement.
- Avertissement explicite pour les préférences alimentaires non renseignées et blocage des modèles typés invalides.
- **Simulation indicative du nombre d'animateurs** par date/site/créneau et tranche d'âge, distincte du nombre d'adultes prenant un repas.
- Organisation multisite et option facultative de repas directeur/renfort, sans certifier la conformité réglementaire.

## Contenus

- `Noethys-SL-0.1.0-rc.8-Setup.exe` — installateur Windows.
- `Noethys-SL-0.1.0-rc.8-Windows-portable.zip` — archive portable avec dossier `Portable/`.
- `SHA256SUMS.txt` — empreintes SHA-256 des deux binaires.

## Limites et précautions importantes

- **Adhésions / P1 #426** : la création automatique des cotisations demeure **suspendue** pour prévenir les facturations anticipées ; la refonte complète du déclenchement à la clôture ou lors d'une facture anticipée justifiée reste à réaliser. Aucune régularisation automatique des données antérieures.
- **Factures / #428** : le correctif de l'aperçu et du transfert vers l'éditeur d'emails est inclus et testé, mais la recette utilisateur sur poste pilote reste ouverte.
- **Sans porc** : le questionnaire individuel ne conserve pas d'historique daté des réponses. Le calcul consulte la préférence *actuellement renseignée*, pas celle d'une date passée ; une absence de réponse exige un contrôle humain.
- **Multisite** : le dédoublement d'un directeur entre **commandes indépendantes** n'est pas encore empêché automatiquement.
- Les rôles, sites, services et identifiants de question/choix doivent être configurés puis vérifiés avant usage. Un comptage proposé n'est pas une certification réglementaire.
- Les anciens modèles de commandes sans classification peuvent encore fonctionner après avertissement de compatibilité.
- Cette RC8 doit être **essayée sur une copie isolée ou une base fictive** avant tout déploiement. Vérifier les commandes, les PDF et les brouillons d'emails sans envoyer, ainsi que la facturation ; effectuer une sauvegarde vérifiée au préalable.

## Qualification du code

Avant empaquetage, [CI wx](https://github.com/fr4nck/Noethys-SL/actions/runs/39239363460) : **789 tests exécutés, 0 échec, 10 ignorés**. Tests fictifs du comptage SQLite, génération PDF réelle et brouillon email simulé sans réseau. La publication RC8 ne doit intervenir qu'après succès du **build Windows complet**, ses tests MySQL jetables, ses contrôles de démarrage, du Setup, du ZIP portable et des empreintes.

Suivi : [#429](https://github.com/fr4nck/Noethys-SL/issues/429), [#430](https://github.com/fr4nck/Noethys-SL/issues/430), [#426](https://github.com/fr4nck/Noethys-SL/issues/426), [#428](https://github.com/fr4nck/Noethys-SL/issues/428).
