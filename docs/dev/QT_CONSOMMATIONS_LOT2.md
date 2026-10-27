# Lot Qt C2 — calendrier et navigation des consommations (27/10/2026)

## Contrat

- C2 conserve le tableau de lecture C1, les sept états toujours cochables, le mode annuel par défaut et le plafond de 300 lignes.
- Choix de l'activité par identifiant (libellé et ID affichés). Les activités sont lues sans écriture depuis la table historique activites.
- Calendrier des mois, dates cliquables et liste de journées. Le clic active le filtre exact de jour ; « Afficher toute l'année » revient au mode C1. Changer l'année ou le mois met à jour la sélection.
- **Comptage mensuel exact indépendant du tableau borné** par une requête SELECT COUNT(*) GROUP BY date. Il respecte l'année, les états, l'activité et la recherche texte/nombre. Une journée peut dépasser 300 lignes sans fausser le calendrier.
- Le détail d'une consommation affiche date, état, personne, activité, unité, groupe, horaires, prestation, montant associé. Quand IDevenement est renseigné, son ID et son nom apparaissent. En l'absence de lien d'événement, le logiciel ne déduit **aucune séance canonique**.
- Aucune somme financière, création/suppression, facturation, changement de pointage, migration SQL, ajout de branche ou écriture en base.
- La connexion SQL reste celle du pont Qt gardé par l'autorisation explicite existante ; en recette, uniquement une copie SQLite fictive. Comptage, listing et activité utilisent des connexions distinctes et fermées. Opérations de consultation lancées en arrière-plan sous Qt ; seule la dernière demande actualise le calendrier.
- Cohérence des sources avec les six codes d'état du gestionnaire historique : reservation, attente, refus, present, absentj, absenti ; les autres valeurs et NULL sont regroupés dans le septième choix.

## Tests et limites

- Fixtures totalement fictives : SQL SQLite, bornes de mois/année, état inconnu, recherche et caractères SQL, filtre d'activité, événement réel associé, contrôle non-écriture, plus de 300 consommations un même jour, clics calendrier, retour au mode année et sélection.
- CI cible : workflow « Qt prototype — Noethys » sur Windows / PySide6, compilation et unittest tests_qt.
- Pas de comptage réglementaire des présences, ni de nombre de séances distinctes : GROUP BY date compte les lignes de consommations, pas des enfants distincts ni les événements.
- Pas d'édition ni sauvegarde des consommations. Le prochain lot C3 devra qualifier les opérations de saisie transactionnelles sur copie isolée et la parité métier wx avant activation.
- Garde de publication : tests hors écran ne remplacent pas une recette humaine Windows avec copie représentative, vérification DPI, performance MySQL et non-régression main/wx.
- Source de travail : qt sur base e65a590 ; main f6f5ccd ; wx a24e1dd. Pas de merge global, ni de synchronisation de correctifs communs réalisée par ce lot.
