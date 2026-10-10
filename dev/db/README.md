# Base de développement / recette Noethys

Ce dossier fournit un serveur **MySQL 5.5.62 isolé dans Docker** afin de reproduire l'environnement SQL historique de Noethys sans installer durablement MySQL 5.5 sur Windows et sans dépendre du serveur de production PMSL.

Noethys reste exécuté **nativement** sur le poste. Seule la base de développement/recette est conteneurisée.

## Démarrage

```powershell
Copy-Item dev\db\.env.example dev\db\.env
notepad dev\db\.env
powershell -ExecutionPolicy Bypass -File dev\db\start.ps1
```

Connexion par défaut :

- hôte : `127.0.0.1` ;
- port : `3308` ;
- base/utilisateur/mot de passe : valeurs du fichier `.env`.

Le port est lié uniquement à `127.0.0.1`. L'image MySQL 5.5.62 est ancienne et destinée exclusivement à la reproduction locale d'un environnement historique.

## Qualification Noe-032 : données synthétiques uniquement

Tant que l'anonymiseur Noethys n'a pas été audité, **aucun dump réel ou issu de la production ne doit être importé dans cet environnement**.

Le smoke test crée lui-même une base fictive, la sauvegarde avec `mysqldump --databases`, la réimporte dans la base jetable configurée puis contrôle une table et une vue :

```powershell
powershell -ExecutionPolicy Bypass -File dev\db\smoke.ps1
```

## Import d'un dump synthétique

```powershell
powershell -ExecutionPolicy Bypass -File dev\db\import.ps1 -DumpPath "C:\Temp\noethys-synthetique.sql" -SyntheticData
```

Les sauvegardes Noethys réseau utilisent `mysqldump --databases`, qui inscrit le nom de la base source dans le dump. L'import :

- refuse les dumps qui contiennent plusieurs bases source ;
- retire les directives `CREATE DATABASE` et `USE` ;
- réimporte les objets dans `MYSQL_DATABASE`, la base jetable configurée ;
- échoue si aucun objet SQL n'est présent après l'import.

Pour effacer complètement la base Docker et repartir d'un volume vierge :

```powershell
powershell -ExecutionPolicy Bypass -File dev\db\reset.ps1 -Force
```

## Anonymisation

Noethys contient des données familles/enfants, facturation, coordonnées, inscriptions et parfois des commentaires ou documents. Son anonymisation ne doit donc **pas** réutiliser aveuglément l'outil Teamworks.

Un dump réel reste une donnée de production tant qu'un anonymiseur Noethys spécifique, audité sur le schéma courant, n'a pas neutralisé les données directement et indirectement identifiantes.

L'outil d'anonymisation Noethys fera l'objet d'un lot séparé : inventaire du schéma, classification des champs, transformations déterministes, contrôle des pièces/fichiers externes et rapport résiduel.

## Relation avec PMSL-Arch

Cette organisation applique la décision transversale `ADR-006` :

- production jamais utilisée comme bac à sable ;
- services de données reproductibles ;
- secrets hors Git ;
- jeux issus de la production non partageables avant anonymisation contrôlée ;
- qualification de migration SQL distincte de la simple réussite d'un conteneur.
