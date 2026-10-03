# Conventions Word

Dans la fiche famille, choisir **Générer une convention**, puis **Word → DOCX**.
Sélectionner un modèle `.docx`, renseigner la période et les valeurs proposées,
puis générer. Le document rempli est enregistré séparément du modèle et ouvert
dans l'application Word/LibreOffice associée. Aucun paiement ou tarif n'est
modifié par cette génération.

Le modèle se prépare dans Word ou LibreOffice avec les mêmes mots-clés que
Noedoc. La police d'un mot-clé et son style sont conservés lors du remplacement,
y compris lorsque Word a réparti le mot-clé entre plusieurs runs. Les champs
sont traités dans le corps, les tableaux, les zones de texte, les en-têtes et les
pieds de page. Les images du modèle sont conservées.

Exemples : `{ORGANISATEUR_NOM}`, `{ORGANISATEUR_RUE}`, `{ORGANISATEUR_CP}`,
`{ORGANISATEUR_VILLE}`, `{ORGANISATEUR_TEL}`, `{ORGANISATEUR_MAIL}`,
`{FAMILLE_NOM}`, `{CONVENTION_ADRESSE_STRUCTURE}`, `{CONVENTION_SAISON}`,
`{CONVENTION_REPRESENTANT_NOM_COMPLET}`, `{CONVENTION_REPRESENTANT_FONCTION}`,
`{CONVENTION_DATE_SIGNATURE}`, `{CONVENTION_LIEU_SIGNATURE}`,
`{CONVENTION_TARIF_HORAIRE_AFFICHE}`, `{CONVENTION_PLANNING_DETAIL}`.

Les autres champs calculés par `UTILS_Convention_champs.GetChampsConvention`
sont également disponibles. Les champs inconnus produisent une erreur sans
écraser un document de sortie existant. Les valeurs absentes restent vides.
Les longues valeurs du planning utilisent de vrais sauts de ligne Word.

Seul `.docx` est pris en charge, pas l'ancien format binaire `.doc`. Les formules
conditionnelles Noedoc `[[...]]` sont explicitement refusées ; cette première
version prend en charge les mots-clés, pas le langage de formules. Les images
et les signatures intégrées au modèle restent celles du modèle choisi.

Le moteur repose sur ZIP et XML de la bibliothèque standard ; aucune nouvelle
dépendance n'est nécessaire dans l'installation Noethys. Word ou LibreOffice
est utile pour éditer/ouvrir le résultat, mais pas pour le remplir. La génération
ne convertit pas automatiquement la convention Word en PDF.
