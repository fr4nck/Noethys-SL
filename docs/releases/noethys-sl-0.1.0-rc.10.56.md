# Noethys SL 0.1.0 RC10.56 — préversion cumulative Windows

**PMSL — 9 novembre 2026.** Edition wxPython, sans migration de base. La version de compatibilite reste **1.3.4.4**.

## Correctif P0 #437

- Controle d'existence et d'ecriture du dossier avant export MySQL, sans long export inutile si la destination est absente.
- Si le chemin partage est invalide sur le poste courant, proposition d'une destination locale. Le choix est memorise apres reussite uniquement, sans alteration de la procedure commune.
- Annulation de la selection : aucun export et aucune purge des archives historiques.
- Echec tardif de copie : affichage du dossier concerne et de l'erreur systeme. L'archive anterieure n'est pas remplacee en cas d'echec.

Ce correctif couvre un echec terrain etabli par journal : copie tentee vers un ancien profil Windows absent. La correlation avec tous les autres incidents n'est pas etablie.

## Continuité et portée

Les fonctions de RC10.55 et les evolutions integrees dans la branche `wx` sont reprises dans ce candidat, sous reserve de qualification. Les modifications recentes d'AFAS2, des statistiques et de Connecthys necessitent leurs recettes propres ; les tests automatiques ne remplacent pas les controles de la direction.

La recette Windows de publication comprend les tests critiques, le demarrage d'un paquet isole et la sauvegarde/restauration de donnees **fictives** sur MySQL 5.7.44 local, avec un gros document binaire. La validation terrain de sauvegarde **DATA + DOCUMENTS** PMSL et d'une restauration sur serveur independant reste a realiser avant fermeture du ticket #437. PHOTOS est facultatif.

## Livrables si les barrieres passent

- `Noethys-SL-0.1.0-rc.10.56-Setup.exe`
- `Noethys-SL-0.1.0-rc.10.56-Windows-portable.zip`
- `SHA256SUMS.txt`

**Préversion, non stable.** Aucun remplacement d'installation ni intervention sur la base PMSL n'est realise par les workflows de construction/publication.

## Essai terrain RC10.56 — correctifs integres au 9 novembre 2026

**Statut : preversion officielle de recette, non stable.** Cette RC reprend le code et les correctifs de la branche `wx` au commit source utilise par le workflow de publication. Elle ne modifie ni la version interne de compatibilite 1.3.4.4, ni les schemas SQL. Elle ne doit pas etre interpretee comme une certification generale du module Statistiques, de l'interface ou des sauvegardes en production.

### Statistiques — STATS-RESTORE Q3/Q4

- Les 33 objets de statistiques ont des controles SQL individuels sur des bases SQLite fictives. La [CI Q4 #42700698161](https://github.com/fr4nck/Noethys-SL/actions/runs/42700698161) a passe **52/52 tests sous Ubuntu ET Windows**.
- Les 15 graphiques ont chacun produit un **vrai PNG Matplotlib Agg**, verifie sous Ubuntu et Windows ([CI #42701694076](https://github.com/fr4nck/Noethys-SL/actions/runs/42701694076) : 15/15 PASS par systeme).
- La chaine **Matplotlib > wx.Bitmap > MemoryFS > ouverture HTML source > destruction naturelle** a passe son test natif Windows en sous-processus, **15 graphiques enregistres/ouverts/liberes**, sortie sans crash ([CI #42703735195](https://github.com/fr4nck/Noethys-SL/actions/runs/42703735195), revalidation [#42704220405](https://github.com/fr4nck/Noethys-SL/actions/runs/42704220405)). Aucun echec natif MemoryFS n'a ete mis en evidence par ces campagnes.
- Les corrections de reactivite et de proprietaire de fenetres du chantier [#432](https://github.com/fr4nck/Noethys-SL/issues/432) sont incluses dans `wx`, mais **l'absence de retour inopine en mode fenetre n'est pas encore certifiee sur le PC de l'utilisateur**.
- **Limites :** la regle metier du quotient familial multi-types et les categories non representees par certains graphes [#442](https://github.com/fr4nck/Noethys-SL/issues/442) restent ouvertes ; la recette des 33 objets sur vrai MySQL 5.7 et les parcours d'impression/zoom dans l'installateur restent a effectuer.

### Sauvegarde, installation et essais

- Le correctif de sauvegarde [#437](https://github.com/fr4nck/Noethys-SL/issues/437) verifie les destinations et preserve les archives precedentes en cas d'echec ; des tests MySQL locaux jetables sont prevus dans la construction officielle. **Une sauvegarde DATA+DOCUMENTS et sa restauration reelle PMSL n'ont pas encore ete certifiees.** Ne pas supprimer une sauvegarde precedente avant cette verification.
- Deux livrables Windows sont prevus : **Setup.exe** (installation normale) et **Windows-portable.zip** (essai avec profil distinct), accompagnes de **SHA256SUMS.txt**.
- Pour un premier essai, preferer le **portable avec un profil de test et des donnees fictives** ; conserver l'installation existante et les sauvegardes a part. Ne pas lancer de migration ou de synchronisation reelle pour ce seul diagnostic.
- Points de recette : ouvrir les 11 pages de statistiques, afficher chaque graphe, changer plusieurs fois d'activite/periode, tester zoom et apercu/impression, fermer/rouvrir, surveiller la maximisation de la fenetre principale, puis tester une sauvegarde/restauration exclusivement sur une base de test.

**Publication controlee :** la release GitHub est creee avec le statut `prerelease` uniquement apres compilation Windows, recettes critiques, tests MySQL fictifs, demarrage de l'executable installe/portable, controle des fichiers et de leurs SHA-256. En cas d'echec d'une barriere, **aucune RC n'est publiee**.
