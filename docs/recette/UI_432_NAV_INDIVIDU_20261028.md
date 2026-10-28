# UI-432 — reproduction navigation individu depuis la liste (28/10/2026)

## Nouveau signal utilisateur, non couvert par le premier diagnostic Connecthys

Sur Noethys-SL wx Windows, avec fenêtre principale maximisée, clic droit sur un
individu depuis la liste, puis **Ouvrir la fiche individuelle** :
1. le système donne parfois l'impression que le plein écran se perd ;
2. la fiche individuelle s'ouvre en passant par une fenêtre familiale ;
3. à sa fermeture, il faut ensuite fermer la fiche famille pour revenir à la liste.

Le nouveau déclencheur est **distinct** des lenteurs/éventuelles iconisations
pendant la synchronisation Connecthys. Il n'établit pas à lui seul une
modification du flag Win32 `IsZoomed`.

## Cause structurelle démontrée

`noethys/Ol/OL_Individus.py` :
- `OnContextMenu` relie l'item **70** « Ouvrir la fiche individuelle » à `Modifier` ;
- `Modifier` pose `ouvrirFicheInd=True` et appelle `OuvrirFicheFamille` ;
- l'ancien `OuvrirFicheFamille` choisit obligatoirement une famille (ou
  demande confirmation si aucun rattachement), ouvre `DLG_Famille.Dialog`,
  puis appelle `dlg.OuvrirFicheIndividu(IDindividu)`, avant
  `dlg.ShowModal()` sur la famille.

Ce parcours génère une **fenêtre familiale intermédiaire inutile**, et un
deuxième dialogue modal à fermer. La perte de maximisation de la fenêtre
principale n'est pas encore attribuée causalement à ce détour.

## Correction ciblée sur wx

- Le parcours `ouvrirFicheInd=True`, qu'il provienne du clic droit ou de
  Maj+double-clic, ouvre `DLG_Individu.Dialog` directement, quel que soit
  le nombre de familles auxquelles l'enfant est rattaché.
- Le propriétaire est **le parent wx de plus haut niveau de la liste**
  (`wx.GetTopLevelParent(self)`), jamais une fiche famille cachée et jamais
  un dialogue sans parent. Un `finally` détruit la fenêtre à la sortie
  de `ShowModal`.
- Le droit `familles_fiche/consulter` est conservé sur l'action existante,
  et le droit `individus_fiche/modifier` est vérifié avant l'édition,
  comme il l'était dans `CTRL_Composition.Modifier`.
- Après validation, rafraîchissement de la liste avec préservation de
  l'ID sélectionné, puis actualisation du conteneur; historique de recherche
  inchangé. La fermeture ou l'annulation ramène directement à la liste.
- L'ouverture de la **fiche famille** par double-clic ordinaire ou par
  « Modifier la fiche famille », ainsi que la **grille des consommations**,
  ne change pas.
- Aucun `Maximize(True)`, `Iconize()`, `Raise()` forcé n'est ajouté :
  le symptôme Win32 doit être mesuré, pas masqué.

## Qualifications

- `tests/test_noethys_sl_ouverture_individu_directe.py` : 11 scénarios
  simulés, dont sélection du menu 70, famille 20, grille 60, Maj+double-clic,
  ouverture sans consultation de rattachements, owner modal, retour à la liste,
  annulation, exception, droits utilisateur, historique de recherche.
- Les tests sont ajoutés à la CI rapide Windows et au candidat RC10 Windows.
  **La recette réelle du problème de maximisation reste à faire** : fenêtre
  principale maximisée → clic droit individu → fiche individuelle → fermer,
  puis comparer `IsMaximized` / `IsIconized` de la MainFrame et états Win32
  avant, pendant et après. Vérifier aussi les individus sans famille ou
  rattachés à plusieurs familles.
- Pas de données PMSL réelles, pas de migration, pas de changement Connecthys,
  `main`, `qt` ou des documents Pêle-Mêle.
- L'ancien candidat RC10 `5c63e83c` **ne contient pas ce correctif**.
  Construire un nouveau candidat puis vérifier sa CI avant publication ;
  une CI verte seule ne prouve pas la correction du symptôme Windows réel.

**Verdict** : navigation inutile clairement identifiée et corrigée dans
le code ciblé, stabilisation du plein écran en recette Windows
**non encore démontrée**.
