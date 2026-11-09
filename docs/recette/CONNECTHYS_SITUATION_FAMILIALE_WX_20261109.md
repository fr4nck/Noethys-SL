# Connecthys-SL — Recette de la situation familiale wx (09/11/2026)


## Qualification complémentaire : installation et MySQL (09/11/2026)

- **Windows, exe réellement installé : PASS** sur [GitHub Actions #42673996161](https://github.com/fr4nck/Noethys-SL/actions/runs/42673996161), SHA `8a090255d85afc3671b3feb0dc59d12fa84cf094`. PyInstaller a construit `Noethys.exe`, Inno Setup a produit et installé le Setup dans un sous-dossier **temporaire du runner Windows**, puis l'application a atteint l'étape de fin d'initialisation `oninit_fin` en ouvrant une base SQLite **entièrement fictive**. La génération du profil a compté **0 tentative réseau**. Les **5 tests graphiques wx** (dont le calendrier reparenté dans la zone défilante) sont également PASS. [Diagnostics d'installation](https://github.com/fr4nck/Noethys-SL/actions/runs/42673996161/artifacts/13698924006). **Le scénario interactif de traitement de réservations n'a pas été exécuté dans le binaire installé.**
- **MySQL 5.7.44 local : PASS** sur [GitHub Actions #42674823345](https://github.com/fr4nck/Noethys-SL/actions/runs/42674823345), SHA `55fabfafb1fdadd74acf5e0be55dd0f0a6e6c302`. Archive officielle contrôlée par SHA-256, serveur limité à `127.0.0.1:3399` sur runner Windows, bases temporaires de test et nettoyage. **12/12 tests MySQL PASS**, notamment reprise d'une tentative interrompue sans verrou persistant, refus d'un second traitement concurrent entre connexions, jetons de reprise, états SQL, suivis d'emails simulés, solde du jour, ventilation des factures, adhésion et historique d'annulation familial.
- **Qualification ciblée totale : 145/145 PASS** sur le run MySQL : **128 tests métier SQLite + 5 tests wx GUI + 12 tests MySQL**. Tests sur données synthétiques et garde réseau, sans secrets ni communications PMSL. C'est une preuve sur des chemins distincts, pas la recette d'un **parcours métier complet dans l'installateur**.
- Les workflows anciens [RC9 MySQL #42672430281](https://github.com/fr4nck/Noethys-SL/actions/runs/42672430281) et [RC10.55 candidat #42672723196](https://github.com/fr4nck/Noethys-SL/actions/runs/42672723196) ont échoué **avant création de leurs jobs de test** : ils ne prouvaient ni PASS ni FAIL métier. Les nouveaux chemins isolés ci-dessus produisent de vraies preuves. La **publication d'une RC générale** relève d'autres barrières fonctionnelles et de la CI globale.
- Comparaison des blobs des modules Connecthys essentiels : inchangés entre les SHA Windows installés, MySQL qualifiés et la branche `wx` au contrôle du 09/11/2026. Aucune copie de base de production utilisée.

## Périmètre et verdict

- Branche : `wx` ; correctif de géométrie : `0274601078203960c278e3a5956aa8e74d52c84c`.
- Première exécution graphique : [#42666116572](https://github.com/fr4nck/Noethys-SL/actions/runs/42666116572), **3 échecs de géométrie sur 4 tests** : écran Windows de 1044 × 800, contenu métier en débordement vertical.
- Correctif : zone centrale `wx.ScrolledWindow`, commandes Automatique/Manuel/Fermer fixes, taille minimale verticale abaissée, délégation des événements du calendrier au vrai dialogue ; aucun calcul de réservation, facturation ou adhésion modifié.
- Seconde exécution : [#42667482310](https://github.com/fr4nck/Noethys-SL/actions/runs/42667482310), **128 tests métier Connecthys PASS et 4 tests graphiques réels wx PASS**, zéro échec, Windows Python 3.10 + wxPython 4.2.5, réseau bloqué, sources non empaquetées.
- [Quatre captures PNG de la fenêtre avec données entièrement fictives](https://github.com/fr4nck/Noethys-SL/actions/runs/42667482310/artifacts/13697192624) : `01_situation_famille_fictive.png`, `02_autre_famille_fictive.png`, `03_lecture_indisponible.png`, `04_autre_categorie.png`. Captures consultées et recadrage/comportement contrôlés. L'artefact de CI est soumis à rétention.
- **Verdict actualisé : PASS sur source wx, démarrage du véritable exécutable installé et moteur MySQL 5.7 isolé. Les parcours interactifs métier complets dans le binaire installé, interruptions réseau réelles et transports réels restent NON TESTÉS. Aucune publication générale autorisée par ce seul lot.**

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
| Construction PyInstaller, installation Inno Setup puis ouverture de l'exe sur profil et base fictifs | Run #42673996161 : fin d'initialisation wx `oninit_fin` | PASS (démarrage) |
| Parcours complet de réservation / annulation depuis le binaire installé | Aucun clic métier effectué dans l'exe empaqueté | NON TESTÉ |
| MySQL 5.7.44 local de recette, deux connexions concurrentes, reprises et situation familiale | Run #42674823345 : 12 tests dédiés | PASS (moteur SQL) |
| Déconnexion physique réseau et scénario complet à plusieurs machines | Le runner n'a ni serveur PMSL ni postes distants | NON TESTÉ |
| Envoi vers un vrai serveur SMTP / Connecthys installé | Aucune émission réelle autorisée sur le runner | NON TESTÉ |

## Protocole restant sur application Windows installée

Utiliser uniquement un **candidat portant le correctif ci-dessus** ; une ancienne préversion installée ne contient pas ces modifications. Ne pas publier de release et ne pas relier la recette au serveur, au SMTP ou à la base familiale de production.

1. Employer un profil, des comptes et une base **fictifs / copie isolée et non connectée**, dans un sous-dossier de travail dédié, par exemple `C:\_Atelier_IA\Noethys-SL\Recette_Connecthys`. Ne jamais déplacer ni supprimer les sauvegardes d'origine.
2. Ouvrir trois demandes fictives successives : famille avec deux factures partiellement réglées et adhésion active ; autre famille avec avoir et cotisation expirée ; famille sans historique exploitable. Contrôler les soldes au jour / global et la ventilation des factures par recoupement indépendant.
3. Sur écran standard et sur petit écran, contrôler le rendu complet : trois cartes sans superposition, plus de solde rouge redondant, zone centrale défilante, commandes permanentes et aucune sortie involontaire du mode maximisé/plein écran.
4. Sur la copie isolée, interrompre l'enregistrement d'une demande entre calcul et validation SQL, puis la reprendre **en automatique et en manuel**, en contrôlant le nombre et les identifiants exacts de consommations avant/après ; aucune double réservation ou double réponse.
5. Contrôler les annulations de demandes du portail pour tous les enfants de la famille : historique complet conservé, nouvelle réservation après annulation, suppressions sans ajout initial, zéros/non-calculables distincts. Ne pas confondre état de la demande et présence physique.
6. Tester les emails exclusivement via transport fictif et réponses d'acceptation simulées : pas de double email accepté lors d'une reprise ; aucun email réel.
7. Le **moteur MySQL 5.7 local** et les verrous sur deux connexions sont déjà qualifiés. Il reste à tester les parcours complets de clics et les interruptions d'une session avec deux postes simulés, sur un serveur jetable et un exécutable installé, sans données familiales réelles.

**STOP-GATE de publication :** les tests ciblés de code, l'installation du candidat fictif et le MySQL isolé sont PASS. Le parcours métier complet **dans l'exécutable installé** et les autres barrières de la RC générale restent à qualifier, ainsi que tout scénario de transport réel (non autorisé sur ce banc). Aucun statut PASS implicite sur ces points.

## Traçabilité

Sources : `tests/test_connecthys_gui_recette_wx.py`, `tests/test_connecthys_situation.py`, `noethys/Dlg/DLG_Saisie_portail_demande.py`, `noethys/Utils/UTILS_Portail_situation.py`, `.github/workflows/noethys-sl-connecthys-qualification.yml`.

Aucun fichier métier, profil Windows du directeur ni base SQL de production ne sont modifiés par cette recette CI.
