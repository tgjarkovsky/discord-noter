import pytest

import projects
from projects import list_projects, style_folder


@pytest.fixture
def styles(tmp_path, monkeypatch):
    """Přesměruje STYLES_DIR na dočasnou složku."""
    monkeypatch.setattr(projects, "STYLES_DIR", tmp_path / "styles")
    return tmp_path / "styles"


def test_missing_styles_dir_means_no_projects(styles):
    assert list_projects() == []


def test_projects_are_subfolders_sorted(styles):
    for name in ["Zeta", "Alfa"]:
        (styles / name).mkdir(parents=True)
    (styles / "README.md").write_text("není projekt", encoding="utf-8")
    assert list_projects() == ["Alfa", "Zeta"]


def test_style_folder_points_into_styles(styles):
    assert style_folder("Alfa") == str(styles / "Alfa")
