## Objet

Relancer le diagnostic des zones noires / incohérences graphiques observées pendant la recette humaine de Noethys Vanilla, en réutilisant le REX Teamworks désormais capitalisé dans PMSL-Arch.

Référence méthodologique : fr4nck/PMSL-Arch#42.

## Baseline

- ligne : `maintenance/vanilla`
- candidat 1.3.4.3 : PR #367
- HEAD observé de #367 : `a0fcbb072653ffe6a238651dd3ba7f9ac44141f1`
- la recette humaine Windows reste explicitement requise avant stabilité.

## Premier constat mécanique

Le candidat Vanilla n'embarque pas le design system moderne de `master`. Son `UTILS_Interface.py` reste le moteur historique Vert/Bleu/Noir.

Le thème historique **Noir** contient explicitement :
- `couleur_tres_foncee = wx.Colour(0, 0, 0)`
- `couleur_claire = wx.Colour(150, 150, 150)`
- surfaces claires à 240/240/240 et 230/230/230.

Le profil utilisateur `Customize.ini` conserve `interface.theme` et sa valeur par défaut `Vert`.

Point important : le correctif #358 qui « verrouillait le thème clair » appartient au rail UI modernisé de `master`; il n'est pas une preuve que la ligne `maintenance/vanilla` neutralise effectivement toutes les sources historiques de noir. Le diagnostic doit donc être mené sur le SHA Vanilla réel, sans transposer aveuglément le correctif #358.

## Hypothèses à vérifier, sans les confondre avec une cause démontrée

H1 — une ou plusieurs zones utilisent encore directement les tokens du thème historique Noir.

H2 — un contrôle natif wxMSW hérite d'une couleur système / parent différente de celle attendue.

H3 — une surface peinte manuellement ou un contrôle custom réapplique une couleur après initialisation.

H4 — le défaut dépend du cycle de paint/repaint et non de la valeur initiale de palette.

H5 — une configuration utilisateur historique sélectionne ou réinjecte un thème/couleur que la recette pensait neutralisé.

## Protocole de diagnostic

Pour chaque zone noire observée :

1. identifier écran, classe et contrôle ;
2. relever parent, type wx, couleur de fond/texte effective et thème lu depuis Customize.ini ;
3. trouver la provenance : système, parent, UTILS_Interface, valeur codée en dur, contrôle custom ou paint ;
4. choisir sur le même écran un contrôle sain et comparer les deux chemins ;
5. vérifier construction, Show/ShowModal, resize, Refresh/Layout et fermeture/réouverture ;
6. reproduire sur Windows avec le même artefact ;
7. n'implémenter aucun correctif avant d'avoir réduit le défaut au plus petit mécanisme causal.

## Inventaire statique à produire

Sur le HEAD candidat, inventorier au minimum :
- appels `SetBackgroundColour` / `SetForegroundColour` ;
- `wx.Colour(0, 0, 0)`, `BLACK`, `#000000` et équivalents ;
- usages de `UTILS_Interface.GetValeur` et `GetTheme` ;
- contrôles custom et handlers `EVT_PAINT` des écrans touchés ;
- appels tardifs/récursifs `Refresh`, `Update`, `Layout`, `Show`, `ShowModal` ;
- lecture/écriture du thème dans `Customize.ini`.

## Critère de sortie

Le diagnostic n'est terminé que lorsque chaque anomalie possède :
- écran/contrôle ;
- chemin de code ;
- source effective de la couleur/repaint ;
- cause démontrée ou hypothèse marquée comme telle ;
- contrôle sain de comparaison ;
- correctif minimal envisagé ;
- test automatisable ;
- validation visuelle Windows restante.

PR volontairement **diagnostic / lecture seule** : aucun correctif graphique dans ce lot.
