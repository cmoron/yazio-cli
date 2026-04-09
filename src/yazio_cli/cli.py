"""Yazio CLI — track nutrition from the terminal."""

from __future__ import annotations

from datetime import date as Date

import typer
from rich.console import Console
from rich.table import Table

from yazio_cli import api

app = typer.Typer(help="Yazio calorie tracking CLI", no_args_is_help=True)
console = Console()


def _today() -> str:
    return Date.today().isoformat()


@app.command()
def login(
    username: str = typer.Option(..., prompt=True, help="Yazio email"),
    password: str = typer.Option(..., prompt=True, hide_input=True, help="Yazio password"),
) -> None:
    """Authenticate with Yazio email/password and cache the token."""
    try:
        api.login(username, password)
        console.print("[green]Logged in successfully.[/green]")
    except api.AuthError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1) from None


@app.command("web-login")
def web_login(
    session_cookie: str = typer.Option(
        ..., prompt="yz_session cookie", help="yz_session cookie from yazio.com"
    ),
) -> None:
    """Login using yz_session cookie from yazio.com (for Apple/Google sign-in users)."""
    try:
        api.web_login(session_cookie)
        console.print("[green]Token extracted and saved.[/green]")
    except api.AuthError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1) from None


@app.command()
def summary(
    date: str = typer.Argument(default=None, help="Date (YYYY-MM-DD), defaults to today"),
) -> None:
    """Show daily nutrition summary."""
    date = date or _today()
    data = api.daily_summary(date)

    goals = data.get("goals", {})
    meals = data.get("meals", {})

    # Totals across meals
    total_cal = sum(m.get("nutrients", {}).get("energy.energy", 0) for m in meals.values())
    total_protein = sum(m.get("nutrients", {}).get("nutrient.protein", 0) for m in meals.values())
    total_fat = sum(m.get("nutrients", {}).get("nutrient.fat", 0) for m in meals.values())
    total_carbs = sum(m.get("nutrients", {}).get("nutrient.carb", 0) for m in meals.values())

    goal_cal = goals.get("energy.energy", 0)

    table = Table(title=f"Summary for {date}")
    table.add_column("", style="bold")
    table.add_column("Consumed", justify="right")
    table.add_column("Goal", justify="right", style="dim")
    table.add_column("%", justify="right")

    def pct(val: float, goal: float) -> str:
        return f"{val / goal * 100:.0f}%" if goal else "-"

    table.add_row(
        "Calories",
        f"{total_cal:.0f} kcal",
        f"{goal_cal:.0f} kcal",
        pct(total_cal, goal_cal),
    )
    table.add_row(
        "Protein",
        f"{total_protein:.1f} g",
        f"{goals.get('nutrient.protein', 0):.0f} g",
        pct(total_protein, goals.get("nutrient.protein", 0)),
    )
    table.add_row(
        "Fat",
        f"{total_fat:.1f} g",
        f"{goals.get('nutrient.fat', 0):.0f} g",
        pct(total_fat, goals.get("nutrient.fat", 0)),
    )
    table.add_row(
        "Carbs",
        f"{total_carbs:.1f} g",
        f"{goals.get('nutrient.carb', 0):.0f} g",
        pct(total_carbs, goals.get("nutrient.carb", 0)),
    )
    table.add_row(
        "Water",
        f"{data.get('water_intake', 0)} ml",
        f"{goals.get('water', 0):.0f} ml",
        pct(data.get("water_intake", 0), goals.get("water", 0)),
    )
    table.add_row(
        "Steps",
        f"{data.get('steps', 0)}",
        f"{goals.get('activity.step', 0):.0f}",
        pct(data.get("steps", 0), goals.get("activity.step", 0)),
    )

    console.print(table)

    # Per-meal breakdown
    meal_table = Table(title="Meals")
    meal_table.add_column("Meal", style="bold")
    meal_table.add_column("Calories", justify="right")
    meal_table.add_column("P", justify="right")
    meal_table.add_column("F", justify="right")
    meal_table.add_column("C", justify="right")

    for name in ("breakfast", "lunch", "dinner", "snack"):
        m = meals.get(name, {})
        n = m.get("nutrients", {})
        meal_table.add_row(
            name.capitalize(),
            f"{n.get('energy.energy', 0):.0f}",
            f"{n.get('nutrient.protein', 0):.1f}g",
            f"{n.get('nutrient.fat', 0):.1f}g",
            f"{n.get('nutrient.carb', 0):.1f}g",
        )

    console.print(meal_table)


def _resolve_item(item: api.JsonDict) -> api.JsonDict:
    """Resolve a consumed item to name + nutrients (per-amount, not per-gram)."""
    if item.get("type") == "simple_product":
        n = item.get("nutrients", {})
        return {
            "name": item.get("name", "?"),
            "daytime": item.get("daytime", "?"),
            "amount": item.get("amount", 0),
            "cal": n.get("energy.energy", 0),
            "protein": n.get("nutrient.protein", 0),
            "fat": n.get("nutrient.fat", 0),
            "carb": n.get("nutrient.carb", 0),
        }

    # Regular product — fetch details, nutrients are per-gram
    amount = item.get("amount", 0)
    product_id = item.get("product_id", "")
    try:
        product = api.get_product(product_id)
    except api.ApiError:
        return {
            "name": f"[unknown: {product_id[:8]}]",
            "daytime": item.get("daytime", "?"),
            "amount": amount,
            "cal": 0,
            "protein": 0,
            "fat": 0,
            "carb": 0,
        }

    n = product.get("nutrients", {})
    return {
        "name": product.get("name", "?"),
        "daytime": item.get("daytime", "?"),
        "amount": amount,
        "cal": n.get("energy.energy", 0) * amount,
        "protein": n.get("nutrient.protein", 0) * amount,
        "fat": n.get("nutrient.fat", 0) * amount,
        "carb": n.get("nutrient.carb", 0) * amount,
    }


@app.command()
def meals(
    date: str = typer.Argument(default=None, help="Date (YYYY-MM-DD), defaults to today"),
) -> None:
    """Show consumed items for a day."""
    date = date or _today()
    data = api.consumed_items(date)

    raw_items = (
        data.get("products", []) + data.get("recipe_portions", []) + data.get("simple_products", [])
    )
    if not raw_items:
        console.print(f"[dim]No items logged for {date}.[/dim]")
        return

    items = [_resolve_item(i) for i in raw_items]
    # Sort by meal order
    meal_order = {"breakfast": 0, "lunch": 1, "dinner": 2, "snack": 3}
    items.sort(key=lambda x: meal_order.get(x["daytime"], 9))

    table = Table(title=f"Meals for {date}")
    table.add_column("Meal", style="bold")
    table.add_column("Item")
    table.add_column("Amount", justify="right")
    table.add_column("Cal", justify="right")
    table.add_column("P", justify="right")
    table.add_column("F", justify="right")
    table.add_column("C", justify="right")

    for item in items:
        table.add_row(
            item["daytime"],
            item["name"],
            f"{item['amount']:.0f}g",
            f"{item['cal']:.0f}",
            f"{item['protein']:.1f}g",
            f"{item['fat']:.1f}g",
            f"{item['carb']:.1f}g",
        )

    console.print(table)


@app.command()
def water(
    date: str = typer.Argument(default=None, help="Date (YYYY-MM-DD), defaults to today"),
) -> None:
    """Show water intake for a day."""
    date = date or _today()
    data = api.water_intake(date)
    console.print(f"Water intake for {date}: [bold]{data.get('water_intake', 0)} ml[/bold]")


@app.command()
def weight(
    days: int = typer.Option(30, help="Number of days of history to show"),
) -> None:
    """Show weight history."""
    from datetime import timedelta

    end = Date.today()
    start = end - timedelta(days=days)
    data = api.weight(start.isoformat(), end.isoformat())
    if isinstance(data, list):
        entries: list[api.JsonDict] = data
    else:
        raw = data.get("items") or data.get("values") or [data]
        entries = raw if isinstance(raw, list) else [raw]

    table = Table(title="Weight History")
    table.add_column("Date", style="bold")
    table.add_column("Weight", justify="right")

    for entry in entries[-10:]:  # Last 10
        if isinstance(entry, dict):
            raw_date = entry.get("date", "?")
            w = entry.get("value", entry.get("weight", 0))
            table.add_row(raw_date[:10], f"{w:.1f} kg")

    console.print(table)


@app.command()
def goals(
    date: str = typer.Argument(default=None, help="Date (YYYY-MM-DD), defaults to today"),
) -> None:
    """Show nutrition goals."""
    date = date or _today()
    data = api.goals(date)

    table = Table(title=f"Goals for {date}")
    table.add_column("Goal", style="bold")
    table.add_column("Value", justify="right")

    labels = {
        "energy.energy": ("Calories", "kcal"),
        "nutrient.protein": ("Protein", "g"),
        "nutrient.fat": ("Fat", "g"),
        "nutrient.carb": ("Carbs", "g"),
        "water": ("Water", "ml"),
        "activity.step": ("Steps", ""),
        "bodyvalue.weight": ("Target weight", "kg"),
    }

    for key, (label, unit) in labels.items():
        val = data.get(key)
        if val is not None:
            table.add_row(label, f"{val} {unit}".strip())

    console.print(table)


@app.command()
def search(query: str = typer.Argument(..., help="Food to search for")) -> None:
    """Search the Yazio food database."""
    items = api.search_products(query)

    if not items:
        console.print("[dim]No results.[/dim]")
        return

    table = Table(title=f"Search: {query}")
    table.add_column("ID", style="dim")
    table.add_column("Name")
    table.add_column("Cal/100g", justify="right")
    table.add_column("P/100g", justify="right")
    table.add_column("F/100g", justify="right")
    table.add_column("C/100g", justify="right")

    for item in items[:15]:
        n = item.get("nutrients", {})
        # Nutrients are per-gram, multiply by 100 for per-100g display
        table.add_row(
            item.get("product_id", "?")[:12],
            item.get("name", "?"),
            f"{n.get('energy.energy', 0) * 100:.0f}",
            f"{n.get('nutrient.protein', 0) * 100:.1f}g",
            f"{n.get('nutrient.fat', 0) * 100:.1f}g",
            f"{n.get('nutrient.carb', 0) * 100:.1f}g",
        )

    console.print(table)


@app.command()
def add(
    product_id: str = typer.Argument(..., help="Product ID (from search)"),
    amount: float = typer.Option(..., help="Amount in grams"),
    meal: str = typer.Option(..., help="breakfast, lunch, dinner, or snack"),
    date: str = typer.Option(default=None, help="Date (YYYY-MM-DD), defaults to today"),
    serving_id: str = typer.Option(default=None, help="Serving ID (optional)"),
) -> None:
    """Add a food item to your diary."""
    date = date or _today()
    if meal not in ("breakfast", "lunch", "dinner", "snack"):
        console.print(f"[red]Invalid meal: {meal}. Use breakfast, lunch, dinner, or snack.[/red]")
        raise typer.Exit(1)
    api.add_consumed_item(product_id, amount, date, meal, serving_id)
    console.print(f"[green]Added {amount}g of {product_id} to {meal} on {date}.[/green]")


@app.command()
def remove(
    item_id: str = typer.Argument(..., help="Consumed item ID to remove"),
) -> None:
    """Remove a food item from your diary."""
    api.remove_consumed_item(item_id)
    console.print(f"[green]Removed item {item_id}.[/green]")


@app.command()
def exercises(
    date: str = typer.Argument(default=None, help="Date (YYYY-MM-DD), defaults to today"),
) -> None:
    """Show exercises for a day."""
    date = date or _today()
    data = api.exercises(date)

    all_exercises = data.get("training", []) + data.get("custom_training", [])
    if not all_exercises:
        console.print(f"[dim]No exercises for {date}.[/dim]")
        return

    table = Table(title=f"Exercises for {date}")
    table.add_column("Name", style="bold")
    table.add_column("Duration", justify="right")
    table.add_column("Calories", justify="right")
    table.add_column("Steps", justify="right")

    for ex in all_exercises:
        duration_min = ex.get("duration", 0) // 60
        table.add_row(
            ex.get("name", "?"),
            f"{duration_min} min",
            f"{ex.get('energy', 0):.0f} kcal",
            str(ex.get("steps", 0)),
        )

    console.print(table)
