# Prochaines étapes de conception

## 1. Stabiliser l'existant

- [x] Valider les jeux de données des workflows disponibles.
- [x] Exécuter l'ensemble des tests unitaires et fonctionnels.
- [x] Vérifier la cohérence entre les spécifications, la matrice de traçabilité et l'implémentation.
- Documenter les limites actuellement connues.

## 2. Clarifier l'architecture cible

- Définir la séparation entre le modèle métier, le chargement des données et les générateurs de sortie.
- [x] Formaliser les responsabilités des scripts de validation, de génération Mermaid et de génération HTML.
- [x] Décider si le catalogue de workflows reste un fichier statique ou devient une abstraction extensible.
- Définir une stratégie de versionnement du schéma et des fichiers de données.

## 3. Faire évoluer le modèle de données

- Recenser les besoins communs aux différents workflows.
- Identifier les extensions nécessaires pour les rôles, règles, phases, états et transitions.
- Ajouter un attribut `couleur` aux états et définir son format ainsi que sa valeur par défaut.
- Ajouter un attribut `type` aux états.
- Limiter les valeurs autorisées de `type` à `etape`, `exigence` et `service`.
- [x] Préciser les contraintes d'intégrité et les règles de compatibilité ascendante.
- Ajouter chaque nouvelle exigence dans `docs/specifications.md` avant son implémentation.

## 4. Intégrer Grist

- Créer un modèle Grist de la DINUM conforme au modèle de référence au format JSON.
- Définir la correspondance entre chaque table et chaque champ du modèle JSON et leurs équivalents dans Grist.
- Ajouter dans Grist les écrans permettant de créer et de modifier les workflows, leurs phases, leurs états et leurs transitions.
- Intégrer les champs `couleur` et `type` des états dans les tables et les écrans de saisie Grist.
- Valider dans Grist les valeurs autorisées pour le type d'un état : `etape`, `exigence` ou `service`.
- Prévoir un contrôle automatisé détectant tout écart de structure entre le modèle JSON et les tables Grist.
- Maintenir simultanément le modèle JSON, les tables Grist, les écrans de saisie, la documentation et les tests lors de chaque modification du modèle.
- Documenter la procédure de migration des documents Grist existants lorsqu'une évolution du modèle n'est pas rétrocompatible.

## 5. Préparer les prochaines fonctionnalités

- Définir les formats d'import et d'export prioritaires.
- Étudier la génération de vues filtrées par rôle, phase ou état.
- [x] Prévoir une navigation croisée entre workflows, phases et états.
- [x] Fournir une interface statique d'édition et d'export JSON des workflows.
- Créer une zone d'administration.
- Créer une zone de suivi de projet.
- Le suivi de projet doit se dérouler à travers des écrans gérés par Grist.
- Ajouter une gestion des droits utilisant Keycloak pour contrôler l'accès à la zone d'administration et à la zone de suivi de projet.
- L'authentification doit utiliser le serveur Keycloak de la suite incluant Grist ou un autre serveur Keycloak paramétrable.
- Générer dans les pages Grist les mêmes informations que dans la partie statique du site.
- Permettre la modification des workflows depuis la zone de suivi de projet.
- Permettre de renseigner le niveau d'avancement de chaque état du workflow.
- Permettre l'ajout et l'historisation de commentaires pour chaque état de chaque projet suivi.
- Permettre le suivi simultané de plusieurs projets.
- Permettre à un utilisateur connecté de sélectionner plusieurs projets.
- Gérer, depuis les écrans d'administration, les droits de chaque utilisateur sur chaque projet.
- Permettre à un utilisateur de visualiser les prochaines étapes du workflow en fonction de l'accomplissement des états.
- Représenter les tâches à accomplir sous la forme d'un inventaire de fragments de workflow centrés sur ces tâches, avec une mise en évidence de leurs états.
- Créer un écran d'administration permettant d'éditer tous les attributs d'un workflow au format JSON.
- Permettre de lancer la génération des pages statiques depuis les écrans d'administration.
- Permettre à un administrateur de créer un nouveau suivi de projet pour un utilisateur.
- Permettre à un utilisateur de créer un nouveau projet à suivre pour lui-même.
- Créer les nouveaux projets à partir d'un modèle de workflow au format JSON.
- Gérer plusieurs modèles de workflow au format JSON et permettre d'en sélectionner un lors de la création d'un nouveau suivi de projet.

## 6. Renforcer la qualité

- [x] Ajouter des scénarios de test pour les données invalides et les références croisées.
- [x] Tester la génération complète du site avec plusieurs workflows.
- [x] Vérifier l'accessibilité et la sécurité des sorties HTML.
- Tester la conformité entre le modèle JSON, les tables Grist et les écrans de saisie.
- Ajouter des contrôles automatiques de formatage et de validation dans l'intégration continue.

## notes
- lignes d'eau
- dockerisation
- construction d'un pugin grist
- sauvegarde dans les tables grist
- [x] éditeur du texte de l'état en Markdown, HTML ou texte brut
- ajout d'un editeur mermaid
- convertion mermaid <-> tableau grist

## 7. Éditeur JSON et vocabulaire

- [x] Unifier « description » et « texte associé » sous le terme « texte de l'état ».
- [x] Conserver les formats de saisie Markdown, HTML et texte brut.
- [x] Supprimer les pages individuelles `states/*.html`.
- [x] Conserver un répertoire unique des états dans `etats.html`.
- [x] Signaler les états contenant une destination de lien invalide.
- [x] Autoriser la copie et le téléchargement du JSON malgré ces avertissements.
- [x] Afficher le vocabulaire normatif dans l'éditeur.
- [x] Documenter la compatibilité ascendante du champ historique `Etat.description`.
- [x] Remplacer le tableau des transitions par une liste dans le champ identifiant.
- [x] Charger et supprimer une transition depuis le formulaire.
- [x] Remplacer le tableau des états par une liste dans le champ identifiant.
- [x] Charger et supprimer un état depuis le formulaire.
- [x] Relier l'éditeur au répertoire distinct `etats.html`.
- [x] Permettre de placer l'édition des transitions à droite ou sous les états.
- [x] Mémoriser la disposition de l'éditeur dans `localStorage`.
- [x] Générer un répertoire `transitions.html` accessible depuis la navigation.
- [x] Afficher la validité des liens dans les répertoires des états et transitions.
- [x] Éditer les liens structurés portés par les transitions.
- [x] Fournir des exemples valides et invalides pour les états et transitions.
- [x] Remplacer la simulation des swimlanes en `flowchart` par la syntaxe
  Mermaid native `swimlane-beta`.



## Critères de décision

Chaque évolution doit :

1. conserver la compatibilité entre le schéma et les données ;
2. être reliée à une exigence et à des tests ;
3. maintenir la documentation concernée ;
4. éviter de coupler le modèle métier à un format de rendu particulier ;
5. fournir un chemin de migration lorsque le format des données change ;
6. maintenir la cohérence du modèle JSON, des tables Grist et des écrans de saisie.
