# AFAS V2 — prototype préparatoire (non intégré)

> **Remplacé** : le module développé se trouve dans `noethys/Utils/UTILS_AFAS2_*.py` et `noethys/Dlg/DLG_AFAS2_Declarations.py` (voir `docs/afas/MODULE_DECLARATIONS_AFAS_V2.md`). Ces prototypes restent comme référence historique ; leurs anciens formats de preset sont convertibles par `UTILS_AFAS2_Presets.MigrerAncienFormat`.

Ce répertoire contient un contrat Python autonome et ses tests fictifs. Aucun module applicatif Noethys, aucune base PMSL et aucune branche wx/qt n'est modifiée par ce lot.

- `afas_contract.py` : matrice ALSH/ALSH Ados, validation de catalogue, filtrage de sélection, résolution explicite des couples IDactivite/IDgroupe, validation des catégories d'unités, sérialisation JSON en mémoire.
- `test_afas_contract.py` : 15 tests unitaires fictifs (15 PASS / 0 FAIL / 0 SKIP exécutés hors wx et hors MySQL le 23/10/2026).

Exécution depuis ce répertoire : `python -m unittest -v test_afas_contract.py`.

## Limitations bloquantes

- Les IDs réels n'ont pas été identifiés : les IDs de tests sont fictifs et ne doivent jamais être utilisés pour les données PMSL.
- La matrice initiale est figée ; une future préconfiguration éditable et versionnée est nécessaire.
- `save_profile`/`load_profile` sérialisent en mémoire sans persistance durable.
- Aucun calcul des heures réalisées/facturées CAF, garderies ou AEEH n'est qualifié ici.
- Aucun anti-double-comptage des consommations ou filtrage de couples dans le moteur existant n'est démontré.
- Aucun menu autonome, aucune interface wxPython, aucun export CAF et aucune recette Windows ne sont livrés.

## Intégration ultérieure

Respecter les règles de `AGENTS.md`, préserver la RC9 sur `wx` et qualifier chaque évolution métier avant de raccorder ce prototype à l'application. Ne pas annoncer ce prototype comme une fonctionnalité AFAS livrée.
