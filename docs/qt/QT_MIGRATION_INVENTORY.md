# Inventaire de migration Qt — Noethys

> Branche de référence : `poc/qt-theme-isole`  
> État audité : 5 septembre 2026  
> Source de vérité : entrées utilisateur déclarées dans `Noethys.MainFrame.CreationBarreMenus()`, panneaux créés par `CreationPanneaux()`, et modules réellement présents dans `noethys_qt/`.

## Légende

- ✅ **Qt complet** : surface réellement utilisable en Qt, raccordée aux données Noethys et couverte par tests.
- 🟠 **Qt partiel** : surface migrée mais au moins un sous-panneau ou comportement historique reste à porter.
- ⬜ **wx uniquement** : aucune surface Qt fonctionnelle équivalente n'existe encore.
- ➖ **hors priorité UI** : commande d'aide/système ou action qui n'est pas un écran métier à migrer en premier.

L'inventaire vise les **surfaces utilisateur et panneaux métier**, pas chaque boîte de dialogue technique interne appelée en cascade. Pour la fiche Activité, la décomposition descend volontairement au niveau des sous-panneaux afin de repérer les derniers trous fonctionnels.

---

# 1. Coque principale et panneaux d'accueil

| Surface historique | Statut Qt | Priorité | Observation |
|---|---:|---:|---|
| Fenêtre principale Noethys / menus / barres d'outils / navigation | ⬜ | P0 | Le lancement Qt ouvre encore directement le module Activités. |
| Panneau **Recherche individus** | ⬜ | P0 | Surface quotidienne majeure. |
| Panneau **Tableau de bord / Effectifs** | ⬜ | P1 | À reconstruire selon `DASHBOARD_MODERNISATION.md`. |
| Panneau **Messages** | ⬜ | P2 | Module optionnel dans la cible moderne. |
| Panneau **Éphéméride** | ⬜ | P3 | Faible criticité métier. |
| Panneau **Accueil** | ⬜ | P1 | La cible moderne prévoit un dashboard opérationnel et modulaire. |
| Panneau serveur Nomadhys (optionnel) | ⬜ | P3 | À réévaluer selon stratégie Nomadhys. |
| Barre raccourcis : gestionnaire conso / liste conso / badgeage / facture | ⬜ | P1 | Les cibles métier correspondantes sont encore wx. |
| Barre utilisateur / identification | ⬜ | P1 | Nécessaire avant un vrai shell Qt de production. |

---

# 2. Menu Fichier

Toutes les interfaces ci-dessous restent wx. Les moteurs de sauvegarde/restauration ont des travaux de durcissement séparés, mais leur **UI n'est pas migrée en Qt**.

| Surface | Statut | Priorité |
|---|---:|---:|
| Créer un nouveau fichier | ⬜ | P2 |
| Ouvrir un fichier | ⬜ | P1 |
| Fermer le fichier | ⬜ | P1 |
| Informations sur le fichier | ⬜ | P2 |
| Créer une sauvegarde | ⬜ | P1 |
| Restaurer une sauvegarde | ⬜ | P1 |
| Sauvegardes automatiques | ⬜ | P2 |
| Convertir en fichier réseau | ⬜ | P3 |
| Convertir en fichier local | ⬜ | P3 |
| Export vers Noethysweb | ⬜ | P3 |

---

# 3. Paramétrage

## 3.1 Paramétrage général

| Surface | Statut | Priorité |
|---|---:|---:|
| Préférences | ⬜ | P1 |
| Enregistrement | ⬜ | P3 |
| Utilisateurs | ⬜ | P1 |
| Modèles de droits | ⬜ | P2 |
| Accès réseau | ⬜ | P2 |
| Organisateur | ⬜ | P1 |
| Cotisations — types | ⬜ | P2 |
| Groupes d'activités | ⬜ | P2 |
| **Activités — liste + fiche** | 🟠 | **P0** |
| Procédures de badgeage | ⬜ | P3 |
| Synthèse vocale | ⬜ | P3 |
| Questionnaires | ⬜ | P1 |
| Images interactives | ⬜ | P3 |

## 3.2 Modèles

Tous wx uniquement :

- Modèles de documents
- Modèles d'Emails
- Modèles de tickets
- Modèles de contrats
- Modèles de plannings
- Modèles d'aides journalières
- Modèles de prestations
- Modèles de commandes de repas

Priorité globale : **P2**, sauf modèles d'Emails/documents nécessaires à une surface P1.

## 3.3 Facturation — paramétrage

Tous ⬜ wx uniquement : Régies, Préfixes de factures, Lots de factures, Lots de rappels. Priorité **P2**.

## 3.4 Comptabilité — paramétrage

Tous ⬜ wx uniquement : Comptes bancaires, Modes de règlements, Émetteurs, Exercices comptables, Postes analytiques, Catégories comptables, Comptes comptables, Tiers, Budgets, Relevés bancaires. Priorité **P2**, avec comptes/modes de règlement à remonter en **P1** quand le module Règlements passe en Qt.

## 3.5 Prélèvement automatique

Établissements bancaires, Perceptions : ⬜ wx uniquement, **P2**.

## 3.6 Locations — paramétrage

Catégories de produits, Produits : ⬜ wx uniquement, **P2**.

## 3.7 Renseignements généraux

Tous ⬜ wx uniquement : Types de pièces, Régimes sociaux, Caisses, Types de quotients, Catégories socio-professionnelles, Villes/codes postaux, Secteurs géographiques, Types de sieste, Catégories médicales, Maladies, Vaccins, Médecins. Priorité **P2** ; Types de pièces/Caisses/Types de quotients passent à **P1** car les écrans Activités et Familles les consomment.

## 3.8 Scolarité

Niveaux scolaires, Écoles, Classes : ⬜ wx uniquement, **P2**.

## 3.9 Transports

Tous ⬜ wx uniquement, **P3** :

- Bus : compagnies, lignes, arrêts
- Cars : compagnies, lignes, arrêts
- Navettes : compagnies, lignes, arrêts
- Taxi : compagnies
- Train : gares, compagnies
- Avion : aéroports, compagnies
- Bateau : ports, compagnies
- Métro : compagnies, lignes, arrêts
- Pédibus : lignes, arrêts

## 3.10 Restauration

Restaurateurs, Catégories de menus, Légendes de menus : ⬜ wx uniquement, **P1/P2** selon migration des commandes de repas.

## 3.11 Autres paramétrages

Périodes de gestion, Catégories de messages, Adresses d'expédition d'Emails, Listes de diffusion, Vacances, Jours fériés : ⬜ wx uniquement. **Vacances / jours fériés = P1** car plusieurs moteurs métier en dépendent.

---

# 4. Fiche Activité — audit détaillé

La fiche Qt expose bien les neuf onglets historiques dans le même ordre. Les états ci-dessous distinguent le **nom de l'onglet** de la complétude de ses sous-outils.

| Onglet / sous-panneau | Statut | Reste à faire |
|---|---:|---|
| Liste des activités | ✅ | CRUD, duplication, suppression protégée, simulation et assistants raccordés. |
| Généralités — identité / période / coordonnées | ✅ | — |
| Généralités — groupes d'activités | ✅ | — |
| Généralités — capacité / codes comptables / régie / inscriptions multiples | ✅ | — |
| Généralités — responsables | ✅ | — |
| Généralités — logo personnalisé | ✅ | — |
| Agréments | ✅ | Modes aucun / unique / multiples et sentinelles historiques. |
| Groupes | ✅ | CRUD, ordre et protections d'usage. |
| Renseignements — pièces | ✅ | — |
| Renseignements — cotisations obligatoires | ✅ | — |
| Renseignements — vaccins obligatoires | ✅ | — |
| Renseignements — informations obligatoires | ✅ | — |
| Étiquettes | ✅ | Hiérarchie, ordre, suppressions protégées. |
| Unités — unités de consommation | ✅ | — |
| Unités — groupes / incompatibilités / repas / horaires / raccourcis | ✅ | — |
| Unités — unités de remplissage | ✅ | — |
| **Unités — éditeur avancé d'auto-génération** | 🟠 | Les paramètres historiques sont préservés mais ne disposent pas encore de leur éditeur Qt complet. |
| Calendrier — ouvertures | ✅ | — |
| Calendrier — capacités de remplissage | ✅ | — |
| Calendrier — événements simples | ✅ | Nom, horaires, capacité, montant simple. |
| **Calendrier — tarification avancée attachée aux événements** | 🟠 | Les tarifs avancés historiques sont détectés et préservés, mais non modifiables depuis la fenêtre événement Qt. |
| Portail — paramètres inscriptions/réservations | ✅ | — |
| Portail — périodes | ✅ | — |
| Portail — unités de réservation | ✅ | — |
| Portail — limites et absence injustifiée | ✅ | — |
| Tarification — catégories / villes | ✅ | — |
| Tarification — noms de prestations / tarifs | ✅ | — |
| Tarification — JOURN / FORFAIT / CREDIT / BAREME | ✅ | Compatibilité historique couverte par tests de round-trip. |
| Tarification — méthodes de calcul | ✅ | — |
| Tarification — combinaisons | ✅ | — |
| Tarification — `montant_questionnaire` | ✅ | Référence de question, pas montant libre. |
| **Tarification — filtre d'application Étiquettes** | 🟠 | Valeur historique préservée mais pas d'éditeur dédié dans le dialogue Tarif. |
| **Tarification — filtres Questionnaire d'application** | 🟠 | Duplication/préservation sécurisées, mais édition directe depuis le tarif encore absente. |
| Assistants — annuelle / séjour / stage / cantine / sorties | 🟠 | Structure métier générée. Les variantes tarifaires avancées de l'assistant historique restent volontairement ramenées à « à finaliser / gratuit / montant fixe ». |
| Mode Simulation Ajouter/Dupliquer/Supprimer | ✅ | Zéro écriture. |

## 4.1 Les quatre sous-chantiers qui empêchent encore de déclarer « Fiche Activité 100 % Qt »

1. **Auto-génération avancée des unités** : porter l'éditeur des conditions/paramètres historiques, sans écraser les valeurs existantes.
2. **Tarifs avancés d'événements** : permettre depuis Calendrier d'ouvrir/éditer les tarifs rattachés à `IDevenement`, en réutilisant le moteur Tarification Qt déjà migré.
3. **Filtres Tarification Étiquettes + Questionnaire** : rendre éditables les filtres d'application déjà conservés en base.
4. **Assistants de création — tarification avancée** : réintroduire les choix historiques utiles (QF et méthodes associées) uniquement après preuve d'usage ; ne pas dupliquer tout le moteur de tarification dans l'assistant.

---

# 5. Individus / Familles

**Tout ce domaine est encore wx uniquement.** C'est le prochain rail prioritaire pour que l'application Qt cesse d'être « juste la page Activités ».

| Surface | Statut | Priorité |
|---|---:|---:|
| Recherche individus/familles (panneau principal) | ⬜ | **P0** |
| Fiche famille | ⬜ | **P0** |
| Fiche individu | ⬜ | **P0** |
| Inscriptions scolaires | ⬜ | P2 |
| Liste détaillée des inscriptions | ⬜ | **P1** |
| Liste des inscriptions à une activité | ⬜ | **P1** |
| Saisie d'un lot d'inscriptions | ⬜ | P1 |
| Désinscription par lot | ⬜ | P1 |
| Inscriptions en attente | ⬜ | P1 |
| Inscriptions refusées | ⬜ | P1 |
| Transmission / impression des inscriptions | ⬜ | P2 |
| Liste des contrats | ⬜ | P1 |
| Liste des individus | ⬜ | P1 |
| Liste des familles | ⬜ | P1 |
| Transports récap/détail/programmations | ⬜ | P3 |
| Anniversaires | ⬜ | P3 |
| Informations médicales | ⬜ | P2 |
| Pièces fournies / manquantes | ⬜ | P2 |
| Régimes et caisses | ⬜ | P2 |
| Quotients familiaux / revenus | ⬜ | **P1** |
| Mandats SEPA | ⬜ | P2 |
| Codes comptables | ⬜ | P2 |
| Comptes internet | ⬜ | P2 |
| Import photos | ⬜ | P3 |
| Import Excel/CSV familles-individus | ⬜ | P3 |
| Import familles depuis fichier Noethys | ⬜ | P3 |
| Export XML familles | ⬜ | P3 |
| Archivage / suppression individus | ⬜ | P2 |
| Étiquettes / badges PDF | ⬜ | P3 |

---

# 6. Cotisations

Tout ⬜ wx uniquement : Liste des cotisations, cotisations manquantes, saisie par lot, transmission Email, impression, dépôts de cotisations. Priorité **P2**, sauf liste/saisie qui passent **P1** si l'usage PMSL le justifie.

---

# 7. Locations

Tout ⬜ wx uniquement : Liste des produits, Liste des locations, Email/impression, demandes, Email/impression des demandes, planning, chronologie, tableau, synthèse, images interactives. Priorité **P3** par défaut.

---

# 8. Consommations

Domaine critique, tout ⬜ wx uniquement actuellement.

| Surface | Statut | Priorité |
|---|---:|---:|
| Gestionnaire des consommations | ⬜ | **P0** |
| Liste des consommations | ⬜ | **P1** |
| Traitement par lot | ⬜ | P1 |
| Liste détaillée | ⬜ | P1 |
| Liste d'attente | ⬜ | P1 |
| Places refusées | ⬜ | P1 |
| Absences | ⬜ | P1 |
| Synthèse consommations | ⬜ | P2 |
| État global | ⬜ | P2 |
| État nominatif | ⬜ | P2 |
| Badgeage | ⬜ | P2 |

---

# 9. Facturation

Tout ⬜ wx uniquement.

Priorité P1 : génération de factures, liste des factures, liste des prestations, soldes familles, recalcul/verrouillage des prestations.  
Priorité P2 : Hélios, prélèvement, Email/impression factures, rappels, attestations, liste des tarifs, contrats PSU, déductions, forfaits-crédits, synthèses, export comptable.

Surfaces recensées :

- Vérification ventilation
- Factures : génération, Hélios, prélèvement, Email, impression, liste, liste détaillée
- Lettres de rappel : génération, Email, impression, liste
- Attestations de présence : génération, liste
- Attestations fiscales : génération
- Liste des tarifs
- Validation des contrats PSU
- Liste / recalcul / verrouillage des prestations
- Synthèse / liste / saisie par lot des déductions
- Saisie par lot des forfaits-crédits
- Soldes familles / soldes individuels
- Synthèse / solde des impayés
- Synthèse prestations / prestations par famille
- Export écritures comptables

---

# 10. Règlements

Tout ⬜ wx uniquement.

| Surface | Priorité |
|---|---:|
| Régler une facture | **P1** |
| Liste des reçus | P2 |
| Liste des règlements | **P1** |
| Liste détaillée | P2 |
| Vérification ventilation | P2 |
| Détail prestations d'un dépôt | P2 |
| Analyse ventilation/dépôts | P2 |
| Synthèse modes de règlements | P2 |
| Prélèvement automatique | P2 |
| Gestion des dépôts | **P1** |

---

# 11. Comptabilité

Tout ⬜ wx uniquement : comptes, opérations de trésorerie, opérations budgétaires, virements, rapprochement bancaire, suivi trésorerie, suivi budgets, graphiques. Priorité **P2** après stabilisation Facturation/Règlements.

---

# 12. Outils, statistiques et restauration

Tout ⬜ wx uniquement à ce stade :

- Statistiques
- Commandes des repas
- Menus des repas
- Nomadhys
- Connecthys : synchronisation / traitement des demandes
- PMSL Équipe — synchronisation Noethys
- Carnet d'adresses
- Éditeur d'Emails
- Envoi SMS
- Calculatrice
- Calendrier général
- Villes/codes postaux
- Géolocalisation GPS
- Horaires du soleil
- Connexions réseau
- Messages
- Historique
- Extensions
- Traductions
- Updater
- Utilitaires administrateur : correcteur, purges, répertoires, procédures, réinitialisation, transfert de tables, réparations prestations/consommations/forfaits, TVA/codes comptables, conversion RIB/SEPA, titulaires Hélios, tiers solidaires, consoles Python/SQL, liste SQL personnalisée.

**P1** pour Commandes des repas, PMSL Équipe synchronisation, statistiques utiles ; le reste est P2/P3.

---

# 13. Affichage / aide

Les perspectives, panneaux, barres d'outils personnelles et actualisation sont encore wx. Leur équivalent devra être repensé dans la coque Qt plutôt que copié littéralement.

Les écrans Aide / forum / tutoriels / ressources / mise à jour sont hors du chemin critique de migration métier.

---

# 14. Ordre de migration recommandé après cet audit

L'objectif n'est plus de poursuivre longtemps dans un seul dialogue Activité. Pour rendre **Noethys Qt testable comme application**, l'ordre proposé est :

1. **P0-A — Terminer les quatre trous de la fiche Activité** : auto-génération unités, tarifs avancés événements, filtres Étiquettes/Questionnaire, assistants tarifaires avancés utiles.
2. **P0-B — Créer la coque principale Qt** : navigation stable, thème, état de connexion, utilisateur, et lancement des modules migrés.
3. **P0-C — Recherche Individus/Familles** : deuxième vraie surface métier, lecture/recherche d'abord puis ouverture des fiches.
4. **P0-D — Fiches Famille + Individu** : préserver tous les onglets historiques réellement utilisés.
5. **P0-E — Gestionnaire des consommations** : tableau dense central de l'exploitation quotidienne.
6. **P1 — Inscriptions / contrats / quotients / prestations**.
7. **P1 — Règlements et facturation**.
8. **P1/P2 — Commandes de repas, statistiques et dashboard d'accueil**.
9. **P2 — Comptabilité et paramétrages secondaires**.
10. **P3 — Locations, transports, utilitaires secondaires et outils périphériques**.

## Critère pour dire « Noethys Qt est essayable comme logiciel »

Ne plus exiger que l'utilisateur lance un module isolé. Le minimum est : **coque Qt + recherche familles/individus + Activités + accès au gestionnaire des consommations**, même si certaines fonctions secondaires restent temporairement wx.

## Critère pour dire « une surface est migrée »

Une surface n'est pas marquée ✅ parce qu'elle s'affiche. Elle doit :

- lire les données historiques réelles ;
- préserver ou écrire sans modifier le schéma ;
- couvrir les garde-fous métier historiques ;
- rester dense et utilisable clavier/souris ;
- respecter clair/sombre ;
- avoir des tests de round-trip ou de non-régression sur les écritures sensibles ;
- ne pas perdre silencieusement les champs anciens qu'elle ne sait pas encore éditer.
