# Conventions Word

Dans la fiche famille, choisir **G�n�rer une convention**, puis **Word � DOCX**.
S�lectionner un mod�le `.docx`, renseigner la p�riode et les valeurs propos�es,
puis g�n�rer. Le document rempli est enregistr� s�par�ment du mod�le et ouvert
dans l'application Word/LibreOffice associ�e. Aucun paiement ou tarif n'est
modifi� par cette g�n�ration.

Le mod�le se pr�pare dans Word ou LibreOffice avec les m�mes mots-cl�s que
Noedoc. La police d'un mot-cl� et son style sont conserv�s lors du remplacement,
y compris lorsque Word a r�parti le mot-cl� entre plusieurs runs. Les champs
sont trait�s dans le corps, les tableaux, les zones de texte, les en-t�tes et les
pieds de page. Les images du mod�le sont conserv�es.

Exemples : `{ORGANISATEUR_NOM}`, `{ORGANISATEUR_RUE}`, `{ORGANISATEUR_CP}`,
`{ORGANISATEUR_VILLE}`, `{ORGANISATEUR_TEL}`, `{ORGANISATEUR_MAIL}`,
`{FAMILLE_NOM}`, `{CONVENTION_ADRESSE_STRUCTURE}`, `{CONVENTION_SAISON}`,
`{CONVENTION_REPRESENTANT_NOM_COMPLET}`, `{CONVENTION_REPRESENTANT_FONCTION}`,
`{CONVENTION_DATE_SIGNATURE}`, `{CONVENTION_LIEU_SIGNATURE}`,
`{CONVENTION_TARIF_HORAIRE_AFFICHE}`, `{CONVENTION_PLANNING_DETAIL}`.

Les autres champs calcul�s par `UTILS_Convention_champs.GetChampsConvention`
sont �galement disponibles. Les champs inconnus produisent une erreur sans
�craser un document de sortie existant. Les valeurs absentes restent vides.
Les longues valeurs du planning utilisent de vrais sauts de ligne Word.

Seul `.docx` est pris en charge, pas l'ancien format binaire `.doc`. Les formules
conditionnelles Noedoc `[[...]]` sont explicitement refus�es ; cette premi�re
version prend en charge les mots-cl�s, pas le langage de formules. Les images
et les signatures int�gr�es au mod�le restent celles du mod�le choisi.

Le moteur repose sur ZIP et XML de la biblioth�que standard ; aucune nouvelle
d�pendance n'est n�cessaire dans l'installation Noethys. Word ou LibreOffice
est utile pour �diter/ouvrir le r�sultat, mais pas pour le remplir. La g�n�ration
ne convertit pas automatiquement la convention Word en PDF.
