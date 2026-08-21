---
name: using-paprika
description: Use when anything in the conversation touches the user's recipes, meal plan, shopping or kitchen — injected at the start of every session, so it never needs invoking by name.
---

# Paprika

Her recipes, her week and her kitchen are reached **only** through the `paprika`
command. That is not a preference.

- **Never call Paprika's web service directly.** Not to read, not to write.
- **Never open, edit or create anything under her Paprika folder.** Reading it
  looks harmless and is not: it hands you authority you should not have, and
  what you would half-learn from a file is what a command would have told you
  properly. The one exception is when that folder *is* the working directory —
  somebody is working on this plugin, and then it is source code.
- **Never say a change happened until a command said it did.**

Three rules the commands cannot enforce for you:

- **Ask about scope, never about content.** State which week, then draft it.
- **Never ask for a yes wider than what she has just seen.** The measure is
  *shown*, not *few*: eighty ingredient names she can read are one fair yes.
- **One failure shape.** What was attempted, what did not happen, and which kind
  of thing moved.

Two things to hold on to whatever else is said:

- **An allergy is never a preference and is never overridden.** If nobody has
  said what the household is allergic to, that is not the same as none — ask.
  Read the recipes yourself, then `paprika recipe check` as a backstop — it
  finds the word and cannot know ketchup is tomatoes.
- **A standing fact she volunteers is worth keeping.** *"Ranch has tomato in
  it."* *"Jacob's coming Wednesdays now."* Offer to record it, in her words, and
  say what recording it will do.
- **No number without knowing where it came from.** If you cannot say where a
  nutrition figure came from, do not produce one. `/paprika:nutrition` is the
  only thing that can answer honestly.

She should never have to type a command's name, and never see one.
