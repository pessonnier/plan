# Directives de développement

Ce projet vise à modéliser des workflows de suivi, à produire des représentations Mermaid et à documenter les règles associées.

## Principe général

Toute évolution du modèle de données, des règles de workflow ou de la génération Mermaid doit être accompagnée d'une mise à jour de la documentation.

Le maintien de la documentation est obligatoire.

## Traçabilité spécifications-code-tests

Toute exigence fonctionnelle doit recevoir un identifiant stable `REQ-*` dans
`docs/specifications.md`. La matrice `traceability/requirements.json` doit la
relier à son code, à au moins un test unitaire et à au moins un test
fonctionnel.

Le contrôle est obligatoire :

```powershell
py scripts/validate_traceability.py
```

Les conventions détaillées sont décrites dans
`docs/testing-traceability.md`.

## Compatibilité obligatoire du modèle et des données

Le fichier `schema/workflow-model.json` constitue la référence contractuelle
des fichiers de données.

Toute modification du modèle ou d'un jeu de données doit conserver leur
compatibilité réciproque. Elle doit être vérifiée par des tests automatisés qui
contrôlent au minimum :

- l'existence des tables et champs dans le modèle ;
- les champs obligatoires et les types de valeurs ;
- les valeurs autorisées pour les champs de type `choice` ;
- l'unicité des identifiants ;
- la résolution des références entre tables, y compris entre fichiers ;
- la compatibilité Mermaid des identifiants.

Une modification ne doit pas être considérée comme complète si les tests de
compatibilité échouent. Le validateur de référence est
`scripts/validate_workflow_data.py`.

## Documentation obligatoire

Une pull request ne doit pas être considérée comme complète si elle modifie le comportement ou la structure du projet sans mettre à jour les documents concernés.

Les documents à maintenir sont notamment :

- `docs/database-structure.md` pour la structure de la base de données ;
- `docs/mermaid-representations.md` pour les diagrammes Mermaid ;
- `docs/html-site-generation.md` pour les pages HTML et sites statiques ;
- `docs/specifications.md` pour les exigences fonctionnelles ;
- `docs/testing-traceability.md` pour la stratégie de test et de traçabilité ;
- tout futur document décrivant les règles métier, les formats d'import/export ou les conventions de nommage.

## Cas imposant une mise à jour documentaire

La documentation doit être mise à jour lorsqu'une modification concerne :

- une table ;
- un champ ;
- une relation entre tables ;
- un type ou une destination de lien portée par `Etat` ou `Transition` ;
- une règle de transition ;
- une règle de validation ;
- un format Mermaid généré ;
- une convention d'identifiant ;
- un format de contenu comme Markdown, HTML ou texte brut ;
- une sortie destinée à MediaWiki.
- une page HTML ou la structure du site statique.
- un manifeste ou une entrée du catalogue de workflows.
- une exigence, son implémentation ou sa couverture de test.

## Règles de contribution

Chaque contribution doit préciser :

1. l'objectif de la modification ;
2. les tables ou champs impactés ;
3. les effets attendus sur les diagrammes Mermaid ;
4. les documents mis à jour ;
5. les limites connues ou points restant à traiter.

## Revue de pull request

Avant fusion, vérifier que :

- les nouveaux champs sont documentés ;
- les exemples Mermaid restent cohérents ;
- les identifiants utilisés dans les exemples sont compatibles Mermaid ;
- les contenus Markdown, HTML ou texte brut sont clairement typés ;
- les impacts sur MediaWiki sont explicités si nécessaire.
- les fichiers de données sont compatibles avec `schema/workflow-model.json` ;
- les contenus HTML issus des données sont filtrés avant publication ;
- les liens de navigation du site statique sont couverts par les tests ;
- les liens `page_phase`, `page_etat` et `url` respectent leur format ;
- la matrice relie chaque exigence au code et aux deux niveaux de test ;
- les tests automatisés de compatibilité et de génération réussissent.

## Vérifications avant contribution

Depuis la racine du projet :

```powershell
py scripts/validate_workflow_data.py `
  data/workflows/projet-informatique/manifest.json
py scripts/validate_traceability.py
py -m unittest discover -s tests -v
```

## Convention de nommage

Les identifiants internes doivent être stables, courts et compatibles avec Mermaid.

Exemples recommandés :

```text
A_qualifier
En_instruction
A_valider
En_correction
Clos
```

Exemples à éviter :

```text
À qualifier
En instruction
Etat à valider !
```

Les libellés lisibles par les utilisateurs doivent rester dans les champs `nom`, `libelle` ou `description`.
