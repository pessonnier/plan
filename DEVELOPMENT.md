# Directives de développement

Ce projet vise à modéliser des workflows de suivi, à produire des représentations Mermaid et à documenter les règles associées.

## Principe général

Toute évolution du modèle de données, des règles de workflow ou de la génération Mermaid doit être accompagnée d'une mise à jour de la documentation.

Le maintien de la documentation est obligatoire.

## Documentation obligatoire

Une pull request ne doit pas être considérée comme complète si elle modifie le comportement ou la structure du projet sans mettre à jour les documents concernés.

Les documents à maintenir sont notamment :

- `docs/database-structure.md` pour la structure de la base de données ;
- `docs/mermaid-representations.md` pour les diagrammes Mermaid ;
- tout futur document décrivant les règles métier, les formats d'import/export ou les conventions de nommage.

## Cas imposant une mise à jour documentaire

La documentation doit être mise à jour lorsqu'une modification concerne :

- une table ;
- un champ ;
- une relation entre tables ;
- une règle de transition ;
- une règle de validation ;
- un format Mermaid généré ;
- une convention d'identifiant ;
- un format de contenu comme Markdown, HTML ou texte brut ;
- une sortie destinée à MediaWiki.

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
