# Documentation Noethys SL

Noethys SL est la lignée de développement de Noethys maintenue dans le dépôt
`fr4nck/Noethys-SL`. Sa numérotation publique (tags `noethys-sl-*`) est
distincte de celle de Noethys d'origine, créé par Ivan LUCAS.

## Branches

| Branche | Rôle |
|---|---|
| `main` | socle commun : moteur, règles métier, sécurités, contrats de données, tests partagés, documentation |
| `wx` | adaptations propres à l'interface wxPython |
| `qt` | adaptations propres à l'interface Qt |

Les règles de travail (aucune branche supplémentaire, non-régression entre
les trois branches, sécurité des données) sont dans `AGENTS.md`, à la racine
du dépôt. L'état détaillé des branches, des reprises et des décisions est
tenu dans [Reprise et état des branches](dev/REPRISE_CODEX.md).

## Points d'entrée

- **Exploitation** : [récupération d'un dump SQL](exploitation/RECUPERATION_DUMP_SQL.md),
  [adhésions automatiques](metier/ADHESIONS_AUTOMATIQUES.md).
- **Recettes** : [candidat du 08/10/2026](recette/RECETTE_CANDIDAT_2026-10-08.md),
  [conventions](recette_conventions/README.md).
- **Évolutions reportées** : [fonctionnalités reportées](dev/FONCTIONNALITES_REPORTEES.md)
  (travaux archivés, non intégrés).
- **Audits** : [audit réseau RC2](audit/AUDIT_RESEAU_RC2.md),
  [contrat Connecthys](audit/CONTRAT_CONNECTHYS.md).

!!! warning "Données"
    Cette documentation ne doit contenir ni données de familles, ni secrets,
    ni sauvegardes. Les recettes se font sur des bases fictives isolées.
