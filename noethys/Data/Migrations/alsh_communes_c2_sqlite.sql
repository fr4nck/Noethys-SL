-- ALSH C2 - PROP0SAL ONLY. Run once on a throwaway SQLite copy after C1.
-- Never execute on MAD or production without backup and approval.
-- Baseline captures the address OBSERVED AT INSTALLATION, not a historical move date.
-- Capture is done by database triggers, including external imports and direct SQL.
-- Children who inherit adresse_auto are resolved at query time, without duplication.
CREATE TABLE alsh_communes_c2_observations (
 IDobservation INTEGER PRIMARY KEY AUTOINCREMENT,
 IDindividu INTEGER NOT NULL REFERENCES individus(IDindividu),
 jour_constat TEXT NOT NULL,
 instant_utc TEXT NOT NULL,
 source TEXT NOT NULL,
 adresse_auto INTEGER,
 rue_resid TEXT,
 cp_resid TEXT,
 ville_resid TEXT
);
CREATE INDEX alsh_c2_observations_enfant_dates
 ON alsh_communes_c2_observations(IDindividu,jour_constat,IDobservation);
CREATE TABLE alsh_communes_c2_correspondances (
 code_postal TEXT NOT NULL,
 ville_normalisee TEXT NOT NULL,
 code_insee TEXT NOT NULL,
 libelle_commune TEXT NOT NULL,
 UNIQUE(code_postal, ville_normalisee)
);
CREATE TABLE alsh_communes_c2_profils (
 IDprofil INTEGER PRIMARY KEY AUTOINCREMENT,
 nom TEXT NOT NULL UNIQUE,
 config_json TEXT NOT NULL,
 maj_utc TEXT NOT NULL,
 acteur TEXT NOT NULL
);
CREATE TABLE alsh_communes_c2_dates_validees (
 IDobservation INTEGER PRIMARY KEY REFERENCES alsh_communes_c2_observations(IDobservation),
 date_effet TEXT NOT NULL,
 justificatif TEXT NOT NULL,
 acteur TEXT NOT NULL,
 date_validation TEXT NOT NULL
);
CREATE TABLE alsh_communes_c2_audit (
 IDaudit INTEGER PRIMARY KEY AUTOINCREMENT,
 acteur TEXT NOT NULL,
 action TEXT NOT NULL,
 reference TEXT NOT NULL,
 donnees_json TEXT NOT NULL,
 date_action TEXT NOT NULL
);

CREATE TRIGGER alsh_c2_suivi_creation AFTER INSERT ON individus
BEGIN
 INSERT INTO alsh_communes_c2_observations
 (IDindividu,jour_constat,instant_utc,source,adresse_auto,rue_resid,cp_resid,ville_resid)
 VALUES (NEW.IDindividu, date('now'), strftime('%Y-%m-%dT%H:%M:%fZ','now'),
         'creation', NEW.adresse_auto,NEW.rue_resid,NEW.cp_resid,NEW.ville_resid);
END;

CREATE TRIGGER alsh_c2_suivi_modification
 AFTER UPDATE OF adresse_auto,rue_resid,cp_resid,ville_resid ON individus
 WHEN OLD.adresse_auto IS NOT NEW.adresse_auto
   OR OLD.rue_resid IS NOT NEW.rue_resid
   OR OLD.cp_resid IS NOT NEW.cp_resid
   OR OLD.ville_resid IS NOT NEW.ville_resid
BEGIN
 INSERT INTO alsh_communes_c2_observations
 (IDindividu,jour_constat,instant_utc,source,adresse_auto,rue_resid,cp_resid,ville_resid)
 VALUES (NEW.IDindividu, date('now'), strftime('%Y-%m-%dT%H:%M:%fZ','now'),
         'modification',NEW.adresse_auto,NEW.rue_resid,NEW.cp_resid,NEW.ville_resid);
END;

-- Installation baseline: no invented earlier residence date.
INSERT INTO alsh_communes_c2_observations
 (IDindividu,jour_constat,instant_utc,source,adresse_auto,rue_resid,cp_resid,ville_resid)
 SELECT IDindividu,date('now'),strftime('%Y-%m-%dT%H:%M:%fZ','now'),
        'etat_initial',adresse_auto,rue_resid,cp_resid,ville_resid
 FROM individus;
