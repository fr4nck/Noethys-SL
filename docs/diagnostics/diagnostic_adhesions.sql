-- Diagnostic des adhésions automatiques — LECTURE SEULE
-- =====================================================================
-- Aucune instruction de ce fichier ne modifie la base (SELECT uniquement).
-- Compatible MySQL (fichier réseau) et SQLite (fichier local).
-- Les valeurs à saisir sont des paramètres : aucune donnée réelle ici.
--
-- PARAMÈTRES À REMPLACER
--   IDFAMILLE_A_DIAGNOSTIQUER : numéro de la fiche famille (IDfamille)
--   PRENOM_A_DIAGNOSTIQUER    : prénom, utilisé UNIQUEMENT à l'étape 1 et
--                               toujours combiné au rattachement à la famille
--   IDINDIVIDU_A_DIAGNOSTIQUER: identifiant retenu à l'issue de l'étape 1
--
-- EXÉCUTION EN LECTURE SEULE
--   MySQL (fichier réseau) :
--     1. de préférence sur une copie restaurée de la base, ou avec un
--        compte MySQL limité au droit SELECT ;
--     2. base : <nom du fichier>_data (vérifier avec SHOW DATABASES;) ;
--     3. USE <nom du fichier>_data;
--        START TRANSACTION READ ONLY;
--        ... requêtes ci-dessous ...
--        ROLLBACK;
--   SQLite (fichier local) : sur une COPIE du fichier <nom>_DATA.dat :
--        sqlite3 -readonly copie_DATA.dat
--
-- Procédure : exécuter l'étape 1, noter l'IDindividu (un seul attendu),
-- remplacer IDINDIVIDU_A_DIAGNOSTIQUER, puis exécuter les étapes 2 à 8.
-- =====================================================================

-- 1. Identifier l'individu par son RATTACHEMENT à la famille (pas par le
--    seul prénom) : plusieurs lignes = homonymes dans la même famille ou
--    fiches en double, à départager avant de continuer.
SELECT r.IDfamille, r.IDindividu, r.IDcategorie, r.titulaire, i.nom, i.prenom, i.date_naiss
FROM rattachements r
JOIN individus i ON i.IDindividu = r.IDindividu
WHERE r.IDfamille = IDFAMILLE_A_DIAGNOSTIQUER
  AND i.prenom LIKE 'PRENOM_A_DIAGNOSTIQUER%'
ORDER BY r.IDindividu;

-- 2. Adhésions (cotisations) de l'individu et prestations associées.
--    Deux IDcotisation distincts = deux créations, un seul IDcotisation
--    vu deux fois à l'écran = doublon d'affichage.
SELECT c.IDcotisation, c.IDindividu, c.IDfamille, c.IDtype_cotisation, c.IDunite_cotisation,
       c.date_saisie, c.date_debut, c.date_fin, c.IDprestation, c.IDutilisateur, c.observations,
       p.IDprestation AS prestation, p.date AS date_prestation, p.label, p.montant,
       p.IDcompte_payeur, p.IDfamille AS famille_prestation, p.IDfacture
FROM cotisations c
LEFT JOIN prestations p ON p.IDprestation = c.IDprestation
WHERE c.IDindividu = IDINDIVIDU_A_DIAGNOSTIQUER
ORDER BY c.date_debut, c.IDcotisation;

-- 3. Prestations « cotisation » de l'individu, rattachées ou non à une
--    cotisation (une orpheline signalerait une écriture partielle).
SELECT p.IDprestation, p.date, p.label, p.montant, p.IDcompte_payeur, p.IDfamille, p.IDfacture,
       (SELECT COUNT(*) FROM cotisations c WHERE c.IDprestation = p.IDprestation) AS nb_cotisations
FROM prestations p
WHERE p.categorie = 'cotisation' AND p.IDindividu = IDINDIVIDU_A_DIAGNOSTIQUER
ORDER BY p.date, p.IDprestation;

-- 4. Ventilations éventuelles de ces prestations (montants déjà réglés).
SELECT v.IDventilation, v.IDreglement, v.IDprestation, v.montant
FROM ventilation v
WHERE v.IDprestation IN (SELECT p.IDprestation FROM prestations p
                         WHERE p.categorie = 'cotisation' AND p.IDindividu = IDINDIVIDU_A_DIAGNOSTIQUER);

-- 5. Historique des saisies de cotisations (catégorie 21) : même heure =
--    une seule sauvegarde, heures ou utilisateurs différents = sauvegardes
--    successives ou postes différents.
SELECT h.IDaction, h.date, h.heure, h.IDutilisateur, h.IDfamille, h.action
FROM historique h
WHERE h.IDcategorie = 21 AND h.IDindividu = IDINDIVIDU_A_DIAGNOSTIQUER
ORDER BY h.date, h.heure, h.IDaction;

-- 6. Réservations et présences : participations déclenchantes possibles
--    (l'observation « [adhesion-auto] » de l'étape 2 cite la source et l'ID).
SELECT co.IDconso, co.date, co.etat, co.IDactivite, co.IDcompte_payeur, co.date_saisie, co.IDutilisateur
FROM consommations co
WHERE co.IDindividu = IDINDIVIDU_A_DIAGNOSTIQUER AND co.etat IN ('reservation', 'present')
ORDER BY co.date;

-- 7. Ampleur globale (toute la base) : adhésions qui se chevauchent dont au
--    moins une automatique.
SELECT a.IDindividu, a.IDcotisation, a.date_debut, a.date_fin,
       b.IDcotisation AS IDcotisation_chevauchee, b.date_debut AS debut_chevauchee, b.date_fin AS fin_chevauchee
FROM cotisations a
JOIN cotisations b
  ON a.IDindividu = b.IDindividu AND a.IDtype_cotisation = b.IDtype_cotisation
 AND a.IDcotisation < b.IDcotisation
 AND a.date_debut <= b.date_fin AND b.date_debut <= a.date_fin
WHERE a.observations LIKE '%[adhesion-auto]%' OR b.observations LIKE '%[adhesion-auto]%'
ORDER BY a.IDindividu, a.date_debut;

-- 8. Adhésions automatiques anticipées (début postérieur à la saisie).
SELECT IDcotisation, IDindividu, date_saisie, date_debut, date_fin
FROM cotisations
WHERE observations LIKE '%[adhesion-auto]%' AND date_debut > date_saisie
ORDER BY date_saisie, IDindividu;

-- 9. Incident TRV-032 du 08/10/2026 : paramètre e-mail « timeout ».
--    La table parametres n'enregistre ni date ni poste : la PRÉSENCE de cette
--    ligne ne permet pas de l'attribuer aux tests, Noethys crée la même
--    ligne (valeur vide) au premier envoi d'e-mail depuis n'importe quel
--    poste. Voir docs/incidents/2026-10-08-tests-base-reseau.md.
SELECT IDparametre, categorie, nom, parametre
FROM parametres
WHERE categorie = 'email' AND nom = 'timeout';

-- 9 bis. Position de cette ligne parmi les derniers paramètres créés (indice
--        d'ordre de création seulement, pas une preuve).
SELECT IDparametre, categorie, nom
FROM parametres
ORDER BY IDparametre DESC
LIMIT 15;
