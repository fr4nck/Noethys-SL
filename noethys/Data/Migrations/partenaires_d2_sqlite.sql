-- Lot D2 : migration SEPAREE, a executer manuellement sur copie jetable apres D1.
-- Foreign keys doit etre active sur chaque connexion : PRAGMA foreign_keys=ON.
-- Aucun ALTER des tables Noethys et aucune migration implicite.
-- Preconditions explicites : D1 doit deja etre installe dans cette base jetable.
SELECT IDpartenaire FROM partenaires_structures LIMIT 0;
CREATE TABLE partenaires_conventions (
  IDconvention_partenaire INTEGER PRIMARY KEY AUTOINCREMENT,
  IDpartenaire INTEGER NOT NULL REFERENCES partenaires_structures(IDpartenaire) ON DELETE RESTRICT,
  reference TEXT NOT NULL CHECK (length(trim(reference)) > 0),
  libelle TEXT NOT NULL CHECK (length(trim(libelle)) > 0),
  type_convention TEXT NOT NULL CHECK (type_convention IN ('scolaire','associative','collectivite','autre')),
  date_debut TEXT NOT NULL,
  date_fin TEXT NOT NULL CHECK (date_fin >= date_debut),
  etat TEXT NOT NULL CHECK (etat IN ('ouverte','cloturee')),
  cree_le TEXT NOT NULL,
  modifie_le TEXT NOT NULL,
  UNIQUE (IDpartenaire, reference)
);
CREATE INDEX idx_partenaires_conventions_structure ON partenaires_conventions(IDpartenaire, etat);

CREATE TABLE partenaires_conventions_versions (
  IDversion INTEGER PRIMARY KEY AUTOINCREMENT,
  IDconvention_partenaire INTEGER NOT NULL REFERENCES partenaires_conventions(IDconvention_partenaire) ON DELETE RESTRICT,
  numero_version INTEGER NOT NULL CHECK (numero_version > 0),
  nature TEXT NOT NULL CHECK (nature IN ('initiale','avenant')),
  statut TEXT NOT NULL CHECK (statut IN ('brouillon','signee')),
  brouillon_marker INTEGER CHECK (brouillon_marker = 1 OR brouillon_marker IS NULL),
  date_effet TEXT NOT NULL,
  clauses TEXT NOT NULL DEFAULT '',
  support_modele TEXT NOT NULL CHECK (support_modele IN ('noedoc','word')),
  reference_modele TEXT NOT NULL,
  mode_facturation TEXT NOT NULL CHECK (mode_facturation IN ('payante','gratuite')),
  date_signature TEXT,
  signataire TEXT,
  empreinte_document_signe TEXT,
  partenaire_snapshot TEXT,
  empreinte_contenu TEXT,
  cree_le TEXT NOT NULL,
  modifie_le TEXT NOT NULL,
  UNIQUE (IDconvention_partenaire, numero_version),
  UNIQUE (IDconvention_partenaire, brouillon_marker),
  CHECK ((statut='brouillon' AND brouillon_marker=1 AND date_signature IS NULL
      AND empreinte_document_signe IS NULL AND empreinte_contenu IS NULL)
    OR (statut='signee' AND brouillon_marker IS NULL AND date_signature IS NOT NULL
      AND signataire IS NOT NULL AND empreinte_document_signe IS NOT NULL
      AND partenaire_snapshot IS NOT NULL AND empreinte_contenu IS NOT NULL))
);
CREATE INDEX idx_partenaires_conventions_versions_etat
 ON partenaires_conventions_versions(IDconvention_partenaire, statut, date_effet);

-- TEXT volontaire sur SQLite : DECIMAL(n,2) y deviendrait REAL et perdrait l'exactitude.
-- MySQL 5.7 utilise DECIMAL(12,2) ; le moteur Python echange des Decimal/str.
CREATE TABLE partenaires_conventions_tarifs (
  IDtarif_convention INTEGER PRIMARY KEY AUTOINCREMENT,
  IDversion INTEGER NOT NULL REFERENCES partenaires_conventions_versions(IDversion) ON DELETE RESTRICT,
  categorie TEXT NOT NULL CHECK (categorie IN ('adultes','enfants','scolaires','autre')),
  libelle TEXT NOT NULL CHECK (length(trim(libelle)) > 0),
  unite TEXT NOT NULL CHECK (unite IN ('heure','seance','forfait')),
  montant TEXT NOT NULL CHECK (length(trim(montant)) > 0),
  date_debut TEXT NOT NULL,
  date_fin TEXT NOT NULL CHECK (date_fin >= date_debut)
);
CREATE INDEX idx_partenaires_conventions_tarifs_version ON partenaires_conventions_tarifs(IDversion, categorie);

CREATE TABLE partenaires_conventions_evenements (
  IDevenement INTEGER PRIMARY KEY AUTOINCREMENT,
  nature TEXT NOT NULL CHECK (nature IN ('convention','version','tarifs')),
  IDobjet INTEGER NOT NULL,
  action TEXT NOT NULL,
  acteur TEXT NOT NULL,
  champs TEXT NOT NULL DEFAULT '',
  date_action TEXT NOT NULL
);
CREATE INDEX idx_partenaires_conventions_evenements_objet
 ON partenaires_conventions_evenements(nature, IDobjet, IDevenement);
