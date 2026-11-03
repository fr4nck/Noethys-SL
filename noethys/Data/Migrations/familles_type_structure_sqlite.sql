-- Migration facultative et explicite. NE PAS appliquer sur la production sans sauvegarde.
-- Les dossiers existants restent de type famille / particulier (NULL).
-- A executer UNE seule fois, apres verification de PRAGMA table_info('familles').
ALTER TABLE familles ADD COLUMN type_structure VARCHAR(40) DEFAULT NULL;
