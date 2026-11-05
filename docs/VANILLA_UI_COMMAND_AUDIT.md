# Audit UI et stabilisation — Noethys Vanilla

> État : **audit de stabilisation — Vanilla NON déclarée stable**.
>
> Périmètre exclusif : dépôt `fr4nck/Noethys`, branche `maintenance/vanilla`, base auditée `b09082726278d397b9f107ea470245ce51851fa3` (2026-08-27).

Date de l'audit : 2026-09-07.

## Méthode et limites

Cet audit ne modifie aucun runtime, aucune logique métier, aucune base de données et aucun composant Connecthys. Il combine : inspection du code exact de `maintenance/vanilla`, inspection des bindings wx, analyse des cycles `ShowModal`/`Destroy`/timers/callbacks, analyse de la CI Windows de la branche et éléments de recette humaine déjà fournis.

L'environnement de cette passe ne fournit pas de poste Windows interactif avec la base Docker de recette. En conséquence, aucune interaction Windows 100/150/200 %, aucun clic métier et aucune validation Event Viewer n'est inventé : les scénarios non réellement exécutés sont marqués `NON TESTABLE`.

Le candidat humain `74d25fdd8431eb7a167ab35cab8e1e8aa4e3bdc9` est un SHA différent et divergent de la branche auditée. Ses observations sont conservées comme **signaux à reproduire**, mais ne valent pas validation de `maintenance/vanilla`.

La CI `Vanilla r2 - portable et installateur` de la branche valide compilation, test ciblé crashreport, import wxPython, construction PyInstaller/Inno Setup et démarrage de l'exécutable installé pendant 10 secondes. Elle ne teste pas les commandes métier, la fermeture/réouverture de dialogues, le clavier ni le DPI.

L'inventaire ci-dessous porte sur **36 commandes/parcours prioritaires de stabilisation** identifiés pendant cette passe. Il ne prétend pas constituer un inventaire exhaustif de toutes les centaines de commandes historiques du logiciel : une couverture exhaustive nécessitera un harness UI Windows automatisé.

## AUDIT 1 — Actions

| Écran | Action / bouton | Résultat | Symptôme | Gravité | Fichier / classe | Test / preuve |
|---|---|---|---|---|---|---|
| Noethys installé | Lancer l'exécutable installé | OK | Le processus reste vivant pendant le smoke test Windows | — | `.github/workflows/vanilla-r2.yml` | Run Windows exact SHA ; lancement 10 s |
| Liste détaillée des consommations | Ouvrir la liste | NON TESTABLE | Route menu présente ; ouverture exacte avec données non rejouée | — | `noethys/Noethys.py`, `DLG_Liste_consommations.Dialog` | Inspection route `On_conso_liste_detail_conso` |
| Liste détaillée des consommations | Afficher directement la liste complète | NON TESTABLE | Le constructeur appelle directement `OnParametre()` ; aucun contrôle « Voir tout » dans ce dialogue, mais rendu exact non rejoué | — | `DLG_Liste_consommations.Dialog` | Inspection source |
| Liste détaillée des consommations | Filtre année | NON TESTABLE | Binding présent, effet données non exécuté | — | `DLG_Liste_consommations.Dialog` | `EVT_CHOICE -> OnParametre` |
| Liste détaillée des consommations | Filtre activité | NON TESTABLE | Binding présent, effet données non exécuté | — | `DLG_Liste_consommations.Dialog` | `EVT_CHOICE -> OnParametre` |
| Liste détaillée des consommations | Recherche texte | NON TESTABLE | Handler temporisé présent ; cycle de vie non qualifié | MAJEUR (risque) | `CTRL_ObjectListView.BarreRecherche` | `wx.Timer` + `Recherche` inspectés |
| Liste détaillée des consommations | Double-clic / aperçu | NON TESTABLE | Handler dans l'ObjectListView, rendu PDF non exécuté | — | `OL_Liste_consommations.ListView` | Inspection bindings OLV |
| Liste détaillée des consommations | Bouton Aperçu | NON TESTABLE | Binding présent ; sortie non exécutée | — | `DLG_Liste_consommations.Dialog` | `EVT_BUTTON -> Apercu` |
| Liste détaillée des consommations | Bouton Modifier | KO | Le bouton est instancié mais n'est ni ajouté au sizer ni bindé : commande inaccessible | MAJEUR | `DLG_Liste_consommations.Dialog` | Inspection source confirmée |
| Liste détaillée des consommations | Supprimer sans sélection | NON TESTABLE | Chemin d'erreur présent, dialogue non exécuté | — | `OL_Liste_consommations.ListView.Supprimer` | Inspection source |
| Liste détaillée des consommations | Supprimer consommation déjà pointée | NON TESTABLE | Garde-fou présent, non exécuté | — | `OL_Liste_consommations.ListView.Supprimer` | Inspection source |
| Liste détaillée des consommations | Annuler suppression avec prestation liée | NON TESTABLE | Sur refus du premier dialogue, `Destroy()` n'est pas exécuté avant `return False` | MINEUR (risque) | `OL_Liste_consommations.ListView.Supprimer` | Inspection source |
| Liste détaillée des consommations | Imprimer | NON TESTABLE | Binding présent ; imprimante/PDF non exécutés | — | `DLG_Liste_consommations.Dialog` | Inspection binding |
| Liste détaillée des consommations | Export texte | NON TESTABLE | Binding présent ; fichier non généré | — | `DLG_Liste_consommations.Dialog` | Inspection binding |
| Liste détaillée des consommations | Export Excel | NON TESTABLE | Binding présent ; fichier non généré | — | `DLG_Liste_consommations.Dialog` | Inspection binding |
| Liste détaillée des consommations | Fermer pendant chargement puis rouvrir immédiatement | KO | Crash natif connu `0xc0000005`; branche actuelle ne nettoie ni timer ni FastObjectListView avant destruction | BLOQUANT | `DLG_Liste_consommations.py`, `CTRL_ObjectListView.py` | Recette humaine connue + vulnérabilité présente dans le code ; PR #359 ciblée |
| Liste détaillée des consommations | Croix Windows pendant chargement puis réouverture | NON TESTABLE | Même chemin vulnérable ; aucun `EVT_CLOSE`/nettoyage spécifique dans la branche | BLOQUANT (risque) | `DLG_Liste_consommations.Dialog` | Inspection source ; scénario exact à rejouer |
| Liste détaillée des consommations | Echap | NON TESTABLE | `wx.ID_CANCEL` existe ; destruction native/timer non qualifiée | MAJEUR (risque) | `DLG_Liste_consommations.Dialog` | Inspection source |
| Liste détaillée des consommations | Fermeture normale puis réouverture | NON TESTABLE | Aucun test répétitif disponible | MAJEUR (risque) | `DLG_Liste_consommations.Dialog` | Pas de test branche |
| Liste détaillée des consommations | Menu contextuel Aperçu | NON TESTABLE | Génération menu standard présente | — | `OL_Liste_consommations.ListView` | Inspection source |
| Liste détaillée des consommations | Menu contextuel Supprimer | NON TESTABLE | Binding dynamique présent ; action non exécutée | — | `OL_Liste_consommations.ListView` | Inspection source |
| Liste détaillée des consommations | Filtres avancés | NON TESTABLE | Route générique OLV présente ; non exécutée | — | `CTRL_ObjectListView.CTRL_Outils` | Inspection source |
| Liste détaillée des consommations | Configuration de liste | NON TESTABLE | Route OLV présente ; persistance non exécutée | — | `CTRL_ObjectListView` | Inspection source |
| Tableau de remplissage | Toolbar « Liste d'attente » | NON TESTABLE | Binding réellement présent et mène à `OuvrirListeAttente`; signal humain « aucun effet » sur candidat différent à reproduire sur la branche | MAJEUR (signal) | `DLG_Remplissage.ToolBar`, `Panel.OuvrirListeAttente` | Inspection binding + signal recette candidat |
| Menu Consommations | « Liste d'attente » | NON TESTABLE | Route `On_conso_attente -> ctrl_remplissage.OuvrirListeAttente` présente ; résultat exact non rejoué | MAJEUR (signal) | `noethys/Noethys.py`, `DLG_Remplissage.py` | Inspection source |
| Liste d'attente | Ouvrir fiche famille | NON TESTABLE | Binding présent ; parcours non exécuté | — | `DLG_Attente.Dialog` | Inspection binding |
| Liste d'attente | Imprimer | NON TESTABLE | Binding présent ; sortie non exécutée | — | `DLG_Attente.Dialog` | Inspection binding |
| Liste d'attente | Export Excel | NON TESTABLE | Binding présent ; sortie non exécutée | — | `DLG_Attente.Dialog` | Inspection binding |
| Liste d'attente | Fermer / Echap | NON TESTABLE | `wx.ID_CANCEL` présent ; cycle fermeture non rejoué | — | `DLG_Attente.Dialog` | Inspection source |
| Liste d'attente | Rafraîchir période/activité | NON TESTABLE | Dialogue reçoit les paramètres du remplissage ; rendu réel non rejoué | — | `DLG_Attente.py`, `DLG_Remplissage.py` | Inspection source |
| Remplissage | Actualiser | NON TESTABLE | Handler présent ; `MAJ()` peut programmer un `CallLater` global | MAJEUR (risque) | `DLG_Remplissage.Panel.MAJ` | Inspection source |
| Fenêtre principale | Fermer par la croix puis relancer | NON TESTABLE | `EVT_CLOSE -> Quitter`; seul timer autodeconnect est explicitement stoppé ; relance UI non automatisée | MAJEUR (risque) | `noethys/Noethys.py::MainFrame` | Inspection + smoke de démarrage uniquement |
| Fiche famille | Changer d'onglet puis fermer immédiatement | NON TESTABLE | `wx.CallLater(1, page.MAJ)` sans garde de destruction | MAJEUR (risque) | `DLG_Famille.Notebook` | Inspection source |
| Fiche famille | TAB / Shift+TAB / Entrée / Echap | NON TESTABLE | Aucun test clavier de branche | — | `DLG_Famille.Dialog` | Absence de test |
| Menus / barres personnalisées | « Pièces fournies » / « Pièces manquantes » | KO | Deux commandes différentes portent le même code `liste_pieces_fournies`; le dictionnaire par code écrase une entrée | MINEUR | `noethys/Noethys.py` | Inspection source confirmée |
| Noethys | Thème clair avec Windows sombre | NON TESTABLE | La branche lit un thème historique `CUSTOMIZE`; aucune qualification Windows dark/light exacte n'est disponible | MAJEUR (contrat non qualifié) | `noethys/Noethys.py`, `UTILS_Customize` | Inspection source ; validation Windows requise |

### Comptage actions

- Commandes/parcours prioritaires recensés : **36**.
- Actions avec preuve d'exécution disponible : **2** (1 smoke Windows au SHA exact ; 1 scénario humain de crash à reproduire sur le SHA exact).
- `OK` : **1**.
- `KO` : **3**.
- `NON TESTABLE` : **32**.

## AUDIT 2 — Crashs, exceptions et cycle de vie wx

| Fenêtre / classe | Scénario | Résultat | Erreur | Reproductible | Gravité | Fichier / classe | Test / preuve |
|---|---|---|---|---|---|---|---|
| Liste détaillée des consommations | Fermer pendant chargement puis rouvrir immédiatement, répétitions | CRASH CONFIRMÉ | Crash natif Windows `0xc0000005` / signal Application Error 1000 | Oui sur recette connue ; à rejouer sur build exact | BLOQUANT | `DLG_Liste_consommations.Dialog`, `FastObjectListView` | Recette connue ; PR #359 décrit le même défaut de cycle de vie |
| Liste détaillée des consommations | Fermer par la croix pendant chargement puis rouvrir | COMPORTEMENT SUSPECT | Même FastObjectListView/timer sans cleanup explicite | À confirmer | BLOQUANT | `DLG_Liste_consommations.Dialog` | Aucun `EVT_CLOSE` spécifique sur la branche |
| Recherche OLV | Saisir puis fermer avant expiration du timer | COMPORTEMENT SUSPECT | Callback `wx.Timer` possible pendant destruction | À confirmer | MAJEUR | `CTRL_ObjectListView.BarreRecherche` | Timer sans hook de nettoyage ; PR #359 le stoppe explicitement |
| Remplissage | Fermer/changer de fenêtre après planification MAJ auto | COMPORTEMENT SUSPECT | `wx.CallLater(..., self.MAJ)` global non annulé à la destruction | À confirmer | MAJEUR | `DLG_Remplissage.Panel` | Inspection `MAJ_AUTO_EN_ATTENTE` |
| Fiche famille / Notebook | Changer d'onglet puis fermer immédiatement | COMPORTEMENT SUSPECT | `wx.CallLater(1, page.MAJ)` peut viser un contrôle détruit | À confirmer | MAJEUR | `DLG_Famille.Notebook` | Inspection source |
| Fiche famille / Notebook | Pages masquées/configurées puis changement d'onglet | COMPORTEMENT SUSPECT | `event.GetOldSelection()` est indexé dans la liste canonique avant test `wx.NOT_FOUND`; index notebook et liste canonique peuvent diverger | À confirmer | MAJEUR | `DLG_Famille.Notebook.OnPageChanged` | Inspection source |
| Liste détaillée consommations | Base sans activité | COMPORTEMENT SUSPECT | `CTRL_Activite` retourne avant `SetItems`, puis `SetID(None)` tente `SetSelection(0)` | À confirmer | MAJEUR | `DLG_Liste_consommations.CTRL_Activite` | Inspection source |
| Suppression consommation | Refuser après avertissement prestation liée | COMPORTEMENT SUSPECT | Premier `wx.MessageDialog` non détruit avant `return False` | À confirmer | MINEUR | `OL_Liste_consommations.ListView.Supprimer` | Inspection source |
| Ticker présents | Fermer pendant timer actif | COMPORTEMENT SUSPECT | `wx.Timer` périodique sans hook explicite de destruction ; parentage wx peut suffire | À confirmer | MINEUR | `CTRL_Ticker_presents.CTRL` | Inspection source |

### Comptage crashs

- Crashs confirmés : **1**.
- Exceptions Python/wx confirmées : **0**.
- Comportements suspects : **8**.
- Faux positifs classés : **0** dans ce rapport ; les simples occurrences de `Destroy`, `EndModal`, etc. sans scénario crédible ne sont pas remontées.

### PR #359

La PR #359 est **ciblée et cohérente avec le défaut** : arrêt du timer de recherche, neutralisation du getter/cache de la liste virtuelle, remise du compteur natif à zéro, nettoyage idempotent et chemin de fermeture commun bouton/croix. Sa CI est verte, mais cela ne valide pas le crash natif.

Elle reste **NON VALIDÉE HUMAINEMENT** tant que le scénario suivant n'est pas passé sur le build Windows de recette : ouvrir la liste, laisser charger, fermer avant la fin, rouvrir immédiatement, répéter plusieurs fois, refaire par la croix Windows, puis vérifier l'absence d'Application Error 1000 / `0xc0000005` et de travail résiduel.

## AUDIT 3 — Windows, DPI, dimensions et scroll

| Fenêtre / classe | 100 % | 150 % | 200 % | Défaut | Impact | Fichier |
|---|---|---|---|---|---|---|
| Fenêtre principale `MainFrame` | NON TESTABLE | NON TESTABLE | NON TESTABLE | MinSize `935x740`; DPI awareness Windows commentée ; aucune recette multi-DPI disponible | Risque de zone utile insuffisante sur petit écran / fort scaling | `noethys/Noethys.py` |
| Liste détaillée des consommations | NON TESTABLE | NON TESTABLE | NON TESTABLE | **Défaut layout confirmé** : bouton Modifier créé mais absent du sizer ; MinSize `1030x700` | Commande Modifier inaccessible à tous les DPI ; risque supplémentaire de dépassement à fort scaling | `DLG_Liste_consommations.py` |
| Liste d'attente | NON TESTABLE | NON TESTABLE | NON TESTABLE | MinSize `805x600`, sizers growables présents ; comportement DPI réel non qualifié | Risque non confirmé | `DLG_Attente.py` |
| Fiche famille | NON TESTABLE | NON TESTABLE | NON TESTABLE | MinSize `960x710`, dialogue redimensionnable ; pas de recette 150/200 % | Risque non confirmé | `DLG_Famille.py` |
| Tableau Remplissage / Effectifs | NON TESTABLE | NON TESTABLE | NON TESTABLE | AUI MinSize panneau `580x200`; contenu dynamique ; aucun test de scroll/redimensionnement multi-DPI | Risque non confirmé | `noethys/Noethys.py`, `DLG_Remplissage.py` |
| Vanilla sous Windows configuré sombre | NON TESTABLE | NON TESTABLE | NON TESTABLE | Le thème historique est choisi via `CUSTOMIZE`; la garantie « Vanilla toujours claire » n'est pas qualifiée sur ce SHA | Contrat Vanilla à valider impérativement | `noethys/Noethys.py`, configuration interface |

### Comptage DPI/layout

- Défauts DPI/layout confirmés : **1** (défaut de layout du bouton Modifier).
- Défauts spécifiquement DPI confirmés : **0**, faute d'hôte Windows interactif 100/150/200 % pendant cette passe.

## Les 10 problèmes les plus pénalisants

1. Crash natif `0xc0000005` de la liste détaillée des consommations lors de fermeture pendant chargement puis réouverture.
2. Chargement potentiellement très coûteux des réponses de questionnaires : `GetReponses(type="individu")` charge globalement les réponses avant construction des lignes de consommations.
3. Bouton **Modifier** de la liste détaillée instancié mais invisible et sans binding.
4. « Liste d'attente » observée sans effet en recette humaine, alors que le binding statique existe : cause runtime non isolée sur le SHA exact.
5. Risque de mauvais mapping des pages dans `DLG_Famille.Notebook.OnPageChanged` lorsque des pages configurables sont masquées.
6. `wx.CallLater` de remplissage non explicitement annulé à la destruction.
7. Cas base sans activité : `SetSelection(0)` possible sur `wx.Choice` sans items réellement installés.
8. Identifiant de commande dupliqué pour « pièces fournies » / « pièces manquantes », incohérent avec les barres personnalisées basées sur un dictionnaire par code.
9. Couverture automatisée UI/wx quasi inexistante sur la branche : un seul fichier de tests cible le destinataire des crashreports.
10. DPI 100/150/200 %, clavier et contrat « thème clair même si Windows est sombre » non qualifiés automatiquement.

## Les 5 bugs à corriger en premier

| Priorité | Bug | Fichier/module probable |
|---|---|---|
| 1 | Crash fermeture/réouverture consommations | `noethys/Dlg/DLG_Liste_consommations.py`, `noethys/Ctrl/CTRL_ObjectListView.py`, `noethys/Ol/OL_Liste_consommations.py` |
| 2 | Lenteur questionnaire sur liste consommations | `noethys/Ol/OL_Liste_consommations.py`, `noethys/Utils/UTILS_Questionnaires.py` |
| 3 | Bouton Modifier invisible/non bindé | `noethys/Dlg/DLG_Liste_consommations.py` |
| 4 | Liste d'attente sans effet — à reproduire avant correction | `noethys/Noethys.py`, `noethys/Dlg/DLG_Remplissage.py`, `noethys/Dlg/DLG_Attente.py` |
| 5 | Mapping/callbacks différés de la fiche famille | `noethys/Dlg/DLG_Famille.py` |

## Tests automatisés manquants prioritaires

1. Harness Windows du build installé : ouvrir/fermer/réouvrir la liste des consommations en boucle, bouton et croix, avec fermeture pendant chargement.
2. Contrôle Event Viewer / code processus pour détecter `0xc0000005` et Application Error 1000.
3. Test de nettoyage `FastObjectListView` : getter/cache/item count et timer de recherche après fermeture.
4. Test structurel UI détectant les contrôles créés mais ni sizés ni bindés — doit attraper `bouton_modifier`.
5. Test d'unicité des codes de commandes du menu principal.
6. Test de route « Liste d'attente » depuis toolbar et menu jusqu'au `ShowModal()`.
7. Test liste détaillée des consommations sur base vide / zéro activité.
8. Test des `CallLater`/timers avec destruction immédiate du parent.
9. Test du notebook famille avec différentes combinaisons de pages masquées.
10. Test de non-régression « liste complète directement visible / pas de Voir tout ».
11. Tests clavier : Entrée, Echap, TAB, Shift+TAB sur dialogues prioritaires.
12. Tests export/impression avec ressources disponibles et ressources manquantes.
13. Harness captures/bounds Windows aux DPI 100/150/200 %, avec contrôle qu'aucun bouton essentiel n'est hors écran.
14. Test Windows en thème sombre vérifiant que Vanilla reste visuellement claire.

## Validations humaines encore obligatoires sous Windows

- PR #359 : scénario fermeture pendant chargement / réouverture immédiate répété, bouton puis croix, avec vérification Event Viewer.
- Ouvrir réellement « Liste d'attente » depuis toolbar et menu avec la base Docker de recette ; vérifier fenêtre utilisable et fermeture/réouverture.
- Confirmer la liste complète immédiatement visible et l'absence de comportement « Voir tout ».
- Vérifier Vanilla claire alors que Windows est configuré sombre.
- Recette 100/150/200 % sur fenêtre principale, consommations, attente, famille et remplissage : bornes écran, boutons, scroll, labels, redimensionnement, fermeture/réouverture.
- Parcours clavier Entrée/Echap/TAB/Shift+TAB sur les dialogues prioritaires.
- Aperçus, impressions et exports sur la base Docker de recette, y compris ressources manquantes.
- Fermeture complète de Noethys puis relance, sans timer/callback résiduel visible.

## Premier correctif unique recommandé après validation de cet audit

**Valider d'abord la PR #359 sur Windows avec le scénario natif exact. Si et seulement si cette recette passe, intégrer uniquement ce correctif ciblé de cycle de vie dans `maintenance/vanilla`, sans lui adjoindre le correctif de performance, le bouton Modifier ou tout autre changement.**

Aucune nouvelle correction issue du présent audit n'est autorisée avant validation de ce rapport.
