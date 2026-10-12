# Fonctionnalités reportées

Inventaire consultable des travaux **archivés mais non intégrés** dans `main`,
`wx` ou `qt`. **Archiver n'est pas intégrer** : une fonctionnalité listée ici
n'existe pas dans le produit tant qu'elle n'a pas été reprise, testée et
qualifiée sur les branches canoniques.

## Où sont les archives

- Un `git bundle` autonome par branche supprimée, vérifié (`git bundle verify`,
  restauration réelle dans un dépôt vide au SHA exact, `git fsck`), empreintes
  SHA-256 dans `SHA256SUMS.txt`.
- Copie principale : `C:\Users\Ordi\Documents\Sauvegardes-Noethys\branches-supprimees-20261012\`
  (poste de développement) ; seconde copie hors poste :
  `OneDrive\Sauvegardes-Noethys\branches-supprimees-20261012\`.
- Les commits des pull requests restent aussi conservés par GitHub
  (`refs/pull/<numéro>/head`).
- Restauration d'une branche :

```bash
git fetch <fichier.bundle> "+refs/remotes/origin/*:refs/heads/*"
git push origin <branche>
```

La liste complète des branches archivées, avec SHA et empreintes, est dans
[Reprise et état des branches](REPRISE_CODEX.md) (§§ 31 à 33).

## Règles de reprise

1. Repartir de `main` et comparer le contenu (pas l'historique) avant tout portage.
2. Aucune migration SQL implicite : migration explicite, testée sur copie avec
   sauvegarde, restauration et rollback.
3. Chantiers réseau, pointage et rattachements : hors publication tant qu'ils
   ne sont pas qualifiés de bout en bout.
4. Recette graphique uniquement sur runner isolé ou machine virtuelle.

## Pull requests reportées

| Sujet | PR | Issue de reprise | Archive (branche @ SHA) | Dépendances |
|---|---|---|---|---|
| Fonctions des individus dans les entités (table `rattachements_fonctions`, type École) | #384 (empilée sur #370) | #423 | `feature/vanilla-entites-fonctions` @ `4e2c615b` ; `feature/vanilla-conventions` @ `c2c3e87a` | migration SQL additive ; feuille de route #382, #383 |
| Consommateur `session-attendance/1` (pointage de séance) | #369 | #424 | `feature/session-attendance-consumer-2026-09-19` @ `74410a3e` | interventions Noe-062 de la lignée `master` ; table `interventions_attendance_inbox` |
| `SecretProvider` Windows du client mailbox inter-domaines | #355 | #424 | `noe-062-secure-secret-provider` @ `04f7886c` | client mailbox de la lignée `master` |

## Packaging

| Sujet | Archive | Motif du report |
|---|---|---|
| ZIP livré avec un dossier `Portable` déjà présent (mode portable par défaut) | `noe-041-portable-mode` @ `3cf6cbfe` | décision du 12/10/2026 : conserver ZIP et Setup sans imposer un nouveau packaging ; activation manuelle documentée dans [Mode portable](../exploitation/MODE_PORTABLE.md) |
| Smoke test non interactif de l'exécutable gelé (Noe-040 : `eeaa998c`, `ca40c11c`, `6f1de516`, `2116562b`) | `noe-041-portable-mode` @ `3cf6cbfe` | outillage de qualification Windows à reprendre avec le prochain chantier de build (le workflow de `main` vérifie déjà le démarrage de l'exécutable) |

## Prototypes

| Sujet | Archive | État |
|---|---|---|
| Prototype d'interface Qt (`noethys_qt/`, `tests_qt/`) | `poc/qt-theme-isole` @ `cba459cd` | voir la section « Prototype Qt » de la reprise |
