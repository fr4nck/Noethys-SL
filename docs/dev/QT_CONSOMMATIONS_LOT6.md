# Noethys SL Qt — Lot C6 : comparaison transactionnelle et recette graphique

Date : 27 octobre 2026. Développement limité à la branche qt, sans
suppression ni création de branche, sans mise à jour de main ou wx.

## Preuves et bases du lot

- main : f6f5ccdf6a491025db052b7759aa6facc01b2eca.
- wx : 11b85461607bd5186f4043fadde831832114911d.
- qt à l'ouverture : 016ab1792ae8107ae128326a8625d6813649ae30.
- C6 code : 8da887012b50a121469869c8120e0c06228d8809.
- C6 configuration CI : ce5656d2191a67ba33b909e7f4448b2645c4e9b0.
- Les méthodes Sauvegarde historiques wx et qt ont été comparées au C5 :
  même corps de méthode épinglé FNV32 d4745a0b malgré la divergence
  générale du fichier CTRL_Grille.py. Cette identité est contrôlée
  automatiquement par le banc C5 réutilisé en C6.

## C6 : la preuve de rollback

Fichier de test : tests_qt/test_consumptions_c6_deferred_wx.py.

C6 exécute la VRAIE méthode historique Sauvegarde depuis le code
du dépôt, deux fois sur deux bases entièrement fictives et isolées :
une première fois selon les appels Commit/Close historiques, une
seconde sous un adaptateur de TEST qui reporte les Commit et Close
jusqu'à la fin de l'opération.

Les deux résultats SQLite sont identiques lorsque l'opération réussit,
y compris pour une modification de prestation et la suppression de
ventilation qu'elle provoque. Pour une panne simulée dans l'historique,
le premier Commit historique laisse la consommation modifiée sans
historique. La variante à validation unique annule toutes les
modifications du scénario. Les pannes avant premier Commit et après
insertion d'un mémo sont également couvertes.

Limite majeure : la doublure contrôlée n'est PAS une solution à
déployer. Elle ne contient ni les autorisations réelles, ni la
gestion des périodes, ni les tarifs complets, ni les appels externes
potentiellement non réversibles. Elle ne démontre pas que le
gestionnaire wx dispose d'un rollback global sur une base réelle.
Le panneau Qt C3 demeure non exécutable. Aucun writer Qt métier
n'a été ajouté.

## C6 : vérification graphique Windows

Fichier de capture : tools/qt_c6_visual_capture.py.

La vraie surface Qt ConsumptionCalendarPage est lancée uniquement
avec la fixture SQLite fictive test_consumptions_calendar. Elle
sélectionne une journée contenant deux consommations, vérifie que
le filtre par jour et le tableau réagissent et que l'avertissement
de désactivation des écritures est visible, puis capture la fenêtre.

Le workflow .github/workflows/qt-prototype.yml a été enrichi :
- rendu 100 % : 1280 x 830 pixels, capture scale100.png ;
- rendu 150 % : 1920 x 1245 pixels, capture scale150.png ;
- artifact public GitHub Actions : qt-c6-captures-fictives,
  artifact ID 12740784525, rétention déclarée 14 jours ;
- aucune donnée personnelle ; aucun profil Noethys chargé.

Ce contrôle valide le lancement et des dimensions statiques dans
l'environnement Windows CI. Il NE vérifie ni les scintillements
pendant interactions, ni les changements continus de page, ni
les polices ou DPI du poste utilisateur. Les images doivent
être ouvertes et appréciées visuellement.

## Qualification CI

Run code C6 : https://github.com/fr4nck/Noethys-SL/actions/runs/40522554249
Run code + captures : https://github.com/fr4nck/Noethys-SL/actions/runs/40522819704

Les deux runs Windows ont conclu SUCCESS ; compilation PASS et
215 tests Python PASS (0 échec, 0 erreur), dont 10 nouveaux scénarios C6.
Le second run a également validé les deux générations PNG et
le dépôt de l'artifact qt-c6-captures-fictives.

## Matrice de non-régression après C6

| Branche | Référence | Verdict |
| --- | --- | --- |
| main | f6f5ccd | NON APPLICABLE au banc de tests Qt ; synchronisation métier EN ATTENTE |
| wx | 11b8546 | Source de référence vérifiée, branche NON MODIFIÉE ; parité globale EN ATTENTE |
| qt | ce5656d | VALIDÉ TECHNIQUEMENT en CI ; usage réel et release EN ATTENTE |

## STOP-GATE et suite

Aucun correctif métier commun recopié sans qualification, aucune
migration SQL, aucun compte ou consommation de production modifié,
aucun bouton Enregistrer ajouté à l'écran des consommations.

Prochaines étapes proposées : C7 pour une qualification dynamique
des mises à jour visuelles Qt et de la navigation au clavier, avec
captures/vidéos reproductibles sur données fictives ; puis analyse
des droits, périodes et opérations transactionnelles complètes sur
copies de recette indépendantes, avant d'envisager la saisie Qt.
