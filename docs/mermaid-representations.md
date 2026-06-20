# Représentations Mermaid

Cette page montre comment les données du modèle peuvent être transformées en diagrammes Mermaid.

Deux représentations sont prévues :

- `flowchart` pour représenter le cheminement global d'un processus ;
- `stateDiagram-v2` pour représenter les états et transitions d'un objet suivi.

## Représentation en graphe de processus

Le graphe de processus est utile pour expliquer le circuit général d'un workflow à des utilisateurs métier.

```mermaid
flowchart TD
    A_qualifier[À qualifier]
    En_instruction[En instruction]
    A_valider[À valider]
    En_correction[En correction]
    Clos[Clos]

    A_qualifier -->|dossier complet| En_instruction
    A_qualifier -->|dossier incomplet| En_correction
    En_instruction -->|conforme| A_valider
    A_valider -->|accepté| Clos
    A_valider -->|refusé| En_correction
    En_correction -->|corrigé| En_instruction
```

## Représentation en diagramme d'états

Le diagramme d'états est utile pour vérifier la cohérence du cycle de vie d'un objet suivi.

```mermaid
stateDiagram-v2
    [*] --> A_qualifier
    A_qualifier --> En_instruction : dossier complet
    A_qualifier --> En_correction : dossier incomplet
    En_instruction --> A_valider : conforme
    A_valider --> Clos : accepté
    A_valider --> En_correction : refusé
    En_correction --> En_instruction : corrigé
    Clos --> [*]
```

## Règle de génération d'un `flowchart`

Chaque état devient un noeud Mermaid.

Exemple :

```text
Etat.etat_id = A_qualifier
Etat.nom = À qualifier
```

Résultat :

```mermaid
flowchart TD
    A_qualifier[À qualifier]
```

Chaque transition devient une flèche.

Exemple :

```text
Transition.etat_source_id = A_qualifier
Transition.etat_cible_id = En_instruction
Transition.libelle = dossier complet
```

Résultat :

```mermaid
flowchart TD
    A_qualifier -->|dossier complet| En_instruction
```

## Règle de génération d'un `stateDiagram-v2`

Les états de type `initial` doivent être reliés depuis `[*]`.

```mermaid
stateDiagram-v2
    [*] --> A_qualifier
```

Les états de type `final` doivent pouvoir pointer vers `[*]`.

```mermaid
stateDiagram-v2
    Clos --> [*]
```

Les transitions normales sont représentées par une flèche avec libellé.

```mermaid
stateDiagram-v2
    En_instruction --> A_valider : conforme
```

## Utilisation dans MediaWiki

Une page MediaWiki peut intégrer le code Mermaid généré afin de documenter visuellement le workflow.

Exemple de bloc à publier :

````text
```mermaid
stateDiagram-v2
    [*] --> A_qualifier
    A_qualifier --> En_instruction : dossier complet
    En_instruction --> A_valider : conforme
    A_valider --> Clos : accepté
    Clos --> [*]
```
````

## Bonnes pratiques

- Utiliser des identifiants Mermaid sans espaces ni accents.
- Conserver les libellés métier dans le champ `nom` ou `libelle`.
- Générer uniquement les transitions actives dans les vues destinées aux utilisateurs.
- Vérifier que chaque état final est atteignable.
- Vérifier qu'aucun état normal n'est isolé.
- Documenter les conditions et rôles associés aux transitions.
