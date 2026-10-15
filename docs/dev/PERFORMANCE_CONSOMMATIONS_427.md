# Qualification synthetique des consommations — 15/10/2026

## Sources et environnement

Depart distant verifie : main `0b2e2d47b2a899bc650cc6ec1090b67129897dbe`,
wx `23a49c7d129d7ce7c6167437c6fb939eaa835e53`,
qt `9f27a1378ce28c96f79e8ff5d080e2f3d77b45c1`.
CTRL_Grille.py, GestionDB.py et les deux handlers OK sont identiques sur ces
trois sources. Les arbres complets divergent (interfaces, packaging, documents,
autres correctifs) : aucune fusion globale ni remplacement d'arbre autorise.
Les CI anterieures main 38724108383 et wx 38724128232 sont SUCCESS aux SHA
f04e68a et 23a49c7 respectivement.

Mesures Windows, Python 3.11.9, neuf repetitions par cas, mediane du temps
client de Sauvegarde ; compilation AST, construction des donnees et imports
exclus du chronometrage. Le harnais compile la methode reelle mais remplace DB
et historique par des doubles. Aucun import applicatif, profil ni reseau.
Ce ne sont ni des mesures serveur ni une recette utilisateur. Les donnees
sont fabriquees integralement ; aucun fichier Portable existant n'est utilise.

## Audit precis et risques

- Sauvegarde ouvre une DB puis traite prestations/deductions/ventilation,
  consommations, memos et historique. Une consommation modifiee reecrit
  vingt champs, dont verrouillage=0 et IDprestation nullable. Modifier
  seulement etat n'est pas equivalent au contrat actuel. Une valeur chargee
  sur le poste A peut ecraser un champ change entre-temps par B : risque
  preexistant, sans detection de version. Ne pas presenter ce lot comme une
  resolution des conflits simultanes sur la meme consommation.
- Executermany adapte ? et %s selon SQLite/MySQL et laisse les exceptions
  remonter. Contrairement a ExecuterReq (qui capture les erreurs et renvoie 0),
  une erreur dans ce chemin interrompt Sauvegarde. Un UPDATE de lot par CASE,
  jointure ou table temporaire changerait ordre, verrous, limites de paquet,
  declencheurs et comportement d'erreur partielle : recette MySQL requise.
- La sauvegarde valide les consommations avant les memos/historiques ;
  InsertActions(DB=DB) fait lui-meme un Commit, puis Sauvegarde en fait un
  autre. Ces frontieres sont conservees ; retirer un Commit n'est pas une
  optimisation neutre. GetProchainID predit des ID d'auto-increment pour les
  prestations/deductions : allocations concurrentes a qualifier separement.
- MySQLdb ouvre une connexion par DB, puis USE. Le pooling de mysql.connector
  n'est pas celui du pilote par defaut MySQLdb ; aucun pooling ajoute ici.
  SauvegardeTransports evite deja la connexion sans changement. Les parametres
  ouvrent encore une DB pour SELECT puis eventuelles ecritures ; leur lecture
  voit les modifications d'autres postes. Un cache de valeurs initiales qui
  eviterait ce SELECT modifierait cette semantique partagee.
- Les handlers OK couvrent sauvegarde, transports, parametres et fermeture.
  DLG_Famille.OnBoutonConsommations appelle MAJpageActive apres le retour modal :
  ce rechargement est hors du contexte actuel du profileur. Une trace OK rapide
  n'exclut donc pas une lenteur de rafraichissement apres fermeture. Aucun
  rafraichissement ni evenement wx supprime dans ce lot.

## Reproduction du pilote, sans serveur

Source officielle inspectee :
[mysqlclient v2.2.7, cursors.py](https://github.com/PyMySQL/mysqlclient/blob/v2.2.7/src/MySQLdb/cursors.py),
SHA256 `ed8a93fed04ee66ba446d3b6b3d49aaa5513b29eed276c16b741fafb58a5469c`.
Cette version sert de reference reproductible ; requirements.txt n'epingle
pas mysqlclient, la version du binaire RC7.2 n'est pas deduite de cette source.

Le benchmark compile uniquement executemany, _do_execute_many et la regex
originales depuis un fichier fourni explicitement. Le transport est un double :

| Lignes | UPDATE : appels transport | INSERT : appels transport |
| --- | --- | --- |
| 1 | 1 | 1 |
| 10 | 10 | 1 |
| 50 | 50 | 1 |

Il confirme le fallback UPDATE ligne par ligne pour cette source du pilote,
pas une latence reseau mesuree. Reduire les colonnes ne retire pas ces appels.
Docker present mais moteur local indisponible : aucun serveur existant contacte,
demarre ou modifie. Pas de qualification MySQL serveur dans ce lot.

## Lot retenu : preparation des seules consommations a ecrire

Eviter la construction de vingt valeurs et la conversion des etiquettes sur
les consommations inchangees. Conserver explicitement les suppressions implicites
etat=None avec IDconso, les suppressions multihoraires hors grille, tous les
ajouts/modifications/suppressions, les SQL et frontieres transactionnelles.
Le parcours de la grille reste lineaire, mais le travail par ligne inchangee
est reduit a la verification du statut et de la suppression implicite.

| Lignes chargees | Modifications | Avant (ms) | Apres (ms) |
| --- | --- | --- | --- |
| 50 | 1 | 0,230 | 0,078 |
| 50 | 10 | 0,264 | 0,139 |
| 50 | 50 | 0,426 | 0,426 |
| 10 000 | 1 | 33,073 | 2,120 |
| 10 000 | 10 | 32,712 | 1,906 |
| 10 000 | 50 | 33,216 | 2,299 |

Ajouts : pour 10 000 lignes chargees, respectivement 1/10/50 ajouts :
33,225/32,700/33,452 ms avant, 1,781/1,944/2,747 ms apres. A chaque cas : un
appel Executermany et trois Commit du harnais avant comme apres. Ces temps
incluent les copies des doubles ; ne pas extrapoler un facteur de gain sur OK.

## Tests et reproduction

- Huit tests nouveaux : lignes inchangees sans conversion, SQL/NULL/vingt
  champs, mix ajout/modification/suppressions et historique/frontieres,
  suppression multihoraire, exception avant Commit, adaptation des deux
  dialectes, deux connexions et deux threads SQLite (attente du verrou).
- Comparaison differentielle sur 45 combinaisons statut/etat/ID : memes SQL,
  valeurs, historique, commits et erreurs que le fichier de depart (y compris
  erreurs preexistantes sur entrees incoherentes). Pas de copie de moteur
  metier dans les tests.
- Suite locale Python 3.10/wx : 67 tests, OK, deux skips MySQL faute de serveur.
  Inclut transports/profilage anterieurs, adhesions/coupe-circuit P1/concurrence,
  garde tarification et fermeture des deux interfaces de consommations.
  Syntaxe compilee. Les nouveaux tests sont ajoutes a la CI rapide.

Depuis la racine du depot, extraire le fichier initial avec Git vers un fichier
UTF-8 hors sources applicatives, puis :

```text
python scripts/benchmark_grille_synthetic.py --source <fichier_initial>
python scripts/benchmark_grille_synthetic.py
python scripts/benchmark_grille_synthetic.py --compare-source <fichier_initial>
python scripts/benchmark_grille_synthetic.py --driver-source <cursors.py_v2.2.7>
python -m unittest tests.test_noethys_sl_grille_synthetic -v
```

Les sorties brutes et sources de mesure sont dans qualification/ de la copie
locale de travail, hors commit ; les chiffres utiles et provenance sont ici.

## STOP-GATE et prochaine qualification

Pas de modification SQL, tarification, historique, facturation, annulation,
commit, pooling, migration ni adhesion automatique. RC7.2 ffd28de ne contient
aucun des lots #427. Aucun nouvel installateur : le gain client de quelques
dizaines de ms ne suffit pas a justifier seul un deploiement.

Prochaine etape : serveur MySQL/MariaDB jetable sur donnees generees, pilote
et version explicites, 1/10/50 changements et ajouts, erreurs a mi-lot,
concurrence meme ligne/lignes disjointes et ID de prestations, NULL, rollback,
facturation et historique. Ensuite seulement envisager un lot SQL distinct.
Le profileur NOETHYS_SL_PROFILE_CONSOS=1 peut etre active avant lancement sur
un profil de recette exclusivement synthetique et isole. Le journal anonyme
local permet de distinguer consommations/transports/parametres ; aucun essai
contre production. Pour mesurer le retour fiche famille, instrumenter aussi
le rafraichissement post-modal dans un prochain lot independant. Recette wx
Windows et Qt specifique restent necessaires avant qualification de release.
