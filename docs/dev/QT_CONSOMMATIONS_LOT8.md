# Noethys SL — C8 : démonstration Qt Windows et recette graphique

Date : 27 octobre 2026. Ce lot ne livre pas un logiciel de gestion en production.

## Objectif et sécurité

Lancer sur Windows une VRAIE fenêtre Qt de consultations des consommations, à thème clair/sombre, en conservant tous les contrôles C1-C7, afin de rechercher par observation humaine les problèmes d'affichage que GitHub Actions en mode offscreen ne peut pas établir.

Le lanceur tools/qt_c8_windows_demo.py crée TOUJOURS son propre TemporaryDirectory. Il y génère 112 consommations totalement inventées (quatre personnes fictives sur 28 jours d'octobre 2026, deux activités, six états usuels, NULL et code inconnu, prestations fictives). Il ne demande aucun chemin de base, ne lit pas Config.json et ne charge pas la base Noethys configurée. À la fermeture, le répertoire fictif est effacé.

Aucun writer Qt de consommation n'est activé : le panneau C3 est un précontrôle bloquant, sans bouton Enregistrer. Les montants affichés n'ont aucune valeur de facturation.

## Exécution Windows interactive (recette humaine)

Depuis la racine d'un clone fr4nck/Noethys-SL à jour sur la branche qt :

1. Installation ponctuelle avec Python 3.11 :
   py -3.11 -m pip install -r requirements-qt.txt
2. Lancement par double-clic :
   tools\Noethys-Qt-C8-Demo.cmd
   ou par console :
   py -3.11 tools\qt_c8_windows_demo.py --theme light --scale 1
3. Pour tester l'échelle 125 % :
   py -3.11 tools\qt_c8_windows_demo.py --theme dark --scale 1.25
4. Pour tester l'échelle 150 % :
   py -3.11 tools\qt_c8_windows_demo.py --theme light --scale 1.5

Ne pas mélanger les essais à l'échelle simulée QT_SCALE_FACTOR avec le changement de mise à l'échelle réel de Windows : pour la recette DPI physique, régler aussi la mise à l'échelle dans Paramètres Windows > Système > Écran. Vérifier l'effet de la combinaison choisie. Quitter complètement le processus avant de relancer.

## Parcours de recette utilisateur C8

- Choisir le thème Système, Clair puis Sombre. Vérifier lisibilité, contrastes, focus, couleurs des états et absence de clignotement.
- Sélectionner les 2, 3 et 17 octobre. Naviguer rapidement vers d'autres mois puis revenir. Vérifier que la date et le détail suivent le calendrier.
- Choisir une activité, une autre, puis Toutes ; tester le champ de recherche et les sept états par clic.
- Enchaîner « Tout sélectionner », « Tout désélectionner » et Actualiser, avec et sans sélection de consommation.
- Utiliser la touche Entrée dans la liste des jours, les flèches dans le tableau, F5 pour actualiser et Ctrl+F pour rechercher.
- Redimensionner la fenêtre, réduire la largeur et la hauteur, puis l'agrandir. Tester sur écran principal et sur second écran si disponible, aux échelles Windows 100 %, 125 %, 150 %.
- Vérifier que la bannière FICTIVE / LECTURE SEULE reste visible, que le précontrôle annonce AUCUNE_ECRITURE et qu'aucune opération réelle n'est possible.
- Noter les épisodes de scintillement : écran, DPI, résolution, thème, action, date/heure, vidéo et fréquence reproductible. Une capture statique n'est pas suffisante pour démontrer un bug de repaint.

## CI sur GitHub Actions

Le même script permet des vérifications automatisées en mode --smoke, avec configuration de thème et facteur d'échelle, images PNG et métadonnées JSON déposées dans artifacts/qt-c8. La suite de tests_qt/test_consumptions_c8_demo.py contrôle la fixture fictive, le précontrôle, les thèmes, les redimensionnements, les filtres et l'absence d'accès au Config.json.

Ces essais tournent dans un runner Windows à rendu hors écran. Ils prouvent une ouverture de fenêtre Qt et la cohérence des contrôles, mais pas les performances vidéo d'une session graphique interactive ni une recette humaine.

## Traçabilité

Branches à l'ouverture : main f6f5ccd, wx 11b8546 et qt a55fba2. Le code métier wx, les adhésions et les trois branches de base ne sont pas modifiés, seul qt reçoit les fichiers du lot. Verdict CI, nombre de tests, captures et SHA final à consigner après exécution. Les écritures de consommation Qt et le remplacement de wx restent sous STOP-GATE.
