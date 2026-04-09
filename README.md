# yazio-cli

CLI pour le suivi nutritionnel Yazio, basé sur l'API non officielle reverse-engineered.

## Installation

```bash
cd ~/src/yazio-cli
uv sync
```

## Authentification

### Email / mot de passe (si tu en as un)

```bash
uv run yazio login
```

### Apple / Google Sign-In (pas de mot de passe Yazio)

Si tu t'es inscrit via "Sign in with Apple" ou Google, tu n'as pas de mot de passe Yazio. Il faut extraire le token depuis le site web :

1. Ouvre https://www.yazio.com/fr/app/account dans Firefox (ou Chrome)
2. Connecte-toi avec ton compte Apple/Google
3. Ouvre les DevTools : **F12** → onglet **Stockage** (Firefox) ou **Application** (Chrome)
4. Dans **Cookies** → `https://www.yazio.com`, copie la valeur du cookie `yz_session`
   - C'est une longue chaîne qui commence par `Fe26.2**...`
5. Lance la commande :

```bash
uv run yazio web-login --session-cookie 'Fe26.2**...'
```

Le CLI extrait les tokens API depuis la page web et les sauvegarde dans `~/.config/yazio/token.json`. Le refresh est automatique tant que le refresh token est valide.

Si le token expire et que le refresh échoue, il suffit de refaire l'étape ci-dessus.

## Commandes

```
yazio summary [DATE]       Résumé journalier (calories, macros, eau, pas)
yazio meals [DATE]         Détail des aliments consommés
yazio water [DATE]         Consommation d'eau
yazio goals [DATE]         Objectifs nutrition
yazio exercises [DATE]     Exercices du jour
yazio weight [--days N]    Historique de poids (30 jours par défaut)
yazio search <query>       Chercher un aliment dans la base Yazio
yazio add <ID> --amount N --meal breakfast|lunch|dinner|snack
                           Ajouter un aliment au journal
yazio remove <ID>          Supprimer une entrée
```

`DATE` est au format `YYYY-MM-DD`, par défaut aujourd'hui.

## API Python

Le module `yazio_cli.api` peut être importé directement :

```python
from yazio_cli import api

summary = api.daily_summary("2026-04-09")
items = api.consumed_items("2026-04-09")
results = api.search_products("poulet")
```

## Formats de retour (API)

Toutes les fonctions retournent des `dict` JSON (sauf `search_products` → `list[dict]` et `remove_consumed_item` → `None`).

### `daily_summary(date)`

```json
{
  "activity_energy": 492,
  "consume_activity_energy": true,
  "steps": 8132,
  "water_intake": 2000,
  "goals": {
    "energy.energy": 3064.7,
    "water": 2000,
    "activity.step": 10000,
    "nutrient.protein": 156.9,
    "nutrient.fat": 83.0,
    "nutrient.carb": 282.4,
    "bodyvalue.weight": 65
  },
  "units": {
    "unit_mass": "kg",
    "unit_energy": "kcal",
    "unit_serving": "g",
    "unit_length": "cm"
  },
  "meals": {
    "breakfast": {
      "energy_goal": 919.4,
      "nutrients": {
        "energy.energy": 727.1,
        "nutrient.carb": 68.2,
        "nutrient.fat": 33.2,
        "nutrient.protein": 33.6
      }
    },
    "lunch": { "energy_goal": 1225.9, "nutrients": { "..." : "..." } },
    "dinner": { "energy_goal": 766.2, "nutrients": { "..." : "..." } },
    "snack": { "energy_goal": 153.2, "nutrients": { "..." : "..." } }
  },
  "user": {
    "start_weight": 64.1,
    "current_weight": 64.5,
    "goal": "build_muscle",
    "sex": "male"
  },
  "active_fasting_countdown_template_key": null
}
```

### `consumed_items(date)`

Retourne 3 listes : `products`, `recipe_portions`, `simple_products`.

**`products[]`** — aliments de la base Yazio (pas de nutriments inline, il faut appeler `get_product`) :
```json
{
  "id": "45595f92-...",
  "date": "2026-04-09 13:18:40",
  "daytime": "breakfast",
  "type": "product",
  "product_id": "9d9b131a-...",
  "amount": 20,
  "serving": "tablespoon",
  "serving_quantity": 1
}
```

**`simple_products[]`** — aliments personnalisés/IA (nutriments inline, valeurs absolues) :
```json
{
  "id": "c32dbfc9-...",
  "date": "2026-04-09 13:19:11",
  "daytime": "lunch",
  "type": "simple_product",
  "name": "Bol de poulet grillé avec riz mélangé, avocat, maïs, poivron et laitue",
  "nutrients": {
    "energy.energy": 519,
    "nutrient.protein": 44,
    "nutrient.fat": 19,
    "nutrient.carb": 39
  },
  "is_ai_generated": true
}
```

### `get_product(product_id)`

Détail d'un produit. **Les nutriments sont par gramme** (multiplier par `amount` pour le total).

```json
{
  "name": "Filets de poulet",
  "is_verified": true,
  "category": "poultry",
  "producer": null,
  "base_unit": "g",
  "nutrients": {
    "energy.energy": 1.02,
    "nutrient.protein": 0.2355,
    "nutrient.fat": 0.007,
    "nutrient.carb": 0.0,
    "nutrient.sugar": 0.0,
    "nutrient.dietaryfiber": 0.0,
    "nutrient.saturated": 0.0021,
    "nutrient.sodium": 0.00066,
    "...": "vitamines, minéraux..."
  },
  "servings": [
    { "serving": "piece.medium", "amount": 125.0 },
    { "serving": "g", "amount": 100.0 }
  ],
  "language": "fr"
}
```

### `search_products(query)` → `list[dict]`

Retourne une liste de produits (max 50). Nutriments **par gramme**.

```json
[
  {
    "score": 110,
    "name": "Filets de poulet",
    "product_id": "9d7ca984-...",
    "serving": "piece.medium",
    "serving_quantity": 1,
    "amount": 125,
    "base_unit": "g",
    "producer": null,
    "is_verified": true,
    "nutrients": {
      "energy.energy": 1.02,
      "nutrient.carb": 0.0,
      "nutrient.fat": 0.007,
      "nutrient.protein": 0.2355
    },
    "language": "fr"
  }
]
```

### `water_intake(date)`

```json
{
  "water_intake": 2000.0,
  "gateway": null,
  "source": null
}
```

### `goals(date)`

```json
{
  "energy.energy": 2572.7,
  "nutrient.protein": 156.9,
  "nutrient.fat": 83.0,
  "nutrient.carb": 282.4,
  "water": 2000.0,
  "activity.step": 10000.0,
  "bodyvalue.weight": 65.0
}
```

### `exercises(date)`

```json
{
  "training": [
    {
      "id": "74f6b7de-...",
      "date": "2026-04-09 18:45:57",
      "name": "cycling",
      "energy": 321.0,
      "distance": 21047,
      "duration": 45,
      "gateway": "apple_health",
      "steps": 0
    }
  ],
  "custom_training": [
    {
      "id": "41bf4508-...",
      "date": "2026-04-09 11:57:02",
      "name": "Mes exercices personnalisés",
      "energy": 171.0,
      "duration": 66,
      "gateway": "apple_health",
      "steps": 0
    }
  ],
  "activity": {
    "energy": 0.0,
    "distance": 4756,
    "duration": 0,
    "gateway": "apple_health",
    "steps": 8132
  }
}
```

### `weight(start, end)` → `list[dict]`

```json
[
  { "date": "2026-03-08 09:04:02", "value": 63.4 },
  { "date": "2026-04-09 07:26:11", "value": 64.5 }
]
```

### `add_consumed_item(product_id, amount, date, meal)`

Ajoute un aliment. `meal` : `breakfast`, `lunch`, `dinner`, `snack`.

### `remove_consumed_item(item_id)`

Supprime une entrée (par `id` du consumed item, pas le `product_id`). Retourne `None`.

## Développement

```bash
uv run ruff check src/ tests/    # lint
uv run ruff format src/ tests/   # format
uv run mypy src/                 # types
uv run pytest -v                 # tests
```

## Notes

- API non officielle — peut cesser de fonctionner si Yazio modifie son backend
- Basé sur le travail de [juriadams/yazio](https://github.com/juriadams/yazio)
- Token stocké en clair dans `~/.config/yazio/token.json`
- Les nutriments des produits sont **par gramme** (pas pour 100g)
- Les nutriments des `simple_products` sont des **valeurs absolues** (pas par gramme)
