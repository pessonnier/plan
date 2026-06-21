# plan

Projet de suivi et de modelisation de workflows.

## Objectif

Definir un modele de donnees pour suivre des workflows, documenter les etats et transitions, puis produire des representations Mermaid utilisables dans MediaWiki.

## Documentation

- docs/database-structure.md
- docs/mermaid-representations.md
- DEVELOPMENT.md

## Schema

Le fichier schema/workflow-model.json decrit les tables, champs, types et relations du modele initial.

## Génération Mermaid

Le script `scripts/generate_mermaid.py` génère un `flowchart` et un
`stateDiagram-v2` :

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
navigation, la sécurité des descriptions HTML et la configuration de Mermaid.

La page d'accueil permet de choisir entre les workflows « Projet
informatique » et « Analyse statique de code ». Dans chaque workflow,
`index.html` fusionne la vue générale et le diagramme des phases. L'onglet
`Tous les états` mène à `etats.html`.

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
