# Noethys SL 0.1.0 RC10.4 — situation des communes et fiche enfant

Cette version reprend **toutes les modifications de la branche wx apres RC10.3**, sous reserve des verifications de recette indiquees ci-dessous.

## Nouveautes

- **Situation des communes ALSH** : option « Compter les absences injustifiees » desactivee par defaut. Si activee, les absences injustifiees sont comptabilisees separement des presences, jamais deguisees en frequentation reelle ; leur prise en charge conventionnelle doit etre confirmee.
- Import des consommations en lecture seule, selection explicite des unites d'accueil, gestion des acomptes et edition **PDF, CSV et Excel (.xlsx)**.
- **Fiche enfant #436** : reprise de la fiche Pêle-Mêle et impression A4 sur deux pages ; reprise des informations existantes sans doublonner les données medicales. L'affichage et l'export des données sensibles restent soumis aux habilitations et choix explicites.
- Maintien des correctifs **RC10.3** sur recherche d'anomalies, attentes, proprietaires et non-regression de la maximisation.
- Correction des deux echecs de tests apparus apres RC10.3 (signature de lecture d'absences et placement des boutons).

## Precautions

- **Sauvegardes #437 : incident reel encore ouvert.** Les tests sur MySQL fictif/jetable ne suffisent pas a prouver la sauvegarde/restauration complete de la base PMSL ; ne pas considerer cette release comme une resolution automatique du probleme sur le site.
- **Connecthys #435 et fenetres #432 :** la recette automatisee ne remplace pas la verification sur le poste utilisateur et une copie de base.
- Pas de modification volontaire de la version interne Noethys (`1.3.4.4`) ni de migration de schema pour ce changement de version publique.
- Aucune activation automatique d'un nouveau droit d'acces medical ni du portail familles.

## Livraison

Installateur Windows et ZIP portable produits **a partir d'un meme candidat** par GitHub Actions, avec verification du demarrage, de la sauvegarde MySQL jetable, du profil portable et des empreintes SHA-256. Publication uniquement apres toutes les barrieres de CI et autorisation explicite.
