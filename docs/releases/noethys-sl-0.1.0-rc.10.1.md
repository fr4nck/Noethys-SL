# Noethys SL 0.1.0 RC10.1 — sauvegardes réseau

Cette mise à jour Windows reprend RC10 et corrige la sauvegarde MySQL/MariaDB,
notamment la procédure automatique « Ma sauvegarde ». Elle conserve la version
interne de compatibilité **1.3.4.4**, les données et les réglages existants.

- Si le dossier enregistré n'existe pas sur le poste, Noethys propose d'en
  choisir un autre avant l'export. Le choix est mémorisé **sur ce poste** après
  une sauvegarde réussie ; le dossier des autres ordinateurs n'est pas modifié.
- L'export MySQL est lancé directement, surveillé, avec progression visible et
  diagnostic en cas de blocage. Les gros documents binaires sont pris en charge.
- Les dumps doivent être complets avant archivage. Les sauvegardes précédentes
  sont préservées si une copie échoue ou si la procédure est annulée.
- La vérification des gros dumps laisse la fenêtre de progression active.

**Installation :** pour une installation classique, télécharger le **Setup** et
installer dans le même dossier que la version précédente. Pour une utilisation
portable, extraire le **ZIP portable dans un nouveau dossier** et reprendre
volontairement sa configuration. Les clients MySQL 5.7 nécessaires à la sauvegarde
sont fournis ; aucun serveur MySQL n'est installé par ce paquet.

Au premier essai de « Ma sauvegarde », si le dossier d'un ancien poste est
introuvable, choisir un dossier existant et accessible sur l'ordinateur courant.
Attendre le message de fin de sauvegarde. En cas d'échec, conserver le diagnostic
indiqué par l'application ; une archive interrompue n'est pas une sauvegarde valide.

**Validation du paquet :** tests Windows, sauvegarde/restauration MySQL 5.7
jetable avec document fictif de plus de 24 Mio, présence du moteur dans
l'exécutable, démarrage du programme, deux démarrages portables avec conservation
du profil et empreintes SHA-256. Les fichiers `Setup.exe`, `Windows-portable.zip`
et `SHA256SUMS.txt` proviennent du même commit vérifié.

Les limites de RC10 sur les autres chantiers restent applicables, notamment
CAF/AFAS masqué et OCR non livré. RC10.1 reste une préversion de la série 0.1.0.
La publication n'installe rien automatiquement et n'effectue aucune restauration
sur les bases utilisées au quotidien. RC10 reste disponible comme référence.
