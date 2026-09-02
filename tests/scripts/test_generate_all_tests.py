from pathlib import Path
from tempfile import NamedTemporaryFile

from scripts.generate_all_tests import analyze_module, generate_comprehensive_test


def test_analyze_module():
    code = """
class TestClass:
    def __init__(self, req_arg):
        pass

    def simple_method(self):
        pass

    def method_with_args(self, a, b=1):
        pass

    async def async_method(self):
        pass

    def varargs_method(self, *args, **kwargs):
        pass

    @classmethod
    def class_method(cls):
        pass

    @staticmethod
    def static_method():
        pass
"""
    with NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(code)
        temp_path = Path(f.name)

    try:
        analysis = analyze_module(temp_path)

        assert len(analysis["classes"]) == 1
        cls_info = analysis["classes"][0]
        assert cls_info["name"] == "TestClass"

        methods = {m["name"]: m for m in cls_info["methods"]}

        assert "__init__" in methods
        assert methods["__init__"]["requires_args"] is True

        assert "simple_method" in methods
        assert methods["simple_method"]["requires_args"] is False
        assert methods["simple_method"]["type"] == "instance"

        assert "method_with_args" in methods
        assert methods["method_with_args"]["requires_args"] is True

        assert "async_method" in methods
        assert methods["async_method"]["is_async"] is True

        assert "varargs_method" in methods
        assert methods["varargs_method"]["has_varargs"] is True

        assert "class_method" in methods
        assert methods["class_method"]["type"] == "classmethod"
        assert methods["class_method"]["requires_args"] is False

        assert "static_method" in methods
        assert methods["static_method"]["type"] == "staticmethod"
        assert methods["static_method"]["requires_args"] is False

    finally:
        temp_path.unlink()

def test_generate_comprehensive_test_safe_instantiation(monkeypatch, tmp_path):
    code = """
class SafeClass:
    def __init__(self):
        pass

    def method_no_args(self):
        pass

    def method_args(self, a):
        pass
"""
    test_dir = tmp_path / "app"
    test_dir.mkdir()
    test_file = test_dir / "test_safe_instantiation.py"
    test_file.write_text(code)

    # Mock pathlib.Path.relative_to so it works for the temp directory
    def mock_relative_to(self, other):
        return Path("test_safe_instantiation.py")
    monkeypatch.setattr(Path, "relative_to", mock_relative_to)

    analysis = analyze_module(test_file)
    output = generate_comprehensive_test(test_file, analysis)

    assert "obj = SafeClass()" in output
    assert "result = obj.method_no_args()" in output
    assert "# TODO: provide arguments for method_args" in output

def test_generate_comprehensive_test_unsafe_instantiation(monkeypatch, tmp_path):
    code = """
class UnsafeClass:
    def __init__(self, req_arg):
        pass

    def method_no_args(self):
        pass
"""
    test_dir = tmp_path / "app"
    test_dir.mkdir()
    test_file = test_dir / "test_unsafe_instantiation.py"
    test_file.write_text(code)

    def mock_relative_to(self, other):
        return Path("test_unsafe_instantiation.py")
    monkeypatch.setattr(Path, "relative_to", mock_relative_to)

    analysis = analyze_module(test_file)
    output = generate_comprehensive_test(test_file, analysis)

    assert "# TODO: Instantiate UnsafeClass with required arguments" in output
    assert "obj = UnsafeClass()" not in output

def test_generate_comprehensive_test_async_and_static(monkeypatch, tmp_path):
    code = """
class AdvancedClass:
    async def async_method(self):
        pass

    @classmethod
    def class_method(cls):
        pass
"""
    test_dir = tmp_path / "app"
    test_dir.mkdir()
    test_file = test_dir / "test_async_and_static.py"
    test_file.write_text(code)

    def mock_relative_to(self, other):
        return Path("test_async_and_static.py")
    monkeypatch.setattr(Path, "relative_to", mock_relative_to)

    analysis = analyze_module(test_file)
    output = generate_comprehensive_test(test_file, analysis)

    assert "@pytest.mark.asyncio" in output
    assert "async def test_async_method_basic(self):" in output
    assert "# TODO: provide arguments for async_method" in output

    assert "result = AdvancedClass.class_method()" in output
