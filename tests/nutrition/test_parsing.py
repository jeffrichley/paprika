"""Reading an ingredient line, and the accounting for what we could not read.

The lines here are the edge cases the research doc ran against two parsers and a
commercial API. What is asserted is not the parser's cleverness — that is its
own project's problem — but that everything it sets aside comes back out, since
the failure mode is a line that quietly loses a word at high confidence.
"""

from __future__ import annotations

from paprika_core.nutrition.parsing import parse_line


def test_a_stated_mass_is_read_as_a_mass() -> None:
    parsed = parse_line("250 g plain flour")

    assert parsed.quantity == 250.0
    assert parsed.unit == "g"
    assert parsed.name == "plain flour"
    assert parsed.unaccounted == ()


def test_a_size_word_is_a_size_and_not_a_unit() -> None:
    """A size modifier has no fixed gram value, which is the point of the field."""
    parsed = parse_line("2 large yellow onions, diced")

    assert parsed.quantity == 2.0
    assert parsed.unit == ""
    assert parsed.size == "large"
    assert parsed.name == "yellow onions"
    assert "diced" in parsed.prep_words
    assert parsed.preparation == ()


def test_a_range_keeps_both_ends_and_says_it_was_a_range() -> None:
    """The archived tagger drops the upper bound and reports high confidence."""
    parsed = parse_line("2-3 cloves garlic, minced")

    assert parsed.is_range is True
    assert parsed.quantity == 2.5
    assert parsed.unit == "clove"


def test_a_per_container_mass_is_multiplied_by_the_count() -> None:
    parsed = parse_line("2 (14.5 oz) cans diced tomatoes")

    assert parsed.unit == "oz"
    assert parsed.quantity == 29.0
    assert parsed.container == "can"


def test_to_taste_is_a_fact_about_the_recipe_and_not_a_failure() -> None:
    parsed = parse_line("salt to taste")

    assert parsed.open_ended is True
    assert parsed.name == "salt"


def test_a_comment_comes_back_out_rather_than_being_dropped() -> None:
    """Zestful reported 0.903 confidence while discarding exactly this."""
    parsed = parse_line("2 tbsp butter, divided, plus more for greasing")

    assert parsed.quantity == 2.0
    assert parsed.unit == "tbsp"
    assert any("greasing" in word for word in parsed.unaccounted)


def test_an_alternative_food_is_kept_rather_than_misfiled() -> None:
    parsed = parse_line("1 cup milk or cream")

    assert parsed.name == "milk"
    assert parsed.alternatives == ("cream",)


def test_preparation_that_changes_the_food_is_separated_from_knife_work() -> None:
    parsed = parse_line("1 cup red peppers, roasted and chopped")

    assert "roasted" in parsed.preparation
    assert "chopped" in parsed.prep_words
    assert "chopped" not in parsed.preparation


def test_a_line_with_no_quantity_is_not_quantified() -> None:
    parsed = parse_line("olive oil")

    assert parsed.quantity is None
    assert parsed.open_ended is True


def test_a_blank_line_is_read_without_waking_the_parser() -> None:
    """The parser raises an IndexError on empty text, and prints while doing it."""
    parsed = parse_line("   ")

    assert parsed.name == ""
    assert parsed.quantity is None
