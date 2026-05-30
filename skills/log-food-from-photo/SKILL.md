# Skill: log-food-from-photo

Use this workflow whenever the user shares a food photo and wants to log it.

## Steps

1. **Analyze the photo**
   Call `analyze_food_photo` with the image path from the session context.
   Never skip this step even if you think you recognise the food — the
   FatSecret Image Recognition result gives you the `food_id` and `serving_id`
   required to log.

2. **Present candidates**
   Show the top candidates in a short, readable list:
   - Food name (brand if available)
   - Serving description and calories per serving
   - Macros (protein / carbs / fat) if useful

   Example:
   > I see **Margherita Pizza** (Trader Joe's) — 1 slice (107 g), **272 kcal**
   > (protein 12 g · carbs 34 g · fat 10 g).
   > Is that right? Which serving size, and how many servings?

3. **Wait for explicit confirmation**
   Do NOT call `log_food_entry` until the user clearly confirms:
   - The correct food item
   - The serving size they want
   - The quantity (number of servings)
   - Optionally: the meal type and date (default to inferred values if not specified)

4. **Handle corrections**
   If the user says the recognition is wrong ("that's focaccia, not pizza"),
   call `search_food` with the corrected name, then present the new candidates
   and wait for confirmation again.

5. **Log the confirmed entry**
   Call `log_food_entry` with the confirmed `food_id`, `serving_id`, `quantity`,
   `meal`, and `food_entry_name`. Use today's date unless the user specifies otherwise.

6. **Confirm back**
   After a successful log, tell the user what was recorded:
   > Logged **Margherita Pizza, 1 slice** to *dinner* — 272 kcal ✓

## Multi-item meals

If the photo contains several foods (`analyze_food_photo` returns multiple
candidates), handle each item in turn:
- List all detected foods with their calories.
- Ask the user to confirm or correct each one.
- Call `log_food_entry` once per confirmed item.

## Guardrails

- Never call `log_food_entry` speculatively or before the user confirms.
- If the user says "just log it" without specifying a serving, pick the first
  suggested serving and state it explicitly before logging.
- If recognition fails (no candidates returned), fall back to `search_food`
  using your vision-model description of the meal.
