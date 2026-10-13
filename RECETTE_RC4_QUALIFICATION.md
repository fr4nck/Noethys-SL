# Recette Noethys-SL RC4 — Passe 1 Qualification

**Date :** 2026-10-13  
**Branch :** wx  
**HEAD :** 2fab2dc8  
**Environnement :** Windows 11, Python 3.10, wxPython 4.2.5  

## État initial

- RC4 construite sur commit 2fab2dc8.
- Portable RC4 présent : `noethys/Portable/`.
- Modifications locales : aucune (git status propre sauf untracked Portable).
- Résultats de recette antérieurs (RC2) : Consultation consommations, factures, attestations et export PDF OK.

## Anomalies classées

### Anomalie A : Génération de devis — P1 ⚠️ CONFIRMÉE

**Fichier :** `noethys/Dlg/DLG_Impression_devis.py`, ligne 231  
**Problème :** `listeActivites.sort()` échoue avec une exception `TypeError: '<' not supported between instances of 'str' and 'NoneType'`

**Cause :** La requête SQL (ligne 213-221) utilise une jointure gauche externe sur `prestations.IDactivite`, ce qui peut retourner des lignes avec `nom = NULL`. La liste contient donc des tuples `(None, IDactivite)`. Python 3 refusecomparer `None` avec `str`.

**Preuves :**
- Code source : tuples `(nom, IDactivite)` où `nom` peut être `None`.
- SQL : `LEFT OUTER JOIN` sans jointure interne obligatoire.

**Statut :** BUG CONFIRMÉ — Bloque la génération de devis.

---

### Anomalie B : Accès à la base PHOTOS supprimée — P2 ⚠️ CONFIRMÉE

**Fichier :** `noethys/Ctrl/CTRL_Photo.py`, lignes 30 et 79  
**Problème :** Tentatives de connexion à une base "PHOTOS" séparate via `GestionDB.DB(suffixe="PHOTOS")`. Quand la base n'existe pas, MySQL retourne l'erreur 1049 (unknown database).

**Cause :** La base `pelemele_photos` a été supprimée volontairement. Le code accède toujours à une base PHOTOS externe.

**Preuves :**
- Ligne 30 : `DB = GestionDB.DB(suffixe="PHOTOS")`
- Ligne 79 : même appel
- Gestion d'erreur basique (test `DB.echec`), mais accès non gracieux.

**Statut :** BUG CONFIRMÉ — Répétition d'erreur MySQL 1049 ; photosmises en défaut lors de l'ouverture/suppression de fiches.

---

### Anomalie C : Envoi d'attestations — Accumulation de pièces jointes — P2 ❓ À INVESTIGUER

**Observation :** Deux envois manuels d'attestations montrent une accumulation possible des pièces jointes.

**Preuves :**
- Premier email : une attestation.
- Second email : deux attestations apparemment identiques, noms de fichiers différents.

**Statut :** HYPOTHÈSE — Pas de trace de code d'envoi examinée en détail. À vérifier dans `UTILS_Envoi_email.py` et la gestion d'état des pièces jointes.

**Priorité :** P2 — Sécurité métier (pas d'envoi d'une pièce jointe appartenant à une autre famille).

---

### Anomalie D : Calendrier annuel historique — Dialogue ancien — P2 ⚠️ CONFIRMÉE PARTIELLEMENT

**Fichier :** `DLG_calendrier_simple` et `CTRL_Saisie_date.Date2`  
**Problème :** Le calendrier annuel historique apparaît encore lors de l'édition des attestations. Autres dialogues `DLG_calendrier_simple` appelés par le composant partagé : au moins 20 fichiers dans l'échantillon.

**Preuves :**
- Le composant `CTRL_Saisie_date.Date2` utilise `DLG_calendrier_simple` en lieu de calendrier moderne.
- Impact large : 20+ dialogues concernés.

**Statut :** ANOMALIE CONFIRMÉE — Impact fonctionnel mineur (UX ancienne), mais diffusion large.

**Priorité :** P3 — Correction cosmétique/UX, pas un blocage fonctionnel.

---

### Anomalie E : Connecthys et SQLAlchemy — Avertissements ORM — P2 ⚠️ À EXAMINER

**Problème :** Quatre avertissements de relations ORM potentiellement conflictuelles observées lors de la synchro Connecthys.

**Preuves :** Avertissements SQLAlchemy, nature exacte à identifier.

**Statut :** SIGNAL — Pas examiné en détail. Vérifier s'il y a une corruption de données, un conflit de relations ou un faux positif.

**Priorité :** P2 — À qualifier avant qualification définitive.

---

### Anomalie F : Notes de versions — Historique incomplet — P3

**Problème :** Les notes RC3 et RC4 manquent dans l'affichage. RC1 et RC2 sont après l'historique ancien.

**Constante :** `GetVersionLogicielle()` lit la première ligne de `Versions.txt` pour identifier la version technique.

**Statut :** COSMÉTIQUE — Pas de blocage fonctionnel, mais documentation incomplète.

**Priorité :** P3 — Correction mineure.

---

### Anomalie G : Connexion MySQL distante — Erreur 2002 — P2 ❓ À INVESTIGUER

**Problème :** Erreur 2002 (Unable to connect to MySQL server) lors d'une connexion distante.

**Preuves :** Signal uniquement, cause non identifiée.

**Statut :** NON QUALIFIÉ — À reproduire pour identifier s'il s'agit d'une configuration réseau ou d'une anomalie de code.

**Priorité :** P2 — Peut bloquer les déploiements réseau.

---

### Anomalie H : Autodétection au démarrage — Signal d'anomalie — P2 ❓ À INVESTIGUER

**Observation :** Autodétection signalant une anomalie au démarrage, nature non identifiée.

**Statut :** NON QUALIFIÉ — À reproduire et examiner les logs.

**Priorité :** P2 — Peut indiquer un défaut de configuration ou une régression.

---

## Parcours non testés depuis RC4

- Inscriptions
- Reçus de règlements
- Consultations avancées

## Prochaines étapes (Passe 2)

1. **P1 — Anomalie A :** Correction du tri des activités (gestion de `None`).
2. **P2 — Anomalie B :** Gestion gracieuse de l'absence de base PHOTOS (préférence ou fallback).
3. **P3 — Anomalie C/E :** Investigation détaillée avant correction.
4. **P4 — Tests de régression :** Vérifier que les corrections ne cassent pas les parcours validés.

