# Contribuer à la documentation

La documentation Noethys est versionnée avec le code. Une modification documentaire durable doit donc suivre le même circuit de revue qu'une modification technique.

## Principes

- modifier les fichiers dans `docs/` plutôt qu'un wiki séparé ;
- préférer la mise à jour d'un document canonique existant à la création d'un document concurrent ;
- conserver la distinction entre **Upgrade** et **Vanilla** ;
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

1. partir de la branche produit concernée ;
2. créer une branche dédiée ;
3. modifier ou ajouter le Markdown ;
4. vérifier les liens et la navigation ;
5. exécuter `mkdocs build --clean` ;
6. ouvrir une pull request ;
7. faire relire la modification avec le changement technique associé lorsqu'il existe ;
8. publier uniquement après intégration.

Le workflow documentaire valide la construction MkDocs séparément. Le filtrage éventuel des autres workflows applicatifs relève de leur propre configuration et n'est pas modifié par ce lot.

## Navigation

Le menu principal est défini dans `mkdocs.yml`. Ajouter une nouvelle page au menu uniquement si elle apporte un point d'entrée durable. Les documents spécialisés peuvent rester accessibles par liens et par recherche sans alourdir la navigation principale.

## Recherche

Le moteur de recherche est alimenté par le contenu construit depuis `docs/`. Des titres et intertitres explicites améliorent directement la qualité des résultats.

## Versions

Le premier déploiement publie la documentation de `master`. Le multi-version n'est volontairement pas activé tant qu'un besoin réel de publication simultanée de plusieurs versions n'est pas établi.

Lorsque ce besoin apparaîtra, la solution retenue devra conserver :

- les sources Markdown dans Git ;
- une correspondance explicite entre version documentaire et version du produit ;
- la revue par pull request ;
- un mécanisme de publication reproductible.
