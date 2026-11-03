# Noethys SL 0.1.0 RC10.5 — candidat cumulatif (non publie)

Statut : **candidat de consolidation sur `wx`**. Ce fichier sert de liste
de contenu pour la prochaine preversion. Il ne certifie ni une installation
Windows deja diffusee, ni la resolution des incidents de production.

## Correctifs retenus

- **#438 — fermeture Connecthys** : liberation explicite du canal SFTP et
  de la session `paramiko.SSHClient` sur les chemins normaux et en erreur.
  Les attentes de 1 et 30 secondes du worker Connecthys sont interruptibles.
  La fermeture acceptee arrete le worker ; une sauvegarde annulee ne le stoppe
  pas et conserve la fenetre ouverte.
- **S1 — securite du client Connecthys (opt-in)** : champ facultatif
  `ssh_host_key_sha256` (empreinte SHA256 de la cle publique hote verifiee
  independamment) ; une autre cle est rejetee pendant l'echange SSH, avant
  l'authentification. Les deux clients SSH du produit utilisent ce controle.
  Si le champ est vide, politique historique inchangee : le serveur
  Connecthys d'Ivan Lucas ne requiert aucune mise a jour. Les messages de
  diagnostic n'affichent plus les URL contenant les jetons de synchronisation.
- **S1 — empreinte facultative du code `models.py`** : l'administrateur
  peut renseigner `models_sha256` (64 caracteres hexadecimaux, releves
  independamment du serveur de transfert). Le client compare le SHA256 des
  octets du fichier telecharge **avant son execution**, puis compile les
  memes octets verifies. Le champ vide preserve exactement la lecture
  historique. Une mise a jour officielle du fichier impose de confirmer
  puis de mettre a jour cette empreinte.
  **Limite importante** : la verification couvre seulement `models.py`,
  et non les modules Python annexes qu'il peut importer. Elle ne
  constitue ni un bac a sable ni une signature d'origine.
- **S1 — secrets de config.py** : generation du fichier temporaire
  avec droits restreints (0600 sur POSIX), puis effacement apres tentative
  d'envoi, meme si l'upload echoue. Un transfert ou un reload WSGI connu
  en echec n'est plus annonce comme succes. La copie telechargee du
  serveur pour comparaison est aussi supprimee apres lecture.
  Aucun changement du contenu attendu par Connecthys Ivan Lucas.
- **S1 — droits distants facultatifs** : `ssh_config_prive` est
  **desactive par defaut**. Si explicitement active en SSH/SFTP,
  `application/data/config.py` est passe en mode `0600`, meme lorsque
  le contenu est inchange ; un echec des permissions est signale.
  `0644` reste le comportement historique sans cette option.
  Cette option exige une validation prealable de l'utilisateur
  qui fait tourner le serveur web (WSGI) : si ce compte n'est pas
  proprietaire, Connecthys peut devenir inaccessible. Le transfert
  historique n'etant pas atomique, les droits peuvent rester plus
  ouverts pendant la copie : **ceci n'est pas un remede complet**.
- **S1.4 — publication atomique de config.py (SSH/SFTP)** :
  `ssh_config_atomique` est **desactive par defaut**. En mode volontaire,
  le nouveau fichier est ecrit sous un nom temporaire aleatoire du meme
  dossier, marque `0600` avant l'ecriture des octets secrets, relu en
  entier et compare par SHA256, puis publie avec l'extension OpenSSH
  `posix-rename`. Tant que cette derniere operation n'a pas reussi,
  l'ancien `config.py` n'est pas ecrase par ce chemin de code.
  **Pas de repli silencieux sur l'ecrasement traditionnel** : si
  l'extension n'est pas prise en charge, le transfert est declare en
  echec et une suppression du fichier de staging est tentee.
  Le nouveau fichier adopte `0644` pour le lecteur web historique, ou
  `0600` uniquement si `ssh_config_prive` est aussi active, apres
  recette des droits. L'etape finale est atomique **seulement si le
  serveur implemente correctement posix-rename**. Il reste possible
  qu'un fichier temporaire subsiste en cas de rupture du serveur lors
  de sa suppression ; aucune garantie d'isolement du serveur lui-meme.
  Cette option ne demande aucune modification de Connecthys mais
  suppose une capacite SFTP disponible chez l'hebergeur.
- **#437 — sauvegardes MySQL** : conservation de l'export `mysqldump` surveille
  (sans `shell=True`, delais bornes et diagnostic), de la verification SQL et
  de la protection des anciennes archives. Le blocage `*_DOCUMENTS` de
  production et la validation d'une sauvegarde PMSL restaurable restent ouverts.
- **#426 — facturation** : lecture SQL stricte (pas de faux zero), message
  indiquant la table et la cause MySQL sans divulguer la requete complete,
  et un unique second essai de SELECT hors pool sur rupture reseau identifiee
  (codes 2006, 2013, 2014, 2055). Une erreur de schema ou de droits bloque
  toujours le controle ; aucune cotisation n'est ajoutee implicitement.
  La cause constatee sur `pelemele` n'est pas etablie sans nouvel essai terrain.
- **#436 — fiche enfant** : conservation des formulaires, du filtrage des
  donnees sensibles selon habilitations et du registre des autorisations.
- **Situation ALSH des communes** : conservation du choix explicite des
  absences injustifiees, separees des presences et des participations,
  sans activation implicite.

D'autres correctifs pourront rejoindre cette RC10.5 avant gel du SHA.
Les travaux non qualifies sur `wx` ne sont pas annonces comme correctifs
valides par la presente note.

## Barriere Windows avant publication

La validation du **vrai** serveur Connecthys historique n'est pas realisee
par les tests de cles publiques et fichiers Python factices. Ne pas
activer les empreintes SSH ou `models.py` sur le profil PMSL avant
verification independante par l'hebergeur ou le distributeur du code,
puis qualification dans un profil de recette.

1. CI rapide Windows `wx` PASS sur le SHA exact retenu, y compris fermeture
   Connecthys, controle des autorisations et garde-reseau.
2. Construction `noethys-sl-rc105-windows.yml` avec `publier=false` :
   identité 0.1.0 RC10.5, verifications du binaire, de son demarrage,
   du profil portable, des clients MySQL 5.7 et des empreintes SHA-256.
3. Recette MySQL 5.7 **jetable** avec gros BLOB, sauvegarde et restauration.
   Elle ne vaut pas preuve de sauvegarde complete de la base PMSL.
4. Sur un poste Windows de recette, fermer Noethys apres une session
   Connecthys et prouver la disparition du PID et des connexions SSH.
   Qualifier le comportement en cas de synchronisation en cours.
5. Accord explicite de publication depuis `wx` seulement, apres les
   barrieres precedentes ; aucun `push` ne publie une release.

Une configuration initiale en lecture seule / une sauvegarde
du fichier distant doit etre disponible avant de tester en recette les
options `ssh_config_prive` et `ssh_config_atomique`.
N'activer ni l'une ni l'autre en production avant qualification du
processus web, du serveur SFTP et de la procedure de retour arriere.

## Compatibilite Connecthys Ivan Lucas — CONTRAT NON REGRESSION

La compatibilite avec le **Connecthys historique d'Ivan Lucas** est une
exigence bloquante pour RC10.5 et les versions suivantes. Le renforcement
de la securite du client Noethys-SL ne doit pas exiger une modification ou
une mise a jour du serveur Connecthys de l'association.

- Conserver le protocole des synchronisations ascendantes/descendantes,
  les URL et commandes du Connecthys existant, les noms de fichiers et
  bases, les formats `models.py`, `config.py` et le format chiffre `SV2`.
- Ne jamais activer `ssh_config_prive` sur PMSL sans
  avoir teste sur un serveur isole les droits de lecture de WSGI et la
  procedure de retour arriere.
- Conserver les modes d'hebergement deja pris en charge : local, FTP et
  SSH/SFTP. Ne pas imposer unilateralement HTTPS, un nouveau port ou un
  nouveau mode d'authentification au serveur historique.
- Maintenir le fonctionnement des cles et secrets deja configures, sans
  les reinitialiser et sans migration de base ou de profil de production.
- Renforcer les verifications **cote client** sans changer les donnees
  echangees : fermeture des transports, controles d'integrite et
  journalisation sans secrets. Pour la cle hote SSH, une **empreinte SHA256
  facultative** peut etre saisie dans Parametrage > Connecthys > SSH/SFTP,
  uniquement apres une validation independante par l'hebergeur. Aucune
  empreinte n'est acceptee automatiquement comme preuve de confiance :
  la relever par la seule connexion suspecte ne garantit rien.
  Une empreinte saisie refuse les cles differentes, sans modification du
  serveur ni de son protocole ; champ vide = compatibilite historique
  avec `AutoAddPolicy`, qui reste un risque residuel explicite.
- Le chargement de `models.py` fait partie du protocole actuel et
  execute du code distant. Le champ facultatif `models_sha256` refuse
  l'execution d'un **models.py** dont les octets ne correspondent pas a une
  empreinte verifiee hors bande. Cette empreinte ne couvre **pas** les
  imports relatifs de code annexe et n'isole pas Python. Qualifier les
  dependances ou un ensemble de sources complet avant de presenter ce
  mecanisme comme une preuve d'origine du code execute.
- Moderniser le chiffrement uniquement avec **lecture/ecriture legacy
  interoperable** pour Connecthys : un nouveau format ne peut pas devenir
  obligatoire tant que le Connecthys original ne le comprend pas. Isoler
  strictement les lectures d'anciennes sauvegardes de celles de fichiers
  non fiables venant du reseau.
- Pour toute correction, recette de synchronisation complete **montante
  et descendante** contre une installation de la version historique
  effectivement utilisee, en environnement de test, sans effacer ni
  reinitialiser les donnees reelles. Echecs de compatibilite = blocage
  de publication.

Ce contrat ne signifie pas que toutes les anciennes options sont sures.
Les risques residuels (FTP non chiffre, acceptation des cles hote inconnues
et code recu du portail) doivent etre identifies et reduits avec un
mode de migration valide, plutot que masques ou changes sans essai.

## Compatibilite et limites

- Version publique : `0.1.0-rc.10.5` ; version interne Noethys :
  **`1.3.4.4` inchangee**, sans migration SQL.
- Identifiant d'installation Inno Setup conserve pour les mises a jour
  existantes. Ne pas effacer le profil de production.
- La RC10.4 deja installee ne recoit **aucune** correction retroactive.
- Les tickets [#437](https://github.com/fr4nck/Noethys-SL/issues/437)
  et [#438](https://github.com/fr4nck/Noethys-SL/issues/438)
  restent ouverts jusqu'a validation terrain.
