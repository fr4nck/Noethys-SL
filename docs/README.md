# Documentation Noethys — Upgrade et Vanilla

> Index consolidé au 14 septembre 2026.

Le dossier `docs/` contient principalement des documents vivants. Les anciens audits et plans devenus obsolètes ont été retirés : l'historique Git et les PR conservent leur provenance sans encombrer la documentation courante.

Les fichiers Markdown de ce dossier restent la source documentaire. MkDocs fournit une vue navigable et recherchable de ce même corpus.

## Périmètre des lignes produit

Le dépôt porte deux lignes distinctes :

- **Upgrade** — branche `master`, modernisée avec Python 3, wxPython Phoenix, CI/packaging modernes et évolutions UI/UX ou métier décidées ;
- **Vanilla** — branche `maintenance/vanilla`, destinée à maintenir la version historique sans introduire les modernisations d'Upgrade.

La frontière canonique entre ces deux lignes est documentée dans [`governance/PROJECT_STRATEGY.md`](governance/PROJECT_STRATEGY.md).

## Ordre de lecture recommandé

1. [`PROJECT_STATE.md`](PROJECT_STATE.md) — état transversal, frontières et décisions durables ;
2. [`PROJECT_DECISIONS_CHATGPT.md`](PROJECT_DECISIONS_CHATGPT.md) — décisions auparavant dispersées dans les conversations et règle permettant de supprimer les chats sans perdre la mémoire du projet ;
3. [`ROADMAP.md`](ROADMAP.md) — trajectoire actuelle ;
4. [`NOE-BACKLOG.md`](NOE-BACKLOG.md) — chantiers, issues et travaux restants ;
5. [`DEVELOPMENT.md`](DEVELOPMENT.md) — environnement et règles techniques ;
6. document métier ou technique spécialisé correspondant au chantier concerné.

## Documents canoniques actuels

### Pilotage

- [`PROJECT_STATE.md`](PROJECT_STATE.md) — décisions transversales et sources de vérité.
- [`PROJECT_DECISIONS_CHATGPT.md`](PROJECT_DECISIONS_CHATGPT.md) — invariants Vanilla, Qt séparé, Connecthys multi-rôles, frontières avec Teamworks/Portails/PMSL-Arch et état de l'exploration Noé-Doc.
- [`ROADMAP.md`](ROADMAP.md) — phases et trajectoire générale.
- [`NOE-BACKLOG.md`](NOE-BACKLOG.md) — correspondance entre chantiers et issues.
- [`UPGRADE-HISTORY.md`](UPGRADE-HISTORY.md) — historique consolidé maintenu.

### Développement, recette et distribution

- [`DEVELOPMENT.md`](DEVELOPMENT.md) — runtime, tests, CI, bases, wxPython et packaging.
- [`RC-CHECKLIST.md`](RC-CHECKLIST.md) — checklist de gel et de qualification RC.
- [`RECETTE-BASE-EXISTANTE.md`](RECETTE-BASE-EXISTANTE.md) — recette sur copie d'une base réellement utilisée.
- [`PACKAGING-WINDOWS11.md`](PACKAGING-WINDOWS11.md) — chaîne de fabrication Windows.
- [`NOE-040-WINDOWS-PACKAGING.md`](NOE-040-WINDOWS-PACKAGING.md) — décisions du lot packaging Windows encore utiles.
- [`NOE-041-MODE-PORTABLE.md`](NOE-041-MODE-PORTABLE.md) — mode portable et isolation des données/configurations.
- [`NOE-032-SAUVEGARDE-RESTAURATION.md`](NOE-032-SAUVEGARDE-RESTAURATION.md) — invariants et limites des sauvegardes/restaurations.
- [`HARDENING_BUG_PROVENANCE.md`](HARDENING_BUG_PROVENANCE.md) — règles de provenance et durcissement des corrections.
- [`CONTRIBUTING_DOCS.md`](CONTRIBUTING_DOCS.md) — contribution, prévisualisation locale et publication de la documentation.

### UI/UX

- [`DESIGN_SYSTEM_UI_UX.md`](DESIGN_SYSTEM_UI_UX.md) — référence visuelle canonique : Fluent 2, tokens Material Design 3, profondeur ciblée et densité desktop.
- [`WXPYTHON_UI_RULES.md`](WXPYTHON_UI_RULES.md) — règles d'implémentation wxPython, parentage, sizers, scaling, thèmes et debugging.

### Métier et architecture

- [`COMMANDES_REPAS_POINTS_LIVRAISON.md`](COMMANDES_REPAS_POINTS_LIVRAISON.md) — commandes de repas et points de livraison.
- [`ARCHITECTURE-TIERS-PRESTATIONS-PLANNING.md`](ARCHITECTURE-TIERS-PRESTATIONS-PLANNING.md) — tiers, conventions, mises à disposition, EPS, planning et facturation.
- [`MAIL_MODULE_ARCHITECTURE.md`](MAIL_MODULE_ARCHITECTURE.md) — cible du module Messagerie.
- [`NOE-003-COTISATION-PRESTATION.md`](NOE-003-COTISATION-PRESTATION.md) — invariant cotisation/prestation conservé car encore pertinent.

## Source de vérité

En cas de contradiction :

1. code et tests intégrés ;
2. issues et PR GitHub ;
3. documents canoniques ci-dessus ;
4. historique Git pour comprendre la provenance.

Une PR ouverte n'est pas un comportement intégré tant qu'elle n'est pas fusionnée. Une PR fermée sans fusion reste uniquement une référence historique.

## Règle d'entretien

Lorsqu'une conversation produit une décision durable :

- corriger le code et ajouter un test si la décision est exécutable ;
- ouvrir ou mettre à jour une issue si du travail reste ;
- mettre à jour le document canonique correspondant si la règle est transversale ;
- éviter de créer un document concurrent lorsqu'un document existant peut porter l'information.

Ainsi, aucune conversation ChatGPT n'a besoin d'être conservée comme archive du projet.

## Publication MkDocs

La documentation publiée est construite depuis ce dossier. Pour la prévisualiser localement :

```bash
python -m pip install -r requirements-docs.txt
mkdocs serve
```

Le premier lot publie `master` uniquement. Le multi-version pourra être ajouté ultérieurement lorsqu'un besoin de publication simultanée de plusieurs versions sera établi.
