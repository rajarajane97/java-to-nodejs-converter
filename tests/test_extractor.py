from pathlib import Path
from ai2node.extractor.pipeline import extract_metadata
from ai2node.reader.java_reader import JavaFileInfo


def test_extracts_methods(tmp_path: Path):
    """Ensure method extraction picks up simple Java methods.
    """
    java_file = tmp_path / "ExampleService.java"
    java_file.write_text(
        """
        public class ExampleService {
            public String greet(String name) { return "Hello " + name; }
        }
        """,
        encoding="utf-8",
    )
    info = JavaFileInfo(path=str(java_file), size_bytes=len(java_file.read_bytes()), category="Service")
    knowledge = extract_metadata([info])
    assert any(m.name == "greet" for c in knowledge.modules for m in c.methods)


def test_complexity_and_dependencies(tmp_path: Path):
    a = tmp_path / "AService.java"
    b = tmp_path / "BService.java"
    a.write_text(
        """
        public class AService {
            private BService b;
            public int f(int x){ if(x>0){ return x; } else { return -x; } }
        }
        """,
        encoding="utf-8",
    )
    b.write_text(
        """
        public class BService {
            public int g(int y){ for(int i=0;i<y;i++){ y+=1; } return y; }
        }
        """,
        encoding="utf-8",
    )
    infos = [
        JavaFileInfo(path=str(a), size_bytes=len(a.read_bytes()), category="Service"),
        JavaFileInfo(path=str(b), size_bytes=len(b.read_bytes()), category="Service"),
    ]
    knowledge = extract_metadata(infos)
    classes = {c.name: c for c in knowledge.modules}
    assert "AService" in classes and "BService" in classes
    # Dependency: AService references BService
    assert "BService" in classes["AService"].dependencies
    # Complexity scores are >= 1
    for c in knowledge.modules:
        for m in c.methods:
            assert m.complexity_score >= 1


