"""A Library built on the real recipe object, not on a convenient one.

Thirty-five fields, seven of them undocumented anywhere, and the free-text twins
left as ``null`` rather than dropped — because a field a fixture omits is a field
no test can notice a write dropping.

The category tree here is three levels deep with several roots, which is the
shape of the reference account rather than a flat list.
"""

from __future__ import annotations

import hashlib
from typing import Any

CATEGORY_TREE: list[dict[str, Any]] = [
    # Roots
    {"uid": "CAT-MAINS", "name": "Main Dishes", "parent_uid": None, "order_flag": 0},
    {"uid": "CAT-BAKING", "name": "Baking", "parent_uid": None, "order_flag": 1},
    # Second level
    {
        "uid": "CAT-POULTRY",
        "name": "Poultry",
        "parent_uid": "CAT-MAINS",
        "order_flag": 0,
    },
    {
        "uid": "CAT-SEAFOOD",
        "name": "Seafood",
        "parent_uid": "CAT-MAINS",
        "order_flag": 1,
    },
    {
        "uid": "CAT-BREAD",
        "name": "Bread",
        "parent_uid": "CAT-BAKING",
        "order_flag": 0,
    },
    # Third level
    {
        "uid": "CAT-ROAST",
        "name": "Roasts",
        "parent_uid": "CAT-POULTRY",
        "order_flag": 0,
    },
    {
        "uid": "CAT-SOURDOUGH",
        "name": "Sourdough",
        "parent_uid": "CAT-BREAD",
        "order_flag": 0,
    },
]


def sync_hash(seed: str) -> str:
    """Return a well-formed 64-hex sync token.

    The server's own value is an opaque random change token that cannot be
    recomputed client-side. What matters on the wire is only that it is 64 hex
    characters, which this is.

    Args:
        seed: Anything stable, so a fixture is reproducible.

    Returns:
        str: Sixty-four hex characters.
    """
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def make_recipe(
    uid: str,
    name: str,
    *,
    categories: list[str] | None = None,
    rating: int = 0,
    total_time: str = "",
    ingredients: str = "1 thing\n2 other things",
    **overrides: Any,
) -> dict[str, Any]:
    """Build one full recipe object, every field present.

    Args:
        uid: The recipe's uid. Uppercase UUID4 in real data.
        name: Its title.
        categories: Category **uids**, never names.
        rating: Zero to five.
        total_time: Free text, exactly as Paprika stores it.
        ingredients: One per line, newline-separated. Not a list.
        **overrides: Any field to set differently.

    Returns:
        dict[str, Any]: The recipe, with all thirty-five fields.
    """
    recipe: dict[str, Any] = {
        "uid": uid,
        "name": name,
        "ingredients": ingredients,
        "directions": "Do the first thing.\n\nThen the second.",
        "description": None,
        "notes": "",
        "nutritional_info": "",
        "servings": "4",
        "difficulty": "",
        "prep_time": "10 min",
        "cook_time": "25 min",
        "total_time": total_time,
        "rating": rating,
        "categories": list(categories or []),
        "source": "",
        "source_url": "",
        "image_url": "",
        # The three photo fields are null, never "", when there is no photo.
        "photo": None,
        "photo_hash": None,
        "photo_large": None,
        # Read-only, minted fresh on every fetch and expiring within hours.
        "photo_url": None,
        "hash": sync_hash(uid),
        "created": "2024-03-11 18:02:44",
        "on_favorites": False,
        "on_grocery_list": None,
        "in_trash": False,
        "is_pinned": False,
        "scale": None,
        # The seven undocumented fields. Currently null in live data and
        # therefore the easiest thing in the world to drop by accident.
        "cook_minutes": None,
        "prep_minutes": None,
        "total_minutes": None,
        "servings_min": None,
        "servings_max": None,
        "cookbook_uid": None,
        "metadata_version": None,
    }
    recipe.update(overrides)
    return recipe


def build_library() -> list[dict[str, Any]]:
    """Build a small Library that exercises the shapes the index has to render.

    Returns:
        list[dict[str, Any]]: Recipes: rated and unrated, timed and untimed,
            categorised at every level of the tree and not categorised at all.
    """
    return [
        make_recipe(
            "8F2A1C4E-11D3-4A1B-9C3D-1A2B3C4D5E6F",
            "Roast Lemon Chicken",
            categories=["CAT-ROAST", "CAT-POULTRY"],
            rating=4,
            total_time="1 hr 10 min",
        ),
        make_recipe(
            "B7E14A02-22C9-4E8F-A10B-9F3E2D1C4B5A",
            "Weeknight Sourdough",
            categories=["CAT-SOURDOUGH"],
            rating=5,
            total_time="35",
        ),
        make_recipe(
            "3C9D5E71-33AB-4C2D-8E7F-6A5B4C3D2E1F",
            "Seared Cod with Capers",
            categories=["CAT-SEAFOOD"],
            rating=0,
            total_time="20 min",
        ),
        make_recipe(
            "D41F8A63-44BE-4F1A-B2C8-7D6E5F4A3B2C",
            "Aunt Ruth's Casserole",
            categories=[],
            rating=0,
            total_time="",
        ),
        # She trashed this one. It is still on the wire and still readable —
        # `in_trash` is not removal — but it is no longer in her Library.
        make_recipe(
            "6A2B9C08-55DF-4A3E-91C7-8B7A6C5D4E3F",
            "The One She Threw Out",
            categories=["CAT-MAINS"],
            in_trash=True,
        ),
    ]


#: How many of :func:`build_library`'s recipes are still in her Library.
LIBRARY_SIZE = 4


#: Slot numbers, as Paprika stores them.
BREAKFAST, LUNCH, DINNER, SNACK = 0, 1, 2, 3


def make_meal(
    uid: str,
    date: str,
    name: str,
    *,
    meal_type: int = DINNER,
    recipe_uid: str | None = None,
) -> dict[str, Any]:
    """Build one meal-plan entry, every field present.

    Args:
        uid: Its identifier. Uppercase UUID4 in real data, client-minted.
        date: ``YYYY-MM-DD``; Paprika stores a space-separated time with it.
        name: What it says on the plan.
        meal_type: Which slot.
        recipe_uid: The recipe, or ``None`` for a free-text meal — which is a
            real case, not an edge one.

    Returns:
        dict[str, Any]: The meal.
    """
    return {
        "uid": uid,
        "recipe_uid": recipe_uid,
        "date": f"{date} 00:00:00",
        "type": meal_type,
        "name": name,
        "order_flag": 0,
        # An empty string is accepted here, and is what a client that has not
        # read her meal types should send.
        "type_uid": "",
        "scale": None,
        "is_ingredient": False,
    }


def build_plan() -> list[dict[str, Any]]:
    """Build a short Plan, including a meal that is not a recipe.

    Returns:
        list[dict[str, Any]]: The meals.
    """
    library = build_library()
    return [
        make_meal(
            "11111111-0001-4A1B-9C3D-1A2B3C4D5E6F",
            "2026-08-24",
            "Roast Lemon Chicken",
            recipe_uid=library[0]["uid"],
        ),
        make_meal(
            "11111111-0002-4A1B-9C3D-1A2B3C4D5E6F",
            "2026-08-25",
            "Leftovers",
        ),
    ]


#: Her own aisles, which is where an ingredient's filing comes from.
GROCERY_AISLES: list[dict[str, Any]] = [
    {"uid": "AISLE-CANNED", "name": "Canned Goods", "order_flag": 0},
    {"uid": "AISLE-PRODUCE", "name": "Produce", "order_flag": 1},
]

#: Her account's ingredient-to-aisle table. An ingredient absent from it has no
#: aisle, which is a degraded entry rather than a blocked write.
GROCERY_INGREDIENTS: list[dict[str, Any]] = [
    {"uid": "GI-1", "name": "black beans", "aisle_uid": "AISLE-CANNED"},
    {"uid": "GI-2", "name": "onions", "aisle_uid": "AISLE-PRODUCE"},
]


def make_pantry_item(
    uid: str, ingredient: str, *, aisle: str = "", in_stock: bool = True
) -> dict[str, Any]:
    """Build one pantry item, in the shape a live account returns.

    Note what is *not* here: no `name`, because a pantry item has none.

    Args:
        uid: Its identifier.
        ingredient: What it is.
        aisle: Where her account files it.
        in_stock: Whether she has it.

    Returns:
        dict[str, Any]: The item.
    """
    return {
        "uid": uid,
        "ingredient": ingredient,
        "aisle": aisle,
        "aisle_uid": "",
        "quantity": "",
        "in_stock": in_stock,
        "has_expiration": False,
        "expiration_date": None,
        "purchase_date": "2026-08-01 00:00:00",
    }


def build_pantry() -> list[dict[str, Any]]:
    """Build a short Pantry, including something she has run out of.

    Returns:
        list[dict[str, Any]]: The items.
    """
    return [
        make_pantry_item("PANTRY-1", "cumin", aisle="Spices"),
        make_pantry_item("PANTRY-2", "rice", aisle="Dry Goods"),
        make_pantry_item("PANTRY-3", "soy sauce", aisle="Sauces", in_stock=False),
    ]


#: Her shopping lists. `list_uid` is required on every grocery item, so this is
#: not optional furniture.
GROCERY_LISTS: list[dict[str, Any]] = [
    {"uid": "LIST-1", "name": "Groceries", "order_flag": 0, "is_default": True},
    {"uid": "LIST-2", "name": "Hardware", "order_flag": 1, "is_default": False},
]
