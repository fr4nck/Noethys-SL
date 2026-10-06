# Aujourd’hui — panneau d’accueil RC2

L'horloge est remplacée par un panneau natif clair, défilable. Son titre visible est **Aujourd’hui**. Le nom interne de la pane AUI reste `ephemeride` : les perspectives existantes sont conservées.

## Affichage personnel

Le tableau de bord peut utiliser de **1 à 4 colonnes**. Chaque utilisateur choisit les blocs qu'il veut afficher, leur colonne et leur ordre : Météo, Infos officielles, Vacances scolaires et Événements.

La disposition est enregistrée dans la base Noethys pour l'`IDutilisateur` connecté, sans migration SQL, via la table historique `parametres`. Elle suit donc l'utilisateur lorsqu'il se connecte à la même base depuis un autre poste. Un utilisateur sans préférence retrouve la disposition par défaut en 3 colonnes : météo à gauche, informations officielles puis vacances au centre, événements à droite.

Les sources et données communes (localisation, préfecture, agenda, événements saisis) restent distinctes de cette préférence d'affichage. Masquer Météo ou Infos officielles évite également leurs appels réseau tant que le bloc reste masqué.

## Météo

Trois jours, matin 6–12 h et après-midi 12–18 h, en heure Europe/Paris. Pictogrammes accompagnés de libellés ; température min/max, pluie cumulée, probabilité maximale, vent/rafales maximum, humidité min/max. Les six valeurs horaires doivent être présentes ; un cumul incomplet est affiché « — », jamais comme zéro. Détail sur 7 ou 10 jours sans nouvelle requête. Source : [Open-Meteo](https://open-meteo.com/en/docs), attribution visible dans le panneau.

La localisation vient de l'organisateur (GPS ou ville/code postal). Le géocodage exige une concordance unique avec le code postal français. Réglages manuels disponibles. Aucun lieu personnel imposé à toutes les installations.

Cache de trente minutes, séparé par base, coordonnées et date ; date de consultation visible. Une actualisation manuelle force le réseau. Un échec peut conserver la prévision du même lieu et du même jour, avec une mention explicite. Les coordonnées résolues sont conservées pour permettre le mode hors connexion. Aucune prévision ne constitue une vigilance officielle.

## Préfecture

En Ille-et-Vilaine, découverte du RSS depuis la [page officielle](https://www.ille-et-vilaine.gouv.fr/syndication/listexport). Ailleurs, choisir la source préfectorale HTTPS `.gouv.fr` dans les réglages. Seuls les liens du même hôte sont suivis. Bulletins publiés depuis moins de sept jours, relatifs à vigilance/arrêtés/restrictions/risques. Leur validité et leur territoire doivent être vérifiés dans la source. Un flux indisponible ou non reconnu est signalé, sans conclure à une absence de vigilance. Le flux préfectoral réel n'a pas pu être joint dans l'environnement de développement ; le parsing et la découverte sont testés sur des flux contrôlés.

## Vacances

Calendrier officiel métropolitain A/B/C **2026–2027** issu du calendrier déjà présent sur master et vérifié contre l'[arrêté du 22 octobre 2025](https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000052416058). Zone déduite du code postal ou choisie. Départ après la classe, reprise le matin ; compteur jusqu'au départ. Corse et outre-mer : pas de zone inventée. Hors période couverte, absence de calendrier explicitement indiquée. Les prochaines dates de la table `vacances` sont affichées séparément, sans écriture ni changement des règles dimanche–dimanche.

## Événements

Trois catégories : Officiel, Local, Insolite. Petit catalogue annuel sourcé auprès des organismes (UNESCO/ONU, World Smile Day, Star Wars, International Pasta Organisation). World Smile Day suit le premier vendredi d'octobre et non une date fixe.

Les événements locaux sont **saisis après consultation de leur source**, pas importés automatiquement. L'[agenda de Vitré Communauté](https://www.vitrecommunaute.org/systeme/agenda/?display=liste) est proposé pour le département 35. Réglages : agenda, ajout/retrait des dates, titre, catégorie, commune/secteur, source HTTPS. Le filtre par territoire s'applique seulement aux événements locaux. Horizon de trente jours. Ce catalogue est un point de départ, pas une couverture exhaustive des journées et festivals.

## Recette

- Ouvrir l'accueil et vérifier le titre **Aujourd’hui** ; le nom AUI interne reste `ephemeride`.
- Tester 1, 2, 3 puis 4 colonnes ; déplacer chaque bloc d'une colonne à l'autre, modifier son ordre et le masquer.
- Se déconnecter/reconnecter avec deux identifiants différents : chacun doit retrouver sa propre disposition ; vérifier aussi depuis un second poste si disponible.
- Rétrécir/agrandir la pane : défilement vertical, boutons accessibles, textes correctement repliés dans la largeur de leur colonne.
- Vérifier météo sur trois jours, détail 7 puis 10 jours et attribution.
- Couper le réseau : cache daté ou message d'indisponibilité ; aucune fausse absence d'alerte.
- Choisir ville/GPS, zone et source préfectorale ; fermer et rouvrir Noethys.
- Ajouter un événement Bais puis Moutiers et tester le filtre ; ouvrir leurs sources.
- Vérifier les dates officielles et les dates de la base, notamment dimanche–dimanche.
- Changer de base pendant une requête ; le résultat précédent ne doit pas se publier dans la nouvelle base.
- Fermer la fenêtre pendant une requête : le résultat tardif doit être ignoré.

Aucune migration SQL, aucun nouveau paquet Python. Les accès réseau/DB sont hors du thread graphique ; la publication se fait via `wx.CallAfter` et invalide les résultats obsolètes.
