# #436 — Fiche d'accueil enfant : audit et premier contrat commun

**État au 28/10/2026 : sous-lot A, contrat métier pur en développement/qualification.** Pas encore d'écran unifié utilisable, d'enregistrement des autorisations, de document PAI sécurisé, de publication aux familles, ni de migration SQL.

## Inventaire confirmé dans le dépôt

| Rubrique | Source existante | Décision et risque |
| --- | --- | --- |
| Identité/enfant | `individus.IDindividu` et fiche `DLG_Individu` | Réutiliser l'ID, ne pas créer une deuxième fiche enfant |
| AEEH | `individus.aeeh` (`NULL/0/1`), `aeeh_periodes` (`date_debut/date_fin`) | Lecture de ces champs uniquement ; aucune duplication en questionnaire ou médical. Un statut AEEH ne se déduit pas des périodes, ni l'inverse |
| Santé | `problemes_sante`, médecin, vaccinations, onglet médical | Ne pas transcrire de diagnostic dans les autorisations ; pas de lecture par défaut |
| PAI | Aucun statut et historique opérationnels dédiés qualifiés dans cet inventaire | Métadonnées minimales à concevoir et versionner ; ne pas présumer que problème de santé = PAI |
| Repas | `questionnaire_questions/choix/reponses`, choix `standard`, `sans_porc`, `vegetarien`, `sans_repas_pmsl` (#433) | Lecture de la réponse existante, sans nouveau questionnaire ; aucune valeur standard implicite dans la fiche |
| Autorisations | Pas de preuve par enfant/périmètre/période équivalente démontrée | Nécessite un contrat daté et auditable avant persistance ; ne pas utiliser les anciens `DICT_AUTORISATIONS` de liens familiaux |
| Portail | Question `visible_portail` de Noethysweb évoquée en #436, non équivalente au contrat wx | Toutes les rubriques demeurent inaccessibles au portail, sans simple bascule de visibilité |

## Découverte de sécurité (bloquante pour la fiche UI sensible)

Dans `UTILS_Utilisateurs.VerificationDroits`, l'absence de droit explicite retourne `True`. `VerificationDroitsUtilisateurActuel` retourne aussi `True` lorsque la fenêtre générale n'est pas accessible. Les restrictions existantes sur les actions de modification des problèmes de santé **ne constituent donc pas une garantie de confidentialité de lecture**. Ne jamais appeler ces mécanismes seuls pour donner accès à une nouvelle fiche AEEH/PAI.

Le moteur `UTILS_Fiche_accueil_enfant.py` exige une habilitation **exactement `True` par rubrique** (`repas`, `aeeh`, `pai`, `autorisations`), refuse tout accès par défaut et ne calcule pas les données privées lorsqu'il masque une rubrique. **Attention : le contrôleur d'accès à la base doit appliquer le même refus avant ses SELECT**, sinon le masquage de la vue serait insuffisant. Ce raccordement n'est pas encore livré.

## Contrat du moteur livré

- Une vue instantanée par `IDindividu` et date de consultation, sans écriture et indépendante de wx/Qt ; la provenance des données reste dans les tables existantes.
- AEEH : trois états et **liste des périodes d'origine**, avec indicateur de période active indépendant du statut (`None` = aucune période). Aucun indicateur de handicap générique.
- Repas : réutilisation exclusive des **quatre rôles #433**, sans champ médical, sans nouvel enregistrement, sans déduction de présence méridienne ni de facturation.
- PAI : `non_renseigne`, `non`, `signale`, `document_a_verifier`, `valide` ou `expire`. Un PAI validé requiert une vérification documentaire, un valideur identifié et une période ; aucun diagnostic, lien vers pièce ou ordonnance ne sort du moteur. Ce contrat **ne crée pas un registre PAI**.
- Autorisations par enfant et périmètre : piscine/baignade, prise de vue, utilisation interne, site/imprimés, réseaux sociaux, maquillage, activités physiques. L'état est `oui`, `non`, `non_renseigne`, `expire` ou `a_verifier`. Aucun « oui » par défaut. Périodes inclusives, dernière preuve datée prioritaire, révocation sans écrasement, conflit à vérifier ; une décision ultérieure expirée interdit la réactivation automatique d'un ancien « Oui », identité de l'autorité parentale vérifiée explicitement avant `oui`. La question juridique du nombre de signatures nécessaires selon le contexte reste à qualifier : ne pas l'inférer dans ce moteur.
- Aucun partage automatique du statut de prise de vue avec la publication sur les réseaux sociaux. Aucun champ visible aux parents dans cette livraison : `portail` est toujours `False`.

### Contrat attendu de la future persistance d'autorisations

Chaque événement devra comporter `IDindividu`, `type`, `perimetre`, `valeur` (`NULL/0/1`), `date_debut`, `date_fin`, `repondu_le` avec fuseau, `signataire` identifié, `autorite_verifiee`, `texte_version` et référence de preuve protégée. Les preuves et documents eux-mêmes doivent être sécurisés hors export/commande/CI. Les événements historiques seront conservés, et non remplacés silencieusement.

**Aucune table ni migration n'est créée par ce sous-lot.** Le schéma, les clés et les contraintes de concurrence devront être qualifiés sur SQLite et MySQL jetables avant tout code d'écriture.

## Qualification effectuée et restante

- 33 tests locaux purs/SQLite en mémoire sur données fictives : tri-état, périodes, révocations, périmètres, preuve juridique minimale, collision de réponses, confidentialité par défaut, non-couplage des repas, absence de sortie médicale ; aucun serveur, email ou base PMSL utilisée.
- Tests intégrés à la CI rapide Windows à l'occasion du commit, sous réserve du résultat du run GitHub. **Le statut CI ne peut être déclaré PASS qu'après sa conclusion.**
- **À suivre :** audit des droits de lecture et des sorties d'impression, branchement sécurisé des lectures des tables existantes, conception du stockage PAI/autorisations et transaction/historisation, tests de migrations SQLite/MySQL fictives, interface unique wx, qualification des mêmes contrats côté Qt. Activation portail : lot C distinct, désactivé.
- #433 : le run rapide Windows `40634463963` au HEAD code wx `f12c207a` est `SUCCESS` (28/10/2026). Cela ne valide pas le raccordement financier du panier familial.
- #435 : chantier de réconciliation Connecthys séparé, aucune modification réalisée dans ce lot.

## 29/10/2026 — Contrat d'intégration de la Fiche Enfant PMSL existante

**Document maître de mise en forme :** `Fiche Enfant.pdf` et sa version `Fiche Enfant.doc` fournis par PMSL. **Ce formulaire existant est le modèle visuel et fonctionnel** : ne pas le remplacer par une fiche médicale inventée, ni l'aplatir en un questionnaire sans structure.

### Ordre exact des rubriques du formulaire original (deux pages)

**Page 1** — Bandeau « Accueil de loisirs Pêle-Mêle — Fiche enfant » ; ALSH fréquenté (La Guerche CP-CM2, Moutiers PS-GS, Bais), année, classe ; **Identité** (sexe, nom, prénom, date/ville de naissance) ; **Responsable légal n°1** et **n°2** (noms, adresses, CP, commune, téléphones domicile/portable/professionnel) ; **Accompagnants** (nom, prénom, lien, téléphone, engagement de mise à jour écrite) ; **Vaccinations** (copie carnet, dernier DT Polio) ; **Médecin traitant** (identité, commune, cabinet, téléphone).

**Page 2** — **Maladies et allergies** : traitement en cours (oui/non, ordonnance), maladies antérieures, PAI (oui/non et nature déjà saisie), AESH en milieu scolaire (oui/non), AEEH (oui/non), établissement médico-social (oui/non), allergies alimentaires/médicamenteuses/autres, précautions, régime sans viande/sans porc, difficultés de santé, lunettes/prothèses ; **Autorisations diverses** : Photos (site `pelemele.org`), Maquillage, Baignade, Activités physiques (**quatre choix Oui/Non séparés**) ; déclaration finale du responsable légal, lieu/date et **signature manuscrite**, coordonnées PMSL en pied de page.

### Consigne d'intégration des données existantes — sans création de dossier médical parallèle

- **Réutiliser l'onglet médical et ses données déjà présentes** (vaccinations, médecin, allergies, problèmes de santé, traitements, PAI renseignés) pour alimenter les zones correspondantes de la fiche, **dans le respect des droits de lecture existants et de leur éventuel renforcement** ; ne jamais créer une seconde base médicale ni recopier les diagnostics dans l'historique général.
- **Réutiliser `individus.aeeh` et `aeeh_periodes`** plutôt que créer une deuxième question AEEH.
- **Réutiliser l'identité, les deux responsables légaux, les accompagnants et leurs liens familiaux** dans les tables existantes. Pour toute correspondance ambiguë, indiquer « à vérifier » au lieu d'inventer des titulaires.
- **Réutiliser `Type de repas` (#433)** sans écraser ni confondre ses quatre valeurs avec les anciennes cases « sans viande » et « sans porc » du document : afficher la valeur effective et conserver explicitement les cases historiques lors d'un export si elles sont distinctes.
- **Autorisation de photos** : le formulaire courant précise le **site `pelemele.org`**, pas les réseaux sociaux. Ne jamais interpréter « Oui » comme autorisant la publication sur un réseau social. Les autorisations maquillage, baignade et activités physiques doivent garder leur libellé d'origine ; éventuels découpages plus fins dans un écran interne séparé uniquement après décision métier.
- Une réponse absente **ne devient jamais « Oui »**. Distinguer renseigné Oui, renseigné Non, et Non renseigné ; afficher la provenance et la date de la fiche signée. La signature réelle ne peut pas être déduite d'une simple case cliquée.
- **Impression/export fidèle** : reprendre les 2 pages, l'ordre des blocs, titres, sections, largeur des champs, zones de signatures et coordonnées du formulaire. Réserver de la place au texte variable et utiliser un contrôle visuel contre le PDF d'origine.
- **Interface de consultation interne** : une seule vue regroupée, avec liens vers les écrans préexistants pour les champs déjà saisis, et préparation des autorisations non encore enregistrées. Accès contrôlé pour la partie santé ; aucun volet « parents » activé sans consentement et test de droits.
- **Aucun déploiement/migration ni traitement automatique de la base PMSL** avant tests fictifs, qualification des permissions et comparaison visuelle de l'impression avec le PDF fourni.

**Critère de sortie :** pour un enfant fictif entièrement renseigné dans les écrans Noethys existants, la fiche reproduite doit présenter ses données sans ressaisie, respecter les 4 autorisations d'origine, fournir un PDF/imprimé conforme au document PMSL et une provenance fiable pour chaque modification. Le contrôle de réception de fiche enfant déjà présent dans RC10.2/RC10.3 ne suffit pas à ce critère.
