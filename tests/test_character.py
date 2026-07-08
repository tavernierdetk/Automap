"""Tests for the character pipeline Stage C (photo -> CharacterProfile).

The network call to Ollama is injected, so these run without a model. They cover the
categorical trait mapping, tolerance of a messy response, .tres rendering, and the
end-to-end write including the manual height override and the dry-run path.
"""
from automap.character import (
    BUILDS,
    HAIR_COLORS,
    HAIRSTYLES,
    attributes_to_tres,
    parse_attributes,
    photo_to_profile,
)


def _full_response(**overrides):
    base = {
        "build": "average", "skin_tone": "fair",
        "hair_color": "brown", "shirt_color": "blue", "pants_color": "navy",
        "hairstyle": "short", "glasses": False, "facial_hair": False,
    }
    base.update(overrides)
    return base


def test_named_colors_map_to_rgb():
    a = parse_attributes(_full_response(hair_color="blonde"))
    assert a.hair_color == HAIR_COLORS["blonde"]
    assert a.descriptors["hair_color"] == "blonde"


def test_build_category_maps_to_float():
    assert parse_attributes(_full_response(build="slim")).build == BUILDS["slim"]
    # Unknown build (or a stray number) falls back to average, never an extreme.
    assert parse_attributes(_full_response(build=95)).build == 1.0
    assert parse_attributes(_full_response(build="huge")).build == 1.0


def test_unknown_hairstyle_falls_back():
    assert parse_attributes(_full_response(hairstyle="mohawk")).hairstyle == "short"
    for style in HAIRSTYLES:
        assert parse_attributes(_full_response(hairstyle=style)).hairstyle == style


def test_defensive_numeric_color_is_normalized():
    # If a model ignores the enum and returns 0-255 RGB, scale it into 0-1 (the bug the
    # 3B model exhibited). Values <= 1 pass through unchanged.
    a = parse_attributes(_full_response(hair_color=[255, 128, 0]))
    assert a.hair_color == (1.0, 128 / 255.0, 0.0)


def test_parse_tolerates_garbage():
    a = parse_attributes({"skin_tone": None, "build": "oops"})
    assert 1.4 <= a.height_m <= 2.1
    assert a.hairstyle in HAIRSTYLES
    assert isinstance(a.glasses, bool)


def test_height_defaults_to_standard_and_override_wins(tmp_path):
    photo = tmp_path / "p.jpg"; photo.write_bytes(b"x")
    # No override -> standard 5'9" (1.75 m), regardless of anything the model says.
    a = photo_to_profile(photo, tmp_path / "a.tres", write=False, _caller=lambda *x, **k: _full_response())
    assert a.height_m == 1.75
    # Override wins.
    b = photo_to_profile(photo, tmp_path / "b.tres", write=False, height_override=1.68,
                         _caller=lambda *x, **k: _full_response())
    assert b.height_m == 1.68


def test_tres_render_is_well_formed():
    text = attributes_to_tres(parse_attributes(_full_response(hairstyle="long", glasses=True)))
    assert 'script_class="CharacterProfile"' in text
    assert 'res://scripts/character_profile.gd' in text
    assert 'hairstyle = "long"' in text
    assert "glasses = true" in text
    assert text.count("Color(") == 4  # skin, hair, shirt, pants


def test_photo_to_profile_writes_tres_with_override(tmp_path):
    photo = tmp_path / "person.jpg"
    photo.write_bytes(b"not-a-real-jpeg")  # _caller is mocked, contents unused
    out = tmp_path / "out" / "person.tres"

    attrs = photo_to_profile(
        photo, out,
        height_override=1.90,
        _caller=lambda *a, **k: _full_response(hairstyle="medium", glasses=True),
    )

    assert out.exists()
    assert attrs.height_m == 1.90               # override applied
    assert attrs.hairstyle == "medium"          # from the model
    body = out.read_text()
    assert "height_m = 1.9" in body
    assert 'hairstyle = "medium"' in body
    assert "glasses = true" in body


def test_photo_to_profile_dry_run_writes_nothing(tmp_path):
    photo = tmp_path / "person.jpg"
    photo.write_bytes(b"x")
    out = tmp_path / "out" / "person.tres"

    attrs = photo_to_profile(
        photo, out,
        write=False,
        _caller=lambda *a, **k: _full_response(hairstyle="afro"),
    )

    assert not out.exists()              # dry run: nothing on disk
    assert attrs.hairstyle == "afro"     # but attributes still returned
