# Noethys SL 0.1.0 RC8.1 — correctif P1 adhésions

**Préversion Windows de recette. Ne pas installer directement sur les postes PMSL de production sans recette pilote.**

Cette version conserve toutes les nouveautés de **RC8** (repas sans porc, récapitulatif des adultes, encadrement et PDF/email) et ajoute le parcours de facturation des adhésions qui avait été développé sur `main` mais **omis de la branche Windows `wx` lors de RC8**.

## Correctif P1 #426

- La saisie et la sauvegarde de réservations ne créent plus automatiquement de cotisations : **le coupe-circuit reste actif**.
- Dans l'assistant **Génération de factures**, sur la première étape lorsque les prestations « cotisation » sont incluses, les participations passées éligibles sont recherchées en lecture seule avant l'aperçu. Les séances futures et les absences sont exclues.
- Le système présente le nombre de cotisations proposées et leur montant, puis exige une **confirmation explicite**. Il est possible de continuer sans les créer ou de revenir aux paramètres.
- Après accord, le moteur revérifie sous verrou transactionnel l'état de la participation, la date, le titulaire, le paiement et les adhésions existantes. Une modification détectée interrompt la préparation ; les cotisations admises sont créées avec leur prestation et historique.
- Lors d'une facturation mensuelle terminée, la date comptable est bornée à la fin de la période ; lors d'une facture anticipée dans le mois, elle est bornée à la date du jour. La **date de début de validité de l'adhésion** reste celle de la première participation éligible.
- Les cotisations créées avant l'aperçu apparaissent dans les prestations de facturation, et ne sont jamais ajoutées après confirmation de l'aperçu.

## Audit des anciennes anomalies

Un service `UTILS_Adhesions_echeances.AuditerCotisationsAnticipees` permet un inventaire **en lecture seule** des cotisations automatiques suspectes créées notamment par RC7. Il signale séparément les lignes déjà **facturées ou ventilées**, et ne supprime ni ne modifie aucun enregistrement. Les éventuelles régularisations doivent être validées et tracées individuellement.

## Limites non levées

- L'audit des écritures anciennes n'a pas été exécuté sur la base PMSL. Il n'y a donc **aucune régularisation automatique** des anomalies RC7.
- Les cotisations déjà facturées ou réglées nécessitent une procédure comptable de régularisation ou d'avoir, pas une suppression SQL.
- La création par « clôture » est actuellement disponible au **parcours de facturation explicite**. Il n'existe pas de tâche automatique mensuelle indépendante de l'assistant.
- La validation sur poste utilisateur Windows et la qualification comptable des cas réels restent indispensables avant le déploiement général.
- La version de compatibilité interne `1.3.4.4` reste inchangée ; **aucune migration SQL implicite**.
- Les limites métier de RC8 relatives aux repas et aux commandes multisites restent applicables.

**Suivi :** [P1 #426](https://github.com/fr4nck/Noethys-SL/issues/426). Les binaires RC8 publiés précédemment restent immuables.
