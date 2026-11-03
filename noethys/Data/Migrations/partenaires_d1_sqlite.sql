-- Lot D1 - SQLite, EXECUTION MANUELLE SUR BASE DE TEST UNIQUEMENT.
-- Echec voulu si une table existe deja : aucune migration implicite.
CREATE TABLE partenaires_structures (
    IDpartenaire INTEGER PRIMARY KEY AUTOINCREMENT,
    categorie TEXT NOT NULL CHECK (categorie IN ('association', 'ecole', 'collectivite', 'etablissement', 'autre')),
    raison_sociale TEXT NOT NULL CHECK (length(trim(raison_sociale)) > 0),
    nom_usage TEXT,
    siret TEXT,
    adresse_ligne1 TEXT,
    code_postal TEXT,
    commune TEXT,
    pays TEXT,
    email_general TEXT,
    telephone_general TEXT,
    observations TEXT,
    statut TEXT NOT NULL CHECK (statut IN ('actif', 'archive')),
    cree_le TEXT NOT NULL,
    modifie_le TEXT NOT NULL
);
CREATE INDEX idx_partenaires_structures_nom ON partenaires_structures(raison_sociale);
CREATE INDEX idx_partenaires_structures_categorie ON partenaires_structures(categorie, statut);

CREATE TABLE partenaires_contacts (
    IDcontact_partenaire INTEGER PRIMARY KEY AUTOINCREMENT,
    IDpartenaire INTEGER NOT NULL REFERENCES partenaires_structures(IDpartenaire) ON DELETE RESTRICT,
    nom TEXT NOT NULL CHECK (length(trim(nom)) > 0),
    prenom TEXT,
    fonction TEXT,
    email TEXT,
    telephone TEXT,
    principal INTEGER CHECK (principal = 1 OR principal IS NULL),
    statut TEXT NOT NULL CHECK (statut IN ('actif', 'archive')),
    cree_le TEXT NOT NULL,
    modifie_le TEXT NOT NULL,
    UNIQUE (IDpartenaire, principal)
);
CREATE INDEX idx_partenaires_contacts_parent ON partenaires_contacts(IDpartenaire, statut);

CREATE TABLE partenaires_liens_noethys (
    IDlien INTEGER PRIMARY KEY AUTOINCREMENT,
    IDpartenaire INTEGER NOT NULL REFERENCES partenaires_structures(IDpartenaire) ON DELETE RESTRICT,
    type_reference TEXT NOT NULL CHECK (type_reference IN ('famille', 'compte_payeur', 'tiers_comptable')),
    IDreference INTEGER NOT NULL CHECK (IDreference > 0),
    actif INTEGER CHECK (actif = 1 OR actif IS NULL),
    date_debut TEXT NOT NULL,
    date_fin TEXT,
    UNIQUE (type_reference, IDreference, actif),
    UNIQUE (IDpartenaire, type_reference, actif)
);
CREATE INDEX idx_partenaires_liens_parent ON partenaires_liens_noethys(IDpartenaire, actif);

CREATE TABLE partenaires_evenements (
    IDevenement INTEGER PRIMARY KEY AUTOINCREMENT,
    nature TEXT NOT NULL CHECK (nature IN ('structure', 'contact', 'lien')),
    IDobjet INTEGER NOT NULL,
    action TEXT NOT NULL,
    acteur TEXT NOT NULL,
    champs TEXT NOT NULL DEFAULT '',
    date_action TEXT NOT NULL
);
CREATE INDEX idx_partenaires_evenements_objet ON partenaires_evenements(nature, IDobjet, IDevenement);
