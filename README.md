# plan

Projet de suivi et de modelisation de workflows.

## Objectif

Definir un modele de donnees pour suivre des workflows, documenter les etats,
transitions et lignes d'eau, puis produire des representations Mermaid
utilisables dans MediaWiki.

## Documentation

- docs/database-structure.md
- docs/specifications.md
- docs/html-site-generation.md
- docs/mermaid-representations.md
- TODO.md
- DEVELOPMENT.md

## Schema

Le fichier schema/workflow-model.json decrit les tables, champs, types et relations du modele initial.

## Génération Mermaid

Le script `scripts/generate_mermaid.py` génère un diagramme de processus
Mermaid et un `stateDiagram-v2`. Les workflows qui contiennent des lignes d'eau
sont rendus avec la syntaxe native `swimlane-beta`; les vues structurelles de
schéma restent en `flowchart` :

```powershell
py scripts/generate_mermaid.py examples/workflow-data.json
py scripts/generate_mermaid.py schema/workflow-model.json --output workflow-model.md
py scripts/generate_mermaid.py data/workflows/projet-informatique/manifest.json
```

La sortie par défaut contient des blocs Mermaid Markdown directement
réutilisables dans une page MediaWiki configurée pour Mermaid. Consulter
`docs/mermaid-representations.md` pour les formats d'entrée, les options et les
règles de génération.

## Validation des données

Le modèle et les fichiers de données doivent toujours rester compatibles. Le
workflow de projet informatique fragmenté se valide avec :

```powershell
py scripts/validate_workflow_data.py `
  data/workflows/projet-informatique/manifest.json
py -m unittest discover -s tests -v
```

Ces contrôles sont également exécutés automatiquement par l'intégration
continue.

## Génération HTML

Une page HTML complète :

```powershell
py scripts/generate_workflow_html.py `
  data/workflows/projet-informatique/manifest.json `
  --output build/projet-informatique.html
```

Un site statique navigable :

```powershell
py scripts/generate_workflow_site.py `
  data/workflows/catalog.json `
  --output build/site-workflows
```

Consulter `docs/html-site-generation.md` pour la structure des sorties, la
navigation, la sécurité des textes HTML et la configuration de Mermaid.

## Console d’exploitation TUI

Une interface terminal centralise le catalogue, la création de workflows,
l'accès aux paramétrages, la validation, la génération d'un fichier Mermaid ou
du site complet et deux réglages clairement séparés : thème de la TUI et thèmes
indépendants des sites web :

```powershell
python -m pip install -r requirements-tui.txt
python scripts/workflow_tui.py
```

Les raccourcis clavier, les modes sans interface et les règles de création sont
documentés dans `docs/tui.md`.

La page d'accueil permet de choisir les workflows « Documentation », « Projet
informatique » et « Analyse statique de code ». Le workflow « Documentation »
contient un guide visuel des formes, couleurs, liens, puces, infobulles,
orientations, familles de diagrammes et limites du moteur. Dans chaque workflow,
`index.html` fusionne la vue générale et le diagramme des phases. Les
diagrammes avec lignes d'eau utilisent des couloirs Mermaid `swimlane-beta`.
Chaque schéma est suivi d'un volet « Afficher le code Mermaid ». Les pages de
workflow ouvrent l'éditeur avec le bon workflow présélectionné, et l'éditeur
permet de revenir à sa version publiée.

Le portail commun et chaque workflow disposent de leur propre page
`settings.html`, avec un mode clair, sombre ou automatique et les paires Océan,
Forêt, Aubergine ou Graphite. Les préférences sont conservées séparément dans
le navigateur et une bascule d'en-tête change le mode immédiatement.
Le site HTML embarque localement la version de Mermaid déclarée dans
`scripts/vendor/javascript-dependencies.json`, car cette syntaxe nécessite
Mermaid 11.16.0 ou une version ultérieure. Il reste ainsi utilisable dans
Firefox et hors ligne lorsque les pages sont ouvertes directement avec une URL
`file://` ; les grands diagrammes sont consultables par défilement horizontal.
La dépendance se contrôle et se met à jour avec
`scripts/update_javascript_dependencies.ps1` ; la procédure détaillée figure
dans `docs/html-site-generation.md`.
L'entrée
`Répertoire des états` mène à `etats.html` et `Répertoire des transitions` à
`transitions.html`. Ces pages affichent les liens structurés et leur validité.
Les pages individuelles `states/*.html` ne sont plus générées.

Le catalogue génère aussi `editor.html`. Cette page permet de choisir un
workflow, de modifier ses états et transitions, leurs liens, puis de copier ou
enregistrer explicitement le document JSON fusionné. Le site statique ne peut
pas remplacer silencieusement les sources du projet : un sélecteur de fichier
est utilisé lorsque le navigateur le permet, avec un téléchargement de repli.
Le formulaire accepte le texte de l'état
en Markdown, HTML ou texte brut et met en évidence les destinations invalides
des états et transitions. Les états et transitions existants sont sélectionnés
par leur libellé et leur identifiant ; l'inventaire complet des états reste
consultable dans `etats.html`. Un bouton permet d'afficher l'édition des
transitions à droite des états ou en dessous.
Ces avertissements ne bloquent pas l'export JSON. Le vocabulaire normatif est
affiché dans l'éditeur et défini dans `docs/specifications.md`.

## Tests et traçabilité

Les exigences de `docs/specifications.md` sont reliées au code, aux tests
unitaires et aux tests fonctionnels par
`traceability/requirements.json`.

```powershell
py scripts/validate_traceability.py
py -m unittest discover -s tests -v
```

La méthode et les conventions sont documentées dans
`docs/testing-traceability.md`.

## Exigence documentaire

Toute modification du modele de donnees, des regles de workflow ou des representations Mermaid doit etre accompagnee d'une mise a jour de la documentation.
