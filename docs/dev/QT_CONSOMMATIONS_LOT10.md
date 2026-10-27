# Noethys SL Qt — Lot C10 : fiches métier dans une seule fenêtre

Date : 27 octobre 2026. Uniquement la branche qt.

## Objectif et nature

Le démonstrateur C8 a été jugé léger et homogène par l'utilisateur sur
son poste Windows. C10 conserve cette fluidité en ajoutant des fiches
contextuelles Familles, Individus, Activités et Inscriptions. Il s'agit
toujours de données synthétiques et non d'un logiciel Noethys complet.

## Versions et comparatif des branches

| Branche | Base contrôlée | Statut |
| --- | --- | --- |
| main | f6f5ccdf6a491025db052b7759aa6facc01b2eca | NON APPLICABLE, inchangée |
| wx | 11b85461607bd5186f4043fadde831832114911d | NON APPLICABLE, inchangée |
| qt | 2b19fdfaa798f1bc1ec4580b775887e5b8d4a92e | Code C10 testé en CI |

Commits du développement :
- f4cf65116ccf27996b7d4955780246b9cbce7ec0 : navigation et dix tests.
- 8d025096c73de4cabb0694ccdbe0619be30a3470 : recettes visuelles,
  contrôle du périmètre du test de recherche et workflow Windows.

## Fonctions livrées dans le démonstrateur fictif

- Une liste à gauche et une fiche de détail à droite dans un QSplitter :
  aucun dialogue supplémentaire, et largeur ajustable.
- Familles : membres effectivement rattachés et inscriptions liées.
  Les valeurs IDcategorie et titulaire restent des indicateurs BRUTS ;
  aucune catégorie n'est interprétée comme Représentant/Enfant/Contact.
- Individus : naissance, liens familiaux, adresse référencée sans
  extrapolation, courriel fictif et compte des inscriptions.
- Activités : dates, code et inscriptions associées.
- Inscriptions : famille/individu, activité, statut et date.
- Navigation contextuelle : Famille #100 vers ses deux membres
  uniquement, puis inscriptions de l'individu sélectionné via ID
  numérique paramétré. Retour conservant la sélection précédente.
- Recherche dans les lignes déjà lues, sans répéter la requête de
  liste à chaque touche ; les fiches peuvent faire des SELECT propres.
- Base strictement créée dans TemporaryDirectory par C8, contrôles
  de chemin, marqueur de fixture, SQLite URI ro et PRAGMA query_only.
  Aucun UPDATE/INSERT/DELETE métier.
- Important : depuis l'inscription, la navigation ouvre encore le
  calendrier GLOBAL. L'interface annonce explicitement qu'il ne
  s'agit PAS d'un filtre individuel/inscription exact.

## Résultats Windows

Source : https://github.com/fr4nck/Noethys-SL/actions/runs/40541696279

Windows / Python 3.11 / PySide6 : compilation PASS, 244 tests PASS,
0 échec, 0 erreur. Dix nouveaux tests C10. Les cas couvrent fiches,
relations par identifiant, retour et sélection, refus de chemin externe,
absence d'édition, filtres de liste, activité, clavier, thèmes et tailles.

Deux scénarios de captures visuelles : clair 100 %, sombre 150 %.
Trois images chacun (Famille, Individus, Inscriptions) plus JSON.
Artifact qt-c10-fiches-fictives, ID 12751351279, taille 48 895 octets,
rétention 14 jours annoncée dans le workflow. La base fictive a été
comparée avant/après, aucun changement.

Précision qualité : le premier run C10 (40541040767) indiquait
SUCCESS mais contenait des tracebacks Python au sein de callbacks Qt
dus à un mock de test qui interdisait par erreur les lectures des
fiches. Le test a été corrigé pour cibler seulement les requêtes
de liste. Le run de référence 40541696279 ne présente aucun
Traceback dans ses logs. Ne pas utiliser le premier run comme preuve.

## STOP-GATE et prochaine étape

Aucune écriture financière, rôle familial inféré, mutation de
rattachements ou usage d'une base réelle. Le démonstrateur n'est
pas un installateur prêt à être déployé. Le rendu graphique Windows
réel, la saisie et la parité de facturation wx/Qt sont distincts.

Priorité C11 : remplacer le lien inscription → calendrier global par
un filtre de consommations EXACT sur IDindividu et, lorsque vérifié,
IDinscription, en conservant le panneau bloquant C3 et la lecture seule.
