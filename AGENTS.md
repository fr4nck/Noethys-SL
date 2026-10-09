# Noethys-SL — consignes de travail et de reprise

## Branches canoniques (décision du 09/10/2026)

**Aucune création de branche supplémentaire.** Les trois branches de développement retenues sont :
- `main` : socle commun et branche principale cible ;
- `wx` : adaptations propres à wxPython ;
- `qt` : adaptations propres à Qt (pas de migration Qt implicite).

Travailler directement sur la branche existante pertinente, en commits traçables. Ne pas ouvrir une branche temporaire, `feature/*`, `fix/*`, `integration/*` ou `release/*`. Pour les changements partagés, choisir `main` ; pour ceux dépendant exclusivement de l'interface, choisir `wx` ou `qt`, sans recopier ni perdre les changements communs.

**Transition en cours :** GitHub affiche encore `master` comme branche par défaut. `main` est la cible, mais le changement de branche par défaut ne sera fait qu'après vérification de l'intégrité du code, des références, des workflows et des travaux non intégrés. Ne pas écraser `master` et ne pas le supprimer prématurément.

## Vérifications avant toute modification

1. Lire les SHA réels de `main`, `wx`, `qt` et de la référence concernée ; ne pas se fier uniquement aux conversations ou aux noms des branches.
2. Comparer les **arbres et fichiers**, pas uniquement les comptages de commits : l'historique contient des divergences et des fusions squash.
3. Conserver les travaux WIP : anciens PR, anciennes branches, tags, releases, stashes et worktrees restent des références historiques tant que leurs apports n'ont pas été qualifiés.
4. Aucun force-push ni réécriture d'historique sur les trois branches canoniques. Toute mise à jour de ref vérifie le SHA attendu et doit être un fast-forward, sauf décision explicite motivée.
5. Pour les correctifs métier : test de non-régression ciblé ; pour Windows, validation du runtime réel avant de qualifier une release. Une CI verte ne remplace pas une recette métier.

## Sécurité et données

- Jamais de test sur la base de production ou sur un profil portable qui la pointe.
- Isoler les bases fictives, vérifier la garde réseau des tests et ne jamais exposer les secrets, sauvegardes ni données des familles.
- Aucune migration SQL implicite. Préserver les contrats Noethys/Connecthys et tester sauvegarde/restauration et rollback sur copie avant toute bascule.
- Les chantiers réseau, pointage et rattachements non qualifiés restent hors publication jusqu'à preuve technique.

## CI et publication

- Privilégier la CI rapide sans packaging ; builder Windows complet uniquement sur demande de qualification ou de release.
- Conserver les tags/releases comme preuves de provenance ; ne pas déduire d'une PR fermée que tous ses fichiers ont été intégrés.
- Avant d'arrêter une session : consigner branche, SHA, actions réellement effectuées, CI, WIP/hors Git, exclusions et prochaine étape, dans la documentation de reprise existante.

Point d'entrée : `docs/dev/REPRISE_CODEX.md` ; conventions historiques : `docs/governance/PROJECT_STRATEGY.md` (certaines références de branches y sont antérieures à la consolidation actuelle).
