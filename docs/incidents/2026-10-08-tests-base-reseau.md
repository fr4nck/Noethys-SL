# Incident du 08/10/2026 — tests automatisés connectés à la base réseau de production

Famille transversale : **TRV-032** (PMSL-Arch, `docs/AUDIT_BUGS_TRANSVERSAUX.md`).

## Contexte

Sur le poste de développement 5700x, la configuration utilisateur de Noethys désigne la base réseau (MySQL) de production :

- `noethys/Portable/Config.json` du dossier de travail `Noethys` (profil « portable », prioritaire) ;
- `%APPDATA%/noethys/Config.json` (utilisé hors dossier `Portable`, par exemple depuis `Noethys-RC2`).

Les tests n'isolaient pas cette configuration : tout `GestionDB.DB()` non redirigé vers une base de test ouvrait une connexion à cette base.

## Exécutions concernées

Quatre exécutions complètes de la suite (`python -m unittest discover -s tests`), lancées depuis `Noethys` avant la mise en place de la garde (commit `4a3739f7`, 12:25) :

| N° | Fin (heure locale) | Code testé | Tests |
|---|---|---|---|
| 1 | ≈ 11:47 | `cc39c887` | 526 (sortie tronquée, journal écrasé par l'exécution 2) |
| 2 | 11:48:27 | `cc39c887` | 526 |
| 3 | 11:51:07 | fusion `7be696f9` en cours | 534 |
| 4 | 12:11:21 | `746bbd6e` | 584 |

Les tentatives de lancement antérieures (pytest absent, option `-t` erronée) se sont arrêtées avant l'exécution de tout test. Les exécutions ciblées et les scripts de reproduction de la même période ont été rejoués avec une connexion factice enregistreuse : ils n'ont ouvert **que des lectures** `GetIDfichier` (au plus une par processus), ou aucune connexion.

## Constats

### Connexions constatées

- Rejeu de la suite avec une connexion factice enregistreuse (aucun accès réseau) : **31 connexions par exécution complète**. Les trois modules de test à l'origine de ces appels, et le code qu'ils appellent, sont identiques aux commits des quatre exécutions (seul le bloc de garde ajouté ensuite diffère).
- Lors de la première exécution sous garde (12:22), les 31 tentatives ont été interceptées.
- Aucune des exécutions 2 à 4 n'a affiché le message d'échec de connexion de `GestionDB` (« La connexion a MYSQL a echouee ») : les connexions ont **très probablement abouti**. Ce n'est pas une preuve directe : aucun journal côté serveur n'a été consulté.

### Opérations envoyées, d'après le code réellement exécuté

Chaque connexion : `connect`, `set_character_set('utf8')`, `USE <base>`. Puis :

| Origine | Nombre / exécution | Requêtes |
|---|---|---|
| `UTILS_Parametres.Parametres(mode="get", categorie="email", nom="timeout")`, appelé par `UTILS_Envoi_email.Base_messagerie.__init__` (tests Mailjet) | 29 | `SELECT` du paramètre ; **s'il est absent** : `INSERT INTO parametres (categorie, nom, parametre)` avec `('email', 'timeout', '')` puis `COMMIT` |
| `FonctionsPerso.GetIDfichier`, appelé à l'import de `CTRL_Grille` / `UTILS_Impression_reservations` | 2 | `SELECT` du paramètre `IDfichier` |

Aucun `UPDATE`, `DELETE`, `CREATE` ni `ALTER` n'est émis par ces chemins.

### Écritures possibles

**Au plus une ligne** dans la table `parametres` : `('email', 'timeout', '')`, et seulement si elle n'existait pas avant la première exécution. Une fois créée, les appels suivants la lisent sans écrire. Cette ligne est identique à celle que Noethys crée lui-même au premier envoi d'e-mail depuis n'importe quel poste.

### Écritures confirmées

**Aucune.** Rien n'a été lu ni écrit sur la production pour le vérifier. La table `parametres` ne conserve ni date ni poste : la **présence** de la ligne ne prouve pas que les tests l'ont créée. Seuls des journaux du serveur MySQL (journal binaire ou journal général, s'ils sont activés) pourraient montrer un `INSERT` sur `parametres` entre 11:45 et 12:12 le 08/10/2026 depuis l'adresse du poste 5700x.

## Configurations réelles

Ni `noethys/Portable/Config.json` (modifié le 25/09/2026) ni `%APPDATA%/noethys/Config.json` (10:15 le 08/10/2026, avant la session) n'ont été modifiés. Les tests ont seulement créé des sous-dossiers temporaires par processus dans `noethys/Portable/Temp`.

## Mesures

- `4a3739f7` : garde réseau des tests (`tests/_garde_reseau.py`, `test_000_garde_reseau`).
- `03b56fca` : configuration de test explicite (profil temporaire, aucun fichier ouvert) et garde importée par chaque module de test.
- `aee1626e`, `b9c8b386` : autorisation explicite du seul serveur MySQL local de test (`NOETHYS_TEST_MYSQL_*`, hôte 127.0.0.1 ou localhost), toute autre destination restant refusée.
- Contrôles : suite complète et chacun des 72 modules lancés seuls avec interception du pilote MySQL : 0 tentative ; empreintes des deux `Config.json` réels inchangées ; recettes graphiques lancées avec la même garde et un profil temporaire.

## Vérification à mener séparément (lecture seule)

`docs/diagnostics/diagnostic_adhesions.sql`, requêtes 9 et 9 bis, selon le mode d'emploi en tête du fichier. Ne rien corriger : la ligne, si elle existe, est sans effet fonctionnel (délai d'envoi d'e-mail vide = valeur par défaut).
