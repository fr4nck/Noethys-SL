# Facturation / adhesions : erreur MySQL 2005 (10/11/2026)

## Observation terrain

- Poste Nicolas, Noethys-SL 0.1.0 RC10.55, fichier reseau affiche « pelemele ».
- Generation de factures du 01/10 au 31/10/2026, option « Cotisations » cochee.
- Avertissement « Cotisations automatiques non verifiees » : erreur MySQL `(2005, "Unknown server host 'SERVEURPMSL' (11001)")` depuis `UTILS_Adhesions.py:128`.
- Le serveur MySQL n'est pas necessairement arrete : l'erreur signale une resolution du nom d'hote impossible pour cette nouvelle connexion.
- L'ouverture prealable de l'application n'est pas une preuve que *toute nouvelle connexion* MySQL reussira.

## Cause code identifiee

`UTILS_Adhesions._lire` ouvre une nouvelle connexion via `GestionDB.DB()` pour chaque SELECT, et possede une relance unique hors pool sur les codes 2006/2013/2014/2055. Le code 2005, produit ici par un echec DNS, n'etait pas admis a cette relance. La cause de l'echec DNS (nom d'hote, suffixe DNS, VPN, DNS Windows, indisponibilite transitoire) reste **non determinee**.

## Correction code

- Autoriser **une seule relance** des SELECT en lecture seule apres erreur 2005, avec `pooling=False`, fermeture des deux connexions et meme configuration active.
- **Aucun** changement implicite de serveur, de port, de compte, de profil ou de fichier reseau.
- Aucune nouvelle tentative sur requete d'ecriture, erreur de droits (1045), de schema (1054), ou base SQLite.
- Si le second essai echoue : propager l'erreur. Ne jamais convertir l'erreur en resultat vide ou absence de cotisation.
- La preparation des factures propose deja « Non » par defaut. En exploitation, choisir **Non** jusqu'a requalification des cotisations ; le bouton « Oui » peut preparer des factures auxquelles manquent des cotisations.

## Couverture et qualification

Fichier cible : `noethys/Utils/UTILS_Adhesions.py`.

Tests ajoutes : `tests/test_noethys_sl_adhesions_dns_2005.py` (AST des fonctions reelles sans ouverture de base):
1. recuperation d'un SELECT apres une erreur 2005 ;
2. erreur 2005 persistante => echec explicite, jamais faux zero ;
3. 1045 sans relance ;
4. UPDATE sans relance ;
5. SQLite sans relance.

Branches et commits de correction (sans fusion globale) :
- main : `5165a9d3` ; tests `d643461e`.
- wx : `64ae89c2` ; tests `5b1981a6`.
- qt : `31208f6f` ; tests `ff588abe`.

## STOP-GATE de publication

Les commits et tests sources **ne sont pas une recette poste Windows**. Avant d'annoncer l'incident resolu dans une RC :
- executer les tests concernes et verifier la CI sur les branches concernees ;
- recette Windows sur base MySQL fictive : echec DNS 2005 une fois puis succes, et echec persistant ;
- verifier sur le poste de Nicolas, sans exposer de mot de passe, que le nom d'hote configure correspond a celui effectivement accessible et que la connexion peut etre ouverte plusieurs fois ;
- verifier preview, cotisations attendues, non-duplication, absence d'ecriture avant consentement, puis emission controlee ;
- si DNS persiste, corriger la configuration ou la resolution reseau de maniere explicite, **pas** en substituant silencieusement une IP ou un serveur ;
- aucun test avec ecritures sur la base de production.

Incident distinct : informations d'authentification historisees dans le depot (voir `docs/dev/REPRISE_CODEX.md`). Ne pas republier les identifiants ni les encoder comme si Base64 etait du chiffrement.

## Qualification complementaire — 10/11/2026

**CI Windows de reference avant ce lot** :
- main : run 42815786940, 1315 tests, SUCCESS ;
- wx : run 42815793747, 2358 tests, SUCCESS ;
- les 16 tests cibles DNS / garde / choix humain ont reussi dans les deux campagnes.

**Recette MySQL 5.7.44 reelle sur serveur jetable** :
- main : run 42822887373, SUCCESS (4/4) ;
- wx : run 42822897870, SUCCESS (4/4) ;
- qt : run 42822906594, SUCCESS (4/4).
- Les 4 tests comprennent deux cas de facturation en MySQL reel
  (choix individuel, aucune cotisation pour le titulaire exclu ;
  premier appel simule en erreur 2005 puis deuxieme connexion *reelle*),
  ainsi que deux scenarios MySQL de concurrence / InnoDB fournis
  par le banc d'adhesions.
- La panne DNS initiale du test est **simulee** ; aucun serveur MySQL
  de production et aucun enregistrement de famille reel ne sont utilises.
- Source : tests/test_noethys_sl_facturation_cotisations_mysql.py ;
  workflow : .github/workflows/noethys-sl-fact-cot-mysql57.yml.

**Renforcement de la validation de factures** :
- DLG_Factures_generation_selection.Validation execute le controle apres
  la confirmation de l'operateur et immediatement avant SauvegardeFactures ;
- annulation => aucun controle reseau inutile et aucune ecriture ;
- blocage de la garde => aucune emission ;
- tests d'ordre de traitement sous Windows et test du vrai composant
  wx.MultiChoiceDialog ajoutes a la CI rapide (requalification en cours
  lors de la presente note).

**STOP-GATE restant** : reproduire le parcours complet dans la vraie interface
wx sur une base MySQL fictive, puis diagnostiquer la resolution du nom
SERVEURPMSL sur le poste concerne. Un test de reprise apres erreur
2005 ne prouve pas la disponibilite DNS de ce poste. Les changements
concurrents sur les prestations entre le dernier controle et l'ecriture
restent une limite a examiner avant une garantie stricte. Ne pas
publier de RC declaree stable sur cette seule preuve.
