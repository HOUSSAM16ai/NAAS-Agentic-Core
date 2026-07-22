"""Formal argument analysis — a tiny propositional expression tree + validity.

This is the *logic / inference* substrate. It provides:

* a small, immutable propositional expression tree (:class:`Atom`, :class:`Not`,
  :class:`And`, :class:`Or`, :class:`Implies`, :class:`Iff`) that can both be
  **evaluated** under an assignment and **structurally inspected**;
* :class:`Argument` — a set of premises entailing a conclusion, whose validity is
  decided by the verified engine ``app.core.foundations.logic.entails`` (never by a
  heuristic — symbolic truth before language, CLAUDE.md §0);
* :func:`classify_argument_form` — deterministic recognition of the canonical
  valid forms (modus ponens/tollens, hypothetical/disjunctive syllogism) and the
  classic **formal fallacies** (affirming the consequent, denying the antecedent,
  circular reasoning / begging the question).

Dependency-free beyond the standard library and ``app.core.foundations``. Every
structural violation raises :class:`ReasoningError`.
"""

from __future__ import annotations

import abc
from collections.abc import Sequence
from dataclasses import dataclass

from app.core.foundations import logic
from app.core.reasoning.errors import ReasoningError

Assignment = dict[str, bool]


class Expr(abc.ABC):
    """An immutable propositional expression over named boolean atoms."""

    __slots__ = ()

    @abc.abstractmethod
    def evaluate(self, assignment: Assignment) -> bool:
        """Truth value of the expression under ``assignment`` (missing atom → error)."""

    @abc.abstractmethod
    def atoms(self) -> frozenset[str]:
        """The set of atom names appearing in the expression."""

    # ``Expr`` instances compare/​hash structurally via their dataclass subclasses.
    def __or__(self, other: Expr) -> Or:  # convenience: A | B
        return Or(self, other)

    def __and__(self, other: Expr) -> And:  # convenience: A & B
        return And(self, other)


@dataclass(frozen=True)
class Atom(Expr):
    """An atomic proposition, e.g. ``Atom("rain")`` for «it is raining»."""

    name: str

    def __post_init__(self) -> None:
        if not self.name or not str(self.name).strip():
            raise ReasoningError("Atom name must be a non-empty string")

    def evaluate(self, assignment: Assignment) -> bool:
        try:
            return bool(assignment[self.name])
        except KeyError as exc:
            raise ReasoningError(f"no truth value for atom {self.name!r}") from exc

    def atoms(self) -> frozenset[str]:
        return frozenset({self.name})


@dataclass(frozen=True)
class Not(Expr):
    """Logical negation ``¬e``."""

    operand: Expr

    def evaluate(self, assignment: Assignment) -> bool:
        return not self.operand.evaluate(assignment)

    def atoms(self) -> frozenset[str]:
        return self.operand.atoms()


@dataclass(frozen=True)
class And(Expr):
    """Logical conjunction ``a ∧ b``."""

    left: Expr
    right: Expr

    def evaluate(self, assignment: Assignment) -> bool:
        return self.left.evaluate(assignment) and self.right.evaluate(assignment)

    def atoms(self) -> frozenset[str]:
        return self.left.atoms() | self.right.atoms()


@dataclass(frozen=True)
class Or(Expr):
    """Logical (inclusive) disjunction ``a ∨ b``."""

    left: Expr
    right: Expr

    def evaluate(self, assignment: Assignment) -> bool:
        return self.left.evaluate(assignment) or self.right.evaluate(assignment)

    def atoms(self) -> frozenset[str]:
        return self.left.atoms() | self.right.atoms()


@dataclass(frozen=True)
class Implies(Expr):
    """Material implication ``a → b``."""

    antecedent: Expr
    consequent: Expr

    def evaluate(self, assignment: Assignment) -> bool:
        return logic.implies(
            self.antecedent.evaluate(assignment),
            self.consequent.evaluate(assignment),
        )

    def atoms(self) -> frozenset[str]:
        return self.antecedent.atoms() | self.consequent.atoms()


@dataclass(frozen=True)
class Iff(Expr):
    """Biconditional ``a ↔ b``."""

    left: Expr
    right: Expr

    def evaluate(self, assignment: Assignment) -> bool:
        return logic.iff(self.left.evaluate(assignment), self.right.evaluate(assignment))

    def atoms(self) -> frozenset[str]:
        return self.left.atoms() | self.right.atoms()


@dataclass(frozen=True)
class Argument:
    """A set of premises advanced in support of a conclusion.

    Validity is decided by ``foundations.logic.entails`` over every assignment of
    the atoms appearing anywhere in the argument — a proof, not a guess.
    """

    premises: tuple[Expr, ...]
    conclusion: Expr

    def __post_init__(self) -> None:
        if not isinstance(self.premises, tuple):
            object.__setattr__(self, "premises", tuple(self.premises))
        if not self.premises:
            raise ReasoningError("an argument needs at least one premise")

    def variables(self) -> list[str]:
        """Sorted atom names over all premises and the conclusion."""
        names: frozenset[str] = self.conclusion.atoms()
        for premise in self.premises:
            names = names | premise.atoms()
        return sorted(names)

    def is_valid(self) -> bool:
        """True iff the premises *entail* the conclusion (verified, symbolic)."""
        variables = self.variables()
        return logic.entails(
            [p.evaluate for p in self.premises],
            self.conclusion.evaluate,
            variables,
        )

    def is_sound(self, facts: Assignment) -> bool:
        """True iff the argument is valid *and* every premise holds under ``facts``."""
        if not self.is_valid():
            return False
        return all(p.evaluate(facts) for p in self.premises)

    def counterexample(self) -> Assignment | None:
        """A witness to invalidity, or ``None`` if the argument is valid.

        Returns the first assignment (in ``itertools.product`` order) that makes
        every premise true but the conclusion false — the concrete case that
        breaks the argument, the heart of «show me why it doesn't follow».
        """
        from itertools import product

        variables = self.variables()
        for combo in product((False, True), repeat=len(variables)):
            assignment = dict(zip(variables, combo, strict=True))
            if all(p.evaluate(assignment) for p in self.premises) and not self.conclusion.evaluate(
                assignment
            ):
                return assignment
        return None


# ── Argument-form recognition ────────────────────────────────────────────────
_VALID_FORMS = frozenset(
    {
        "modus_ponens",
        "modus_tollens",
        "hypothetical_syllogism",
        "disjunctive_syllogism",
    }
)
_FALLACY_FORMS = frozenset(
    {
        "affirming_the_consequent",
        "denying_the_antecedent",
        "circular_reasoning",
    }
)


def is_fallacy(form: str) -> bool:
    """True iff ``form`` (a :func:`classify_argument_form` result) is a formal fallacy."""
    return form in _FALLACY_FORMS


def classify_argument_form(argument: Argument) -> str:
    """Return the canonical form label of ``argument``.

    Recognises the four classic valid forms and the three classic formal
    fallacies structurally; otherwise falls back to ``"valid"`` / ``"invalid"``
    decided by :meth:`Argument.is_valid`. The structural match and the semantic
    validity always agree for the recognised forms — the fallacies are exactly the
    *invalid* look-alikes of modus ponens/tollens.
    """
    premises = argument.premises
    conclusion = argument.conclusion

    # Circular reasoning / begging the question: the conclusion is literally one
    # of the premises. (Valid but rhetorically empty — flagged as a fallacy.)
    if conclusion in premises:
        return "circular_reasoning"

    conditional = next((p for p in premises if isinstance(p, Implies)), None)
    others = [p for p in premises if p is not conditional]

    if conditional is not None and len(others) == 1:
        other = others[0]
        p, q = conditional.antecedent, conditional.consequent
        # Modus ponens: (p→q), p ⊢ q
        if other == p and conclusion == q:
            return "modus_ponens"
        # Modus tollens: (p→q), ¬q ⊢ ¬p
        if other == Not(q) and conclusion == Not(p):
            return "modus_tollens"
        # Affirming the consequent (fallacy): (p→q), q ⊢ p
        if other == q and conclusion == p:
            return "affirming_the_consequent"
        # Denying the antecedent (fallacy): (p→q), ¬p ⊢ ¬q
        if other == Not(p) and conclusion == Not(q):
            return "denying_the_antecedent"

    # Hypothetical syllogism: (p→q), (q→r) ⊢ (p→r)
    conditionals = [p for p in premises if isinstance(p, Implies)]
    if len(conditionals) == 2 and isinstance(conclusion, Implies):
        a, b = conditionals
        if a.consequent == b.antecedent and conclusion == Implies(a.antecedent, b.consequent):
            return "hypothetical_syllogism"
        if b.consequent == a.antecedent and conclusion == Implies(b.antecedent, a.consequent):
            return "hypothetical_syllogism"

    # Disjunctive syllogism: (p∨q), ¬p ⊢ q
    disjunction = next((p for p in premises if isinstance(p, Or)), None)
    if disjunction is not None and len(premises) == 2:
        rest = next(p for p in premises if p is not disjunction)
        if rest == Not(disjunction.left) and conclusion == disjunction.right:
            return "disjunctive_syllogism"
        if rest == Not(disjunction.right) and conclusion == disjunction.left:
            return "disjunctive_syllogism"

    return "valid" if argument.is_valid() else "invalid"


def make_argument(premises: Sequence[Expr], conclusion: Expr) -> Argument:
    """Convenience constructor validating inputs and returning an :class:`Argument`."""
    if conclusion is None or not isinstance(conclusion, Expr):
        raise ReasoningError("conclusion must be an Expr")
    exprs = tuple(premises)
    if any(not isinstance(e, Expr) for e in exprs):
        raise ReasoningError("every premise must be an Expr")
    return Argument(premises=exprs, conclusion=conclusion)


# ── Text parser (compact propositional DSL) ──────────────────────────────────
# Grammar (lowest → highest precedence): iff (<->) → implies (->) → or (| ∨) →
# and (& ∧) → not (~ ! ¬) → atom / (expr). Atoms are ``[A-Za-z_][A-Za-z0-9_]*``.
_TOKEN_ALIASES = {
    "∧": "&",
    "∨": "|",
    "¬": "~",
    "!": "~",
    "→": "->",
    "↔": "<->",
    "⊃": "->",
}


def _tokenize(text: str) -> list[str]:
    for src, dst in _TOKEN_ALIASES.items():
        text = text.replace(src, dst)
    tokens: list[str] = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch.isspace():
            i += 1
        elif text.startswith("<->", i):
            tokens.append("<->")
            i += 3
        elif text.startswith("->", i):
            tokens.append("->")
            i += 2
        elif ch in "()&|~":
            tokens.append(ch)
            i += 1
        elif ch.isalnum() or ch == "_":
            j = i
            while j < n and (text[j].isalnum() or text[j] == "_"):
                j += 1
            word = text[i:j]
            lowered = word.lower()
            tokens.append({"and": "&", "or": "|", "not": "~"}.get(lowered, word))
            i = j
        else:
            raise ReasoningError(f"unexpected character {ch!r} in logic expression")
    if not tokens:
        raise ReasoningError("empty logic expression")
    return tokens


def parse(text: str) -> Expr:
    """Parse a propositional formula string into an :class:`Expr`.

    Accepts ``->`` / ``<->`` / ``&`` / ``|`` / ``~`` (and the words
    ``and``/``or``/``not`` and the unicode symbols ``∧ ∨ ¬ → ↔``). Raises
    :class:`ReasoningError` on malformed input — the caller never gets a silently
    wrong tree.
    """
    tokens = _tokenize(text)
    pos = 0

    def peek() -> str | None:
        return tokens[pos] if pos < len(tokens) else None

    def eat(expected: str | None = None) -> str:
        nonlocal pos
        if pos >= len(tokens):
            raise ReasoningError("unexpected end of logic expression")
        tok = tokens[pos]
        if expected is not None and tok != expected:
            raise ReasoningError(f"expected {expected!r}, got {tok!r}")
        pos += 1
        return tok

    def parse_iff() -> Expr:
        left = parse_implies()
        while peek() == "<->":
            eat("<->")
            left = Iff(left, parse_implies())
        return left

    def parse_implies() -> Expr:
        left = parse_or()
        if peek() == "->":  # right-associative
            eat("->")
            return Implies(left, parse_implies())
        return left

    def parse_or() -> Expr:
        left = parse_and()
        while peek() == "|":
            eat("|")
            left = Or(left, parse_and())
        return left

    def parse_and() -> Expr:
        left = parse_not()
        while peek() == "&":
            eat("&")
            left = And(left, parse_not())
        return left

    def parse_not() -> Expr:
        if peek() == "~":
            eat("~")
            return Not(parse_not())
        return parse_atom()

    def parse_atom() -> Expr:
        tok = peek()
        if tok == "(":
            eat("(")
            inner = parse_iff()
            eat(")")
            return inner
        if tok is None or tok in {"&", "|", "->", "<->", ")"}:
            raise ReasoningError(f"expected an atom, got {tok!r}")
        eat()
        return Atom(tok)

    tree = parse_iff()
    if pos != len(tokens):
        raise ReasoningError(f"trailing tokens after expression: {tokens[pos:]}")
    return tree
