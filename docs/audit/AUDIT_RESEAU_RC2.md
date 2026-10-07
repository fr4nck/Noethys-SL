# Audit exhaustif des entrées / sorties réseau — Noethys-SL 0.1.0 RC2

> **Phase 1 : audit uniquement.** Aucun fichier de production (`noethys/`) n'a été modifié.
> Les seuls ajouts sont ce rapport et des tests de caractérisation `tests/test_audit_reseau_*.py`.
> Un test de caractérisation **vert signifie « comportement actuel reproduit »** (y compris lorsqu'il est défectueux).
> Ils devront être inversés au fur et à mesure des corrections.
> Aucun secret réel n'est reproduit dans ce document.

---

## 1–4. Identification

| Élément | Valeur |
|---|---|
| Dépôt audité | `fr4nck/Noethys-SL` |
| Branche auditée | `rc/noethys-sl-0.1.0-rc.2` |
| HEAD exact | `91d9e625d96c5a1460d42dda053db509fa28d181` (« docs: aligner la recette Aujourd’hui sur l’ergonomie validée », 07/10/2026 17:30 +0200) |
| Branche de travail de l'audit | `claude/noethys-sl-network-audit-6r5tup` (= HEAD RC2 + tests + ce rapport) |
| Date de l'audit | 07/10/2026 |
| Environnement de test | Linux, Python 3.13.16, wxPython 4.2.2 (GTK3, sous Xvfb), sans Internet. Le build Windows de la RC2 utilise Python **3.10** et wxPython 4.2.5. |

---

## 5. Historique et PR pertinentes — ce qui est réellement dans la RC2

Vérifié dans Git (ascendance, `git show`, et présence ligne à ligne des ajouts de chaque PR dans HEAD).

| PR | État GitHub | Présence dans la RC2 (HEAD) |
|---|---|---|
| #376 Stabiliser Mailer et progression Connecthys | fusionnée (`f4c4cef`, via `release/noethys-sl-0.1.0`, ancêtre de RC2) | **Présente** : `_FormateErreurMessagerie`, `wx.CallAfter` pour jauge/image/journal Connecthys. Ne couvre pas `MAJ_bouton` (→ CNX-14). |
| #378 Isoler les appels wx du thread d'import Nomadhys (#377) | fusionnée (`7e9b0f6`) | **Présente** : `AppelSynchroneUI`, `EstVivant` dans `DLG_Synchronisation_donnees.py`. |
| #387 Mailer Connecthys : dépendance Mailjet, Python 3, confirmation | fermée sans merge | Contenu **couvert** par #388/#393 (gestion d'erreur Python 3 réalisée autrement : `_FormateErreurMessagerie`, garde `six.PY2`). Rien ne manque. |
| #388 Consolidation #387 sur #376 | fermée sans merge | **100 % des lignes ajoutées présentes** dans HEAD (16 fichiers, dont `UTILS_Envoi_email.py` 132/132, `DLG_Mailer.py` 22/22, tests Mailjet). |
| #393 Correctif Mailjet qualifié | fusionnée (`e4a0694`) | **Présente** (Base64Content ASCII, cycle de vie ProgressDialog Mailjet). |
| #397 Import Connecthys `models.py` (RC1) | fermée sans merge | **Réintégrée par #413** (`63a0715`) : `ChargeModuleModels` présent, `UTILS_Portail_synchro.py` identique à `31fa7ff`. |
| #404 Parent de `SafeYield` (pièces portail) | fermée sans merge | **Présente** (`DLG_Saisie_portail_demande.py:1594-1595`) + test `bea7ecd`. |
| #406 / #413 Réintégration RC2 | #413 fusionnée | Commits `723f2e8…f310439`, `bea7ecd` présents. |
| Commits récents réseau | — | `964fc64` (parent ProgressDialog Mailer), `4dccd87`/`a2b9d1c`/`4fbcdbb` (envoi email **unitaire** hors thread wx), `b6d078a`/`813c7e4` (progression Connecthys) : **présents**. |
| #355 (secrets mailbox Windows), #369 (session-attendance) | ouvertes vers `master` | **Absentes** de la RC2. |

**Réception de messages / PMSL Sync** : la RC2 ne contient **ni IMAP, ni POP, ni PMSL Sync / ReturnSync, ni client mailbox interdomaines** (grep exhaustif négatif). Ces modules existent sur `master` (`UTILS_PMSL_Sync.py`, `UTILS_PMSL_ReturnSync.py`, `UTILS_Interdomain_Mailbox_Client.py`, `DLG_PMSL_Synchronisation.py`) mais **ne font pas partie de la RC2** et sont hors périmètre.

### État des tests et de la CI

- **CI de la RC2** : le seul workflow déclenché sur la branche (`noethys-sl-windows.yml`) fait `compileall` + contrôles de visuel/version + build PyInstaller + démarrage 12 s. **Aucun test unitaire n'y est exécuté.** Les tests réseau existants (Mailer, Mailjet, Connecthys, Nomadhys, SafeYield) ne sont lancés par **aucun** workflow sur cette branche. Dernier run : succès (`eda554c`, 07/10/2026).
- **Suite locale complète** (hors tests d'audit), sous Xvfb : **622 passés, 36 échoués, 1 xfail**.
  - 29 échecs Mailjet (`test_vanilla_mailjet_*`) : `Base_messagerie.__init__` lit `UTILS_Parametres` → `GestionDB.py:101` `TypeError` sans profil Noethys local. Tests **dépendants de l'environnement**, jamais exécutés en CI.
  - 4 échecs `test_ephemerides*` : tests non mis à jour après l'évolution du panneau « Aujourd'hui » (`NameError CTRL`, attribut `book`, signature `Settings`).
  - 1 échec AUI (`LoadPerspective(restoreminimize=…)`, dépend de la version wx), 2 échecs conventions.
- **Tests d'audit ajoutés** : **151 tests + 13 sous-tests, tous verts**, sans Internet, en ~21 s.

---

## 6. Carte des frontières réseau

```
                                   ┌────────────────────────────── INTERNET / LAN ──────────────────────────────┐
                                   │                                                                            │
 ┌──────────── Poste Noethys-SL ───┴───────┐                                                                    │
 │                                         │  SMTP 25/587 (STARTTLS non vérifié) ─────────► Serveur SMTP client  │
 │  DLG_Mailer / UTILS_Envoi_email ────────┼─ HTTPS 443 (mailjet_rest) ───────────────────► api.mailjet.com     │
 │  UTILS_Sauvegarde / Rapport_bugs ───────┤                                                                    │
 │  DLG_Envoi_sms ─────────────────────────┼─ HTTPS (requests, sans timeout) ─────────────► Mailjet SMS / OVH / Brevo
 │                                         │                                                                    │
 │  Connecthys (UTILS_Portail_*) ──────────┼─ FTP 21 en clair │ SFTP 22 (AutoAddPolicy) ──► Hébergement portail │
 │   · config.py ↑  · models.py ↓ (exec)   │─ HTTP(S) /syncup /syncdown /update /upgrade /repairdb /cleardb      │
 │   · export .crypt ↑ · demandes JSON ↓   │   (jeton journalier dans l'URL, sans timeout)                      │
 │   · pièces ↓ (pickle possible)          │─ HTTPS github.com/Noethys/Connecthys/archive/master.zip (install)  │
 │                                         │                                                                    │
 │  Nomadhys                               │◄─ TCP 8000 (Twisted, 0.0.0.0, SANS authentification) ◄── Tablettes  │
 │   · CTRL_Serveur_nomade (entrant)       │─ FTP 21 en clair ─────────────────────────────► Répertoire FTP     │
 │   · DLG_Synchronisation (FTP)           │                                                                    │
 │                                         │                                                                    │
 │  GestionDB (mode réseau) ───────────────┼─ MySQL 3306 (TLS non imposé, sans timeout) ──► Serveur MariaDB     │
 │  UTILS_Sauvegarde (mysqldump/mysql) ────┤                                                                    │
 │                                         │                                                                    │
 │  « Aujourd'hui » (CTRL_Ephemeride) ─────┼─ HTTPS (thread + CallAfter, 8 s) ────────────► geo.api.gouv.fr, open-meteo.com
 │  UTILS_Vacances ────────────────────────┼─ HTTPS 5 s ──────────────────────────────────► data.gouv.fr        │
 │  UTILS_Pes / UTILS_Prelevements (XSD) ──┼─ HTTP en clair, sans timeout ────────────────► noethys.com        │
 │  UTILS_Gps / Distances_villes ──────────┼─ HTTP en clair ──────────────────────────────► maps.google(apis).com
 │  DLG_Controle_referentiel ──────────────┼─ HTTP(S) Customize, sans timeout ────────────► référentiel externe │
 │  DLG_Enregistrement ────────────────────┼─ HTTPS 5 s ──────────────────────────────────► noethys.com        │
 │  webbrowser / LanceFichierExterne ──────┼─ (navigateur système, pas de requête applicative)                 │
 │  DLG_Updater ───────────────────────────┼─ (code mort dans la RC2 : ouvre seulement la page Releases)        │
 └─────────────────────────────────────────┘                                                                    │
                                   └────────────────────────────────────────────────────────────────────────────┘
```

**Aucun mécanisme de réception d'email** (IMAP/POP) dans la RC2. Les seuls flux **entrants** sont :
(1) le serveur TCP Nomadhys, (2) les fichiers déposés par les tablettes sur FTP, (3) les demandes du portail Connecthys (tirées par `syncdown`), (4) les pièces des familles (tirées depuis `pieces/`), (5) `models.py` téléchargé puis exécuté.

---

## 7. Tableau des flux identifiés

Légende : TO = timeout ; UI = thread principal wx ; W = thread worker ; « — » = absent.

| # | Flux | Fichier : fonction | Sens / protocole / destination | Auth | Données / PII / secrets | TO | Chiffrement / validation | Retry / idempotence | Thread | État local avant → après |
|---|---|---|---|---|---|---|---|---|---|---|
| E1 | Envoi SMTP (moteur `smtp`) | `UTILS_Envoi_email.SmtpV2.Connecter/Envoyer` → `Outils/mail/smtp.py` | sortant, SMTP, hôte/port saisis (25/587 ; 465 impossible : `use_ssl=False` l.600) | login/mdp | MIME complet, factures, PJ ; PII oui ; mdp SMTP | 20 s Mailer, 10 s test, 180 s sauvegarde, **— rapport de bug, — SMS-mail** | STARTTLS **sans contexte → CERT_NONE** ; TypeError en Py ≥ 3.12 | 1 retry auto sur `SMTPServerDisconnected` ; **non idempotent** (nouveau Message-ID) | W si envoi unitaire visible ; **UI** sinon | rien → historique (cat. 33) en fin de lot ; `recus`, `avis_depot`, `email_date` par appelants |
| E2 | SMTP obsolète | `SmtpV1` (l.524-586), `DLG_Traductions.EnvoyerEmail` | idem | idem | idem | 150 s (Traductions) | idem | — | UI | code mort / cassé (imports Py2) |
| E3 | Mailjet Send v3.1 | `UTILS_Envoi_email.Mailjet` (l.819-1013) | sortant, HTTPS api.mailjet.com:443 | Basic clé/secret | JSON, PJ base64 ; PII ; clé API | **non transmis** (défaut lib 60 s) | TLS vérifié (sauf CNX-06) | lib : 3 retries POST (version non épinglée) ; « Réessayer » = nouveau POST | W / UI | idem E1 |
| E4 | SMS via API | `DLG_Envoi_sms.Envoyer` l.1084-1178 | sortant, HTTPS Mailjet v4 / OVH (GET) / Brevo | Bearer / **mdp dans query string** / api-key | n° tél., texte | **—** | TLS vérifié | aucun ; **aucune trace des SMS partis** | UI | rien → rien |
| E5 | SMS via email | `DLG_Envoi_sms.EnvoyerEmail` | via E1/E3, PJ `sms.txt` | — | n° tél. | **—** | idem E1 | — | UI | `sms.txt` dans Temp |
| C1 | Connexion stockage portail | `UTILS_Portail_synchro.Connexion` l.365-419 | sortant, FTP 21 **clair** / SFTP 22 / local | mdp ou clé | — ; mdp FTP/SSH | **—** | FTP : aucun ; SSH : **AutoAddPolicy** | — | W (auto) / UI (manuel) | — ; `SSHClient` jamais fermé |
| C2 | Envoi `config.py` | `Upload_config` l.184-326 | sortant → `application/data/config.py` | via C1 | **SECRET_KEY, URI MySQL+mdp, MAIL_PASSWORD** | — | selon C1 ; chmod **0644** | résultat **ignoré**, renvoie True | W/UI | `Temp/<pid>/config.py` **jamais supprimé** |
| C3 | `models.py` | `Upload_data` l.516-538, `ChargeModuleModels` | entrant ← `application/models.py` | via C1 | code Python | — | **aucune intégrité** ; **exec** dans Noethys | — | W/UI | — |
| C4 | Export montant | `Upload_data` l.494-1620 | sortant, `.crypt` puis `GET /syncup/<n>` | via C1 / aucun jeton sur syncup | base SQLite PII (partiellement chiffrée), certificats PayZen | — | AES-CFB sans MAC | at-least-once ; succès si corps == `"True"` | W/UI | `.db` + `.crypt` **jamais supprimés** → `last_synchro` |
| C5 | Demandes portail | `Download_data` l.1629-1813 | entrant, `GET /syncdown/<jeton>/<curseur>` | **jeton = date + chiffres de secret_key, dans l'URL et imprimé** | demandes, réservations, renseignements, **maj_password** | — | TLS (sauf CNX-06) | curseur ; **pas d'ACK** (stub) ; dédup locale seulement en full_synchro | W/UI | → insertion atomique (1 commit) ; `internet_mdp` mis à jour immédiatement |
| C6 | Commandes distantes | l.1822-1964 | sortant `update/upgrade/repairdb/cleardb/<jeton>` | jeton journalier | — | — | idem | non vérifié | UI/W | — |
| C7 | Pièces des familles | `DLG_Saisie_portail_demande.Traitement_pieces`, `ConnectEtTelechargeFichier` | entrant ← `pieces/<nom>` | via C1 | documents des familles | — | **pickle si non-SV2** ; pas de MAC | — | **UI** (un seul SafeYield avant) | fichier déchiffré laissé dans `portail_temp/` |
| C8 | Installation Connecthys | `UTILS_Portail_installation.Installer` | entrant HTTPS `github.com/Noethys/Connecthys/archive/master.zip` + upload | — / via C1 | code serveur | — | **non épinglé, zip-slip** | **boucle infinie** si taille inconnue | UI | fichiers dans Temp |
| C9 | Contrôle serveur | `UTILS_Portail_controle` | SSH exec / local `Popen(shell=True)` | SSH | commandes | — | AutoAddPolicy | — | UI | kill de tout `python … run.py` |
| C10 | Synchro auto | `CTRL_Portail_serveur.Serveur` | orchestration | — | — | — | — | drapeau `synchro_en_cours` (try/finally) | **W non démon** ; `MAJ_bouton` hors UI | — |
| N1 | Serveur direct Nomadhys | `CTRL_Serveur_nomade.Echo` (Twisted wxreactor) | **entrant** TCP 8000, **0.0.0.0** | **aucune** (filtre IP optionnel par préfixe) | ↓ export complet (individus, photos, `familles`, `utilisateurs`…) ; ↑ fichiers d'actions | — | **clair par défaut** (chiffrement seulement si `synchro_cryptage_activer`) | pas d'ACK au client | reactor (UI) + thread d'export qui écrit sur le transport | fichier écrit sous un **nom choisi par le client** |
| N2 | FTP Nomadhys | `DLG_Synchronisation.RecevoirFTP` l.715-768, `On_outils_purger_ftp`, `UTILS_Export_nomade` l.294 | bidirectionnel FTP 21 **clair** | login/mdp (base64 dans Config.json) | fichiers d'actions / export | **—** | aucun | **suppression distante inconditionnelle** | UI | `.dat` local → archivage `.archive` + `nomade_archivage` après import manuel |
| N3 | Import Nomadhys | `DLG_Synchronisation_donnees.Traitement` | local (données reçues) | — | consommations, mémos | — | — | 1 sauvegarde par action | W + `AppelSynchroneUI` | commit par action ; archivage du fichier en fin |
| D1 | MySQL réseau | `GestionDB.GetConnexionReseau` l.995-1035 | sortant MySQL 3306 | user/mdp (base64 dans Config.json) | toute la base | **—** (ni connect ni read) | TLS **jamais imposé** ; hostname non vérifié | aucune ; **commit par requête**, exceptions avalées | UI | — |
| D2 | mysqldump / mysql | `UTILS_Sauvegarde` l.127-176, 340-397 | sortant via binaire | `logintemp.cnf` en clair (umask) | base | — | idem D1 | `--single-transaction` | UI | fichier supprimé en `finally` |
| D3 | Utilisateurs MySQL | `DLG_Saisie_utilisateur_reseau` l.291-338 | SQL `CREATE USER … IDENTIFIED BY '<mdp>'` | — | **mdp dans la requête** | — | — | échec non détecté | UI | requête imprimée dans `journal.log` en cas d'erreur |
| O1 | « Aujourd'hui » météo/géocodage | `CTRL_Ephemeride` + `UTILS_Ephemerides.read_url` | sortant HTTPS geo.api.gouv.fr, open-meteo | — | ville, CP, coordonnées de la structure | 8 s/opération | TLS (sauf CNX-06) ; https imposé ; 2 Mo max | cache si même clé | **W + CallAfter** (correct) | cache dans Config |
| O2 | Calendrier scolaire | `UTILS_Vacances.Calendrier` | HTTPS data.gouv.fr | — | — | 5 s | TLS | `except` nu → `{}` | UI | — |
| O3 | Schémas XSD PES/SEPA | `UTILS_Pes.ValidationXSD`, `UTILS_Prelevements.ValidationXSD` | **HTTP clair** noethys.com | — | — | **—** | aucune empreinte | `except` → **True** | UI | zip extrait dans Temp |
| O4 | Google Maps géocodage / distances | `UTILS_Gps`, `UTILS_Distances_villes`, `UTILS_Stats_individus` | **HTTP clair**, sans clé API | — | adresse organisateur ; **CP/villes des individus** | 5/10 s | aucun | `except` nu | UI | `organisateur.gps` réécrit à `None` |
| O5 | Référentiel | `DLG_Controle_referentiel` | URL Customize | — | **nom/prénom dans l'URL** | — | selon URL | — | UI | — |
| O6 | Enregistrement | `DLG_Enregistrement` | HTTPS noethys.com | identifiant/code dans l'URL | — | 5 s | TLS | — | UI | — |
| O7 | Navigateur | `webbrowser.open`, `LanceFichierExterne` | lancement navigateur | — | — | — | URL en http:// pour 3 dialogues | — | UI | — |
| O8 | Mise à jour | `DLG_Updater`, `Noethys.RechercheMAJinternet` | **neutralisé** (return False ; ouvre la page Releases) | — | — | — | code mort : exe http sans signature | — | — | — |

---

## 8–14, 17. Anomalies

Les constats communs à plusieurs domaines ont été **fusionnés** (X-xx). Les identifiants des audits de domaine (EMAIL-, CNX-, NOM-, NET-, DB-, SEC-) sont conservés en référence.

Statut de preuve : **CONFIRMÉ** = reproduit par un test d'audit ou lecture de code non ambiguë ; **PROBABLE** = raisonnement solide non exécuté contre un vrai serveur ; **À PROUVER** = dépend d'un élément non disponible (code serveur Connecthys, Windows, tablette Nomadhys).

### Synthèse

| P | Nb | Identifiants |
|---|---|---|
| **P0** | 7 | X-01, X-02, CNX-03, NOM-01, NOM-02, NOM-03, CNX-16 (À PROUVER) |
| **P1** | 23 | X-03…X-08, EMAIL-03, EMAIL-04, EMAIL-07, EMAIL-10, CNX-07, CNX-08/09, CNX-10, CNX-11, CNX-14, CNX-17, NOM-04, NOM-05, NET-02, DB-05/06, DB-07, SEC-14, SEC-01 |
| **P2** | ~30 | voir tableau P2 |
| **P3** | ~20 | voir tableau P3 |

---

### P0 — Perte/corruption, exécution de contenu distant, validation crypto neutralisée à impact critique

#### X-01 — Désérialisation `pickle` de fichiers reçus du réseau → exécution de code — P0 — CONFIRMÉ
*(CNX-01, SEC-06, NOM « ancien format »)*
- **Où** : `noethys/Utils/UTILS_Cryptage_fichier.py:166-173` `DecrypterFichier` : tout fichier ne commençant pas par `SV2` passe par `pickle.load`, **avant** toute vérification de mot de passe.
- **Points d'entrée réseau** :
  1. pièces des familles téléchargées depuis Connecthys (`DLG_Saisie_portail_demande.py:1609`) ;
  2. fichiers `.nsc` Nomadhys reçus par FTP (`DLG_Synchronisation.py:61`) ou par le **serveur TCP sans authentification** (N1) ;
  3. restauration de sauvegarde (`DLG_Restauration.py:60`, entrée locale).
- **Reproduction** : `test_audit_reseau_connecthys.py::CryptageFichierTests::test_fichier_non_sv2_deserialise_par_pickle`, `test_audit_reseau_nomadhys.py::CryptageTests::test_ancien_format_deserialise_pickle_du_fichier_recu`, `test_audit_reseau_secrets.py` (SEC-06) : une charge bénigne s'exécute.
- **Impact réel** : exécution de code arbitraire sur le poste Noethys (accès complet à la base). Chemin le plus court : un appareil du LAN envoie un `.nsc` au serveur Nomadhys (aucune authentification, NOM-01), puis l'utilisateur analyse le fichier. Côté portail : il suffit de contrôler un fichier de `pieces/` (portail compromis, FTP clair X-04, SFTP sans clé X-02). *À PROUVER* : que Connecthys stocke parfois une pièce sans la rechiffrer.
- **Attendu** : aucun `pickle.load` sur un contenu externe ; refuser tout format non `SV2` pour les fichiers reçus (conserver l'ancien format uniquement derrière une action explicite, hors réseau).

#### X-02 — Clé d'hôte SSH jamais vérifiée (`paramiko.AutoAddPolicy`) — P0 — CONFIRMÉ
*(CNX-02, SEC-11)*
- **Où** : `UTILS_Portail_synchro.py:392-393` (`Connexion`), `UTILS_Portail_controle.py:47-48` (`OpenSSHConnec`). Aucun `load_system_host_keys` / `known_hosts` : une clé **nouvelle ou modifiée** est acceptée silencieusement à chaque connexion.
- **Reproduction** : `test_audit_reseau_connecthys.py` (`test_ssh_autoaddpolicy_*`, `test_ssh_controle_autoaddpolicy`).
- **Impact** : un attaquant en position d'interception obtient le mot de passe SSH, reçoit `config.py` (tous les secrets du portail) et peut injecter `models.py` (CNX-03, exécuté dans Noethys) ou une pièce (X-01). Classé P0 parce que la validation neutralisée débouche sur une exécution de code.
- **Attendu** : `RejectPolicy` + empreinte épinglée en configuration, confirmation explicite à la première connexion, alerte bloquante si la clé change.

#### CNX-03 — `models.py` téléchargé puis exécuté (`exec`) sans contrôle d'intégrité — P0 — CONFIRMÉ
- **Où** : `UTILS_Portail_synchro.py:421-492` `ChargeModuleModels` (appel l.534). Hérité de #397 ; le mécanisme de chargement a changé, pas le niveau de confiance.
- **Reproduction** : tests existants `ChargeModuleModelsTests` + `test_audit_reseau_connecthys.py::UploadDataReponsePerdueTests` (un `models.py` déposé est exécuté).
- **Impact** : quiconque peut écrire `application/models.py` (portail compromis, FTP clair, SFTP sans clé) exécute du code dans Noethys.
- **Attendu** : modèle embarqué et versionné dans Noethys, ou signature vérifiée.

#### NOM-01 — Serveur Nomadhys : export complet des données à tout client du réseau, sans authentification — P0 — CONFIRMÉ
- **Où** : `Ctrl/CTRL_Serveur_nomade.py` : `reactor.listenTCP(port, factory)` l.235 **sans `interface=`** (toutes interfaces) ; `Echo.dataReceived` l.132-144 : la commande brute `recevoir` déclenche `GenerationFichier` → `UTILS_Export_nomade.Export.Run()` puis l'envoi du fichier. Seul un filtre IP **optionnel**, par préfixe de chaîne (`IsIPinListe` l.105-112 : `192.168.1.1` autorise `192.168.1.100`).
- **Données** : individus avec photos, informations, titulaires, tables `familles`, `utilisateurs`, `consommations`, `memo_journee`, `comptes_payeurs`… (`UTILS_Export_nomade.py:159-232`). Chiffrement **seulement si** `synchro_cryptage_activer` (l.245), désactivé par défaut. Combiné à SEC-14 (mots de passe utilisateurs en clair dans `utilisateurs.mdp`), un export peut contenir des mots de passe.
- **Reproduction** : `test_audit_reseau_nomadhys.py::ServeurTCPTests::test_recevoir_sans_authentification_declenche_l_export`, `ServeurSourceTests::test_ecoute_toutes_interfaces_sans_interface_explicite`, `test_export_contient_tables_sensibles`.
- **Impact** : fuite massive de données personnelles (mineurs, santé, familles) à tout appareil du LAN (Wi-Fi invité, poste compromis), ou d'Internet si le port est redirigé (mode « Internet » de la synchro).
- **Attendu** : authentification mutuelle (secret partagé appareil + défi), chiffrement obligatoire, écoute limitée à l'interface choisie, filtre IP exact (CIDR).
- **Condition** : actif seulement si `synchro_serveur_activer` (Noethys.py:513-516).

#### NOM-02 — Serveur Nomadhys : écriture/écrasement de fichier arbitraire par un client — P0 — CONFIRMÉ
- **Où** : `CTRL_Serveur_nomade.py:155-157` : `open(UTILS_Fichiers.GetRepSync(nom), "wb")` avec `nom` fourni par le client dans l'en-tête JSON, sans assainissement.
- **Reproduction** : `test_nom_de_fichier_client_permet_l_ecriture_hors_sync` (`../`), `test_nom_absolu_ecrase_un_fichier_arbitraire` (fichier existant tronqué dès l'en-tête).
- **Impact** : corruption ou remplacement de tout fichier inscriptible par l'utilisateur Windows (base `.dat` locale, `Config.json`, scripts de démarrage…), sans authentification.
- **Attendu** : `os.path.basename` + liste blanche du motif `actions_<IDfichier>_<horodatage>.(nsc|nsd)` + taille maximale.

#### NOM-03 — Synchro FTP Nomadhys : fichier distant supprimé même si l'analyse locale a échoué → perte définitive silencieuse — P0 — CONFIRMÉ
- **Où** : `Dlg/DLG_Synchronisation.py:752-765` `RecevoirFTP` : la boucle appelle `AnalyserFichier(...)` puis **`ftp.delete(nomFichier)` sans tester `resultat`**. Or `AnalyserFichier` (l.43-80) **supprime le `.nsc` local avant de savoir si le déchiffrement a produit un zip valide** (l.62), et renvoie `False` sans message en cas de mauvais mot de passe, taille incorrecte ou zip invalide.
- **Reproduction** : `RecevoirFTPTests::test_echec_dechiffrement_puis_suppression_distante_perte_totale` : fichier chiffré avec un autre mot de passe → supprimé à distance, supprimé localement, aucun `.dat`, **aucun message**. Idem pour un transfert tronqué (taille ≠) : `test_taille_incorrecte_supprime_le_fichier_local` + suppression distante.
- **Impact** : les pointages / consommations / mémos saisis sur la tablette sont perdus définitivement (seule copie supprimée des deux côtés), cas réaliste après un changement de mot de passe de chiffrement ou une coupure.
- **Attendu** : ne supprimer à distance qu'après un `AnalyserFichier` réussi, idéalement après import et archivage ; conserver l'original en quarantaine en cas d'échec ; signaler l'échec.

#### CNX-16 — Connecthys : perte possible de demandes côté serveur entre `syncdown` et `syncup` — P0 — À PROUVER
- **Où** : `UTILS_Portail_synchro.py:1417-1434`, 1510-1512 (`Upload_data`) : l'export renvoie la table `actions` des N derniers mois et `tables_modifiees_synchro`. `Synchro_totale` exécute `syncdown` **avant** `syncup` (l.138).
- **Mécanisme** : si le serveur **remplace** sa table `actions` par l'export, une demande déposée par une famille entre les deux appels est effacée sans avoir été téléchargée.
- **À prouver** : lire le traitement `syncup` du code serveur Connecthys (absent du dépôt).

---

### P1

#### X-03 — Vérification TLS désactivée pour **tout le processus** par l'option Connecthys `accept_all_cert` — P1 — CONFIRMÉ
*(NET-01, SEC-09, CNX-06)*
- **Où** : `UTILS_Portail_synchro.py:100-102` : `ssl._create_default_https_context = ssl._create_unverified_context`. Jamais restauré, même si une instance suivante est créée avec `False`.
- **Effet** : sous Python 3.10/3.11 (build Windows) tous les `urllib` HTTPS du processus perdent la validation : « Aujourd'hui », calendrier scolaire, enregistrement, `urlretrieve` de l'installation Connecthys (`master.zip`, code ensuite déployé). `requests` (SMS, Mailjet) n'est pas touché. Sous 3.12+, l'effet dépend de l'ordre des appels.
- **Reproduction** : `test_audit_reseau_divers.py::ContexteTLSGlobal` (dont un test sous `python3.11`), `test_audit_reseau_connecthys.py::test_accept_all_cert_desactive_tls_pour_tout_le_processus`, `test_https_certificat_autosigne`, `test_audit_reseau_secrets.py` (SEC-09).
- **Attendu** : contexte SSL local passé à `urlopen(context=…)` pour Connecthys uniquement, idéalement avec empreinte épinglée.

#### X-04 — FTP en clair (Connecthys et Nomadhys) — P1 — CONFIRMÉ
*(CNX-04, NOM « aucun timeout ni TLS », SEC-10 partie transport)*
- **Où** : `UTILS_Portail_synchro.py:380`, `UTILS_Portail_installation.py:321`, `DLG_Synchronisation.py:248, 635, 730, 754`, `UTILS_Export_nomade.py:294`.
- **Effet** : identifiants FTP, `config.py` (SECRET_KEY, mot de passe MySQL, mot de passe SMTP), `models.py`, exports, pièces, fichiers d'actions transitent en clair. Passe à **P0** dès que le FTP traverse Internet.
- **Reproduction** : `test_ftp_en_clair_sans_timeout` (Connecthys), `RecevoirFTPTests::test_aucun_timeout_ni_tls` (Nomadhys).
- **Attendu** : `FTP_TLS` + `prot_p()` ou SFTP avec clé vérifiée ; abandon du FTP.

#### X-05 — SMTP : STARTTLS sans validation de certificat — P1 — CONFIRMÉ
*(EMAIL-02, SEC-12)*
- **Où** : `Outils/mail/smtp.py:68` (`starttls(keyfile=…, certfile=…)` sans `context`), `UTILS_Envoi_email.py:541` (SmtpV1), `DLG_Traductions.py:383`.
- **Effet** : `ssl._create_stdlib_context()` = `CERT_NONE`, pas de contrôle du nom d'hôte : un intercepteur obtient le mot de passe SMTP et le contenu des factures/reçus.
- **Reproduction** : `test_audit_reseau_emails.py` (EMAIL-02), `test_audit_reseau_secrets.py` (SEC-12).
- **Attendu** : `starttls(context=ssl.create_default_context())`.

#### X-06 — Jeton d'authentification Connecthys dérivé du secret, dans l'URL et dans `journal.log` — P1 — CONFIRMÉ (client) / À PROUVER (portée serveur)
*(CNX-05, SEC-08)*
- **Où** : `UTILS_Portail_synchro.py:1622-1627` `GetSecretInteger` = `AAAAMMJJ` + **tous les chiffres de `secret_key`** ; `print` de l'URL l.1588, 1683, 1844, 1879, 1913, 1947 (stdout → `journal.log` dans l'exécutable, Noethys.py:4616-4617, joignable au rapport de bug).
- **Effet** : jeton valable toute la journée, commun à `syncdown`, `update`, `upgrade`, `repairdb`, **`cleardb`** ; visible dans les journaux du serveur/proxy, en clair si l'URL est `http://` (valeur par défaut `http://127.0.0.1:5000`) ; révèle les chiffres de la clé.
- **Attendu** : HMAC horodaté en en-tête, plus aucun `print` d'URL.

#### X-07 — Secrets du portail laissés sur disque et lisibles sur le serveur — P1 — CONFIRMÉ
*(SEC-10, CNX-12, CNX-13)*
- **Où** : `Upload_config` l.297-302 (`Temp/<pid>/config.py`, jamais supprimé ; seul un arrêt normal purge `Temp`) ; `portail_temp/config.py` ; `import_*.db` (l.547, `os.remove` commenté l.1534) et `.crypt` **à chaque synchro** ; pièces déchiffrées ; `UploadFichier` l.2093-2096 : **`chmod 0644`** sur tout envoi SFTP, y compris `config.py`.
- **Reproduction** : `test_reponse_perdue_puis_nouvel_essai`, `test_config_contient_les_secrets…`, `test_sftp_upload_config_chmod_0644`.
- **Attendu** : `tempfile` 0600, suppression en `finally`, `config.py` en 0600 côté serveur.

#### EMAIL-03 — SMTP : résultat incertain après DATA → **renvoi automatique, doublon** — P1 — CONFIRMÉ
*(cas critique demandé : « serveur accepte, confirmation perdue »)*
- **Où** : `UTILS_Envoi_email.py:666-681` (`SmtpV2.Envoyer_lot`), `DLG_Mailer.py:467-473` (`_ExecuterEnvoiUniqueHorsUI._worker`).
- **Scénario** : le serveur reçoit le message complet (fin de DATA « . ») puis coupe ou se tait jusqu'au timeout (20 s) avant le `250`. `smtplib` lève `SMTPServerDisconnected` ; Noethys reconnecte et **renvoie** le message, avec un **nouveau Message-ID** (aucune déduplication possible côté destinataire).
- **Comportement constaté** (mini-serveur SMTP local) : 2 messages reçus, succès unique déclaré. Si la reconnexion échoue : le message, pourtant reçu, est déclaré **en échec** et « Réessayer » produit le doublon.
- **Impact** : factures, rappels, reçus en double chez les familles ; cas réaliste sur serveur lent.
- **Attendu** : distinguer coupure *avant* fin de DATA (renvoi sûr) et *après* (résultat **incertain**) ; jamais de renvoi automatique dans le second cas ; Message-ID stable entre tentatives ; statut « incertain » dans le compte rendu ; « Réessayer » explicite avec avertissement.

#### EMAIL-04 — Mailjet : timeout → « Réessayer » re-POSTe le même message — P1 — CONFIRMÉ (re-POST) / À PROUVER (dédup Mailjet)
- **Où** : `UTILS_Envoi_email.py:1099-1148`, `Mailjet.Connecter` l.819-831 (`Client` créé **sans** `timeout`). `mailjet-rest` non épinglé dans `requirements.txt` ; la version 1.9.0 retente elle-même les POST (3 fois) et ajoute un `Idempotency-Key` dont la prise en compte par Mailjet n'est pas prouvée.
- **Attendu** : statut « incertain », épinglage de version, `timeout` explicite.

#### EMAIL-07 — Reçu de règlement mémorisé comme envoyé même si l'email échoue (faux succès) — P1 — CONFIRMÉ
- **Où** : `DLG_Saisie_reglement.py:1229` teste `dlg2.listeAnomalies`, **jamais alimenté** par `DLG_Mailer` (affecté seulement l.107) ; `except: pass` l.1232.
- **Effet** : insertion dans `recus` + historique « Edition d'un reçu » sans envoi. **Attendu** : tester `listeSucces`.

#### EMAIL-10 — Connecthys : « Reçu de règlement envoyé par Email » renvoyé à la famille sans vérifier l'envoi — P1 — CONFIRMÉ
- **Où** : `DLG_Saisie_portail_demande.py:1221-1223` : résultat d'`EnvoiEmailFamille` ignoré, `{"etat": True}`.

#### X-08 — SMS : coupure en cours de boucle, aucune trace des SMS partis, faux « terminé » — P1 — CONFIRMÉ
*(EMAIL-11, NET-03, NET-04)*
- **Où** : `Dlg/DLG_Envoi_sms.py:1084-1186`. `requests.post/get` **sans timeout ni try** ; `.json()` non protégés (une 502 HTML lève `JSONDecodeError`) ; message « Envoi des SMS terminé. » placé **entre** le bloc Mailjet et le bloc OVH (l.1112-1116) → affiché **avant** l'envoi OVH/Brevo, puis une seconde fois (l.1180-1184) ; Mailjet tout en échec + « Continuer » → « terminé ».
- **Effet** : erreur réseau au n-ième numéro → n-1 SMS partis, rien d'enregistré, pas de bilan ; relancer = doublons **facturés**. Serveur muet = UI figée sans limite.
- **Reproduction** : `test_audit_reseau_divers.py::EnvoiSMS` (6 tests), `test_audit_reseau_emails.py`.
- **Attendu** : timeout, try par numéro, journal des envois réussis, bilan unique, reprise ciblée, worker.

#### CNX-07 — Connecthys : aucun timeout réseau (HTTP, FTP, SSH) — P1 — CONFIRMÉ
- **Où** : `urlopen` l.1591, 1687, 1848, 1883, 1917, 1951 ; `ftplib.FTP` l.380 ; `ssh.connect` l.396 ; `UTILS_Portail_installation.py:56, 153, 370`.
- **Effet** : serveur muet → thread de fond bloqué indéfiniment avec `synchro_en_cours=True` (plus aucune synchro) ; UI figée pour la synchro manuelle, les pièces, l'installation ; thread **non démon** empêchant la sortie du processus.
- **Reproduction** : `test_serveur_muet_bloque_le_client_au_dela_du_delai`, `test_aucun_timeout_sur_urlopen`.

#### CNX-08 / CNX-09 — Connecthys : doublons de demandes importées — P1 — CONFIRMÉ
- **Où** : `Download_data` l.1641-1656 (curseur lu avant l'appel), l.1716-1722 (`max(IDaction)+1` après), dédup locale seulement en `full_synchro` (l.1735-1737) ; aucune contrainte UNIQUE sur `ref_unique` ; aucun verrou entre synchro manuelle (UI, DPC:2242) et thread de fond, ni entre postes.
- **Effet** : `[(1,'4001'),(2,'4001')]` + 2 réservations (test). Curseur remis à 0 si `ref_unique` non numérique, procédure A9120, anonymisation → dédup entièrement déléguée au serveur. La procédure existante A9052 (« actions du portail en doublon ») confirme l'historique du problème.
- **Impact** : demande traitée deux fois (consommations, paiements) ; rejeu d'un ancien `maj_password` (CNX-29).
- **Attendu** : index unique sur `ref_unique` + insertion conditionnelle ; verrou de synchro partagé en base.

#### CNX-10 — Installation Connecthys : boucle infinie hors ligne — P1 — CONFIRMÉ
- **Où** : `UTILS_Portail_installation.py:448-455` : `num_essai` jamais incrémenté ; `sleep(1)` sur le thread UI. **Attendu** : `num_essai += 1` + timeout.

#### CNX-11 — Installation : archive `master.zip` non épinglée + zip-slip — P1 — CONFIRMÉ
- **Où** : `UTILS_Portail_installation.py:138`, `Dezipper` l.157-183. Code déployé puis exécuté sur le serveur.
- **Attendu** : tag/commit épinglé + SHA-256 ; contrôle `realpath` sous la destination.

#### CNX-14 — Connecthys : widgets wx modifiés depuis le thread worker — P1 — CONFIRMÉ (appel) / PROBABLE (crash)
- **Où** : `CTRL_Portail_serveur.py:131` appelle `Panel.MAJ_bouton` (l.241-280 : `SetLabel`, `SetBackgroundColour`, `taskBarIcon.Connecthys`) depuis le worker. #376 n'a traité que jauge/image/journal.
- **Attendu** : `wx.CallAfter(self.parent.MAJ_bouton)`.

#### CNX-17 — Connecthys : renseignements de famille perdus silencieusement — P1 — CONFIRMÉ
- **Où** : `Download_data` l.1771-1777 `except: pass` sur un renseignement indéchiffrable : l'action est importée **sans** le renseignement, sans message.

#### NOM-04 — Nomadhys : mauvais mot de passe / fichier altéré non détecté, fichier source supprimé — P1 — CONFIRMÉ
- **Où** : `UTILS_Cryptage_fichier.py:110-127` (AES-CFB, clé = MD5 hex sans sel, **sans MAC**) ; `DLG_Synchronisation.AnalyserFichier` l.56-68 supprime le `.nsc` puis échoue sur le zip, laisse un `.nsd` déchet, `return False` sans message.
- **Reproduction** : `CryptageTests::test_mauvais_mot_de_passe_ne_leve_aucune_erreur`, `test_absence_de_mac_alteration_non_detectee`, `AnalyserFichierTests::test_mauvais_mdp_supprime_le_nsc_et_retourne_false`.
- **Cumul** : avec NOM-03 = perte définitive.

#### NOM-05 — Serveur Nomadhys : fichier tronqué analysé sans contrôle de taille, aucun accusé de réception — P1 — CONFIRMÉ (Noethys) / À PROUVER (tablette)
- **Où** : `CTRL_Serveur_nomade.connectionLost` l.208-220 : `AnalyserFichier(nomFichier)` **sans `tailleFichier`** ; aucun ACK renvoyé au client.
- **Reproduction** : `test_fin_de_connexion_analyse_sans_controle_de_taille` (10 octets sur 1 000 000).
- **Impact** : si la tablette considère l'envoi réussi à la fermeture de la socket et purge ses données (À PROUVER côté Nomadhys), les actions sont perdues.
- **Attendu** : vérifier la taille annoncée, renvoyer un ACK applicatif après analyse réussie.

#### NET-02 — Validation XSD PES/SEPA neutralisée silencieusement (faux succès) — P1 — CONFIRMÉ
- **Où** : `UTILS_Pes.py:520-552`, `UTILS_Prelevements.py:778-815` : `except Exception` → **`return True`** (hors ligne, 502 HTML, zip corrompu, `version_sepa` inattendue → `NameError`) ; schéma téléchargé en **HTTP clair** sans empreinte (un intermédiaire peut fournir un XSD permissif) ; `urlretrieve` sans timeout sur l'UI.
- **Impact** : fichier bancaire / Trésor public non validé enregistré sans alerte.
- **Attendu** : XSD embarqués dans le paquet ; statut « validation non effectuée » affiché ; jamais `True` sur erreur.

#### DB-05 / DB-06 — MySQL : écritures multi-requêtes non transactionnelles, erreurs avalées — P1 — CONFIRMÉ
- **Où** : `GestionDB.py:334-372` `ReqInsert`, 444-469 `ReqMAJ`, 471-482 `ReqDEL` (commit par appel, exceptions imprimées puis avalées ; aucun `rollback` dans GestionDB) ; avec `commit=False`, l'échec d'une étape est avalé et le `Commit()` de l'appelant valide un lot partiel. Appelants : `DLG_Saisie_reglement.py:1493-1528`, `CTRL_Ventilation.py:801-807`, `DLG_Factures_generation_selection.py:287-293`.
- **Effet** : coupure réseau MySQL après l'INSERT d'un règlement → règlement validé **sans ventilation**, `Sauvegarde` renvoie `True`.
- **Attendu** : transaction explicite + propagation des erreurs + rollback.

#### DB-07 — Numéros de facture en double possibles en réseau — P1 — PROBABLE
- **Où** : `DLG_Factures_generation_selection.py:223` (`MAX(numero)+1`), 287 ; ni verrou ni contrainte UNIQUE.

#### SEC-14 — Mots de passe des utilisateurs Noethys stockés en clair — P1 — CONFIRMÉ
- **Où** : `DLG_Saisie_utilisateur.py:648, 734`, `Noethys.py:1609` (`utilisateurs.mdp` + SHA256 non salé). Exposés par NOM-01 (export Nomadhys), sauvegardes, exports.

#### SEC-01 — Mot de passe MySQL écrit dans `journal.log` en cas d'échec de `CREATE USER` — P1 — CONFIRMÉ
- **Où** : `GestionDB.py:283` `ExecuterReq` imprime la requête ; `DLG_Saisie_utilisateur_reseau.py:307` (`IDENTIFIED BY '<mdp>'`, SQL concaténé, une apostrophe suffit à provoquer l'échec). `journal.log` peut être joint au rapport de bug.

---

### P2 — Anomalies réelles récupérables

| Id | Statut | Où | Constat | Recommandation |
|---|---|---|---|---|
| EMAIL-01 / SEC-13 | CONFIRMÉ | `Outils/mail/smtp.py:68` | `starttls(keyfile=, certfile=)` → `TypeError` sous Python ≥ 3.12 (paramètres retirés) : tout SMTP STARTTLS impossible, socket laissée ouverte. **Build Windows 3.10 non touché** ; installations source Linux (3.12) touchées. | `starttls(context=…)` (même correctif que X-05). |
| EMAIL-05 | CONFIRMÉ | `smtp.py:126` | Dict des refus partiels de `sendmail` ignoré ; `UTILS_Sauvegarde.py:205` envoie à plusieurs destinataires et affiche « succès ». | Exploiter le retour de `sendmail`. |
| EMAIL-06 / NET-05 | CONFIRMÉ | `DLG_Envoi_sms.py:1129-1133` | Mot de passe OVH dans la query string ; présent dans le texte de `ConnectionError` (non capturée). Secrets SMS en clair dans `parametres` et affichés. | API sans mdp dans l'URL ; message d'erreur nettoyé ; champ masqué. |
| EMAIL-08 | CONFIRMÉ | `DLG_Mailer.py:745-749` | Historique : SQL formaté ; une adresse avec apostrophe lève `OperationalError` **après** envoi réussi (lot non historisé). | Requête paramétrée. |
| EMAIL-09 | CONFIRMÉ | `DLG_Mailer.py:612-613` | PJ communes ajoutées en place à `track.pieces` → doublées au second envoi (« test » puis « envoyer », ou après échec). | `list(track.pieces) + communes`. |
| EMAIL-13 | CONFIRMÉ | `DLG_Mailer.py:713-742`, `UTILS_Envoi_email.py:715-716, 1146-1147` | Lot sur thread UI sans annulation, `sleep` entre messages ; historique écrit **en fin de lot seulement** ; « Arrêter » = aucun compte rendu. Kill du processus → aucun envoi tracé. | Historique au fil de l'eau, worker, compte rendu sur arrêt. |
| EMAIL-14 | CONFIRMÉ | `DLG_Mailer.py:663` | Envoi unitaire **caché** (`EnvoiEmailFamille(visible=False)`, bouton Connecthys) reste sur l'UI (le correctif 4dccd87 exige `IsShownOnScreen`) ; rapport de bug et SMS-mail sans timeout. | Worker pour tous les chemins ; timeout partout. |
| DB-01 | CONFIRMÉ | `GestionDB.py:1007, 1019-1033` | Ni `connect_timeout` ni `read_timeout` MySQL, ouverture sur le thread UI. | Timeouts explicites. |
| DB-02 | CONFIRMÉ (paramètres) / À PROUVER (lib) | `GestionDB.py:62-72` | TLS MySQL jamais imposé, hostname non vérifié. | Option « TLS requis » `VERIFY_IDENTITY`. |
| DB-03 | CONFIRMÉ | `GestionDB.py:998, 145` | Mot de passe contenant `;` → `ValueError`, « connexion impossible ». | Format structuré. |
| SEC-05/07, CNX-26 | CONFIRMÉ | `UTILS_Cryptage_fichier.py:42-48, 110-127` | Clé = MD5 hex sans sel ; AES-CFB **sans MAC** : altération/troncature non détectée (pièce corrompue enregistrée). | PBKDF2/scrypt + AES-GCM. |
| SEC-16 / CNX-20 | CONFIRMÉ | `DLG_Ouvrir_fichier.py:252-275`, `DLG_Portail_config.py:1322-1356, 2093-2122` | Export `.nnc` (mdp MySQL) et `.cfg` Connecthys (tous les secrets) en clair, sans avertissement ; mdp stats copié dans le presse-papiers. | Avertissement + option sans secrets. |
| SEC-17 / EMAIL-18 | CONFIRMÉ | `adresses_mail`, `parametres` (portail, envoi_sms), `Config.json` | Secrets en clair en base ou base64 ; champs non masqués (`DLG_Saisie_email_exp.py:444`). | Coffre OS (DPAPI) — le `SecretProvider` de #355 peut servir de base. |
| SEC-19 / CNX-27 | CONFIRMÉ | `DLG_Portail_config.py:41-45`, `UTILS_Internet.py:58`, UPS:541 | `secret_key`, mots de passe internet, noms d'export générés avec `random`. | Module `secrets`. |
| CNX-15 | CONFIRMÉ | UPS:1579-1615 | **Réponse `syncup` perdue** : Noethys conclut à l'échec ; au second essai un **nouvel** instantané est traité ; aucun doublon dans Noethys, fichiers accumulés côté portail et poste. Idempotence serveur À PROUVER. | Identifiant d'export idempotent + nettoyage. |
| CNX-18 | CONFIRMÉ | UPS:320/326, 592-598, 631, 382 | Échecs d'envoi de `config.py`, fond, logo, documents ignorés ; `last_fond` / `last_synchro` avancent quand même. | Tester les retours. |
| CNX-19 | CONFIRMÉ | UPS:415-417, 2109-2111, 500-1568, 343-344 | `SSHClient` jamais fermé ; connexions non fermées en échec ; pas de `try/finally` dans `Upload_data`. | `finally`. |
| CNX-21 | CONFIRMÉ | `UTILS_Portail_controle.py:189-202` | Arrêt du serveur : tue **tout** `python … run.py`. | Fichier PID. |
| CNX-28 / CNX-29 / CNX-31 / CNX-33 | PROBABLE / CONFIRMÉ | UPS:1615, 1748-1754, DPC:2242-2267, DSPD:958-981 | Fenêtre de modifications perdues (`last_synchro=now()` en fin) ; `maj_password` appliqué sans validation ; synchro manuelle bloquante, « Annuler » sans effet, concurrente du thread ; effet métier et état « validation » dans deux transactions. | Voir rapport détaillé du domaine. |
| NOM-06 | CONFIRMÉ | `DLG_Synchronisation.py:730-748` | Coupure pendant RETR (B) : message trompeur « La connexion FTP n'a pas pu être établie » ; fichiers déjà téléchargés non analysés (orphelins `.nsd/.nsc` invisibles : la liste n'affiche que `.dat`). Rien supprimé à distance → récupérable. | Message précis, analyse des fichiers complets. |
| NOM-07 | CONFIRMÉ (exception) / PROBABLE (doublon) | `DLG_Synchronisation.py:764` | Coupure pendant `DELE` (F) : `EOFError` non interceptée dans le handler wx ; au cycle suivant le même fichier est re-téléchargé et reproposé à l'import alors qu'il a peut-être déjà été importé/archivé. Les actions sont majoritairement « état cible » (consommation, mémo upsert), donc rejeu plutôt idempotent, sauf séquences ajout/suppression. | Suppression distante seulement après archivage ; dédup par nom dans `nomade_archivage`. |
| NOM-08 | CONFIRMÉ | `DLG_Synchronisation.py:623-645` | Purge FTP : si `IDfichier` est vide, **tous** les fichiers de synchro de **toutes** les bases du répertoire sont supprimés. Fréquence d'un IDfichier vide À PROUVER. | Refuser la purge sans IDfichier. |
| NOM-09 | CONFIRMÉ | `DLG_Synchronisation.py:730, 754`, `UTILS_Export_nomade.py:294` | FTP Nomadhys sans timeout, sur le thread UI. | Timeout + worker. |
| NOM-10 | CONFIRMÉ | `CTRL_Serveur_nomade.py:147-193` | Pas de découpage des messages TCP : un morceau de fichier qui est un JSON valide (`b"123"`) est pris pour une commande (`TypeError`) ; `taille=0` → `ZeroDivisionError` dans le reactor. | Protocole à en-tête de longueur. |
| NOM-11 | CONFIRMÉ (appel) / PROBABLE (crash) | `CTRL_Serveur_nomade.py:58-75, 119-128` ; `UTILS_Export_nomade.Run` | `transport.write` appelé depuis le thread d'export (Twisted non thread-safe) ; `wx.MessageDialog(None, …)` possible depuis ce thread en cas d'erreur d'export ; `Export.Run()` renvoyant `None` → `TypeError`. | `reactor.callFromThread`, `wx.CallAfter`. |
| NOM-12 | CONFIRMÉ | `DLG_Synchronisation_donnees.Traitement.run` l.372-480 | Action inconnue → réutilise le `resultat` précédent (**faux succès**, « Sauvegarde » rejouée) ; état inconnu → `UnboundLocalError` qui tue le thread sans bilan. Survient seulement en cas d'incompatibilité de version tablette. | `else` explicite → erreur. |
| NOM-13 | PROBABLE | `Traitement.run` | Coupure/arrêt pendant l'import (D) : chaque action est sauvegardée séparément, le fichier n'est pas archivé → réimport complet ensuite (rejeu, cf. NOM-07). | Archivage par action ou transaction globale. |
| NOM-14 | CONFIRMÉ | `AnalyserFichier` | Un `.nsd` **en clair** est accepté même si le chiffrement est activé (rétrogradation). | Refuser le clair si chiffrement actif. |
| NET-06 | CONFIRMÉ | `DLG_Controle_referentiel.py:191-255` | Sans timeout, UI ; `ParseError` non capturé ; `TypeError` au tri de deux homonymes de même pertinence ; nom/prénom dans l'URL ; HTML non échappé. | Timeout, `sort(key=…)`, `html.escape`. |
| NET-07 | CONFIRMÉ (code) / PROBABLE (refus Google) | `UTILS_Gps.py:18`, `UTILS_Distances_villes.py:52`, `DLG_Organisateur.py:216, 232` | HTTP clair sans clé API (refus probable) ; CP/villes de tous les individus envoyés à Google ; `organisateur.gps` réécrit à `None` à chaque validation. | Retirer ou passer à l'API Adresse HTTPS ; ne pas écraser sur échec. |
| NET-08 | CONFIRMÉ | `UTILS_Vacances.py:22-28` | Erreur réseau = « aucune suggestion » (indiscernable) ; JSON objet → `TypeError` non capturé ; UI. | Erreur explicite. |
| NET-09 | CONFIRMÉ | `CTRL_Ephemeride._load:445-451` | « Aujourd'hui » garde l'ancienne adresse de l'organisateur (réglages mémorisés prioritaires) ; appels réseau même panneau AUI fermé (lecture). | Priorité à `organisateur`, arrêt du timer à la fermeture. |
| NET-10 | CONFIRMÉ (Linux) / À PROUVER (Windows) | `FonctionsPerso.LanceFichierExterne` l.1018-1025 | Linux : `os.system("xdg-open " + x)` sans guillemets (URL tronquées au `&`, injection shell possible via un href HTML affiché) ; Windows : `/` → `\` dans les URL. | `subprocess` en liste / `webbrowser.open`. |
| CI-01 | CONFIRMÉ | `.github/workflows/noethys-sl-windows.yml` | La CI de la RC2 n'exécute **aucun** test ; 36 tests existants échouent localement (dépendance au profil, tests non maintenus). | Job pytest Linux/Xvfb + base fixture. |

### P3 — Dette / faiblesse sans impact opérationnel démontré

| Id | Où | Constat |
|---|---|---|
| EMAIL-12 | `UTILS_Envoi_email.py:430` | PJ `text/*` ouvertes sans `encoding` (cp1252 sous Windows vs `sms.txt` UTF-8) — PROBABLE sous Windows. |
| EMAIL-15 / EMAIL-16 | `UTILS_Envoi_email.py:503-508, 1000-1011` | Erreur Mailjet opaque `'Messages'` + JSON (adresses) dans le journal ; secret contenant `==` → `ValueError`. |
| EMAIL-17 | Rapport_bugs l.377, Sauvegarde l.213, test d'adresse l.717, SMS l.1191 | `Fermer()` hors `finally` (sockets ouvertes ; sauvegarde laissée dans Temp sur échec d'envoi). |
| EMAIL-19 / NET-13 | `SmtpV1`, `DLG_Traductions`, `sendTextMail`, `DLG_Updater`, `UTILS_Meteo`, `UTILS_Icalendar`, `UTILS_Internet` FTP/HTTP, `fetch_bulletins` | Code réseau mort ou cassé (dangereux s'il était réactivé : exe HTTP sans signature, `os.system` non quoté). |
| EMAIL-20 | `DLG_Mailer` | Double clic « Envoyer » : modales probablement protectrices, aucun verrou explicite — À PROUVER. |
| DB-04, DB-08 | `GestionDB.py:1269-1277`, `DLG_Utilisateurs_reseau.py` | Préfixe `#64#` ambigu ; SQL concaténé pour la gestion des comptes MySQL. |
| SEC-15 | `CTRL_Identification.py:57-72` | « Mot de passe du jour » calculable = accès administrateur (héritage amont, **décision produit**). |
| SEC-20 | `UTILS_Sauvegarde.py:505-511` | `logintemp.cnf` dépendant de l'umask, valeur non quotée — À PROUVER. |
| CNX-22 | DPC:2215-2235 | Messages « Upgrade/Réparation/Effacement effectué » jamais affichés (résultat perdu). |
| CNX-23, CNX-24, CNX-25 | UPC:131, UPS:2023, UPS:1606 | `Popen(shell=True)` avec liste ; `chdir("../../")` faux ; `b"True\n"` traité comme échec. |
| CNX-30, CNX-32, CNX-34 | UPS:1622, 1595-1700 ; CPS:483-488 | Jeton dépendant de la date locale (minuit) ; causes d'erreur absentes du journal ; `CallAfter` possible sur panneau détruit à la fermeture. |
| NOM-15 | `CTRL_Serveur_nomade.py` | Écoute 0.0.0.0, filtre IP par préfixe, `StopServer` jamais appelé. |
| NET-11, NET-12, NET-14, NET-15, NET-16 | `DLG_Enregistrement`, `UTILS_Aide`, URL `fr4nck/Noethys`, timeouts urllib, `ElementTree` | Appel au service amont dès l'ouverture, code licence non encodé ; URL du canal du fork à vérifier ; timeouts urllib ne bornant pas le DNS ; parsing XML distant. |

---

## 10. Matrice générale de panne (protocoles principaux)

| Panne | SMTP (E1) | Mailjet (E3) | SMS API (E4) | Connecthys HTTP (C4–C6) | Connecthys FTP/SFTP (C1–C3, C7) | Nomadhys TCP (N1) | Nomadhys FTP (N2) | MySQL (D1) |
|---|---|---|---|---|---|---|---|---|
| DNS impossible | erreur affichée, pas de fuite | erreur | **exception non capturée** | `False`, cause absente du journal | `False` | n/a (entrant) | message générique | « connexion impossible » |
| Connexion refusée | erreur | erreur | exception non capturée | `False` | `False` | — | message générique | idem |
| Timeout / serveur muet | 20 s (Mailer), **illimité** (rapport de bug, SMS-mail) | 60 s (lib) | **illimité, UI figée** | **illimité** (worker bloqué, `synchro_en_cours` reste vrai) | **illimité** | aucun délai de session | **illimité, UI** | **délai TCP OS, UI** |
| Auth refusée | erreur sans fuite de mdp | erreur | exception / JSON | `False` | `False` | **aucune auth** | message générique | message pilote, sans mdp |
| Certificat invalide | **accepté** (CERT_NONE) | refusé (requests, non affecté par X-03) | refusé | refusé ; **accepté pour tout le processus** si `accept_all_cert` | n/a | n/a | n/a | **non vérifié** |
| Clé SSH inconnue | n/a | n/a | n/a | n/a | **acceptée** | n/a | n/a | n/a |
| Clé SSH modifiée | n/a | n/a | n/a | n/a | **acceptée silencieusement** | n/a | n/a | n/a |
| Coupure avant émission | erreur, renvoi sûr | erreur | exception (rien envoyé) | `False` | `False` | fichier partiel | message trompeur | erreur avalée |
| Coupure pendant émission | reconnexion + renvoi | retry lib | n-1 SMS partis non tracés | `.crypt` orphelin | STOR partiel | **analysé sans contrôle de taille** | orphelins locaux | **écriture partielle validée** (DB-05) |
| Opération distante réussie + confirmation perdue | **renvoi auto → doublon** (EMAIL-03) | « Réessayer » → doublon probable (EMAIL-04) | relance → **doublons facturés** | syncup **retraité** (CNX-15) ; syncdown re-téléchargé (dédup serveur) | — | client sans ACK (À PROUVER tablette) | DELE échoue → **réimport** (NOM-07) | commit fait, erreur côté client (rare) |
| HTTP 4xx | n/a | exception | **JSONDecodeError** possible | `False` | n/a | n/a | n/a | n/a |
| HTTP 5xx | n/a | retry lib | JSONDecodeError (HTML) | `False` | n/a | n/a | n/a | n/a |
| Réponse invalide | n/a | erreur opaque `'Messages'` | exception | `False` ; forme JSON inattendue → `TypeError` rattrapé plus haut | n/a | `TypeError` / `ZeroDivisionError` | zip invalide → `False` silencieux | n/a |
| Contenu tronqué | n/a | n/a | n/a | `False` | **pièce corrompue enregistrée** (pas de MAC) | **analysé** | taille vérifiée → fichier supprimé **et supprimé à distance** (NOM-03) | n/a |
| Contenu corrompu / malveillant | n/a | n/a | n/a | renseignements perdus en silence (CNX-17) | **pickle → exécution de code** (X-01), `models.py` exécuté (CNX-03) | **écriture de fichier arbitraire** (NOM-02), pickle | pickle (X-01) ; mauvais mdp → **perte** | n/a |
| Seconde tentative utilisateur | doublon si 1er accepté | doublon | doublons | doublons si concurrence (CNX-08) | réécriture | — | réimport | doublon de numéro de facture (DB-07) |

### Nomadhys — coupures A à F

| Moment | Ce qui se passe à la reprise | Risque |
|---|---|---|
| A. avant transfert | rien n'est modifié ; message générique | aucun |
| B. pendant transfert (FTP) | exception → message « connexion impossible » ; fichiers déjà reçus non analysés (orphelins invisibles) ; rien supprimé à distance → re-téléchargés au cycle suivant | aucune perte ; orphelins locaux |
| B. pendant transfert (TCP) | `connectionLost` analyse le fichier partiel sans contrôle de taille → zip invalide → `False` silencieux ; pas d'ACK | **perte si la tablette purge** (À PROUVER) |
| C. après transfert, avant import | FTP : **fichier distant déjà supprimé** ; seul le `.dat` local subsiste (import = étape manuelle) ; si l'analyse a échoué → **perte totale** (NOM-03) | perte |
| D. pendant import | actions déjà sauvegardées une par une ; fichier non archivé → réimport intégral | rejeu (majoritairement idempotent), import partiel visible |
| E. après import local, avant confirmation distante | pas de confirmation distante : la tablette apprend l'archivage via `nomade_archivage` dans l'export suivant | rejeu si la tablette renvoie le fichier |
| F. après import, avant suppression distante | n/a en FTP (suppression avant import) ; si `DELE` échoue : `EOFError` non gérée, re-téléchargement et reproposition | doublon d'import possible |

### Connecthys — scénario critique demandé (réponse perdue)

1. Noethys dépose `import_<n>.crypt` puis `GET /syncup/<n>`. 2. Le portail traite. 3. La réponse est perdue (timeout illimité → en pratique coupure). 4. Noethys conclut à l'échec, `last_synchro` n'avance pas. 5. L'utilisateur (ou le cycle suivant) recommence → **nouvel export sous un nouveau nom**, retraité par le portail.
- **Doublon dans Noethys** : non (sens montant).
- **Double traitement serveur** : oui (prouvé côté client) ; effet métier dépend de l'idempotence serveur (**À PROUVER**, sémantique probable de remplacement → voir CNX-16).
- **Corruption / perte** : accumulation de fichiers sensibles côté portail et poste (X-07).
- **Sens descendant** (`syncdown`) : at-least-once, import local atomique, dédup **déléguée au serveur** ; doublons démontrés en cas de concurrence (CNX-08).

**Contrat de livraison réel** : descendant = *at-least-once sans déduplication locale fiable* ; montant = *at-least-once, idempotence non garantie côté client*. L'objectif « AT LEAST ONCE + DÉDUPLICATION » n'est **pas** atteint.

---

## 11. Sécurité des secrets — inventaire (valeurs jamais reproduites)

| Secret | Stockage | Forme | Fuites constatées |
|---|---|---|---|
| Mot de passe MySQL réseau | `Config.json` (+ `.bak`) `nomFichier`, `derniersFichiers` | base64 `#64#` | export `.nnc` en clair ; `logintemp.cnf` ; `journal.log` (SEC-01) ; **non** affiché dans le titre ni le menu (vérifié) |
| Mot de passe SMTP | `adresses_mail.motdepasse` | **clair** | recopié dans `config.py` Connecthys ; envoyé après STARTTLS non vérifié |
| Clé / secret Mailjet | `adresses_mail.parametres` | **clair**, champ non masqué | — (pas de fuite dans les libellés de progression, vérifié) |
| Secrets SMS (Mailjet, OVH, Brevo) | `parametres` cat. `envoi_sms` | **clair**, champs visibles | mdp OVH dans l'URL et dans l'exception |
| Connecthys `ftp_mdp`, `ssh_mdp`, `db_mdp`, `stats_mdp`, `email_password`, `secret_key` | `parametres` cat. `portail` | **clair**, PropertyGrid en clair | `config.py` temporaire non supprimé, chmod 0644 distant, FTP clair, export `.cfg`, jeton dérivé dans URL/journal |
| Nomadhys FTP + clé de chiffrement | `Config.json` | base64 | FTP clair, champ non masqué |
| Mot de passe des sauvegardes | `Config.json`, `sauvegardes_auto` | base64 | chiffrement faible (MD5, sans MAC) |
| Mots de passe utilisateurs Noethys | `utilisateurs.mdp` | **clair** + SHA256 non salé | export Nomadhys (NOM-01), sauvegardes |
| Mots de passe internet familles | `familles/utilisateurs.internet_mdp` | AES clé = fin de l'IDfichier (même base) | obfuscation seulement |

Aucun secret réel n'est committé dans le dépôt (valeurs factices `ICI_MOT_DE_PASSE`, `XXXX`, `********` uniquement).

---

## 9. Threads et interface wx — synthèse

| Opération réseau | Thread | Constat |
|---|---|---|
| Email unitaire visible | worker + `CallAfter`, modale non fermable | correct (4dccd87) |
| Email par lot, unitaire caché, rapport de bug, sauvegarde, test d'adresse | **UI** | blocage (20 s → illimité), `sleep` sur l'UI, pas d'annulation |
| SMS | **UI** | blocage illimité |
| Connecthys automatique | worker non démon + `CallAfter` (jauge/journal) | **`MAJ_bouton` hors UI** (CNX-14) ; blocage illimité ; processus non terminable |
| Connecthys manuel, pièces, installation, contrôle | **UI** | blocage illimité ; « Annuler » sans effet ; boucle infinie à l'installation |
| Nomadhys serveur | reactor (UI) + thread d'export | `transport.write` et dialogue wx hors thread (NOM-11) |
| Nomadhys FTP | **UI** | blocage illimité |
| Nomadhys import | worker + `AppelSynchroneUI` / `EstVivant` | correct (#378) ; NOM-12 |
| « Aujourd'hui » | worker + `CallAfter` + génération | correct |
| MySQL, XSD, Google, vacances, référentiel, enregistrement | **UI** | blocages bornés (5–10 s) ou illimités (XSD, référentiel, MySQL) |

---

## 15–16. Tests existants et tests manquants

### Tests existants liés au réseau
`test_noethys_sl_mailer_errors.py`, `test_vanilla_dlg_mailer_progress_parent.py`, `test_vanilla_mailjet_email_confirmation.py`, `test_vanilla_mailjet_progress_lifecycle.py`, `test_vanilla_connecthys_synchro.py`, `test_noethys_sl_connecthys_wx_thread.py`, `test_connecthys_reservations_progress.py`, `test_portail_pieces_safe_yield.py`, `test_noethys_sl_nomadhys_wx_thread.py`, `test_ephemerides*.py`, `test_vanilla_crash_recipient.py`.
Aucun ne couvre : timeouts, TLS, clés SSH, FTP, réponse perdue, doublons, fichiers temporaires, fuite de secrets, pickle, intégrité, transactions MySQL. **Aucun n'est exécuté par la CI de la RC2.**

### Tests d'audit ajoutés (caractérisation, tous verts)

| Fichier | Tests | Couverture |
|---|---|---|
| `tests/test_audit_reseau_emails.py` | 24 | mini-serveur SMTP local (coupure après DATA, muet, refus RCPT, refus AUTH), Mailjet simulé, SMS, appelants métier |
| `tests/test_audit_reseau_connecthys.py` | 38 (+13 sous-tests) | serveur HTTP local (4xx/5xx, vide, invalide, tronqué, redirection, muet, certificat auto-signé), SSH/FTP simulés, concurrence, réponse perdue, temporaires, pickle, zip-slip, threads |
| `tests/test_audit_reseau_nomadhys.py` | 27 | crypto, `AnalyserFichier`, FTP simulé (coupures B/C/F, purge), serveur TCP (auth, nom de fichier, taille, framing), thread d'import |
| `tests/test_audit_reseau_divers.py` | 35 | « Aujourd'hui », TLS global, XSD, SMS, référentiel, Google, vacances, enregistrement, ouverture d'URL |
| `tests/test_audit_reseau_secrets.py` | 27 | GestionDB réseau (timeouts, TLS, atomicité, `;`), journalisation, `logintemp.cnf`, chiffrement, stockage des secrets |

Commande : `xvfb-run -a python -m pytest -q tests/test_audit_reseau_*.py` → **151 passed, 13 subtests passed**.
Limites : Twisted et MySQLdb non installés (code extrait par AST / pilote simulé) ; pas de vrai serveur FTP/SFTP ; pas d'exécution sous Windows.

### Tests manquants (à écrire avec les corrections)
- SMTP : coupure après DATA sans renvoi automatique, statut « incertain » ; STARTTLS avec certificat invalide refusé ; refus partiels.
- Mailjet : timeout transmis, version épinglée.
- SMS : bilan, reprise ciblée, timeout, aucun secret dans les exceptions.
- Connecthys : timeouts, clé SSH épinglée (nouvelle/modifiée refusée), FTPS, unicité `ref_unique`, verrou de synchro, ACK, suppression des temporaires, refus pickle, zip-slip, `MAJ_bouton` via `CallAfter` ; **côté serveur** : sémantique `syncup` (CNX-16) et autorisation du jeton.
- Nomadhys : suppression distante seulement après succès, authentification du serveur TCP, assainissement du nom, ACK, test avec une vraie tablette / Twisted.
- MySQL : transaction règlement + ventilation avec coupure simulée (rollback), unicité des numéros de facture (MariaDB en CI), timeouts et `ssl_mode` réellement passés.
- CI : job pytest Linux/Xvfb sur la RC2 avec base fixture.

---

## 17. Recommandations de correction — ordre proposé (phase 2)

1. **Supprimer les exécutions de contenu distant** : X-01 (pickle), CNX-03 (`models.py`), NOM-02 (nom de fichier), CNX-11 (zip-slip / épinglage).
2. **Fermer les canaux non authentifiés** : NOM-01 (auth + chiffrement obligatoire du serveur Nomadhys), X-02 (clé SSH épinglée), X-04 (FTPS/SFTP), X-05 (STARTTLS vérifié, corrige aussi EMAIL-01), X-03 (contexte TLS local), X-06 (HMAC en en-tête, plus de `print` d'URL).
3. **Garantir l'absence de perte** : NOM-03/NOM-04 (suppression distante après succès, quarantaine), NOM-05 (ACK + taille), CNX-17, DB-05/06 (transactions).
4. **Garantir l'absence de doublon** : EMAIL-03/04 (statut incertain, pas de renvoi auto), X-08 (SMS), CNX-08/09 (unicité `ref_unique` + verrou), DB-07.
5. **Supprimer les faux succès** : EMAIL-07, EMAIL-10, NET-02, CNX-18, NOM-12.
6. **Timeouts et threads** : CNX-07, CNX-10, CNX-14, EMAIL-13/14, DB-01, NOM-09, NET-06/08.
7. **Secrets au repos** : X-07, SEC-14, SEC-17, SEC-01, SEC-16/CNX-20.
8. **CI** : exécuter la suite (dont les tests d'audit inversés au fil des correctifs) sur la RC2.

Chaque correctif devrait inverser le test de caractérisation correspondant (le test « anomalie présente » devient « anomalie absente »).

---

## 18. Note

La consigne d'origine se termine par un point « 18. » sans contenu. Ce rapport s'arrête donc au point 17 ; préciser le contenu attendu du point 18 si nécessaire.
