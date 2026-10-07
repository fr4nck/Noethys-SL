# Contrat Connecthys ↔ Noethys-SL RC2 (état observé)

> Document établi par lecture du code, **avant** toute évolution protocolaire (rail réseau 1).
> Il décrit l'existant ; il ne propose aucun changement de protocole.

## Sources lues

| Côté | Référence |
|---|---|
| Noethys-SL | `rc/noethys-sl-0.1.0-rc.2` @ `91d9e625`, plus la branche `fix/rc2-network-stopgate-1` |
| Connecthys | `github.com/Noethys/Connecthys`, branche `master` @ `7949752` (03/09/2026), version applicative **1.1.0** (`versions.txt` : `version_min_noethys=1.3.3.0`) |
| Nomadhys (format des fichiers chiffrés) | `github.com/Noethys/Nomadhys` @ `2472fb1` (version 2.0, 2022) |

**Pourquoi `master` est la bonne référence.** Noethys installe Connecthys depuis `https://github.com/Noethys/Connecthys/archive/master.zip` (`UTILS_Portail_installation.py:138`). La mise à jour (`/update`) télécharge une version étiquetée listée dans `versions.txt` (`application/updater.py:82,128`).

**Version réellement déployée : À PROUVER.** Une instance installée avant le 03/09/2026 peut être plus ancienne. Le dernier changement de `importation.py` date du 03/03/2023, celui de `exportation.py` du 23/03/2024, celui de `models.py` du 02/03/2023. Pour la sémantique décrite ici (traitement des actions, filtre des demandes), le code est stable depuis 2016 à 2021, d'après l'historique Git.

---

## A. syncdown : récupération des demandes du portail

| | |
|---|---|
| **Requête** | `GET {url}/syncdown/<jeton>/<last>` (`UTILS_Portail_synchro.Download_data`) |
| **Jeton** | Voir F. |
| **`last`** | `ref_unique` de l'action de plus grand `IDaction` en local. Vaut `0` si `full_synchro`, si la base locale est vide, ou si cette valeur n'est pas numérique. |
| **Réponse** | JSON : liste d'actions (`Action.as_dict()`, toutes les colonnes de `portail_actions` et des tables liées), HTTP 200. |
| | Mauvais jeton : texte `Erreur de clé de sécurité`, HTTP 200. |
| | Exception serveur : trace HTML, HTTP 500. |
| **Effet serveur** (`exportation.Exportation`) | `last == 0` : **toutes** les actions dont `etat != "suppression"`. |
| | Sinon : actions dont `IDaction > IDaction(last)` **et** `etat == "attente"` (repli : `horodatage > horodatage(last)`). |
| | Écrit le paramètre `derniere_synchro`. Supprime du disque les pièces des actions `validation` et les pièces de plus de 365 jours. |
| **Effet client** | Insertion de toutes les actions reçues (`IDaction = max+1`) en **une transaction**. `maj_password` est appliqué immédiatement. |
| **Idempotence** | Lecture idempotente côté serveur, hors nettoyage des pièces. |
| **Retry** | Aucun. Le cycle suivant relit depuis le même curseur. |
| **Risque de doublon** | **CONFIRMÉ** si `last` repart à 0 hors `full_synchro` : le serveur renvoie alors aussi les demandes **déjà traitées**, et Noethys ne déduplique qu'en `full_synchro` (CNX-09). |
| | **CONFIRMÉ** en cas de synchros concurrentes (CNX-08). |
| **Risque de perte** | Aucun observé côté serveur : le serveur ne supprime pas l'action et n'attend pas d'accusé de réception. |
| **Compatibilité** | Inchangée au rail 1. |

## B. syncup : envoi des données de Noethys

| | |
|---|---|
| **Requête** | 1. Dépôt de `application/data/import_<n>.crypt` (FTP, SFTP ou local). |
| | 2. `GET {url}/syncup/<n>`. **`<n>` est le nom du fichier, pas un jeton** : `import_%d.crypt`, avec `<n>` aléatoire de 20 chiffres. |
| **Réponse** | `"True"` (texte, `str(True)`) si l'import a réussi. |
| | Sinon un texte : `fichier crypt inexistant`, `AES non disponible`, `Le fichier n'est pas une archive valide`. Trace HTML 500 sur exception. |
| | Noethys n'accepte que le corps exact `True` (CNX-25 : `True\n` serait compté comme un échec). |
| **Effet serveur** (`importation.Importation`) | Déchiffrement avec `SECRET_KEY[:10]`, puis suppression du `.crypt`. |
| | Mise à jour des `parametres` et des `users`. |
| | **DROP puis recréation** des tables listées dans `tables_modifiees_synchro` (factures, consommations, individus…). |
| | **Table des actions** : si elle est vide côté serveur, import complet. Sinon, **uniquement** `UPDATE portail_actions SET etat, traitement_date, reponse WHERE ref_unique = …`. |
| | Supprime les `import_*` de plus d'un jour. |
| **Effet client** | `last_synchro = now()` seulement si la réponse vaut `True`. |
| **Idempotence** | Rejouer un instantané identique ne fait que réécrire les mêmes tables et les mêmes états : **effet idempotent**. |
| **Retry** | Aucun automatique ; nouvel instantané au cycle suivant. |
| **Risque de doublon** | Aucun dans Noethys. Côté serveur, deux traitements aboutissent au même état final (voir le scénario « réponse perdue », section N). |
| **Risque de perte** | Voir CNX-16 ci-dessous : **RÉFUTÉ**. |
| **Compatibilité** | Inchangée au rail 1. Le contexte TLS local n'est utilisé qu'avec `accept_all_cert`, et l'appel `urlopen(req)` d'origine est conservé sans cette option. |

### CNX-16 : perte d'une action entre syncdown et syncup → **RÉFUTÉ** (Connecthys 1.1.0, comportement stable depuis 2016)

Scénario :
- **T0** : `syncdown`.
- **T1** : une famille crée l'action X.
- **T2** : `syncup`.

1. À T2, la table des actions du serveur n'est pas vide : `importation.py` n'ajoute pas `actions` aux tables supprimées et ne fait qu'un `UPDATE … WHERE ref_unique = <ref de l'instantané>`.
2. X n'existe pas dans l'instantané de Noethys : **aucune ligne ne la touche**. X survit en `attente`.
3. Au `syncdown` suivant, X a `IDaction > IDaction(last)` et `etat == "attente"` : elle est téléchargée.

Seul cas de remplacement complet : la table des actions du serveur est **vide** (première synchronisation ou `cleardb`). Aucune action famille ne peut alors être perdue.

**Statut : RÉFUTÉ** pour Connecthys `master` @ `7949752`. Ce n'est pas encore prouvé pour une instance déployée plus ancienne que 2016-08 (commit `6e0b54a`), cas jugé improbable.

## C. Structure des actions

`portail_actions` (`models.Action`) contient : `IDaction`, `horodatage`, `IDfamille`, `IDindividu`, `IDutilisateur`, `categorie`, `action`, `description`, `commentaire`, `parametres`, `etat`, `traitement_date`, `IDperiode`, `ref_unique`, `reponse` (450 caractères), `IDpaiement`, `ventilation`. Les réservations, renseignements et locations sont liés par `IDaction`.

États observés : `attente` (créée par la famille), `validation` (traitée par Noethys), `suppression`.

## D. `ref_unique`

Générée par Connecthys (`Action.GetRefUnique`) : `AAAAMMJJHHMMSSffffff` + `IDfamille` sur 6 chiffres, soit 26 chiffres.

- C'est la **clé de corrélation** entre les deux bases : curseur de `syncdown` et clé de l'`UPDATE` de `syncup`.
- Elle n'a **aucune contrainte d'unicité** côté Noethys.

## E. Accusé de réception

**Aucun ACK explicite.**
- `Valide_reception_demande` est un stub (`UTILS_Portail_synchro.py`).
- Le seul retour est différé : l'`etat` et la `reponse` repartent au `syncup` suivant.

Contrat effectif : **at-least-once sans déduplication locale fiable**.

## F. Jeton d'authentification

Calcul : `int(AAAAMMJJ + tous les chiffres de SECRET_KEY)`.
- Côté serveur : `views.VerifyKey`, `exportation.Exportation`.
- Côté client : `GetSecretInteger`.

Il est commun à `syncdown`, `update`, `upgrade`, `repairdb` et `cleardb`. Il dépend de la date **locale** de chaque machine (CNX-30). Il passe dans l'URL et est imprimé dans `journal.log` (X-06).

**Inchangé au rail 1.**

## G–J. update, upgrade, repairdb, cleardb

| Route | Effet serveur | Réponse |
|---|---|---|
| `/update/<jeton>/<version_noethys_int>/<mode>` | Cherche dans `versions.txt` une version compatible, puis télécharge `archive/<version>.zip` depuis GitHub et l'installe. | JSON `{"resultat": …}` |
| `/upgrade/<jeton>` | `models.UpgradeDB()` (migrations) | JSON `{"resultat": "ok" \| "erreur", …}` |
| `/repairdb/<jeton>` | `models.RepairDB()` | idem |
| `/cleardb/<jeton>` | **Vide toutes les tables du portail** | `{"resultat": "ok"}` |

Mauvais jeton : JSON d'erreur, HTTP 200.

**Inchangé au rail 1.**

## K. `models.py` (CNX-03) : fonction réelle

**Ce que c'est.** `application/models.py` est le **schéma SQLAlchemy de Connecthys** (Parametre, User, Action, Individu… 30 classes), versionné dans le dépôt Connecthys (53 commits, dernier changement en 2023-03).

**Variabilité.**
- Il n'est **pas propre à une instance** : il est identique pour une version donnée.
- Il contient un double import : `from application import db…` sous Flask, sinon un repli SQLAlchemy pur « pour Noethys » (prévu par l'auteur).

**Pourquoi Noethys le télécharge.** Pour construire la base SQLite d'export avec **exactement** le schéma de la version de Connecthys installée. L'import serveur relit cette base avec les mêmes classes.

**Mécanisme Noethys.** `ChargeModuleModels` (#397) charge le fichier dans un paquet unique, puis exécute `exec` dans le processus Noethys.

**Risque.** Exécution de code téléchargé, sans contrôle d'intégrité.

**Statut au rail 1 : non modifié**, conformément à la consigne.

Proposition compatible pour le rail 2 : calculer le SHA-256 du fichier téléchargé et le comparer à une liste d'empreintes connues, extraites des versions étiquetées de Connecthys et embarquées dans Noethys.
- Empreinte connue : chargement.
- Empreinte inconnue : refus explicite, ou repli sur la copie embarquée de la version annoncée par `/get_version`.

Aucun changement côté serveur n'est nécessaire.

## L. Pièces envoyées par les familles

**Côté Connecthys** (`views.pieces`, depuis 2021-03, commit `f30d47a`) :
- Le fichier est enregistré sous `uuid4().<ext>`, puis chiffré **en place** par `CrypterFichier(…, SECRET_KEY[:10])`. Sous Python 3, ou sans `ancienne_methode` : `cryptFile2`, donc **format SV2**.
- Si `IMPORT_AES` vaut `False` côté serveur, la pièce reste **en clair**.

**Côté Noethys** :
- Téléchargement depuis `pieces/<nom>`, puis `DecrypterFichier(…)`.
- **Rail 1** : `autoriser_ancien_format=False`. Une pièce non SV2 n'est **jamais** désérialisée par pickle ; la demande reste « attente » avec un message.
- Avant le rail 1, une pièce en clair déclenchait déjà une erreur, car le contenu passait par pickle.

**Compatibilité** : aucune pièce Connecthys n'est émise au format pickle. Le parcours SV2 est inchangé ; **compatibilité prouvée**.

## M. Format des fichiers chiffrés

| Format | Écrit par | Lu par |
|---|---|---|
| **SV2** : `b"SV2"` + IV + AES-CFB, clé MD5 hexadécimale, sans MAC | Noethys sous Python 3 (**toujours**, même avec `ancienne_methode=True`) ; Connecthys sous Python 3 ; Nomadhys ≥ 2020 | Tous |
| **Ancien** : pickle d'un objet AES-ECB | Noethys et Connecthys en Python 2 avec `ancienne_methode` ; Nomadhys < 2020 | Noethys : **restauration locale uniquement** depuis le rail 1 |

## N. Réponses attendues après traitement d'une demande

**Le traitement d'une demande est local à Noethys.** `DLG_Saisie_portail_demande.Traitement.Traiter()` renvoie `{"etat": bool, "reponse": texte}` ou `False`.

- `etat=True` : `SetEtat("valide")` met l'état local à `validation` et `reponse` reçoit le texte affiché à la famille.
- Sinon, la demande reste `attente`.

**Ce qui est transmis à Connecthys** : seulement `etat`, `traitement_date` et `reponse`, au `syncup` suivant (`UPDATE` par `ref_unique`). Connecthys affiche `reponse` à la famille.

**Scénario « réponse syncup perdue »** :
1. Noethys a déposé et Connecthys a importé.
2. La réponse `True` est perdue.
3. Noethys ne fait pas avancer `last_synchro`.
4. Le cycle suivant dépose un nouvel instantané, traité à l'identique.

Résultat : pas de doublon, pas de corruption, pas de perte. Un `.crypt` orphelin reste côté serveur, supprimé au bout d'un jour (`importation.py`).

## O. Sémantique de `etat` (EMAIL-10)

`etat` signifie « **la demande est traitée** selon la méthode choisie ; `reponse` est le texte à publier à la famille ».

- **Il n'est jamais envoyé tel quel** : seuls `etat="validation"` et `reponse` sont publiés au `syncup`.
- `Traitement_factures` renvoyait déjà `False` quand l'email échouait.

Correction EMAIL-10 (rail 1) : `Traitement_recus`, en mode automatique avec envoi par email, renvoie `False` si l'email n'est pas accepté. La demande reste `attente`, valeur déjà existante.

- Aucune valeur nouvelle, aucun format nouveau.
- Effet côté portail : la famille voit sa demande toujours en attente, au lieu d'une réponse « Reçu de règlement envoyé par Email. » fausse.
- **Compatibilité prouvée.**

---

## Fichiers Connecthys modifiés au rail 1 : compatibilité

Pour chaque fonction, les points vérifiés sont : changement de requête, de réponse, de format, de jeton, de fichier échangé, de séquence. **Toutes les réponses sont « non ».** La compatibilité serveur est prouvée par lecture du code serveur et par les tests listés.

| Fichier | Fonction | Avant | Après | Compatibilité serveur |
|---|---|---|---|---|
| `Utils/UTILS_Portail_synchro.py` | `Synchro.__init__`, 6 appels `urlopen` | `accept_all_cert` modifiait `ssl._create_default_https_context` pour tout le processus | Contexte SSL local passé aux seuls appels vers Connecthys ; sans l'option, `urlopen(req)` identique | Prouvée : URL, verbes et corps identiques (`test_urlopen_inchange_sans_l_option`, `test_https_certificat_autosigne`) |
| `Utils/UTILS_Portail_installation.py` | `AffichetailleFichier`, `Installer.Installer`, lecture de `get_version` | Boucle infinie si la taille de l'archive est inconnue ; `urlopen` sans timeout | 3 essais de 30 s, message final ; `get_version` avec le même contexte TLS local | Prouvée : même URL `master.zip`, même archive, même procédure. **À qualifier en réseau réel** : présence de `Content-Length` chez GitHub |
| `Ctrl/CTRL_Portail_serveur.py` | `Serveur.EffectuerCycle` | `MAJ_bouton()` appelé depuis le worker | Via `wx.CallAfter`, ignoré si le panneau est détruit | Prouvée : aucun échange réseau modifié |
| `Dlg/DLG_Saisie_portail_demande.py` | `Traitement_recus` (automatique, email) | `{"etat": True}` même si l'email a échoué | `False` : la demande reste « attente », comme pour les factures | Prouvée : valeurs existantes (section O) |
| `Dlg/DLG_Saisie_portail_demande.py` | `Traitement_pieces` | `DecrypterFichier` acceptait le pickle ; exception non gérée | SV2 seul ; erreur → `{"etat": False}` et message | Prouvée : pièces SV2 ou en clair, jamais pickle (section L) |

## Points bloqués ou à prouver

- **Version Connecthys réellement déployée** : À PROUVER (lire `/get_version` en production).
- **CNX-08 / CNX-09** (déduplication) : la correction suppose un index unique ou un contrôle sur `ref_unique` côté Noethys. C'est compatible côté serveur, mais cela touche les données locales. **Rail 2**.
- **X-06** (jeton) : passer à une authentification HMAC demande une **évolution conjointe** de Connecthys. **BLOQUÉ PAR COMPATIBILITÉ CONNECTHYS** tant qu'aucune version serveur ne l'accepte.
- **CNX-03** (`models.py`) : proposition d'empreintes, section K. **Rail 2**.
- **X-02** (clé SSH), **X-04** (FTP clair) : configuration propre à chaque hébergement. **Rail 2**, avec une étape de confirmation de l'empreinte.
