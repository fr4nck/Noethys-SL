-- Diagnostic des adhésions automatiques — LECTURE SEULE
-- =====================================================================
-- Aucune instruction de ce fichier ne modifie la base (SELECT uniquement).
-- Compatible MySQL (fichier réseau) et SQLite (fichier local).
--
-- AVANT EXÉCUTION
--   Remplacer chaque occurrence de PRENOM_A_DIAGNOSTIQUER par le prénom
--   recherché (ex. Arthur). Le « % » final élargit aux prénoms composés.
--
-- MYSQL (fichier réseau Noethys)
--   1. Utiliser de préférence un compte MySQL ne disposant que du droit SELECT,
--      ou une copie restaurée de la base (mysqldump puis import sur un serveur
--      de recette).
--   2. Base à sélectionner : <nom du fichier>_data (vérifier avec SHOW DATABASES;).
--   3. Ouvrir une transaction en lecture seule avant les requêtes :
--         USE <nom du fichier>_data;
--         START TRANSACTION READ ONLY;
--      puis exécuter les requêtes ci-dessous, et terminer par :
--         ROLLBACK;
--
-- SQLITE (fichier local <nom>_DATA.dat)
--   Travailler sur une COPIE du fichier, ouverte en lecture seule :
--         sqlite3 -readonly copie_DATA.dat < diagnostic_adhesions.sql
--
-- LECTURE DES RÉSULTATS (requêtes 2 et 4)
--   - deux IDcotisation distincts            → deux créations réelles ;
--   - un seul IDcotisation listé deux fois    → doublon d'affichage ;
--   - observations « [adhesion-auto] … »      → création automatique, avec la
--     participation déclenchante (consommation ou prestation, et son ID) ;
--   - deux créations à la même heure (req. 4) → une seule sauvegarde de la grille ;
--     à des heures différentes               → sauvegardes successives ;
--   - date_debut postérieure à date_saisie    → adhésion anticipée (réservation
--     future).
-- =====================================================================

-- 1. Individu(s) concerné(s) — plusieurs lignes : fiches en double possibles
SELECT IDindividu, nom, prenom, date_naiss
FROM individus
WHERE prenom LIKE 'PRENOM_A_DIAGNOSTIQUER%'
ORDER BY nom, prenom;

-- 2. Cotisations et prestations associées
SELECT c.IDcotisation, c.IDindividu, c.IDfamille, c.IDtype_cotisation, c.IDunite_cotisation,
       c.date_saisie, c.date_debut, c.date_fin, c.IDprestation, c.observations,
       p.date AS date_prestation, p.label, p.montant, p.IDcompte_payeur, p.IDfacture
FROM cotisations c
LEFT JOIN prestations p ON p.IDprestation = c.IDprestation
WHERE c.IDindividu IN (SELECT IDindividu FROM individus WHERE prenom LIKE 'PRENOM_A_DIAGNOSTIQUER%')
ORDER BY c.IDindividu, c.date_debut, c.IDcotisation;

-- 3. Prestations « cotisation » sans cotisation rattachée (orphelines)
SELECT p.IDprestation, p.date, p.label, p.montant, p.IDindividu, p.IDcompte_payeur, p.IDfacture
FROM prestations p
WHERE p.categorie = 'cotisation'
  AND p.IDindividu IN (SELECT IDindividu FROM individus WHERE prenom LIKE 'PRENOM_A_DIAGNOSTIQUER%')
  AND NOT EXISTS (SELECT 1 FROM cotisations c WHERE c.IDprestation = p.IDprestation)
ORDER BY p.date, p.IDprestation;

-- 4. Historique des saisies de cotisations (catégorie 21) : heure et utilisateur
SELECT h.date, h.heure, h.IDutilisateur, h.IDindividu, h.action
FROM historique h
WHERE h.IDcategorie = 21
  AND h.IDindividu IN (SELECT IDindividu FROM individus WHERE prenom LIKE 'PRENOM_A_DIAGNOSTIQUER%')
ORDER BY h.date, h.heure;

-- 5. Réservations et présences : dates pouvant avoir déclenché une création
SELECT co.IDconso, co.IDindividu, co.date, co.etat, co.IDactivite, co.date_saisie, co.IDutilisateur
FROM consommations co
WHERE co.etat IN ('reservation', 'present')
  AND co.IDindividu IN (SELECT IDindividu FROM individus WHERE prenom LIKE 'PRENOM_A_DIAGNOSTIQUER%')
ORDER BY co.IDindividu, co.date;

-- 6. Ampleur globale : adhésions qui se chevauchent, dont au moins une automatique
SELECT a.IDindividu, a.IDcotisation, a.date_debut, a.date_fin,
       b.IDcotisation AS IDcotisation_chevauchee, b.date_debut AS debut_chevauchee, b.date_fin AS fin_chevauchee
FROM cotisations a
JOIN cotisations b
  ON a.IDindividu = b.IDindividu AND a.IDtype_cotisation = b.IDtype_cotisation
 AND a.IDcotisation < b.IDcotisation
 AND a.date_debut <= b.date_fin AND b.date_debut <= a.date_fin
WHERE a.observations LIKE '%[adhesion-auto]%' OR b.observations LIKE '%[adhesion-auto]%'
ORDER BY a.IDindividu, a.date_debut;

-- 7. Adhésions automatiques commençant après leur date de saisie (anticipées)
SELECT IDcotisation, IDindividu, date_saisie, date_debut, date_fin
FROM cotisations
WHERE observations LIKE '%[adhesion-auto]%' AND date_debut > date_saisie
ORDER BY date_saisie, IDindividu;

-- 8. Contrôle TRV-032 : paramètre e-mail « timeout » vide, susceptible d'avoir été
--    inséré par la suite de tests lancée le 08/10/2026 depuis le poste 5700x
--    (ligne identique à celle que Noethys crée lui-même au premier envoi d'e-mail).
SELECT IDparametre, categorie, nom, parametre
FROM parametres
WHERE categorie = 'email' AND nom = 'timeout';
