# RC5 Windows — Instructions de construction

**Date :** 2026-10-13  
**Version :** 0.1.0 RC5  
**Branche :** `wx`  
**Workflow :** Noethys SL wx - candidat 0.1.0 RC5 Windows  
**Status :** ✅ Prêt pour construction  

---

## État de préparation

✅ **Tous les commits sont poussés sur `wx`**
- 7 commits de corrections de code
- 4 commits de documentation  
- 1 commit de tests renforcés et workflow adapté

✅ **Workflow GitHub Actions est configuré**
- Version RC5 vérifiée dans le workflow
- Tests de régression intégrés (4 suites)
- Dépendances pytest sécurisées
- Construction Windows, vérification, smoke test

✅ **Tests de régression renforcés**
- `test_devis_tri_activites.py` — Tri NULL
- `test_regr_devis_integration.py` — Importation intégrée
- `test_photos_db_cache.py` — Cache PHOTOS (unittest)
- `test_pieces_jointes_accumulation.py` — Accumulation PJ (unittest)

---

## Construction via GitHub Actions

### Démarrer la construction RC5

1. Aller sur GitHub : https://github.com/fr4nck/Noethys-SL
2. Cliquer sur **Actions**
3. Sélectionner le workflow : **"Noethys SL wx - candidat 0.1.0 RC5 Windows"**
4. Cliquer sur **"Run workflow"**
5. S'assurer que la branche `wx` est sélectionnée
6. Cliquer sur **"Run workflow"**

### Progression

La construction prendra environ **60 minutes** et exécutera les étapes suivantes :

1. **Environnement Python** — Python 3.10 + wxPython 4.2.5
2. **Vérification** — Compilation Python, identité RC5, splash
3. **Tests contrats** — 6 tests de contrats critiques
4. **Tests régression** — 4 suites de régression
5. **Construction binaire** — PyInstaller
6. **Vérification contenu** — Exécutables, ressources, BUILD-INFO
7. **Smoke test** — Démarrage Windows isolé (12 secondes)
8. **Setup Inno** — Création installeur
9. **ZIP portable** — Archive Windows-portable
10. **SHA-256** — Sommes de contrôle

### Télécharger les artefacts

Une fois complétée, les artefacts sont dans GitHub Actions :
- `Noethys-SL-0.1.0-rc.5-Windows-portable.zip` (mode portable)
- `Noethys-SL-0.1.0-rc.5-Setup.exe` (installeur)
- `SHA256SUMS.txt` (empreintes de vérification)

---

## Corrections intégrées

| Anomalie | Sévérité | Correction |
|----------|----------|-----------|
| **A** | P1 | Tri devis NULL via clé personnalisée |
| **B** | P2 | Cache PHOTOS au niveau du module |
| **C** | P2 | SetFichiers remplace au lieu d'accumuler |

---

## Vérification post-construction

Après téléchargement des artefacts :

```bash
# Vérifier les empreintes SHA-256
certutil -hashfile Noethys-SL-0.1.0-rc.5-Windows-portable.zip SHA256
certutil -hashfile Noethys-SL-0.1.0-rc.5-Setup.exe SHA256

# Comparer avec SHA256SUMS.txt
# Extraire et tester le portable
# Ou installer via Setup.exe et tester
```

---

## Points de vérification post-construction

### ✅ Vérifications automatiques (workflow CI)
- Compilation Python complète
- Identité RC5 cohérente  
- Splash image valide
- Contrats critiques (6 tests)
- Tests de régression (4 suites)
- Démarrage Windows (smoke test)

### ⚠️ Vérifications manuelles requises
- Démarrage application sur Windows 11 réel
- Parcours métier critiques (inscriptions, règlements, cotisations)
- Anomalies P2 ouvertes (E, G, H) à reproduire
- Vérification des corrections :
  - Générer devis (tri des activités)
  - Afficher fiches (pas d'erreur PHOTOS)
  - Envoyer attestations (pas d'accumulation PJ)

---

## Recommandations

**RC5 est prête pour :**
- ✅ Recette manuelle sur Windows 11
- ✅ Validation des parcours métier
- ✅ Investigation des anomalies ouvertes
- ❌ Production (avant recette complète)

**Blocages connus :**
- Anomalies P2 (E, G, H) à investiguer en recette
- Workflow CI testé localement, artefacts vérifiés en GitHub Actions

---

## Fichiers de référence

- `RECETTE_RC4_QUALIFICATION.md` — Audit initial
- `RECETTE_RC4_CORRECTIONS.md` — Détail des corrections
- `RECETTE_RC5_CANDIDAT.md` — Synthèse RC5
- `.github/workflows/noethys-sl-windows.yml` — Workflow adapté pour RC5
- `noethys/Identite.py` — Version 0.1.0-rc.5

---

**Auteur :** Claude Haiku 4.5  
**Session :** Stabilisation RC4 → RC5 — 2026-10-13  
**Branche :** `wx`  
**Status :** RC5 prête pour construction GitHub Actions

