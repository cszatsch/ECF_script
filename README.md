# Convertisseur CSV — Fiches fiscales partenaires

Outil qui **pivote** un fichier CSV de fiches fiscales : le fichier d'entrée a
une ligne par couple *(Partenaire, Catégorie)*, le fichier de sortie regroupe
**une ligne par partenaire** avec **une colonne par type d'identifiant**.

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

| Partenaire | TVA intracom_xx0 | SIRET_xx1   | SIREN_xx2 |
|------------|------------------|-------------|-----------|
| 20000068   | FR55389036427    | 3,89036E+13 | 389036427 |
| 20000069   | FR44352689327    | 3,52689E+13 | 352689327 |

### Règle de routage

Le code de la colonne `Catégorie` a toujours la forme `[xx][n]` : deux lettres
(code pays, ex. `FR`) suivies d'un chiffre. **Seul le dernier chiffre**
détermine la colonne de destination, **quel que soit le pays** :

| Dernier caractère | Exemples     | Colonne de sortie  |
|-------------------|--------------|--------------------|
| `0`               | `FR0`, `DE0` | `TVA intracom_xx0` |
| `1`               | `FR1`, `DE1` | `SIRET_xx1`        |
| `2`               | `FR2`, `DE2` | `SIREN_xx2`        |

> Le `xx` des en-têtes est littéral (placeholder du code pays) : la colonne est
> commune à tous les pays.

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
- **Schéma de sortie stable** : les trois colonnes sont toujours présentes,
  même si un partenaire ne possède qu'une partie des valeurs (cellule laissée
  vide). Un code au format inattendu (ne se terminant pas par 0/1/2) n'est pas
  perdu : il reçoit sa propre colonne ajoutée en fin.

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

## Adapter les libellés de colonnes

Modifiez le dictionnaire `DEFAULT_COLUMN_LABELS` dans `converter.py`. Il associe
le **dernier caractère** du code catégorie au libellé de colonne ; l'ordre des
clés fixe l'ordre des colonnes de sortie.

```python
DEFAULT_COLUMN_LABELS = {
    "0": "TVA intracom_xx0",
    "1": "SIRET_xx1",
    "2": "SIREN_xx2",
}
```

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
