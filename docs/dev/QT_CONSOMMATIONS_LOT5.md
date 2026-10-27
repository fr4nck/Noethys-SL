# Noethys SL Qt — C5 : référence de sauvegarde wx exécutée sur SQLite fictive

Date : 27 octobre 2026. Développement sur la seule branche qt, base 754a014.

## Fait nouveau : qualification croisée des blobs

- Branches lues avant le lot : main f6f5ccd ; wx 11b8546 ; qt 754a014.
- noethys/Ctrl/CTRL_Grille_cases.py : même blob 46b1e02 sur les trois branches.
- noethys/GestionDB.py : même blob c4ed9fd sur les trois branches.
- noethys/Ctrl/CTRL_Grille.py : wx f653316 tandis que main/qt 0b92eaa.
- **La fonction Sauvegarde(self) est IDENTIQUE caractère par caractère** entre les deux versions, malgré la divergence du fichier complet. Empreinte FNV32 du corps : d4745a0b. Cette preuve ne vaut pas synchronisation des autres méthodes.
- noethys/Utils/UTILS_Adhesions.py diverge entre wx 9f249a6 et main/qt b6d7465 ; aucune modification ni réactivation de AUTO_CREATION_SUSPENDUE.

## Méthode de recette C5

- Le test tests_qt/test_consumptions_c5_wx_execution.py extrait uniquement le corps Sauvegarde de la copie noethys/Ctrl/CTRL_Grille.py. Il refuse son exécution si l'empreinte diverge de celle comparée aux sources wx.
- La fonction wx est ensuite compilée, sans importer wxPython, Noethys configuré ou GestionDB : les dépendances sont remplacées par un adaptateur SQLite local et des doublures synthétiques.
- La base de recette est créée par TemporaryDirectory et possède des tables portant les noms et colonnes sollicités par Sauvegarde. Ce n'est PAS un schéma Noethys complet ni une copie utilisateur.
- L'adaptateur rejette tous les chemins externes, vérifie le marqueur de fixture, limite les opérations SQL aux tables autorisées, et laisse la création automatique d'adhésions explicitement suspendue.
- Scénarios : aucune modification, UPDATE de consommation, INSERT, DELETE, changement d'une prestation avec suppression de ventilation, erreur avant premier commit, erreur du service historique après premier commit, comparaison à l'interdiction d'écrire Qt C3 et refus de chemin étranger.

## Observation métier importante, à ne pas extrapoler

Sur cette fixture seulement, la vraie méthode Sauvegarde de wx exécute un premier DB.Commit après les consommations, puis traite les mémos et l'historique et effectue un second commit. En injectant une erreur dans l'historique, le banc observe que la consommation peut rester validée alors que l'historique n'est pas enregistré. Cela prouve un **risque de non-atomicité dans ce chemin de code**, sans affirmer qu'une erreur correspondante a été observée en exploitation.

Le fichier GestionDB.ExecuterReq n'appelle pas Commit implicitement ; ReqInsert, ReqMAJ et ReqDEL peuvent en revanche le faire par défaut. Les règles de vérification de droits/périodes sont dans les appels amont de wx, et ne sont pas portées en Qt.

## Périmètre de conformité

Ce résultat est une référence de comportement ponctuelle, pas une parité complète des effets facturation. Il manque : droits effectifs, contrôle de période, inscriptions, tarifs, forfaits, liquidations, règlements, historique complet, MySQL/InnoDB, erreurs concurrentes, migrations et copie réelle représentative. Le diagnostic C3 demeure non exécutable. Aucun module produit noethys_qt n'a été modifié.

STOP-GATE maintenu : aucune activation de saisie ni installateur Qt publié à ce stade. La CI du commit fonctionnel C5 et la matrice finale seront ajoutées après qualification.
