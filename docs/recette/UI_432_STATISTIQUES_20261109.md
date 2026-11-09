# UI-432J — Statistiques : correctif borne et inventaire transversal (09/11/2026)

## Statut et preuves initiales
- Issue de suivi : [#432](https://github.com/fr4nck/Noethys-SL/issues/432).
- Nouvelle observation utilisateur du 9 novembre : perte involontaire de maximisation pendant l'ouverture des statistiques ; capture montrant « Actualisation des données… » sur la page Individus / Age, periode annuelle 2026, deux activites selectionnees. La capture **ne prouve pas** a elle seule un evenement d'iconisation Win32.
- Base de ce lot : `wx=14f372dfbd0e3f71999d3215079cc2f6d097dbb2` ; `main=07d672a2e4b414cfeef8911b8b9285d05f32cb21` ; `qt=b6bc25ba7ac5cd42aeeff0a8874a727f132a5482`.
- La precedente CI [#42592740688](https://github.com/fr4nck/Noethys-SL/actions/runs/42592740688) a echoue : quatre erreurs `UnboundLocalError` dans le parcours PDF (boucle `for _ in generer()` masquant la traduction `_(...)`) et une assertion de titre encore fixe a RC10.5 quand le produit affiche RC10.55. Ne pas revendiquer un etat initial CI PASS.

## Chaine technique prouvee dans le code initial
1. `Noethys.MainFrame.On_outils_stats` instancie `DLG_Stats.Dialog(self)`, appelle `ModificationParametres(premiere=True)`, puis seulement `ShowModal()`.
2. `ModificationParametres` invoquait `MAJpageAffichee()` immediatement : le **premier calcul precedait l'affichage** de la fenetre Statistiques.
3. `DLG_Stats.MAJpage` ouvrait une attente `UTILS_Attente.BusyInfo(..., None)`, puis effectuait SQL, graphes et HTML synchroniquement, avec destruction de l'attente seulement sur sortie normale.
4. `UTILS_Stats_modeles.HTML.MAJ` conservait une connexion DB pendant toute l'actualisation et ne garantissait pas `DB.Close()` en cas d'exception. `GetFigure` retournait depuis la boucle sans fermer cette connexion.
5. `DLG_Stats.Imprimer` pouvait retourner lors d'une selection vide sans detruire la fenetre d'attente.

**Qualification :** risques de blocage et de fenetres non parentees **CONFIRMES PAR LECTURE DU CODE** ; attribution de la minimisation observee a chacun de ces mecanismes **NON DEMONTREE**.

## Modifications du candidat
- Le premier calcul est planifie par `wx.CallAfter` apres l'ouverture de la boite Statistiques.
- Lorsque Stats est visible, `MAJpage` utilise `UTILS_Etapes_ui.Executer` avec une fenetre modale dont Stats est le parent. Le moteur `HTML.MAJ_etapes` calcule les objets un par un et rend la main a wx entre deux objets. La methode publique `HTML.MAJ` conserve son comportement synchrone historique pour les autres appelants, dont l'impression.
- Les operations SQL, matplotlib et wx restent **sur le meme thread graphique** et sont seriees. Connexions et figures inutilisees liberees par `finally`, y compris en cas d'interruption de l'iterateur.
- L'attente du chemin synchrone de secours et celle de l'impression sont maintenant parentees, avec destruction contextuelle.
- Diagnostic opt-in `NOETHYS_SL_UI_DIAG=1` : `statistiques.actualisation`, `statistiques.rendu_html`, `statistiques.objet` ; aucun nom, identifiant, valeur, SQL ou chemin de document.
- Correction de l'erreur `for _ in generer()` et adaptation du contrat de titre a `Identite.PRODUCT_VERSION_DISPLAY` **sans changer la version interne de compatibilite**.
- Un outil `tools/ui432_audit_transversal.py` inspecte la syntaxe des modules de `Dlg`, `Ctrl`, `Ol`, `Utils` et `Noethys.py`, sans importer Noethys ni ouvrir une base. Les categories sont des **signaux a trier**, et non des preuves de bug.

## Inventaire transversal reellement execute en CI

Le scanner de syntaxe statique a termine **PASS** dans [GitHub Actions #42597225620](https://github.com/fr4nck/Noethys-SL/actions/runs/42597225620) : **1 070 modules**, **219 signaux**, **0 erreur d'analyse**.

| Categorie | Signaux |
|---|---:|
| SQL dans fonctions de type handler | 134 |
| Attentes sans parent explicite | 58 |
| wx.Yield potentiel dans handlers | 11 |
| Progressions sans parent explicite | 7 |
| Reseau potentiellement synchrone | 5 |
| time.sleep potentiel dans handlers | 3 |
| Modification explicite d'etat de fenetre | 1 |

Les indicateurs ci-dessus **ne constituent pas 219 anomalies demontrees** : la semantique de chaque appel et son thread d'execution doivent etre etablis.

Triage manuel des cinq principaux signaux reseau :
- **P1 potentiel** : `Dlg/DLG_Saisie_email_exp.py::OnBoutonTester` appelle `Connecter` et `Envoyer` sur son chemin UI.
- **P1 potentiel** : `Dlg/DLG_Envoi_sms.py::EnvoyerEmail` comporte une connexion/envoi synchrones et un dialogue d'erreur `parent=None`.
- **P1 potentiel** : `Utils/UTILS_Rapport_bugs.py::Envoyer_mail` effectue une connexion et un envoi synchrones depuis son dialogue.
- **A analyser, sans reecriture automatique** : `Dlg/DLG_Mailer.py::Envoyer` a deja des workers hors UI dans les voies principales ; classifier les chemins secondaires avant modification.
- **Le moteur n'est pas necessairement un handler UI** : `Utils/UTILS_Envoi_email.py::Envoyer_lot`, dont le thread depend de l'appelant.

**Decision** : aucun changement des moteurs d'envoi dans UI-432J. Le prochain lot doit utiliser des transports fictifs et verifier les garanties anti-double envoi avant de transformer ces parcours.

## Barriere de recette
- Contrats fictifs : `tests.test_ui432_statistiques`, `tests.test_ui432_audit_transversal`, precedents `tests.test_ui432_factures_proprietaire`, `tests.test_stats_modeles_mode_contract` et tests des fenetres.
- **Reste a verifier** : CI rapide Windows sur ce candidat ; vrais HWND et `GW_OWNER` ; reaction de `IsHungAppWindow` lors d'une requete lente ; comparaison du rendu et des totaux statistiques sur donnees fictives ; relecture d'une vraie navigation statistiques/Connecthys/factures ; recette utilisateur.
- **Limite structurelle ouverte :** un appel SQL ou un rendu graphique individuel de plus de cinq secondes bloque toujours le thread wx pendant *cet objet*. Le fractionnement inter-objets n'est pas une resolution generale ni une preuve d'absence de fenetre fantome.
- **Autre limite :** l'impression multi-page conserve l'ancien calcul synchrone. Le parentage du `wx.PreviewFrame` appelle une qualification Windows specifique avant modification.
- Aucun envoi reel, aucune base PMSL, aucune migration SQL, aucun tag, installateur ou release. `main` et `qt` non modifies.

## Matrice de portabilite
| Branche | Etat au debut du lot | Interpretation |
|---|---|---|
| wx | candidat en preparation ; tests Windows a suivre | logique de dialogue specifique wx |
| main | non modifie | parties moteur commun a qualifier independamment |
| qt | non modifie | widget wx non applicable ; pas de propagation automatique |

**Verdict provisoire : CORRECTIONS CANDIDATES / VALIDATION WINDOWS ET UTILISATEUR EN ATTENTE.** Garder l'issue #432 ouverte.
