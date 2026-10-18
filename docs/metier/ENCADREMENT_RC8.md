# Encadrement previsionnel par site et creneau — chantier #429

**Statut : moteur Python pur qualifie par tests unitaires, non raccorde a l'interface ni a une base utilisateur. RC8 non publiee.**

## Regles de calcul

- Le calcul est realise **par date, site et creneau explicites**. En configuration PMSL, matin (4 h), midi (repas, temps independant) et apres-midi (4 h) peuvent etre trois creneaux differents. Le fait qu'une journee comporte 2 x 4 heures ne conduit pas a sommer les besoins simultanes.
- Periscolaire : **5 heures consecutives exactement** est classe dans la tranche courte (et non dans >5 h). Taux hors PEDT : <6 ans **1/10** et 6 ans ou plus **1/14** ; au-dela de 5 heures : **1/8** et **1/12**.
- PEDT : jamais actif par defaut. Si explicitement applicable, taux **1/14 et 1/18** pour 5 h au plus ; **1/10 et 1/14** au-dela.
- Extrascolaire : **1/8** avant six ans et **1/12** a partir de six ans.
- L'age est calcule a la **date d'accueil**, jamais a la date actuelle ; six ans revolus appartient a la tranche 6+.
- Les deux effectifs de mineurs sont arrondis **separement au superieur**, puis additionnes. Il s'agit d'une **suggestion prudente** et non d'une attestation de conformite, qui depend aussi des personnels, de leurs qualifications, des activites et du cadre declare.

Sources reglementaires : [R227-15](https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000006905540) et [R227-16](https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000037247312) du code de l'action sociale et des familles. Les taux PEDT ne sont utilisables que lorsque les conditions legales sont effectivement remplies.

## Donnees attendues

Le moteur noethys/Utils/UTILS_Encadrement.py expose CalculerEncadrement(consommations, individus, unites_config, mode).

- consommations : dates, identifiants d'enfants/personnes, groupes, unites et etats ; les personnes nommees ne sont ni conservees dans le resultat ni affichees.
- individus : date_naiss, indicateur est_adulte facultatif pour les personnels dont la fiche est incomplete.
- unites_config : affectation **explicite** des couples (IDgroupe, IDunite) vers site, creneau, cadre d'accueil, duree consecutive et PEDT eventuel. Le logiciel **ne deduit pas** le site ni le regime du nom d'une activite, du jour de la semaine ou d'une commande de repas.
- mode previsionnel : reservations + presents ; mode reel : presents uniquement. Les absences sont exclues.
- une personne ne compte qu'une fois **dans un meme site et creneau** malgre plusieurs unites. Un conflit de site pour la meme personne/jour/creneau est signale.
- les adultes (dont directeur, adjoint et stagiaire adultes) sont exclus des besoins en animateurs ; leurs **repas** restent un calcul completement independant (#430).
- date de naissance absente ou incoherente : categorie **age inconnu**, avec calcul_complet=False ; ne jamais presenter la suggestion comme exhaustive.
- unite sans affectation, cadre inconnu, PEDT incoherent ou taux contradictoires sur le meme site/creneau : erreur explicite au lieu d'un calcul trompeur.

## Integration ulterieure

Le raccordement necessite un parametrage de site/creneau qui ne soit pas confondu avec le parametrage des colonnes du restaurateur, ainsi qu'une lecture de la base en lecture seule et un affichage separe. **Aucun nombre d'animateurs n'est actuellement injecte dans les commandes de repas ou le PDF restaurateur.**

Les tests unitaires sont dans tests/test_noethys_sl_encadrement.py ; ils ne lisent aucune base ni aucune donnee des familles. Avant recette RC8 : tests sur base fictive, interface Windows reelle, controle des creaneaux qui se chevauchent et qualification du dispositif de direction multisite (#429/#430).
