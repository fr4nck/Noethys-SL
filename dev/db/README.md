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

**STOP-GATE encore actif :** tests de restauration Noethys sur un schema
complet entierement synthetique, SQL tronque, manifeste, marqueur terminal,
postconditions, rollback, vrais tests Windows et MySQL/MariaDB. Les protections
SQL presentes sur master ne sont pas integrees par ce seul outillage.

**Aucune execution sur un profil Noethys reel, aucune copie de familles,
aucune migration SQL, aucune publication de version.**
