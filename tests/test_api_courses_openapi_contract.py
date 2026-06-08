from __future__ import annotations

from app.api.main import create_app


EXPECTED_PATHS = {
    "/courses",
    "/courses/{course_id}",
}


def _operation(spec: dict, path: str) -> dict:
    path_item = spec["paths"][path]
    assert set(path_item) == {"get"}
    return path_item["get"]


def _parameter_names(operation: dict) -> list[str]:
    return [param["name"] for param in operation.get("parameters", [])]


def test_courses_openapi_contract_freezes_readonly_surface() -> None:
    spec = create_app().openapi()

    course_paths = {path for path in spec["paths"] if path.startswith("/courses")}
    assert course_paths == EXPECTED_PATHS

    list_courses = _operation(spec, "/courses")
    detail_course = _operation(spec, "/courses/{course_id}")

    assert _parameter_names(list_courses) == ["q", "year", "month_start", "month_end"]
    assert _parameter_names(detail_course) == ["course_id"]

    assert list_courses["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/CourseListResponse"
    }
    assert detail_course["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/CourseDetail"
    }

    course_id_param = detail_course["parameters"][0]
    assert course_id_param["in"] == "path"
    assert course_id_param["required"] is True
