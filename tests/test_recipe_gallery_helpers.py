from __future__ import annotations

import json

from app.ui.widgets.recipes_page import (
    _collect_recipe_image_gallery,
    _json_to_string_dict,
    _load_recipe_image_gallery,
    _recipe_image_gallery_from_payload,
)


def test_collect_recipe_image_gallery_filters_blank_paths_and_keeps_order() -> None:
    items = [("/a.png", False), ("", True), ("/b.png", True)]

    assert _collect_recipe_image_gallery(items) == [
        {"path": "/a.png", "is_main": False, "order": 0},
        {"path": "/b.png", "is_main": True, "order": 2},
    ]


def test_load_recipe_image_gallery_orders_by_order_and_ignores_invalid_payload() -> None:
    raw = '[{"path": "/b.png", "is_main": true, "order": 2}, {"path": "/a.png", "order": 1}, {"path": "", "order": 0}]'

    assert _load_recipe_image_gallery(raw) == [
        {"path": "/a.png", "is_main": False},
        {"path": "/b.png", "is_main": True},
    ]


def test_load_recipe_image_gallery_returns_empty_for_non_list_payload() -> None:
    assert _load_recipe_image_gallery('{"path": "/x.png"}') == []


def test_recipe_image_gallery_survives_saved_json_round_trip() -> None:
    saved_json = json.dumps(
        {"images_gallery": [{"path": "/img/a.png", "is_main": True, "order": 0}]},
        ensure_ascii=False,
    )

    loaded_payload = _json_to_string_dict(saved_json)

    assert _recipe_image_gallery_from_payload(loaded_payload) == [
        {"path": "/img/a.png", "is_main": True},
    ]


def test_recipe_image_gallery_supports_legacy_payload_key() -> None:
    payload = {
        "__images_gallery_json": '[{"path": "/img/legacy.png", "is_main": false, "order": 0}]',
    }

    assert _recipe_image_gallery_from_payload(payload) == [
        {"path": "/img/legacy.png", "is_main": False},
    ]
