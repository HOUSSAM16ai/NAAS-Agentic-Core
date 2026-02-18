import ast


class ComplexityAnalyzer(ast.NodeVisitor):
    """Advanced Cyclomatic Complexity Analyzer"""

    def __init__(self):
        self.file_complexity = 0
        self.functions: list[dict[str, object]] = []
        self.classes: list[dict[str, object]] = []
        self.current_class: str | None = None
        self.imports: list[str] = []
        self.max_nesting = 0

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Analyze classes"""
        self.current_class = node.name
        self.classes.append(
            {
                "name": node.name,
                "line": node.lineno,
                "methods": [],
                "loc": self._count_node_lines(node),
            }
        )
        self.generic_visit(node)
        self.current_class = None

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Analyze functions"""
        complexity = self._calculate_complexity(node)
        nesting = self._calculate_nesting(node)
        loc = self._count_node_lines(node)

        func_info = {
            "name": node.name,
            "line": node.lineno,
            "complexity": complexity,
            "nesting_depth": nesting,
            "loc": loc,
            "is_public": not node.name.startswith("_"),
            "class": self.current_class,
            "num_parameters": len(node.args.args),
        }

        self.functions.append(func_info)
        self.file_complexity += complexity
        self.max_nesting = max(self.max_nesting, nesting)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Analyze async functions"""
        self.visit_FunctionDef(node)  # type: ignore

    def visit_Import(self, node: ast.Import) -> None:
        """Track imports"""
        for alias in node.names:
            self.imports.append(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Track from imports"""
        if node.module:
            self.imports.append(node.module)
        self.generic_visit(node)

    def _calculate_complexity(self, node: ast.FunctionDef) -> int:
        """Calculate McCabe Cyclomatic Complexity"""
        complexity = 1  # Base complexity

        for child in ast.walk(node):
            # Decision points
            if isinstance(
                child,
                (
                    ast.If,
                    ast.While,
                    ast.For,
                    ast.AsyncFor,
                    ast.ExceptHandler,
                    ast.With,
                    ast.AsyncWith,
                ),
            ):
                complexity += 1
            # Boolean operators
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1
            # Comprehensions
            elif isinstance(child, (ast.ListComp, ast.DictComp, ast.SetComp, ast.GeneratorExp)):
                complexity += 1

        return complexity

    def _calculate_nesting(self, node: ast.FunctionDef) -> int:
        """Calculate maximum nesting depth"""
        max_depth = 0

        def visit_node(n, depth) -> None:
            nonlocal max_depth
            max_depth = max(max_depth, depth)

            for child in ast.iter_child_nodes(n):
                if isinstance(child, (ast.If, ast.While, ast.For, ast.AsyncFor, ast.Try, ast.With)):
                    visit_node(child, depth + 1)
                else:
                    visit_node(child, depth)

        visit_node(node, 0)
        return max_depth

    def _count_node_lines(self, node) -> int:
        """Count node lines"""
        if hasattr(node, "end_lineno") and node.end_lineno:
            return node.end_lineno - node.lineno + 1
        return 1
