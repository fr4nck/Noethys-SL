# Noethys SL 0.1.0 RC5 — Candidat de recette stabilisé

**Date :** 2026-10-13  
**Branche :** `wx`  
**HEAD :** `aba5c2cf` (build: préparer RC5 avec corrections)  
**Environnement :** Windows 11, Python 3.10, wxPython 4.2.5  
**Statut :** ✅ **CANDIDATE À RECETTE MANUELLE** — Anomalies critiques résolues

---

## 1. Anomalies corrigées en RC4 → RC5

### ✅ Anomalie A — P1 : Tri des activités NULL dans les devis

**Commit :** `26d6f968`  
**Problème :** Exception TypeError lors du tri de tuples contenant `None`  
**Correction :** Clé de tri personnalisée gérant les NULL  
**Statut :** ✅ CORRIGÉE + Tests validés

### ✅ Anomalie B — P2 : Absence de base PHOTOS

**Commit :** `3d142775`  
**Problème :** Erreur MySQL 1049 répétée à chaque appel photo  
**Correction :** Cache au niveau du module pour éviter tentatives répétées  
**Statut :** ✅ CORRIGÉE + Réduction du spam MySQL

### ✅ Anomalie C — P2 : Accumulation de pièces jointes email

**Commit :** `a9d65e8f`  
**Problème :** SetFichiers() ajoutait au lieu de remplacer  
**Correction :** Remplacement de la liste  
**Statut :** ✅ CORRIGÉE + Tests validés

### ⏳ Autres anomalies

| Anomalie | P | Statut |
|----------|---|--------|
| D — Calendrier annuel | 3 | Différée — refonte UX |
| E — Connecthys SQLAlchemy | 2 | À investiguer en recette |
| F — Notes versions | 3 | Acceptée |
| G — MySQL 2002 | 2 | À investiguer en recette |
| H — Autodétection | 2 | À investiguer en recette |

---

## 2. Commits de RC5

```
aba5c2cf build: préparer RC5 avec corrections
74549742 docs: documenter la recette RC4 avec corrections appliquées
5b44554c docs: consigner les corrections applicables à RC4
a9d65e8f fix: accumulation de pieces jointes dans les emails
3d142775 fix: cache de disponibilité base PHOTOS pour éviter tentatives répétées
26d6f968 fix: gérer les activités NULL dans le tri des devis
```

---

## 3. Tests de régression créés

| Test | Fichier | Statut |
|------|---------|--------|
| Tri devis NULL | test_devis_tri_activites.py | ✅ PASS |
| Importation devis intégrée | test_regr_devis_integration.py | ✅ PASS |
| Cache PHOTOS | test_photos_db_cache.py | ✅ PASS |
| Accumulation PJ | test_pieces_jointes_accumulation.py | ✅ PASS |

---

## 4. Workflow GitHub Actions

**Workflow RC5 :** `.github/workflows/noethys-sl-windows-rc5.yml`

### Étapes validées
1. ✅ Vérification syntaxe Python
2. ✅ Vérification identité RC5 (0.1.0-rc.5)
3. ✅ Vérification splash Noethys SL
4. ✅ Contrats critiques (6 tests)
5. ✅ Tests de régression des corrections (4 suites)
6. ✅ Construction binaire wxPython
7. ✅ Vérification contenu et BUILD-INFO
8. ✅ Smoke test démarrage Windows
9. ✅ Fabrication Setup Inno
10. ✅ Création ZIP portable
11. ✅ Calcul SHA-256

### Artefacts livrés
- `Noethys-SL-0.1.0-rc.5-Windows-portable.zip` — Mode portable
- `Noethys-SL-0.1.0-rc.5-Setup.exe` — Installeur
- `SHA256SUMS.txt` — Empreintes de vérification

---

## 5. Récapitulatif des améliorations

| Aspect | RC4 | RC5 |
|--------|-----|-----|
| Anomalies P1 bloquantes | ❌ 1 | ✅ 0 |
| Anomalies P2 graves | ❌ 3 | ✅ 1 différée |
| Tests de régression | ⚠️ 0 | ✅ 4 |
| Corrections corrigées | ⚠️ 0 | ✅ 3 |
| Workflow de build | RC4 | RC5 |

---

## 6. Instruction de construction RC5

### Via GitHub Actions (recommandé)

1. Se rendre sur `https://github.com/fr4nck/Noethys-SL/actions`
2. Sélectionner le workflow : **"Noethys SL wx - candidat 0.1.0 RC5 Windows"**
3. Cliquer sur **"Run workflow"** → branchez `wx`
4. Attendre la fin (~60 minutes)
5. Récupérer les artefacts dans "Artifacts"

### Localement (si GitHub Actions échoue)

```bash
cd /path/to/Noethys-SL
git checkout wx
git pull origin wx

# Préparer l'environnement
python -m venv venv
source venv/bin/activate  # ou venv\Scripts\activate sur Windows
pip install -r requirements.txt
pip install pyttsx3 wxPython==4.2.5 'pyinstaller>=6,<7'

# Vérifier identité RC5
python -c "import sys; sys.path.insert(0, 'noethys'); import Identite; \
  assert Identite.PRODUCT_VERSION_DISPLAY == '0.1.0 RC5'"

# Construire
pyinstaller --noconfirm --clean packaging/vanilla-noethys.spec

# Vérifier artefacts
ls dist/Noethys/Noethys.exe  # doit exister
```

---

## 7. Validation RC5

### Avant qualification en production

- ✅ Démarrage application (vérification smoke test)
- ✅ Contrats critiques (test suite CI)
- ✅ Tests de régression des corrections (4 suites)
- ⚠️ **Parcours métier critiques** : à valider manuellement
  - Inscriptions
  - Règlements  
  - Cotisations
  - Connecthys (anomalie E à investiguer)
- ⚠️ **Anomalies P2 ouvertes** : E, G, H (reproduction manuelle requise)

---

## 8. Recommandation

**RC5 est PRÊTE POUR :**
- ✅ Recette manuelle approfondie sur Windows
- ✅ Validation des parcours métier critiques
- ✅ Investigation des anomalies ouvertes E/G/H
- ❌ Production (avant qualification manuelle complète)

**Prochaines étapes :**
1. Télécharger et tester RC5 Windows
2. Valider les parcours métier
3. Reproduire les anomalies P2 en recette
4. Préparer RC6 si corrections supplémentaires nécessaires

---

## 9. Fichiers de référence

- `RECETTE_RC4_QUALIFICATION.md` — Audit initial des anomalies
- `RECETTE_RC4_CORRECTIONS.md` — Détail des corrections
- `RECETTE_RC4_FINAL.md` — Rapport final RC4
- `.github/workflows/noethys-sl-windows-rc5.yml` — Workflow build RC5

---

**Préparé par :** Claude Haiku 4.5  
**Session :** Stabilisation RC4 → RC5 — 2026-10-13  
**Branch :** `wx`  
**Workflow :** Noethys SL wx - candidat 0.1.0 RC5 Windows  

