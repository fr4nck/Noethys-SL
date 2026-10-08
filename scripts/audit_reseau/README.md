# Outils de vérification du rail réseau 1

Outils **hors production**, utilisés par `docs/audit/CONTRE_QUALIFICATION_RAIL1.md`. Aucun ne contacte un service distant ni ne modifie le code de Noethys.

| Outil | Usage |
|---|---|
| `contrat_connecthys_par_version.py` | Vérifie, sur chaque tag de Connecthys, les éléments du contrat (`syncup`, `syncdown`, jeton, `ref_unique`, SV2, pièces). Nécessite un clone local de `Noethys/Connecthys`. |
| `imports_reportlab.py` | Repère les imports ReportLab devenus introuvables avec la version installée (598 imports analysés, 0 introuvable sur la branche sous ReportLab 5.0.1). |
| `pdf_recu.py`, `pdf_rappel.py`, `pdf_cotisation.py`, `pdf_releve.py` | Génèrent un vrai PDF avec le moteur concerné, sur une base de test synthétique. `CODE_ROOT` désigne l'arborescence à tester (branche ou RC2). |
| `comparer_pdf.py` | Compare deux PDF après normalisation des dates et de l'identifiant (ReportLab n'est pas déterministe sur ces champs). |

**Comparer le rendu avant/après le retrait de `ShowBoundaryValue`** : générer le même document avec une copie de la RC2 (`SHIM_SBV=1`) puis avec la branche, sous la même version de ReportLab, puis comparer :

```
CODE_ROOT=/chemin/rc2     SHIM_SBV=1 xvfb-run -a python3 scripts/audit_reseau/pdf_recu.py avant.pdf
CODE_ROOT=/chemin/branche            xvfb-run -a python3 scripts/audit_reseau/pdf_recu.py apres.pdf
python3 -I scripts/audit_reseau/comparer_pdf.py avant.pdf apres.pdf
```

Vérifier que la ligne `ORIGINE` affichée par le script désigne bien l'arborescence voulue : le jeu de test ajoute lui-même son propre dossier au chemin d'import, ce qui peut faire charger le mauvais code.
