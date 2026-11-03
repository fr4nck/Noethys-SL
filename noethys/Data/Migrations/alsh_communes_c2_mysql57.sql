-- ALSH C2 - PROPOSED for MySQL 5.7, never executed in production.
-- Requires TRIGGER privilege. Apply once after C1 migration on an isolated copy.
-- Existing addresses are observed from installation date, NOT before.
CREATE TABLE alsh_communes_c2_observations (
 IDobservation BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 IDindividu INTEGER NOT NULL,
 jour_constat DATE NOT NULL,
 instant_utc DATETIME NOT NULL,
 source VARCHAR(32) NOT NULL,
 adresse_auto INTEGER NULL,
 rue_resid TEXT NULL,
 cp_resid VARCHAR(20) NULL,
 ville_resid VARCHAR(255) NULL,
 INDEX alsh_c2_observations_enfant_dates (IDindividu,jour_constat,IDobservation)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE alsh_communes_c2_correspondances (
 code_postal VARCHAR(20) NOT NULL,
 ville_normalisee VARCHAR(150) NOT NULL,
 code_insee CHAR(5) NOT NULL,
 libelle_commune VARCHAR(255) NOT NULL,
 UNIQUE KEY uq_alsh_c2_correspondance (code_postal,ville_normalisee)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE alsh_communes_c2_profils (
 IDprofil INTEGER AUTO_INCREMENT PRIMARY KEY,
 nom VARCHAR(150) NOT NULL UNIQUE,
 config_json MEDIUMTEXT NOT NULL,
 maj_utc DATETIME NOT NULL,
 acteur VARCHAR(150) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE alsh_communes_c2_dates_validees (
 IDobservation BIGINT UNSIGNED PRIMARY KEY,
 date_effet DATE NOT NULL,
 justificatif VARCHAR(255) NOT NULL,
 acteur VARCHAR(150) NOT NULL,
 date_validation DATETIME NOT NULL,
 FOREIGN KEY (IDobservation) REFERENCES alsh_communes_c2_observations(IDobservation)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE alsh_communes_c2_audit (
 IDaudit BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 acteur VARCHAR(150) NOT NULL,
 action VARCHAR(80) NOT NULL,
 reference VARCHAR(200) NOT NULL,
 donnees_json MEDIUMTEXT NOT NULL,
 date_action DATETIME NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Single-statement triggers (no DELIMITER command necessary for supported clients).
CREATE TRIGGER alsh_c2_suivi_creation AFTER INSERT ON individus FOR EACH ROW
 INSERT INTO alsh_communes_c2_observations
 (IDindividu,jour_constat,instant_utc,source,adresse_auto,rue_resid,cp_resid,ville_resid)
 VALUES (NEW.IDindividu,UTC_DATE(),UTC_TIMESTAMP(),
         'creation',NEW.adresse_auto,NEW.rue_resid,NEW.cp_resid,NEW.ville_resid);

CREATE TRIGGER alsh_c2_suivi_modification AFTER UPDATE ON individus FOR EACH ROW
 INSERT INTO alsh_communes_c2_observations
 (IDindividu,jour_constat,instant_utc,source,adresse_auto,rue_resid,cp_resid,ville_resid)
 SELECT NEW.IDindividu,UTC_DATE(),UTC_TIMESTAMP(),
        'modification',NEW.adresse_auto,NEW.rue_resid,NEW.cp_resid,NEW.ville_resid
 FROM DUAL
 WHERE NOT (OLD.adresse_auto <=> NEW.adresse_auto)
    OR NOT (OLD.rue_resid <=> NEW.rue_resid)
    OR NOT (OLD.cp_resid <=> NEW.cp_resid)
    OR NOT (OLD.ville_resid <=> NEW.ville_resid);

INSERT INTO alsh_communes_c2_observations
 (IDindividu,jour_constat,instant_utc,source,adresse_auto,rue_resid,cp_resid,ville_resid)
 SELECT IDindividu,UTC_DATE(),UTC_TIMESTAMP(),
        'etat_initial',adresse_auto,rue_resid,cp_resid,ville_resid FROM individus;
