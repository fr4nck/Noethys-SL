# Noethys SL

**Noethys SL** est une évolution de Noethys Desktop, logiciel libre de gestion multi-activités pour les accueils de loisirs, structures périscolaires, cantines, clubs sportifs et structures culturelles.

Le projet conserve le socle métier et la compatibilité des données historiques de Noethys tout en modernisant progressivement le runtime Python 3 / wxPython, l'interface, la fiabilité des traitements et plusieurs fonctions métier.

## État au 30 septembre 2026

La ligne **Noethys SL 0.1.0 RC1** est la base de qualification courante.

Elle comprend notamment :

- une interface Windows stabilisée et l'identité publique Noethys SL ;
- la compatibilité Python 3 / wxPython Phoenix ;
- des correctifs de fiabilité sur l'envoi d'e-mails, la synchronisation Connecthys, Nomadhys, les listes et plusieurs traitements historiques ;
- un calendrier saisonnier septembre → août avec T1/T2/T3 et S1/S2 ;
- la génération par lot des vacances selon la règle dimanche → dimanche ;
- le socle de prévision et d'actualisation CAF / AFAS ;
- la génération de conventions via le moteur Noedoc historique ;
- des modèles de convention associatif, PMSL et scolaire ;
- la gestion complète des modèles Convention : installation, édition Noedoc, duplication, renommage, modèle par défaut et suppression contrôlée ;
- un packaging Windows portable qualifié.

La version interne historique `1.3.4.2` reste utilisée pour les fichiers, les migrations historiques et les mécanismes de compatibilité existants.

## Windows

Windows est la cible de distribution prioritaire.

Le portable Windows de référence a été construit et qualifié le **29 septembre 2026**. La chaîne de qualification couvre la compilation, wxPython, les tests de non-régression du workflow, la construction du paquet et un smoke test de démarrage de `Noethys.exe`.

## Installation depuis les sources

Le projet reste exécutable depuis les sources avec Python 3 et les dépendances du dépôt :

```bash
git clone https://github.com/fr4nck/Noethys-SL.git
cd Noethys-SL
pip install -r requirements.txt
python noethys/Noethys.py
```

Selon la plateforme, l'installation de wxPython et de certaines dépendances système peut demander des paquets spécifiques.

## Documentation

- [Roadmap](docs/ROADMAP.md)
- [Historique des versions](noethys/Versions.txt)
- [Gestion des modèles Convention](docs/dev/CONVENTION_MODELES_GESTION.md)

## Principes de développement

Les évolutions cherchent à préserver les bases et configurations existantes, à éviter les migrations implicites de schéma et à privilégier les corrections ciblées et testables. Les changements touchant aux données métier doivent être qualifiés sur une copie de base réelle avant publication.
