import ast
import json
from pathlib import Path

PKG_ROOT = Path.home() / "wheelchair_ws" / "src" / "wheelchair_robot"
OUT_PATH = Path.home() / "wheelchair_ws" / "tools" / "context.json"

EVENT_KEYWORDS = {
    "obstacle_too_close", "obstacle_cleared", "keepout_violation",
    "imu_emergency", "localization_lost", "user_stop", "sos",
    "manual", "auto", "blocked", "modified", "allowed",
}

def extract_from_file(filepath):
    src = Path(filepath).read_text()
    tree = ast.parse(src)
    chunks = []

    if (doc := ast.get_docstring(tree)):
        chunks.append({"type": "module_doc", "file": str(filepath), "content": doc})

    for node in ast.walk(tree):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if (doc := ast.get_docstring(node)):
                chunks.append({
                    "type": "docstring", "file": str(filepath),
                    "name": node.name, "content": doc,
                })
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            method = node.func.attr
            if method in ("create_subscription", "create_publisher",
                          "create_client", "create_service"):
                args_repr = [ast.unparse(a) for a in node.args]
                chunks.append({
                    "type": f"ros2_{method}", "file": str(filepath),
                    "line": node.lineno,
                    "content": f"{method}({', '.join(args_repr)})",
                })
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value in EVENT_KEYWORDS:
                chunks.append({
                    "type": "event_literal", "file": str(filepath),
                    "line": node.lineno, "content": node.value,
                })
    return chunks

if __name__ == "__main__":
    all_chunks = []
    for py in PKG_ROOT.rglob("*.py"):
        try:
            all_chunks.extend(extract_from_file(py))
        except SyntaxError:
            pass
    for yaml_file in PKG_ROOT.rglob("*.yaml"):
        all_chunks.append({
            "type": "param_file", "file": str(yaml_file),
            "content": yaml_file.read_text(),
        })
    OUT_PATH.write_text(json.dumps(all_chunks, indent=2, ensure_ascii=False))
    print(f"✅ {len(all_chunks)} chunks → {OUT_PATH}")