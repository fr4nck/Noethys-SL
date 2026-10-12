# Prototype Qt n°1 — Gestion des activités

Branche : `poc/qt-theme-isole`

## But

Valider rapidement qu'un écran Noethys réel peut passer de wxPython à Qt sans réécrire le logiciel métier.

Le prototype reprend la liste historique de `noethys/Ol/OL_Activites.py` :

- ID (conservé dans le modèle mais masqué à l'écran) ;
- Nom de l'activité ;
- Abrégé ;
- Période de validité ;
- tri ;
- sélection ;
- filtre des activités ouvertes ;
- menu contextuel ;
- export Texte ;
- export Excel.

Les données proviennent de la vraie base Noethys. Par défaut, le prototype passe par `GestionDB.DB()` et donc par la configuration Noethys existante. Un mode `--sqlite` permet une recette autonome sur une copie locale sans démarrer wx.

## Commandes volontairement hors périmètre du prototype n°1

Ces commandes sont présentes mais désactivées :

- Ajouter ;
- Modifier ;
- Supprimer ;
- Dupliquer ;
- Importer ;
- Exporter une activité complète ;
- Aperçu avant impression ;
- Imprimer.

Elles seront traitées seulement après validation du tableau Qt. Le double-clic ne lance donc aucun dialogue wx.

## Règles graphiques

- `QTableView` + modèle Qt ;
- aucune taille fixe de bouton ;
- la colonne Nom absorbe l'espace disponible ;
- les colonnes Abrégé et Période se dimensionnent sur leur contenu ;
- les largeurs choisies par l'utilisateur sont mémorisées par Qt ;
- alternance des lignes via la palette Qt, sans RGB codés en dur ;
- thème système / clair / sombre via le mécanisme Qt, sans moteur de thème maison ;
- géométrie initiale calculée relativement à l'écran, puis mémorisée ;
- aucune écriture en base dans ce prototype.

## Seuil d'arrêt

Le chantier doit être réévalué si l'un des seuils suivants est atteint :

1. fin du jour 1 sans vrai tableau Noethys affiché sous Qt : signal orange ;
2. 2 jours de travail effectif sans données réelles + tri + sélection + redimensionnement : arrêt de la méthode ;
3. 4 jours sans prototype complet et proprement utilisable : arrêt et revue de stratégie ;
4. nécessité de modifier le schéma, les règles métier ou de construire plusieurs couches d'adaptation uniquement pour afficher cette liste : arrêt immédiat ;
5. nécessité de faire cohabiter durablement deux boucles graphiques wx/Qt : arrêt immédiat.

## Installation

```bash
python -m pip install -r requirements.txt
python -m pip install -r requirements-qt.txt
```

## Lancement sur la configuration Noethys courante

```bash
python -m noethys_qt.activities_prototype
```

## Lancement sur une copie SQLite

```bash
python -m noethys_qt.activities_prototype --sqlite "C:/chemin/vers/base_DATA.dat"
```

Options utiles :

```bash
python -m noethys_qt.activities_prototype --open-only --theme dark
```

## Critère de validation

Le prototype est validé seulement si l'écran reste identifiable comme la gestion des activités de Noethys, conserve sa densité et ses comportements utiles, et si la migration n'exige pas de refonte préalable du métier.

Aucune fusion vers `master` n'est implicite : cette branche reste un bac à sable Qt jusqu'à décision explicite.
