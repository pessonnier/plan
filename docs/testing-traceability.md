# Tests et traçabilité

Le projet applique une traçabilité bidirectionnelle entre les spécifications,
le code et les tests.

## Identifiants d'exigence

Les exigences sont définies dans `docs/specifications.md` avec un identifiant
stable au format :

```text
REQ-<DOMAINE>-<NUMERO>
```

Exemples :

```text
REQ-DATA-001
REQ-MERMAID-001
REQ-SITE-001
```

Un identifiant supprimé ou renommé constitue une modification de
spécification. La matrice et les tests concernés doivent être mis à jour dans
la même contribution.

## Matrice de traçabilité

`traceability/requirements.json` relie chaque exigence à :

- son document de spécification ;
- une ou plusieurs fonctions ou classes d'implémentation ;
- un ou plusieurs tests unitaires ;
- un ou plusieurs tests fonctionnels.

Une référence Python utilise le format :

```text
chemin/du/fichier.py::Classe.methode
chemin/du/fichier.py::fonction
```

Le script `scripts/validate_traceability.py` analyse les fichiers Python avec
leur arbre syntaxique. Il vérifie que :

- chaque identifiant est unique et présent dans le document indiqué ;
- chaque exigence référence du code, un test unitaire et un test fonctionnel ;
- tous les fichiers et symboles référencés existent.

Commande :

```powershell
py scripts/validate_traceability.py
```

## Tests unitaires

Les tests unitaires sont placés directement dans `tests/`. Ils vérifient les
fonctions Python sans lancer une commande externe, notamment :

- validation du modèle et des références ;
- règles de génération Mermaid ;
- filtrage du HTML ;
- structure et liens des pages générées ;
- cohérence de la matrice de traçabilité.

## Tests fonctionnels

Les tests fonctionnels sont placés dans `tests/functional/`. Ils exécutent les
scripts avec un interpréteur Python séparé et vérifient les résultats visibles :

- code retour et messages des commandes ;
- création des fichiers et répertoires ;
- présence des diagrammes et descriptions ;
- navigation du site ;
- filtrage de données HTML dangereuses ;
- validation de la matrice.

Ils fixent l'encodage des sous-processus à UTF-8 pour produire les mêmes
résultats sous Windows et Linux.

## Exécution

Suite complète :

```powershell
py -m unittest discover -s tests -v
```

Tests fonctionnels uniquement :

```powershell
py -m unittest discover -s tests/functional -v
```

Traçabilité uniquement :

```powershell
py scripts/validate_traceability.py
```

## Règle de contribution

Toute nouvelle exigence doit être ajoutée simultanément :

1. dans `docs/specifications.md` ;
2. dans `traceability/requirements.json` ;
3. dans le code ;
4. dans au moins un test unitaire ;
5. dans au moins un test fonctionnel.

Une modification n'est pas complète si la traçabilité ou une catégorie de
tests échoue.
