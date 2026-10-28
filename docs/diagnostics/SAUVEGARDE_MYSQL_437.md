# Sauvegarde réseau après RC10 — incident #437

## Complément RC10.1

La sauvegarde automatique propose un dossier existant lorsque le chemin hérité
est introuvable. Cette préférence est enregistrée dans le profil local après
réussite, y compris à la fermeture du logiciel ; le chemin SQL partagé des autres
postes reste inchangé. Une annulation ne lance aucun export ni purge. Le message
d'erreur contient aussi le code MySQL (par exemple 1045), en plus du rapport JSON.
La chaîne Windows RC10.1 contrôle la présence du moteur et de son exécuteur dans
le paquet et effectue la recette MySQL avec une vraie progression wx.

## Défauts et correction du 28 octobre 2026

La RC10 (`d01566118f66775620d3df5e888bc50abfd4ecef`) attend sans limite un
`mysqldump` lancé par `cmd.exe`. Le premier correctif wx `21ec1447` ajoute une
surveillance ; le présent lot réutilise ce travail et assure une sortie complète
vérifiable. Une procédure peut aussi désigner un dossier d'un autre utilisateur,
absent du poste courant : ce cas est désormais refusé avant tout export, avec un
message indiquant le dossier à corriger. L'origine du blocage réseau ancien ne
peut pas être déduite de ce seul dossier absent.

- Moteur commun `UTILS_MySQL_backup` : lancement direct, fichiers SQL et stderr
  distincts, surveillance et arrêt de l'enfant, diagnostic taille/durée/code et
  dernier état MySQL, secrets et contenu SQL masqués.
- Fichier de connexion explicite (`--defaults-file`) : ne pas hériter d'options
  de filtrage d'un autre fichier de configuration MySQL. Les options personnelles
  de filtrage, `--force`, `--no-data`, changement de cible et désactivation des
  triggers sont refusées. Les options de compatibilité sont passées en arguments,
  jamais dans un shell.
- `--single-transaction --skip-lock-tables --quick --hex-blob`, paquet client
  jusqu'à 1 Gio. **Aucun SET GLOBAL ni réglage serveur.** Cette borne client ne
  remplace pas la borne serveur ; l'encodage hexadécimal peut doubler la taille
  d'une instruction INSERT à restaurer. Le serveur local de recette accepte
  128 Mio par paquet ; une future cible de restauration doit être dimensionnée.
- Ligne finale mysqldump exigée avant l'ajout du manifeste SHA-256, puis contrôle
  CRC du NOD dans l'outil autonome. Analyse SQL en worker dans le parcours wx,
  avec rafraîchissement régulier du dialogue de progression.
- Dossier de travail réseau unique par appel. Nettoyage des ZIP partiels et
  identifiants, y compris si le client est absent. Copie de destination préparée
  dans le même dossier puis remplacement atomique. Purge des anciennes
  sauvegardes uniquement après succès, y compris avec l'interface optionnelle.

La limite historique de `mysqldump` 5.7 (24 Mio) et la limite serveur sont
indépendantes : [documentation MySQL](https://dev.mysql.com/doc/refman/5.7/en/mysqldump.html).
La recette synthétique reproduit un échec réel 2020/code 3 avec un BLOB de
27 262 974 octets et l'ancienne commande. La nouvelle sauvegarde est restaurée
sur MySQL 5.7.44 jetable, avec comparaison SHA-256 des données binaires.
Ce contre-exemple n'attribue pas l'ancien blocage PMSL à la taille des pièces.

## Outils utilisables sans ouvrir Noethys

Depuis cette copie source, avec Python 3.10 ou plus récent et les clients MySQL
5.7 livrés dans le paquet RC10. Désigner volontairement le profil et l'hôte
exacts : aucune sélection automatique de la dernière connexion.

```powershell
py -3.10 tools/diagnostic_sauvegarde_mysql.py --client 'C:/Recette/mysql-client/bin/mysql.exe' --profil 'C:/Profil/Config.json' --hote 'SERVEURPMSL' --base pelemele --base mad --sortie 'C:/Recette/diagnostic.json'
py -3.10 tools/sauvegarder_mysql.py --client 'C:/Recette/mysql-client/bin/mysqldump.exe' --profil 'C:/Profil/Config.json' --hote 'SERVEURPMSL' --base pelemele --base mad --categorie DATA --categorie DOCUMENTS --sortie 'C:/Recette/Noethys.nod'
```

Le premier outil ne lance que des SELECT : version, limites, tailles, empreintes
des documents et répertoire de « Ma sauvegarde ». Il ne transmet ni document,
ni nom de famille, ni identifiant personnel. Le second exporte les quatre
éléments sélectionnés ; ajouter explicitement PHOTOS si cette base existe et
doit être incluse. Il refuse une archive cible existante. Sa destination doit
permettre les liens physiques (NTFS dans la recette Windows). Le rapport
`<archive>.diagnostic.json` reste indépendant des fichiers SQL temporaires.

`verifier_sauvegarde_mysql_isolee.py` ne prend aucun hôte ni profil cible : seul
`127.0.0.1:3407`, compte de recette, datadir explicitement vérifié et bases
absentes sont acceptés. Il restaure les membres, contrôle les documents puis
retire exclusivement les bases créées sur ce serveur jetable. Il ne doit pas
être adapté pour contourner ces gardes ou viser la production.

## Preuves et limites de qualification

Windows 11 / Python 3.10.11 : 83 tests ciblés sur chaque branche. Sur `main`,
la recette MySQL réelle supplémentaire porte le total à **84 PASS, 0 FAIL,
0 SKIP**. Les 83 tests portent sur les erreurs et temporaires, options,
conservation des anciennes archives, annulation, analyse SQL, manifeste,
restauration simulée et rafraîchissement pendant une analyse lente. Un vrai
processus Python bloqué est arrêté et attendu ; aucun réseau dans ce scénario.

La sauvegarde opérationnelle des quatre éléments demandés a aussi été créée
en lecture seule puis restaurée sur le serveur local jetable. CRC, manifestes,
quantités, tailles et empreintes des documents concordent avec la source. Les
archives, empreintes détaillées, diagnostics de connexion et données restent
**hors Git** dans le dossier local de recette ; aucun de ces fichiers n'est
publié avec le correctif.

Pas de modification du profil, de la procédure en base, du serveur de
production, du schéma, des binaires RC10 ou de sa release. Le dossier configuré
doit être adapté volontairement dans l'application pour les prochaines
sauvegardes de l'ancienne RC10. Le lot source ne constitue pas une nouvelle
version Windows installée. Recette graphique et packaging d'un prochain
candidat restent distincts ; le module commun est identique sur main/wx/qt.
