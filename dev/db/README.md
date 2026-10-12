# Noe-032 — bac a sable MySQL 5.5, donnees synthetiques

Source : PR historique #104, reprise ciblee sur main / wx / qt.
**Statut : smoke execute avec succes sur Windows 11 / Docker Desktop 29.8 le
12/10/2026 (MySQL 5.5.62, PASS 2 lignes / 1 vue). Workflow CI manuel non rejoue.**

Ce dossier prepare un MySQL 5.5.62 **strictement jetable** pour la
qualification Noethys. Il ne constitue NI une validation des restaurations
Noethys, NI un anonymiseur, NI un importeur de sauvegardes de production.

## Isolation et securite

- Projet Docker fixe : `noethys-sl-noe032` ; conteneur
  `noethys-sl-noe032-mysql55` ; volume propre au projet.
- Ecoute exclusivement sur `127.0.0.1:3308`.
- Base de recette forcee a `noethys_dev` ; source de fixture
  `noethys_fixture_source` ; aucune base PMSL.
- Image historique officielle epinglee par digest ; runtime Linux/AMD64
  uniquement ; Docker local requis (pas de contexte distant).
- Secrets exclusivement dans `dev/db/.env`, ignore de Git.
- Le guard refuse noms, port, compte, mot de passe et image inattendus.
- `import.ps1` n'accepte que le format de la petite fixture synthetique
  (table `fixture_data`, vue `fixture_view`) ; aucun dump Noethys
  general ou export reel. Le drapeau -SyntheticData seul n'est pas une
  preuve d'anonymisation : ne jamais fournir de dump de production.
- `reset.ps1` exige deux confirmations et ne supprime que le projet nomme.
- `smoke.ps1` **detruit et recree** les deux schemas de cette fixture
  **dans le conteneur de recette uniquement**. Ne pas l'utiliser pour des
  donnees que vous souhaitez conserver.

## Execution sur Windows (PowerShell, depot Noethys-SL)

Depuis le dossier du depot sur le poste de recette :

```powershell
Set-Location "$env:USERPROFILE\Documents\GitHub\Noethys-SL"
Copy-Item dev\db\.env.example dev\db\.env
notepad dev\db\.env
# Remplacer les deux mots de passe CHANGE_ME par des valeurs fortes.
& .\dev\db\start.ps1
& .\dev\db\smoke.ps1
```

Pour reconstruire l'environnement **jetable**, et uniquement celui-ci :

```powershell
Set-Location "$env:USERPROFILE\Documents\GitHub\Noethys-SL"
& .\dev\db\reset.ps1 -Force -Confirmation SUPPRIMER-noethys-sl-noe032
```

Docker Desktop et PowerShell sont requis. Le script refuse un moteur Docker
distant. Docker Hub ne sert plus le manifeste schema v1 historique
(`d404d78a...`, refuse meme par Skopeo) : l'image est epinglee sur le digest v2
linux/amd64 officiel du meme tag `mysql:5.5.62` (`c9c671d0...`).

## CI et gates

Le workflow `.github/workflows/noe-032-mysql-smoke.yml` est **manuel**
(workflow_dispatch) : aucune fabrication Windows ni consommation automatique
des minutes de CI pour chaque push documentaire.

Il doit verifier :
1. conversion et lancement du conteneur isole ;
2. generation d'une table et d'une vue fictives ;
3. dump --databases et import strictement limite a cette fixture ;
4. postconditions (deux lignes, une vue), destruction du volume de recette.

**Protections de restauration (12/10/2026) :** manifeste SHA-256, analyse
syntaxique, ligne finale mysqldump des anciens dumps, marqueur terminal et
postconditions sont integres dans `UTILS_Sauvegarde` / `UTILS_SQL_Integrite`
et ont ete recettes de bout en bout sur ce MySQL 5.5 (donnees synthetiques).

**STOP-GATE encore actif :** rollback transactionnel d'une restauration
reseau, recette dans l'application Noethys complete sous Windows, schema
Noethys complet synthetique, MariaDB/MySQL plus recents cote serveur.

## Anonymisation (doctrine reprise de la PR #104)

Noethys contient des donnees de familles et d'enfants, de facturation, des
coordonnees, des inscriptions et parfois des commentaires ou documents. Son
anonymisation ne doit **pas** reutiliser aveuglement un outil concu pour un
autre logiciel.

Un dump reel reste une donnee de production tant qu'un anonymiseur Noethys
specifique, audite sur le schema courant, n'a pas neutralise les donnees
directement et indirectement identifiantes. Cet outil fera l'objet d'un lot
separe : inventaire du schema, classification des champs, transformations
deterministes, controle des pieces et fichiers externes, rapport residuel.
Les dossiers `dev/db/imports/`, `dev/db/exports/` et le rapport
`dev/db/anonymization-report.txt` sont ignores par Git par anticipation.

Decision transversale PMSL-Arch `ADR-006` : la production n'est jamais un bac
a sable ; services de donnees reproductibles ; secrets hors Git ; jeux issus
de la production non partageables avant anonymisation controlee ; une
qualification de migration SQL ne se resume pas a la reussite d'un conteneur.

**Aucune execution sur un profil Noethys reel, aucune copie de familles,
aucune migration SQL, aucune publication de version.**
