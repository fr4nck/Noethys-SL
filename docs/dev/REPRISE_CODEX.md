# Reprise du chantier Noethys-SL — état au 08/10/2026

## Retours terrain RC7.3 — accueil, bouton et créneaux (16/10/2026)

- La capture fournie affiche RC7.3 sur le poste. Aucun lancement, accès à sa base,
  installation ni configuration de production effectués par l'agent.
- Demandes : supprimer l'effet de grand cadre blanc, réduire le vide, rendre le
  compteur Connecthys clairement cliquable et distinguer les créneaux EMS.
- Fond SYS_COLOUR_3DFACE repris par le bandeau ; marges réduites, titres alignés,
  colonne vacances compacte (240 DIP), agenda seul extensible, colonnes vides sans
  espace réservé. Préférences existantes conservées et agenda à défilement propre.
- Bouton demandes : bord arrondi visible, fond teinté, curseur main, surbrillance
  au survol et au focus, état pressé ; GenButton et sa navigation clavier/clic
  conservés, libellé multiligne avec nombre complet. Ancien panneau non compact
  inchangé. Aperçu natif isolé normal et survol inspecté, données strictement fictives.
- L'ancien total EMS était le nombre de personnes distinctes de la journée, pas
  un effectif simultané. Nouveau bandeau hors ALSH : une entrée par séance
  identifiée, ou unité/groupe/plage configurés ; horaire et nom de séance/unité
  affichés. Deux unités ou séances parallèles ne sont pas fusionnées parce que
  leurs heures coïncident. Une personne à deux séances compte une fois dans chacune.
  Dédoublonnage dans chaque créneau ; états attente/absence exclus ; ouvertures et
  séances vides conservent zéro. Groupes distincts séparés. Activités inactives exclues.
  Les heures des unités configurées servent de créneaux, à défaut celles des
  consommations ; une plage large configurée ne permet pas de déduire un effectif
  simultané maximal. Aucun calcul de pic d'occupation ni pointage en temps réel.
- Séance liée par IDevenement prioritaire sur la plage générique de l'unité.
  Consommation sans lien de séance alors que plusieurs existent sur cette unité :
  « horaire non renseigné », sans répartition arbitraire entre séances. Pas de règle
  de tarification, d'inscription, de facture, d'annulation ni d'écriture métier changée.
  ALSH conserve ses M/A par groupe, via unités de remplissage et conditions existantes.
- Toujours six SELECT, enrichis avec les métadonnées des ouvertures, événements et
  LEFT JOIN sur les clés des unités/événements. Aucun nouveau schéma ni connexion
  répétée par créneau. Quatre tests SQLite supplémentaires : créneaux distincts,
  dédoublonnage, mêmes horaires/séances distinctes, lien inconnu, groupes et unités
  parallèles, aucune écriture. Fixtures MySQL étendues sans données réelles.
- Dernier code : main **7ebe1cd985d84483c03ce2df3c387ca3311fd60c**,
  wx **9026ef5ce54091dcbfd622c4992ca9fa44b64b5c**,
  qt **6dd9f7bea23d2ed946185884f6a4a0078f9edb6f**.
  Neuf fichiers communs (code, tests, préparation serveur, workflows) comparés :
  identiques. Portages ciblés ; repas directeur RC8 et adaptations propres conservés.
- CI rapide main [38889769079](https://github.com/fr4nck/Noethys-SL/actions/runs/38889769079)
  SUCCESS : 662 tests / 6 ignorés ; wx
  [38889809868](https://github.com/fr4nck/Noethys-SL/actions/runs/38889809868) SUCCESS :
  675 tests / 10 ignorés ; qt
  [38889820013](https://github.com/fr4nck/Noethys-SL/actions/runs/38889820013) SUCCESS :
  627 tests / 6 ignorés, suite commune wx, pas une validation UI Qt native.
- Recette serveur du code FINAL
  [38889769125](https://github.com/fr4nck/Noethys-SL/actions/runs/38889769125) SUCCESS :
  MySQL 5.7.44 local réellement démarré sur runner isolé, 3 tests OK / aucun ignoré.
  Jeu fictif à deux créneaux d'une activité et deux séances simultanées identifiées :
  résultats SQLite/MySQL égaux et tables inchangées par read_day ; concurrence
  et actualisation conditionnelle du journal Mailjet conservées. Serveur stoppé,
  seule base unique de la recette détruite. Aucun appel API ni email.
- Recette indépendante sans packaging via workflow MySQL existant, entrée
  mode=accueil, appel du nouveau workflow réutilisable. La première tentative
  directe du nouveau nom était refusée car absent de master (branche par défaut
  historique). Le run 38889425498 a ensuite échoué AVANT les tests car le script
  préparateur n'existait que sur wx : copie identique partagée sur main/qt,
  run intermédiaire 38889670615 SUCCESS, puis run final ci-dessus. Aucun test
  ignoré/affaibli pour masquer cet échec. Runs rapides remplacés par nouveaux
  commits annulés par concurrence normale.
- Qualification : sources communes VALIDÉES sur les trois branches ; MySQL 5.7
  du code commun VALIDÉ sur main et blobs identiques wx/qt ; UI Qt native,
  configuration réelle EMS/ALSH, DPI et nouveau binaire empaqueté EN ATTENTE.
  Les 28 et 113 tests locaux intermédiaires sont antérieurs aux CI finales ;
  les CI finales font foi. Captures/logs fictifs dans qualification/ hors Git.
- Aucun nouvel installateur : le candidat RC7.3 du build 9a8cf664 reste inchangé
  et ne contient PAS ces retouches postérieures. Avant de reconstruire, attribuer
  une identité distincte au prochain candidat ; ne pas réutiliser RC7.3 pour un
  contenu différent. Cotisations automatiques toujours suspendues, issue #427
  non résolue par ces changements d'affichage. Prochaine étape : nouvelle recette
  visuelle du candidat distinct puis vérification des créneaux configurés du pilote.

## RC7.3 Windows fabriquée — preuves finales du 16/10/2026

- Candidat wx demandé par Franck, construit depuis **9a8cf664103d0e14fdaf0bcc83ccdbb7d535c630**.
  [Build 38884469875](https://github.com/fr4nck/Noethys-SL/actions/runs/38884469875) : SUCCESS.
  Identité publique 0.1.0-rc.7.3 ; compatibilité interne 1.3.4.4 conservée.
- [Artefact candidat 12039586320](https://github.com/fr4nck/Noethys-SL/actions/runs/38884469875/artifacts/12039586320),
  Noethys-SL-0.1.0-rc.7.3-Windows-candidat, 250592802 octets, expiration 15/11/2026.
  Deux livrables et SHA256SUMS.txt téléchargés et contrôlés localement sans installation :
  - Setup : 105263582 octets, SHA-256 `64d2d8e8cbdc609437a48d50e9bc2af1072c578500574e6ad67839cb0a7de19d`.
  - ZIP portable : 147058963 octets, SHA-256 `74ace81aacfab80b5f94b0324f5e3ca3a038a9ad852570148e3fbcff9e9f08cf`.
- Provenance BUILD-INFO conforme au SHA et au run ; notes RC7.3 présentes dans le ZIP.
  Table des modules du PYZ de Noethys.exe inspectée : CTRL_Accueil_compact,
  UTILS_Accueil_jour, DLG_Suivi_mailjet, UTILS_Suivi_mailjet, Outils.WordWrapRenderer
  réellement embarqués. Constantes Identite embarquées : RC7.3. Portable/README.txt présent.
- CI rapide wx [38884114272](https://github.com/fr4nck/Noethys-SL/actions/runs/38884114272) :
  SUCCESS, 671 tests / 10 ignorés. CI main cfa88af3eff44e55778dcbbee1a1b0c0a53c9bf6
  [38883974376](https://github.com/fr4nck/Noethys-SL/actions/runs/38883974376) : SUCCESS,
  658 tests / 6 ignorés. Aucun affaiblissement des tests.
- Contrats du build : 280 tests OK / 7 ignorés. Recette serveur MySQL 5.7.44 local
  **réel et jetable : 10 tests OK / aucun ignoré**, incluant sauvegarde/restauration
  avec les clients livrés, six SELECT de l'accueil identiques à SQLite sur jeu
  fictif (groupes, repas, heures, étiquettes), aucune écriture par ces lectures,
  GET_LOCK Mailjet réel, huit enregistrements concurrents / quatre threads sans
  doublon, Unicode hors BMP sur utf8 historique, actualisation conditionnelle
  empêchant une consultation ancienne d'écraser l'état livré. Aucun appel API.
- Smoke exécutable : processus encore actif après 12 secondes sur runner isolé.
  ZIP extrait démarré, profil créé dans Portable/ et aucune écriture de profil
  dans APPDATA/noethys. Setup fabriqué par Inno Setup. Les avertissements de
  nettoyage temporaire / ResourceWarning des tests ne sont pas des échecs de test ;
  ne pas annoncer pour autant une recette métier complète du binaire.
- Nouveau test de qualification commun : main cfa88af3, wx 1e705075,
  qt d9cadf38. Ce fichier est identique sur les trois branches ; exécution serveur
  prouvée sur wx seulement. Les identités / notes Windows restent propres à wx.
  Les modules communs accueil/Mailjet/adhésions étaient identiques au départ.
- INCLUS : accueil compact, bandeau configurable des effectifs PRÉVUS M/A par
  groupe ALSH, Connecthys compact, impression dépôts, arrondis rappels, suivi
  Mailjet volontaire, optimisation et profilage facultatif des consommations.
  EXCLU : chantier repas directeur multisite #430 réservé RC8 sur main.
  AUTO_CREATION_SUSPENDUE=True : protection P1 adhésions maintenue.
- STOP-GATE restant pour une utilisation habituelle : recette pilote isolée des
  unités M/A réellement paramétrées et de l'affichage DPI 125/150/200 %, parcours
  complets du binaire, API Mailjet authentifiée sur compte de recette. Pas de
  qualification MySQL 5.5 des nouveaux tests, de nouvelle optimisation des UPDATE
  ou des transactions, ni d'UI Qt native. Pas de gain terrain revendiqué.
- **Aucune installation terrain ni publication de release/tag**. RC7.2 sur le poste
  n'est pas devenue RC7.3 par cette fabrication. Aucun accès de production, email,
  impression physique ou donnée réelle. Logs et téléchargements conservés localement
  dans optimisation-consos-20261015/qualification/ hors Git. Les anciennes sections
  ci-dessous sont des états historiques ; la présente preuve fait foi pour le candidat.

## Accueil compact — intégration demandée pour RC7.3, 16/10/2026

- Accord utilisateur : maquette Horizon ; météo quatre jours M/A, pluie en mm,
  vent en km/h avec flèche seule, clic sur tout le bloc pour les détails ;
  événements avec défilement indépendant et nombre configurable (0 = tous).
  Connecthys intégré à droite, demandes / état / progression / journal au clic.
  Quatre titres de même hauteur, date sur deux lignes « Vendredi 16 / Octobre 26 ».
- Bandeau sur toute la largeur : seulement activités programmées au jour affiché.
  Priorité ALSH par défaut, sélection et ordre personnel ; activités hors dates
  de validité exclues. Choisir M/A pour les accueils dont le nom ne permet pas
  l'identification automatique. Autres activités : total distinct de participants.
  Les effectifs sont PRÉVUS : pointage effectué après la journée selon l'utilisateur,
  aucune prétention de présence temps réel ni de contrôle automatique des absents.
- Départ vérifié : main `bb08cc752bdb4ca21a4719f73420f6444fd610fe` (avance repas
  conservée), wx initial `c9038741479b637397345d27e2b8fc435d4345d9`, qt initial
  `ec13651695a0f02ccc58136af335f00abf032edf`. Attention : les refs de suivi
  origin/wx `ca12e5a9` et origin/qt `31a2a5d9` étaient ANCIENNES ; ls-remote et
  FETCH_HEAD confirment les SHA précédents. Les quatre fichiers modifiés préexistants ont des blobs identiques
  sur les trois branches avant intervention. Aucun merge global / nouvelle branche.
- UTILS_Accueil_jour : six SELECT portables MySQL/SQLite, ouvertures / événements /
  consommations de la date, réservations et présences seulement, sets par personne.
  Attente et absences exclues ; personne de journée entière dans les deux périodes.
  Correspondance M/A indéterminée : « — », jamais un faux zéro. Heures MySQL timedelta
  et SQLite texte prises en charge. Aucune écriture métier / migration / tarification.
  Contrôle complémentaire de CTRL_Remplissage : les sites/tranches d'âge sont
  des GROUPES d'une même activité ALSH. Les lignes du bandeau ALSH sont donc
  séparées par IDgroupe (Bais −6 / Moutiers −6...), jamais agrégées entre sites.
  Test SQLite dédié : deux groupes, effectifs distincts, doublons inter-périodes.
  Contrôle supplémentaire : les deux compteurs réutilisent les associations des
  unités de remplissage MAT/APM (pas une coupure horaire à midi), leurs plages
  conditionnelles et étiquettes comme CTRL_Remplissage. Une réservation de repas
  à midi n'est pas une réservation d'après-midi sans association explicite.
  Préférences : unités matin/après-midi sélectionnables si les noms sont ambigus.
- Préférences : catégorie accueil_aujourdhui, identifiant utilisateur et base, comme
  la disposition historique ; choix des activités, M/A, ordre et nombre d'événements.
  Chargement dans le worker existant, résultat invalidé à fermeture/changement
  d'utilisateur. Rafraîchissement à cinq minutes, cache météo conservé à trente.
  Direction du vent : moyenne circulaire ; anciens caches sans direction → « — ».
- Connecthys : même instance client / mêmes commandes / cadence réseau inchangée.
  État basé sur le booléen réel de Synchro_totale, pas sur l'icône « on » ni l'heure
  de dernière tentative. Dernier succès distinct ; aucune remise à zéro des demandes
  si leur lecture échoue. Callbacks wx ignorés après destruction. Journal de session
  borné à 1000 lignes au clic ; destination historique du journal conservée.
- Recette synthétique native Windows : 77 tests initiaux (dont audit Connecthys) OK,
  54 ciblés finaux OK ; suite rapide locale 652 tests OK / 6 ignorés. Rendu natif
  isolé inspecté dans qualification/accueil-natif.png, puis largeur corrigée pour
  que Connecthys reste visible à droite à 1200 px. Maquette et captures ne sont
  pas des données de production ; qualification/ reste local hors Git.
- CI et portages finaux : VALIDÉS dans le tableau ci-dessous. EN ATTENTE :
  recette d'une base MySQL jetable et de la configuration des unités ALSH du pilote.
  UI Qt native non qualifiée. Aucun appel Connecthys réel, email, production ou
  installateur. Identités et Versions.txt inchangés : RC7.3 demeure une CIBLE,
  pas une version construite/installée. Coupe-circuit adhésions toujours actif.
- Première qualification CI main du lot `3622f28243c7fe47da3e7d22b99306391a5374ee` :
  [38875715124](https://github.com/fr4nck/Noethys-SL/actions/runs/38875715124) SUCCESS.
  Portages préparés et 55 tests ciblés OK sur wx/qt, non publiés à ce stade.
  La séparation par groupe ALSH est ajoutée ensuite, 41 tests ciblés OK avant
  nouvelle CI. Les différences repas présentes seulement sur main restent
  conservées ; ce lot n'affirme pas une synchronisation globale des trois branches.
- Recette native complémentaire : les libellés multilignes de GenButton étaient
  centrés comme une seule ligne, coupant le premier chiffre du nombre de demandes.
  BoutonDemandes utilise DC.DrawLabel multiligne ; rendu natif « 22 demandes »
  inspecté après correction, 18 tests ciblés OK. Derniers tests d'alignement : les
  quatre titres ont la même coordonnée Y et Connecthys reste dans le panneau.

### Qualification finale de l'accueil compact

Derniers commits de CODE (les commits de preuves suivants ne changent que ce document) :

| Branche | Code final | CI rapide |
| --- | --- | --- |
| main | `a31451d8f7b2ebfefe66b4af17fb09965eba2222` | [38878484485](https://github.com/fr4nck/Noethys-SL/actions/runs/38878484485) SUCCESS : 658 tests / 6 ignorés |
| wx | `c5c099390d19f7cef805fed25f5c060e89f6090e` | [38878617360](https://github.com/fr4nck/Noethys-SL/actions/runs/38878617360) SUCCESS : 671 tests / 10 ignorés |
| qt | `a45ffe9ebb915bd65a63c69f8c7e2ad027fa2031` | [38878631894](https://github.com/fr4nck/Noethys-SL/actions/runs/38878631894) SUCCESS : 623 tests / 6 ignorés, code commun wx |

- 17 nouveaux tests d'accueil compact : SQLite native éphémère, compteur distinct,
  plusieurs groupes d'une activité, repas seul non assimilé à l'après-midi,
  unités M/A explicites, conditions horaires et étiquettes, choix/ordre/activité
  inactive, direction circulaire, vrai wx (préférences, titres alignés et largeur,
  tous les pictogrammes), état Connecthys et échec conservant le compteur précédent.
  60 tests ciblés finaux OK sur chaque arbre ; suite locale antérieure aux trois
  derniers tests : wx 667 / 12 ignorés, qt 619 / 6 ignorés. Les CI ci-dessus font foi
  pour le CODE final, pas ces comptes locaux intermédiaires.
- Neuf fichiers communs de code et tests comparés par blob : identiques sur les
  trois SHA. Portages ciblés des seuls commits de ce chantier, aucun écrasement
  des variantes historiques ni du travail repas de main. Coupe-circuit adhésions
  toujours True sur les trois arbres. Les runs intermédiaires main remplacés par
  un nouveau push ont été annulés par la concurrence CI ; pas de test affaibli.
- VALIDÉ : lectures/sélections/dédoublonnages sur SQLite fictive, UI wx native,
  non-régression de la suite rapide, contrat de retour réel de synchronisation.
  EN ATTENTE : serveur MySQL jetable, correspondance des unités du poste pilote,
  recette DPI 125/150/200 %, UI Qt native et exécutable empaqueté.
- RC7.3 reste la cible autorisée, pas un candidat fabriqué. Aucun changement
  d'identité publique, de notes livrées, de tag/release, d'installation, de base
  de production ni d'envoi d'email. Vérifier les unités M/A avant usage opérationnel
  des compteurs pour l'encadrement ; « — » signifie correspondance à configurer.

## Impression du depot et rappels a 0 EUR — 15/10/2026

- Deux signalements terrain RC7.2 : les entrees Outils / apercu et imprimer
  de Saisie d'un depot ne donnent aucune fenetre (absence de parametres
  confirmee par Franck) ; des familles a jour figurent dans les candidats aux
  rappels avec 0,00 EUR. Pas de traceback du poste et aucune base reelle lue.
- Tetes reelles avant travail : main `1c6fd7a6fbc1ece8672949d86cdbe1df69e58794`,
  wx `2ce816bebf0fc78b114226fe789b1e9ddab6d98b`,
  qt `dd7633b93bd3bcb439a22a77e3cefc0cf1423665`.
  Fichiers compares avant modification ; seul UTILS_Printer differe entre
  main et wx sur six wx.Pen fixes a largeur 0 plutot que 0.25. Aucun ecart
  main/qt sur ce perimetre. Chemins de depot/menus/parametres identiques a
  ffd28de (candidat RC7.2) sur wx ; ne pas attribuer un correctif deja livre.
- Impression : Outils.ListCtrlPrinter importait WordWrapRenderer comme module
  global, resolu en sources via Chemins.sys.path, absent du namespace de
  package attendu par PyInstaller. Import relatif explicite, teste dans un
  sous-processus sans repertoire Outils sur sys.path. Defaut coherent avec
  l'absence des parametres ; confirmation binaire du poste encore necessaire.
- Suite du parcours reproduite sur vrai wx : TypeError wx.Pen avec epaisseur
  float (dont valeur utilisateur 0.25), puis DC.DrawRectangle avec coordonnees
  float. Largeurs converties a l'API wx (0 = trait fin), coordonnees converties
  uniquement au dessin dans les deux moteurs, calcul de mise en page inchange.
  Conservation des intros, totaux et pieds de page du moteur Noethys historique.
  Parametres rattaches a la fenetre de depot ; menus communs affichent une erreur
  et ecrivent le traceback dans journal.log plutot que laisser un clic muet.
- Recette synthetique : vraie liste de depot / menus wx ; deux actions routees
  vers leurs parcours respectifs, annulation sans impression, parametres et
  rendu multipage de 49 reglements fictifs dans wx.MemoryDC. Aucun spool,
  pilote, impression papier, email ni donnees de capture utilisateur utilises.
  Bitmap representatif de trois lignes, qualification/depot-synthetique.png,
  inspecte visuellement ; les 49 lignes sont couvertes par le test multipage.
- Rappels : SUM(.10 + .20) peut depasser .30 de quelques fractions de centime
  sur colonnes FLOAT ; Decimal(str(SUM)) conservait ce residu, solde<0 incluait
  le compte puis le format a deux decimales affichait 0.00. Arrondir la seule
  difference au centime avant son test, comme montant affiche ; aucune mise a
  jour de prestations, ventilations, factures, reglements ou rappels existants.
  Une dette reelle de 0.01 reste incluse ; zero, crediteur et compte solde exclus.
  Criteres de dates, activites, categories, exceptions et comptes inchanges.
- Contre-preuves avant correctif : reexecution de la version `1c6fd7a6` sur
  les donnees synthetiques renvoie la fausse dette (test en echec attendu) ;
  ancien import du moteur sans sys.path Outils leve ModuleNotFoundError
  WordWrapRenderer avant l'ouverture des parametres. Apres correctif, import
  et tests passent ; il ne s'agit pas d'une execution du binaire installe.
- Tests ajoutes a la CI rapide : test_noethys_sl_impression_depot (7),
  test_noethys_sl_rappels_solde (7). SQLite natif temporaire et montants Decimal
  de retour SQL simules, snapshots avant/apres des ecritures ; pilote Windows,
  serveur MySQL reel et parcours UI Qt natif non qualifies dans ce lot.
- STOP-GATE : aucun build, installation ni modification de production. Source
  corrigee ne signifie pas correction disponible dans la RC7.2 installee.
  Coupe-circuit P1 des adhesions et travaux Mailjet/performance conserves.
  Les preuves definitives par branche sont consignees apres les CI rapides.

### Preuves impression depot / rappels a zero

| Branche | Rappels (arrondi du solde) | Impression (dernier code) | CI rapide |
| --- | --- | --- | --- |
| main | `e15b7346a9872c694e2ab248a3aefa570c5835d1` | `67578569ff576fb39728fb891fbe9685e12671f1` | [38774271273](https://github.com/fr4nck/Noethys-SL/actions/runs/38774271273) SUCCESS, 629 tests / 6 ignores |
| wx | `dd09c8af79e5c201104b6d988b2ee51f2e321853` | `9a667e15186d9f1d6ffe7741d117b93bdd6f3a14` | [38775138685](https://github.com/fr4nck/Noethys-SL/actions/runs/38775138685) SUCCESS, 653 tests / 10 ignores |
| qt | `d05a330fbeb3e13bbc62b633248b9c94a4dd7880` | `4ced625974b1d35431a92eb219c9f1ae81100ec4` | [38775155967](https://github.com/fr4nck/Noethys-SL/actions/runs/38775155967) SUCCESS, 605 tests / 6 ignores, code commun wx uniquement |

Correctif complementaire independant : le moteur PrintPage renvoie "pages
restantes" (False a la derniere page), mais wx.Printout.OnPrintPage attend
"page rendue" ; False y annule le travail. Retour True apres rendu dans les
deux moteurs ; pagination et signal interne conserves. Contrat confirme dans
la [documentation wxPython](https://docs.wxpython.org/wx.Printout.html#wx.Printout.OnPrintPage).
Rendu reel de 49 lignes aussi exerce via le callback wx ; test de contrat
ajoute pour les deux moteurs (derniere page et page intermediaire).

| Branche | Dernier code (callback wx) | CI finale |
| --- | --- | --- |
| main | `85343b78dde07a6b640ebbbbeaefe1e29fbbcb71` | [38776091464](https://github.com/fr4nck/Noethys-SL/actions/runs/38776091464) SUCCESS, 630 tests / 6 ignores |
| wx | `20e160bae8a12b2f241e3c8fe0fe51557448a167` | [38776849847](https://github.com/fr4nck/Noethys-SL/actions/runs/38776849847) SUCCESS, 654 tests / 10 ignores |
| qt | `71ee00fcb1d73741ce3a9e75831e9fe4085c5eb0` | [38776863577](https://github.com/fr4nck/Noethys-SL/actions/runs/38776863577) SUCCESS, 606 tests / 6 ignores, code commun wx |

Lot initial : 13 nouveaux tests ; 58 tests cibles locaux OK / 1 ignore sur les trois
arbres ; suite rapide locale main 629 / OK / 6 ignores. Une premiere execution
locale avec PYTHONUTF8=1 impose a casse le decodage du stderr natif wx d'un
sous-processus de fermeture ; reexecution dans l'environnement Windows
d'origine OK, sans modifier ni affaiblir ce test. CI main confirme la suite.
Apres le correctif de callback : 14 tests nouveaux / OK sur les trois arbres.
Portages cibles prepares puis testes ; publication wx/qt apres CI main verte.
Meme code et memes tests sur les trois branches sur ce perimetre ; les six
corrections de largeur fixe deja presentes dans wx ont ete conservees et
portees dans main/qt, sans ecraser les autres differences des branches.

| Qualification | main | wx | qt |
| --- | --- | --- | --- |
| Rappel au centime / zero exclu / un centime conserve / snapshots SQLite | VALIDÉ | VALIDÉ | VALIDÉ code commun |
| Import par package / menus / proprietes / rendu wx.MemoryDC | VALIDÉ | VALIDÉ | VALIDÉ code commun wx |
| Cause sur binaire du poste, pilote physique, serveur MySQL reel | EN ATTENTE | EN ATTENTE | EN ATTENTE |
| UI Qt native | NON APPLICABLE | NON APPLICABLE | EN ATTENTE |
| Nouveau candidat / installation utilisateur | NON EFFECTUÉ | NON EFFECTUÉ | NON EFFECTUÉ |

Prochaine etape : qualification d'un candidat Windows distinct, sur profil
synthetique isole (dont import du moteur embarque), puis recette pilote de
l'apercu et des candidats aux rappels. Aucun build ni installation revendiques
ici. Logs et bitmaps dans qualification/ hors Git ; captures terrain non copiees
dans les tests. Les commits de preuves suivants ne changent que ce document,
pas les arbres de code qualifies par les runs cites.

## Suivi Mailjet dans Noethys — 15/10/2026

- Demande explicite de Franck : implementer la consultation des etats disponibles
  dans le portail Mailjet. Depart reel verifie : main `a597b478`, wx `ca12e5a9`,
  qt `31a2a5d9`. Comparaison des trois fichiers modifies avant portage : dialogs
  identiques ; protections supplementaires de UTILS_Envoi_email propres a wx
  (_ExigerAcceptation et retour None du PDF) a conserver par patch cible.
- Nouvel ecran **Suivi Mailjet** depuis Outils du Mailer ou bouton Historique,
  soumis au droit `outils_historique/consulter`. Compte d'expedition explicite,
  destinataire/sujet/etat/derniere verification, recherche, details. Ouverture
  sans HTTP ; verification volontaire de 1 a 50 lignes, HTTP hors thread wx.
  Fermer arrete les messages suivants et abandonne les resultats non conserves,
  sans callback wx depuis le travailleur ; timeouts HTTP bornes par requete.
- Journal partage dans la categorie reservee `noethys_sl_suivi_mailjet_v1`
  de la table native `parametres`, JSON versionne par compte/MessageID.
  JSON ASCII avec echappement Unicode pour conserver les emojis sur les
  anciens serveurs MySQL utf8 a trois octets, sans modifier leur encodage.
  Aucune migration implicite. Les nouvelles acceptations sont journalisees
  par destinataire To/Cc/Bcc, sans corps, piece jointe ou cle API ; les comptes
  sont identifies par SHA256 de la cle, les secrets restent dans leur configuration
  existante. Fichier capture sur thread UI avant l'envoi unitaire hors UI.
  Une panne du journal conserve le succes d'envoi et affiche un avertissement
  de ne pas renvoyer. Aucun renvoi automatique, SMTP inchange.
- Concurrence : enregistrement idempotent sous BEGIN IMMEDIATE SQLite ou
  GET_LOCK MySQL (liberation explicite), puis commit ; mise a jour conditionnee
  a l'ancienne valeur exacte du JSON (BINARY sur MySQL), sans ecraser une
  consultation concurrente. Erreur API : garder dernier etat et date verifies,
  afficher l'erreur de consultation separement. Journal corrompu : refuser,
  ne rien effacer. Lecture des 500 dernieres entrees du compte, pas de purge.
- Ancien historique : seules traces categorie 33 avec suffixe MessageID complet
  sont proposees ; reprise volontaire apres choix confirme du compte emetteur.
  Pas de recherche approximative par sujet/adresse. Le destinataire inconnu
  est retrouve par l'API ; les traces tronquees restent non recuperables ici.
- Consultation : exclusivement GET HTTPS api.mailjet.com, sans redirection,
  identifiant entier 64 bits conserve en texte, verification compte/ID/adresse.
  `/message/{ID}` fournit l'etat ; `/messagehistory/{ID}` les evenements observes
  (100 maximum), `/bouncestatistics/{ID}` le motif d'echec si disponible.
  401/403/404/429/5xx, JSON malforme et panne reseau ne sont jamais une livraison.
  401/403/429 arretent le reste du lot. Secrets masques dans les details.
- Semantique : accepte par Send API != livre ; sent/delivered signifie accepte
  par le serveur destinataire, pas presence garantie en boite de reception.
  opened = ouverture signalee, pas preuve de lecture. Sources officielles :
  [message](https://dev.mailjet.com/docs/email-api/getting-started/retrieve-sent-message),
  [historique](https://dev.mailjet.com/docs/email-api/getting-started/view-message-history),
  [etats](https://documentation.mailjet.com/hc/en-us/articles/360048398994-Email-statuses-all-metrics-explained).
- Tests `test_noethys_sl_suivi_mailjet` : 36, OK / 1 ignore (MySQL local non
  declare). SQLite natif jetable, vrai wx, API/Send simulees ; concurrence
  enregistrement/deux postes, CAS obsolete refuse, rollback, idempotence,
  parametres etrangers preserves, secrets, limites API, fermeture en cours,
  droits refuses avant lecture DB, envoi accepte malgre panne du journal.
  Test MySQL conditionnel sur base locale neuve via `_garde_reseau` ; aucune
  connexion production. Capture de recette locale sur quatre destinataires
  example.org, ecran verifie. Test ajoute aux CI rapides.
- STOP-GATE : pas d'appel authentifie Mailjet, test serveur MySQL reel EN ATTENTE,
  UI Qt native EN ATTENTE ; qualification pilote avec compte de recette avant
  de qualifier une livraison utilisateur. Aucun email reel, schema, donnee
  production, regle financiere, coupe-circuit d'adhesion ou installateur modifie.
  Aucun suivi automatique retroactif ni promesse de reception/lecture.
  Les preuves CI et commits de portage sont consignees apres qualification.

### Preuves du suivi Mailjet

Lot initial, avec compatibilite Unicode :

| Branche | Implementation | Compatibilite Unicode (dernier code) | CI rapide |
| --- | --- | --- | --- |
| main | `7390e38369bcc5f869632f7c3911180aac71293f` | `e3cc2e2b2a0b0364370546cd4bc0ac6e6dbc16e5` | [38751242315](https://github.com/fr4nck/Noethys-SL/actions/runs/38751242315) SUCCESS, 615 tests / 6 ignores |
| wx | `792ef1a24cf910dc2e7e7ff8bbc77a4abe11db86` | `47819c107599b5b4caafd1cca3ebcd0ea548d4e1` | [38752182475](https://github.com/fr4nck/Noethys-SL/actions/runs/38752182475) SUCCESS, 639 tests / 10 ignores |
| qt | `d902947ca8fac7d780b0378342bef5cd75ea3b2d` | `559b8acf99fed335019af8347ea796b933c068e4` | [38752201133](https://github.com/fr4nck/Noethys-SL/actions/runs/38752201133) SUCCESS, 591 tests / 6 ignores, code commun wx uniquement |

Dernier correctif independant : consommer le resultat SELECT RELEASE_LOCK
avant restitution d'une connexion MySQL non bufferisee au pool ; LIMIT 1 sur
le controle d'existant pour ne laisser aucun resultat multiple en attente.
Test protocole de curseur non bufferise ajoute (36 tests module, OK / 1 ignore,
sur les trois arbres) ; le test MySQL serveur reste conditionnel et non execute.

| Branche | Dernier commit code | CI finale |
| --- | --- | --- |
| main | `675420c271377671c9d1a7a10a58dc6b71359f9d` | [38752508891](https://github.com/fr4nck/Noethys-SL/actions/runs/38752508891) SUCCESS, 616 tests / 6 ignores |
| wx | `35990787fce2d2e9fbf11ec730b32a016d6921f0` | [38753841669](https://github.com/fr4nck/Noethys-SL/actions/runs/38753841669) SUCCESS, 640 tests / 10 ignores |
| qt | `925d1d2bd15fe68c3cb89cddce07c7c1e1576b97` | [38753857972](https://github.com/fr4nck/Noethys-SL/actions/runs/38753857972) SUCCESS, 592 tests / 6 ignores, code commun wx uniquement |

Publication main puis portages cibles apres CI main SUCCESS. Tests locaux :
suite rapide 614 / OK / 6 ignores avant le dernier test Unicode ; module
Unicode 35 / OK / 1 ignore, puis final 36 / OK / 1 ignore. Sur chaque portage : 96 tests cibles / OK / 1 ignore
(suivi, acceptation, erreurs, confirmations, cycle de progression, Mailer,
changelog). Deux dependances absentes du runtime local (xlrd et psutil) ont
ete installees dans qualification/dependances uniquement pour la suite large,
sans changer l'environnement utilisateur. Premier controle statique des
boutons ajuste en explicitant les ajouts au sizer, sans affaiblir le test.
Run main initial 38750725644 annule par concurrence GitHub au profit du
correctif Unicode ; il ne constitue pas une preuve de qualification.

Nouveaux moteur, dialog et tests identiques sur les trois branches ; blob
moteur final `ac33b0aa5ad5ac4b623270486a1e139fbc2e4c71`, dialog
`e0a05ef8c613f0944b661cf9c20f0a9c069423d4`. Dialogs historiques/Mailer
identiques ; les seuls ecarts du moteur d'envoi wx restent ses protections
anterieures (_ExigerAcceptation / PDF None), conservees apres comparaison.
Pas de merge global, nouvelle branche ni force-push.

| Qualification | main | wx | qt |
| --- | --- | --- | --- |
| API simulee / journal SQLite / concurrence / fermeture wx | VALIDÉ | VALIDÉ code commun | VALIDÉ code commun |
| Serveur MySQL reel / API Mailjet authentifiee de recette | EN ATTENTE | EN ATTENTE | EN ATTENTE |
| UI Qt native | NON APPLICABLE | NON APPLICABLE | EN ATTENTE |
| Installation utilisateur / nouveau candidat Windows | NON EFFECTUÉ | NON EFFECTUÉ | NON EFFECTUÉ |

Journaux/capture synthetiques et dependances locales sont dans qualification/
hors Git ; aucun fichier sources/ modifie. La prochaine etape est une recette
pilote isolee (serveur MySQL jetable et compte Mailjet de recette, sans email
reel), puis qualification d'un candidat distinct si demande. La RC7.2 deja
installee ne contient pas cette fonctionnalite. Les prochains commits de
preuve ne changent que ce document, pas le code qualifie par ces CI.

## Cotisations automatiques multi-activites — 15/10/2026 (#426)

- Demande precisee par Franck : une cotisation individuelle par beneficiaire,
  plusieurs activites associees dans `cotisations.activites`, sans nouvelle
  facturation ; ajout de l'activite declencheuse puis des autres activites
  du meme dispositif frequentees pendant sa validite. Le selecteur manuel
  existe deja dans DLG_Saisie_cotisation et utilise les IDs separes par `;`.
- Depart initial main d4210e77, wx fc80e29b, qt a5745b99 ; nouvelles tetes
  concurrentes conservees avant integration : main
  `4ee3aeb500a52617bd9ac31d807449382a757a02`, wx
  `84d9f96e4fd71009471f7bf26c2c1a693816283c`, qt
  `cd3c938af6012e8427ef8e5aeb1ea5b9f599fe1a` (changelog/version interne).
  Nouvelles consignes AGENTS.md lues. Moteur Adhesions identique avant portage.
- Correctif : GetParticipations expose IDactivite ; CreerAdhesion renseigne
  le champ natif. CompleterActivitesAutomatiques ajoute l'union sur une
  cotisation marquee [adhesion-auto], dans sa periode inclusive, pour les
  activites liees au meme type, jusqu'a la date de reference incluse
  (aucune seance posterieure a cette date).
  Reservation/present et prestation isolee suivent les criteres existants.
- Relire la liste sous verrou du titulaire/type, transaction SQLite IMMEDIATE
  ou MySQL GET_LOCK + SELECT FOR UPDATE ; update du seul champ activites et
  historique dans une meme transaction. Rollback sur erreur ; pas de perte
  d'ajout concurrent. Garder les rattachements existants, sans doublon ; ne pas
  les retirer apres annulation. Respecter les periodes verrouillees ; rejeter
  un format invalide ou plus de 450 caracteres, sans tronquer les donnees.
- Pas de modification des cotisations manuelles, des dates/montants,
  prestations, factures, ventilations ou reglements existants. Titulaire
  personne physique/structure et payeur de la participation conserves.
- Tests locaux : 90 executes, OK, 3 ignores faute de serveur MySQL local
  declare ; dont 17 nouveaux tests (16 executes, 1 MySQL conditionnel).
  Deux processus SQLite : A lit avant ecriture, B attend le verrou puis
  relit ; les deux activites restent associees. Tests : creation depuis
  conso/prestation, cumul sans double cotisation ni prestation, idempotence,
  dates/deux annees, structures/sections/payeur, manuel, annulations, rollback,
  periode verrouillee, format et limite, facturation/ventilation preservees.
  Syntaxe compilee ; CI main SUCCESS ; preuves definitives ci-dessous.
- STOP-GATE : AUTO_CREATION_SUSPENDUE reste True et le hook de grille garde
  son retour P1. Ce lot ne reactive pas l'automatisme : cloture mensuelle,
  facture anticipee, apercu comptable et annulations controlees restent a
  terminer dans #426 ; serveur MySQL reel et UI Qt native EN ATTENTE.
  Aucun build, installation, nouvelle branche, suppression de donnees, email,
  intervention production ou alteration des notes de version livrees.

### Preuves du rattachement multi-activites

| Branche | Commit moteur/tests | CI rapide |
| --- | --- | --- |
| main | `55889badb2adc91ec1a4f0a43d75ef8ce6fe0b44` | [38744861087](https://github.com/fr4nck/Noethys-SL/actions/runs/38744861087) SUCCESS, 580 tests, 5 ignores |
| wx | `6cb8149c94b261c2935894b5be80ce8a9937038d` | [38746118910](https://github.com/fr4nck/Noethys-SL/actions/runs/38746118910) SUCCESS, 604 tests, 9 ignores |
| qt | `6fc8ce60bda1f8a088275059f21edee9ef007cd3` | [38746117092](https://github.com/fr4nck/Noethys-SL/actions/runs/38746117092) SUCCESS, 556 tests, 5 ignores ; code commun wx, pas UI Qt native |

Moteur identique (blob `9a739e2fca0b8e03026aedf19877ece53b7eb8eb`) et
deux fichiers de tests identiques sur les trois branches. Portages cibles
apres CI main, tests locaux 69 / OK / 3 ignores sur wx et qt ; leurs autres
changements, dont notes de version propres et version interne, conserves.
Pas de nouvelle branche ni force-push. Les commits de preuve suivants ne
changent que ce document ; aucune CI runtime distincte revendiquee dessus.

| Qualification | main | wx | qt |
| --- | --- | --- | --- |
| Activite declencheuse / union / non-double facturation / SQLite concurrent | VALIDÉ | VALIDÉ code commun | VALIDÉ code commun |
| MySQL reel : lecture sous verrou / union concurrente | EN ATTENTE | EN ATTENTE | EN ATTENTE |
| Activation auto apres cloture ou facture anticipee / annulations financieres | EN ATTENTE / STOP-GATE | EN ATTENTE / STOP-GATE | EN ATTENTE / STOP-GATE |
| UI Qt native | NON APPLICABLE | NON APPLICABLE | EN ATTENTE |

Le test MySQL supplementaire utilise exclusivement le serveur local de
recette autorise par `_garde_reseau`, une base `zz_test_adh_*` creee par le
test et deux processus ; il reste ignore sans NOETHYS_TEST_MYSQL_*.
Ce test conditionnel ne vaut pas preuve d'execution serveur.

Prochaine etape : qualifier ce test sur MySQL jetable et le nouveau
declenchement financier de #426 avec apercu avant validation, exclusion des
reservations futures et annulations controlees. Ne pas lever le coupe-circuit
de grille sur la seule presence du rattachement multi-activites. Pas de
modification en production, de lot retrospectif ou d'installateur dans cette
session ; les travaux #427 et les notes de version livrees restent conserves.

### Signalement Mailjet — verification en lecture seule

Franck souhaite retrouver dans Noethys les statuts accessibles sur le portail
Mailjet. Audit main : UTILS_Envoi_email.Mailjet conserve MessageID/MessageUUID
sur le message accepte ; DLG_Mailer.MemorisationHistorique ajoute les MessageID
au texte d'historique (categorie 33) pour les personnes retrouvees par adresse.
Aucun appel de consultation du statut ou de l'historique Mailjet trouve dans
les sources. Ne pas deduire la livraison de l'acceptation par Send API.

Documentation officielle verifiee :
[consulter un message](https://dev.mailjet.com/docs/email-api/getting-started/retrieve-sent-message),
`GET /v3/REST/message/{MessageID}`, et
[historique d'un message](https://dev.mailjet.com/docs/email-api/getting-started/view-message-history).
Piste a developper : conserver une correspondance durable par destinataire,
puis consulter et afficher les statuts fournisseur dans Noethys ; le texte
libre et borne de l'historique ne constitue pas a lui seul un registre exhaustif.
Cette consultation pourrait se faire depuis le poste, sans serveur de webhooks
obligatoire. Aucun code de suivi livre dans cette session, aucune connexion
authentifiee au compte Mailjet, aucune lecture des cles ni aucun email envoye.


## Reprise #427 — preparation client des consommations — 15/10/2026

- Depart distant verifie : main `0b2e2d47b2a899bc650cc6ec1090b67129897dbe`,
  wx `23a49c7d129d7ce7c6167437c6fb939eaa835e53`,
  qt `9f27a1378ce28c96f79e8ff5d080e2f3d77b45c1`. Fichiers grille, GestionDB et
  handlers OK identiques ; arbres globaux divergents, aucune fusion globale.
  CI precedentes 38724108383 (main f04e68a) et 38724128232 (wx 23a49c7) SUCCESS.
- Audit, protocole et mesures : [PERFORMANCE_CONSOMMATIONS_427.md](PERFORMANCE_CONSOMMATIONS_427.md).
  Vingt champs reecrits par UPDATE, connexions parametres, Commit historique,
  risque d'ecrasement concurrent et rafraichissement famille apres modal examines.
  Source officielle mysqlclient 2.2.7 reproduite sans serveur : 1/10/50 UPDATE
  donnent 1/10/50 appels transport, INSERT regroupe ; version RC7.2 non deduite.
- Lot runtime limite : ne preparer les vingt champs que si la consommation
  genere une ecriture. Suppressions implicites et multihoraires conservees.
  Aucun SQL, Commit, historique, tarif, facture, annulation ou adhesion change.
  Benchmark synthetique 10 000 lignes / une modification : mediane neuf essais
  33,073 -> 2,120 ms ; 50/50 modifications 0,426 -> 0,426 ms. Aucun gain terrain
  revendique, nombre d'acces SQL identique.
- Qualification locale : 67 tests Python 3.10/wx, OK, deux skips MySQL ; huit
  tests nouveaux dont SQLite deux connexions/deux threads et attente de verrou.
  Comparaison avant/apres 45 combinaisons : SQL/valeurs/historique/commits/erreurs
  identiques. Nouveau test ajoute a la CI rapide ; resultat final SUCCESS, voir matrice ci-dessous.
- STOP-GATE : moteur Docker local indisponible, aucune recette serveur MySQL
  ni UI Qt effectuee. UPDATE groupes/champs reduits/pooling/transactions restent
  EN ATTENTE. RC7.2 ffd28de ne contient aucun lot #427. Aucun build/installation,
  production, email, donnees existantes ou references historiques touches.
- Copie isolee locale : `optimisation-consos-20261015` dans l'espace du projet ;
  `qualification/` contient sources de mesure et journaux synthetiques hors Git.
  Sources synchronisees et anciens WIP preserves. Publication main puis portages
  cibles wx/qt effectues ; trois CI SUCCESS, voir preuves finales ci-dessous.

### Preuves finales du lot #427 — 15/10/2026

| Lot / preuve | main | wx | qt |
| --- | --- | --- | --- |
| Preparation client #427 | VALIDÉ `2aaa3046a6a4bd928eb8ad5d6f02b74c3851f87b` | VALIDÉ `cc436b2c05ccedf30fc823dd82b332cb7324481b` | VALIDÉ code commun `ab23538919321fe721bf102e94eb56f086ccf68b` |
| CI rapide syntaxe + contrats Windows | [38732132634](https://github.com/fr4nck/Noethys-SL/actions/runs/38732132634) SUCCESS, 553 tests / 4 skips | [38732766252](https://github.com/fr4nck/Noethys-SL/actions/runs/38732766252) SUCCESS, 577 tests / 8 skips | [38732765420](https://github.com/fr4nck/Noethys-SL/actions/runs/38732765420) SUCCESS, 539 tests / 4 skips ; commun wx, pas UI Qt native |
| Tests locaux transports/profilage/nouveau lot | VALIDÉ, inclus dans 67 tests | VALIDÉ, 19 tests | VALIDÉ commun, 19 tests |
| Serveur MySQL / UPDATE groupes / pooling | EN ATTENTE / STOP-GATE | EN ATTENTE / STOP-GATE | EN ATTENTE / STOP-GATE |
| Recette interface Qt native | NON APPLICABLE | NON APPLICABLE | EN ATTENTE |

Les blobs CTRL_Grille.py (`0b92eaa09815b5bb3ad6385b1bfd3a712e88dbca`),
GestionDB.py (`c4ed9fd040430883609f7e2169240d484ede6352`), harnais, benchmark et
nouveau test sont identiques sur les trois commits de code. Chaque portage
a pour parent la tete initiale de sa branche. Les workflows sont adaptes
par ajout du seul nouveau test, sans perdre leurs autres contrats. Aucune
nouvelle branche, fusion globale ni force-push ; publication main apres
tests locaux, puis wx/qt apres CI main SUCCESS. Les notes de preuve ajoutees
ensuite ne changent que docs/dev/REPRISE_CODEX.md, sans nouvelle CI runtime.

L'issue [#427](https://github.com/fr4nck/Noethys-SL/issues/427) reste ouverte :
un cout client est reduit, le goulet terrain n'est pas mesure. Pas de nouvelle
qualification globale des differences entre branches, pas de release stable
revendiquee. RC7.2 ffd28de et l'installation Windows restent hors de ce lot.
Prochaine etape et STOP-GATE : serveur jetable synthétique, mesures SQL avec
pilote/version explicites et rafraichissement famille post-modal ; aucune
execution de recette sur production.


Document de transmission (Claude Code → Codex). Mettre à jour en fin de chaque session.


## Lot limité Noe-032 — ZIP partiel sur fichier absent — 10/10/2026

- **Départ vérifié** : `main = wx = qt = 025112dd55744988989f0c3f321e76557f0fe11d` ; `master = b0be3c7ebdf2d69d6028eb4fd6fc08e340a68b9e`, toujours branche par défaut. [CI wx #38033543533](https://github.com/fr4nck/Noethys-SL/actions/runs/38033543533) : succès au SHA antérieur `32841c42`. Consignes lues : `AGENTS.md`, ce document, PMSL-Arch `main` (`cbe3e6e65b53d98783a5192846979aedbe375465`), politique de développement, ADR-006/010 et gouvernance Actions.
- **Code : `4b5dc5103d8af14e5eab1500368be43e55061415`**. Deux lignes ferment puis suppriment le ZIP temporaire lorsqu'un fichier local manque. Test historique `test_missing_local_file_closes_zip_and_removes_partial_archive` repris avec assertions intactes et harnais AST isolé ; deux cas ajoutés : absence après une première entrée avec destination existante préservée, sauvegarde complète réussie. Test inclus en CI rapide ; restauration SQL inchangée.
- **25 tests historiques inchangés réutilisés** (`test_noe_032_backup_integrity.py`, `test_noe_032_restore_flow.py`) : 25/25 sur le module `master`, mocks et données fictives. Sur `main` initial : 5 succès / 5 échecs / 15 erreurs ; candidat : 6 succès / 5 échecs / 14 erreurs. Seul le test du lot passe de défaut à succès ; les 19 écarts préexistants hors lot (SQL, exceptions sous-processus, nettoyage email…) restent EN ATTENTE. Journaux hors Git dans l'espace Codex : `tmp/qualification-noe032/main-before.log` et `main-after.log`.
- **Qualification** : verrou ZIP Windows reproduit avant correction ; 15 tests ciblés réussis après, compilation et diff contrôlés. [CI main #38036079406](https://github.com/fr4nck/Noethys-SL/actions/runs/38036079406) : SUCCÈS syntaxe Ubuntu et 96 tests Windows, réseau isolé, sans packaging. CI wx : [wx #38036255934](https://github.com/fr4nck/Noethys-SL/actions/runs/38036255934), SUCCÈS Ubuntu et Windows au même SHA de code.
- **Propagation prouvée** : les trois branches étaient identiques, sans commit propre à perdre. Après CI main, push atomique fast-forward non forcé de `wx`/`qt` vers `4b5dc510`, HEAD distants revérifiés. Une seule note documentaire pour ce lot, également propagée par fast-forward.

| Périmètre au commit de code `4b5dc510` | `main` | `wx` | `qt` |
| --- | --- | --- | --- |
| ZIP partiel, 3 tests | VALIDÉ + CI | VALIDÉ, arbre identique + CI wx | VALIDÉ code commun ; UI Qt EN ATTENTE |
| Gardes réseau/fermeture ZIP antérieures, 12 tests conservés | VALIDÉ + CI | CODE IDENTIQUE + CI wx | CODE IDENTIQUE ; UI Qt EN ATTENTE |
| Protections SQL avancées / restauration MySQL réelle | EN ATTENTE / STOP-GATE | EN ATTENTE / STOP-GATE | EN ATTENTE / STOP-GATE |

- **PR #104 examinée, non dupliquée** : HEAD `bbbddddec529074729acc1bed5f947361b3ee4a9`, MySQL 5.5.62 épinglé par digest, `127.0.0.1:3308`, `.env` hors Git, scripts start/import/reset. README : ancienne ADR-004 à remplacer par ADR-006 ; comptage de tables insuffisant pour qualifier la restauration. Inventaire Docker en lecture seule : seul `noethys-mysql57` actif (`127.0.0.1:3307`), laissé intact.
- **Suite / limite** : aucune recette SQL réelle dans ce lot indépendant. Réutiliser #104 sur environnement isolé et données 100 % synthétiques pour qualifier dumps complets/tronqués, manifeste, marqueur et postconditions avant portage SQL. Aucune base existante touchée, migration, nouvelle branche, fusion globale, suppression ou force-push ; `master` et PR préservées.

## Synchronisation et durcissement Noe-032 — 10/10/2026

- **Non-régression interbranches** : invariant ajouté dans `AGENTS.md` et matrice initiale documentée par le commit `edc014bc9de286cee24c5f19d32c743763246eca`. Les anciennes références `wx` (`98af4873`) et `qt` (`6deee441`) étaient des ancêtres stricts de `main`, avec respectivement 0 commit unique ; chacune a été avancée par fast-forward non forcé vers `edc014bc`, sans perte ni conflit. Run [wx #38032993554](https://github.com/fr4nck/Noethys-SL/actions/runs/38032993554) : Ubuntu et tests Windows **SUCCÈS**.
- **Lot indépendant Noe-032** : le commit `c6130084c04e023a5a014bdd51b694176f76d1ee` reprend uniquement cinq appels `fichierZip.close()` avant les retours d'annulation ou d'erreur dans `Restauration`, présents historiquement dans `master`. Le test `tests/test_noethys_sl_restore_network_config.py` couvre les chemins locaux/réseau factices et vérifie statiquement les six retours précoces. Aucune restauration SQL, migration ni base réelle.
- **Qualification des tests** : run [main #38033235384](https://github.com/fr4nck/Noethys-SL/actions/runs/38033235384) **ÉCHEC DU TEST FICTIF UNIQUEMENT** : entrée sans suffixe `.sql` n'activant pas le chemin d'annulation réseau. Commit `32841c42d8f45f34ff96d4f8737c8ecf546b995c` : correction d'une seule ligne dans la donnée de test ; le code de production `c6130084` reste inchangé. Run [main #38033397162](https://github.com/fr4nck/Noethys-SL/actions/runs/38033397162) : Ubuntu et tests Windows **SUCCÈS**.
- **Propagation contrôlée** : `main`, `wx` et `qt` ont été vérifiées au même SHA `32841c42d8f45f34ff96d4f8737c8ecf546b995c` après deux fast-forwards non forcés des branches `wx` et `qt`. CI de requalification `wx` : [#38033543533](https://github.com/fr4nck/Noethys-SL/actions/runs/38033543533), **SUCCÈS (tests Ubuntu et Windows)**.
- **Matrice actualisée de non-régression au SHA `32841c42` :**

| Périmètre commun / interface | `main` | `wx` | `qt` |
| --- | --- | --- | --- |
| Deux garde-fous réseau Noe-032, tests `a09df2cc` et `64f68c0e` | VALIDÉ (CI main) | CODE IDENTIQUE, SUCCÈS (tests Ubuntu et Windows) | CODE IDENTIQUE ; recette Qt EN ATTENTE |
| Fermeture ZIP sur annulations/erreurs, `c6130084` et `32841c42` | VALIDÉ (CI main #38033397162) | CODE IDENTIQUE, SUCCÈS (tests Ubuntu et Windows) | CODE IDENTIQUE ; recette Qt EN ATTENTE |
| Résolution `ObjectListView`, `eab750f6` | VALIDÉ | CODE IDENTIQUE, SUCCÈS (tests Ubuntu et Windows) | CODE IDENTIQUE ; recette Qt EN ATTENTE |
| Restaurations MySQL/MariaDB réelles et protections SQL avancées de `master` | NON INTÉGRÉ / EN ATTENTE | NON INTÉGRÉ / EN ATTENTE | NON INTÉGRÉ / EN ATTENTE |
| Interface Qt native | NON APPLICABLE | NON APPLICABLE | NON QUALIFIÉE |

- **Environnement de recette existant** : la PR [#104](https://github.com/fr4nck/Noethys-SL/pull/104) contient déjà `dev/db/compose.yml` (MySQL 5.5.62 épinglé, port `127.0.0.1:3308` par défaut) et scripts PowerShell de démarrage. Elle n'est **ni fusionnée ni qualifiée localement dans cette session** ; ne pas dupliquer son travail. Ce serveur ancien doit être lancé uniquement en environnement jetable isolé, avec données synthétiques et secrets hors Git.
- **Stop-gates / suite** : 25 tests Noe-032 historiques `master` réussis sur mocks (run #35826834598) mais **non requalifiés sur `main`**. Aucun serveur réel MySQL/MariaDB de recette accessible dans cette session : manifeste SQL, marqueur terminal, postconditions et restauration d'une base fictive demeurent bloqués. `master` reste la branche GitHub par défaut, le contenu divergent est préservé, huit PR ouvertes. Aucune branche créée, aucun force-push, PR close ou suppression de branche ; aucun packaging lourd.
- **Prochaine action** : qualifier la PR #104 ou un environnement équivalent sur une machine de recette, lancer sauvegarde puis restauration sur **données 100 % synthétiques**, requalifier les 25 tests contre le candidat `main`, puis intégrer les protections avancées sous preuve avant une éventuelle bascule de branche par défaut.

## Non-régression interbranches — contrôle initial du 10/10/2026

- **Source de vérité :** comparer les SHA et arbres Git du dépôt `fr4nck/Noethys-SL` ; ne pas déduire l'équivalence du simple nom des branches.
- **SHA avant synchronisation :** `main` = `28ebcaf7aa096001f49c354486e38f641914a746`, `wx` = `98af487389c4a1fd392f3b1fc2c75186066e6edc`, `qt` = `6deee441050fb653c95901a8ae4dd1145c4ed96e`. `master` = `b0be3c7ebdf2d69d6028eb4fd6fc08e340a68b9e`, toujours branche GitHub par défaut, à conserver.
- **Comparaisons prouvées :** `wx` est ancêtre strict de `main` (12 commits seulement sur `main`, zéro commit propre à `wx`) ; `qt` est également ancêtre strict (14 commits seulement sur `main`, zéro commit propre à `qt`). Pas de merge global requis. Ces chiffres sont ceux **avant** le commit de cette politique et doivent être revérifiés immédiatement avant un éventuel fast-forward.
- **Protection permanente :** invariant de non-régression maintenant dans `AGENTS.md`. Pour chaque future publication, vérifier la propagation des correctifs communs et les comportements propres aux interfaces. Une ascendance Git seule ne vaut pas recette Windows/Qt.
- **Matrice au point de contrôle (avant propagation)** :

| Ensemble testé / correctif | `main` | `wx` | `qt` |
| --- | --- | --- | --- |
| Noe-032 — refus sauvegarde réseau sans connexion (`a09df2cc`, CI #37981580013) | VALIDÉ | ABSENT, à propager | ABSENT, à propager |
| Noe-032 — refus restauration réseau sans connexion (`64f68c0e`, CI #37982029069) | VALIDÉ | ABSENT, à propager | ABSENT, à propager |
| `ObjectListView` — résolution imports (`eab750f6`, CI #37972096356 puis #37979402584) | VALIDÉ | ABSENT, à propager | ABSENT, à propager |
| Restauration MySQL/MariaDB réelle, manifeste SQL, postconditions | EN ATTENTE (non intégré) | EN ATTENTE | EN ATTENTE |
| Parcours UI spécifiques Qt | NON APPLICABLE à ce stade (code actuel wx) | NON APPLICABLE | EN ATTENTE (aucune recette Qt) |

- **Propagation prévue :** mettre `wx` et `qt` au HEAD du socle commun par fast-forward avec vérification de SHA, puis constater réellement les nouvelles références. Cette section constitue l'état *avant* l'opération : ne pas conclure que la propagation a eu lieu sur cette seule documentation.
- **Stop-gates inchangés :** MySQL/MariaDB jetable requis avant qualification réelle des restaurations et avant reprise des protections SQL avancées ; recette UI Windows et Qt nécessaire avant leur publication. Aucune nouvelle branche, aucun force-push, suppression ou modification des données de production.

## Lot Noe-032 qualifie — 09/10/2026

- **Branche et code vérifiés** : `main` à `64f68c0eaae13a2771944ff49cbb556810123849` avant cette note. `master` n'a pas été modifiée ; GitHub conserve `master` comme branche par défaut.
- **TERMINÉ / VALIDÉ — Sauvegarde réseau sans paramètres** : commit `a09df2cc386c6321ae9db7682436dbb0b551a0f3`. `Sauvegarde` refuse les fichiers réseau lorsque `dictConnexion is None` avant toute création de ZIP, y compris en mode mixte local + réseau. Trois tests unitaires isolés dans `tests/test_noethys_sl_backup_network_config.py` (réseau seul, mixte, chemin local conservé), ajoutés à la CI rapide. Run [#37981580013](https://github.com/fr4nck/Noethys-SL/actions/runs/37981580013) : succès syntaxe Ubuntu et tests Windows.
- **TERMINÉ / VALIDÉ — Restauration réseau sans paramètres** : commit `64f68c0eaae13a2771944ff49cbb556810123849`. `Restauration` refuse le réseau sans `dictConnexion`, ferme le ZIP et s'arrête avant toute extraction locale, même en restauration mixte. Trois tests unitaires isolés dans `tests/test_noethys_sl_restore_network_config.py` (archive factice, refus réseau et mixte, parcours local conservé), ajoutés à la CI rapide. Run [#37982029069](https://github.com/fr4nck/Noethys-SL/actions/runs/37982029069) : succès syntaxe Ubuntu et tests Windows.
- **Portée exacte** : deux gardes de refus et six tests, sans modification de schéma, de formats `.nod/.noc`, de code de restauration SQL exécutée, de production ou de données réelles. Aucune branche créée, aucune branche ni PR supprimée/fermée, aucun force-push ni packaging lourd. Vérification de tests sur GitHub Actions ; aucune recette MySQL réelle ni tests intégrés locaux de toute l'application lors de cette passe.
- **CONFIRMÉ SUR `master`, NON RÉIMPORTÉ** : le run historique [#35826834598](https://github.com/fr4nck/Noethys-SL/actions/runs/35826834598) réussissait les 25 tests Noe-032 (10 intégrité de backup, 15 flux restauration) contre des simulations MySQL. Les blobs des deux fichiers de test et du module du commit testé sont identiques à ceux du HEAD `master` contrôlé. Ceci ne valide PAS leur exécution sur `main`.
- **BLOQUÉ / STOP-GATE** : transfert du manifeste SHA-256 SQL, analyse de dump tronqué, marqueur terminal, postconditions MySQL (tables, vues, événements, fonctions) et nettoyage des secrets sans preuve d'une recette contre un serveur MySQL/MariaDB jetable. L'environnement de cette session ne possède pas de serveur ou client MySQL/MariaDB ni Docker/Podman et ne peut pas accéder à GitHub par `git clone` local. Aucun test de restauration sur une base existante, ni publication.
- **PROCHAINE ACTION CONCRÈTE** : sur une machine/runner de qualification disposant de MySQL ou MariaDB, créer des bases **entièrement fictives et jetables**, sans profil Portable ni accès réseau de production ; qualifier à la fois dumps complets, tronqués, hérités sans manifeste, échecs de sous-processus et restauration partiellement réussie ; requalifier les 25 tests historiques sur le candidat `main` sans affaiblir les assertions ; porter ensuite les protections Noe-032 par petits lots et mesurer les postconditions.
- **Bascule de branche par défaut : NON FAITE**. `master`, `wx`, `qt`, RC et les huit PR restent des références à préserver tant que les travaux uniques ne sont pas qualifiés.

## Poursuite consolidation — 09/10/2026 (soir)

- **Inventaire confirmé** : `master` reste divergente. Fonctions sauvegarde/restauration MySQL et contrôles Noe-032 présents dans `master` mais pas dans `main` : ne pas fusionner intégralement ni effacer `master` avant qualification ciblée. Exemples : `_AjouterManifesteIntegriteSQL`, `_VerifierPostconditionRestaurationMySQL` ; tests `tests/test_noe_032_backup_integrity.py` et `tests/test_noe_032_restore_flow.py` restés sur `master`.
- **Correction isolée appliquée sur `main`** : commit `05022fae5946a4db486b3ed973b9d70453b0abaf`, `UTILS_Sauvegarde.GetListeFichiersZIP` ferme l'archive ZIP avec `with`, comme dans `master` ; test sans base réelle `tests/test_noethys_sl_backup_zip_lifecycle.py`. Commit `b0d71728fe44e52e2483e1353299eb35744ca282` ajoute ce test à la CI rapide.
- **CI** : run de qualification du dernier commit [#37979402584](https://github.com/fr4nck/Noethys-SL/actions/runs/37979402584), en attente du résultat au moment de la rédaction. Le run précédent a été annulé par la concurrence automatique.
- **Aucune autre modification** : aucun `master`/RC/WIP modifié, aucune création ou suppression de branche, aucun force-push, aucun schéma SQL modifié. La branche par défaut demeure `master`. Ne pas confondre CI rapide et qualification complète de restauration réseau.
- **Suite** : porter le lot Noe-032 uniquement après revue des 2 suites de tests, des contrats historiques `.nod/.noc` et d'une restauration réelle sur base fictive isolée. Puis traiter les domaines tiers, interventions et synchronisation sans réactiver implicitement d'anciens comportements Repens.

## Mise à jour de consolidation — 09/10/2026

- **But confirmé :** `main` sera la branche par défaut après qualification. Seules les branches de développement `main`, `wx`, `qt` seront conservées à terme ; aucune nouvelle branche ne doit être créée. Consignes applicables dans `AGENTS.md`.
- **Opérations Git réalisées :** `main` a avancé par fast-forward depuis `6deee441050fb653c95901a8ae4dd1145c4ed96e` jusqu'au HEAD `wx` `98af487389c4a1fd392f3b1fc2c75186066e6edc` (deux commits CI seulement). Ensuite, ajout du déclenchement rapide sur `main` par `b36f037ce9934d508f71bdbbff8466e663e54845`, puis ajout des règles `AGENTS.md` via `f8f889ba98145f47f5d6c37d9711751f7779c087`.
- **Non effectués :** aucune création/suppression de branche, aucune fusion de `master`, aucun force-push, aucun changement de branche par défaut, aucune modification SQL ou du code métier, aucun test sur la base réelle.
- **Références au moment du contrôle :** `wx` = `98af4873` ; `qt` = `6deee441` ; `master` = `b0be3c7e`. `master` est toujours la branche par défaut sur GitHub et doit être préservée : son arbre diverge fortement de `main` (modules Repens, synchronisations, interventions, autres code/tests/docs). Ne jamais inférer d'un nombre de commits que tout le code correspondant est absent ou présent.
- **Qualification du 09/10 :** premier run [#37971043856](https://github.com/fr4nck/Noethys-SL/actions/runs/37971043856) : syntaxe OK, trois échecs Windows sur un import `ObjectListView` masqué par `sys.path`. Correctif ciblé `eab750f65c6674edcf4068f922c034bde28d18cb` (`Chemins.py` et test), correction de l'alias du test `7b3a0307147116f0f8e348390fb1cb50a5b8dbe6`. Run [#37972096356](https://github.com/fr4nck/Noethys-SL/actions/runs/37972096356) sur `7b3a0307` : **succès Ubuntu et tests Windows**, sans packaging lourd. Ceci ne remplace ni recette Windows complète ni validation Connecthys réelle.
- **Prochaine étape :** classer les différences métier encore utiles de `master` et des branches RC/WIP, ne réimporter que les correctifs prouvés, requalifier sur la ligne cible, puis changer la branche par défaut dans les paramètres GitHub après l'accord de publication. Ne pas effacer `master` ni fermer une PR non intégrée avant préservation vérifiée.


## 1. Dossier, branches, commits

- Dossier principal : `C:\Users\Ordi\Documents\GitHub\Noethys` (poste 5700x), dépôt `fr4nck/Noethys-SL`.
- Invariant PMSL-Arch : trois branches seulement, `main` (moteur), `wx`, `qt`. Au 08/10/2026 elles pointent sur le même commit (tout le code actuel est wx ; la séparation moteur/UI n'est pas commencée).
- Base de `main` : ligne RC2/RC2.1 en service (`fea13ce7`, tag `noethys-sl-0.1.0-rc.2.1`), puis :
  - fusion des deux commits divergents `integration/rc2-convention-recovery-20261004` (`cc39c887`) ;
  - fusion de la ligne de secours `rescue/noethys-sl-20261004` / `d9b70c2b` (`7be696f9`) ;
  - reprise thématique du travail non commité de `Noethys-RC2-clean` (instantané de diagnostic `d08e37fb`, objet local non référencé) ;
  - corrections listées ci-dessous.
- Worktrees existants (non supprimés) : `Noethys-RC2` (`integration/rc2-convention-recovery-20261004`, propre, intégrée) et `Noethys-RC2-clean` (HEAD détaché `8b3789d9`, **modifications non commitées conservées** ; éléments volontairement non repris : `DialogFondu`/`UTILS_Transitions`, ancienne variante Word, suppression du Toaster d'accueil).
- PMSL-Arch : `main` porte `66e5e06` (registre TRV-016/031/032) et `9dc3f97` (règle du titulaire de l'adhésion). La branche locale de travail de ce dépôt reste `docs/profil-poste-5700x-2026-09-24`.

## 2. Corrections terminées et preuves

| Sujet | Commits | Preuve |
|---|---|---|
| Boutons Mode / Émetteur de la saisie d'un règlement (TAILLE_IMAGE float refusé par Phoenix) | `c17fdf27` | `tests/test_noethys_sl_parametrage_reglement.py` (échoue sans correctif) ; artefact : dialogues ouverts par Paramétrage > Comptabilité, ajout + persistance en base fictive ; RC2.1 publiée : aucune fenêtre |
| Adhésions : chevauchement refusé, au plus une adhésion à venir | `746bbd6e` | `test_noethys_sl_adhesions.py` |
| Adhésions : signalement « à vérifier » (fenêtre ou historique) | `9eac1977` | `test_noethys_sl_adhesions_signalement.py` ; simulation portail (sans Connecthys) |
| Adhésions : sauvegardes simultanées (SQLite `BEGIN IMMEDIATE`, MySQL `GET_LOCK` + InnoDB exigé), aucune écriture partielle | `aee1626e` | `test_noethys_sl_adhesions_concurrence.py` : deux processus, SQLite et MySQL 5.7 local ; ancien code = 2 adhésions + 2 prestations |
| Adhésions : titulaire (structure personne morale / chaque personne d'une famille) | `7f56aecf` | `test_noethys_sl_adhesions_titulaire.py` (6/8 échouent avec l'ancien code) |
| Sortie Word : écriture atomique, refus des mots-clés inconnus | `f0d90147`, doc `200e148f` | `test_vanilla_convention_docx.py` |
| Devis d'une famille sans adresse (None refusé par wx) | `cdf8ecc5` | `test_noethys_sl_devis_adresse_incomplete.py` ; PDF de devis contrôlés (avec/sans adresse, règlement non ventilé) |
| Noedoc : blocs flottants des conventions sans débordement | `d16d907c`, `e6c9f2de` | `test_noethys_sl_noedoc_ecoulement.py` ; captures Windows 3 modèles × 2 tailles |
| Garde des tests (production) | `4a3739f7`, `03b56fca`, `aee1626e`, `b9c8b386` | suite complète + 72 modules seuls : 0 connexion au pilote MySQL |
| Module `etat_global` exécuté par unittest | `da8cd8ec` | 40 tests, 1 échec attendu documenté |
| Incident et diagnostics | `5dafe288`, `9f0f007f` | voir § 9 |
| Procédure de recette et fichier fictif | `169a93b0` | `docs/recette/RECETTE_CANDIDAT_2026-10-08.md` |

Résultat global au commit `e6c9f2de` : 661 tests OK (1 échec attendu), sous garde réseau et avec le MySQL local.

## 3. Modifications non commitées

Aucune dans `Noethys` hors éléments locaux ignorés volontairement (jamais à committer) : `local-diff.txt`, `local-status.txt`, `portable-inventory.txt`, `tracked-files.txt` (inventaires préexistants) et `noethys/Portable/` (**profil réel pointant vers la base de production**).

## 4. Commandes

Depuis `C:\Users\Ordi\Documents\GitHub\Noethys` :

```powershell
# Suite complète (garde réseau incluse dans chaque module)
.venv310\Scripts\python.exe -m compileall -q noethys tests
.venv310\Scripts\python.exe -m unittest discover -s tests
# Avec le serveur MySQL local de test (voir § 5)
$env:NOETHYS_TEST_MYSQL_HOST="127.0.0.1"; $env:NOETHYS_TEST_MYSQL_PORT="3307"
$env:NOETHYS_TEST_MYSQL_USER="root"; $env:NOETHYS_TEST_MYSQL_PASSWORD="<mot de passe du conteneur>"
.venv310\Scripts\python.exe -m unittest tests.test_noethys_sl_adhesions_concurrence
```

Build portable (reproduit `.github/workflows/noethys-sl-windows.yml`) dans un environnement propre :

```powershell
python -m venv <build>\venv
<build>\venv\Scripts\python.exe -m pip install -r requirements.txt   # sans la ligne « pyttsx »
<build>\venv\Scripts\python.exe -m pip install pyttsx3 wxPython==4.2.5 "pyinstaller>=6,<7"
<build>\venv\Scripts\pyinstaller.exe --noconfirm --clean packaging/vanilla-noethys.spec
# puis BUILD-INFO.txt et Compress-Archive -Path dist/Noethys (voir le workflow)
```

`.venv310` ne contient ni pytest ni PyInstaller ; Inno Setup (Setup.exe) n'est pas installé sur le poste.

## 5. MySQL Docker de test

- Conteneur `noethys-mysql57`, MySQL 5.7.44, InnoDB par défaut, `127.0.0.1:3307`, utilisateur `root` ; mot de passe connu de Franck, **jamais dans Git**.
- Bases existantes à ne pas modifier : `docker_mad*`, `docker_mairies*`, `docker_pelemele_*`.
- Les tests créent puis suppriment uniquement des bases `zz_test_adh_<aléa>` ; `_garde_reseau.ServeurMySQLDeTest()` n'autorise que l'hôte local déclaré.

## 6. Artefact portable existant (candidat local non publié)

- `C:\Users\Ordi\Documents\GitHub\Noethys\dist\Noethys-SL-0.1.0-rc.2+e6c9f2de-local-Windows-portable.zip`
- Commit `e6c9f2deb172b9f0041bc6d1a9c11b29b717ebe2` ; SHA-256 `5967EDADC68DE302D14B62A3640F2A1449EBCBAA25E36F4973B6CB06AB362FE8`.
- Bytecode des 29 modules modifiés depuis RC2.1 identique au commit. Titre affiché encore « RC2 » ; `BUILD-INFO.txt` porte le commit.

## 7. Sauvegarde

`C:\Users\Ordi\Documents\Sauvegardes-Noethys\Noethys-avant-consolidation-20261008-112618.tar` (1,58 Go, Noethys + Noethys-RC2 + Noethys-RC2-clean, `.git` commun ; `git fsck` propre sur extraction). Seule copie de l'état d'origine de `Noethys-RC2-clean` hors du worktree.

## 8. Processus et ressources temporaires

- Processus actifs : `C:\Noethys\Noethys.exe` (instance de l'utilisateur, **ne pas toucher**) ; conteneur `noethys-mysql57`. Aucune instance de test restante.
- Temporaires (scratchpad Claude Code, supprimables) : environnement de build, environnement pywinauto, copie extraite de l'artefact avec profil Portable fictif et fichier `Recette`, RC2.1 publiée téléchargée, captures et scripts de recette.

## 9. Incident du 08/10/2026 (production)

Rapport : `docs/incidents/2026-10-08-tests-base-reseau.md` ; famille TRV-032 dans PMSL-Arch `docs/AUDIT_BUGS_TRANSVERSAUX.md`. Quatre exécutions de la suite avant la garde, 31 connexions chacune ; au plus une écriture possible (`parametres` email/timeout vide) ; **aucune écriture confirmée**. Contrôle en lecture seule : `docs/diagnostics/diagnostic_adhesions.sql`, requêtes 9 et 9 bis.

## 10. Règle métier des adhésions

Référence : PMSL-Arch `docs/REGLES_ADHESION_ACTIVITES.md` ; implémentation `docs/metier/ADHESIONS_AUTOMATIQUES.md`.

- Structure (association, école/collectivité, organisme, entreprise : personne morale titulaire de la famille) : **une adhésion pour la structure**, quelles que soient ses sections, activités ou représentants.
- Famille de personnes physiques : **une adhésion par personne qui participe**, couvrant toutes ses activités, jamais commune à la famille.

## 11. Tâches restantes (par priorité)

**P0**
1. Diagnostic réel d'Arthur (famille 688) **non effectué** : exécuter en lecture seule `docs/diagnostics/diagnostic_adhesions.sql` (identification par rattachement, puis par IDindividu) ; ne corriger aucune donnée.
2. **Validé en recette fictive par Codex** : boutons Mode / Émetteur depuis la saisie d'un règlement dans le portable, avec création effective des deux éléments. La recette par le comptable sur données fictives reste possible ; ne jamais ouvrir la production avec le candidat.
3. Contrôle en lecture seule de la ligne `parametres` de l'incident (requêtes 9 / 9 bis).

**P1**
4. Recette **125 % et 150 %** effectuée : règlement et devis accessibles ; crash Noedoc au double-clic isolé et corrigé. Nouveau portable à retester graphiquement ; voir § 13 pour les limites exactes.
5. **Corrigé et validé** : crash à la fermeture après « Rappel de sauvegarde ». Arrêt des timers du bandeau avant destruction (commit source `db27767b`) ; nouveau portable testé sur Recette, fermeture normale avec code 0. Voir § 12.
6. **Aucune recette Connecthys réelle** : seul le traitement d'une demande de réservation a été simulé localement (grille, adhésion, signalement).
7. Avant publication officielle : numéro de version (RC3), notes de version, reciblage du workflow `noethys-sl-windows.yml` (déclencheur actuel `release/noethys-sl-0.1.0`), Setup via la CI.

**P2 — à préserver, ne rien supprimer sans décision de Franck**
8. Ligne **Upgrade** `origin/master` (1 478 commits propres, non intégrée à `main`).
9. 144 branches distantes non intégrées à `main` (10 déjà intégrées : `integration/rc2-…`, `release/noethys-sl-0.1.0`, `maintenance/vanilla`, etc.).
10. Trois **stashes** du 25/09/2026 (dépôt commun) à examiner avant toute résorption.
11. Worktrees `Noethys-RC2` et `Noethys-RC2-clean` : résorption après recette et accord sur les éléments non repris.
12. Famille de défauts « valeur par défaut évaluée à l'import » (`GenerationNomDoc`, 14 occurrences) : à ratisser.


## 12. Reprise Codex — 08/10/2026

- Push vérifié : `main`, `wx`, `qt` sur `a66e404a` ; PMSL-Arch `main` sur `9dc3f97`.
- Portable e6c9f2de testé dans une extraction dédiée avec le fichier SQLite fictif
  **Recette**, sans profil réel. Parcours fiche famille > saisie d'un règlement :
  bouton Mode, création `MODE RECETTE CODEX`, bouton Émetteur, création
  `EMETTEUR RECETTE CODEX` ; les deux éléments apparaissent dans leurs listes.
  Le règlement de test a été annulé ; aucune base réelle touchée.
- Crash reproduit dans ce portable : exception Windows `0xc0000005` dans
  `wxbase32u_vc140_x64.dll`. Reproduit aussi depuis les sources sans fichier
  ouvert et sans Noedoc. La piste Noedoc n'explique pas ce cas.
- Isolation : sans le panneau éphéméride, la fermeture réussit ; arrêter le
  seul timer de défilement avant la fermeture suffit aussi. Désinstaller le
  gestionnaire AUI seul ne suffit pas. Correctif : arrêter le bandeau et son
  timer de pause après acceptation de la fermeture, avant destruction wx.
- Nouveau test `test_noethys_sl_fermeture_windows.py` : fermeture réelle de
  l'accueil dans un sous-processus Windows, profil temporaire, réseau interdit.
  Succès après correctif, zéro tentative de connexion réseau.
- Le portable e6c9f2de existant **ne contient pas** ce nouveau correctif tant
  qu'un nouveau build n'a pas été produit et vérifié.
- Restent : DPI 125 % / 150 %, confirmation des données réelles d'Arthur,
  recette Connecthys réelle et résorption des anciens travaux après validation.
- Deux instances de l'installation réelle ont été constatées. Celle lancée
  à 14:23 semble provenir du premier essai de lancement du portable via
  Computer Use. Aucune interaction métier ni fermeture sur ces instances.

Validation du correctif : suite `python -m unittest discover -s tests` terminée
avec code 0. Des avertissements de nettoyage de bases temporaires et les
exceptions volontairement simulées restent imprimés par les tests existants.


Nouveau portable local construit avec le commit source `db27767b` :
`C:\Users\Ordi\Documents\GitHub\Noethys\dist\Noethys-SL-0.1.0-rc.2+db27767b-local-Windows-portable.zip`.
SHA-256 : `8ca961a436cc73ae5e5233de91e593293fb4cc702e3caf89b48715ab8c5ebc05`.
Intégrité ZIP vérifiée ; aucun profil Portable ni base inclus dans l'archive.
Le nouvel exécutable démarre et propose l'ouverture du fichier fictif Recette.
Après identification manuelle par Franck, la fermeture graphique du nouveau
portable sur le fichier fictif Recette a été validée : croix de la fenêtre,
« Pas maintenant » au rappel de sauvegarde, processus terminé avec code 0.
La fermeture depuis les sources est également validée par le test.
Le titre reste RC2 : aucune nouvelle version publique ni release créée.


## 13. Recette DPI et crash au double-clic Noedoc — 08/10/2026

Écran Windows 2560 × 1440 ; mise à l'échelle 125 %, puis 150 %, vérifiée
dans les Paramètres. Candidat `db27767b`, fichier SQLite fictif Recette.
Aucune donnée réelle ni aucun profil de production utilisé.

- À 125 % : fiche famille, saisie de règlement, boutons Mode et Émetteur
  ouverts et fermés ; commandes accessibles. Devis fictif généré et ouvert
  dans Adobe Reader malgré un règlement de 50 € non ventilé. Deux messages
  Windows « Font Capture », exception `0xc06d007e`, sont apparus pendant
  l'ouverture de l'aperçu ; Franck les a fermés. Causalité non établie.
- À 150 % : mêmes parcours règlement/Mode/Émetteur accessibles ; devis
  fictif généré et ouvert dans Reader sans nouveau message Font Capture.
  L'éditeur Noedoc s'ouvre et se ferme via le bouton Modifier.
- Au double-clic sur « Facture par défaut », le portable s'arrête à 125 %
  et à 150 % : événements Windows 1000, `0xc0000005` puis `0xc000041d`,
  module `_core.cp310-win_amd64.pyd`. Reproduction depuis le code source
  sur une copie temporaire de Recette avec garde réseau.
- Trace faulthandler : `FloatCanvas.GetHitTestColor`, appelé depuis
  `GUIMode.OnLeftUp`, lit le point `(289, 257)` dans un tampon `(20, 20)`
  avant le premier dessin. AlphaPixelData n'effectue pas de contrôle des
  bornes ; le relâchement du double-clic provoque la lecture native invalide.
- Correctif isolé `027ffe7e` : CanvasNoedoc contrôle l'existence et les
  dimensions du tampon de sélection avant lecture. Hors tampon : aucune
  sélection ; dans le tampon : comportement FloatCanvas conservé.
- Vérification graphique du code corrigé à 150 % : double-clic depuis la
  liste des modèles, dessin complet, sélection d'un bloc et affichage des
  propriétés, Annuler puis fermeture de la liste et de l'accueil ; code 0.
- Cinq tests ciblés passent : trois `test_noethys_sl_noedoc*.py`, un
  `test_noedoc_texte_ui.py`, un `test_noethys_sl_fermeture_windows.py`.
  Le nouveau test exerce dans un sous-processus les coordonnées négatives,
  les bords et le point réel du crash, les pixels valides, la priorité du
  tampon de premier plan et l'absence de tampon. Réseau interdit.

Nouveau portable local (correctifs fermeture + Noedoc), commit source
`027ffe7e98faa67478934db3bdca1919bf8658d7` :
`C:\Users\Ordi\Documents\GitHub\Noethys\dist\Noethys-SL-0.1.0-rc.2+027ffe7e-local-Windows-portable.zip`.
SHA-256 : `778485c3ba9aa36317604f0b2afc3f33dd8b954834ca2d728fa270bc27bdd998`.
Build terminé, intégrité ZIP vérifiée, aucun profil Portable dans l'archive.
Un profil fictif séparé a été préparé dans l'extraction de recette.

Validation graphique du nouveau portable `027ffe7e` terminée :
- À 150 % : double-clic sur le modèle, dessin complet, sélection d'un bloc,
  propriétés affichées, Annuler puis fermeture des fenêtres et du processus.
  Aucun crash observé ; code de sortie non recueilli pour cette exécution.
- À 125 % : même parcours, puis fermeture de l'accueil ; code de sortie 0
  recueilli sur le processus conservé depuis son lancement.

La recette DPI est ciblée : elle ne valide pas exhaustivement l'éditeur,
les autres écrans ou toutes les résolutions. Les messages Font Capture
restent une anomalie non attribuée. L'affichage Windows est actuellement
à 125 % ; la valeur habituelle de Franck reste à confirmer pour restauration.
Arthur réel, contrôle de l'incident et recette Connecthys réelle restent
en attente. Aucun tag, release ou déploiement ; anciens travaux préservés.


## 14. Élagage local vérifié — 11/10/2026

Demande de Franck : élaguer les branches/worktrees et les fichiers locaux
d'audit. Aucun changement de code métier ni de branche distante.

- Trois branches locales supprimées par `git branch -d`, après preuve qu'elles
  sont des ancêtres de main `694ccacc2d37ba71298b56e7ddb6901be6a55d2d` :
  `integration/rc2-convention-recovery-20261004` (`a78c6581`),
  `release/noethys-sl-0.1.0` (`aa88f53a`),
  `rescue/noethys-sl-20261004` (`d9b70c2b`). Aucun travail unique à perdre.
- Worktree propre `C:\Users\Ordi\Documents\GitHub\Noethys-RC2` retiré par
  `git worktree remove`, sans forçage. Ses 2 760 fichiers, dont 272 caches
  ignorés, sont archivés et vérifiés par SHA-256 avant retrait.
- Neuf fichiers d'audit archivés puis retirés du dossier principal : les cinq
  fichiers de `audit-branches-20261011-022224/`, `local-diff.txt`,
  `local-status.txt`, `portable-inventory.txt`, `tracked-files.txt`.
- Archives conservées dans
  `C:\Users\Ordi\.codex\.chatgpt-projects\g-p-6a9e93a502648191a942e5ece9d8ebea\elagage-20261011` :
  `original-all-refs.bundle`, `github-all-refs.bundle`, `audits-locaux.zip`,
  `Noethys-RC2-clean-integrated-worktree.zip` (ce dernier contient le worktree
  propre **Noethys-RC2**, pas le worktree WIP **Noethys-RC2-clean**).
  Les bundles sont vérifiés par Git, les ZIP contrôlés entrée par entrée et
  les empreintes enregistrées dans `backup-manifest.json`.

Préservés et vérifiés après retrait : main/master/wx/qt locaux, tags, trois
stashes, les deux profils Portable (empreintes inchangées), et le worktree
`Noethys-RC2-clean` à HEAD détaché `8b3789d9` avec ses 32 fichiers suivis
modifiés et ses fichiers non suivis. Ses différences et son inventaire restent
identiques. Aucun test sur base ou profil réel, aucune migration.

GitHub : 63 branches distantes inventoriées et toutes revérifiées aux mêmes
SHA après intervention ; huit PR toujours ouvertes avec mêmes têtes/bases :
#422, #384, #369, #366, #355, #112, #104, #102. Les noms canoniques et toutes les
têtes/bases de PR sont protégés. Parmi les 49 autres branches, aucune n'est
entièrement ancêtre d'une référence protégée. Ceci ne prouve pas l'absence
d'une intégration squash : leur qualification fichier/comportement reste
EN ATTENTE, donc aucune suppression distante effectuée.

État du dossier principal après nettoyage, avant ce commit documentaire :
seul `?? noethys/Portable/`, aucune modification suivie. Branches locales
restantes : main, master, wx, qt ; worktrees restants : Noethys et
Noethys-RC2-clean. La copie isolée Codex de propagation Nomadhys est conservée
comme espace de preuves, distincte des worktrees historiques.

Têtes distantes inchangées : main `694ccacc2d37ba71298b56e7ddb6901be6a55d2d`,
wx `dcede8170874dd79cd9a5b5825bc3b4ed85feb62`,
qt `8902e655f93cebabdc84ff3ab8ea1f1ac89b73e0`,
master `b0be3c7ebdf2d69d6028eb4fd6fc08e340a68b9e`.
La présente note est un commit documentaire local sur main, non publié.
CI : aucune nouvelle exécution demandée, aucun packaging ou release.

Suite : qualifier les apports squash et les travaux uniques des 49 branches
historiques par petits lots ; comparer les sources WIP de Noethys-RC2-clean
avec main avant archivage/retrait éventuel. Ne pas restaurer le fichier .git
de l'archive du worktree tel quel ; utiliser la sauvegarde Git et recréer un
worktree historique seulement sur décision explicite de restauration.


## 15. Qualification des branches historiques et élagage distant — 11/10/2026
Suite explicitement demandée par Franck après l’élagage local. Les 49 branches
historiques hors références canoniques et têtes/bases de PR ont été examinées
contre les 14 références protégées. Inventaire de 325 PR, dont huit ouvertes.
Une PR fermée sans fusion n’a jamais été traitée comme une preuve d’intégration.

Méthode : pour chaque source/cible, calcul de l’ancêtre commun puis liste
complète des fichiers modifiés dans le delta source. Comparaison des blobs Git,
des modes de fichier et des suppressions avec l’arbre de la cible conservée.
Critère de retrait : tous les fichiers du delta final sont identiques dans
une même référence protégée. L’archivage de l’historique complet couvre aussi
les commits intermédiaires. Ceci qualifie la conservation du contenu pour
élagage, sans qualification métier globale ni annonce de synchronisation.

### Cinq suppressions distantes réellement effectuées

| Branche supprimée | SHA source | Contenu conservé dans | SHA cible | Fichiers identiques |
| --- | --- | --- | --- | --- |
| candidate/vanilla-20260907 | 451e8e35635aeb8179566ae7175a784387282f2b | feature/vanilla-conventions | c2c3e87a5b7dd883d397b6b1a7d8965997bd34ed | 1 |
| fix/rc2-fiscal-age-reference-year | 82128134e3070efc13e5c977fff39c774c5bee65 | rc/noethys-sl-0.1.0-rc.2 | 91d9e625d96c5a1460d42dda053db509fa28d181 | 8 |
| fix/rc2-fiscal-reportlab-import | 0a6e217da224fb3f2daddb5b74ad1154eb4da007 | main | 694ccacc2d37ba71298b56e7ddb6901be6a55d2d | 1 |
| fix/rc2-network-users-list-index | ec7389322b697122be8c11220942a7b84f3cc8a9 | rc/noethys-sl-0.1.0-rc.2 | 91d9e625d96c5a1460d42dda053db509fa28d181 | 4 |
| fix/wx-period-controller-final | 243b87aab71129e200cdf165815ac507f52abbde | design-form-density-standard | f96fa35865462500f12ad2caee98027e488f3955 | 2 |

Suppression atomique, sans force. Contrôle de l’ensemble des refs distantes
avant exécution et garde pre-push vérifiant les SHA annoncés pour chacune
des cinq suppressions ; la garde accepte le SHA attendu et rejette un SHA
modifié dans ses deux vérifications. Les cinq têtes sont présentes dans
github-all-refs.bundle, dont l’intégrité et les refs sont revérifiées.
Après suppression : **58 branches distantes**, toutes aux SHA inchangés ;
huit PR ouvertes inchangées (titres, descriptions, brouillons, têtes/bases) :
#102, #104, #112, #355, #366, #369, #384, #422. Aucun nouveau nom de branche,
aucune fusion, aucun changement de branche par défaut, tag ou release.
Références de suivi locales obsolètes nettoyées par fetch --prune.

### Matrice des 44 branches conservées

Ces branches présentent encore au moins un fichier différent des références
comparées. Une différence ne signifie pas automatiquement un correctif absent :
elle peut être un apport unique, une variante ou une évolution ultérieure.
Leur retrait est donc EN ATTENTE de qualification ciblée des comportements.

| Branche conservée | SHA source | Meilleure comparaison | Fichiers différents / delta | Statut de retrait |
| --- | --- | --- | --- | --- |
| agent/windows-ci-audit | 7df621ea3a30 | master | 7/9 | EN ATTENTE |
| agent/windows11-pyinstaller | f85f77266eec | master | 60/63 | EN ATTENTE |
| audit/vanilla-black-ui-rex | bcee84abff89 | main | 1/1 | EN ATTENTE |
| audit/vanilla-deep-scan-20260826 | cacafa37eb31 | main | 4/4 | EN ATTENTE |
| audit/vanilla-final-undefined-names | 8ae3a36f9394 | feature/vanilla-conventions | 3/8 | EN ATTENTE |
| audit/vanilla-ui-command-inventory | eef718234412 | main | 7/7 | EN ATTENTE |
| audit/vanilla-upstream-630ef | 58dcab19fd0e | main | 2/2 | EN ATTENTE |
| build/vanilla-windows-portable | 4d5dda48269b | rc/noethys-sl-0.1.0-rc.2 | 22/50 | EN ATTENTE |
| chatgpt/noethys-convention-ui-activites-20260929 | 7cd062c3f634 | rc/noethys-sl-0.1.0-rc.2 | 23/51 | EN ATTENTE |
| chore/noethys-sl-requirements-documentation | d3964671af35 | main | 1/1 | EN ATTENTE |
| chore/workflows-consolidation | f28861260cf2 | master | 1/4 | EN ATTENTE |
| claude/noethys-windows-ci-audit-qy5m9t | 3b847c6b2957 | master | 25/25 | EN ATTENTE |
| diagnostic/vanilla-ui-black-surfaces | f7362db86d47 | main | 1/1 | EN ATTENTE |
| feat/noethys-sl-afas-previsionnel | 108dc5f5e61e | main | 1/2 | EN ATTENTE |
| feat/noethys-sl-rc1-convention-finalise | f6cac3302a2f | main | 18/28 | EN ATTENTE |
| feat/noethys-sl-vacances-sportives | 77f2be447110 | main | 1/2 | EN ATTENTE |
| feat/rc2-reception-quotient | f48450935bb1 | rc/noethys-sl-0.1.0-rc.2 | 1/15 | EN ATTENTE |
| feature/extensions-registry | 9174ba32a45e | master | 4/4 | EN ATTENTE |
| feature/noe-060-reporting | dcfce2954011 | master | 1/1 | EN ATTENTE |
| feature/noe-062-conventions | f85fd51ee404 | master | 2/2 | EN ATTENTE |
| feature/noe-062-mises-a-disposition | c69f3c80325e | master | 8/8 | EN ATTENTE |
| feature/noe-062b-groupes-structures | 203fff34134c | master | 4/4 | EN ATTENTE |
| feature/noe-062b-roles-contacts | 177b4c3dcd1b | master | 4/4 | EN ATTENTE |
| feature/noe-063-portail-consolide | 55b2b129e67e | master | 21/21 | EN ATTENTE |
| feature/noe-063b-rss-atom-connecthys | 8f84f5edb72b | master | 12/12 | EN ATTENTE |
| feature/noe-063d-tarifs-ui | 20d5b15c1adb | master | 21/21 | EN ATTENTE |
| fix/noe-062b-hardening | 752645c5a772 | master | 4/4 | EN ATTENTE |
| fix/noethys-sl-aui-docking-minimize | aac763f24480 | rc/noethys-sl-0.1.0-rc.2 | 3/12 | EN ATTENTE |
| fix/noethys-sl-aui-guides-fantomes | 7704ee753687 | rc/noethys-sl-0.1.0-rc.2 | 4/12 | EN ATTENTE |
| fix/noethys-sl-light-only | ccdfb82bcf1b | master | 3/3 | EN ATTENTE |
| fix/noethys-sl-mailjet-consolidation | 51ee128a60de | rc/noethys-sl-0.1.0-rc.2 | 2/16 | EN ATTENTE |
| fix/noethys-sl-mailjet-email-confirmation | 9e0945b5d0a4 | rc/noethys-sl-0.1.0-rc.2 | 6/16 | EN ATTENTE |
| fix/rc2-network-stopgate-1 | cf5f9fbe6ccd | rc/noethys-sl-0.1.0-rc.2 | 40/40 | EN ATTENTE |
| fix/rc2-pr385-compatible | ba67c6b9a5fc | rc/noethys-sl-0.1.0-rc.2 | 3/13 | EN ATTENTE |
| fix/vanilla-no-black | 7c39f16ab148 | main | 15/15 | EN ATTENTE |
| fix/windows-installable-config | fbdebc8b6ef4 | master | 5/5 | EN ATTENTE |
| noe-041-portable-mode | 3cf6cbfe5d6f | design-form-density-standard | 5/9 | EN ATTENTE |
| noe-042-rc-gate | 085115c40fa5 | design-form-density-standard | 1/3 | EN ATTENTE |
| noe-062-programmation-occurrences | 88904fc780a0 | master | 4/4 | EN ATTENTE |
| noe-062c-lieux-execution-seances | be059ccd4804 | master | 5/7 | EN ATTENTE |
| poc/qt-theme-isole | cba459cd62cb | master | 54/54 | EN ATTENTE |
| refactor/ui-list-tools-repens | 52ed49bf888b | master | 14/23 | EN ATTENTE |
| refactor/ui-navigation-repens | 6bf8a4cceb8b | master | 1/2 | EN ATTENTE |
| test/vanilla-windows-ui-driver-prototype | be87c00ea51a | main | 10/10 | EN ATTENTE |

Preuves détaillées : content-audit.json (chaque fichier, blobs source/cible,
ancêtres communs et cibles), pr-history.json, remote-cleanup-plan.json et
remote-cleanup-result.json, dans le dossier local de sauvegarde indiqué au §14.
Le bundle sauvegarde aussi les 44 branches conservées.

Les arbres de main/wx/qt/master distants sont inchangés : aucune nouvelle
exécution de tests ni CI requise pour une suppression de refs sans changement
de contenu. Les 55 tests par branche du lot Nomadhys ne sont pas présentés
comme qualification de ces travaux historiques.
Localement : Portable, tags, trois stashes, branches master/wx/qt et worktree
WIP Noethys-RC2-clean préservés. main reçoit uniquement cette note documentaire,
en second commit local non publié après e59f3400. Seul Portable reste non suivi.
Suite : revue par lots des différences restantes ; aucune suppression de
travail non qualifié ni réimportation métier implicite.


## 16. Élagage qualifié, lot documentaire et tests — 12/10/2026

Suite demandée par Franck ; publication des notes documentaires autorisée.
Les 44 branches restantes sont triées : sept sont qualifiées pour retrait,
37 restent en place car leur variante de code ou de comportement ne permet
pas un retrait automatique. Aucune fusion ni modification du runtime.

| Branche | SHA | Preuve de conservation |
| --- | --- | --- |
| audit/vanilla-black-ui-rex | bcee84abff892903d166d9cdcdd03627e972572b | Delta constitué uniquement de Markdown : originaux conservés octet pour octet dans docs/archives/branches-20261012. |
| diagnostic/vanilla-ui-black-surfaces | f7362db86d4775221822996b22dae96c2de49095 | Delta constitué uniquement de Markdown : originaux conservés octet pour octet dans docs/archives/branches-20261012. |
| feature/noe-060-reporting | dcfce29540113562a41dba0a254dabe42c17d06a | Delta constitué uniquement de Markdown : originaux conservés octet pour octet dans docs/archives/branches-20261012. |
| feat/noethys-sl-afas-previsionnel | 108dc5f5e61e27c9549ebd1aeaf70b5dc46fe809 | Moteur identique à main ; AST de toutes les assertions originales conservé ; garde réseau ajoutée. Tests ciblés réussis. |
| feat/noethys-sl-vacances-sportives | 77f2be447110ce245458427bb8b66c82821cd55d | Moteur identique à main ; AST de toutes les assertions originales conservé ; garde réseau ajoutée. Tests ciblés réussis. |
| chore/noethys-sl-requirements-documentation | d3964671af351c2ebc5f0bea999fb46290dc3866 | Tous les paquets source sont encore déclarés dans main, qui ajoute mailjet-rest. Ordre/commentaires historiques archivés. |
| chore/workflows-consolidation | f28861260cf2f23dd2027e9b20ca3a452a86fd42 | Lignes opérationnelles identiques à master ; seuls commentaires et noms affichés diffèrent. Original archivé sous docs/. |

AFAS : 8 tests réussis ; vacances : 10 tests réussis, avec une assertion
supplémentaire sur le samedi 31/10/2026 dans main. Toutes les assertions
historiques sont conservées. Runtime Python 3.10 Windows existant, sources
dans la copie isolée, APPDATA/LOCALAPPDATA temporaires, profil test vide,
réseau bloqué ; zéro tentative réelle. Le premier essai sous Python 3.11
n’avait pas pu importer la garde à cause de wxPython absent ; la qualification
réussie utilise ensuite le runtime Windows disponible, sans retrait de garde.

Les fichiers d’archive ne remplacent aucune documentation courante et
n’activent aucun workflow. Chaque blob source est revérifié au moment de la
copie et indexé dans provenance.json. Les historiques complets des sept
branches sont dans github-all-refs.bundle (session précédente), vérifié.
Ce commit prépare les archives avant toute suppression distante. Publication
envisagée en un push atomique : main avance seulement par documentation,
et les sept refs sont retirées avec contrôle de leurs SHA ; les noms et
têtes/bases de PR restent protégés. Le résultat réellement distant sera
consigné après vérification, sans présumer ici le succès du push.

Liste des 37 sources conservées dans qualification.json de la session du
12/10/2026 ; leurs SHA et différences détaillées restent dans content-audit.json
de la session précédente. Les 37 sources portent des variantes, outils,
protections ou fonctionnalités qui demandent une décision ciblée ; elles ne
sont pas déclarées absentes du moteur sur la seule différence de fichier.


### Résultat distant confirmé du lot du 12/10/2026

L’envoi atomique a réussi : publication des deux notes locales e59f3400,
aa74aa87 et du commit d’archives e9c9398fc544a5698753a3fda6e8dcf13c84822b
sur main, plus retrait effectif des sept branches du tableau ci-dessus.
Après cette opération : 51 branches distantes, dont 37 historiques conservées.
Toutes les autres têtes distantes sont inchangées ; huit PR ouvertes inchangées.
Aucun code runtime ni test modifié, aucune nouvelle branche ni force-push.
Les références locales obsolètes sont nettoyées par fetch --prune.

Vérifications finales : profils Portable, tags, trois stashes, branches locales
master/wx/qt et le worktree WIP Noethys-RC2-clean (diff binaire et inventaire
non suivi) inchangés. Le dossier principal ne présente que Portable comme
non suivi. Les 18 tests ciblés réussis, leurs logs, les empreintes des archives
et la liste des 37 branches conservées sont dans elagage-20261012 dans l’espace
de sauvegarde de cette session. Les sources archivées sont consultables dans
docs/archives/branches-20261012 ; aucune consigne historique n’est activée.
Cette confirmation est publiée comme commit documentaire séparé sur main.
CI distante : aucun succès revendiqué ; aucun packaging ni release demandé.
La poursuite implique une qualification de variantes de code, surtout réseau,
interventions, Qt et packaging ; aucune réintégration automatique autorisée.


## 17. Clôture du tri des 37 sources restantes — 12/10/2026

Toutes les 37 branches ont maintenant une décision de retrait motivée, et
non un simple comptage de commits ou statut de PR. Comparaison des blobs et
AST contre les 14 têtes protégées ; comparaison des changements propres
à chaque branche avec son ancêtre commun (imports, variables, définitions,
méthodes et suppressions). L’analyse distingue les divergences héritées
des apports réellement propres. Aucune décision métier implicite.

### Sept références qualifiées pour retrait

| Branche | SHA | Conservation |
| --- | --- | --- |
| audit/vanilla-deep-scan-20260826 | cacafa37eb31e35f60ae1b6eb2e96237274159c6 | No application runtime changes in the branch delta. No protected runtime/workflow/test references to the unique tool paths or modules across all 14 protected heads. Complete changed source files, tests and workflows retained as inert documentation archives and full Git history in verified bundle. |
| audit/vanilla-ui-command-inventory | eef718234412ddf98867a2a4bbdbf29241b18397 | No application runtime changes in the branch delta. No protected runtime/workflow/test references to the unique tool paths or modules across all 14 protected heads. Complete changed source files, tests and workflows retained as inert documentation archives and full Git history in verified bundle. |
| audit/vanilla-upstream-630ef | 58dcab19fd0e2b542ce3c06c28f60422742c79ed | No application runtime changes in the branch delta. No protected runtime/workflow/test references to the unique tool paths or modules across all 14 protected heads. Complete changed source files, tests and workflows retained as inert documentation archives and full Git history in verified bundle. |
| test/vanilla-windows-ui-driver-prototype | be87c00ea51a6fef8ad33cf2ae848eaa6b676a85 | No application runtime changes in the branch delta. No protected runtime/workflow/test references to the unique tool paths or modules across all 14 protected heads. Complete changed source files, tests and workflows retained as inert documentation archives and full Git history in verified bundle. |
| noe-042-rc-gate | 085115c40fa5b2072bfdabebdf2f099330945b76 | Gate conditions and shell commands are identical in protected branch, ignoring labels/comments/action version tags. Historical gate test blob is identical and passes on the preserved workflow. Workflow build additions differ and are archived; no release or package is executed. |
| refactor/ui-navigation-repens | 6bf8a4cceb8bdf0da6ea13cb20b5c98fc6402f04 | All five functions added/modified by this branch relative to its common ancestor have identical ASTs in protected branch. No source function deleted, module imports/globals unchanged by source. Test blob identical. Remaining file difference is ConfigurerGrille inherited from the common ancestor and subsequently delegated to Style.appliquer_grille in protected branch. |
| feat/rc2-reception-quotient | f48450935bb18125b3b46a4e5e5346bea7804076 | All branch-owned changes preserved in protected RC2 reference. Fourteen delta files have identical blobs; in remaining file Traitement.Traitement_pieces AST is identical. No own binding was removed. Quotient atomic-write and received-file regressions pass on synthetic/memory data with network blocked. Other file differences are inherited/evolved code, retained in full source archive. |

Les quatre outils ne sont appelés ni par le runtime, ni par les workflows,
ni par les tests des 14 références protégées (recherche des chemins et noms
de modules). Leurs originaux sont conservés, avec les tests et workflows,
dans docs/archives/branches-20261012-final ; le bundle préserve les historiques.
Le gate RC conserve les mêmes conditions et commandes de validation ;
la navigation conserve les cinq fonctions propres et les tests identiques ;
la réception de quotient conserve les 14 blobs identiques et la méthode
Traitement.Traitement_pieces au même AST dans la référence RC2 protégée.

Validation ciblée supplémentaire : gate RC 5 tests, navigation 4, quotients
12 (SQLite mémoire/fictif, atomicité, factures inchangées), réception pièces
4 (AST, dépendances factices) : **25 réussites**, aucune tentative réseau
réelle. Aucun build, interaction avec une base réelle ou recette GUI complète.

### Trente branches conservées avec motif précis

Conserver ces références ne signifie pas que leurs fonctionnalités sont
qualifiées en production. Leur code propre n’est pas démontré intégralement
repris : supprimer ou intégrer ces variantes requiert une décision sur leur
devenir. Le tri de retrait est achevé ; la qualification métier et les recettes
sont des travaux distincts. Les exemples ci-dessous sont des différences,
pas une annonce automatique de correctifs absents de main.

| Branche | SHA | Fichier/fonction motivant le maintien |
| --- | --- | --- |
| agent/windows-ci-audit | 7df621ea3a30 | .github/workflows/ci.yml ; docs/CI-WINDOWS-AUDIT.md |
| agent/windows11-pyinstaller | f85f77266eec | .github/workflows/ci.yml ; .github/workflows/windows-package.yml |
| audit/vanilla-final-undefined-names | 8ae3a36f9394 | .github/workflows/final-undefined-name-audit.yml |
| build/vanilla-windows-portable | 4d5dda48269b | .github/workflows/noethys-sl-windows.yml ; .github/workflows/vanilla-windows-package.yml |
| chatgpt/noethys-convention-ui-activites-20260929 | 7cd062c3f634 | .github/workflows/noethys-sl-windows.yml ; README.md |
| claude/noethys-windows-ci-audit-qy5m9t | 3b847c6b2957 | noethys/Dlg/DLG_Badgeage_interface.py : GetInfosActivite, CTRL_Interface.Procedure_enregistrer ; noethys/Dlg/DLG_Famille.py : Dialog.GetIDcomptePayeur, Dialog.MenuImprimerReleve |
| feat/noethys-sl-rc1-convention-finalise | f6cac3302a2f | docs/dev/CONVENTION_DOCX.md ; noethys/Dlg/DLG_Famille.py : CreateIDfamille, Notebook.__init__ |
| feature/extensions-registry | 9174ba32a45e | docs/EXTENSIONS.md ; noethys/Extensions/__init__.py |
| feature/noe-062-conventions | f85fd51ee404 | noethys/Utils/UTILS_Impression_convention.py ; tests/test_convention_engine_contract.py |
| feature/noe-062-mises-a-disposition | c69f3c80325e | docs/NOE-062-MISES-A-DISPOSITION.md ; docs/NOE-062C-PROGRAMMATION.md |
| feature/noe-062b-groupes-structures | 203fff34134c | noethys/Utils/UTILS_Tiers.py ; noethys/Utils/UTILS_Tiers_Schema.py |
| feature/noe-062b-roles-contacts | 177b4c3dcd1b | noethys/Utils/UTILS_Tiers.py ; noethys/Utils/UTILS_Tiers_Schema.py |
| feature/noe-063-portail-consolide | 55b2b129e67e | docs/NOE_063C_TARIFS_PORTAIL.md ; docs/NOE_063_PORTAIL_CONTENUS_DYNAMIQUES.md |
| feature/noe-063b-rss-atom-connecthys | 8f84f5edb72b | docs/NOE_063B_RSS_ATOM.md ; docs/NOE_063_PORTAIL_CONTENUS_DYNAMIQUES.md |
| feature/noe-063d-tarifs-ui | 20d5b15c1adb | docs/NOE_063B_RSS_ATOM.md ; docs/NOE_063C_TARIFS_PORTAIL.md |
| fix/noe-062b-hardening | 752645c5a772 | noethys/Dlg/DLG_Ecoles.py : from:Utils:0:UTILS_Interventions:None, import:GestionDB:None ; noethys/Dlg/DLG_Seances_sport_ecoles.py |
| fix/noethys-sl-aui-docking-minimize | aac763f24480 | noethys/Noethys.py : MainFrame.Initialisation, MyApp.OnInit ; tests/test_vanilla_aui_docking_lifecycle.py |
| fix/noethys-sl-aui-guides-fantomes | 7704ee753687 | docs/noethys_sl_wx_pr375_apparence_claire.md ; noethys/Chemins.py : assignment:Name(id='STATIC_IMAGE_ALIASES', ctx=Store()), GetStaticPath |
| fix/noethys-sl-light-only | ccdfb82bcf1b | .github/workflows/windows-package.yml ; noethys/Utils/UTILS_Interface.py : GetApparence, SetApparence |
| fix/noethys-sl-mailjet-consolidation | 51ee128a60de | noethys/Dlg/DLG_Mailer.py : Dialog.Envoyer |
| fix/noethys-sl-mailjet-email-confirmation | 9e0945b5d0a4 | noethys/Dlg/DLG_Mailer.py : Dialog.Envoyer ; noethys/Noethys.py : MainFrame.Initialisation, MyApp.OnInit |
| fix/rc2-network-stopgate-1 | cf5f9fbe6ccd | docs/audit/AUDIT_RESEAU_RC2.md ; docs/audit/CONTRAT_CONNECTHYS.md |
| fix/rc2-pr385-compatible | ba67c6b9a5fc | noethys/Dlg/DLG_Saisie_portail_demande.py : Traitement.Traitement_pieces |
| fix/vanilla-no-black | 7c39f16ab148 | .github/workflows/vanilla-release.yml ; .github/workflows/vanilla-windows-package.yml |
| fix/windows-installable-config | fbdebc8b6ef4 | .github/workflows/windows-package.yml ; noethys/Utils/UTILS_Fichiers.py : DeplaceFichiers |
| noe-041-portable-mode | 3cf6cbfe5d6f | .github/workflows/windows-package.yml ; noethys/Utils/UTILS_Fichiers.py : GetRepUtilisateur |
| noe-062-programmation-occurrences | 88904fc780a0 | noethys/Data/DATA_Programmations_Structures.py ; noethys/Utils/UTILS_Programmations_Structures.py |
| noe-062c-lieux-execution-seances | be059ccd4804 | noethys/Data/DATA_Structures.py : assignment:Name(id='DB_STRUCTURES', ctx=Store()) ; noethys/Utils/UTILS_Interventions_Execution.py : statement:Expr(value=Constant(value='Extension opérationnelle 1:1 des séances Noe-062C.\n\nLa séance canonique reste dans ``interventions``. Ce module ne duplique ni le\nréférentiel RH (Teamworks reste source de vérité), ni les lieux : il conserve\nuniquement leurs UID/IDs de référence et les écarts entre prévu et réalisé.\n')), GestionnaireExecutionInterventions.EnregistrerExecution |
| poc/qt-theme-isole | cba459cd62cb | .github/workflows/qt-prototype.yml ; docs/QT_MIGRATION_INVENTORY.md |
| refactor/ui-list-tools-repens | 52ed49bf888b | .github/workflows/ci.yml ; .github/workflows/windows-package.yml |

Le dossier publié dossier-conservation.json sous l’archive finale contient
les SHA complets, chaque fichier et définition concernés, les ancêtres,
cibles et preuves. Cela couvre notamment le prototype Qt, les extensions,
programmations/groupes/rôles/lieux, contenus/tarifs Portail, variantes de
réception réseau et Mailjet, AUI/Noedoc, packaging et configuration.
Ces sources restent en place ; aucune fusion générale, reprise automatique
de schéma, fermeture de PR ou abandon de travail unique.

Ce commit publie les archives avant retrait distant, en un envoi atomique
main + sept suppressions, avec contrôle des SHA et des huit PR ouvertes.
Si l’envoi réussit, il restera 44 branches : 14 protégées et 30 sources
conservées avec motifs. Le résultat réel sera vérifié et consigné ensuite.


### Résultat final réel : tri de retrait achevé

Le push atomique du lot final a réussi à main
f95636fc94122e67caa613e690550e5f2e0aa7aa : sept références retirées,
archives des 43 fichiers originales publiées avec blobs vérifiés, dossier de
maintien des trente autres sources publié. Après vérification : 44 branches
distantes, 14 références protégées et 30 variantes de code conservées avec
motifs explicites. Huit PR ouvertes, titres/descriptions/drafts et têtes/bases
inchangés ; les autres branches distantes restent aux mêmes SHA.

Bilan de tout l’élagage dans cette conversation : 19 branches distantes
retirées (5 + 7 + 7), trois branches locales intégrées retirées, un worktree
propre retiré, neuf fichiers locaux d’audit archivés. Les historiques Git
complets sont sauvegardés et vérifiés ; les sources particulières retirées
restent consultables dans les archives documentaires de main.

Contrôle final : runtime et tests de main inchangés depuis 694ccacc ; aucun
code métier migré implicitement, aucun packaging/release, nouvelle branche,
merge global ou force-push. Portable, tags, trois stashes, branches locales
master/wx/qt et worktree WIP Noethys-RC2-clean vérifiés inchangés. Seul Portable
reste non suivi dans le dossier principal. main est publié et aligné avec
origin/main après cette confirmation documentaire.

Les 37 sources ont toutes été examinées ; les trente maintiens sont des
décisions de conservation de variantes identifiées, pas une file de branches
encore non inventoriées. Leur intégration ou abandon demanderait de choisir
des comportements, protections ou fonctionnalités ; ce serait un chantier
métier distinct de l’élagage autorisé. La documentation ne revendique pas
une qualification fonctionnelle globale de ces variantes ni une CI verte.


## 18. Reprise réelle et requalification des stop-gates — 12/10/2026

Contrôle autonome après le tri déjà publié, sans reprendre un plan ancien.
Consignes AGENTS.md et présent document lus avant toute action. GitHub réel :
**44 branches, huit PR ouvertes, master toujours par défaut**. Point de départ
main `621b904f533ee0e20dec8657740634313c033167`, wx
`dcede8170874dd79cd9a5b5825bc3b4ed85feb62`, qt
`8902e655f93cebabdc84ff3ab8ea1f1ac89b73e0`, master
`b0be3c7ebdf2d69d6028eb4fd6fc08e340a68b9e`.

### Résultat du tri de retrait

**Zéro branche supprimée dans cette reprise ; zéro candidate sûre restante.**
Les 19 suppressions des lots précédents ne sont pas comptées comme opérations
de cette reprise. Les 30 branches conservées ont exactement les SHA du dossier
publié en section 17 ; les 13 autres têtes protégées sont inchangées et main
n'a ajouté que de la documentation depuis la comparaison `ee234ada`.
Relecture du dossier, vérification des blobs source et comparaison à chacune
des 14 têtes protégées actuelles : des variantes demeurent. Le maintien est
reconfirmé ; aucune différence de blob n'est à elle seule interprétée comme
fonctionnalité absente. Les analyses AST et décisions précédentes restent
applicables puisque leurs entrées runtime sont inchangées. La sauvegarde ne
constitue pas une autorisation d'abandonner un apport non intégré.

### PR et références protégées

Les huit PR suivantes restent ouvertes, avec leurs têtes et bases conservées :

| PR | Tête et SHA | Base |
| --- | --- | --- |
| #422 | rc/noethys-sl-0.1.0-rc.3 — `28c2294cead7aa09f6d04c3bbdd9339593377e5b` | rc/noethys-sl-0.1.0-rc.2 |
| #384 | feature/vanilla-entites-fonctions — `4e2c615bcbee669b08e12f1580e2e81fb4351295` | feature/vanilla-conventions |
| #369 | feature/session-attendance-consumer-2026-09-19 — `74410a3ef4ef8b618a2214487453d379ff596f3a` | master |
| #366 | docs/mkdocs-wiki — `e43492b156a92551579faa6c606333c98f2bf280` | master |
| #355 | noe-062-secure-secret-provider — `04f7886cfd8d5f62bc02b243f6d57ebfff8b6297` | master |
| #112 | design-form-density-standard — `f96fa35865462500f12ad2caee98027e488f3955` | master |
| #104 | dev-db-docker — `b7dc7c195022949626f8a7e9a55d2677e710d107` | master |
| #102 | docs/open-development-policy — `d218e2980fbc7ab5b6577ec50c74931aae836c93` | master |

Cela représente 14 références distinctes en comptant main/wx/qt et master.
Les PR ne sont ni fermées, ni fusionnées, ni reciblées. Les bases
feature/vanilla-conventions et RC2 restent notamment nécessaires.

### Conservation revérifiée

- `original-all-refs.bundle` : 57 749 065 octets, SHA-256
  `cbb419ae17192d7e05ff8b1f18b5349656480d86a6e86a0fbfbe80fb2b2c5e8d`.
- `github-all-refs.bundle` : 59 138 549 octets, SHA-256
  `1898e49973c9abf8832c3e6b01b816f7813df94e7d10e96d8cec3e89146890eb`.
- Empreintes identiques au manifeste précédent, `git bundle verify` réussi
  pour les deux. Les 30 SHA des sources maintenues figurent tous exactement
  dans les références du bundle GitHub. Bundles dans `elagage-20261011` de
  l'espace Codex ; aucune nouvelle sauvegarde contenant des données réelles.
- Les 48 fichiers indexés par les deux provenance.json des archives
  `branches-20261012` et `branches-20261012-final` sont identiques octet par
  octet aux blobs de leurs commits source et aux SHA-256 documentés.
- GitHub expose neuf tags et neuf releases ; les références locales possèdent
  aussi des tags historiques/archives. Aucune modification ni assimilation
  d'une release à la qualification de main. RC3 reste une préversion historique
  au commit `6ab134707ac48e16ee82001088234510657f1ab6`.
- Deux worktrees : principal sur main et Noethys-RC2-clean détaché sur
  `8b3789d9de1beeb3a47dbf6ed3be235a7df2cc12`, avec 32 fichiers suivis modifiés.
  WIP conservé, trois stashes conservés. Branches locales master/wx/qt distinctes
  des têtes distantes, conservées sans synchronisation implicite.
- Dossier principal : seul `noethys/Portable/` est non suivi. Aucun accès à son
  contenu, aucune modification des fichiers non suivis existants ou des données
  réelles. Pas de tests applicatifs, SMTP, base, build, packaging ou migration.

### Stop-gates et règle signal nouveau → requalification

1. **MAIL / signal utilisateur nouveau** : travail perdu et mails aux familles
   jamais reçus signalés dans cette conversation. Cause, dates et version exécutée
   non établies ; ne pas inférer une panne Mailjet ou une livraison depuis une CI.
   Les deux branches Mailjet `51ee128a60ded8dfb4d8bcf77f28219eb1f1f6f5` et
   `9e0945b5d0a411ef8d03a7179df5abb4a18919c1` restent conservées. DLG_Mailer
   a le même blob sur main/wx/qt (`3e1090cf8a5adf8d4bb84030dd1e9896aa825867`),
   différent des deux variantes. Diff revu : parent de progression et affichage
   d'erreurs Python 3 notamment ; le signal ne démontre pas leur causalité.
   Requalification requise : résultat par destinataire, erreurs/rejets, statut
   fournisseur et réception sur adresses de recette consenties ; aucun envoi
   réel aux familles ni accès à leurs données dans ce lot.
2. **CI wx rouge** : run [38171008248](https://github.com/fr4nck/Noethys-SL/actions/runs/38171008248)
   au SHA `dcede817`. 96 tests exécutés, une failure, deux skips.
   `test_deux_postes_simultanes_une_seule_adhesion` attend
   `('rien_a_faire', 'adhesion_deja_valide')` et reçoit
   `('rien_a_faire', None)`. Cause non requalifiée ; ne pas affaiblir l'assertion.
   Le dernier run main de code [38168522698](https://github.com/fr4nck/Noethys-SL/actions/runs/38168522698)
   réussit au SHA `694ccacc2d37ba71298b56e7ddb6901be6a55d2d` ; main n'a depuis
   changé que docs. Aucun run au HEAD documentaire main ou au HEAD qt dans les
   100 runs consultés : aucune CI verte revendiquée sur ces têtes.
3. **Non-régression interbranches** : main et wx/qt divergent (16 commits propres
   à main, cinq propres à chaque interface au départ). Les trois différences
   runtime exactes sont DLG_Noedoc.py, OL_Etiquettes.py, UTILS_Stats_modeles.py,
   avec leurs trois nouveaux tests présents seulement sur main. Correctifs
   main `e8d1e7ad` (secteur), `27b988f3` (delta), `bf69d3ca` (mode GetHTML) :
   ABSENTS sous cette forme sur wx/qt, à porter et tester par lots ciblés.
   Les sources et tests du correctif Nomadhys `694ccacc` sont identiques sur
   wx/qt après leurs adaptations `d95fb660` / `508d5f4f` ; aucune nouvelle
   propagation effectuée. Aucune fusion globale ni fast-forward possible
   présumé depuis la seule comptabilité de commits.
4. **master / SQL / métier** : master reste divergente (1 480 commits propres,
   271 côté main au départ), référence par défaut et base de six PR.
   Protections Noe-032 avancées, interventions/pointage/tiers, contrats et
   tests historiques restent à qualifier par thème ; recette MySQL/MariaDB
   synthétique et UI/Qt requise avant publication. Aucune suppression de master.
5. **30 sources non intégrées** : tableau ci-dessous ; conserver chaque ref
   jusqu'à preuve nouvelle de reprise des apports ou décision explicite de
   devenir. Le détail de provenance, ancêtres, définitions et comparaisons
   reste dans `docs/archives/branches-20261012-final/dossier-conservation.json`.

| Source conservée | SHA complet | Exemples de fichiers encore distincts |
| --- | --- | --- |
| agent/windows-ci-audit | `7df621ea3a3034819142c633f5f4c9149c17fa68` | .github/workflows/ci.yml ; docs/CI-WINDOWS-AUDIT.md |
| agent/windows11-pyinstaller | `f85f77266eec49ec02d6a24e0e130d463123b8d5` | .github/workflows/ci.yml ; .github/workflows/windows-package.yml |
| audit/vanilla-final-undefined-names | `8ae3a36f939460a36b9d7b4f86cfa1147208e1b0` | .github/workflows/final-undefined-name-audit.yml ; noethys/Dlg/DLG_Noedoc.py |
| build/vanilla-windows-portable | `4d5dda48269b8cc9313b3a6dc5a4442f0e5c7d2a` | .github/workflows/noethys-sl-windows.yml ; .github/workflows/vanilla-windows-package.yml |
| chatgpt/noethys-convention-ui-activites-20260929 | `7cd062c3f634cff137f20af469ff7ded5e407e42` | .github/workflows/noethys-sl-windows.yml ; README.md |
| claude/noethys-windows-ci-audit-qy5m9t | `3b847c6b2957a5d4a7d118ad7384f8bdc971baaf` | noethys/Dlg/DLG_Badgeage_interface.py ; noethys/Dlg/DLG_Famille.py |
| feat/noethys-sl-rc1-convention-finalise | `f6cac3302a2ff3946f1f389071accec151a5b542` | docs/dev/CONVENTION_DOCX.md ; noethys/Dlg/DLG_Famille.py |
| feature/extensions-registry | `9174ba32a45e8788a6ba456aae722360425371ae` | docs/EXTENSIONS.md ; noethys/Extensions/__init__.py |
| feature/noe-062-conventions | `f85fd51ee40429415819e01284bf9deba6406b13` | noethys/Utils/UTILS_Impression_convention.py ; tests/test_convention_engine_contract.py |
| feature/noe-062-mises-a-disposition | `c69f3c80325e6aeef27bdec82a03ef257ff552a8` | docs/NOE-062-MISES-A-DISPOSITION.md ; docs/NOE-062C-PROGRAMMATION.md |
| feature/noe-062b-groupes-structures | `203fff34134ceb7a9676f877e5901e0bb74dfc4f` | noethys/Utils/UTILS_Tiers.py ; noethys/Utils/UTILS_Tiers_Schema.py |
| feature/noe-062b-roles-contacts | `177b4c3dcd1b2055f4a595512c71ab6305a55b8b` | noethys/Utils/UTILS_Tiers.py ; noethys/Utils/UTILS_Tiers_Schema.py |
| feature/noe-063-portail-consolide | `55b2b129e67ed295f59b161ebb6896c06348a101` | docs/NOE_063C_TARIFS_PORTAIL.md ; docs/NOE_063_PORTAIL_CONTENUS_DYNAMIQUES.md |
| feature/noe-063b-rss-atom-connecthys | `8f84f5edb72b8becd3a58a44994fb23be0117630` | docs/NOE_063B_RSS_ATOM.md ; docs/NOE_063_PORTAIL_CONTENUS_DYNAMIQUES.md |
| feature/noe-063d-tarifs-ui | `20d5b15c1adb4a460d7ff0ed87ed22120ebec0dc` | docs/NOE_063B_RSS_ATOM.md ; docs/NOE_063C_TARIFS_PORTAIL.md |
| fix/noe-062b-hardening | `752645c5a772a822226b1494d908400d85a79c4a` | noethys/Dlg/DLG_Ecoles.py ; noethys/Dlg/DLG_Seances_sport_ecoles.py |
| fix/noethys-sl-aui-docking-minimize | `aac763f24480e98608cfd2ccc918d87ef26594db` | noethys/Noethys.py ; noethys/Utils/UTILS_AUI_Apparence.py |
| fix/noethys-sl-aui-guides-fantomes | `7704ee753687159ee7173e33f86f538bc483c75c` | noethys/Noethys.py ; noethys/Utils/UTILS_AUI_Apparence.py |
| fix/noethys-sl-light-only | `ccdfb82bcf1b1f5d4cd06a9d6382176cd91f6629` | .github/workflows/windows-package.yml ; noethys/Ctrl/CTRL_ObjectListView.py |
| fix/noethys-sl-mailjet-consolidation | `51ee128a60ded8dfb4d8bcf77f28219eb1f1f6f5` | noethys/Dlg/DLG_Mailer.py ; noethys/Dlg/DLG_Saisie_portail_demande.py |
| fix/noethys-sl-mailjet-email-confirmation | `9e0945b5d0a411ef8d03a7179df5abb4a18919c1` | noethys/Dlg/DLG_Mailer.py ; noethys/Dlg/DLG_Saisie_portail_demande.py |
| fix/rc2-network-stopgate-1 | `cf5f9fbe6ccd9472a061ceaf81ab6358effc00b3` | docs/audit/AUDIT_RESEAU_RC2.md ; docs/audit/CONTRAT_CONNECTHYS.md |
| fix/rc2-pr385-compatible | `ba67c6b9a5fc488ff8ba3c15d3cd6bd7826c12d8` | noethys/Ctrl/CTRL_Ephemeride.py ; noethys/Dlg/DLG_Saisie_portail_demande.py |
| fix/vanilla-no-black | `7c39f16ab1489ce4bcd96e2fc1b44995b8d237fa` | .github/workflows/vanilla-release.yml ; .github/workflows/vanilla-windows-package.yml |
| fix/windows-installable-config | `fbdebc8b6ef4ef906bfb8d23246be5eeb1820203` | .github/workflows/windows-package.yml ; noethys/Utils/UTILS_Fichiers.py |
| noe-041-portable-mode | `3cf6cbfe5d6fcd631f21fc821bbecc4988caa7b2` | .github/workflows/windows-package.yml ; noethys/Utils/UTILS_Fichiers.py |
| noe-062-programmation-occurrences | `88904fc780a052a90598f5bde23aa2dffd686a93` | noethys/Data/DATA_Programmations_Structures.py ; noethys/Utils/UTILS_Programmations_Structures.py |
| noe-062c-lieux-execution-seances | `be059ccd480468f76c2b50f3ee000200e2e9bb4f` | noethys/Data/DATA_Structures.py ; noethys/Utils/UTILS_Interventions_Execution.py |
| poc/qt-theme-isole | `cba459cd62cb2d71f43f89825287295d2ead6492` | .github/workflows/qt-prototype.yml ; docs/QT_MIGRATION_INVENTORY.md |
| refactor/ui-list-tools-repens | `52ed49bf888bc381d92e46a87eca7f6a5fc66e65` | .github/workflows/ci.yml ; .github/workflows/windows-package.yml |

**Opération de cette reprise :** ajout de ce constat documentaire sur la branche
existante main uniquement. Aucun runtime/test modifié, aucune branche créée,
suppression, réécriture d'historique, force-push, changement de défaut, tag ou
release. Les stop-gates ci-dessus empêchent une réduction honnête à main/wx/qt.
Preuves détaillées de la reprise dans `audit-reprise-20261012` de l'espace Codex.
Tout nouveau SHA, résultat CI ou signal métier invalide la décision concernée
jusqu'à sa requalification ; ne pas relancer un ancien plan de suppression.


## 19. Levée ciblée des écarts communs et du défaut de synchronisation du test — 12/10/2026

Reprise autorisée après la section 18. État relu : 44 branches et huit PR,
main `dbc0f1df34bf37981397138691b83761ada53aec`, wx `dcede8170874dd79cd9a5b5825bc3b4ed85feb62`,
qt `8902e655f93cebabdc84ff3ab8ea1f1ac89b73e0`. Aucun historique divergent fusionné.

### Corrections publiées

| Branche existante | Commit de code publié | CI rapide Windows et syntaxe |
| --- | --- | --- |
| main | `fcb729a4baa9f20c22af20a92af9f7deec0465a1` | [SUCCÈS #38220003741](https://github.com/fr4nck/Noethys-SL/actions/runs/38220003741) |
| wx | `c8f26c41040b21f0324d319470c063b1f9116e47` | [SUCCÈS #38220003760](https://github.com/fr4nck/Noethys-SL/actions/runs/38220003760) |
| qt | `06107757a4b6614908c37efa543cade1ba22412a` | [SUCCÈS #38220005442](https://github.com/fr4nck/Noethys-SL/actions/runs/38220005442) |

- `main` : aucun code métier modifié. Stabilisation du test d'adhésions
  concurrentes et ajout en CI des trois suites de contrats déjà présentes.
- `wx` et `qt` : adaptation ciblée des trois correctifs communs déjà qualifiés
  sur main : secteur d'une famille sans titulaire, delta d'un déplacement
  Noedoc, refus d'un mode GetHTML invalide. Seulement six lignes runtime ajoutées
  dans trois fichiers ; les trois suites de tests sont reprises sans changement.
- La CI est exécutée par les pushes sur main/wx et par workflow_dispatch
  `mode=rapide` sur qt. Aucun packaging ni validation d'une interface Qt native.

### Cause reproduite de l'échec de concurrence

Le parent libérait A deux secondes après le lancement de B, sans preuve que B
avait atteint `_Verrouiller`. Avec un démarrage B retardé de trois secondes,
l'ancien test reproduit exactement `('rien_a_faire', None)` au lieu de
`('rien_a_faire', 'adhesion_deja_valide')` : B arrive après l'écriture et n'exerce
pas le scénario sous verrou. Cela démontre un défaut du harnais capable de
produire l'échec observé ; ce n'est pas une preuve universelle d'absence de bugs
d'adhésion ni une qualification MySQL réelle.

Correction : B annonce son arrivée immédiatement avant le verrou ; le parent
attend ce signal pendant la pause de A avant de vérifier le blocage puis de
libérer A. Le délai de garde de A échoue explicitement, sans reprise silencieuse.
Un cas avec B retardé de trois secondes exerce désormais ce scénario.
Toutes les assertions historiques de `verifier` sont conservées à AST identique,
dont une seule cotisation, prestation et ligne d'historique. Le moteur et ses
verrous restent inchangés. Contre-épreuve locale : en neutralisant le verrou
uniquement dans les processus fictifs, le test corrigé échoue bien sur
« le poste B n'a pas attendu le poste A ».

### Preuves de non-régression et matrice

Exports des commits suivis dans un nouvel espace isolé, sans profil Portable,
sans nouvelle branche ni worktree. Runtime Python 3.10 Windows existant, profils
APPDATA/LOCALAPPDATA temporaires, variables MySQL de test retirées, garde DB et
garde socket héritée par les enfants. Chaque arbre candidat passe 62 tests
ciblés : 60 réussites, deux tests MySQL ignorés faute de serveur déclaré, zéro
tentative de connexion réseau réelle. La CI rapide confirme ensuite les trois
commits ci-dessus : 105 tests exécutés par branche, 103 réussites et deux MySQL
ignorés, sans affaiblissement d'assertion ni recette sur données réelles.

Comparaison exacte des arbres publiés : aucun écart sous `noethys/`, `tests/`
ou `.github/` entre main/wx/qt ; les divergences documentaires et les historiques
propres sont conservés. Six lignes de correctifs sont transférées et les commits
Nomadhys/TLS/vaccins précédemment adaptés ne sont pas remplacés par un historique
ancien. Il ne s'agit pas d'une séparation effective des moteurs wx et Qt.

| Périmètre | main | wx | qt |
| --- | --- | --- | --- |
| Étiquettes sans titulaire, déplacements Noedoc, mode GetHTML | VALIDÉ tests + CI | VALIDÉ, blobs identiques + CI | VALIDÉ code commun, blobs identiques + CI |
| Synchronisation du test de concurrence SQLite | VALIDÉ, assertions conservées + CI | IDENTIQUE + CI | IDENTIQUE + CI |
| Correctifs communs Nomadhys/TLS/vaccins déjà présents | CONSERVÉS | IDENTIQUES, CONSERVÉS | IDENTIQUES, CONSERVÉS |
| Adhésions MySQL réelles / protections SQL avancées Noe-032 | EN ATTENTE | EN ATTENTE | EN ATTENTE |
| Mails aux familles non reçus, signal utilisateur | EN ATTENTE de requalification | EN ATTENTE | EN ATTENTE |
| Interface Qt native / recette GUI exhaustive | NON APPLICABLE | Recette exhaustive EN ATTENTE | EN ATTENTE |

### Conservation et obstacles restants

Publication atomique de trois avancées normales, chacune ayant sa tête initiale
pour parent direct. Aucune nouvelle branche, force-push, réécriture, suppression,
fusion globale, fermeture/reciblage de PR, tag, release ou bascule de défaut.
**44 branches et huit PR inchangées hors les trois têtes canoniques.**

Signal nouveau → requalification appliqué aux nouvelles têtes : nouvelle
comparaison des blobs des 30 sources aux 14 têtes protégées ; chaque source
reste à son SHA précédent et conserve des fichiers distincts. Les AST runtime
nouvellement présents dans wx/qt étaient déjà accessibles dans main ; aucune
variante historique n'est réputée abandonnée ou entièrement intégrée sur cette
seule base. Zéro nouvelle suppression sûre. Détail de cette vérification dans
`consolidation-suite-20261012/requalification.json` de l'espace Codex ; le dossier
de provenance publié de la section 17 et les bundles demeurent les références.

Les stop-gates CI et trois écarts communs de la section 18 sont levés pour le
périmètre testé. Restent les 30 variantes historiques, master/SQL/métier, le
signal des mails non reçus et la recette Qt. Pour les mails, l'utilisateur indique
la dernière version fournie la semaine précédente, sans certitude RC2/RC3.
Les notes historiques distinguent un candidat local titré RC2 et une RC3 publique ;
Lecture du seul `C:\Noethys\BUILD-INFO.txt` (aucun profil consulté) : installation
présente identifiée « Noethys SL 0.1.0 RC2 - Windows », commit
`4fef6a42cfcaf1258f25209f85c22224441d7f5b`, workflow `37724018307`.
Version exacte lors de l'incident, date et résultat affiché restent à établir.
Ce commit est ancêtre de la source conservée `fix/rc2-network-stopgate-1`
(`cf5f9fbe6ccd9472a061ceaf81ab6358effc00b3`), pas de la tête RC2 protégée ni
du tag RC3 : ne pas déduire le contenu du seul libellé RC2/RC3. Le code source
de cette installation possède `_AfficherCompteRendu`, `_DetailErreurMailjet`,
`callback_succes` et `mailjet_ids`, absents sous ces noms des modules Mailer/
Envoi_email de main. Ce sont des contrats de bilan/traçabilité à requalifier,
pas une preuve que leur absence a causé l'incident ni que l'installation
exécute exactement ses métadonnées. Aucune modification de l'installation.
Aucune livraison ni cause présumée, aucun
mail envoyé, aucune donnée ou adresse de famille lue. Worktree WIP, trois stashes,
branches locales wx/qt/master, tags/releases et fichiers non suivis existants
restent préservés. Le principal est avancé seulement par fast-forward vers main,
sans y exécuter de tests ni accéder au profil Portable.


## 20. Requalification Mailjet : réponses et bilan de lot — 12/10/2026

État initial revérifié : 44 branches, huit PR, main
`7f876edd9207e88c4bad20ee3a3c599884b8017a`, wx
`c8f26c41040b21f0324d319470c063b1f9116e47`, qt
`06107757a4b6614908c37efa543cade1ba22412a`. Suite autorisée par l'utilisateur
après le signal de mails non reçus. Lot borné au backend Mailjet : aucune
requalification de livraison effective ni conclusion sur la cause de l'incident.

### Provenance et reproduction

Source historique de l'installation identifiée :
`4fef6a42cfcaf1258f25209f85c22224441d7f5b`, toujours ancêtre de la source
conservée `fix/rc2-network-stopgate-1` à
`cf5f9fbe6ccd9472a061ceaf81ab6358effc00b3`. Le nom RC2 ne vaut pas identité
avec la tête RC2 protégée ou un autre portable. L'installation reste intacte.

Quatre éléments historiques repris à AST identique : `_RetirerAnomalies`,
`_AfficherCompteRendu`, `ErreurMailjet`, `_DetailErreurMailjet`. Onze tests
Mailjet sélectionnés dans `tests/test_rail1_mail_lot.py` de ce commit sont
réutilisés avec leurs assertions intactes, sous un nouveau harnais avec garde
réseau. SMTP, callbacks d'historique et rattachements du fichier historique
ne sont pas importés comme fonctionnalité dans ce lot.

Reproduction sur main initial : 14 tests, un succès, huit failures et cinq
errors. Les écarts reproduits portent sur le motif d'erreur API, le bilan
après arrêt ou réessai, les identifiants de suivi et la confirmation trop forte.
Trois cas supplémentaires caractérisent HTTP en échec + corps "success",
double lecture d'un JSON inexploitable, et renvoi après panne d'affichage
postérieure à l'acceptation. Deux cas ajoutés pendant la revue protègent les
métadonnées de suivi malformées et la panne d'affichage en fin de lot.

### Résultat publié et CI

| Branche existante | Commit de code | CI rapide syntaxe + Windows |
| --- | --- | --- |
| main | `2b8fab2eecf94bd74e065d716ccb29e67c11433a` | [SUCCÈS #38222855429](https://github.com/fr4nck/Noethys-SL/actions/runs/38222855429) |
| wx | `99a423e6aa7b1a3628c04554dd9e3e27babf4e8c` | [SUCCÈS #38222855118](https://github.com/fr4nck/Noethys-SL/actions/runs/38222855118) |
| qt | `87db1dd4f2cee05306ed3f814ea4cd65c1a03223` | [SUCCÈS #38222856320](https://github.com/fr4nck/Noethys-SL/actions/runs/38222856320) |

- Motifs de refus Mailjet affichés (HTTP, message et code d'erreur) sans dump
  complet de la réponse/payload. Le JSON est lu une seule fois. Un HTTP en
  échec n'est pas compté comme succès, même avec un corps incohérent.
- Identifiants MessageID/MessageUUID conservés sur l'objet message en mémoire ;
  les champs de suivi optionnels malformés ne déclenchent pas de renvoi.
  Aucun schéma ni stockage durable de ces identifiants ajouté implicitement.
- Bilan structuré `dernier_bilan` : acceptés / échecs / non tentés. Après arrêt,
  les messages suivants restent explicitement non tentés ; après un réessai
  réussi, le message sort de la liste des échecs. Type de retour liste conservé.
- Confirmation Mailjet : « accepté pour envoi », avec la limite de remise
  effective ; aucun statut "reçu par la famille" inventé.
- Une panne d'affichage après acceptation ou lors de la clôture de progression
  ne renvoie pas le mail et ne détruit pas le bilan. Contre-exemple reproduit
  avant correction : choix Réessayer après panne de progression entraînait
  deux appels d'envoi pour le même message.

Dans trois exports isolés des commits suivis : 57 tests ciblés réussis par
branche, dont les 16 nouveaux cas et les 41 tests existants de confirmation,
erreurs, Base64/progression et parent de fenêtre. Profils temporaires vides,
variables MySQL retirées, garde DB et garde socket des processus ; zéro
connexion réelle. CI rapide : 121 tests exécutés par branche, 119 réussites
et deux tests MySQL ignorés. Aucun mail réel, serveur SMTP, compte Mailjet,
base réelle, profil Portable, famille réelle ou secret utilisé.

### Matrice et préservation

| Périmètre | main | wx | qt |
| --- | --- | --- | --- |
| Réponses Mailjet, erreurs utiles, IDs en mémoire, bilan, réessai, arrêt | VALIDÉ simulations + CI | IDENTIQUE + CI | IDENTIQUE code commun + CI |
| Absence de renvoi après panne d'affichage post-acceptation | VALIDÉ | IDENTIQUE | IDENTIQUE |
| SMTP, adresses/rattachements, historique durable au fil de l'eau | NON PORTÉ / EN ATTENTE | NON PORTÉ / EN ATTENTE | NON PORTÉ / EN ATTENTE |
| Réception des mails de l'incident / recette GUI réelle | EN ATTENTE | EN ATTENTE | EN ATTENTE |

AST des classes SMTP et de toutes les autres définitions préexistantes du
module inchangés ; Mailer, Connecthys, Nomadhys, SQL et schémas inchangés.
Modifications limitées à UTILS_Envoi_email.py, une suite de tests et son
inclusion dans la CI rapide. Les sources, tests et workflows sont identiques
entre main/wx/qt, les historiques et documents propres restent conservés.

Publication atomique par trois avances normales, chacune ayant pour parent
direct sa tête initiale. Aucune création/suppression de branche, force-push,
réécriture, merge global, clôture/reciblage de PR, tag, release ou build.
Signal nouveau → requalification : nouvelle comparaison des 30 sources aux
14 têtes protégées ; chaque source demeure au même SHA et garde des apports
non démontrés intégralement repris. Zéro candidate supplémentaire sûre.
**44 branches, huit PR préservées.** Sources Mailjet historiques et réseau
maintenues ; ce portage partiel ne justifie pas leur suppression.

Documentation sur main et avance du dossier principal uniquement par
fast-forward. Worktree WIP, stashes, branches locales master/wx/qt, tags,
releases et fichiers non suivis existants préservés. Preuves de la session :
`mail-qualification-20261012` dans l'espace Codex (logs avant/après, différences,
SHA, résultats CI et nouvelle requalification des sources).

### Obstacles et prochaine qualification

Le signal utilisateur concerne le dernier candidat fourni la semaine
précédente. L'utilisateur confirme pendant cette session que le service utilisé
était Mailjet. La version/date lors de l'incident et le résultat affiché restent
à préciser ; aucun accès aux paramètres du profil
réel. Ni les simulations ni la CI ne prouvent que les mails manqués sont arrivés.
Un déploiement du code dans l'installation RC2 n'est pas effectué.

Poursuite : qualifier séparément les adresses configurées/rattachements et
l'historique au fil de l'eau, puis la remise uniquement par éléments de recette
autorisés et statuts fournisseur. SMTP et absence de callback durable restent
des stop-gates, avec master/SQL, les 30 variantes historiques et la recette Qt.
Ne pas réémettre automatiquement des mails dont l'acceptation/livraison est
inconnue. Aucun envoi à une famille n'est autorisé par cette qualification.

Contrats fournisseur consultés : [erreurs Send API v3.1](https://dev.mailjet.com/docs/email-api/send-api-v31/send-api-errors)
et [SandboxMode, succès de validation sans livraison](https://dev.mailjet.com/docs/email-api/send-api-v31/sandbox.mode).
Les tests utilisent uniquement des doublures locales, jamais ce mode distant.


## 21. Qualification et retrait des deux branches Mailjet — 12/10/2026

L'utilisateur confirme : appliquer dans le dépôt uniquement, puis supprimer
les branches qualifiées. Aucune mise à jour de C:\Noethys ni opération sur un
profil réel. Départ : 44 branches et huit PR ouvertes ; main
`544e1d37865c8bec4524142ac6e3ea5ed83a8a64`, wx
`99a423e6aa7b1a3628c04554dd9e3e27babf4e8c`, qt
`87db1dd4f2cee05306ed3f814ea4cd65c1a03223`.

### Deux références qualifiées, sans recopier un code plus ancien

| Référence | SHA attendu | Apports propres conservés |
| --- | --- | --- |
| fix/noethys-sl-mailjet-consolidation | `51ee128a60ded8dfb4d8bcf77f28219eb1f1f6f5` | Base64 ASCII, cycle de progression, confirmation manuelle, erreurs Python 3, protections de thread et mots de passe ; code/tests conservés, parent visible de progression plus protecteur sur main. |
| fix/noethys-sl-mailjet-email-confirmation | `9e0945b5d0a411ef8d03a7179df5abb4a18919c1` | Dépendance Mailjet, conversion d'erreur Python 3, confirmation manuelle, art providers clairs et désactivation dark mode ; fonctions et instructions propres conservées dans les implémentations actuelles. |

Ancêtre commun de comparaison : `3f6e5d0f7fab1396458f048ba8a7a538c41a16e2`.
L'analyse porte sur les changements propres, y compris imports, instructions,
fonctions supprimées, docs et tests, et pas sur la seule différence des arbres.

Preuves du signal nouveau → requalification :
- Tous les fichiers sources comparés aux 14 têtes protégées ; ceux ayant des
  blobs identiques sont indexés avec leur référence de conservation.
- `DLG_Mailer.Dialog.Envoyer` identique par AST après trois remplacements
  explicitement justifiés : helper de formatage Python 3 déjà testé, propriétaire
  réellement visible de la ProgressDialog, exception de destruction limitée à
  RuntimeError. Aucun appel métier abandonné ni retour à parent=None.
- `DLG_Saisie_portail_demande.Dialog.Envoyer` au même AST. Les autres différences
  du fichier sont héritées ; elles ne justifient pas de réintroduire l'ancienne
  réception autorisant les formats chiffrés non SV2.
- Dans Noethys.py, chaque instruction terminale ajoutée par la source dans les
  cinq méthodes concernées est présente dans la cible ; les instructions
  retirées (ancien ModernDockArt, ForceApparenceClaireAUI, accès thème ancien)
  restent absentes. Conditions et garde MSW/claire couvertes par la suite actuelle.
- Chaque nœud AST de l'ancien UTILS_AUI_Apparence est conservé identiquement ;
  les définitions nouvelles du manager sont additives.
- L'apport propre de l'ancien Mailjet.Envoyer_lot est exclusivement la conversion
  Python 2/3 de l'erreur, désormais assurée par _TexteUtf8 et vérifiée en comportement.
  Les prédicats statiques des anciens tests exigeant un bloc inline six.PY2 sont
  archivés intacts ; aucun test actuel affaibli ou retiré pour rendre la CI verte.

Les apports étaient déjà appliqués/qualifiés lors des lots antérieurs : aucun
runtime ni test modifié dans ce lot de retrait. Sur un nouvel export isolé du
SHA main actuel, 91 tests ciblés réussissent (mails, art providers, thème clair,
tooltip et thread wx/Python 3). Profil temporaire, garde DB et socket, aucune
connexion réelle. Les sources/tests/workflows de main/wx/qt sont identiques.
La dernière CI de code reste verte : 121 tests, 119 réussites et deux MySQL
ignorés pour chacune des trois branches (section 20). Pas de recette graphique
exhaustive ni preuve de réception des mails de l'incident.

### Conservation préalable et retrait contrôlé

Les 32 fichiers des deux deltas historiques sont archivés à l'octet près sous
`docs/archives/branches-20261012-mailjet`, avec commits, blobs et SHA-256 dans
qualification.json. Les anciens tests et docs sont conservés même lorsque leur
forme d'implémentation est remplacée. Aucun fichier d'archive n'est exécuté.

`github-all-refs.bundle` revérifié ; les deux SHA y figurent exactement.
Empreinte SHA-256 :
`1898e49973c9abf8832c3e6b01b816f7813df94e7d10e96d8cec3e89146890eb`.
Les deux branches ne sont ni tête ni base d'une des huit PR ouvertes. master,
RC2/RC3, feature/vanilla-conventions et les autres références nécessaires aux
PR restent protégées.

Ce commit prépare un push atomique : archive et note sur main, plus deux
retraits distants. Le hook de pré-push vérifie les SHA annoncés par le serveur,
le périmètre exact et l'absence de force-push ; un changement de ref bloque
l'opération pour requalification. Le résultat réel sera consigné après contrôle.
Si le push réussit, il restera 42 branches : 14 protégées et 28 sources encore
conservées. Aucun merge global, nouvelle branche, historique réécrit, publication
de binaire, tag ou release. Les variantes restantes sont des stop-gates, notamment
réseau, SQL, interventions, Qt, packaging et historique durable des mails.


### Résultat réel confirmé du lot Mailjet

Push atomique réussi au commit d'archives
`e7cb1c9122746df408d004f83563077fc7186f47` : les deux références Mailjet du
tableau ont été retirées aux SHA attendus. Après lecture réelle de GitHub :
**42 branches distantes, 14 références protégées et 28 sources conservées**.
Les huit PR (102, 104, 112, 355, 366, 369, 384, 422), leurs titres/descriptions,
drafts, têtes et bases sont inchangés. Toutes les autres têtes distantes sont
inchangées ; seul main avance par documentation/archives. Tags et releases
revérifiés inchangés. Aucune modification de runtime, de tests ou d'installation.

Les 32 fichiers archivés et le dossier de qualification sont publiés avant le
retrait dans la même transaction Git ; blobs et empreintes revérifiés. Le hook
de contrôle des SHA annoncés a aussi été vérifié en contre-épreuve : un SHA
périmé est refusé avant toute mutation. Pas de flag force ni force-with-lease.
Le journal exact de qualification contient 91 tests réussis ; ce chiffre corrige
le comptage provisoire annoncé oralement de 87. La note préparatoire porte déjà
le chiffre exact.

Le dossier principal est avancé par fast-forward uniquement et les deux refs
locales origin obsolètes sont retirées seulement à leur ancien SHA attendu.
Les quatre branches locales durables (master/main/wx/qt), les trois stashes,
le worktree WIP détaché et les fichiers non suivis existants restent préservés ;
seul main avance. Le contenu du profil Portable n'est pas consulté.

Les 28 sources encore conservées sont les lignes de la section 18 à l'exception
des deux références retirées ci-dessus, détaillées dans dossier-conservation.json
et le dossier de qualification de cette session. Les deux suppressions n'effacent
ni les sources réseau de l'installation historique, ni les callbacks d'historique
et les règles d'adresses non portés. Restent les stop-gates réseau/SQL, traitements
de familles/tiers/interventions, Qt, packaging, et la recette de remise effective
Mailjet. Aucun changement nouveau permettant un autre retrait n'est revendiqué.
Suite : intégrer/qualifier ces domaines par lots avant leur retrait ; ne pas
réutiliser les anciens plans sur un nouveau SHA sans requalification.


## 22. Reprise du bac a sable MySQL #104 et cloture documentaire — 12/10/2026

- **Branches autorisees uniquement :** main, wx, qt. Anciennes branches conservees tant que non qualifiees. `master` reste la branche par defaut, non modifiee. Aucun nouveau branchement, merge global, force-push, migration, packaging ou consultation de donnees PMSL.
- **Source historique :** PR #104 (branche `dev-db-docker`) ; reprise adaptee, non fusionnee. L'environnement MySQL 5.5 conserve la reference digest historique, la liaison locale 127.0.0.1:3308 et une base strictement fictive.
- **Apports publies :** .gitignore, dev/db/.env.example, dev/db/compose.yml, dev/db/guard.ps1, dev/db/start.ps1, dev/db/reset.ps1, dev/db/import.ps1, dev/db/smoke.ps1, dev/db/README.md, .github/workflows/noe-032-mysql-smoke.yml.
- **Securite ajoutee :** nom du projet/conteneur Docker fixe, restart refuse, verifications fichier .env et surcharge d'environnement, contexte Docker local impose, image epinglee ou convertie CI, reset limite au projet avec double confirmation, blocage de tout import generique Noethys au profit de la fixture synthetique unique.
- **Propagation verifiee** : SHA Git blob strictement identique pour chacun des dix fichiers sur main/wx/qt, controle via GitHub apres publication. Les commit SHA des trois branches divergent volontairement et ne signifient pas une difference de contenu de ce lot.
- **Qualification** : verification des fichiers Git reussie ; scripts PowerShell et Docker NON EXECUTES dans cet environnement, Windows reel, ancienne image MySQL et restitution de bases fictives EN ATTENTE. Le workflow est manuel pour preserver les minutes Actions. Ce lot ne leve PAS les stop-gates restauration SQL avancee, schema complet, dump tronque, postconditions, reseau ou rollback. Aucune conclusion sur l'installation d'exploitation.
- **PR documentaires :** #102 et #112 reprennent chacune un seul fichier; les blobs uniques ont ete integres identiquement aux trois branches lors du lot precedent. Les deux PR ont recu une note de provenance et sont fermees comme reprises/supplantees (non mergees), sans modification de master. #104 reste ouverte, non qualifiee.
- **References distantes** : 42 branches au dernier inventaire, aucun retrait supplementaire dans ce lot. PR ouvertes passees de 8 a 6 apres cloture #102/#112 ; recontroler cet inventaire avant toute operation ulterieure.
- **Prochaine action concrete** : executer la recette manuelle sur runner/sandbox isole avec donnees 100 % synthétiques (aucune base PMSL) ; qualifier les 25 tests historiques Noe-032 et les protections de master par comportement avant portage cible sur main puis adaptations wx/qt. Les anciennes branches ne pourront etre supprimees qu'apres preuve d'integration ou arbitrage explicite.

- **Tentative de qualification CI one-shot :** commit `c186aede04cac7f6b087eb18a181d42a7cfbc0ce` ajoute provisoirement un declenchement push restreint a main + dev/db/workflow ; commit `6b6edefbe9dc6621ae4b2230fb04f004d3f7e42d` restaure immediatement le declenchement manuel. Les endpoints de verification disponibles ne retournent pas de run ni statut de checks sur le commit de tentative : **resultat d'execution NON VERIFIE**, pas de succes CI revendique. Rechercher run/logs GitHub de ces SHA avant toute promotion de statut. Aucun workflow permanent sur chaque push.


## 23. Noe-032 — codes de retour SQL et isolation Docker (12/10/2026)

**Source de verite lue avant modification :** main `0f8bfc63`, wx `033b3a0e`, qt `2132b964`, master `b0be3c7e`. Aucune nouvelle branche, aucun merge global, aucune operation sur master, aucun profil reel, aucune migration SQL.

**Defaut de sauvegarde CONFIRME dans les sources :** la fonction Sauvegarde se basait sur une sortie stdout/stderr non vide pour determiner l'echec de mysqldump ; un code de retour non nul avec sortie vide pouvait etre traite comme un succes, eventuellement produire une archive partielle. La fonction Restauration utilisait la meme detection par texte. master possede deja un test explicite sur `proc.returncode` ainsi que d'autres defenses encore absentes ; ne pas recopier son module entier.

**Portage cible dans les trois branches :**
- Dans `noethys/Utils/UTILS_Sauvegarde.py`, chaque subprocess MySQL refuse maintenant `proc.returncode != 0`, meme si stdout/stderr est vide ; diagnostic avec code retour, message d'erreur affiche ; sur echec mysqldump le ZIP temporaire est ferme puis supprime.
- Options mysqldump remises dans l'ordre historique master `--opt --single-transaction --skip-lock-tables` pour neutraliser le verrouillage par defaut implique par `--opt`.
- Un test AST/fixtures `tests/test_noethys_sl_mysql_returncode.py` simule les deux echec silencieux (dump et restauration), sans MySQL, profil ni reseau, et verifie refus/nettoyage du ZIP et des fichiers temporaires. Ajout a la liste explicite CI rapide Windows dans `.github/workflows/noethys-sl-fast.yml`.
- Dans `dev/db/guard.ps1`, refus des overrides `DOCKER_HOST`, `DOCKER_CONTEXT`, `DOCKER_TLS_VERIFY` et `DOCKER_CERT_PATH` : ces variables pouvaient contourner le contexte local Docker selectionne.

**Propagation observee dans GitHub :** les blobs des quatre fichiers ci-dessus sont identiques sur main/wx/qt :
- UTILS_Sauvegarde.py : `2aac43686b361cbd0c5c4953191e5ce96404bbca`
- test_noethys_sl_mysql_returncode.py : `026d5013461fa9795756da9c173899ab2a1cbda3`
- noethys-sl-fast.yml : `90d3bfef9beee153bf1000d23e5ce8409bd5826d`
- guard.ps1 : `43033a2e400b49d45cad6a489ab828475074b2fd`

**HEAD avant la note documentaire :** main `ffeb65448a6590df384f7d9fa28940afe022f77d`, wx `37cba326634d431a3b59c8fbc81ebf83051e5133`, qt `fe7f08105f3fa60a090d3431e1e927fb8a5e9edb`.

**Qualification :** test source ecrit et inclus dans le workflow, sans resultat de test d'execution verifiable dans cet environnement. L'endpoint des statuts de commit retourne une liste vide sur les trois HEAD ; cela ne prouve ni reussite ni echec d'Actions. Pas de `pwsh`, client MySQL ou Docker disponibles pour recette locale dans cet environnement. Ne pas annoncer CI verte ni version stable. Les correctifs sont PUBLIES, execution Windows/MySQL EN ATTENTE.

**STOP-GATE toujours en vigueur :** les fonctions et suites historiques de master pour le manifeste SHA-256 SQL, l'analyse syntaxique, les objets SQL, le marqueur final et les postconditions de restauration ne sont pas integrees. Les 25 tests historiques de master ne sont pas portes comme test runtime avant la qualification du comportement et la vraie recette de base completement synthetique. Aucun changement de branche par defaut ou suppression de source historique. Six PR encore ouvertes a la derniere verification, dont #104.

**Prochaine action :** confirmer CI rapide Windows pour les trois arbres, qualifier MySQL 5.5/Docker avec uniquement la fixture synthétique, puis isoler les protections manifeste et restauration de master avec tests historiques avant integration. Requalifier sur tout signal nouveau.


## 24. Noe-032 — manifeste SQL V1 branche aux sauvegardes et restaurations — 12/10/2026

- **Etat initial verifie :** main `9af27516313f6947bbb5985e705f6ab85530329f`, wx `37cba326634d431a3b59c8fbc81ebf83051e5133`, qt `fe7f08105f3fa60a090d3431e1e927fb8a5e9edb`, master inchange `b0be3c7e`. Aucun nouveau branchement, aucun merge global, aucun force-push, aucune suppression.
- **Source historique :** constantes et enveloppe de manifeste de `master` (`_AjouterManifesteIntegriteSQL`, `_ExtraireChargeSQL` dans `UTILS_Sauvegarde.py`). Aucun remplacement global de l'ancienne implementation du module de sauvegarde.
- **Composant partage :** nouveau `noethys/Utils/UTILS_SQL_Integrite.py` sans dependance wx/DB : ecriture d'un manifeste V1 de meme format (jeton, taille, SHA-256), remplacement atomique `os.replace` preservant le dump original si l'ecriture echoue, validation par blocs de 1 Mio au lieu d'une lecture en memoire du dump complet. Refuse manifeste tronque, taille incoherente, jeton divergent, empreinte fausse et charge vide. Les dumps historiques sans manifeste restent admis par ce seul controle de compatibilite.
- **Activation commune :** `noethys/Utils/UTILS_Sauvegarde.py` ajoute le manifeste apres succes de mysqldump et avant insertion dans le ZIP ; un echec de son creation refuse la sauvegarde et nettoie le ZIP temporaire. En restauration, verification de la copie SQL extraite **avant** creation eventuelle de la base MySQL et avant toute commande mysql. Un manifeste invalide refuse l'import. Le chemin de fichier SQL reste de type texte (`fichierZip.write(fichierSave, ...)`) comme sur master, sans encodage bytes inapproprie.
- **Tests :** `tests/test_noethys_sl_sql_manifest.py` : 11 tests du composant pur, executes localement et PASS sur prototype de module dont le blob Git est identique au blob publie `3cd07c59c9b7501c48c3a8a707bc6a38d37e6729`. Cas testes : enveloppe valide, ancienne sauvegarde, corruption a taille constante, troncature, marqueur orphelin, jeton modifie, dump vide, double enveloppe, gros bloc, echec atomique. `tests/test_noethys_sl_sql_integration.py` ajoute 3 tests AST/faux processus : refus avant SQL, sauvegarde avec manifeste, ancien dump lisible ; tests ajoutes mais leur execution contre le code Noethys GitHub reste **EN ATTENTE**. Suite precedente `test_noethys_sl_restore_network_config.py` conserve ses verifications et attend desormais explicitement sept sorties anticipees, dont la nouvelle garde. Tests references dans CI rapide.
- **Propagation** : fichiers communs `UTILS_SQL_Integrite.py`, `UTILS_Sauvegarde.py`, `test_noethys_sl_sql_manifest.py`, `test_noethys_sl_sql_integration.py`, `test_noethys_sl_restore_network_config.py` et `noethys-sl-fast.yml` controles blob a blob sur main/wx/qt : tous identiques avant le dernier raffinement du cas vide, qui a ensuite ete publie dans les trois branches avec blob identique.
- **HEAD avant cette note :** main `9a89744030cc1afce19b958a970bf94dfb976324`, wx `283bc97429963d203b821de8d4482c2bc0f96d94`, qt `884ce6e66adf22f81bb3f88a923529e969d5c0e4`.
- **Stop-gates non leves :** aucune validation Windows de la nouvelle integration, aucun test reel MySQL/MariaDB ni preuve de CI verte sur HEAD, pas de verification syntaxique complete des dumps historiques. Un ancien dump *sans manifeste* peut encore etre tronque ; l'analyse syntaxique, le marqueur terminal d'execution, l'inventaire des objets SQL et les postconditions avances de master ne sont pas portes. Aucun rollback transactionnel de restauration reseau qualifie. Ne pas annoncer la Vanilla stable, ni supprimer master ou la PR #104.
- **Suite** : verifier la CI rapide Windows et les nouveaux tests d'integration ; sur base MySQL 100 % fictive, tester un dump complet, altere, tronque et ancien. Porter ensuite les controles syntaxiques et de postcondition depuis master par lots separes et qualifies ; jamais de donnees PMSL ni migration implicite.


## 25. Noe-032 — CI rétablie, analyse syntaxique portée, bac à sable MySQL 5.5 exécuté — 12/10/2026

- **État initial vérifié :** local main `2bac6931` en retard ; distant main `eb71601a`, wx `283bc974`, qt `884ce6e6`, master `b0be3c7e` (inchangé). Mise à jour locale par fast-forward vérifié uniquement. Aucune branche créée, aucun merge global, aucun force-push ; worktrees temporaires sur les branches existantes, supprimés après usage.
- **Échec CI constaté puis levé :** CI rapide en échec sur main `9a897440` (run 38240817180) et wx `283bc974` : `NameError: UTILS_SQL_Integrite` dans `test_code_sortie_non_nul_restauration_sans_stdout_rejetee`. Cause : le harnais AST de `tests/test_noethys_sl_mysql_returncode.py` n'injectait pas le module ajouté à `Restauration` (code applicatif sain). Correctif : chargement du vrai module pur. Commits main `b543ab7f`, wx `c4b30891`, qt `64ac2075` (blob `c3be0074`). **CI verte prouvée** : main run 38244936785, wx run 38244936141.
- **Analyse syntaxique portée depuis master :** `_NettoyerSQLPourAnalyse`, `_DecouperInstructionsSQL`, `_ClasserInstructionSQL`, `_NomObjetSQL`, `_NouvelInventaireObjetsSQL` et 6 constantes recopiés dans `UTILS_SQL_Integrite.py`, **identité AST vérifiée** avec `origin/master:noethys/Utils/UTILS_Sauvegarde.py`. Nouvelle entrée `AnalyserDumpSQL` (réutilise `VerifierIntegriteSQL`), appelée par `Restauration` avant création de base et `mysql`. Refus : dump vide, chaîne/commentaire non fermé, dernière instruction incomplète, délimiteur non rétabli, aucun objet restaurable. Tests : `tests/test_noethys_sl_sql_analyse.py` (13 cas : cas master + dump mysqldump synthétique avec BLOB, vue, trigger, troncatures) et 2 cas d'intégration « refus avant SQL » (contre-épreuve : échouent sans le branchement). Ajouté à la CI rapide. Commits main `9aebf953`, wx `915e98e6`, qt `c520a429`. Blobs identiques : `UTILS_SQL_Integrite.py` `3aa67a2e`, `UTILS_Sauvegarde.py` `878eb1e7`, test `b0919262`. **CI verte prouvée** sur main `9aebf953` et wx `915e98e6`.
- **Tests locaux (venv identique CI : Python 3.10.11, wxPython 4.2.5) :** rapide 152/152 OK sur main, wx et qt ; suite complète 790 OK (2 skips, 1 échec attendu) sur main.
- **Bac à sable MySQL 5.5 exécuté pour la première fois (Windows 11, Docker Desktop 29.8) :** quatre défauts bloquants corrigés dans `ea866703` (main), `ad909d86` (wx), `af0a616f` (qt) : garde de contexte Docker toujours en refus (`Select-Object -First 1` vidant `$LASTEXITCODE`) ; manifeste schéma v1 `d404d78a` plus servi par Docker Hub (ni par Skopeo) → épinglage sur le digest v2 officiel linux/amd64 du même tag `mysql:5.5.62` `c9c671d0` ; scripts CRLF envoyés à `sh` ; garde d'import refusant tout vrai dump (double `USE` pour les vues, motif `CREATE DATABASE` en retour arrière). `smoke.ps1` : **PASS (2 lignes, 1 vue)**. Contre-épreuves : base étrangère (même ligne, `CREATE SCHEMA`, `IF NOT EXISTS`), `DOCKER_HOST` distant et image non approuvée refusés. Le workflow manuel `noe-032-mysql-smoke.yml` n'a pas été rejoué. Un conteneur tiers `noethys-mysql57` (port 3307, contenu inconnu) existe sur le poste : non touché. Conteneur de recette arrêté, volume conservé ; `dev/db/.env` local ignoré par Git.
- **Qualification sur MySQL 5.5.62 réel, données 100 % synthétiques (13/13 PASS) :** script hors Git (scratchpad de session) ; base `noe032_qualif_source` créée puis supprimée. Dump aux options exactes de Noethys (`--opt --single-transaction --skip-lock-tables --databases`), 300 individus avec accents/quotes/`;`/`--`/`/*`, 40 BLOB binaires aléatoires, table à nom avec espace, vue, trigger, procédure, fonction : accepté, inventaire exact (vue non comptée comme table). Manifeste sur dump réel accepté. 400 troncatures aléatoires d'ancien dump : toutes refusées ; 100 troncatures avec manifeste : toutes refusées. Restauration réelle par `mysql` : checksums identiques, vue et trigger présents.
- **Limite résiduelle démontrée (ARBITRAGE MÉTIER REQUIS) :** un ancien dump **sans manifeste** coupé exactement entre deux instructions est accepté par l'analyse, et `mysql` le restaure avec le code 0 (une seule table restaurée dans l'essai). Le marqueur terminal et les postconditions de master ne couvrent pas ce cas (objets attendus déduits du dump déjà tronqué). Indice disponible : la ligne finale `-- Dump completed` écrite par mysqldump, absente du dump coupé. Options : refuser, demander confirmation avec avertissement, ou accepter. Rien n'est implémenté sans décision.
- **Matrice Noe-032 après ce lot :** correctif harnais returncode, analyse syntaxique, bac à sable exécutable : **VALIDÉ** sur main/wx/qt (blobs identiques, tests locaux ; CI Actions prouvée main/wx, qt sans CI rapide déclenchée). Marqueur terminal et postconditions MySQL de master : **ABSENT** des trois branches (valeur marginale réduite par le contrôle du code retour, à qualifier). Validation Windows de l'application Noethys réelle sur restauration : **EN ATTENTE**.
- **Suite :** arbitrage `-- Dump completed` ; décider du portage du marqueur terminal et des postconditions (exige `GestionDB` sur la base de recette 3308) ; rejouer éventuellement le workflow manuel MySQL ; poursuivre la stabilisation Vanilla et le tri des PR ouvertes (#104 qualifiable désormais : outillage repris et exécuté).


## 26. Noe-032 — arbitrages appliqués, restauration sûre de bout en bout ; PR #104 ; Vanilla — 12/10/2026

- **Arbitrages du 12/10/2026 appliqués** (décisions de Franck) : (1) ancien dump sans manifeste et sans ligne finale `-- Dump completed` refusé en restauration normale, aucun contournement dans le code, procédure isolée `docs/exploitation/RECUPERATION_DUMP_SQL.md` ; (2) marqueur terminal et postconditions de master repris et adaptés ; (3) contrôle de toute l'archive avant la première écriture.
- **Ligne finale vérifiée par version** : présente avec les options Noethys sur mysqldump MySQL 5.5, 5.7, 8.0 et MariaDB 10.11 (`-- Dump completed on <date>`, ou sans date avec `--skip-dump-date`) ; absente avec `--compact` et `--skip-comments`, options possibles via `Customize` : un dump **avec manifeste** reste donc accepté sans elle (SHA-256). Constat : un client MariaDB sur serveur 5.5 s'interrompt (code 2) sans cette ligne.
- **Code** (main `4278bb17`, wx `45cf505d`, qt `cd577e80`, blobs identiques `UTILS_SQL_Integrite.py` `474a8ad9`, `UTILS_Sauvegarde.py` `4a8a1452`) : `AnalyserDumpSQL(exiger_fin_mysqldump=True)` ; helpers purs `AjouterMarqueurTerminalSQL`, `VerifierPostconditionMySQL` (tables, vues, triggers, routines, événements), `SupprimerMarqueurMySQL` (connexion injectée) ; `Restauration` réordonnée : confirmations et prérequis, lecture CRC complète des fichiers Sqlite et analyse de tous les dumps, puis seulement écriture Sqlite et import MySQL ; marqueur supprimé en `finally` même si `mysql` échoue ; ZIP fermé même sur exception imprévue. Chemin d'appel unique : `DLG_Restauration` → `Restauration`.
- **Tests** : 25 nouveaux cas, tests existants adaptés sans retrait d'invariant (9 sorties gardées avec fermeture du ZIP, aucune extraction avant contrôle). Mutation des 5 protections une à une : toutes détectées. Rapide 174/174 et complète 812 OK en local (venv CI) ; rapide 174/174 sur wx et qt. **CI verte** : main run 38251787125, wx run 38251787106.
- **Recette de bout en bout sur MySQL 5.5.62 réel, données synthétiques : 14/14 PASS** (vraie `Restauration`, vrai `GestionDB`/MySQLdb, vrai client `mysql` du conteneur ; dialogues wx simulés). Couvre ancien dump, manifeste sur base existante, dump coupé en frontière refusé base intacte, mixte invalide sans toucher Sqlite, mixte valide, erreur SQL en import, fin non exécutée, objet manquant, absence de marqueur résiduel. Script hors Git (scratchpad de session).
- **PR #104** : qualifiée fichier par fichier ; apports manquants intégrés (`.gitignore` imports/exports/rapport d'anonymisation, doctrine d'anonymisation et ADR-006 dans `dev/db/README.md`) : main `03ab9f50`, wx `4c23dc0f`, qt `9eebe1b1`. Import générique exclu volontairement. Commentaire de provenance publié, **PR fermée non fusionnée**, branche `dev-db-docker` (`b7dc7c19`) **conservée**. PR ouvertes restantes : #422, #384, #369, #366, #355.
- **Vanilla** : correctif PR #359 déjà présent sur les trois branches (recette Windows native EN ATTENTE). Boutons orphelins masqués et test structurel : main `b20cc82e`, wx `ebd1b0e9`, qt `b5db5656` ; addendum dans `docs/VANILLA_STABILISATION.md`.
- **Matrice** : contrôle préalable de l'archive, ligne finale, marqueur et postconditions, boutons orphelins : **VALIDÉ** main/wx/qt (blobs identiques, tests locaux, CI main/wx ; qt sans CI rapide). Recette dans l'application Noethys complète sous Windows : **EN ATTENTE**. Rollback transactionnel d'une restauration réseau : **ABSENT** (non qualifié). Ne pas annoncer de version stable.
- **Suite** : recette Windows native (restauration mixte sur base 3308 fictive depuis l'UI ; scénario de crash des consommations) ; Vanilla : Liste d'attente, unicité des codes de commande, `CallLater` en attente ; tri des PR #422, #384, #369, #366, #355 et des branches historiques sans perte.


## 27. Noe-032 gelé ; Vanilla : crash natif corrigé à la racine ; tri des PR — 12/10/2026

- **Décisions de Franck (12/10/2026)** : Noe-032 gelé sauf anomalie reproductible ou régression ; pas de rollback MySQL automatique ; sauvegarde préalable et procédure documentée ; dernière recette sauvegarde/restauration depuis l'interface Windows (données fictives) **EN ATTENTE** ; priorité absolue à une Vanilla wxPython exploitable.
- **Crash `0xC0000005` de la liste des consommations** : reproduction automatisée discriminante (ancienne version : crash 3/3 ; version actuelle : 400 cycles OK). Cause racine : timer de `BarreRecherche` encore armé après destruction ; le correctif #359 n'était que local. Correctif générique : main `64d15533`, wx `0d7c86ce`, qt `553ed375` (blobs identiques `CTRL_ObjectListView.py` `2228aaf7`, `OL_Individus.py` `0255f765`, `OL_Villes.py` `6d850202`). Test `tests/test_vanilla_consommations_fermeture.py` (sous-processus) en CI rapide. **CI verte** : main run 38260890467, wx run 38260890753 (le test de crash a tourné sur le runner Windows).
- **Boutons orphelins** (lot précédent) : CI verte main `b20cc82e` (run 38252316470), wx `ebd1b0e9`.
- **Liste d'attente** : non reproductible (SQLite et MySQL 5.5 fictif). **`liste_pieces_fournies`** et **`CallLater` famille/remplissage** : déjà corrigés par #379 sur les trois branches. Timeline : pas de défaut démontré, modification retirée. Scripts de recette hors Git (scratchpad de session).
- **Tests locaux** : rapide 178/178 et complète 816 OK (venv CI) ; tests Vanilla OK sur wx et qt.
- **Tri des PR ouvertes** (comparaison fichier par fichier avec main ; aucune fermée) : #369 et #355 (Noe-062 pointage et secrets interdomaines) : fichiers absents de main, chantiers réseau/pointage hors publication selon AGENTS.md, **conservées** ; #384 (fonctions des individus dans les entités) : modifie `DATA_Tables.py` et `GestionDB.py`, donc le schéma, **arbitrage métier requis** (aucune migration implicite) ; #422 (RC3, versionnement et workflow de publication) : décision de release, **conservée** ; #366 (wiki MkDocs) : documentation hors Vanilla, **conservée**.
- **Suite** : recette humaine Windows (Liste d'attente, sauvegarde/restauration GUI, fermeture de listes pendant une recherche) ; autres P0/P1 des parcours quotidiens ; arbitrage #384.


## 28. Qualification Windows de Vanilla dans l'application réelle — 12/10/2026

- **Décisions de Franck** : PR #384 **reportée, pas abandonnée** (aucune intégration, aucun changement de schéma, branche et PR conservées, à qualifier séparément comme évolution ultérieure) ; correctif de la barre de recherche commune acquis sur main/wx/qt ; priorité à la qualification Windows de Vanilla ; absence de rollback MySQL automatique non bloquante sous réserve de sauvegarde préalable et de procédure de récupération.
- **Méthode** : worktree **détaché** de `main` dans le scratchpad (aucune branche), profil Portable fictif généré par `tests/recette_creer_fichier_fictif.py`. Le dossier non suivi `noethys/Portable/` du dépôt n'a **jamais** été utilisé. Vraie `MainFrame`, vrais dialogues, dialogues modaux pilotés depuis leur boucle (croix, OK), boîtes natives neutralisées, réseau limité au bac à sable 3308. Scripts de pilotage hors Git (scratchpad). Le conteneur tiers `noethys-mysql57` n'a pas été touché.
- **Actions de menu** (217 exécutées) : 4 défauts amont corrigés, `1ad18300` main / `022371a5` wx / `1fac419d` qt — Organisateur, imports CSV (nouveau `Utils/UTILS_Csv_unicode.py`, sans dépendance), Synthèse des déductions. Un faux positif du pilote (`EndModal` forcé sur le gestionnaire AUI) a été écarté par un test de fermeture réelle par la croix, conservé (`tests/test_vanilla_gestionnaire_conso_fermeture.py`).
- **Parcours quotidien** : consultation (famille 11 pages, individu 10 pages, inscription, grille avec saisie en base, liste, gestionnaire) et création (famille, représentant, enfant, inscription, consommation, adhésion) : **0 exception**.
- **Noe-032 par l'interface** (base réseau fictive, clients `mysql`/`mysqldump` 5.5 du conteneur via relais) : sauvegarde avec manifeste et ligne finale ; restauration après perte simulée (données revenues, 0 marqueur) ; ancienne sauvegarde tronquée **refusée**, base intacte ; restauration sur base absente. Défaut amont corrigé : réouverture du fichier restauré, `b25f8b5e` main / `5d70b952` wx / `91ffbadf` qt. **Recette GUI Noe-032 : VALIDÉE (sources, en processus) ; EN ATTENTE sur `Noethys.exe` packagé.**
- **Crash des consommations** : 90 cycles par la commande de menu réelle sans crash (la contre-épreuve passe aussi, grâce au nettoyage local #359 ; la cause racine reste prouvée par le test discriminant du § 27).
- **Tests** : rapide 184/184, complète 822 OK (venv CI) ; nouveaux tests Vanilla OK sur wx et qt ; nouveaux tests ajoutés à la CI rapide.
- **P2 connus, non corrigés** : planning et chronologie des locations (`float` dans `Outils/wxDrawer` et `UTILS_TL_drawing_default`).
- **Suite** : construire le candidat `Noethys.exe` (workflow Windows, sur demande) et rejouer ces recettes sur l'exécutable ; recette humaine courte (DPI, thème clair, clavier) ; trancher l'usage réel des locations à PMSL pour décider du correctif P2.


## 29. Candidat Windows, arrêt des tests graphiques locaux et reprise RC2 (AFAS, Aujourd'hui, périodes) — 12/10/2026

- **Candidat Windows construit** (autorisation de Franck) : workflow existant `noethys-sl-windows.yml` lancé une seule fois en `workflow_dispatch` sur `wx`, run **38273880459**, toutes étapes vertes (compilation, PyInstaller, contrôle du splash, smoke de démarrage du runner, Setup Inno). Provenance : `wx` `b366cb07f6a6c2cce8271ffcc87e91a57708ebd7`, arbre `noethys/`, `tests/`, `packaging/` et `requirements.txt` identique à `main` `0967bde6` (CI verte) ; `BUILD-INFO.txt` porte ce commit. Artefacts (rétention 14 jours) : `Noethys-SL-0.1.0-RC2-Windows-portable.zip` SHA-256 `22bb0980ee572b8231313badb338adcf7b6fc2aa54d0c4d19d322e62787ca52a`, `Noethys-SL-0.1.0-RC2-Setup.exe` SHA-256 `dc656789faa110521b85a3421b3c009da613e79a8c404a33ac6cde29d56edc13`. Ce candidat **ne contient pas** la reprise RC2 ci-dessous (construite avant).
- **Recette du paquet interrompue sur consigne de Franck** : le poste Windows est son poste de travail quotidien. **Interdiction de lancer des tests graphiques sur le bureau actif** ; recette GUI uniquement sur runner GitHub Actions isolé ou VM dédiée, sinon EN ATTENTE. Résultats partiels obtenus avant l'arrêt, sur profil Portable fictif (aucune base réseau) : 126 actions de menu ouvertes et fermées sans exception dans le journal, assistant d'import CSV présent dans le paquet (adaptateur embarqué), écran à 120 DPI (125 %). Le blocage de 83 actions venait du pilote (fermeture d'une fenêtre désactivée), pas de Noethys. Processus de test terminés. **Recette GUI du paquet : EN ATTENTE** (runner isolé à outiller). Les tests qui affichent des fenêtres ne sont plus exécutés localement ; ils passent par la CI rapide.
- **Fonctionnalités RC2 absentes des branches canoniques** : la branche protégée `rc/noethys-sl-0.1.0-rc.2` (`91d9e625`, base de la PR #422) contient 56 commits sans équivalent par patch dans `wx`. Inventaire fichier par fichier face à `wx` : 35 identiques, 15 absents, 43 différents ; analyse à trois voies avec la base commune `8b3789d9`. Reprises ciblées, sans merge, par priorité :
  - **AFAS** (#414, `04c22e7d`) : `DLG_AFAS_Actualisation`, `UTILS_AFAS_Actualisation` (nouveaux), `UTILS_AFAS_Donnees` (agrégation par équipement, réalisé des actualisations arrêté à la date de situation), bouton « CAF / AFAS » de l'État global. main `47e07d66`, wx `6157946a`, qt `64dc7efc` ; blobs identiques à RC2.
  - **Aujourd'hui / éphéméride** (#415 et suites) : `CTRL_Ephemeride` RC2, `UTILS_Ephemerides`, `UTILS_VacancesScolaires`, hunks `Noethys.py` (libellé, menu « Personnaliser Aujourd'hui… », rechargement par utilisateur). Les correctifs propres à `wx` sur ce fichier (anti-flash, arrêt du timer à la fermeture) ont leur équivalent dans la version RC2. main `1de8c06b`, wx/qt via `27ddf6e0`/`e0a7843e`. Workflow `ephemerides.yml` non repris. Le panneau interroge geo.api.gouv.fr et open-meteo avec le seul code postal et la ville de l'organisateur.
  - **Calendrier** : cinq périodes périscolaires (`UTILS_PeriodesSaison`, `CTRL_Grille_periode`, ajouts seulement, aucun symbole retiré), main `9b0e6b71`. Les vacances du dimanche au dimanche (#412) étaient déjà dans `main`.
  - **Défauts de tests hérités de RC2 corrigés** : constantes manquantes et attente d'événements périmée (`test_ephemerides`) ; deux tests graphiques périmés par RC2 elle-même (`0cc84814`, `04466e65`) ; test de fermeture native adapté au nouveau panneau (`StartTicker` avant fermeture, propriété conservée), main `41a0eab3`. La première CI (run 38277275115) était rouge ; l'assertion wx observée provenait du nettoyage `atexit` après arrêt prématuré du test.
- **Preuves** : tests sans interface en local (AFAS 55, éphémérides 21, périodes et vacances 38) ; tests graphiques uniquement sur runner : **CI verte** main `41a0eab3` (run 38277917915, dont `test_dialogue_calcule_la_selection_reelle`, `test_real_panel…`, `test_settings_round_trip…`, `test_accueil_avec_bandeau_se_ferme_sans_violation_native` : ok) et wx `27ddf6e0` (run 38278402272) ; AFAS seul : wx `6157946a` (run 38276825770). Blobs identiques sur main/wx/qt.
- **RC2 restant à qualifier (non repris)** : envoi unitaire d'e-mails hors thread wx (`DLG_Mailer`, `4dccd871`, `a2b9d1c0`, `4fbcdbb4`) ; progression Connecthys au premier plan (`b6d078a5`, `813c7e4c`) ; reports conventions (#418) et lot #406 sur fichiers ayant évolué des deux côtés. **Exclus volontairement** (décision antérieure) : fondus `UTILS_Transitions` / boîte d'identification (`469bc970`, `5208fa86`). La branche RC2 et la PR #422 restent intactes.
- **Suite** : reprise RC2 restante par lots ; nouveau candidat Windows intégrant AFAS / Aujourd'hui / périodes (sur demande) ; recette GUI du paquet sur runner isolé.


## 30. Fin de la reprise RC2 : mailer, Connecthys, conventions, inventaire final — 12/10/2026

- **Consigne** : reprendre les derniers apports RC2 sans fusion globale, sans supprimer RC2, sans reconstruire `Noethys.exe` avant la fin de l'inventaire ; aucun test graphique sur le poste ; un runner Windows n'a pas de session graphique interactive garantie (point à qualifier avant d'y porter une recette GUI). Les tests wx en CI rapide créent des fenêtres sur le runner et passent ; cela ne vaut pas recette utilisateur du paquet.
- **Lots publiés** (blobs identiques main/wx/qt ; main `0f4896d4`, wx `8fcfb8e0`, qt `254e6373`) :
  - **Envoi unitaire d'e-mails non bloquant** (RC2 `4dccd871`, `a2b9d1c0`, `4fbcdbb4`) : main `68f62024`. Correctifs Vanilla préservés : renvoi proposé seulement après un échec avant acceptation ; pour Mailjet, succès via le compte rendu commun de main (« accepté par Mailjet pour envoi », remise non vérifiée) au lieu du libellé RC2. Test Mailjet ajouté (un seul envoi même si la fermeture échoue après acceptation).
  - **Progression Connecthys au premier plan** (`b6d078a5`, `813c7e4c`) : main `510a20d9`, fusion à trois voies sans conflit, sans Yield.
  - **Chargement de `models.py` Connecthys en paquet isolé** (partie Connecthys de #413) : main `a139b766`, correctif TLS `415ce93d` conservé.
  - **Conventions** : défaut « 20.00 € € par heure » reproduit sur main puis corrigé dans les modèles d'exemple : main `0f4896d4`.
- **Non repris, avec motif** : variante Word RC2 et `DialogFondu`/`UTILS_Transitions` (exclusions antérieures ; main a sa génération Word `a78c6581`) ; texte PMSL RC2 à `\n` littéraux (main correct) ; fondu de la boîte d'identification. **Décision métier en attente** : répéter les objets fixes du modèle (en-tête…) sur les pages 2+ d'une convention (RC2, sauf cadre `cadre_pages_suivantes`) ou non (main `a900c7f7`, conservé).
- **Inventaire final RC2** (part des lignes ajoutées par chaque commit déjà présente dans main) : #406 (dont SafeYield), QF #407/#408, attestations fiscales #410, listes wx #411, vacances #412, AFAS, Connecthys, mailer, périodes : **100 %**. Commits intermédiaires « Aujourd'hui » à 82-94 % : lignes réécrites ensuite par RC2 elle-même, version finale reprise. RC3 (`28c2294c`) n'ajoute que version, notes et CI de publication (PR #422). **Déductions** : aucun commit RC2 ; `CTRL_Synthese_deductions` déjà corrigé en Python 3 dans main. Les écarts sur déductions/attestations des branches `claude/noethys-windows-ci-audit-qy5m9t` et `design-form-density-standard` viennent d'un audit de robustesse basé sur `master` (écritures atomiques…) : hors RC2, EN ATTENTE de qualification séparée.
- **CI verte** : main `0f4896d4` (run 38280531242, tests mailer et Connecthys exécutés sur runner : ok), wx `8fcfb8e0` (run 38281403311). Tests sans interface en local : Connecthys 26, conventions 52, mailer statique.


## 31. Nettoyage des branches GitHub, premier lot autorisé (5 branches) — 12/10/2026

- **Autorisation de Franck** : jusqu'à 5 branches historiques ; ne pas toucher `main`, `wx`, `qt`, `master`, RC2, RC3 ni les branches des PR ouvertes (#422, #384, #369, #366, #355 : têtes et bases) ; aucune suppression risquée ; archive `git bundle` vérifiée hors dépôt avant chaque suppression.
- **Méthode** : pour chaque branche, apport propre = commits absents de toutes les références protégées (`main`, `wx`, `qt`, `master`, RC2, RC3) ; part des lignes encore présentes en tête de branche et absentes de ces références. PR de toutes états (325 PR examinées), branches qui les contiennent, worktrees.
- **Branches supprimées** (SHA relu juste avant, `git push origin --delete`, API GitHub : 404) :

| Branche | SHA | Apport propre | Motif |
|---|---|---|---|
| `design-form-density-standard` | `f96fa35865462500f12ad2caee98027e488f3955` | 1 commit, 0 ligne manquante | Document de la PR #112 (fermée) déjà dans main à l'identique |
| `docs/open-development-policy` | `d218e2980fbc7ab5b6577ec50c74931aae836c93` | 1 commit, 0 ligne manquante | `CONTRIBUTING.md` de la PR #102 (fermée) déjà dans main |
| `fix/rc2-pr385-compatible` | `ba67c6b9a5fc488ff8ba3c15d3cd6bd7826c12d8` | 13 commits, 1 ligne de commentaire | Lot #406 (PR #406 et #407 fermées) : 100 % dans main ; panneau remplacé par Aujourd'hui RC2 |
| `dev-db-docker` | `b7dc7c195022949626f8a7e9a55d2677e710d107` | 4 commits | PR #104 qualifiée et fermée (§ 26) : outillage repris durci dans main/wx/qt ; import générique exclu volontairement |
| `audit/vanilla-final-undefined-names` | `8ae3a36f939460a36b9d7b4f86cfa1147208e1b0` | 9 commits | Correctifs de code (synthèse des déductions, zoom chronologie, défauts runtime) présents ; seul manque un workflow d'audit `ruff` F821 déclenché uniquement sur cette branche |

- **Archives** : `C:\Users\Ordi\Documents\Sauvegardes-Noethys\branches-supprimees-20261012\` (hors dépôt), un bundle autonome par branche (`refs/remotes/origin/<branche>`), `git bundle verify` « is okay », restauration réelle dans un dépôt vide (SHA de tête exact, `fsck` sans erreur), empreintes dans `SHA256SUMS.txt` :
  - `audit_vanilla-final-undefined-names.bundle` `9061fc82ca8ca53b201aa92c99025c614e687f1ced6dd667e2747c16a6b43cf2`
  - `design-form-density-standard.bundle` `7a6b3bb29ed043fa0ec849ef6d8344660f4cceb9d1261cc051f37a81f2baaeb1`
  - `dev-db-docker.bundle` `d7e9a3054f12021a5eb003fa28c68626e499b309d7be6259e67579a2af11c4b9`
  - `docs_open-development-policy.bundle` `251219b0f1301e25af75f33199599486fec5c76e6f799daaee8c4d7992822d84`
  - `fix_rc2-pr385-compatible.bundle` `df75b105caf8722069298c9b2731a22189d70bdcf144e3a765daea9f1a322d9f`
  - Restauration : `git fetch <fichier.bundle> "+refs/remotes/origin/*:refs/heads/*"` puis `git push origin <branche>`.
- **Comptage** : 42 branches sur `origin` avant, **37 après**. Branches protégées et PR ouvertes revérifiées intactes après suppression.
- **Écartée pour risque** : `fix/noethys-sl-light-only` (verrouillage du thème clair dans `UTILS_Interface`, mécanisme différent de main, non qualifié). Les autres branches portent un apport propre non intégré (Noe-062/063, extensions, portable, prototype Qt, audits CI, `fix/rc2-network-stopgate-1`…) : conservées.


## 32. Finalisation du nettoyage Git : lots 2 à 5, reprises avant suppression, blocages — 12/10/2026

- **Consigne de Franck** : viser `main`, `wx`, `qt` seules ; lots de 5 branches au plus ; pour chaque branche, tête, commits propres, comparaison aux trois branches, PR, dépendances, worktrees ; réintégrer avec tests les apports utiles manquants ; archive `git bundle` vérifiée (SHA-256) puis `git push origin --delete` et contrôle GitHub ; présenter les blocages au lieu de supprimer. **Aucun build Windows** pendant le nettoyage (le run `38285851819`, lancé avant cette consigne, a été annulé : « completed cancelled »). Aucun test graphique sur le poste ; aucune base réelle.
- **Comptage** : 42 branches avant le lot 1 (§ 31), 37 au début de cette mission, **25 après**.

### Reprises dans main, wx et qt avant suppression (blobs identiques sur les trois branches)

| Lot | Source | main | wx | qt | Tests |
|---|---|---|---|---|---|
| Chemins portables (protection de migration de configuration, dans main depuis #160, sans test) | `fix/windows-installable-config` `31e6d85c` | `ec43b8cd` | propagé | propagé | `test_noe_041_portable_paths` adapté à main (`Temp/<pid>`, dossiers créés au démarrage) ; échoue si les deux gardes de `UTILS_Fichiers` sont retirées |
| `Config.json` illisible : restauration du `.bak` valide, sinon quarantaine `Config.json.corrupt-<horodatage>`, jamais d'écrasement silencieux | `agent/windows11-pyinstaller` `cb646889` | `a2015856` | propagé | propagé | `test_noethys_sl_config_quarantaine` (5) ; échouent sans le correctif |
| Gardes de robustesse (entité disparue : classe, location, type de pièce, activité, inscription scolaire, contrats, PSU, image interactive, inscription ; fiche famille sans compte payeur) | `claude/noethys-windows-ci-audit-qy5m9t` (10 commits) | `8e0ba9e2`…`f6a48805` | `24e53081` | `bd3eae39` | 9 contrats en CI rapide, 58 tests ; 35 échouent sans les correctifs. Devis : version de main conservée (sans ventilation) |
| Rail réseau 1 : ReportLab 5, destinataires non résolus signalés, reçu de règlement jugé sur `listeSucces`, demande de reçu Connecthys laissée en attente si l'e-mail échoue, historique des e-mails au fil de l'eau (apostrophe échappée, MessageID Mailjet), installation Connecthys bornée, `MAJ_bouton` sur le thread wx (#376) | `fix/rc2-network-stopgate-1` | `bbc6a29a`…`75f2e1a6` | `3ebe596d` | `44685a43` | 7 modules ajoutés à la CI rapide (`test_rail1_*`, `test_audit_reseau_emails`, `test_audit_reseau_connecthys`) ; sur l'ancien main : 5 modules en échec, 1 ignoré (fonction absente), l'installation Connecthys boucle sans fin (défaut corrigé) |
| Audit réseau RC2, contrat Connecthys, contre-qualification du rail 1, diagnostic Mailjet | idem | `db4b1476` | `0a11e66a` | `7742df06` | documentation (`docs/audit/`) |

- **Défaut critique trouvé** : `requirements.txt` n'épingle pas ReportLab ; avec ReportLab 5 (installé par le build), `UTILS_Impression_recu`, `UTILS_Impression_rappel`, `UTILS_Impression_cotisation` et `DLG_Releve_prestations` ne s'importaient plus (`ShowBoundaryValue` retiré). Corrigé et verrouillé par `test_rail1_reportlab5`.
- **Rail 1, conflit résolu** : le moteur Mailjet de main (statut HTTP 200/201 exigé, `mailjet_ids` robustes, compte rendu commun) est conservé ; seul l'appel `_NotifierSucces` est repris ; doublons de `_RetirerAnomalies`/`_AfficherCompteRendu` supprimés. Le faux Mailjet du test « Réessayer après timeout » reçoit un statut 200 (`2f5e2ca3`).
- **Isolation des tests** : `test_noe_041_portable_paths` laissait de faux `six`/`Utils` dans `sys.modules` et cassait les modules suivants de la recette rapide ; portée limitée au chargement (`75f2e1a6`).
- **Non repris, avec motif** : contexte TLS Connecthys et fichiers Nomadhys (main plus avancé : `FichierActionsFTPValide`, quarantaine numérotée, purge refusée sans identifiant) ; tests de caractérisation `test_audit_reseau_divers`/`secrets`/`nomadhys` de la branche (ils verrouillent des anomalies RC2, l'un exige `/bin/sh`, la version Nomadhys de main est plus récente) ; outils `scripts/audit_reseau` ; génération Word et `DialogFondu` (exclusions antérieures).
- **Recette** : suite rapide sans interface (liste de la CI moins les 5 modules GUI) : **424 tests OK** (4 ignorés) sur main, wx et qt. **CI rapide verte** : main `f6a48805` (run 38292118236), wx `24e53081` (38292143270), main `75f2e1a6` (38294947926), wx `3ebe596d` (38295315065). `qt` n'a pas de CI rapide sur push.

### Branches supprimées (lots 2 à 5)

SHA relu juste avant, archive vérifiée (`verify` « is okay », restauration dans un dépôt vide au SHA exact, `fsck` sans erreur), `git ls-remote` égal au SHA attendu, puis suppression et API GitHub « HTTP 404 ».

| Lot | Branche | SHA | Bundle SHA-256 | Motif |
|---|---|---|---|---|
| 2 | `agent/windows-ci-audit` | `7df621ea3a3034819142c633f5f4c9149c17fa68` | `066a2fbbbe58c81ce2c3580bba52a0ec3d50bc7fa4afc9910047c2c0728e6280` | code présent ; la seule variante de `UTILS_Procedures` désinscrivait toutes les inscriptions sur liste vide (main s'arrête) ; doc et script d'audit CI archivés |
| 2 | `poc/qt-theme-isole` | `cba459cd62cb2d71f43f89825287295d2ead6492` | `c6e4cedb82cea1fee625f0b59f8f3ab8f27dec262a20c83d958457d2960aa8d7` | **voir réserve ci-dessous** |
| 2 | `build/vanilla-windows-portable` | `4d5dda48269b8cc9313b3a6dc5a4442f0e5c7d2a` | `b1e74a11ef961efe41604aa8521cf5135bf5b25fc1cf07f935b7cb3c364b79a3` | périodes de saison antérieures, remplacées par la version RC2 de main (`9b0e6b71`) ; version et workflow de build dépassés |
| 2 | `chatgpt/noethys-convention-ui-activites-20260929` | `7cd062c3f634cff137f20af469ff7ded5e407e42` | `866b81caf082f9fb4cd9a713ecabe000fd95fe26465a9b452fcdb71a07cc434b` | même base que la précédente ; README/ROADMAP anciens |
| 2 | `fix/noethys-sl-aui-docking-minimize` | `aac763f24480e98608cfd2ccc918d87ef26594db` | `3cf3357ac661ddaea39dad0834025600b9878bbba2a685309b8d6e9fa5ca97b0` | gardes AUI présentes dans main (`NoethysSLAuiManager`) ; lignes restantes = versions antérieures de `Noethys.py` |
| 3 | `feat/noethys-sl-rc1-convention-finalise` | `f6cac3302a2ff3946f1f389071accec151a5b542` | `cfe6ca3b1041a1c539e71a6781568acff5c2b4efbb851e0fa028bc1be20c6280` | seul écart réel : `DialogFondu` (exclu) ; le reste diffère par l'encodage |
| 3 | `fix/noethys-sl-light-only` | `ccdfb82bcf1b1f5d4cd06a9d6382176cd91f6629` | `9635bb59617ab2c6dade49bf5891b38cb54984fa77a6fa929f050e3835b03ad2` | liste désactivée sur fond clair et neutralisation du thème Noir présentes dans main ; le verrouillage `GetApparence`/`EstSombre` vise le mode sombre de la lignée `master`, absent de main |
| 3 | `fix/noethys-sl-aui-guides-fantomes` | `7704ee753687159ee7173e33f86f538bc483c75c` | `2d19d267e7f3971dede516334d11a176b35b801ec60010e17156eeb6db389667` | correctif des guides de dockage présent dans main (`_FenetreEncoreVivante`, `OnCaptureLost`) |
| 4 | `fix/windows-installable-config` | `fbdebc8b6ef4ef906bfb8d23246be5eeb1820203` | `36f89be0e665f11981d95b5168ee19138eec44a02acb6ab26ed39ae94f89b255` | test repris (`ec43b8cd`) ; workflows, installateur et documents de la lignée `master` archivés |
| 4 | `agent/windows11-pyinstaller` | `f85f77266eec49ec02d6a24e0e130d463123b8d5` | `61ee7be158c52a48fac8ee43aa7f04ca575c1572b369e1e08d396d739ff65aed` | quarantaine de configuration reprise (`a2015856`) ; scripts de smoke/préflight PyInstaller archivés, non repris |
| 5 | `claude/noethys-windows-ci-audit-qy5m9t` | `3b847c6b2957a5d4a7d118ad7384f8bdc971baaf` | `dc4d1fc866bed7855bf1cdda4b3db22721d7c0bffa8f2d721efb40b2093fa080` | 10 correctifs repris ; restent les outils d'audit `2e3bc0a9`, `9c477166` (archivés) |
| 5 | `fix/rc2-network-stopgate-1` | `cf5f9fbe6ccd9472a061ceaf81ab6358effc00b3` | `d03ec7ef43e008e13fdb0187ab92eef06d74a57d0e5b53cd713227dc7f68fa80` | correctifs et documents repris (ci-dessus) ; aucune PR |

- **Archives** : `C:\Users\Ordi\Documents\Sauvegardes-Noethys\branches-supprimees-20261012\` et `SHA256SUMS.txt` (17 bundles avec ceux du § 31). Restauration : `git fetch <fichier.bundle> "+refs/remotes/origin/*:refs/heads/*"` puis `git push origin <branche>`.
- **Contrôle a posteriori des lots 2 à 5** (lignes de chaque tête absentes de main, wx, qt, `master` et RC2) : écarts limités aux versions dépassées, à l'encodage et à l'outillage archivé, **sauf `poc/qt-theme-isole`** : le prototype Qt (`noethys_qt/`, `tests_qt/`, `qt-prototype.yml`, `QT_MIGRATION_INVENTORY.md`, environ 11 000 lignes) n'existe sur aucune autre branche. Rien n'est perdu (archive vérifiée), mais ce travail unique n'a pas été réintégré : **décision demandée** (le verser dans `qt`, sans migration implicite, ou le laisser en archive).

### Branches restantes (25) et blocages

| Branche(s) | État | Blocage |
|---|---|---|
| `main`, `wx`, `qt` | canoniques | — |
| `master` (`b0be3c7e`) | branche par défaut GitHub, protégée (suppression interdite) | lignée produit divergente : 1 480 commits SL propres, environ 22 000 lignes de code absentes de main/wx/qt (Noe-062 structures, programmations, interventions, `UTILS_Migration_base`, `DLG_PMSL_Synchronisation`, interface Repens…) ; base des PR #369, #366, #355. **Décision métier** |
| `rc/noethys-sl-0.1.0-rc.2` (`91d9e625`) | entièrement qualifiée (§ 30) | base de la PR #422 |
| `rc/noethys-sl-0.1.0-rc.3` (`28c2294c`) | version, notes, CI de publication | PR #422 ouverte : **abandon motivé proposé** (contenu RC2 repris dans main/wx ; candidat construit depuis `wx`) |
| `feature/vanilla-conventions`, `feature/vanilla-entites-fonctions` | PR #384 | reportée par décision (conserver branche et PR, pas de changement de schéma) |
| `feature/session-attendance-consumer-2026-09-19` (#369), `noe-062-secure-secret-provider` (#355) | PR ouvertes vers `master` | chantiers réseau/pointage non qualifiés : hors publication |
| `docs/mkdocs-wiki` (#366) | documentation MkDocs vers `master` | intégrer à main (adaptation au corpus de main) ou abandonner |
| `feature/noe-062-*` (4), `fix/noe-062b-hardening`, `noe-062-programmation-occurrences`, `noe-062c-lieux-execution-seances`, `feature/noe-063-*` (3), `feature/extensions-registry` | fonctionnalités de la lignée `master` (schéma Noe-062) | dépendent du schéma de `master` : **décision métier** avec `master` |
| `refactor/ui-list-tools-repens` | interface Repens (lignée `master`) | idem |
| `noe-041-portable-mode` | ZIP livré avec dossier `Portable` | **décision de packaging** (le ZIP de main n'est pas portable par défaut) |
| `fix/vanilla-no-black` | correctifs de fond noir déjà dans main | reste l'affichage du logo de l'organisateur sur l'accueil : **décision fonctionnelle** |

- **Branche par défaut** : bascule `master` → `main` **non effectuée** (`master` n'est pas supprimée). Points qualifiés : `master` est protégée (pas de suppression ni de force-push) alors que `main`, `wx`, `qt` ne le sont pas (protection recommandée) ; le workflow planifié « Entretien historique GitHub Actions » n'existe que sur `master` et purge les anciens runs au-delà de 100 : il cessera de tourner à la bascule (ce qui préserve les runs cités comme preuves) ; les PR ouvertes vers `master` ne sont pas modifiées par la bascule.
- **Prochaine étape** : arbitrages de Franck sur les blocages ci-dessus ; puis build Windows candidat sur demande.


## 33. Fin du nettoyage Git : trois branches, reprises de master, bascule sur main — 12-13/10/2026

- **Arbitrages de Franck (12/10/2026)** : objectif `main`, `wx`, `qt` sans perte ; prototype Qt à réintégrer isolé dans `qt` ; #422 fermée après archivage ; #384 reportée avec issue de reprise ; #369 et #355 archivées sans intégration ; #366 (MkDocs) reprise dans `main` ; mode portable sans nouveau packaging ; logo organisateur repris avec test ; master inventorié par ensembles (A corriger, B intégrer si qualifié, C archiver et reporter, D abandon justifié), jamais supprimé en bloc ; protections, workflows, bascule de la branche par défaut, seconde copie des archives. Aucun build Windows, aucune automatisation graphique sur le poste.
- **Comptage** : 25 branches au début de ce lot, **3 à la fin** (`main`, `wx`, `qt`). `git ls-remote --heads origin` (13/10/2026) : `main` `b32ec308`, `wx` `8a7adbc0`, `qt` `d24d0cf1`.

### Pull requests

| PR | Décision | Traçabilité |
|---|---|---|
| #422 (RC3 → RC2) | fermée | contenu RC2 dans main/wx ; tag `noethys-sl-0.1.0-rc.3` et pré-release conservés ; bundles RC2/RC3 |
| #384 (fonctions des individus dans les entités) | fermée, **reportée** | issue #423 ; bundles `feature/vanilla-entites-fonctions`, `feature/vanilla-conventions` ; `refs/pull/384/head` |
| #369 (pointage `session-attendance/1`), #355 (`SecretProvider`) | fermées, **reportées** (réseau, non qualifiées) | issue #424 ; bundles ; `refs/pull/369/head`, `refs/pull/355/head` |
| #366 (MkDocs) | fermée, **reprise** | main `e0a82d71`, `16aa6a9f` ; `mkdocs build --strict` vert en CI ; publication Pages seulement si `DOCS_PAGES_ENABLED=true` (issue #365 ouverte) |

Aucune pull request ouverte.

### Reprises dans les branches canoniques (blobs identiques main/wx/qt sauf mention)

- **Logo de l'organisateur sur l'accueil** (de `fix/vanilla-no-black`) : main `47e20b24` ; transparence conservée, chargé après ouverture d'un fichier, retiré à la fermeture ; `test_accueil_logo_organisateur` (11 tests, 10 échouent sans le correctif).
- **Mode portable** : packaging inchangé (ZIP et Setup) ; activation documentée dans `docs/exploitation/MODE_PORTABLE.md` (main `16aa6a9f`).
- **Prototype Qt** (de `poc/qt-theme-isole`) : **qt uniquement**, `55c35a0b` ; paquet `noethys_qt/` isolé, non activé, absent du packaging, `requirements-qt.txt` optionnel ; **garde ajoutée** : sans `--sqlite`, la base configurée (production possible) n'est ouverte que si `NOETHYS_QT_BASE_CONFIGUREE=1` (`test_garde_base_configuree`) ; workflow `qt-prototype.yml` sur `qt` : **102 tests OK** hors écran (run 38311587090). Reste : recette utilisateur en VM, revue des écritures, décision produit (`docs/qt/README.md`).
- **26 corrections de master** (A01-A19, A21, A23-A25, A27, A28), avec tests : SQL strict (règlements, Quadra/Cerig), frontières texte/binaire et encodages des exports PES/Corail/JVS/Magnus/prélèvements/exports internes, export NoethysWeb en échec, données absentes, imports individus/vacances/badgeage, TIPI, ventilation stricte des paiements en ligne, titulaires multiples, restrictions utilisateur, filtres de tarification, archivage, badgeage (questionnaire, événement), filiation, extensions confinées, hébergement Connecthys inconnu, répertoire de données, `nomFichier` vide, communes homonymes. Détail et SHA : `docs/dev/INVENTAIRE_MASTER.md`. Outils `scripts/audit_branch_assignment_gaps.py` et `scripts/audit_source_coverage.py` repris (requis par les tests de contrat). Une partie (11 correctifs) a été réalisée par un agent dans un worktree isolé puis relue avant intégration ; `chardet` reste facultatif (`FonctionsPerso.DecoderTexteFichier`) ; `test_audit_reseau_emails` inversé pour EMAIL-12 corrigé.
- **Non repris, avec motif** : A20 `isAlive` (déjà couvert par l'alias de `UTILS_Adaptations` ; un commit erroné en ce sens a été retiré avant publication), gardes IndexError partielles de `ce979bbd` (non vérifiées) ; A22 `ast.literal_eval` (EN ATTENTE : contrôle sur copie de base) ; A26 double-clic de grille (EN ATTENTE : recette Windows isolée). Fonctionnalités B (écritures transactionnelles, évaluateur d'expressions, commande de repas automatique, recherche tolérante, chargement différé) et ensembles C/D : reportés, listés dans `docs/dev/FONCTIONNALITES_REPORTEES.md`.
- **Recette** : suite rapide sans interface **516 tests OK** (4 ignorés) sur main, wx et qt ; CI rapide verte (main `a60e805b` run 38314409244, wx `d4d4aaae` run 38314517665) ; MkDocs vert (main `b32ec308` run 38314727754). Chaque test repris ou écrit a été vérifié en échec sans son correctif.

### GitHub

- **Protections** : `main`, `wx`, `qt` interdisent suppression et force-push (aucune revue ni contrôle obligatoire : les fast-forward directs restent possibles).
- **Workflows** : `noethys-sl-windows`, `vanilla-r2`, `vanilla-release`, `vanilla-windows-package` ne se lancent plus que sur demande (`workflow_dispatch`) ; leurs déclencheurs visaient des branches supprimées (main `4a571a5f`). `docs.yml` construit sur `main`. Le workflow planifié « Entretien historique GitHub Actions » n'existait que sur `master` : il ne s'exécute plus.
- **Branche par défaut** : `main` (13/10/2026, API : `default_branch=main`).
- **master** : archivé (`master.bundle`, SHA-256 `c0e925a900b5da94db1a36b7d5475d5c86016e6d916b8cbf273512d5e6ba865e`, deux copies), protection retirée puis branche supprimée ; absente de `git ls-remote` ensuite. La branche locale `master` du poste n'a pas été touchée.

### Archives

- 39 bundles vérifiés (verify, restauration au SHA exact, `fsck`) dans `C:\Users\Ordi\Documents\Sauvegardes-Noethys\branches-supprimees-20261012\` et **seconde copie** `C:\Users\Ordi\OneDrive\Sauvegardes-Noethys\branches-supprimees-20261012\` (39/39 empreintes contrôlées par `sha256sum -c`). Un bundle n'étant pas reproductible octet pour octet, une archive déjà documentée n'est jamais régénérée.
- Branches supprimées dans ce lot (SHA ; bundle SHA-256) :
  - `rc/noethys-sl-0.1.0-rc.3` `28c2294c` ; `ec370a4d3cf94b31c748e0588c32e7db4f435c836aa9cf2510ef734cb0d1655a`
  - `rc/noethys-sl-0.1.0-rc.2` `91d9e625` ; `205d3fa38e0bbddad6c22d803217443257e09df1c7c76b02260d5e9b0f800465`
  - `feature/vanilla-entites-fonctions` `4e2c615b` ; `8c95224b15a047653e4f861ee6ea25917c3d6e4b009d53e2cd104c38aa191fda`
  - `feature/vanilla-conventions` `c2c3e87a` ; `aac52b7f836e4289cad894961da72befadfea90508543623a2258d54e68fa94f`
  - `feature/session-attendance-consumer-2026-09-19` `74410a3e` ; `ea7fc45768e06a107fb4385f2a80dcd9f8448a8eb2c54db8f4df60a838aa7d20`
  - `noe-062-secure-secret-provider` `04f7886c` ; `4f81b7bdf1a4fbe2b475cc933dcb7e2ba9a45e2f2b754d2f829692eea816c9d4`
  - `docs/mkdocs-wiki` `e43492b1` ; `77606fd02f0c1589e098ee9100e76383c21f70aa49501381cffde2b62a65b15c`
  - `noe-041-portable-mode` `3cf6cbfe` ; `4754adb1b6f233e738556bc9fca411d5c18c4050d443a4ab3491419d73c6a0dc`
  - `fix/vanilla-no-black` `7c39f16a` ; `b109f732c4635182edac3eb9dceb802a53498429c8138abffaebb06a117c4ca7`
  - `feature/extensions-registry` `9174ba32` ; `686c3f20865da672884a3fc62ad1bd9b780bd7ed5fad43dcd01cddb52ed30fa8`
  - `feature/noe-062-conventions` `f85fd51e` ; `724083acfe98cdee7cc6704404ba0b68b9bbe7bb180b3cd0bb7260b906bd6574`
  - `feature/noe-062-mises-a-disposition` `c69f3c80` ; `70deb97706eee358056f4da1975df0ece7fe768f6c66847fc73911b983a066fb`
  - `feature/noe-062b-groupes-structures` `203fff34` ; `9b380db77f7caa5c87a2ee5657f048e601b821e3b15763aa0abc3235258235bb`
  - `feature/noe-062b-roles-contacts` `177b4c3d` ; `46cd2fa2d34afaf433f86b2e5b0cda85ae620b0734e8647b48877e5ffe3fc273`
  - `feature/noe-063-portail-consolide` `55b2b129` ; `76d9c5c978fbd52003df1302d9a8a60f8229e91c1950b74fd6779bc9ddc18ca1`
  - `feature/noe-063b-rss-atom-connecthys` `8f84f5ed` ; `770abe162e23253e3cfe855b15c3bc846978869905a4d8fdd6372200ae93ae78`
  - `feature/noe-063d-tarifs-ui` `20d5b15c` ; `0965604f9596cf407227bc1f45dc5e6b5230128023e83a2e19ade6c7c471a722`
  - `fix/noe-062b-hardening` `752645c5` ; `4f7463bfa4413d22a55840fb6f3f21bd61c5bb818b2c29a09b4521d41ed00209`
  - `noe-062-programmation-occurrences` `88904fc7` ; `507493a94ed5a4d385755a9659c53b45e99fcbc93028495c2d6b10250f059988`
  - `noe-062c-lieux-execution-seances` `be059ccd` ; `206af2ce4770039b2a32a22f387ea1e2363bb28d98fb652358cf18ac8c886f95`
  - `refactor/ui-list-tools-repens` `52ed49bf` ; `62cda39a542ecc94fcbff2004b73f4ff5211b1b47475840a88f4ef1d3a9c83cc`
  - `master` `b0be3c7e` ; `c0e925a900b5da94db1a36b7d5475d5c86016e6d916b8cbf273512d5e6ba865e`
- Worktree WIP `Noethys-RC2-clean` (HEAD détachée `8b3789d9`, commit pointé par le tag `noethys-sl-0.1.0-rc.2`) : non touché ; son commit reste dans le dépôt local et dans le tag.

### Prochaine étape

Reprise de la fabrication du candidat Vanilla depuis `wx`, **sur demande de Franck** (build Windows non lancé). Restent EN ATTENTE : A22, A26, gardes partielles de A20, recette utilisateur du prototype Qt.


## Incident P1 du 15/10/2026 — adhésions futures RC7 (issue #426)

- Incident observé en exploitation : une réservation du 06/01/2027 déclenche une cotisation du 06/01/2027 au 06/01/2028 et une prestation datée du 01/10/2026, potentiellement facturable dès octobre. Cause : `CTRL_Grille.Sauvegarde` appelle la réconciliation sans borne supérieure de participation.
- **Mitigation P1, pas de refonte métier** : `UTILS_Adhesions.AUTO_CREATION_SUSPENDUE=True` ; dans `CTRL_Grille.Sauvegarde`, sortie après `DB.Commit()/DB.Close()` avant `ReconcilierSansEchec`. Enregistrement des consommations inchangé ; création automatique d'adhésion suspendue. Aucune suppression de données réelles.
- Code commun (blobs identiques, pas de branche nouvelle) : `main` commit `a106ac0195d9175a7a4fd5d8faa7d9c7b0233617` (CI rapide [run 38715042777](https://github.com/fr4nck/Noethys-SL/actions/runs/38715042777) **SUCCESS**), `wx` `51986a14a6357cf0d024df114704d2f4862341ae`, `qt` `37b75f7e8c11be73fce26a8317f48536a0c0f9a0` ; test de non-régression ajouté `test_coupe_circuit_p1_ne_cree_pas_d_adhesion_pendant_la_sauvegarde`.
- **Candidat Windows RC7.1** : `wx` `8cd839a6b011a6ba68feff3af73537bd4d8aabb3` ; `Identite.PRODUCT_VERSION=0.1.0-rc.7.1`, version interne/protocole Noethys inchangés. CI rapide [run 38715321824](https://github.com/fr4nck/Noethys-SL/actions/runs/38715321824) **SUCCESS**. Build Windows [run 38715321802](https://github.com/fr4nck/Noethys-SL/actions/runs/38715321802) **SUCCESS** : syntaxe, contrats critiques, PyInstaller, clients MySQL embarqués et restauration locale isolée, smoke binaire + ZIP portable, Setup Inno, SHA256SUMS. Artefact `Noethys-SL-0.1.0-rc.7.1-Windows-candidat` (ID 11962707963, rétention 30 jours). Pas de release publiée dans ce lot.
- **Barrière réelle de déploiement** : le succès CI n'atteste pas une installation en production. Les postes RC7 existants demeurent exposés tant que RC7.1 n'y est pas installé ; les cotisations déjà créées demeurent. Avant déploiement : sauvegarde et contrôle sur poste pilote ; déployer ensuite sur **tous les postes**. Éviter la facturation de cotisations suspectes jusqu'à audit.
- **Restant** : audit en lecture seule de `cotisations` marquées `[adhesion-auto]`, `prestations.IDfacture`, `ventilation`, dates de participation ; annulations contrôlées sur approbation ; nouvelle règle clôture mensuelle ou facture anticipée après participation, avec annulations et tests de qualification. Les tests Qt spécifiques restent non vérifiés dans ce lot.
- Suivi canonique : [issue #426](https://github.com/fr4nck/Noethys-SL/issues/426). Ni production, ni Connecthys, ni tag RC7 modifiés.


## Incident P1 du 15/10/2026 — édition PDF et transfert Email des factures wx (#428)

- **Signalement terrain RC7.1** : les fenêtres « Impression de factures » et « Envoi de factures par Email » affichent une facture cochée mais cliquer sur « Aperçu » ou « Transférer vers l'éditeur d'Emails » n'a aucun effet visible. Capture : sous « Mémorisation », la propriété porte le libellé technique `repertoire_copie`.
- **Cause code confirmée** : dans `noethys/Ctrl/CTRL_Factures_options.py`, `CTRL_Parametres.Remplissage` utilisait `wxpg.DirProperty(name=_(u"Répertoire pour copie unique"), label="repertoire_copie", value="")` spécifiquement sous wxPython Phoenix. Or `GetPropertyValues` indexe par `name`, et `DLG_Factures_impression.OnBoutonApercu` comme `DLG_Factures_email.OnBoutonOk` consultent `dictOptions["repertoire_copie"]`. Cause cohérente avec un `KeyError` non intercepté ; traceback réel du poste non obtenu. Correction unifiée : `label=_(...), name="repertoire_copie"`.
- **Commits** : `main` [cc371e2](https://github.com/fr4nck/Noethys-SL/commit/cc371e286972fbc43b8c0dfb5e6c2659f95c3fa8) ; `wx` [b7f85e9](https://github.com/fr4nck/Noethys-SL/commit/b7f85e9afbdf148999cbec8c9afa90bf8a8df836) ; `qt` [82c9e1c](https://github.com/fr4nck/Noethys-SL/commit/82c9e1cbf83be89f58128d9795dfaa0add0e9c5e). Fichier partagé identique ; pas de nouvelle branche ni d'écrasement.
- **Non-régression** : `tests/test_noethys_sl_facture_export_options.py` crée une vraie PropertyGrid wx isolée de DB et teste sa clé `repertoire_copie`, son libellé, les deux boutons avec facturation simulée (aucun PDF ni email réel). [CI main 38719031345](https://github.com/fr4nck/Noethys-SL/actions/runs/38719031345) **SUCCESS** ; [CI wx 38719333474](https://github.com/fr4nck/Noethys-SL/actions/runs/38719333474) **SUCCESS**.
- **Candidat Windows RC7.2** : `wx` [ffd28de](https://github.com/fr4nck/Noethys-SL/commit/ffd28de9f43a591eb2e00b4a0ee32f2ccdeb4ee0). Version publique `0.1.0-rc.7.2`, version interne Noethys et protocole Connecthys inchangés, conserve le coupe-circuit d'adhésion RC7.1. [Build 38719333519](https://github.com/fr4nck/Noethys-SL/actions/runs/38719333519) **SUCCESS** : suite critique dont PDF synthétique, PyInstaller, MySQL jetable sauvegarde/restauration, smoke exécutable/portable, Setup Inno, SHA256SUMS. Artefact `Noethys-SL-0.1.0-rc.7.2-Windows-candidat` (ID 11963754061, expire 14/11/2026) contenant Setup, ZIP portable et empreintes ; aucune release publiée.
- **Barrière utilisateur** : *non installée / non vérifiée sur poste de production* au terme de cette intervention ; tester d'abord l'aperçu d'une facture existante, puis l'ouverture du Mailer et la pièce jointe sans envoyer de message. Ne jamais régénérer une facture pour contourner le défaut. Aucun changement de donnée réseau effectué. Tests Qt spécifiques non exécutés.
- **Suite** : fermer [l'issue #428](https://github.com/fr4nck/Noethys-SL/issues/428) après recette réelle, puis reprendre [#427](https://github.com/fr4nck/Noethys-SL/issues/427) sur les lenteurs SQL et [#426](https://github.com/fr4nck/Noethys-SL/issues/426) sur la règle d'adhésions à clôture/facturation anticipée.


## Performance consommations — validation OK, lot lecture seule / accès évités (#427)

- **Terrain 15/10/2026 :** opérateurs local et distant trouvent la validation « OK » lente après conversion de liste d'attente, sans Connecthys. Aucun temps SQL réel encore relevé. RC7.1 suspend l'adhésion auto, RC7.2 corrige le PDF/email, pas la lenteur.
- **Code partagé** : `noethys/Ctrl/CTRL_Grille.py` n'appelle plus `GetProchainID("prestations")` sans nouvelle prestation et n'ouvre plus de DB dans `SauvegardeTransports` sans création/modification/suppression. Les droits, historiques, tarifications et écritures réelles sont inchangés. Tests de contrat et mocks dans `tests/test_noethys_sl_performance_grille.py` ; cas transports vides, inchangés, suppression, modification, ajout.
- **Commits :** `main` `b3ae046dcf35c357d452621da44a833e78fdce4e`, `wx` `3ad906e3b812dfdbed1d916f7f9367b948cf94b4`, `qt` `14ae47ee49e45eaf799e057021fe6dc121b6d9bb`. CI premier lot wx [#38723483094](https://github.com/fr4nck/Noethys-SL/actions/runs/38723483094) **SUCCESS**.
- **Profilage opt-in** : `noethys/Utils/UTILS_Profilage_consos.py`, hooks des boutons OK `DLG_Grille.py` et `DLG_Gestionnaire_conso.py`. Inactif par défaut, activation uniquement en lançant l'application avec `NOETHYS_SL_PROFILE_CONSOS=1`. Journal JSONL local `%LOCALAPPDATA%\\Noethys-SL\\Diagnostics\\performance-consommations.jsonl` : durée totale, phases `consommations/transports/parametres/fermeture`, 25 fonctions Python les plus longues, compteurs ; jamais SQL, arguments, ID, noms, hôtes, données familiales ni traceback. Erreur de journal non bloquante, taille limitée avec rotation. Test `tests/test_noethys_sl_profilage_conso.py` vérifie opt-in, zéro écriture par défaut, anonymisation de l'exception et couverture des deux handlers.
- **Commits instrumentation :** `main` `f04e68a0c3dd8e8d2e52946d5bdbd98b63c3cebe`, `wx` `23a49c7d129d7ce7c6167437c6fb939eaa835e53`, `qt` `9f27a1378ce28c96f79e8ff5d080e2f3d77b45c1`. CI [main #38724108383](https://github.com/fr4nck/Noethys-SL/actions/runs/38724108383), [wx #38724128232](https://github.com/fr4nck/Noethys-SL/actions/runs/38724128232) : vérifier conclusion avant release. Qt runtime non testé.
- **Stop-gate** : aucune de ces modifications n'est dans le Setup **RC7.2** (build `ffd28de`). Ne pas annoncer un gain terrain ni une amélioration effective sur les postes installés. Aucun build Windows publié, aucune migration, aucune base production touchée. Mesurer ensuite la différence entre temps total, appels `GestionDB`/MySQL et rafraîchissement UI ; benchs sur DB jetables avant toute optimisation lourde des `UPDATE` et commits. Suivi [issue #427](https://github.com/fr4nck/Noethys-SL/issues/427).

## Changelog originel : notes récentes en tête — 15/10/2026

- **Signalement utilisateur :** `noethys/Versions.txt` (menu À propos → Notes de versions) présentait encore une section 1.3.4.4 d'octobre, sans les nouveautés des RC récentes. Convention d'origine rétablie pour la branche `wx` : sections les plus récentes en premier, `Version Noethys SL ... (JJ/MM/AAAA) :` puis une seule nouveauté par ligne commençant par `- `. Entrées historiques depuis `Version 1.3.4.4 (01/10/2026)` conservées bit pour bit (blob Git originel `5b13501bdc51ad5c08aced106d4db0f66e809bf8`).
- **Notes `wx` :** RC7.2 (édition PDF et transfert éditeur d'emails), RC7.1 (suspension temporaire des adhésions automatiques), RC7 (notes reprises de la [release publiée](https://github.com/fr4nck/Noethys-SL/releases/tag/noethys-sl-0.1.0-rc.7)). Aucune optimisation performance issue #427 annoncée comme livrée dans la RC7.2 : ces changements restent uniquement dans le code de développement.
- **Sécurité de compatibilité :** la version interne `1.3.4.4` est encore extraite par `FonctionsPerso.GetVersionLogiciel()`, désormais par recherche d'un entête historique strictement numérique `Version X.X.X.X (date) :` plutôt que première ligne physique. `VERSION_APPLICATION` continue donc de régir sans rupture les migrations/Connecthys ; `Identite.PRODUCT_VERSION` demeure séparée. Aucun schéma de base modifié.
- **Régression :** nouveau `tests/test_noethys_sl_changelog.py` (dernier titre public en tête, tiret par nouveauté, historique original inchangé, version interne), et renforcement de `test_vanilla_identite_noethys_sl.py` pour vérifier explicitement `GetVersionLogiciel() == 1.3.4.4` même quand les notes publiques précèdent l'historique. Ajout des deux tests à la CI rapide `main`/`wx`.
- **Branches et commits :** `main` [2e30b0e](https://github.com/fr4nck/Noethys-SL/commit/2e30b0e454db89e7e2bde004722ab5b114da00c6) (lecteur/contrats), `wx` [84d9f96](https://github.com/fr4nck/Noethys-SL/commit/84d9f96e4fd71009471f7bf26c2c1a693816283c) (notes publiques RC7.2/RC7.1/RC7 et lecteur/contrats), `qt` [cd3c938](https://github.com/fr4nck/Noethys-SL/commit/cd3c938af6012e8427ef8e5aeb1ea5b9f599fe1a) (lecteur/contrats, pas de nouvelles notes RC7.2 puisque la version publique Qt est différente). Aucun force-push, aucune branche supplémentaire.
- **CI :** [main #38735832105](https://github.com/fr4nck/Noethys-SL/actions/runs/38735832105) et [wx #38735877115](https://github.com/fr4nck/Noethys-SL/actions/runs/38735877115) : vérifier leur conclusion définitive avant de qualifier les tests. Syntaxe réussie initialement ; étape Windows en cours au moment de la rédaction.
- **Limite de livraison :** ces nouveaux textes sont dans les branches source, **pas dans le candidat Windows RC7.2** déjà fabriqué (`ffd28de`). Pas de nouveau paquet, de changement de production ni de migration. Prochain build : vérifier menu Notes de versions et version affichée ; recette Windows sur poste pilote avant annonce de disponibilité.
