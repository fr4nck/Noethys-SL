# Noethys SL Qt — Lot C12 : parcours métier dans la vraie coque native

Date : 27/10/2026. Périmètre : branche canonique qt uniquement.
Ce lot est un démonstrateur avancé et non une release utilisable en production.

## 1. Besoin et architecture

Retour utilisateur C8–C11 : moteur Qt perçu plus léger et homogène que wx,
sans scintillement remarqué pendant la première recette manuelle. Les
parcours restent à rapprocher des habitudes de Noethys.

C12 intègre les surfaces déjà implémentées dans la COQUE PRINCIPALE Qt
noethys_qt/noethys_native.py, plutôt que produire une nouvelle coque
parallèle. Le module noethys_qt/inscriptions_readonly.py existait mais
n'était pas relié à la navigation native. Il l'est désormais.

## 2. Fonctions livrées dans Qt

- Rubrique Inscriptions dans le menu de gauche, la barre supérieure,
  le menu Navigation et l'accueil.
- Raccourcis Alt+4 (Inscriptions), Alt+5 (Consommations),
  Alt+Gauche (retour à la fiche précédente).
- Depuis une famille, accès aux inscriptions de cette famille
  (filtre SQL IDfamille paramétré).
- Depuis un individu, accès aux inscriptions filtrées par IDindividu
  et, directement, aux consommations de cet individu.
- Depuis une inscription, résolution par SQL SELECT d'IDinscription
  vers les clés IDindividu/IDfamille/IDactivite ; passage de l'intersection
  IDinscription + IDindividu vers les filtres C11 de consommation.
  La résolution ne s'appuie ni sur le nom ni sur le numéro de ligne affiché.
- Deux niveaux de retour, par exemple Famille → Inscriptions →
  Consommations → Inscriptions → Famille. Le filtre et la sélection
  précédente restent disponibles après retour.
- Navigation globale : une entrée indépendante du menu retire les
  anciens filtres de fiche ; aucun ancien contexte ne doit contaminer
  le dossier suivant.
- Un clic de navigation n'entraîne plus deux demandes SQL identiques.
- Ctrl+F vise le champ de recherche de la rubrique courante,
  sans basculer systématiquement vers la recherche de personnes.
- Le modèle de recherche des individus évite les modelReset lorsque
  la recherche renvoie des lignes identiques (réduction des repaints).
- Les surfaces Inscriptions et Consommations restent en lecture seule,
  le panneau de simulation C3 conserve executable=False.

## 3. Résolution SQL et interdictions

InscriptionRepository.resolve_link valide l'identifiant AVANT d'ouvrir
la connexion. Sur SQLite, PRAGMA query_only=ON ; sur le pont MySQL
existant, seul SELECT est exécuté. Les connexions et curseurs sont
fermés, y compris en cas d'erreur.

Le mode de démonstration natif tools/qt_c12_native_shell_demo.py
utilise UNIQUEMENT C8FictiveDatabase (TemporaryDirectory, 112
consommations inventées). QSettings est dirigé vers un fichier INI
temporaire et l'application ne lit pas la configuration Noethys.
NoethysQtWindow(read_only_demo=True) neutralise l'éditeur Activités
pour empêcher une modification de fixture via la fenêtre de recette.

Ce verrou n'est PAS un mécanisme de contrôle métier en production :
la coque configurée conserve son fonctionnement préexistant pour
l'éditeur d'activités. Ne jamais tester C12 sur la base de l'association.

## 4. Recettes et évolution des tests

Références initiales :
- main f6f5ccdf6a491025db052b7759aa6facc01b2eca ;
- wx 11b85461607bd5186f4043fadde831832114911d ;
- qt bff581f1e3ece6fbd2d23cf945ebaed595a5ad51.

Commits du lot : bdb26d6 (interface + lien), 0315fcf (réduction de double
navigation), 9919ad1 (14 nouveaux tests), be75dfe (retour multi-niveaux),
b946f1c (deux tests de retour), ecd08eb (éditeur Activités bloqué en
démonstration), e24ed12 (différence année entière / journée C8 dans
une ancienne assertion), eec341f (lanceur et CI captures),
44e71c6 (Ctrl+F contextuel, modèle de personnes stabilisé et 2 tests).

CI code corrigé : https://github.com/fr4nck/Noethys-SL/actions/runs/40554010593
271 tests Windows PASS, 0 échec.

CI graphique : https://github.com/fr4nck/Noethys-SL/actions/runs/40554367190
271 tests PASS, deux parcours C12_NATIVE_PASS, 18 captures PNG et
2 rapports JSON, intégrité SQLite fictive conservée.
Artifact : qt-c12-coque-native-fictive ID 12756029369, 290 881 octets,
rétention 14 jours annoncée dans le workflow.

CI intégrale finale avec 2 tests clavier/repaint supplémentaires :
https://github.com/fr4nck/Noethys-SL/actions/runs/40554692254
Verdict EN ATTENTE au moment de rédaction ; ne pas préjuger 273 PASS.

## 5. Limites et matrice interbranches

| Branche | Situation C12 | Contrôle |
| --- | --- | --- |
| main f6f5ccd | NON APPLICABLE (interfaces Qt seulement) | Non modifiée |
| wx 11b8546 | NON APPLICABLE (référence wx) | Non modifiée |
| qt 44e71c6 | VALIDÉ partiellement (271 CI, 18 images), 273 en attente | Démonstration fictive seulement |

Aucun changement des moteurs de tarification, de pointage, de
facturation, d'historique ou d'adhésions. Les constantes autoritatives
des rôles familiaux et l'intégrité des rattachements restent des
chantiers distincts. Aucune copie de données privées ou base .nod
ne fait partie de C12. Les tests offscreen ne certifient pas le
ressenti graphique d'un poste physique ni la parité intégrale wx.

STOP-GATE absolu : saisie des consommations, modifications financières,
réconciliation de prestations/déductions/ventilation/historique,
droits effectifs, périodes, MySQL opérationnel, packaging et
diffusion de la coque Qt non homologués.

## 6. Recette Windows à effectuer ensuite

Dans le worktree Qt indépendant C:\Users\<profil>\Documents\GitHub\Noethys-SL-qt :

    git pull --ff-only origin qt
    .\tools\Noethys-Qt-C12-Shell-Demo.cmd

Le double-clic ouvre désormais la vraie coque principale Qt, sur
données fictives et sans éditeur Activités. Parcours à tester :
recherche d'une famille, ouverture du dossier, bouton Inscriptions,
sélection d'une inscription, bouton Consommations, retour deux fois.
Tester ensuite les raccourcis Alt+4/Alt+5, Alt+Gauche et Ctrl+F.

L'observation humaine sur Windows sera qualifiée séparément.
