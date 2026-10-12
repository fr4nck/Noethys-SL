# Aujourd’hui — panneau d’accueil RC2

L'horloge est remplacée par un panneau natif clair, défilable. Son titre visible est **Aujourd’hui**. Le nom interne de la pane AUI reste `ephemeride` : les perspectives existantes sont conservées.

## Affichage personnel

Le tableau de bord peut utiliser de **1 à 4 colonnes**. Chaque utilisateur choisit les blocs qu'il veut afficher, leur colonne et leur ordre : Météo, Vacances scolaires et Événements.

La disposition est enregistrée dans la base Noethys pour l'`IDutilisateur` connecté, sans migration SQL, via la table historique `parametres`. Elle suit donc l'utilisateur lorsqu'il se connecte à la même base depuis un autre poste. Un utilisateur sans préférence retrouve la disposition par défaut en 3 colonnes : météo à gauche, vacances au centre, événements à droite.

Le panneau est volontairement consultatif : il n'affiche ni bouton **Actualiser**, ni bouton **Réglages**, ni localisation de l'organisateur dans son en-tête. L'actualisation est automatique toutes les trente minutes. La personnalisation se trouve dans **Affichage > Personnaliser Aujourd’hui…**. Les sources et données communes (localisation météo, agenda, événements saisis) restent distinctes de la préférence d'affichage.

## Météo

Trois jours, matin 6–12 h et après-midi 12–18 h, en heure Europe/Paris. Pictogrammes accompagnés de libellés ; température min/max, pluie cumulée, probabilité maximale, vent/rafales maximum, humidité min/max. Les six valeurs horaires doivent être présentes ; un cumul incomplet est affiché « — », jamais comme zéro. Détail sur 7 ou 10 jours sans nouvelle requête. Source : [Open-Meteo](https://open-meteo.com/en/docs), attribution visible dans le panneau.

La localisation vient de l'organisateur (GPS ou ville/code postal). Le géocodage exige une concordance unique avec le code postal français. Réglages manuels disponibles. Aucun lieu personnel imposé à toutes les installations.

Cache de trente minutes, séparé par base, coordonnées et date ; date de consultation visible. L'actualisation est automatique. Un échec peut conserver la prévision du même lieu et du même jour, avec une mention explicite. Les coordonnées résolues sont conservées pour permettre le mode hors connexion. Aucune prévision ne constitue une vigilance officielle.

## Informations officielles

Le bloc préfectoral/RSS est **retiré de l'interface RC2**. L'extraction n'est pas considérée assez fiable pour présenter une information directement exploitable sans explication supplémentaire. Le code de parsing peut rester disponible en interne pour expérimentation, mais aucun flux RSS, message « à vérifier » ou erreur de source préfectorale ne doit apparaître dans le panneau Aujourd’hui.

## Vacances

Calendrier officiel métropolitain A/B/C **2026–2027** issu du calendrier déjà présent sur master et vérifié contre l'[arrêté du 22 octobre 2025](https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000052416058). Zone déduite du code postal ou choisie. Départ après la classe, reprise le matin ; compteur jusqu'au départ. Corse et outre-mer : pas de zone inventée. Hors période couverte, absence de calendrier explicitement indiquée. Les prochaines dates de la table `vacances` sont affichées séparément, sans écriture ni changement des règles dimanche–dimanche.

## Événements

Le panneau n'utilise plus de Notebook par catégorie. Il affiche directement, dans une liste compacte et triée par date, les **10 prochaines dates Officiel/Insolite** disponibles dans le catalogue sourcé. Les catégories restent visibles sur chaque ligne. Le catalogue couvre désormais suffisamment de dates annuelles pour alimenter ce prochain-10 sur une année glissante ; World Smile Day suit le premier vendredi d'octobre et non une date fixe.

Les événements locaux restent distincts : ils sont **saisis après consultation de leur source**, pas importés automatiquement, puis affichés sous une rubrique Local lorsque des dates existent dans les trente prochains jours. L'[agenda de Vitré Communauté](https://www.vitrecommunaute.org/systeme/agenda/?display=liste) reste disponible comme source à consulter.

## Recette

- Ouvrir l'accueil et vérifier le titre **Aujourd’hui** ; le nom AUI interne reste `ephemeride`.
- Tester 1, 2, 3 puis 4 colonnes ; déplacer chaque bloc d'une colonne à l'autre, modifier son ordre et le masquer.
- Se déconnecter/reconnecter avec deux identifiants différents : chacun doit retrouver sa propre disposition ; vérifier aussi depuis un second poste si disponible.
- Rétrécir/agrandir la pane : défilement vertical et textes correctement repliés dans la largeur de leur colonne ; aucun bouton d'administration ne doit apparaître dans le panneau.
- Vérifier météo sur trois jours, détail 7 puis 10 jours et attribution.
- Couper le réseau : cache daté ou message d'indisponibilité ; aucun bloc préfectoral/RSS ne doit apparaître.
- Ouvrir **Affichage > Personnaliser Aujourd’hui…**, choisir ville/GPS et zone, fermer et rouvrir Noethys.
- Vérifier l'affichage compact des 10 prochaines dates Officiel/Insolite.
- Ajouter un événement Bais puis Moutiers et tester le filtre local ; ouvrir leurs sources.
- Vérifier les dates officielles et les dates de la base, notamment dimanche–dimanche.
- Changer de base pendant une requête ; le résultat précédent ne doit pas se publier dans la nouvelle base.
- Fermer la fenêtre pendant une requête : le résultat tardif doit être ignoré.

Aucune migration SQL, aucun nouveau paquet Python. Les accès réseau/DB sont hors du thread graphique ; la publication se fait via `wx.CallAfter` et invalide les résultats obsolètes.
