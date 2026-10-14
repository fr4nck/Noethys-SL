# Prototype Qt isolé (branche `qt`)

Réintégré le 12/10/2026 depuis `poc/qt-theme-isole` (`cba459cd`, archivée),
**sans activation par défaut** et sans modifier l'application wxPython.

## Statut

- **Prototype non qualifié** : il ne fait partie d'aucun paquet (le spec
  PyInstaller et les workflows Windows ne l'incluent pas) et n'est jamais lancé
  par `Noethys.exe`.
- Code isolé dans `noethys_qt/` (racine du dépôt), tests dans `tests_qt/`,
  dépendances optionnelles dans `requirements-qt.txt` (PySide6,
  mysql-connector-python, XlsxWriter). `requirements.txt` est inchangé.
- Aucun import du runtime wx, sauf le mode historique de
  `activities_prototype.py` (lecture via `GestionDB`), lui aussi soumis à la
  garde ci-dessous.

## Garde de données (ajout Noethys-SL)

Sans `--sqlite`, le prototype ouvrirait la base configurée dans Noethys,
c'est-à-dire possiblement la production, et son éditeur sait écrire. Il refuse
donc cet accès par défaut :

```bash
python -m pip install -r requirements-qt.txt
python -m noethys_qt --sqlite <copie_fictive_DATA.dat>
```

L'accès à la base configurée n'est possible qu'avec la variable
`NOETHYS_QT_BASE_CONFIGUREE=1`, en connaissance de cause et jamais sur un poste
ou un profil pointant la production. Test : `tests_qt/test_garde_base_configuree.py`.

## Qualification

- Workflow `.github/workflows/qt-prototype.yml` : Windows, Python 3.11, PySide6,
  tests `tests_qt` hors écran (`QT_QPA_PLATFORM=offscreen`), déclenché sur la
  branche `qt` ou à la demande.
- Aucune recette graphique sur un poste de travail : runner isolé ou machine
  virtuelle uniquement.

## Lot Qt 1 — consultation Individus/Familles (14/10/2026)

- Coque Qt autonome dans `noethys_qt/noethys_native.py`, non lancée par `Noethys.exe`.
- Recherche via `people_search.py` : connexion SQL dans un worker, dernière
  recherche prioritaire, résultats périmés ignorés, boucle Qt non bloquante.
- Sélection zéro famille : fiche individu ; une famille : ouverture directe ;
  plusieurs familles : choix **explicite**, jamais la première par défaut.
- `people_details.py` : fiches **consultatives minimales** Famille/Individu
  (ID stable, identité, coordonnées, rattachements), lecture hors thread UI,
  navigation réversible, aucune méthode d'écriture.
- Données : tests SQLite fictifs, aucune migration SQL ni modification de
  `main`, de `wx`, des binaires RC7 ou des profils utilisateurs.
- Qualification automatique Windows/PySide6 hors écran :
  [CI #38548298813](https://github.com/fr4nck/Noethys-SL/actions/runs/38548298813)
  **SUCCÈS** au commit `7042c57e`.
- **Non qualifié** : recette graphique Windows sur VM, volumes réels,
  autres schémas, ergonomie définitive, parité des fiches wx complètes,
  droits d'accès et moteur des consommations. Les catégories de
  rattachement affichées reprennent le prototype ; les qualifier contre
  le référentiel métier avant d'autoriser une écriture.

### Prochaine action

Recette souris/clavier sur VM Windows et copie fictive isolée, puis
extension progressive des fiches sans dépendance au runtime wx.

## Travail restant avant toute activation

1. Recette utilisateur sur copie fictive, en machine virtuelle.
2. Écritures (création, modification, duplication, suppression d'activités) :
   revue de chaque transaction contre le comportement wx de référence.
3. Décision de produit : périmètre Qt, packaging séparé, cohabitation avec wx
   (une seule boucle graphique par processus).

Documents du prototype : [écran Activités](ACTIVITIES_PROTOTYPE.md),
[inventaire de migration Qt](QT_MIGRATION_INVENTORY.md).
