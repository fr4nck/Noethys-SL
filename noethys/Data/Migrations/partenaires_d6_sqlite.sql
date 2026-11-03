-- LOT D6 -- SCHEMA SQLITE POUR RECETTE ISOLEE UNIQUEMENT.
-- DEPENDANCES : D1, D2, D34, D5 ; PRAGMA foreign_keys=ON sur chaque connexion.
-- AUCUN ALTER OU INSERT VERS familles, comptes_payeurs, factures, prestations.
-- Pas de colonnes de TVA : modele non assujetti declare par l'association.
SELECT IDbordereau FROM partenaires_bordereaux LIMIT 0;
CREATE TABLE partenaires_factures_sequence (
  singleton INTEGER PRIMARY KEY CHECK (singleton=1),
  exercice INTEGER NOT NULL CHECK (exercice BETWEEN 0 AND 9999),
  dernier_numero INTEGER NOT NULL CHECK (dernier_numero>=0),
  derniere_date TEXT
);
INSERT INTO partenaires_factures_sequence (singleton,exercice,dernier_numero,derniere_date)
VALUES (1,0,0,NULL);

CREATE TABLE partenaires_factures_officielles (
  IDfacture_partenaire INTEGER PRIMARY KEY AUTOINCREMENT,
  IDbordereau INTEGER NOT NULL UNIQUE REFERENCES partenaires_bordereaux(IDbordereau) ON DELETE RESTRICT,
  IDpartenaire INTEGER NOT NULL REFERENCES partenaires_structures(IDpartenaire) ON DELETE RESTRICT,
  numero TEXT NOT NULL COLLATE NOCASE UNIQUE,
  exercice INTEGER NOT NULL,
  ordre INTEGER NOT NULL CHECK (ordre>0),
  date_emission TEXT NOT NULL,
  date_echeance TEXT NOT NULL CHECK(date_echeance>=date_emission),
  date_prestation TEXT NOT NULL,
  periode_debut TEXT NOT NULL,
  periode_fin TEXT NOT NULL,
  total TEXT NOT NULL,
  empreinte_bordereau TEXT NOT NULL,
  donnees_json TEXT NOT NULL,
  empreinte_document TEXT NOT NULL,
  etat TEXT NOT NULL CHECK(etat='enregistree'),
  cree_le TEXT NOT NULL,
  cree_par TEXT NOT NULL,
  UNIQUE(exercice,ordre)
);
CREATE INDEX idx_part_factures_partenaire ON partenaires_factures_officielles(IDpartenaire,date_emission);
CREATE TABLE partenaires_factures_evenements (
  IDevenement INTEGER PRIMARY KEY AUTOINCREMENT,
  IDfacture_partenaire INTEGER NOT NULL REFERENCES partenaires_factures_officielles(IDfacture_partenaire) ON DELETE RESTRICT,
  action TEXT NOT NULL CHECK(action='enregistrement'),
  date_action TEXT NOT NULL,
  acteur TEXT NOT NULL
);
