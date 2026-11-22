# Noethys-SL / Statistiques d'assiduite - jalon 1

Date : 11 novembre 2026

Statut : **CANDIDAT NON FUSIONNE**, hors des bases PMSL et de la RC.

## Constat sur la source wx

- `consommations.etat`: `present`, `absentj`, `absenti`, `reservation`, `attente`, `refus`.
- `CTRL_Grille.Sauvegarde()` supprime physiquement les consommations via `DELETE`.
- `historique.IDcategorie=10` conserve une trace textuelle regroupee des suppressions, et non un journal structure de vraies annulations.
- **Aucun nombre historique d'annulations n'est invente.** `annulations.nombre=None` dans la sortie.

## Implementations

- Un seul SELECT SQL (lecture seule) sur les consommations selectionnees.
- Periodes libres : annee calendaire, fractions d'annee et plusieurs annees.
- Ventilation annuelle, mensuelle, par activite, par site uniquement avec mapping valide.
- Journnees-enfants distinctes par enfant et date ; lignes de consommations conservees comme un indicateur distinct.
- Journees mixtes exclues du denominateur du taux d'absence, avec une categorie propre.
- Les reservations non pointees ne deviennent jamais des absences ni des annulations.
- Distinction absences justifiees / injustifiees, categorie vide et controle des etats inconnus.
- Exports aggreges CSV, XLSX et ZIP par site, sans identifiants individuels ni montants.
- Aucun recalcul de facturation, aucune migration et aucune mutation de donnees.

## Limites et qualifications restantes

- Avant mapping de sites, les statistiques par site sont volontairement vides.
- Sans liste d'unites d'accueil approuvee, les totaux de lignes incluent potentiellement repas et autres unites ; les journees-enfants restent dedoublonnees.
- Les annees partielles sont affichees comme partielles et non comparees comme des annees completes.
- Les annulations fiables necessiteront une trace structuree distinguant annulation et correction de saisie, avec motif et horodatage ; une telle modification n'est ni activee ni proposee comme migration automatique.
- Test du programme installe Windows et du serveur MySQL 5.7 reste distinct de la simulation SQLite.

## Recette locale

Commande :

    python -m unittest -v tests.test_stats_assiduite_synthetic tests.test_stats_assiduite_exports tests.test_stats_assiduite_objets

Resultat initial : 44/44 PASS, donnees exclusivement fictives.
