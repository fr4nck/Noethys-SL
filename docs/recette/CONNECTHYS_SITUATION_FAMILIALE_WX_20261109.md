# Connecthys-SL — Recette de la situation familiale wx (09/11/2026)

## Périmètre et verdict

- Branche : `wx` ; correctif de géométrie : `0274601078203960c278e3a5956aa8e74d52c84c`.
- Première exécution graphique : [#42666116572](https://github.com/fr4nck/Noethys-SL/actions/runs/42666116572), **3 échecs de géométrie sur 4 tests** : écran Windows de 1044 × 800, contenu métier en débordement vertical.
- Correctif : zone centrale `wx.ScrolledWindow`, commandes Automatique/Manuel/Fermer fixes, taille minimale verticale abaissée, délégation des événements du calendrier au vrai dialogue ; aucun calcul de réservation, facturation ou adhésion modifié.
- Seconde exécution : [#42667482310](https://github.com/fr4nck/Noethys-SL/actions/runs/42667482310), **128 tests métier Connecthys PASS et 4 tests graphiques réels wx PASS**, zéro échec, Windows Python 3.10 + wxPython 4.2.5, réseau bloqué, sources non empaquetées.
- [Quatre captures PNG de la fenêtre avec données entièrement fictives](https://github.com/fr4nck/Noethys-SL/actions/runs/42667482310/artifacts/13697192624) : `01_situation_famille_fictive.png`, `02_autre_famille_fictive.png`, `03_lecture_indisponible.png`, `04_autre_categorie.png`. Captures consultées et recadrage/comportement contrôlés. L'artefact de CI est soumis à rétention.
- **Verdict : PASS sur sources wx et contrôles de contrat ; recette sur un exécutable installé et sur MySQL isolé : NON TESTÉE. Aucune RC générale autorisée par ce seul résultat.**

## Matrice de recette automatisée

| Vérification | Preuve | Statut |
| --- | --- | --- |
| Vraie classe `DLG_Saisie_portail_demande.Dialog` instanciée sur Windows | Test graphique `test_01` ; widgets réels et capture PNG | PASS |
| Cartes Soldes / Factures impayées / Adhésion sur une seule ligne | Géométrie Win32 des panneaux, titre, tableau et montants fictifs | PASS |
| Disparition du solde rouge en doublon | `ctrl_solde` masqué, toujours utilisé pour le solde global et le jeton PDF/email | PASS |
| Taux d'annulation sur l'historique familial des demandes du portail | Tests métier SQLite synthétiques et `3 / 24 = 12,5 %` dans le dialogue | PASS |
| Changement de famille (2 factures -> 0, adhésion valide -> expirée, taux 12,5 -> 0 %) | Test graphique `test_02` + capture | PASS |
| Lecture indisponible sans zéro fictif ni modale, boutons toujours disponibles | Test graphique `test_03` + capture | PASS |
| Autre catégorie sans synthèse inappropriée | Test graphique `test_04` + capture | PASS |
| Petit écran 1044 × 800, défilement central et trois commandes fixes | Échec reproductible -> correction -> assertions et capture après défilement | PASS |
| Anti-doublons, reprise automatique/manuelle, états SQL et contrôles métier | 128 tests sous SQLite fictif / gardes réseau | PASS sur fixture |
| Parcours de l'application empaquetée, sans patchs/mocks | Aucun exécutable installé ouvert dans ce run | NON TESTÉ |
| Base Noethys MySQL de recette, concurrence entre postes et interruptions du vrai réseau | Ce run bloque tout réseau sortant | NON TESTÉ |
| Envoi vers un vrai serveur SMTP / Connecthys installé | Aucune émission réelle autorisée sur le runner | NON TESTÉ |

## Protocole restant sur application Windows installée

Utiliser uniquement un **candidat portant le correctif ci-dessus** ; une ancienne préversion installée ne contient pas ces modifications. Ne pas publier de release et ne pas relier la recette au serveur, au SMTP ou à la base familiale de production.

1. Employer un profil, des comptes et une base **fictifs / copie isolée et non connectée**, dans un sous-dossier de travail dédié, par exemple `C:\_Atelier_IA\Noethys-SL\Recette_Connecthys`. Ne jamais déplacer ni supprimer les sauvegardes d'origine.
2. Ouvrir trois demandes fictives successives : famille avec deux factures partiellement réglées et adhésion active ; autre famille avec avoir et cotisation expirée ; famille sans historique exploitable. Contrôler les soldes au jour / global et la ventilation des factures par recoupement indépendant.
3. Sur écran standard et sur petit écran, contrôler le rendu complet : trois cartes sans superposition, plus de solde rouge redondant, zone centrale défilante, commandes permanentes et aucune sortie involontaire du mode maximisé/plein écran.
4. Sur la copie isolée, interrompre l'enregistrement d'une demande entre calcul et validation SQL, puis la reprendre **en automatique et en manuel**, en contrôlant le nombre et les identifiants exacts de consommations avant/après ; aucune double réservation ou double réponse.
5. Contrôler les annulations de demandes du portail pour tous les enfants de la famille : historique complet conservé, nouvelle réservation après annulation, suppressions sans ajout initial, zéros/non-calculables distincts. Ne pas confondre état de la demande et présence physique.
6. Tester les emails exclusivement via transport fictif et réponses d'acceptation simulées : pas de double email accepté lors d'une reprise ; aucun email réel.
7. Contrôler la même procédure sur un **serveur MySQL temporaire indépendant** si la RC vise les postes en réseau. Capturer les différences SQLite/MySQL et une éventuelle contention de verrous, sans conserver de données de famille.

**STOP-GATE de publication :** conserver les preuves de l'exécutable et de la base isolée, vérifier le SHA testé, les états SQL, les captures et les emails fictifs. Aucun statut PASS ne sera accordé à ces étapes avant une vraie exécution.

## Traçabilité

Sources : `tests/test_connecthys_gui_recette_wx.py`, `tests/test_connecthys_situation.py`, `noethys/Dlg/DLG_Saisie_portail_demande.py`, `noethys/Utils/UTILS_Portail_situation.py`, `.github/workflows/noethys-sl-connecthys-qualification.yml`.

Aucun fichier métier, profil Windows du directeur ni base SQL de production ne sont modifiés par cette recette CI.
