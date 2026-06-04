from __future__ import annotations

from app.ui.widgets.recipes_page import _collect_recipe_image_gallery, _load_recipe_image_gallery


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
