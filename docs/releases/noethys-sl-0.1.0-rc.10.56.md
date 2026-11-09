# Noethys SL 0.1.0 RC10.56 — préversion cumulative Windows

**PMSL — 9 novembre 2026.** Edition wxPython, sans migration de base. La version de compatibilite reste **1.3.4.4**.

## Correctif P0 #437

- Controle d'existence et d'ecriture du dossier avant export MySQL, sans long export inutile si la destination est absente.
- Si le chemin partage est invalide sur le poste courant, proposition d'une destination locale. Le choix est memorise apres reussite uniquement, sans alteration de la procedure commune.
- Annulation de la selection : aucun export et aucune purge des archives historiques.
- Echec tardif de copie : affichage du dossier concerne et de l'erreur systeme. L'archive anterieure n'est pas remplacee en cas d'echec.

Ce correctif couvre un echec terrain etabli par journal : copie tentee vers un ancien profil Windows absent. La correlation avec tous les autres incidents n'est pas etablie.

## Continuité et portée

Les fonctions de RC10.55 et les evolutions integrees dans la branche \`wx\` sont reprises dans ce candidat, sous reserve de qualification. Les modifications recentes d'AFAS2, des statistiques et de Connecthys necessitent leurs recettes propres ; les tests automatiques ne remplacent pas les controles de la direction.

La recette Windows de publication comprend les tests critiques, le demarrage d'un paquet isole et la sauvegarde/restauration de donnees **fictives** sur MySQL 5.7.44 local, avec un gros document binaire. La validation terrain de sauvegarde **DATA + DOCUMENTS** PMSL et d'une restauration sur serveur independant reste a realiser avant fermeture du ticket #437. PHOTOS est facultatif.

## Livrables si les barrieres passent

- \`Noethys-SL-0.1.0-rc.10.56-Setup.exe\`
- \`Noethys-SL-0.1.0-rc.10.56-Windows-portable.zip\`
- \`SHA256SUMS.txt\`

**Préversion, non stable.** Aucun remplacement d'installation ni intervention sur la base PMSL n'est realise par les workflows de construction/publication.
