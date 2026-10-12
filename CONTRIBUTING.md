# Contribuer à Noethys — fork Upgrade Noethys

Ce dépôt est développé **ouvertement**. Les signalements de bugs, propositions d'amélioration, analyses, tests et pull requests sont les bienvenus lorsqu'ils restent compatibles avec les principes du projet.

Le dépôt amont `Noethys/Noethys` reste la référence historique du logiciel. Ce fork vise à moderniser Noethys Desktop sans effacer son origine ni attribuer individuellement les défauts historiques à un auteur.

## Principes de contribution

Une contribution doit, autant que possible :

- préserver les données et configurations existantes ;
- éviter toute migration implicite de schéma ;
- corriger la cause racine plutôt que masquer un symptôme ;
- rester ciblée, lisible et testable ;
- ne pas mélanger correction de bug, refonte graphique et nouvelle fonction métier sans nécessité ;
- conserver Windows comme cible prioritaire sans rendre le code source Windows-only ;
- accompagner les corrections de bugs d'un test ou d'un contrat de non-régression lorsque c'est réaliste ;
- documenter les décisions durables dans GitHub ou dans `docs/`.

## Développement ouvert, données fermées

Le code, les discussions techniques et la feuille de route peuvent être publics. En revanche, **aucune donnée réelle d'utilisateur ou de structure ne doit être publiée**.

Ne jamais joindre à une issue, un commit, une PR ou un artefact public :

- une base Noethys réelle, même partiellement anonymisée sans vérification ;
- des noms, coordonnées ou données concernant des familles, enfants, salariés ou partenaires ;
- des identifiants, mots de passe, clés API, jetons, chaînes de connexion ou secrets ;
- des exports de production contenant des données personnelles ;
- une configuration locale contenant des informations sensibles.

Les reproductions doivent utiliser des données synthétiques ou une copie correctement nettoyée et contrôlée.

## Issues

Avant d'ouvrir une issue, vérifier si le sujet n'est pas déjà suivi.

Pour un bug, fournir si possible :

- le symptôme observé ;
- le chemin permettant de le reproduire ;
- la version ou le SHA concerné ;
- la plateforme ;
- le comportement attendu ;
- les logs utiles, sans données personnelles ni secrets.

Un résultat d'audit statique n'est pas automatiquement un bug. Les signaux faibles doivent être qualifiés avant correction.

## Pull requests

Les PR doivent rester cohérentes et révisables. Une PR de correction devrait idéalement contenir :

1. le problème démontré ;
2. la correction minimale ;
3. le test ou contrat associé ;
4. l'impact éventuel sur wxPython, la base, le packaging ou la compatibilité ;
5. la provenance du défaut lorsque celle-ci est utile au retour upstream.

La CI rapide doit être verte. Les changements sensibles peuvent demander en plus une qualification complète et/ou une recette Windows sur copie de base réelle.

## Provenance des bugs

La provenance sert à déterminer où un correctif est applicable, **pas à désigner un responsable**.

Les catégories utilisées sont :

- `HISTORIQUE_UPSTREAM` — motif déjà présent dans la lignée officielle de Noethys avant notre fork ;
- `PORTAGE_PY3_WX` — code historique devenu invalide ou dangereux avec Python 3, wxPython Phoenix ou des dépendances modernes ;
- `FORK_REPENS` — défaut introduit par une modification propre à ce fork ;
- `INDETERMINE` — provenance non démontrée.

Lorsqu'un correctif `HISTORIQUE_UPSTREAM` ou `PORTAGE_PY3_WX` est indépendant de Repens, il peut être préparé sous forme de patch minimal pour Vanilla Clean et, lorsque pertinent, proposé au projet Noethys original.

## Interface et wxPython

Pour les changements d'interface, suivre :

- `docs/DESIGN_SYSTEM_UI_UX.md` ;
- `docs/WXPYTHON_UI_RULES.md`.

Ne pas masquer une assertion wx, ne pas réintroduire de géométrie rigide pour faire tenir un écran, et ne pas confondre parent visuel et contrôleur métier.

## Tests locaux

Baseline : Python 3.10.

```bash
python -m compileall -q noethys
python -m unittest discover -s tests -p 'test_*.py' -v
```

Voir `docs/DEVELOPMENT.md` pour les workflows plus complets.

## Licence et attribution

Noethys est historiquement distribué sous licence GNU GPL, comme indiqué dans les en-têtes du code source. Les mentions d'auteurs, copyrights et licences historiques doivent être conservées lors des modifications.

La clarification documentaire de la licence au niveau racine du dépôt doit rester fidèle aux termes réellement applicables au projet d'origine ; ne pas substituer une licence différente par opportunité.
