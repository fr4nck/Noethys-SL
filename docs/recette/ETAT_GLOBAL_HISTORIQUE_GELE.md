# État global des consommations — comportement historique figé

**Décision PMSL du 4 novembre 2026 : ne plus modifier cette fenêtre ni ses règles
de sélection sans demande explicite de la direction.**

Ce panneau est un **outil de contrôle indépendant** des déclarations AFAS V2.
Il doit rester disponible dans sa forme historique, avec la compatibilité
Python 3 et wxPython Phoenix actuelle.

## Comportement obligatoire

- Sélection libre, par clic, des quatre états **Pointage en attente
  (`reservation`), Présent (`present`), Absence justifiée (`absentj`)
  et Absence injustifiée (`absenti`)**.
- Réutilisation des profils enregistrés **à l'identique**, y compris les
  profils « Caf - Périscolaire » et « Caf - Extrascolaire ».
- **Aucune** correction silencieuse d'état au chargement d'un profil.
- **Aucune** alerte « Profil CAF historique : sélection corrigée » lors
  de l'ouverture ou du chargement.
- **Aucun** refus d'aperçu PDF pour le seul motif que l'utilisateur a
  sélectionné plusieurs états.
- Sélecteur natif historique `wx.MultiChoiceDialog` ; conserver
  l'identité des codes enregistrés et le fonctionnement Annuler/OK.
- Bandeau, boutons, profils et présentation historiques conservés.
- Le moteur `CalculateurEtatGlobal` reste modernisé en Python 3/wxPython.

## Protection automatique

- `tests/test_noethys_sl_etat_global_historique.py` : contrat d'interface,
  de sélecteur et de chargement des profils.
- `tests/test_noethys_sl_etat_global_calcul.py` : calcul sans restriction
  d'état supplémentaire.
- `tests/test_noethys_sl_afas_profils_historiques.py` : absence de
  réécriture automatique dans l'interface historique.

Ces tests sont appelés dans la **CI Windows rapide**. Une intervention AFAS
ne doit pas les assouplir, les supprimer, ou changer cette interface. Les
règles spécifiques CAF doivent être appliquées uniquement dans le module
`UTILS_AFAS2_*` et la fenêtre `DLG_AFAS2_Declarations`.

## Comparaison avec AFAS V2

Pour tester un écart de volume sur les mêmes périodes et groupes, produire
successivement l'état global **Présent seul** et **les quatre états**, en
conservant la même sélection d'activités et d'unités. Le détail obtenu
permet de détecter les réservations ou absences facturées absentes du contrôle.
Les catégories repas, garderies et accueil peuvent porter plusieurs
consommations pour un même enfant et une même journée : ne pas additionner
leurs coefficients pour comparer directement aux heures CAF.

L'état global est un **contrôle contradictoire**, pas une déclaration CAF
officielle ; il ne faut pas confondre le filtre libre de ce rapport avec
les rubriques distinctes du formulaire CAF. Aucune donnée de production
n'est modifiée par ces vérifications.
