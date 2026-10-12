# Contribuer à la documentation

La documentation Noethys SL est versionnée avec le code. Une modification documentaire durable doit donc suivre le même circuit de revue qu'une modification technique.

## Principes

- modifier les fichiers dans `docs/` plutôt qu'un wiki séparé ;
- préférer la mise à jour d'un document canonique existant à la création d'un document concurrent ;
- documenter le socle commun dans `main` ; ne décrire dans `wx` ou `qt` que leurs différences d'interface ;
- ne pas publier de données réelles, secrets, identifiants ou informations confidentielles ;
- lorsqu'une modification de code change un comportement documenté, mettre à jour la documentation dans la même pull request si possible ;
- une PR non fusionnée reste une proposition, pas une vérité du produit.

## Prévisualisation locale

Créer un environnement Python dédié puis installer les dépendances documentaires :

```bash
python -m pip install -r requirements-docs.txt
```

Lancer ensuite le serveur local :

```bash
mkdocs serve
```

Puis ouvrir l'adresse indiquée par MkDocs dans le navigateur.

Pour reproduire la construction CI :

```bash
mkdocs build --clean
```

Le dossier généré `site/` est un artefact et ne doit pas être versionné.

## Cycle de contribution

1. travailler sur la branche canonique concernée (`main` pour la documentation commune), sans créer de branche supplémentaire (voir `AGENTS.md`) ;
2. modifier ou ajouter le Markdown ;
3. vérifier les liens et la navigation ;
4. exécuter `mkdocs build --clean --strict` ;
5. commiter la documentation avec le changement technique associé lorsqu'il existe ;
6. la publication n'a lieu qu'à partir de `main`.

Le workflow documentaire valide la construction MkDocs séparément. Le filtrage éventuel des autres workflows applicatifs relève de leur propre configuration et n'est pas modifié par ce lot.

## Navigation

Le menu principal est défini dans `mkdocs.yml`. Ajouter une nouvelle page au menu uniquement si elle apporte un point d'entrée durable. Les documents spécialisés peuvent rester accessibles par liens et par recherche sans alourdir la navigation principale.

## Recherche

Le moteur de recherche est alimenté par le contenu construit depuis `docs/`. Des titres et intertitres explicites améliorent directement la qualité des résultats.

## Versions

La publication documentaire se fait depuis `main` (branche cible du projet). Le déploiement GitHub Pages n'est actif que si la variable de dépôt `DOCS_PAGES_ENABLED` vaut `true` ; sinon le site construit est conservé comme artefact du workflow. Le multi-version n'est volontairement pas activé tant qu'un besoin réel de publication simultanée de plusieurs versions n'est pas établi.

Lorsque ce besoin apparaîtra, la solution retenue devra conserver :

- les sources Markdown dans Git ;
- une correspondance explicite entre version documentaire et version du produit ;
- la revue par pull request ;
- un mécanisme de publication reproductible.
