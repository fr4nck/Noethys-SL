# Reprise du chantier Noethys-SL — état au 27/10/2026

## C2 — calendrier des consommations Qt (27/10/2026)

C2 sur qt, base e65a590 : synthèse SQL mensuelle complète, activité, sélection d'un jour, consultation des événements liés, maintien du filtre annuel C1 et du plafond de 300 résultats. Aucun code métier commun modifié, aucune migration de schéma ni base réelle. Tests SQLite fictifs et Qt hors écran ajoutés ; **CI Windows SUCCESS** sur 5914c75 (run 40508025972) : compilation PASS, 151 tests / 0 échec. UI Windows en situation réelle, DPI, MySQL et publication restent EN ATTENTE. Consultez docs/dev/QT_CONSOMMATIONS_LOT2.md. Main f6f5ccd, wx a24e1dd : non modifiées, divergence interbranches toujours sous STOP-GATE pour publication. Prochaine étape : recette graphique Windows, contrôles MySQL réels sur environnement jetable, puis C3 transactionnel séparé.


## Lot Qt C1 — consultation des consommations (27/10/2026)

Première surface native en lecture seule, sans synchronisation globale depuis main/wx. Six états historiques + états inconnus/vides, filtres cliquables, recherche SQL paramétrée, limite 300, worker Qt, test SQLite fictif et contrôles hors écran. Voir [contrat et limites](QT_CONSOMMATIONS_LOT1.md). La CI Windows du code C1 e65a590 (run 40505427492) a réussi : 129 tests, 0 échec. Aucune validation de production, de MySQL réel, de packaging ni de facture ; recette humaine EN ATTENTE.


## P1 #426 — audit RC7 renforcé et préparation de recette RC8.1 (21/10/2026)

- Correctif limité à l'inventaire : `UTILS_Audit_cotisations`, lecteur autonome explicite SQLite/MySQL local, export HTML/JSON/CSV et fiche comptable vide. Aucune régularisation, aucun appel de création financière, aucune donnée PMSL.
- Trois lacunes reproduites sur l'audit publié : prestation absente hors filtre temporel omise ; prestation présente sans date confondue avec une absence ; date de fin invalide interrompant le rapport.
- Contrôles : facture référencée vs pièce présente, ventilations détaillées même à somme nulle, règlements référencés, dates invalides, liens partagés et incohérences de payeur. Totaux dédupliqués par prestation ; validité future n'atteste pas de présence réelle.
- Qualification locale Linux : **31 PASS / 0 FAIL / 0 SKIP**, tables SQLite du schéma canonique ; interdiction des écritures, empreintes avant/après, exports et erreurs SQL couverts. Compilation des fichiers modifiés PASS.
- Exemple fictif : 9 automatiques examinées, 8 signalées, 6 prestations distinctes, 45,00 EUR ; aucune donnée PMSL. Guide et commandes : `docs/diagnostics/AUDIT_COTISATIONS_RC7_RECETTE_RC81.md`.
- Synchronisation ciblée préparée depuis main `0500ff0`, wx `f48cf15`, qt `7e9745a` : les blobs initiaux du service et de la fixture adhésions sont identiques. Les workflows et l'historique de cette passation sont conservés proprement à chaque branche, sans merge global.
- Matrice de qualification du contenu commun : main / wx / qt = correctif d'audit et tests communs présents dans ce lot, qualification Linux sur contenu commun PASS ; runtime Windows et UI Qt **EN ATTENTE**. Le test est ajouté aux futures CI rapides main/wx ; le workflow ne déclenche pas automatiquement sur qt.
- **CI distante non relancée** (`[skip ci]`) : aucun téléchargement/installation ni build de paquet déclenché dans ce lot. Les 465 tests Windows et 11 tests MySQL du 19/10 restent des preuves de l'ancienne release, pas du nouvel audit. Aucun pilote MySQL dans le conteneur ; nouveau lecteur MySQL non qualifié sur serveur réel.
- Recherche des sources actualisées : #426 et son seul commentaire restent datés du 19/10 ; release RC8.1 et passation wx récupérées, recherche d'issues actualisées et documentaire sans attestation terrain plus récente trouvée. Cela ne démontre pas une absence d'opérations locales.
- **Limites d'exploitation maintenues** : copie isolée identifiée indispensable, recette wx sur copie B jetable, validation comptable nominative. Ne pas modifier les tags/binaires RC7/RC8.1 ni fermer #426 ; aucun poste, production, profil utilisateur ou Connecthys modifié.


## RC8 — Recette fictive des repas, PDF et email (19/10/2026)

**Statut** : développement poursuivi, **RC8 NON PUBLIEE**. Aucune migration SQL, sauvegarde PMSL, accès à la production, téléchargement de paquet, envoi SMTP ou construction d'installateur n'a été effectué dans ce lot.

**Points démontrés :**
- `test_noethys_sl_repas_sqlite_recette` : base SQLite **en mémoire**, données entièrement fictives, question individuelle « sans porc » explicite ; contrôle sur réservations / présences en doublon, absences, même unité dans plusieurs groupes, réponses non renseignées, questions famille refusées et absence d'écriture SQL.
- `test_noethys_sl_repas_pdf_mail_recette` : vrai PDF temporaire produit avec ReportLab ; récapitulatif par date/site/service, enfants moins de 6 ans, enfants 6 ans et plus, détail repas adultes animation/direction/autres, total **6 ans et plus adultes compris**, « dont sans porc » et total général. L'écran corrige les valeurs avant émission ; le PDF refuse une validation absente ou périmée.
- Préparation du brouillon d'email via le mécanisme `EnvoiEmailFamille` avec **mailer simulé** : même PDF, mêmes champs de fusion `{REPAS_TOTAL}`, `{REPAS_6_PLUS}`, `{REPAS_ADULTES}`, `{REPAS_SANS_PORC}`. Aucun SMTP ni destinataire réel.
- Si une préférence alimentaire manque, un avertissement et une confirmation explicite s'affichent avant l'émission.
- Rendu A4 de contrôle effectué sur un tableau synthétique sans débordement visible (contrôle visuel **hors application**, distinct de la recette utilisateur).

**Qualification traçable** :
- `main` code [9f6d3e1](https://github.com/fr4nck/Noethys-SL/commit/9f6d3e12026b6f108e09c305fa74f83178daa396) : [CI Windows 39238759686](https://github.com/fr4nck/Noethys-SL/actions/runs/39238759686), **765 tests / 0 FAIL / 6 SKIP**, PASS.
- `wx` report ciblé [199ff2a](https://github.com/fr4nck/Noethys-SL/commit/199ff2a88c8e6b512651508bd2a8507957af3574) : [CI Windows 39239363460](https://github.com/fr4nck/Noethys-SL/actions/runs/39239363460), **789 tests / 0 FAIL / 10 SKIP**, PASS.
- `qt` report ciblé [522236f](https://github.com/fr4nck/Noethys-SL/commit/522236ffe06050878bd38735f051824ca69c81f0) : mêmes blobs métier, **Qt natif non qualifié**.
- Correspondance SHA des fichiers partagés constatée pour le contrôleur des commandes, la prévalidation PDF/email, le dialogue de contrôle et les deux tests de recette ; aucune fusion globale et aucune création de branche.

**Barrières restantes** : une recette avec utilisateur sur poste Windows (base fictive, modèles et bon du restaurateur) ; gestion des préférences modifiées dans le temps **sans historique natif**, direction multisite partagée entre commandes distinctes **sans déduplication garantie**, questions/choix à configurer manuellement, et validation des autres P1 avant tout candidat RC8.

Voir `docs/metier/REPAS_RC8_VALIDATION.md` et le ticket #430.

## RC8 — repas sans porc et contrôle avant émission (19/10/2026)

- **Décision** : développer avant RC8 ; aucun tag, release, installateur, migration SQL, envoi d'email ni accès à la production.
- **Lot #430** : réponses alimentaires individuelles explicites via `questionnaire_questions`, `questionnaire_choix`, `questionnaire_reponses` ; aucun texte médical interprété. Les réponses ne sont pas historisées : impossible de rétablir le choix à une date passée sans autre stockage.
- **Décompte** : dates / site / service, effectifs enfants séparés à six ans, suggestions « dont sans porc » exclues des totaux additifs ; repas des animateurs, direction, autres adultes saisis séparément, puis tous regroupés dans 6 ans et plus. Absence de preuve d'absence de doublon entre **commandes multisites indépendantes**.
- **UI** : `DLG_Controle_repas.py` avant boutons PDF/email ; valeurs modifiables, recalcul de totaux, annulation empêche l'émission ; modèles typés invalides bloqués. Anciens modèles non typés conservent un avertissement et une confirmation explicite pour l'ancien flux. Aucun mail automatique envoyé.
- **Bilan source** : `main` lot métier validé au commit [7da9785](https://github.com/fr4nck/Noethys-SL/commit/7da97850f5d78b431e352b420e4872e08603f436), `wx` [5abdee4](https://github.com/fr4nck/Noethys-SL/commit/5abdee44f8cc0869970705a37b8b2cf5171c3762), `qt` [7dc1557](https://github.com/fr4nck/Noethys-SL/commit/7dc1557922709210bcf5317a1ff71ebdb4eafb5b). Fichiers métier/tests communs reportés par blobs SHA, sans merge global ; workflows de chaque branche conservés.
- **Tests** : [CI main 39235083395](https://github.com/fr4nck/Noethys-SL/actions/runs/39235083395) : **753 tests, 0 FAIL, 6 SKIP**, compilation PASS et suite Windows PASS. [CI wx 39235956725](https://github.com/fr4nck/Noethys-SL/actions/runs/39235956725) à qualifier par lecture de son verdict ; Qt natif non validé.
- **STOP-GATE** : recette complète sur base fictive dans l'interface Windows, comparaison PDF/brouillon d'email, préexistants modèles, préférence sans porc inconnue, changement de préférence pendant une période et direction multisite partagée. Ne pas qualifier RC8 sans ces points et résolution des P1 antérieurs.
- Détails : `docs/metier/REPAS_SANS_PORC_RC8.md`, `docs/metier/REPAS_RC8_VALIDATION.md` et issue #430.

## RC8 — commandes de repas et encadrement : développement poursuivi (18/10/2026)

- Décision utilisateur : **poursuivre le développement avant toute RC8**. Aucun tag/release, installateur, migration SQL ou déploiement effectué dans ce lot ; aucune donnée réelle lue ni modifiée.
- #430 : suggestion de +1 repas directeur détaché par site/date/service, direction multisite mutualisée par identifiant d'ensemble, repas facultatif d'adjoint ou directeur stagiaire. Option désactivée par défaut ; anti-doublon limité aux colonnes d'une même commande, **pas entre commandes indépendantes**. Le repas déjà compris dans les adultes doit rester explicitement exclu par l'opérateur.
- #429 : moteur sans interface dans un premier lot puis dialogue **Outils > Simuler les besoins en animateurs** dans les commandes de repas. Configuration explicite site/créneau/cadre/durée/PEDT, sous-effectifs <6 et >=6, prévisionnel (réservations + présents) ou réel (présents). Arrondi par tranche, adultes ignorés, doublons dédupliqués, âges inconnus signalés. **Lecture seule** ; aucune injection dans le bon PDF du restaurateur, aucune certification réglementaire.
- Sources partagées qualifiées à l'identique par SHA de blob : noethys/Dlg/DLG_Saisie_commande.py, noethys/Dlg/DLG_Encadrement.py, noethys/Utils/UTILS_Encadrement.py, tests/test_noethys_sl_encadrement_dialog.py, docs/metier/ENCADREMENT_RC8.md. Aucune fusion globale, aucune branche créée.
- **Matrice des commits de développement** : main **5a658703de8a4a743702290cb5df8b418fa9c2f7** ; wx **fd2b7d0df9e7297ef265acce709687133615dffb** ; qt **ca72dd0b653c34038a9b27f04c19d4c1e121fd08**. Workflows adaptes chacun sur sa branche ; variantes propres conservées.
- Tests sans wx local : **13 PASS / 0 FAIL** du moteur, plus syntaxe du dialogue. [CI Windows main 39164801226](https://github.com/fr4nck/Noethys-SL/actions/runs/39164801226) : **724 tests / 0 échec / 6 ignorés**, compilation et runtime wx PASS. [CI rapide wx 39165107741](https://github.com/fr4nck/Noethys-SL/actions/runs/39165107741) lancée, **conclusion à consulter avant qualification wx**. Qt natif non qualifié ; pas de paquet Qt construit.
- **Reste hors portée de ce lot** : reconnaissance fiable du choix alimentaire « sans porc » (#430) faute de source explicite qualifiée ; regroupement général des repas adultes dans les 6 ans et plus ; affectation permanente des sites et créneaux ; calcul des personnels réellement disponibles, direction/stagiaire dans le planning ; déduplication des repas entre plusieurs commandes ; recette fonctionnelle sur un poste Windows réel avec base fictive.
- **STOP-GATE RC8** : terminer les P1 de facturation/adhésion, vérifier les effectifs simultanés et la continuité des temps d'accueil, qualifier les postes de direction et les PDF en copie isolée. Aucune RC8 ne doit être publiée automatiquement.

## Candidat Windows RC7.5 fabriqué et vérifié (16/10/2026)

- Autorisation de Franck : « ok go » après proposition d'intégrer les corrections
  dans un nouvel installateur. Identité distincte RC7.5 ; RC7.4 conservée intacte.
- Source wx empaquetée : e6958884cfbc2432a36ec388fe948efb90be4cdb.
  Identité, changelog et workflow Windows seuls modifiés ; version interne 1.3.4.4
  et historique numérique inchangés. Test assiduité ajouté aux contrats critiques.
- Contient le catalogue indépendant et la sélection des groupes dans Aujourd'hui,
  ainsi que les taux de journées annulées/absences par famille et enfant.
  Le journal reste désactivé par défaut ; activation ADMINISTRATEUR explicite,
  pas de migration SQL implicite ni reconstitution de l'historique antérieur.
  Les correctifs RC7.4 Connecthys, impression/rappels, Mailjet et optimisations
  prudentes restent inclus. Cotisations automatiques toujours suspendues ;
  chantier RC8 repas directeur propre à main toujours exclu du candidat wx.
- Avant préparation : main 9f29ec67ea7ba6c56cd798e837141b79951b4e5f,
  wx 59e4f44df19369229070718038559a211aed43e3,
  qt 2539e26c13a6a2e96e6f767e0ea1685d15eb7362. Six fichiers communs (accueil,
  assiduité et tests) comparés identiques après normalisation des fins de ligne.
  Pas de fusion globale ni de propagation de l'identité Windows vers main/qt.
- Tests locaux : 61 réussis. CI wx 38939996600 sur source empaquetée : succès,
  722 tests / 10 ignorés prévus, log téléchargé et inspecté.
- Construction Windows 38939995981 : succès, 340 tests critiques / 7 ignorés prévus,
  puis 11 tests MySQL 5.7.44 local jetable sans ignoré. Sauvegarde/restauration
  du journal, déclencheurs après restauration et concurrence vérifiés ; démarrage
  binaire Windows puis ZIP extrait/profil Portable réussis sur runner isolé.
- Artefact 12062244984 : Noethys-SL-0.1.0-rc.7.5-Windows-candidat,
  250637060 octets, disponible jusqu'au 15/11/2026. Fichiers téléchargés dans
  qualification/rc75 (hors Git) et SHA256 recalculés conformes :
  Setup 105287660 octets :
  41a5dfa39e5209b44903d8a41538f988ca22ee0490953d96998659ec05f0ad2b
  Portable 147079667 octets :
  9786527a5c77205521a6277ecd37b08f9fe73439b04e40808a62273bb3cad38b
- BUILD-INFO et notes de versions vérifiés ; inspection statique du PYZ du binaire
  confirme Identite RC7.5, Dlg.DLG_Assiduite, Utils.UTILS_Assiduite, le nouveau
  read_catalog et les callbacks de chargement indépendants des réglages.
  Aucun exécutable lancé sur ce poste utilisateur. Logs/scripts hors Git :
  qualification/rc75-build.log, rc75-ci-wx.log, verifier-rc75.py,
  rc75/verification.json et SHA256SUMS.txt ; paquets RC7.3/RC7.4 préservés.
- Matrice : code commun VALIDÉ techniquement sur main/wx/qt aux SHA déjà documentés ;
  paquet Windows wx RC7.5 VALIDÉ techniquement. Qualification métier de déploiement
  EN ATTENTE sur copie isolée ; Qt natif EN ATTENTE et paquet Qt NON APPLICABLE ici.
- STOP-GATE conservé : candidat de recette, pas de tag/release stable, ni de
  déploiement ou d'activation du journal en production. Serveurs autres que MySQL
  5.7.44, recette terrain du journal et DPI restent à qualifier. Aucun email envoyé,
  aucune lecture ou modification de données réelles, aucune installation locale.

## Réglages Aujourd'hui — catalogue activités et groupes (16/10/2026)

- Signalement de Franck : tableau Programme et agenda vide malgré les activités
  ouvertes ; choix nécessaires dans les groupes ALSH et EMS (captures fournies).
- Défaut reproduit : read_day dépend de toutes les lectures du programme et son
  échec remet aussi activities à []. Le dialogue réutilisait exclusivement ce
  résultat. Aucune base réelle consultée : cause précise du déclenchement terrain
  non déterminée, aucune prétention de l'avoir vérifiée en production.
- Correction : lecture indépendante du catalogue activités/groupes/remplissage,
  trois SELECT seulement à l'ouverture des réglages, en tâche de fond sur une
  connexion explicitement liée au fichier courant et fermée dans tous les cas.
  Les callbacks d'un ancien fichier/génération ou d'un contrôle détruit sont ignorés.
  Échec signalé au lieu d'un faux tableau vide ; vraie liste vide explicitée.
- Hiérarchie activité > groupes avec Afficher et Ordre par groupe. Masquer une
  activité masque tous ses groupes ; M/A et unités restent configurés au parent.
  Préférences de groupes enregistrées dans le JSON personnel existant, sans
  migration SQL, en conservant les anciens groupes/préférences non affichés.
- Catalogue = activités valides y compris sans séance aujourd'hui + leurs groupes
  réels reliés par IDactivite. Bandeau = programme du jour seulement ; groupes
  masqués exclus sans mélanger les effectifs. Détection ALSH, règles M/A et
  comptage distinct des séances conservés. Toujours six SELECT par read_day.
- Tests locaux : 34 tests accueil/éphémérides sur chacune des trois branches,
  dont six nouveaux cas : échec consommations sans perte du catalogue, masquages
  ALSH/hors ALSH et priorité parent, période illimitée sur schéma canonique complet,
  persistance des groupes, chargement natif indépendant et callbacks obsolètes.
- Recette MySQL 5.7.44 synthétique 38918080699 : succès, quatre tests sans ignoré ;
  catalogue et programme comparés à SQLite et snapshots inchangés. Les recettes
  existantes journal/rollback/restauration et Mailjet synthétique restent vertes.
- CI finales vertes : main 38918081836 : 709 tests / 6 ignorés prévus ;
  wx 38918174695 : 722 tests / 10 ignorés prévus ; qt 38918189968 : 674 tests /
  6 ignorés prévus. Journaux téléchargés et inspectés. Matrice : correctif partagé
  VALIDÉ techniquement sur les trois sources ; rendu Qt natif et diffusion dans
  un candidat Windows EN ATTENTE. Aucun statut stable attribué.
- Sources : main 4110a7c9caef84fb18e0dfb28a79cdf14d0405c1,
  wx f3fb1636a5c1c26512f5f8f6204b824c4cf78549,
  qt c5e99968c1ea0e77598b85ac6f8b9d6b7898055a. Quatre fichiers communs comparés
  identiques après normalisation CRLF/LF ; propagation ciblée, aucune fusion.
- Preuves hors Git : qualification/accueil-groupes-mysql.log, accueil-groupes-ci-*,
  accueil-reglages-groupes.py/.png. Capture native RGB opaque, données fictives,
  aucun pixel pris dans la base/application utilisateur.
- STOP-GATE : source qualifié, absent du paquet RC7.4 construit sur 23419a6d.
  Aucun nouveau build, tag, release, déploiement ni lecture production. Rendu Qt
  natif et recette terrain sur copie isolée restent à qualifier. Ne pas annoncer
  cette correction comme présente dans l'installateur RC7.4 déjà distribué.

## Assiduité — annulations et absences par famille/enfant (16/10/2026)

- Demande de Franck : deux taux distincts, annulations ET absences ; choix explicite
  du suivi complet des nouvelles réservations plutôt qu'un indicateur de demandes
  Connecthys. L'ancien historique textuel/tronqué ne permet pas une reconstitution
  fiable : aucune fausse reprise ni ancien taux à zéro.
- Accès : Consommations > Liste des absences > Taux par famille / enfant.
  Filtres période/activités, agrégation enfant ou famille et détail par date.
- Grain explicite : enfant + date + activité ; les unités matin/repas/après-midi
  ne font pas compter trois journées. Cohorte annulations : journée ayant une
  nouvelle consommation créée après activation, puis confirmée en réservation.
  Taux = journées de cette cohorte sans consommation active restante et sans
  ancien pointage / journées réservées suivies. Situation actuelle : réinscrire
  la même journée retire l'annulation du taux ; un retrait partiel n'annule pas
  la journée. Les suppressions administratives sont incluses, pas attribuées aux
  parents. Une annulation tardive devenue absenti reste classée absence Noethys.
- Absences = journées entièrement absentes / journées entièrement pointées,
  sans date future. Justifiées/injustifiées séparées (injustifiée prioritaire si
  les deux motifs existent dans une journée entièrement absente). Présence sur
  une partie de journée : absence partielle, hors numérateur. Réservation encore
  non pointée : journée non pointée, hors dénominateur. Agrégats familiaux pondérés
  par nombres de journées, jamais moyenne des pourcentages individuels.
- Activation ADMINISTRATEUR explicite avec description du changement de schéma :
  table noethys_sl_assiduite_v1, deux index, trois triggers INSERT/UPDATE/DELETE.
  Aucun ajout automatique à l'ouverture ni à la lecture ; aucune modification
  de CTRL_Grille.Sauvegarde, des transactions/commits existants ni de GestionDB.
  Identifiants/états/dates uniquement dans le journal, aucun nom, montant ou mail.
  Les triggers suivent les écritures depuis les autres postes/clients aussi.
- SQLite et MySQL InnoDB (aucune conversion automatique). Les écritures de journal
  appartiennent à la transaction de la consommation ; rollback commun vérifié.
  Changements de montant sans changement d'état/contexte non journalisés. Lecture
  SQLite sur snapshot cohérent ; MySQL connexion dédiée et REPEATABLE READ.
  Activation verrouillée/idempotente ; rupture détectée -> calcul suspendu,
  réparation automatique refusée si elle masquerait une période sans historique.
- Contrôles locaux : 17 tests spécifiques ; sélection assiduité/repas/performance
  48 tests réussis sur les trois arbres. Copie SQLite puis nouveau déclenchement
  vérifiés. MySQL réel 5.7.44 jetable : run 38915319292, succès, 4 tests sans ignoré,
  concurrence quatre connexions, rollback, ancien hors suivi et mysqldump/mysql :
  journal restauré identique, triggers inventoriés par le contrôleur SQL existant,
  et nouvelles écritures capturées après restauration. Aucun test production.
- Échecs de qualification conservés : 38914452080 verrou trop long corrigé par
  SHA1 du nom de base ; 38914689652 snapshot après activation corrigé ;
  38915009265 fixture avec réservation ancienne du même enfant bloquant à raison
  une annulation complète, corrigée en séparant cet enfant fictif. Assertions
  conservées ; recette finale verte, pas d'affaiblissement des contrôles.
- CI finales : main 38915320274 : 703 tests / 6 ignorés ; wx 38915539613 :
  716 tests / 10 ignorés ; qt 38915638802 : 668 tests / 6 ignorés. Toutes vertes,
  logs téléchargés qualification/assiduite-ci-{main,wx,qt}.log. Les CI qt exercent
  les contrats communs et le dialogue wx hérité, pas un rendu Qt natif.
- Matrice : moteur/journal/dialogue partagé VALIDÉS techniquement sur les trois
  sources ci-dessous ; recette métier de déploiement et nouvel installateur
  EN ATTENTE sur wx ; rendu Qt natif EN ATTENTE. Aucun statut STABLE attribué.
- Sources partagées : main 1484a9fe80a46e30be19b00e660f2fa25a1eb1f2,
  wx f14e0a0eb3bb1e9ffb706eca59c3e7459f9aca4b,
  qt b3962dd1476202094d182b77c3c232dc090619df. Six fichiers communs comparés
  identiques après normalisation des fins de ligne ; spécificités conservées.
- Mesure strictement synthétique locale SQLite mémoire, médiane 3 passages de
  5000 insertions : 24,48 ms sans journal / 88,73 ms avec, lecture 50,21 ms.
  C'est un coût ajouté, pas un gain ni une mesure de serveur/terrain. Logs/scripts
  qualification/assiduite-* hors Git ; qualification/ précédent préservé.
- STOP-GATE : implémentation source, absente de l'installateur RC7.4 construit sur
  23419a6d. Aucun nouveau paquet, tag ou release fabriqué ici. Recette métier sur
  copie isolée et versions de serveur autres que MySQL 5.7.44 à qualifier ; Qt
  natif non qualifié. Avant prochain candidat, inclure le nouveau module de tests
  parmi les tests critiques du workflow Windows. Aucun suivi activé en production,
  aucune intervention sur données réelles, aucun email envoyé.

## Candidat Windows RC7.4 fabriqué et vérifié (16/10/2026)

- Autorisation de Franck : ajouter les correctifs Connecthys au prochain paquet.
  RC7.3 étant déjà distribuée, identité distincte RC7.4 ; aucune release/tag stable.
- Source empaquetée wx : 23419a6dc4c8753b33337bb8ade391b5a6bc27cc.
  Identité, notes de version et tests propres au candidat wx ; version interne
  numérique 1.3.4.4 inchangée, historique numérique conservé par test.
- Contient les repas dépendant de TOUTES les périodes demandées, priorité Journée
  face aux trois choix cumulés, rôles configurables ; garde des antécédents,
  cas ambigus/facturés/pointés/verrouillés à traiter manuellement. Contient aussi
  les créneaux distincts, fond wx compact et carte Connecthys au survol.
- Avant construction, têtes distantes relevées : main 98ec3d1e, wx 0791f515,
  qt 0edd1d02. Helper, dialogue de rôles et tests identiques sur les trois arbres,
  méthode Appliquer_reservations identique par comparaison AST ; protections wx
  conservées. RC7.4 ne change que packaging/identité/changelog/tests du candidat.
  Les travaux repas directeur RC8 propres à main restent exclus ; création
  automatique des cotisations toujours suspendue (AUTO_CREATION_SUSPENDUE=True).
- Vérifications locales : 71 tests réussis. CI wx 38911889621 sur source empaquetée :
  699 tests / 10 ignorés prévus, succès. Construction 38911888874 : succès ;
  317 tests critiques / 7 ignorés prévus puis 10 tests MySQL 5.7.44 local jetable,
  aucun ignoré. Démarrage binaire puis ZIP extrait/profil Portable : succès.
- Artefact 12050568222 : Noethys-SL-0.1.0-rc.7.4-Windows-candidat,
  250614555 octets, disponible jusqu'au 15/11/2026. Installateur et ZIP téléchargés
  dans qualification/rc74 (hors Git), empreintes recalculées conformes :
  Setup : d1a2bd347c899ed16c52b6ccc7ee3582811f354d0d8d4c3f0cd7e27dd2d9996e
  Portable : 1d5ece4ac33fd935412560f8820ecc2f1f23cc514be2dff6c0f81a9adb593b53
- BUILD-INFO, version embarquée et modules du PYZ inspectés sans exécution locale :
  nouveau helper et dialogues Connecthys, accueil et WordWrapRenderer présents.
  Logs qualification/rc74-build.log, rc74-ci-wx.log, rc74/verification.json hors Git.
- STOP-GATE : candidat technique uniquement ; recette métier sur copie isolée,
  configuration des rôles réels et DPI à vérifier. Aucune installation locale,
  intervention production, suppression de données ni envoi d'email effectués.
  Qualification Mailjet authentifiée et Qt natif restent en attente.

## Connecthys — repas liés aux accueils et priorité Journée (16/10/2026)

- Demandes explicites : repas non limité mais jamais confirmé lorsqu'une période
  d'accueil demandée reste en attente. Clarification de Franck : TOUTES les
  demi-journées demandées doivent être confirmées, pas seulement une ; règle
  identique pour la journée complète. Les parents sélectionnent Matin / Repas /
  Après-midi séparément. Matin seul + repas et repas + après-midi restent possibles.
- Demande complémentaire : si Journée + Matin + Après-midi sont cochés pour une
  même date/inscription, retenir Journée et écarter les deux choix redondants.
  Réponse générée : « Pour le [date], Journée ne peut pas être cumulée avec Matin
  et Après-midi. La formule Journée a été retenue ; les deux demi-journées ont
  été écartées car elles sont déjà incluses. » Journée retenue peut rester en
  attente ; ce texte ne prétend pas qu'elle a été confirmée. Pas de regroupement
  automatique des seules demi-journées quand Journée n'est pas demandée.
- Reproduction AVANT sur source 996d1b0e : deux scénarios / trois assertions en
  échec (repas traité avant un accueil en attente, deux variantes MAT/APM ; les
  quatre choix saisis au lieu de Journée + Repas). Aucun accès réel. Script/log
  qualification/portail-repas-avant.py/.log conservés hors Git et SHA épinglé.
- Nouveau helper pur UTILS_Portail_reservations : copie/normalisation des demandes,
  suppression des choix redondants uniquement parmi les ajouts, ordre stable
  des suppressions et accueil avant repas, contexte date + IDinscription dans
  l'activité/individu déjà fixé par la grille. Même inscription obligatoire pour
  reprendre une attente antérieure ; pas de mélange entre dates ou inscriptions.
- Les attentes déjà enregistrées sont aussi vérifiées lorsqu'une action ultérieure
  demande seulement un repas. Contrôle sur l'état réel de la grille après les
  suppressions du lot ; une attente annulée ne bloque plus. Les unités de repas
  incluses dans les formules d'accueil sont exclues de la recherche pour ne pas
  rendre le repas dépendant de lui-même. Pas de création de période non demandée.
- Contrat réel SaisieConso vérifié sur case fictive : mode='attente' seul remet
  une consommation unitaire existante en réservation à cause de etat par défaut.
  Le chemin repas lié transmet donc explicitement etat=mode. Pas de modification
  de SaisieConso générique, des tarifs ni des méthodes de sauvegarde/transactions.
  Une revalidation de la demande peut confirmer le repas quand les accueils le
  permettent ; pas de mécanisme de promotion en arrière-plan hors traitement.
- Précontrôle avant les saisies : repas facturé, pointé ou verrouillé → traitement
  manuel sans mutation du lot ; attente ancienne sans inscription identifiable,
  période fermée/inexistante ou unité repas Quantite/Evenement/Multihoraires → manuel.
  Support automatique repas unitaire/horaire. Une priorité Journée impliquant des
  demi-journées DÉJÀ enregistrées reste manuelle, même non facturées : pas de
  conversion/suppression silencieuse d'anciennes consommations. Deux formules
  Journée distinctes ambiguës ne sont jamais arbitrées automatiquement.
- Rôle de chaque choix dans Saisie d'une unité de réservation : Automatique,
  Autre choix indépendant, Matin, Repas, Après-midi, Journée complète. Noms usuels
  exacts reconnus avec accents/casse normalisés ; noms composés non devinés.
  Les libellés personnalisés se configurent explicitement. Stockage natif dans
  parametres / categorie noethys_sl_portail_roles_v1 / nom IDunite du portail,
  sans migration ni changement de portail_unites/protocole Connecthys. Un SELECT
  supplémentaire réutilise la connexion déjà ouverte par le traitement ; pas
  de connexion par ligne. Pas de lecture-écriture implicite des rôles à l'ouverture.
- 24 tests dédiés : véritable méthode Appliquer_reservations sur grille/DB fictives,
  cas MAT/APM/Journée, ordre d'arrivée, précédentes attentes, répétition/revalidation,
  annulation conservée, contexte date/inscription, zéro auto-dépendance, protections,
  règles ambiguës, vrais SaisieConso et dialogue wx de paramétrage (persistance mockée),
  helper pur et réentrant à quatre threads. 24 OK sur main/wx/qt. Suite ciblée plus
  large de 88 tests OK avant les derniers cas ; 33 ciblés finaux OK, puis CI ci-dessous.
- Départ : main 996d1b0e, wx 03f21ff8, qt e0dc317a. Code final :
  main **4d1189aa3e0c169cd61e9b8a15e6c7a374fc67bb**,
  wx **e18492286b809792affa32f89283908332d6a57f**,
  qt **44677fe918c67c22ee444661cbd8a12adf794b58**.
  Helper/paramétrage/tests identiques, et méthode Appliquer_reservations identique
  par SHA256 ab86988e65bfabbdaf0f207f139061fe1616456fad7a5cc7b652b37ecb39720d.
  Différence historique du reçu email wx conservée ; aucun merge global ni branche.
- CI main [38908786818](https://github.com/fr4nck/Noethys-SL/actions/runs/38908786818)
  SUCCESS : 686 tests / 6 ignorés ; wx
  [38908857188](https://github.com/fr4nck/Noethys-SL/actions/runs/38908857188)
  SUCCESS : 699 tests / 10 ignorés ; qt
  [38908879627](https://github.com/fr4nck/Noethys-SL/actions/runs/38908879627) SUCCESS : 651 tests / 6 ignorés, code commun wx ; UI Qt native non qualifiée.
  Les CI des lots intermédiaires 38907891890 / 38907989464 / 38908012930 étaient
  vertes ; le premier run main e2201647 a été remplacé et annulé par concurrence.
- Qualification : logique commune VALIDÉE par tests synthétiques sur les trois
  arbres ; recette UI Qt native, paramétrage réel des choix, grilles/tarifs du pilote,
  écritures MySQL de ce scénario et nouveau binaire empaqueté EN ATTENTE. Les tests
  ne prétendent pas remplacer la recette métier du prochain candidat distinct.
- Aucun email envoyé, synchronisation réelle, SQL de production ou réparation
  rétroactive. Annulations/délais existants et sauvegarde de la grille conservés.
  Cotisations automatiques toujours suspendues. Aucun nouvel installateur/tag/release ;
  la RC7.3 déjà fabriquée ne contient pas ce lot. Logs/scripts locaux dans qualification/
  hors Git ; prochaine étape : qualification pilote isolée puis candidat distinct si demandé.

## Carte Connecthys approuvée et captures opaques — 16/10/2026

- Clarification utilisateur : « tout est noir » concernait les captures, pas les
  polices. PNG wx capturés en 32 bits : alpha=0 sur le fond et le texte (vérifié
  par lecture de pixels RGBA), donc rendu noir dans certains afficheurs. Le script
  LOCAL qualification/accueil_preview.py capture désormais les composants dans
  wx.Bitmap(width,height,24). Nouveaux PNG vérifiés RGB sans transparence.
- L'agrandissement global de polices e4cfb6f7 (wx 5f6fae00 / qt c7c44849), issu du
  malentendu, a été annulé par commits de revert traçables, sans réécrire l'historique.
- Référence approuvée fournie : carte sombre arrondie, grand compteur, flèche ↗ en
  haut à droite, « demandes à traiter » dessous, état et heure puis message de
  synchronisation. Carte entière cliquable, curseur main, survol/focus plus clair
  et état pressé. Label accessible contenant le compte conservé ; zéro et compte
  inconnu distincts. Taille calculée pour le nombre ; minimum de hauteur 114 DIP
  évitant la coupure du texte. Boutons de synchronisation/outils conservés.
- État/journal compact rendu sans cadre natif, état et dernière heure sur une ligne,
  explication de l'état dessous. L'heure reste celle du dernier succès effectif,
  aucune nouvelle lecture/écriture DB ni changement du cycle de synchronisation.
  Ancien panneau non compact inchangé. Effectifs et créneaux du lot précédent conservés.
- Dernier code : main 8d3fe4773eb265b13e789de77dd120adcc37e5a4,
  wx 6847af908826070a5939a752eff4a5d9ac4db058,
  qt 97b3316fc8a239ed4a88c89b13e3320c261dedc3. Portages ciblés sans branche nouvelle.
- 28 tests ciblés natifs accueil + préférences OK sur main et rendu normal/survol
  inspecté, uniquement données fictives et DB mockée ; aucun client réseau lancé.
  CI rapide nouvelle main 38905557531 et wx 38905598688 EN COURS à la rédaction.
  Les CI vertes des sections antérieures ne qualifient pas cette nouvelle carte.
  UI Qt native / DPI / binaire empaqueté EN ATTENTE. Aucun nouvel installateur.
- Aperçus locaux fiables : qualification/connecthys-carte.png (composant seul) et
  qualification/accueil-wx-survol.png (vue globale), RGB opaques, hors Git. Les
  captures RGBA plus anciennes et la première annotation générée sur fond noir
  ne doivent pas être utilisées comme preuve du rendu natif. L'agent avait d'abord
  confondu ce défaut de capture avec un défaut de lisibilité ; ce diagnostic est corrigé.
- Prochaine étape : relever la fin des CI, puis qualification d'un candidat distinct
  si demandé. RC7.3 déjà fabriquée reste inchangée, ces retouches ne sont pas installées.

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
  Syntaxe compilee ; CI main [38744861087](https://github.com/fr4nck/Noethys-SL/actions/runs/38744861087) SUCCESS au commit 55889bad.
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
  identiques. Nouveau test ajoute a la CI rapide, CI main [38732132634](https://github.com/fr4nck/Noethys-SL/actions/runs/38732132634) SUCCESS au SHA 2aaa3046a6a4bd928eb8ad5d6f02b74c3851f87b.
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

## Lot Qt Individus/Familles — 14/10/2026

- **Branche** : `qt`, sans branche ajoutée. Base : `2146ad13`.
- **Code** : `f75b5515` (choix N familles obligatoire), `38060ecd`
  (test hors écran), `1c0e8dcf` (fiches consultatives et chargement
  asynchrone), `7042c57e` (recherche non bloquante, latest-wins).
- **Preuves** : CI #38547575403, #38547920649 et
  [#38548298813](https://github.com/fr4nck/Noethys-SL/actions/runs/38548298813)
  en **SUCCÈS**, Windows PySide6 hors écran. L'échec initial
  #38547050445 venait exclusivement d'un test de focus sans fenêtre affichée.
- **Données** : SQLite fictif, contrôle de données avant/après ; lecture seule.
  Aucun test sur une base réelle ou un profil `Portable/`.
- **Non touchés** : `main`, `wx`/prérelease RC7, schéma SQL, packaging.
- **Stop-gates** : reports métier communs RC6/RC7 vers `main`/`qt` encore
  EN ATTENTE. Catégories familiales, volumes et droits d'accès à qualifier.
- **Prochaine action** : recette Windows graphique en VM sur copie isolée ;
  étendre progressivement les fiches sans rendre leurs écritures actives.



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


## 14. Propagation ciblée Nomadhys — 11/10/2026

Périmètre : seul correctif de validation des catégories/actions/états importés,
commit source `694ccacc2d37ba71298b56e7ddb6901be6a55d2d`, confirmé comme tête
distante de main avant intervention. Cherry-pick avec provenance (-x), sans
fusion générale, nouvelle branche distante ni réécriture d'historique.
Une trace documentaire séparée accompagne chaque correctif.

### Matrice des preuves

| Correctif | main | wx | qt |
| --- | --- | --- | --- |
| Validation Nomadhys | VALIDÉ : 694ccacc2d37ba71298b56e7ddb6901be6a55d2d | VALIDÉ : d95fb660de4fc226603d3a9e36a54946455eb1fc | VALIDÉ : 508d5f4f119542e954d3744f06287a46d5f06c5a |
| Rail 1, quarantaine, TLS Connecthys et contrat vaccins | VALIDÉ dans les tests ciblés de ce lot | VALIDÉ dans les tests ciblés de ce lot | VALIDÉ dans les tests ciblés de ce lot |
| Secteur famille sans titulaire, déplacement Noedoc sans delta, mode statistiques invalide | Présents dans l'arbre main ; EN ATTENTE de réexécution de leurs tests dans cette session | ABSENTS ; hors périmètre Nomadhys | ABSENTS ; hors périmètre Nomadhys |

Têtes avant intervention : main `694ccacc2d37ba71298b56e7ddb6901be6a55d2d`,
wx `5538488b0ff03edcef81198a4f97998b675e2ef6`,
qt `6d0c84e78efbe3497e8d2100bc9b6250b8e635fb`.
Parent du correctif source : `b5aa605b916c556885d3d3ed36271c6973746b89`.
Ancêtre commun main/wx et main/qt : `44fd8096506f7362706bb95ef1fbee3dae790a59`.
Les arbres wx et qt initiaux sont identiques. Par rapport au parent source,
ils diffèrent sur les trois protections citées et leurs trois fichiers de tests
(six fichiers, 231 lignes absentes). Ces écarts existants sont conservés.
Le delta de chaque cherry-pick est strictement celui des deux fichiers Nomadhys
(63 insertions, 10 suppressions), sans perte d'autres apports de la cible.

### Empreintes Git identiques pour wx et qt

| Fichier | Avant cherry-pick | Après cherry-pick, identique à main |
| --- | --- | --- |
| noethys/Dlg/DLG_Synchronisation_donnees.py | d31f6d221664600e850c936b9772879a6375c462 | 32d7a32979e1a3cbcb903e68c1b82af95cbacf8c |
| tests/test_audit_reseau_nomadhys.py | 64e43f1914b2d86006f7d06187b22e0fc3d7847d | 95aa7b8d8441be1f66e8fc8d53e2de328f421f85 |

### Validation et publication

Python 3.11 Windows : 55 tests réussis sur chacune des trois têtes de correctif,
165 exécutions au total, aucun échec ni test ignoré :
audit réseau Nomadhys 37, format chiffrement 7, quarantaine 1,
isolation TLS Connecthys 5, contrat vaccins 5.
Garde réseau explicite sur connect/connect_ex/create_connection/getaddrinfo :
zéro tentative réelle. Tests AST, dépendances factices et fichiers temporaires ;
copie isolée sans profil Portable, aucune base de production utilisée.
Diff et empreintes vérifiés avant/après ; contrôle des espaces Git réussi.
La trace documentaire ne modifie aucun fichier de runtime ni de test.

Publication autorisée uniquement après ces contrôles, en fast-forward non forcé
sur les seules refs existantes wx et qt, avec vérification des SHA attendus
et envoi atomique. Le résultat distant et les SHA de documentation seront
confirmés dans le compte rendu de session ; cette note ne présume pas le succès
du push. main, master, branches historiques, tags/releases et PR ne sont pas
modifiés. PR ouvertes relevées : #422, #384, #369, #366, #355, #112, #104, #102 ;
aucune n'a wx ou qt comme tête ou base.

Dépôt original conservé sur main : ses 11 fichiers non suivis sont inventoriés
avec SHA-256 pour comparaison finale, sans copie de profils dans les tests.
Stashes et worktrees historiques conservés. Logs et preuves détaillées gardés
dans l'espace de travail local de la session (nomadhys-evidence.json et logs).
CI distante : aucun résultat revendiqué ici ; aucun build de packaging demandé.
Qualification globale wx/qt : EN ATTENTE / STOP-GATE pour une release, compte
tenu des écarts ci-dessus et des recettes réseau/Windows restant hors de ce lot.
Prochaine étape : qualifier séparément les correctifs communs manquants et
les parcours métier réels avant de déclarer une branche stable.
