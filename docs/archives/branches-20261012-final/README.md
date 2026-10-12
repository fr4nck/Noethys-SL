# Élagage : archives finales et décisions — 12/10/2026

Archives historiques conservées avant retrait des branches, avec chemins et
blobs source. Aucun code ici n’est activé dans Noethys ni dans la CI : les tests,
scripts et workflows sont sous docs/archives/ et restent des références.
La reprise d’un outil doit choisir son contexte de sources et un profil fictif ;
ces copies ne sont pas des outils de production prêts à lancer.

La sauvegarde Git vérifiée conserve tous les commits et modes de fichiers.
Le corpus dossier-conservation.json explique pour chacune des 30 branches
maintenues ses fichiers et fonctions différents, comparés aux 14 têtes protégées.

| Source retirée | SHA | Motif et conservation |
| --- | --- | --- |
| audit/vanilla-deep-scan-20260826 | cacafa37eb31e35f60ae1b6eb2e96237274159c6 | No application runtime changes in the branch delta. No protected runtime/workflow/test references to the unique tool paths or modules across all 14 protected heads. Complete changed source files, tests and workflows retained as inert documentation archives and full Git history in verified bundle. |
| audit/vanilla-ui-command-inventory | eef718234412ddf98867a2a4bbdbf29241b18397 | No application runtime changes in the branch delta. No protected runtime/workflow/test references to the unique tool paths or modules across all 14 protected heads. Complete changed source files, tests and workflows retained as inert documentation archives and full Git history in verified bundle. |
| audit/vanilla-upstream-630ef | 58dcab19fd0e2b542ce3c06c28f60422742c79ed | No application runtime changes in the branch delta. No protected runtime/workflow/test references to the unique tool paths or modules across all 14 protected heads. Complete changed source files, tests and workflows retained as inert documentation archives and full Git history in verified bundle. |
| test/vanilla-windows-ui-driver-prototype | be87c00ea51a6fef8ad33cf2ae848eaa6b676a85 | No application runtime changes in the branch delta. No protected runtime/workflow/test references to the unique tool paths or modules across all 14 protected heads. Complete changed source files, tests and workflows retained as inert documentation archives and full Git history in verified bundle. |
| noe-042-rc-gate | 085115c40fa5b2072bfdabebdf2f099330945b76 | Gate conditions and shell commands are identical in protected branch, ignoring labels/comments/action version tags. Historical gate test blob is identical and passes on the preserved workflow. Workflow build additions differ and are archived; no release or package is executed. |
| refactor/ui-navigation-repens | 6bf8a4cceb8bdf0da6ea13cb20b5c98fc6402f04 | All five functions added/modified by this branch relative to its common ancestor have identical ASTs in protected branch. No source function deleted, module imports/globals unchanged by source. Test blob identical. Remaining file difference is ConfigurerGrille inherited from the common ancestor and subsequently delegated to Style.appliquer_grille in protected branch. |
| feat/rc2-reception-quotient | f48450935bb18125b3b46a4e5e5346bea7804076 | All branch-owned changes preserved in protected RC2 reference. Fourteen delta files have identical blobs; in remaining file Traitement.Traitement_pieces AST is identical. No own binding was removed. Quotient atomic-write and received-file regressions pass on synthetic/memory data with network blocked. Other file differences are inherited/evolved code, retained in full source archive. |
