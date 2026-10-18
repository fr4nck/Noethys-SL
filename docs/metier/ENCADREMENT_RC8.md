# Encadrement previsionnel par site et creneau — chantier #429

**Statut : moteur partage et premiere interface de simulation en lecture seule sur les commandes de repas. Tests Windows et recette utilisateur a qualifier. RC8 non publiee.**

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

## Premiere interface de simulation (commandes de repas)

**Commandes de repas > Outils > Simuler les besoins en animateurs...** ouvre un dialogue **separe**. L'operateur choisit les colonnes de suggestion numerique couvrant les unites a analyser, puis renseigne explicitement le site, le creneau, le cadre d'accueil, la duree consecutive, un PEDT eventuel et le mode previsionnel/reel. Les enfants sont dedoubles entre unites du meme creneau. Les ages sont lus depuis les fiches individus **sans modifier la base** ; aucun nom de mineur n'est affiche ni exporte.

Il s'agit d'une **simulation temporaire**. Les choix de site et de creneau ne sont pas encore memorises dans un referentiel partage. L'operateur doit verifier que toutes les colonnes selectionnees correspondent au **meme site et au meme temps d'accueil**. Le total de repas d'une colonne ne remplace pas le nombre des enfants simultanement presents.

La simulation affiche un resultat par date. Elle n'ajoute aucune ligne a la commande, ne modifie pas le PDF restaurateur, les repas adultes ni les affectations de personnels. L'avertissement « age inconnu » designe un calcul incomplet.

**Limites** : la verification sur un poste Windows reel est a faire ; les horaires de presence exacts et leur chevauchement ne sont pas lus. Le classement du mercredi et des vacances, la mutualisation de direction et la validation des regimes restent des parametres declares, pas des controles reglementaires automatiques. Aucun nombre d'animateurs n'est actuellement injecte dans les commandes de repas ou le PDF restaurateur.

Le raccordement futur necessite un parametrage persistant de site/creneau independant des colonnes du restaurateur, ainsi qu'une lecture de presence horaire si elle est disponible.

Les tests unitaires sont dans tests/test_noethys_sl_encadrement.py ; ils ne lisent aucune base ni aucune donnee des familles. Avant recette RC8 : tests sur base fictive, interface Windows reelle, controle des creaneaux qui se chevauchent et qualification du dispositif de direction multisite (#429/#430).
