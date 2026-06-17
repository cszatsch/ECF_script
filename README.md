# Convertisseur CSV — Fiches fiscales partenaires

Outil qui **pivote** un fichier CSV de fiches fiscales : le fichier d'entrée a
une ligne par couple *(Partenaire, Catégorie)*, le fichier de sortie regroupe
**une ligne par partenaire** avec **une colonne par catégorie** (en-têtes
renommées).

Il se présente sous deux formes partageant la même logique :

- une **application web** (frontend HTML + backend Flask) : on dépose un CSV et
  on télécharge le résultat ;
- un **script en ligne de commande** pour automatiser.

## Transformation

### Entrée

| Partenaire | Catégorie | Nº ID fiscale |
|------------|-----------|---------------|
| 20000068   | FR0       | FR55389036427 |
| 20000068   | FR1       | 3,89036E+13   |
| 20000068   | FR2       | 389036427     |
| 20000069   | FR0       | FR44352689327 |
| 20000069   | FR1       | 3,52689E+13   |
| 20000069   | FR2       | 352689327     |

### Sortie

| Partenaire | FR0 - TVA intracom | FR1 - SIRET | FR2 - SIREN |
|------------|--------------------|-------------|-------------|
| 20000068   | FR55389036427      | 3,89036E+13 | 389036427   |
| 20000069   | FR44352689327      | 3,52689E+13 | 352689327   |

Correspondance des catégories appliquée par défaut :

| Catégorie | Colonne de sortie    |
|-----------|----------------------|
| `FR0`     | `FR0 - TVA intracom` |
| `FR1`     | `FR1 - SIRET`        |
| `FR2`     | `FR2 - SIREN`        |

## Particularités

- **Séparateur détecté automatiquement** : `;` (par défaut Excel FR) ou
  tabulation. La sortie utilise le même séparateur que l'entrée.
- **Encodage détecté automatiquement** à la lecture (`utf-8`, `utf-8-sig`,
  `cp1252`, `latin-1`). La sortie est en **UTF-8 avec BOM**, pour que les
  accents s'affichent correctement dans Excel.
- **Valeurs préservées telles quelles** : une valeur comme `3,89036E+13`
  (virgule décimale) n'est jamais reconvertie ni reformatée.
- **En-têtes reconnus de façon souple** (insensible à la casse / aux accents),
  avec repli sur l'ordre des colonnes (Partenaire, Catégorie, Nº ID fiscale).
- **Schéma de sortie stable** : les trois colonnes FR0/FR1/FR2 sont toujours
  présentes même si une valeur manque (cellule laissée vide).

## Installation

Nécessite Python 3.9+.

```bash
pip install -r requirements.txt
```

## Utilisation — application web

```bash
python app.py
```

Puis ouvrir <http://127.0.0.1:5000>, déposer le fichier CSV et télécharger le
résultat (`<nom>_converti.csv`).

## Utilisation — ligne de commande

```bash
python converter.py examples/entree_exemple.csv sortie.csv
```

## Utilisation — bibliothèque

```python
from converter import convert, convert_bytes

texte_sortie = convert(texte_entree)          # str  -> str
octets_sortie = convert_bytes(octets_entree)  # bytes -> bytes (UTF-8 + BOM)
```

## Adapter les catégories / libellés

Modifiez le dictionnaire `DEFAULT_CATEGORY_LABELS` dans `converter.py`. L'ordre
des clés fixe l'ordre des colonnes de sortie. Toute catégorie présente dans le
fichier mais absente du dictionnaire est ajoutée en fin, sous son nom brut.

## Tests

```bash
pip install pytest
pytest
```

## Structure

```
ECF_script/
├── app.py                 # Application web Flask (backend + routes)
├── converter.py           # Logique de conversion + CLI
├── templates/index.html   # Frontend (page d'upload)
├── static/style.css       # Styles
├── examples/              # Fichier CSV d'exemple
├── tests/                 # Tests (pytest)
├── requirements.txt
└── README.md
```
