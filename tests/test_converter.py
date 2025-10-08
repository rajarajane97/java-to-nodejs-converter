from pathlib import Path
from ai2node.converter.convert import convert_to_express
from ai2node.reader.java_reader import JavaFileInfo


def test_convert_creates_outputs(tmp_path: Path):
    """Convert a single controller and verify outputs exist.

    This validates template loading, rendering, and file writing paths without
    asserting template internals.
    """
    java_file = tmp_path / "UserController.java"
    java_file.write_text("public class UserController { public void getUser(String id){} }", encoding="utf-8")
    files = [
        JavaFileInfo(path=str(java_file), size_bytes=len(java_file.read_bytes()), category="Controller")
    ]
    out_dir = tmp_path / "out"
    templates = Path("ai2node/converter/templates/express").resolve()
    results = convert_to_express(files, templates, out_dir)
    assert (out_dir / "UserControllerController.js").exists()
    assert results

    # Verify a route corresponding to method name heuristic exists
    text = (out_dir / "UserControllerController.js").read_text(encoding="utf-8")
    assert "router.get" in text or "router.post" in text
    assert "get-user" in text  # from method getUser -> get-user


def test_controller_wires_service_call(tmp_path: Path):
    # Controller + implied service name should attempt to call service method
    ctrl = tmp_path / "OrderController.java"
    srv = tmp_path / "OrderService.java"
    ctrl.write_text("public class OrderController { public String getOrder(int id){ return \"x\"; } }", encoding="utf-8")
    srv.write_text("public class OrderService { public String getOrder(int id){ return \"x\"; } }", encoding="utf-8")
    files = [
        JavaFileInfo(path=str(ctrl), size_bytes=len(ctrl.read_bytes()), category="Controller"),
        JavaFileInfo(path=str(srv), size_bytes=len(srv.read_bytes()), category="Service"),
    ]
    out_dir = tmp_path / "out"
    templates = Path("ai2node/converter/templates/express").resolve()
    _ = convert_to_express(files, templates, out_dir)
    ctrl_out = out_dir / "OrderControllerController.js"
    assert ctrl_out.exists()
    text = ctrl_out.read_text(encoding="utf-8")
    assert "require('./OrderService.js')" in text
    assert "service['getOrder']" in text


