ANALYZE_FOOD_PHOTO = {
    "name": "analyze_food_photo",
    "description": (
        "Identify food in a photograph using FatSecret Image Recognition and return "
        "ranked candidates with nutrition data. This tool performs NO writes. "
        "After calling it, present the candidates (food name, serving description, "
        "calories) to the user and ask them to confirm the specific food and serving "
        "size before anything is logged. If the image path is not known, ask the user "
        "to share the photo first."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "image_path": {
                "type": "string",
                "description": (
                    "Absolute file path to the food photograph. "
                    "When the user sends a photo, pass the file path from the "
                    "session context (e.g. /tmp/hermes/photo_abc.jpg). "
                    "Alternatively, provide an HTTP/HTTPS URL."
                ),
            },
            "region": {
                "type": "string",
                "description": "Two-letter region code for localised food data (default: US).",
                "default": "US",
            },
            "language": {
                "type": "string",
                "description": "Language code for result names (default: en).",
                "default": "en",
            },
            "meal_hint": {
                "type": "string",
                "description": (
                    "Optional hint about the meal type to include in the response "
                    "(breakfast, lunch, dinner, other). Used only for display; "
                    "actual meal is confirmed before logging."
                ),
            },
        },
        "required": ["image_path"],
    },
}

SEARCH_FOOD = {
    "name": "search_food",
    "description": (
        "Search the FatSecret food database by name. Use this when the user corrects "
        "or overrides an image-recognition result ('that's focaccia, not pizza'), or "
        "when no photo is available. Returns candidates in the same format as "
        "analyze_food_photo — present them to the user to pick one before logging."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Food name or description to search for (e.g. 'focaccia bread').",
            },
            "region": {
                "type": "string",
                "description": "Two-letter region code (default: US).",
                "default": "US",
            },
            "language": {
                "type": "string",
                "description": "Language code (default: en).",
                "default": "en",
            },
        },
        "required": ["query"],
    },
}

LOG_FOOD_ENTRY = {
    "name": "log_food_entry",
    "description": (
        "Write a food entry to the user's FatSecret diary. "
        "IMPORTANT: Only call this tool AFTER the user has explicitly confirmed "
        "the specific food, serving size, and quantity from a prior "
        "analyze_food_photo or search_food result. Never call speculatively or "
        "before confirmation. This is the only tool that writes to the diary."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "food_id": {
                "type": "string",
                "description": "The food_id from the analyze_food_photo or search_food result.",
            },
            "serving_id": {
                "type": "string",
                "description": "The serving_id the user selected.",
            },
            "quantity": {
                "type": "number",
                "description": "Number of servings (e.g. 1.5 for one-and-a-half portions).",
            },
            "meal": {
                "type": "string",
                "enum": ["breakfast", "lunch", "dinner", "other"],
                "description": (
                    "Meal to log to. Default: infer from current time "
                    "(breakfast before 11 am, lunch 11 am–3 pm, dinner after 3 pm)."
                ),
            },
            "food_entry_name": {
                "type": "string",
                "description": (
                    "Human-readable label for the diary entry "
                    "(e.g. 'Margherita Pizza, 1 slice'). "
                    "Use the food_name from the candidate plus the serving description."
                ),
            },
            "date": {
                "type": "string",
                "description": "ISO 8601 date (YYYY-MM-DD). Defaults to today.",
                "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
            },
        },
        "required": ["food_id", "serving_id", "quantity", "meal", "food_entry_name"],
    },
}
