-- Migration facultative et explicite pour MySQL 5.7.
-- NE PAS appliquer sur la production sans sauvegarde et recette sur copie.
-- Les dossiers existants restent de type famille / particulier (NULL).
-- A executer UNE seule fois apres SHOW COLUMNS FROM familles LIKE 'type_structure'.
ALTER TABLE familles ADD COLUMN type_structure VARCHAR(40) NULL DEFAULT NULL;
