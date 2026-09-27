from pathlib import Path

from autonomousdev.context import ContextEngine
from autonomousdev.repository import RepositoryMapper


def test_mapper_extracts_repository_signals(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "src" / "billing.py").write_text(
        "from decimal import Decimal\n\nclass Invoice:\n    pass\n", encoding="utf-8"
    )
    (tmp_path / "tests" / "test_billing.py").write_text(
        "from src.billing import Invoice\n", encoding="utf-8"
    )
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname='fixture'\ndependencies=['httpx>=0.27']\n", encoding="utf-8"
    )

    index = RepositoryMapper().map(tmp_path)

    assert index.languages["Python"] == 2
    assert index.manifests == ["pyproject.toml"]
    assert index.dependencies["pyproject.toml"] == ["httpx"]
    assert index.tests == ["tests/test_billing.py"]
    billing = next(item for item in index.files if item.path == "src/billing.py")
    assert "Invoice" in billing.symbols
    assert "decimal" in billing.imports


def test_context_is_ranked_bounded_and_auditable(tmp_path: Path) -> None:
    (tmp_path / "auth.py").write_text("def login_rate_limit():\n    return 10\n", encoding="utf-8")
    (tmp_path / "unrelated.py").write_text("def colors():\n    return ['red']\n", encoding="utf-8")
    index = RepositoryMapper().map(tmp_path)

    bundle = ContextEngine(token_budget=100).select("fix login rate limit", index)

    assert bundle.estimated_tokens <= 100
    assert bundle.items[0].path == "auth.py"
    assert bundle.items[0].content_sha256
    assert "login_rate_limit" in bundle.items[0].content
