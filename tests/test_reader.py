from pathlib import Path
from ai2node.reader.java_reader import JavaCodebaseReader


def test_reader_filters_and_categorizes(tmp_path: Path):
    """Smoke test: ensure reader finds Java files and assigns categories.

    creates small synthetic files to avoid filesystem overhead. The
    categorization rules should tag each artifact according to its name.
    """
    src = tmp_path / "src/main/java/com/example"
    src.mkdir(parents=True)
    (src / "UserController.java").write_text("public class UserController {}", encoding="utf-8")
    (src / "UserService.java").write_text("public class UserService {}", encoding="utf-8")
    (src / "UserDAO.java").write_text("public class UserDAO {}", encoding="utf-8")

    reader = JavaCodebaseReader(
        root_dir=tmp_path,
        exclude_globs=["**/target/**"],
        max_file_size_kb=64,
        categorization_rules=["Controller", "Service", "DAO"],
    )

    files = reader.scan()  # exercise traversal, size limits, and exclude globs
    cats = {f.category for f in files}
    assert {"Controller", "Service", "DAO"}.issubset(cats)


