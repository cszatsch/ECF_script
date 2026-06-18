# Outils CSV — Fiches fiscales partenaires

> Ce dépôt réunit **deux outils** dans **une seule application web**
> (`app.py`, port 5000) avec une page d'accueil :
> 1. **Convertisseur** — pivote un export de fiches fiscales (ci-dessous) ;
> 2. **Jointure `four_march`** — fusionne trois exports sur la clé `PARTNER`
>    (voir plus bas).
>
> Lancez `python app.py`, ouvrez <http://127.0.0.1:5000>, puis choisissez
> l'outil. Les deux logiques restent réutilisables séparément
> (`converter.py`, `four_march_join.py`).

## Convertisseur CSV

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

Le code de la colonne `Catégorie` a la forme `[xx][n]` : deux lettres (code
pays, ex. `FR`) suivies d'un chiffre. **Seul le dernier caractère** détermine
la colonne de destination, **quel que soit le pays** :

| Dernier caractère          | Exemples            | Colonne de sortie  |
|----------------------------|---------------------|--------------------|
| `1`                        | `FR1`, `DE1`        | `SIRET_xx1`        |
| `2`                        | `FR2`, `DE2`        | `SIREN_xx2`        |
| `0` **ou tout autre** (3, 4, 5…) | `FR0`, `FR3`, `FR4` | `TVA intracom_xx0` (par défaut) |

**Colonne par défaut.** Tout code ne se terminant pas par `1` ou `2` (donc
`0`, `3`, `4`, `5`…) alimente `TVA intracom_xx0`.

**Priorité en cas de valeurs multiples.** Si un même partenaire possède
plusieurs codes pointant vers `TVA intracom_xx0` (ex. `FR0` **et** `FR3`), la
valeur du code se terminant par `0` est retenue ; les autres sont ignorées. À
défaut de code se terminant par `0`, la première valeur rencontrée est gardée.

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
  vide). Aucune colonne supplémentaire n'est créée : tout code non rattaché à
  SIRET (1) ou SIREN (2) tombe dans la colonne par défaut `TVA intracom_xx0`.

## Installation

Nécessite Python 3.9+.

```bash
pip install -r requirements.txt
```

## Utilisation — application web

```bash
python app.py
```

Puis ouvrir <http://127.0.0.1:5000>, cliquer sur **Convertisseur**, déposer le
fichier CSV et télécharger le résultat (`<nom>_converti.csv`).

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

## Jointure des fournisseurs (`four_march`)

Application web qui **fusionne trois exports CSV** sur la clé `PARTNER` :

| Fichier      | Table SAP                | Rôle                                        |
|--------------|--------------------------|---------------------------------------------|
| FOURNISSEUR  | BUT000                   | table de base (left join) — tous les partenaires |
| TVA          | DFKKBPTAXNUM (converti)  | colonnes TVA intracom / SIRET / SIREN       |
| ZGESS1       | BUT0ID                   | colonnes TYPE / IDNUMBER                     |

On conserve **tous les partenaires de FOURNISSEUR** et on ajoute les colonnes
des deux autres fichiers quand le `PARTNER` correspond (cellules vides sinon).

Dans l'application (`python app.py`, <http://127.0.0.1:5000>), cliquer sur
**Jointure four_march**, déposer les trois fichiers et télécharger
`four_march_resultat.csv`. Un jeu d'exemple est fourni dans
`examples/four_march/`.

Détails gérés automatiquement :

- **Double en-tête** des exports SAP (noms techniques + libellés français) : la
  2ᵉ ligne est détectée, ignorée comme donnée, et reproduite en sortie.
- **Clé alphanumérique** acceptée (ex. `BP001B`, `BPC001`).
- **Doublons** de `PARTNER` : la première occurrence est conservée.
- Séparateur (`;` ou tabulation) et encodage détectés ; sortie UTF-8 (BOM),
  séparateur `;`.

## Tests

```bash
pip install pytest
pytest
```

## Structure

```
ECF_script/
├── app.py                  # Application web Flask unifiée (accueil + 2 outils)
├── converter.py            # Convertisseur — logique de conversion + CLI
├── four_march_join.py      # Jointure — logique de jointure
├── templates/
│   ├── home.html           # Page d'accueil (choix de l'outil)
│   ├── index.html          # Frontend du convertisseur
│   └── four_march.html     # Frontend de la jointure
├── static/style.css        # Styles (communs)
├── examples/               # Fichiers CSV d'exemple (dont examples/four_march/)
├── tests/                  # Tests (pytest)
├── requirements.txt
└── README.md
```
