# Noethys SL Qt — Lot C7 : stabilité graphique et interactions

Date : 27 octobre 2026. Périmètre exclusif de la branche qt.

## 1. Références et conservation des branches

| Ligne | Commit contrôlé | Statut C7 |
| --- | --- | --- |
| main | f6f5ccdf6a491025db052b7759aa6facc01b2eca | NON APPLICABLE — inchangée |
| wx | 11b85461607bd5186f4043fadde831832114911d | NON APPLICABLE à l'interface Qt — inchangée |
| qt | 8aade7b3ddd018a9ea9dc7669ebd275254f2241b | VALIDÉ TECHNIQUEMENT en CI Windows, recette utilisateur EN ATTENTE |

Commits du lot C7 :
- 8ac8c236 : correctifs de rafraîchissement et neuf tests UI.
- e5b8b280 : pilote de captures et mesures d'interaction Qt.
- 82d67198 : suppression de la double découverte de neuf tests existants.
- 880a8080 : mesure des Paint du viewport interne du calendrier.
- 8aade7b3 : déclenchement CI également lors des changements des pilotes de capture.

Aucun merge global, aucune modification de main/wx, aucune écriture sur base Noethys réelle.

## 2. Corrections apportées à l'interface

1. Le modèle ConsumptionTableModel évite beginResetModel/endResetModel si l'ensemble des lignes reçues est strictement inchangé. Un rafraîchissement identique ne vide plus visuellement le tableau et ne fait plus perdre sa sélection.
2. Si les données ont changé, la consommation précédemment sélectionnée est retrouvée par ID (et non par numéro de ligne). Si elle n'est plus visible, le détail et le précontrôle sont effacés.
3. Le tableau de consultation reste actif pendant la lecture asynchrone, plutôt que d'être grisé puis réactivé.
4. Les colonnes courantes disposent de largeurs stables ; les noms/activités restent extensibles. Les changements de filtre n'entraînent plus de recalcul automatique des largeurs de toutes les colonnes.
5. Le lot « Tout sélectionner / Tout désélectionner » notifie le calendrier une fois pour l'ensemble des cases. Les sept émissions successives ne provoquent plus sept lectures SQL mensuelles.
6. Si les comptages du mois sont identiques, le calendrier ne détruit ni ne recrée sa liste de journées et ses marques.

Les filtres, le calendrier et le panneau de simulation C3 restent en lecture seule. Aucune opération de saisie n'est activée.

## 3. Qualification Windows exécutée

Workflow : https://github.com/fr4nck/Noethys-SL/actions/runs/40526847975

- Windows GitHub Actions, Python 3.11, PySide6 hors écran : compilation PASS ; 224 tests PASS, 0 échec, 0 erreur.
- 9 tests C7 nouveaux, sans duplication de la fixture C2.
- Couverture nouvelle : 15 rafraîchissements consécutifs sans modelReset, conservation de l'ID de sélection et du détail, actualisation de montant sur fixture, suppression sûre de la sélection par filtre, une seule lecture mensuelle après sélection globale, absence de reconstruction de la liste des jours, clavier Entrée/flèche, changements rapides de date/activité, redimensionnement, résultats périmés ignorés et largeurs de colonnes stables.
- Les scripts antérieurs C6 (captures statiques 100 % et 150 %) restent PASS.

Pilote dynamique : tools/qt_c7_interaction_trace.py

Le pilote ouvre la vraie surface ConsumptionCalendarPage avec la fixture SQLite entièrement inventée du C2. Il produit, pour chaque profil :
- trois images PNG (initial, filtré, restauré) ;
- un fichier JSON de mesures de modèle, Paint, Resize, sélection et contenu des lignes ;
- 20 actualisations identiques avec 0 modelReset parasite ;
- 24 changements rapides de date/activité avec état final contrôlé ;
- preuve que le dump SQLite de la fixture est identique avant et après ;
- avertissement visible interdisant toute écriture.

Résultats CI : 100 % et 150 % PASS ; 3 images par profil. Mesures observées pour chaque profil : 30 événements Paint sur le viewport du tableau et 30 sur la grille interne du calendrier. Ces comptes ne sont ni un seuil de performance ni une mesure objective du scintillement ; ils dépendent du pilote et de l'environnement.

Artifact GitHub Actions : qt-c7-interactions-fictives, ID 12744657634, 91 770 octets, rétention 14 jours annoncée par le workflow. Six PNG et deux fichiers JSON consultables depuis le run ci-dessus.

## 4. Limites et STOP-GATE

Ce lot démontre une réduction des resets, du reflow et de la perte de sélection en environnement fictif Windows hors écran. Il ne démontre pas l'absence de scintillement lors d'interactions réelles à 60 Hz, sur un poste Windows avec son pilote vidéo, son thème ou plusieurs moniteurs DPI.

La qualification sur copie de base représentative, l'observation de vraies animations et l'audit de parité des écritures métier wx/Qt restent EN ATTENTE. Le précontrôle C3 demeure systématiquement non exécutable, les contrôles de période, de droits, de facturation et de ventilation ne sont pas homologués, et la création automatique d'adhésions reste suspendue. Aucune publication Qt et aucune désactivation de wx.

## 5. Prochaine qualification proposée

C8 : recette graphique Windows réelle sur base intégralement fictive, incluant navigation prolongée, clavier, thèmes, fenêtres, écran à 125/150 %, ergonomie du gestionnaire et conservation des sélections. Les prochaines étapes transactionnelles devront rester séparées de la recette graphique jusqu'à la validation de la parité métier.
