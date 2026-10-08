# Contre-qualification du Rail réseau 1 avant fusion

> Mission : contre-qualifier les corrections du rail 1, sans nouvelle fonctionnalité, sans rail 2, **sans fusion**.
> Code de production inchangé depuis `4fef6a42` (`git diff 4fef6a42 HEAD -- noethys` est vide).
> Aucun secret réel n'est reproduit dans ce document.

## 1. État Git

| Branche | HEAD | Vérifié |
|---|---|---|
| `rc/noethys-sl-0.1.0-rc.2` | `91d9e625d96c5a1460d42dda053db509fa28d181` | oui |
| `claude/noethys-sl-network-audit-6r5tup` | `386bbb4631777626e1ff77a3b71d4594530aff20` | oui, ancêtre du rail 1 |
| `fix/rc2-network-stopgate-1` | `4fef6a42cfcaf1258f25209f85c22224441d7f5b` | oui |

- **Commits** : 22 depuis la RC2 (6 de l'audit, 16 du rail 1). Les 16 du rail 1 : 3 de tests de caractérisation, 11 de correctifs, 2 de documentation. *(Le récapitulatif précédent annonçait à tort « 6 de tests » pour le rail 1 : ces 6 sont ceux de l'audit.)*
- **Fichiers modifiés depuis la RC2** : 31, soit **17 de production** (+568 / −180), **11 de tests** (+4 365), **3 de documentation** (+851).
- **Production modifiée** : `CTRL_Portail_serveur`, `CTRL_Serveur_nomade`, `DLG_Factures_email`, `DLG_Mailer`, `DLG_Rappels_email`, `DLG_Releve_prestations`, `DLG_Saisie_depot`, `DLG_Saisie_portail_demande`, `DLG_Saisie_reglement`, `DLG_Synchronisation`, `UTILS_Cryptage_fichier`, `UTILS_Envoi_email`, `UTILS_Impression_cotisation`, `UTILS_Impression_rappel`, `UTILS_Impression_recu`, `UTILS_Portail_installation`, `UTILS_Portail_synchro`.
- **Inchangés par le rail 1** : workflow Windows, `requirements.txt`, packaging, `Versions.txt`.

## 2. Connecthys de production : STOP-GATE

### **VERSION CONNECTHYS PRODUCTION À RELEVER MANUELLEMENT**

L'instance PMSL n'est pas joignable depuis l'environnement d'analyse, et aucun dépôt local n'indique laquelle est déployée.

**Ce qui a été établi sans toucher à la production :**
- Le dépôt privé `fr4nck/Portails` (« Portail PMSL ») est un **fork de Connecthys 1.1.0**. Son README dit qu'il n'est **pas encore** la cible d'exploitation PMSL. Ses fichiers de contrat sont **octet pour octet identiques** à l'amont 1.1.0.
- La mise à jour automatique de Connecthys étant activée par défaut, une instance issue de l'amont tend vers 1.1.0 (`versions.txt` : 1.1.0, version minimale de Noethys 1.3.3.0 ; Noethys-SL est en 1.3.4.4). **Ce n'est qu'une inférence, non une preuve.**

**Procédure minimale pour relever la version (lecture seule, aucune opération destructive) :**

1. Ouvrir `<URL d'accès à Connecthys>/get_version` dans un navigateur. En mode CGI : `<URL>/<fichier cgi>/get_version`. Réponse attendue : `{"version_str": "1.1.0", "version_tuple": [1, 1, 0]}`. La route ne prend aucun secret et ne modifie rien.
2. Sur l'hébergement, calculer le SHA-256 de `connecthys/application/views.py`, `importation.py`, `exportation.py`, `cryptage.py` et `models.py`, et comparer les 12 premiers caractères au tableau de [`CONTRAT_CONNECTHYS.md`](CONTRAT_CONNECTHYS.md).
3. Ne **lancer ni mise à jour, ni installation, ni `upgrade`, `repairdb`, `cleardb`**.

Me transmettre le résultat de l'étape 1 et les 5 empreintes suffit ; aucune donnée personnelle n'est nécessaire.

## 3. Comparaison des contrats avec les versions Connecthys

Le serveur Connecthys réel **n'a pas été exécuté** (sa pile historique ne démarre pas sous un Python moderne, d'après `Portails/docs/LEGACY_RUNTIME.md`). Les verdicts reposent sur la **lecture du code serveur de 87 versions** (86 tags de 0.1.1 à 1.1.0, plus `master` @ `7949752`), par une analyse mécanique, puis sur les tests côté Noethys.

| Contrat | Résultat sur les 87 versions |
|---|---|
| Routes `syncup`, `syncdown`, `get_version` ; jeton ; `portail_actions` (`ref_unique`, `etat`, `reponse`) ; comportement de `syncup` et `syncdown` | **identiques dans toutes les versions** |
| Format SV2 | présent de **0.7.2** à 1.1.0 |
| Envoi de pièces par les familles, chiffrées en SV2 | de **0.9.1** à 1.1.0 ; aucun appel demandant l'ancien format |
| `models.py` | schéma SQLAlchemy de la version installée (section K du contrat) |
| Routes d'administration | `get_version` et `upgrade` : de 0.1.1 à 1.1.0 ; `update` : de 0.1.2 ; `repairdb` : de 0.5.4 ; `cleardb` : de 0.7.2. Le rail 1 ne modifie aucun appel à ces routes. |

| Correction | Verdict | Détail |
|---|---|---|
| X-03 | **COMPATIBLE PROUVÉ** | Aucune requête ni séquence modifiée ; contexte TLS client uniquement |
| CNX-10 | **COMPATIBLE PROUVÉ** | URL, archive et procédure d'installation inchangées |
| CNX-14 | **COMPATIBLE PROUVÉ** | Interface uniquement |
| EMAIL-10 | **COMPATIBLE PROUVÉ** | `etat`/`reponse` ne sont jamais transmis tels quels ; `UPDATE` par `ref_unique` identique dans toutes les versions |
| X-01, pièces Connecthys | **COMPATIBLE PROUVÉ** | Aucune version n'émet de pièce au format pickle |
| Même verdict pour la **version déployée** | **IMPOSSIBLE À PROUVER** ici | version à relever (section 2) |

CNX-16 : **RÉFUTÉ POUR LE CONTRAT CONNECTHYS QUALIFIÉ** (versions 0.1.1 à 1.1.0 et `master`).

## 4. EMAIL-10 : revalidation

Chaîne vérifiée de bout en bout :
- `Traitement_recus` renvoie `False` si l'email n'est pas accepté ;
- `Traiter()` renvoie ce `False` tel quel et `Traitement()` ne change alors pas l'état : la demande reste **« attente »** ;
- le test `test_rail1_portail_recu.py` exécute la vraie méthode et **échoue sur l'ancien code** ;
- côté Connecthys, aucun état incompatible n'est envoyé : seuls `validation` et `reponse` partent, jamais depuis un échec. L'état `attente` est celui que `syncdown` sélectionne dans les 87 versions pour les demandes à télécharger ;
- comportement identique à celui, historique, de `Traitement_factures`.

**Risque résiduel** : si l'envoi SMTP aboutit mais que la confirmation est perdue (EMAIL-03, rail 2), la demande reste « attente » alors que l'email est parti ; un retraitement peut alors le renvoyer.

## 5. X-01 et format SV2

- **Entrées réseau → SV2 uniquement** : `AnalyserFichier` (Nomadhys : FTP, serveur TCP, import manuel) et `Traitement_pieces` (pièces Connecthys) passent `autoriser_ancien_format=False`.
- **Restauration locale volontaire → ancien format encore accepté** : `DLG_Restauration` appelle `DecrypterFichier` en mode par défaut.
- **Aucun appelant oublié** : un test recense les 3 appelants de `DecrypterFichier`.
- **Connecthys** : aucune version n'émet de pièce au format pickle.
- **Nomadhys** : le code de la version 2.0 chiffre avec `cryptFile2` (SV2) ; il a abandonné le pickle avec l'adaptation Python 3 de janvier 2020 (`ddf8c54`). Sous Python 3, Noethys-SL n'écrit lui-même que du SV2, même avec `ancienne_methode=True` (testé) : une tablette incapable de lire le SV2 ne fonctionnait déjà pas avec la RC2.
- **Aucune version utilisée n'émet donc de pickle sur le réseau** : pas de blocage ni de plan de migration nécessaire à ce stade.
- **Risque résiduel accepté** : une sauvegarde piégée restaurée volontairement reste exploitable (rail 2).

## 6. Qualification Mailjet

Version de la bibliothèque : **1.9.0** (build RC2 du 07/10), **1.9.1** (build de la branche, 08/10). Différences : pagination et garde-fous du **constructeur de messages**, que Noethys n'utilise pas (il appelle `send.create` directement). L'empreinte d'idempotence est identique. Aucun appel réel à l'API Mailjet n'a été fait ; les tests simulent la connexion.

| Exigence | Preuve |
|---|---|
| Message accepté par Mailjet, jamais présenté comme distribué | `test_rail1_mail_lot.py::LibellesTests` ; aucune formulation de distribution dans les libellés (recherche exhaustive) |
| Erreur Mailjet avec motif détaillé | `ErreursMailjetTests` : `error`, `Messages` absent, 401, 5xx non JSON, réponse 200 inattendue |
| Aucun secret affiché | même classe : ni clé, ni secret, ni `Authorization`, ni payload dans l'écran ni dans le journal |
| MessageID conservé | `test_identifiants_mailjet_conserves_sur_le_message`, `test_historique_apostrophe_et_identifiant_mailjet` |
| Historique au fil de l'eau | `HistoriqueAuFilDeLEauTests` (rappel appelé dès l'acceptation, même lot arrêté) |
| Lot arrêté ; acceptés / échecs / non tentés | `ArretApresErreurTests` (Mailjet et SMTP) |
| Famille absente du lot ; adresse libre des rappels | `test_rail1_mail_familles.py` (25 tests : factures et rappels exécutés pour de vrai) |
| Reçu de règlement | `test_rail1_recu_reglement.py` |

**Libellés « envoyé avec succès » restants hors parcours Mailer** (non modifiés, ils n'affirment pas une distribution) : rapport de bug, test d'adresse d'expédition, traductions (code cassé en Python 3), SMS (« Envoi des SMS terminé »), libellé d'étape « Envoi terminé avec succès » de la barre de progression Mailjet. **Dette de formulation, P3.**

Aucun webhook et aucun suivi de distribution n'ont été implémentés.

## 7. ReportLab 5

**Constat** : le build Windows RC2 du 07/10 (run 13, `eda554c`) installe déjà **ReportLab 5.0.1** (journal de l'étape « Installer les dépendances »). Le code RC2, sous ReportLab 5.0.1, **ne peut plus importer** `ShowBoundaryValue` : les moteurs de reçu, rappel, cotisation et relevé échouent donc dans la RC2 telle que construite. Reproduit sur le code RC2 ; non observé sur l'exécutable lui-même.

**Le retrait de `ShowBoundaryValue` ne change pas le rendu :**
- le symbole n'était **jamais utilisé** : un seul `import`, zéro référence, avant comme après (analyse de l'arbre syntaxique) ; `showBoundary=False` est un autre paramètre, inchangé ;
- **rendus générés** avec le code RC2 (symbole de remplacement inerte, faute de quoi il ne s'importe plus) et avec le code de la branche, sous **ReportLab 5.0.1** : **PDF identiques octet pour octet** après normalisation des dates et de l'identifiant du PDF, pour le **reçu, le rappel, la cotisation et le relevé de prestations** ;
- méthode vérifiée par un contrôle : le même code généré deux fois donne des PDF identiques après normalisation ;
- **facture** : non concernée par ce correctif (son moteur n'importait pas le symbole) ; un test existant génère un vrai PDF de facture et réussit sous ReportLab 5.0.1 ;
- **autres incompatibilités ReportLab 5** : sur les **598 imports ReportLab du code entier**, la branche en a **0** d'introuvable sous 5.0.1, la RC2 en avait exactement 4 (ceux corrigés).

**Limites** : jeux de données synthétiques ; le relevé n'a été généré que sur un cas minimal (PDF court) ; les modèles de documents réels de PMSL n'ont pas été utilisés.

**Épinglage de ReportLab.**
- **ÉPINGLAGE NON NÉCESSAIRE pour ce correctif** : le code est désormais compatible avec ReportLab 4.5.1 (imports) et 5.0.1 (imports et rendus).
- **Rendu de l'exécutable Windows : À QUALIFIER WINDOWS.**
- À décider séparément par la release : les dépendances de `requirements.txt` ne sont pas épinglées ; entre deux builds à un jour d'écart, `mailjet-rest` est passé de 1.9.0 à 1.9.1. C'est ce flottement qui a introduit la panne ReportLab sans qu'aucun test ne la voie. L'épinglage relève de la reproductibilité du build, pas de la correction.

## 8. Nomadhys

Tests Linux exécutés (`test_audit_reseau_nomadhys.py` et `test_rail1_format_chiffrement.py`) :

| Scénario | Test | Résultat attendu et obtenu |
|---|---|---|
| Nom valide | `test_nom_nomadhys_valide_accepte` | accepté |
| Nom avec `../` | `test_nom_relatif_hors_sync_refuse` | refusé, rien écrit |
| Chemin absolu | `test_nom_absolu_refuse_et_cible_intacte` | refusé, cible intacte |
| Noms invalides (extension, forme, séparateurs, type) | `test_noms_invalides_refuses` | refusés |
| Taille invalide (0, négative, texte, `None`, booléen, démesurée) | `test_tailles_invalides_refusees` | refusées |
| Fichier complet | `test_succes_supprime_les_intermediaires_et_produit_le_dat`, `test_suppression_distante_avant_tout_import_local` | `.dat` produit, intermédiaires supprimés, distant supprimé **après** succès |
| Fichier tronqué | `test_taille_incorrecte_conserve_en_quarantaine`, `test_fin_de_connexion_analyse_avec_controle_de_taille` | quarantaine `.echec`, jamais importé |
| Mauvais mot de passe | `test_mauvais_mdp_conserve_l_original_en_quarantaine` | original conservé, motif affiché |
| Fichier non SV2 | `test_ancien_format_pickle_refuse_en_reception` | refusé, aucun code exécuté |
| Reprise après correction du mot de passe | `test_reprise_apres_correction_du_mot_de_passe` | importé, puis distant supprimé |
| Suppression FTP uniquement après analyse réussie | `test_echec_dechiffrement_conserve_distant_et_local` | distant conservé en cas d'échec |
| Échec de la suppression distante | `test_coupure_apres_analyse_avant_suppression_F_puis_reimport` | message, fichier reproposé |

**La tablette peut-elle reprendre ses actions ?** Oui, d'après le code Nomadhys 2.0 : `synchronisation.py` supprime seulement le **fichier zip de transfert** après l'envoi ; ses **actions** restent dans sa base `actions_<IDfichier>.dat` jusqu'à ce qu'elle lise le fichier de données de Noethys et y retrouve l'archivage (`nomade_archivage`). Un fichier rejeté ou mis en quarantaine par Noethys n'est pas archivé, donc la tablette ne purge rien et son prochain envoi contient les mêmes actions. **Non vérifié avec une vraie tablette.**

**Hypothèse sur le nom des fichiers** : la liste blanche suppose un `IDfichier` de 14 chiffres et 3 lettres, seule forme de génération dans l'historique depuis 2016 ; une base antérieure à 2016 n'est pas couverte. Le chemin FTP n'applique pas cette liste blanche.

## 9. Windows

### Ce qui a été fait

Pipeline de la RC2 (`noethys-sl-windows.yml`, déclenché sur `fix/rc2-network-stopgate-1` à `4fef6a42`) : run `37724018307`, **succès**, 9 étapes réussies, dont le contrôle de démarrage : « Noethys.exe est resté actif pendant le contrôle de démarrage ».

Versions réellement installées par le build :

| Composant | Build RC2 du 07/10 | Build de la branche du 08/10 |
|---|---|---|
| Python | 3.10.11 | 3.10.11 |
| wxPython | 4.2.5 | 4.2.5 |
| ReportLab | 5.0.1 | 5.0.1 |
| mailjet-rest | 1.9.0 | 1.9.1 |
| paramiko | 5.0.0 | 5.0.0 |

**Limite** : ce pipeline compile, construit l'exécutable et vérifie qu'il démarre. **Il n'exécute aucun test.** Aucun des tests ci-dessous n'a donc tourné sous Windows. L'artefact `Noethys-SL-0.1.0-RC2-Windows` (zip portable et Setup, 242 Mo, SHA-256 `9a31d3fe…f93cbf`) est disponible sur le run **jusqu'au 22/10/2026** ; il n'a pas été téléchargé ici.

### Ce qui reste à faire par une personne (recette Windows manuelle)

**Précaution préalable.** Dans la configuration Connecthys de Noethys, **décocher « Mises à jour automatiques »** pendant la recette. Sinon la première synchronisation demande à Connecthys de se mettre à jour lui-même (écrasement des fichiers du serveur si une version plus récente existe sur GitHub). Réversible : recocher ensuite si souhaité.

Utiliser des adresses de test et ne jamais ouvrir de session d'administration du portail.

| # | Scénario | Étapes | Résultat attendu |
|---|---|---|---|
| A1 | Mailjet, envoi simple | Envoyer un email à **sa propre adresse** depuis le Mailer | Message « accepté par Mailjet » (jamais « envoyé avec succès » ni « remis ») |
| A2 | Mailjet, pièce jointe | Idem avec un PDF | idem |
| A3 | Mailjet, erreur volontaire non destructive | Adresse syntaxiquement invalide saisie à la main (ex. `invalide@`) | Motif Mailjet affiché (HTTP 400, adresse invalide) ; **aucune clé ni secret** à l'écran |
| A4 | Mailjet, lot arrêté | 3 destinataires dont le 2e invalide, choisir « Arrêter » | Compte rendu : 1 accepté, 1 en échec, 1 non tenté |
| A5 | Historique, MessageID | Ouvrir l'historique de la famille d'un destinataire de test | « Envoi de l'Email … (accepté par Mailjet, MessageID n) » ; retrouver ce message dans l'historique Mailjet |
| A6 | Fermeture normale | Quitter Noethys ; lire `journal.log` | Aucune clé API, aucun secret, aucun contenu de message |
| B1 | SMTP, envoi simple | Adresse d'expédition SMTP, 1 destinataire de test | Message « accepté par le serveur de messagerie » |
| B2 | SMTP, pièce jointe | idem avec un PDF | idem |
| B3 | SMTP, reçu | Envoyer un reçu de règlement à une adresse de test | Reçu marqué envoyé **seulement** en cas de succès ; essayer aussi avec un serveur SMTP volontairement faux : le reçu n'est **pas** mémorisé |
| C1 | Facture | Générer et envoyer une facture | PDF généré, aucune erreur d'import |
| C2 | Rappel | Générer une lettre de rappel (PDF) | idem (**ce moteur échouait dans la RC2 telle que construite**) |
| C3 | Reçu de règlement | Générer un reçu | idem (même remarque) |
| C4 | Cotisation et relevé de prestations | Générer les deux | idem (même remarque) |
| C5 | Famille sans destinataire | Lot de factures avec une famille dont l'individu destinataire a été supprimé ou détaché | La famille figure dans l'avertissement avec son motif |
| D1 | Connecthys, connexion | Ouvrir le panneau Connecthys | Affichage correct |
| D2 | Synchronisation normale | « Autoriser tous les certificats » **décoché**, synchroniser | Aucune erreur ; message final « Client de synchronisation prêt » |
| D3 | Option activée (si réellement utilisée) | « Autoriser tous les certificats » coché, synchroniser ; puis envoyer un email Mailjet et ouvrir « Aujourd'hui » | Synchronisation réussie, **et** les autres appels HTTPS restent vérifiés (aucun message de certificat nouvellement toléré) |
| D4 | Bouton | Pendant et après la synchronisation | Le libellé « demande(s) à traiter » se met à jour, sans blocage ni plantage |
| D5 | Fermeture | Quitter Noethys juste après une synchronisation | Fermeture propre |
| D6 | Reçu par Connecthys | Traiter une demande de reçu en automatique avec un email volontairement en échec | La demande **reste « attente »** |
| E | Nomadhys, **si une vraie tablette est disponible** | Échange nominal, dans les deux sens | Fichier reçu, importé, tablette purgée après archivage ; **aucune manipulation destructive** |

**Les scénarios de corruption** (mauvais mot de passe, fichier tronqué, nom invalide) **restent en environnement simulé** : ils sont couverts par les tests Linux.

**À ne pas faire** : installation de Connecthys, `upgrade`, `repairdb`, `cleardb`, mise à jour manuelle.

**Note** : une synchronisation normale **écrit** sur le portail (envoi des données, état des demandes). C'est l'opération habituelle de production ; la lancer de préférence à un moment calme, ou contre une instance de test.

## 10. Suite de tests

| Lot | Résultat |
|---|---|
| `tests/test_audit_reseau_*.py` et `tests/test_rail1_*.py` | **218 réussis** (42 sous-tests) |
| Suite complète, branche | **840 réussis, 36 échecs**, 1 `xfail` |
| Suite complète, RC2 d'origine (`91d9e625`) | 622 réussis, 36 échecs |
| **Échecs de la branche contre la RC2** | **exactement les mêmes 36** (liste comparée) : **aucun nouvel échec** |
| **Comparateur du projet** (`scripts/qualification/compare_test_baseline.py`, celui de la CI : compare les identités **et les causes** des échecs, découverte `unittest`) | RC2 : 659 tests, 37 problèmes ; branche : 877 tests, 37 problèmes. **`new_failures` vide, `changed_causes` vide, `fixed_failures` vide.** Les 37 = les 36 échecs + 1 test que pytest classe en échec attendu (`pytest.mark.xfail`). |
| Tests Mailjet historiques sans profil Noethys (lecture des paramètres neutralisée) | **36 sur 36 réussis**, avant et après |
| Compatibilité syntaxique Python 3.10 des 17 fichiers modifiés | OK |

**DETTE DE TEST PRÉEXISTANTE (36 échecs, non comptés comme une réussite)** :
- 29 tests Mailjet (`test_vanilla_mailjet_*`) : ils lisent les paramètres en base sans profil Noethys ; ils passent quand cette lecture est neutralisée ;
- 4 tests « Aujourd'hui » (`test_ephemerides*.py`) : tests non mis à jour après l'évolution du panneau ;
- 1 test AUI : dépend de la version de wxPython ;
- 2 tests de conventions (recette de modèles, récupération de texte) : non analysés.

Aucun test n'est exécuté par la CI de la RC2.

Commande : `xvfb-run -a python -m pytest -q tests/test_audit_reseau_*.py tests/test_rail1_*.py`.

## 11. Signaux nouveaux

| # | Constat | Gravité | Traitement |
|---|---|---|---|
| N1 | Le build RC2 du 07/10 embarque ReportLab 5.0.1 : reçu, rappel, cotisation et relevé ne peuvent pas être générés dans la RC2 telle que construite | **P1**, confirmé par reproduction sur le code RC2 ; non observé sur l'exécutable | Déjà corrigé au rail 1 (`a05efe8`) : **ce correctif est le plus urgent du lot** |
| N2 | Dépendances non épinglées : les builds flottent (`mailjet-rest` 1.9.0 puis 1.9.1 en un jour) et aucun test ne tourne en CI | P2 | Décision de release, hors correctif |
| N3 | « Mises à jour automatiques » de Connecthys activées par défaut : à chaque synchronisation, le serveur peut écraser son code par l'archive amont. Pour une instance basée sur le fork PMSL, ses modules propres seraient remplacés dès qu'une version amont postérieure à 1.1.0 sort | P2, **préexistant**, hors rail 1 | À décider par l'équipe |
| N4 | Trois tests d'audit exerçaient le pickle en mode par défaut sous un nom suggérant les entrées réseau | P3 | Clarifiés (intitulés et docstrings) ; le test Connecthys vérifie maintenant le chemin réseau en mode strict |

Aucun défaut ni incompatibilité n'a été détecté dans les corrections du rail 1 elles-mêmes.

## 12. Décision

### **RAIL 1 NON QUALIFIÉ POUR MERGE À CE STADE**

Aucun défaut ni incompatibilité n'a été trouvé dans le rail 1. La décision reste négative parce que deux conditions fixées par la mission ne peuvent pas être remplies depuis l'environnement d'analyse. **Bloqueurs exacts :**

1. **Version Connecthys de production non relevée** (stop-gate de la section 2). La compatibilité est prouvée pour toutes les versions publiées et pour le fork PMSL actuel, mais pas pour l'instance réellement déployée. Action : relever `get_version` et les 5 empreintes (quelques minutes).
2. **Recette Windows manuelle non exécutée** (section 9). Le build Windows réussit et démarre, mais aucun scénario métier n'a tourné sous Windows. Action : dérouler le tableau A à E.

**Ce qui n'est PAS un bloqueur** : les 36 échecs de tests (préexistants et identiques à la RC2), l'épinglage de ReportLab (non nécessaire pour le correctif), la mise à jour automatique de Connecthys (à décider).

Si les deux actions donnent le résultat attendu, le rail 1 peut passer en validation humaine avant fusion. **Pas de fusion et pas de rail 2 tant que cette validation n'est pas donnée.**
