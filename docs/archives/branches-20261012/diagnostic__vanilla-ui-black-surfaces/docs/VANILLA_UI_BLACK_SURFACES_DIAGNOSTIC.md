## Objet

Relancer le diagnostic des zones noires observées dans Noethys Vanilla en appliquant le REX Teamworks capitalisé dans PMSL-Arch, sans correction graphique générale à ce stade.

## Baseline

- ligne : `maintenance/vanilla`
- candidat préparé : Vanilla **1.3.4.3**
- PR de version/distribution : #367
- SHA #367 observé au lancement du diagnostic : `a0fcbb072653ffe6a238651dd3ba7f9ac44141f1`
- validation humaine Windows toujours requise avant stabilité.

## Premier constat mécanique

Le contrat Vanilla veut désormais une interface claire même lorsque Windows est sombre (#358).

Or `noethys/Ctrl/CTRL_ObjectListView.py::ObjectListView.Activation(False)` affecte encore explicitement au message de liste vide :

```python
wx.SystemSettings.GetColour(wx.SYS_COLOUR_FRAMEBK)
```

puis applique cette valeur via `stEmptyListMsg.SetBackgroundColour(...)`.

C'est un **candidat concret de divergence de palette** : un contrôle enfant peut reprendre une couleur système Windows sombre alors que Vanilla impose par ailleurs un rendu clair. Cela correspond directement à la famille de défauts rencontrée dans Teamworks : mélange entre palette applicative et couleurs natives système.

Ce constat ne prouve pas encore que toutes les captures/zones noires signalées proviennent de ce chemin. Il fournit en revanche un premier chemin de code précis à reproduire.

## Protocole de diagnostic

Pour chaque zone noire :

1. identifier écran, classe et contrôle ;
2. relever la source effective de Background/Foreground ;
3. comparer avec un contrôle sain du même écran ;
4. distinguer couleur système, couleur historique, héritage parent et repaint tardif ;
5. tester le contrôle en état normal puis désactivé ;
6. tester Windows clair et Windows sombre tout en gardant Vanilla claire ;
7. vérifier le cycle Show/ShowModal, Refresh/Layout et fermeture/réouverture ;
8. ne corriger qu'après attribution mécanique de la cause.

## Recherche prioritaire

- appels à `wx.SystemSettings.GetColour` ;
- `SetBackgroundColour` / `SetForegroundColour` ;
- couleurs noires ou sombres codées en dur ;
- ObjectListView / FastObjectListView ;
- contrôles custom et surfaces AUI ;
- styles appliqués après construction ;
- Refresh/Layout/Update tardifs ou récursifs ;
- états disabled/empty/selected/focus.

## Première hypothèse à tester

**H1 — fuite de palette système dans Vanilla claire.**

Reproduction minimale attendue :

- Windows en mode sombre ;
- Vanilla 1.3.4.3 en thème clair forcé ;
- ouvrir un écran utilisant `CTRL_ObjectListView.ObjectListView` ;
- atteindre un état où `Activation(False)` est appelé ;
- vérifier si `stEmptyListMsg` devient noir/sombre tandis que son parent reste clair.

Si H1 est confirmée, le correctif devra utiliser une couleur cohérente avec la surface claire effective du contrôle/parent, et non une couleur Windows globale. Le test devra verrouiller spécifiquement le cas **Windows sombre + Vanilla claire + liste désactivée**.

## Critère de sortie

Avant tout lot de correction, produire un tableau par anomalie avec :

- écran/contrôle ;
- chemin de code ;
- déclencheur ;
- source effective de couleur ;
- contrôle sain de comparaison ;
- cause confirmée ou hypothèse ;
- correctif minimal ;
- test automatisable ;
- validation Windows restant nécessaire.

Pas de refonte UI, pas de thème sombre Vanilla, pas de modification métier ou BDD dans ce diagnostic.
