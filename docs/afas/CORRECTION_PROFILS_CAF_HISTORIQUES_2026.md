# AFAS — correction des profils CAF historiques (03/11/2026)

## Constat sur la sauvegarde ALSH du 22/10/2026

La sauvegarde `.nod` a été auditée **en lecture seule**. Les deux profils de
l'état global nommés exactement **« Caf - Périscolaire »** et
**« Caf - Extrascolaire »** retiennent quatre états de consommation :
`reservation`, `present`, `absentj`, `absenti`.

Le moteur historique de l'état global applique les coefficients d'unités et
le forfait méridien aux absences sélectionnées, alors que les **heures
réalisées AFAS V2** ne doivent retenir que les présences attestées.

Sur les mercredis hors vacances, au 30 septembre 2026, la reconstitution
agrégée du profil Caf - Périscolaire donne, pour les deux groupes de Bais,
10 820 h (présents seuls) contre 12 003 h (quatre états), soit +1 183 h.
Pour La Guerche seule, l'effet est de +824 h. Ces valeurs **ne sont pas** des
heures AFAS V2 qualifiées ; elles ne démontrent pas la cause exacte de
l'écart historique de 1 086,50 h signalé à Bais.

Aucun nom ni identifiant individuel n'est enregistré dans ce document ;
ni archive .nod, ni extrait contenant des pseudonymes ne doivent être
publiés dans GitHub.

## Correctif de sûreté sur wx

- Commit initial : `6ef4d92bf3ff0a501b6d31e04595785721317c44`.
- `Utils/UTILS_AFAS_ProfilsHistoriques.py` reconnaît **uniquement** les deux
  intitulés historiques ci-dessus.
- À leur chargement dans « État global », la sélection en mémoire passe à
  `["present"]` si elle contenait d'autres états. Un avertissement
  explique que le profil **sauvegardé n'a pas changé**.
- Si l'utilisateur resélectionne ensuite une réservation ou une absence
  dans ce profil, « Aperçu » refuse le calcul et indique la sélection à
  corriger.
- Le bouton de sauvegarde du profil permet à l'utilisateur de conserver
  volontairement « Présent » seul. Aucun UPDATE SQL ni changement des
  profils n'est réalisé en tâche de fond.
- Les autres profils d'états globaux peuvent continuer à sélectionner
  librement réservations, présences et absences : pas de changement de
  comportement pour leurs autres usages.
- Le bouton AFAS V1 reste masqué. AFAS V2 (`Consommations >
  Déclarations AFAS`) retient déjà `present` seul pour le réalisé et
  distingue les états du facturé. Il n'est pas modifié par ce correctif.

## Qualification et déploiement

Tests dédiés :
`tests/test_noethys_sl_afas_profils_historiques.py` ; inclus dans la CI
rapide Windows de `wx`. Avant mise à disposition d'un installateur,
vérifier compilation, tests et recette graphique d'ouverture des deux
profils sur base **fictive**, notamment l'avertissement et le clic de
sauvegarde.

**Aucun paquet publié et aucune base MySQL de production modifiée** par
le commit ; le correctif devient visible seulement après intégration dans
une version installée et une qualification de publication.

## Reste à faire

Paramétrer AFAS V2 dans une **copie** de la base ALSH, vérifier les sites,
unités, calendriers et conventions, puis rapprocher le réel
janvier–septembre 2026 par équipement et mode. L'écart Bais 1 086,50 h
reste à expliquer ; ne pas conclure qu'il est entièrement causé par les
statuts historiques.
