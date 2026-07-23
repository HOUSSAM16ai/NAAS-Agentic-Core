"""Formal languages — finite automata, a small regex engine, grammars, Dyck.

Dependency-free models from the theory of computation's language layer: a
deterministic finite automaton (DFA), a teaching regex matcher supporting
concatenation / union ``|`` / Kleene star ``*`` / grouping, a balanced-brackets
(Dyck-language) recognizer, and a bounded context-free-grammar derivation check.

Every primitive raises :class:`FoundationsError` on a malformed machine/pattern
(symbol outside the alphabet, unbalanced parentheses in a pattern, etc.).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from microservices.foundations_service.src.foundations.errors import FoundationsError


@dataclass(frozen=True)
class DFA:
    """A deterministic finite automaton.

    ``transitions`` maps ``(state, symbol) -> state``. ``accepts`` runs the
    machine over an input string and reports whether it ends in an accept state.
    """

    states: frozenset[str]
    alphabet: frozenset[str]
    transitions: Mapping[tuple[str, str], str]
    start: str
    accept: frozenset[str]

    def __post_init__(self) -> None:
        if self.start not in self.states:
            raise FoundationsError(f"DFA: start state {self.start!r} is not in states")
        if not self.accept <= self.states:
            raise FoundationsError("DFA: accept states must be a subset of states")
        for (state, symbol), target in self.transitions.items():
            if state not in self.states or target not in self.states:
                raise FoundationsError(f"DFA: transition uses unknown state ({state}->{target})")
            if symbol not in self.alphabet:
                raise FoundationsError(f"DFA: transition symbol {symbol!r} not in alphabet")

    def accepts(self, string: str) -> bool:
        """Run the DFA; raise if the input uses a symbol outside the alphabet."""
        state = self.start
        for symbol in string:
            if symbol not in self.alphabet:
                raise FoundationsError(f"DFA.accepts: symbol {symbol!r} not in alphabet")
            key = (state, symbol)
            if key not in self.transitions:
                return False  # dead / missing transition — reject
            state = self.transitions[key]
        return state in self.accept


def matches_regex(pattern: str, text: str) -> bool:
    """Whole-string match of a small regex (concat, ``|``, ``*``, ``(...)``, ``.``).

    A recursive-descent matcher over the classic teaching grammar — no external
    ``re`` module. Raises on unbalanced parentheses.
    """
    tokens = _tokenize(pattern)
    node, pos = _parse_alt(tokens, 0)
    if pos != len(tokens):
        raise FoundationsError("matches_regex: unbalanced ')' in pattern")
    # A whole-string match consumes the entire input (remaining empty).
    return any(rest == "" for _consumed, rest in _match_node(node, text))


def is_balanced(text: str, pairs: str = "()[]{}") -> bool:
    """True when brackets in ``text`` are balanced (the Dyck language)."""
    if len(pairs) % 2 != 0:
        raise FoundationsError("is_balanced: pairs must be even-length (open/close chars)")
    openers = {pairs[i]: pairs[i + 1] for i in range(0, len(pairs), 2)}
    closers = {v: k for k, v in openers.items()}
    stack: list[str] = []
    for ch in text:
        if ch in openers:
            stack.append(ch)
        elif ch in closers:
            if not stack or stack[-1] != closers[ch]:
                return False
            stack.pop()
    return not stack


def derives(
    grammar: Mapping[str, Iterable[str]], start: str, target: str, max_depth: int = 12
) -> bool:
    """Whether a context-free ``grammar`` derives ``target`` from ``start``.

    ``grammar`` maps a non-terminal to alternative right-hand sides (strings of
    terminals + non-terminals). Bounded BFS over sentential forms — raises when
    ``start`` is not a non-terminal.
    """
    if start not in grammar:
        raise FoundationsError(f"derives: start symbol {start!r} is not a non-terminal")
    non_terminals = set(grammar)
    frontier = {start}
    for _ in range(max_depth):
        if target in frontier:
            return True
        nxt: set[str] = set()
        for form in frontier:
            idx = next((i for i, ch in enumerate(form) if ch in non_terminals), None)
            if idx is None:
                continue  # fully terminal — cannot expand
            nt = form[idx]
            for rhs in grammar[nt]:
                candidate = form[:idx] + rhs + form[idx + 1 :]
                if len(candidate) <= len(target) + 4:
                    nxt.add(candidate)
        if not nxt or nxt <= frontier:
            break
        frontier |= nxt
    return target in frontier


# --- Regex engine internals -------------------------------------------------


def _tokenize(pattern: str) -> list[str]:
    return list(pattern)


def _parse_alt(tokens: list[str], pos: int) -> tuple[dict, int]:
    node, pos = _parse_concat(tokens, pos)
    branches = [node]
    while pos < len(tokens) and tokens[pos] == "|":
        right, pos = _parse_concat(tokens, pos + 1)
        branches.append(right)
    if len(branches) == 1:
        return node, pos
    return {"type": "alt", "branches": branches}, pos


def _parse_concat(tokens: list[str], pos: int) -> tuple[dict, int]:
    items: list[dict] = []
    while pos < len(tokens) and tokens[pos] not in "|)":
        atom, pos = _parse_atom(tokens, pos)
        if pos < len(tokens) and tokens[pos] == "*":
            atom = {"type": "star", "child": atom}
            pos += 1
        items.append(atom)
    return {"type": "concat", "items": items}, pos


def _parse_atom(tokens: list[str], pos: int) -> tuple[dict, int]:
    ch = tokens[pos]
    if ch == "(":
        node, pos = _parse_alt(tokens, pos + 1)
        if pos >= len(tokens) or tokens[pos] != ")":
            raise FoundationsError("matches_regex: unbalanced '(' in pattern")
        return node, pos + 1
    return {"type": "char", "value": ch}, pos + 1


def _match_node(node: dict, text: str) -> set[tuple[str, str]]:
    """Return the set of ``(consumed, remaining)`` splits ``node`` can match as a prefix."""
    kind = node["type"]
    if kind == "char":
        if text and (node["value"] == "." or text[0] == node["value"]):
            return {(text[0], text[1:])}
        return set()
    if kind == "concat":
        results = {("", text)}
        for item in node["items"]:
            nxt: set[tuple[str, str]] = set()
            for consumed, rest in results:
                for c2, r2 in _match_node(item, rest):
                    nxt.add((consumed + c2, r2))
            results = nxt
            if not results:
                break
        return results
    if kind == "alt":
        out: set[tuple[str, str]] = set()
        for branch in node["branches"]:
            out |= _match_node(branch, text)
        return out
    # star — zero or more, bounded by input length
    out = {("", text)}
    frontier = {("", text)}
    while frontier:
        nxt = set()
        for consumed, rest in frontier:
            for c2, r2 in _match_node(node["child"], rest):
                if c2 == "":
                    continue  # avoid infinite loop on empty match
                pair = (consumed + c2, r2)
                if pair not in out:
                    nxt.add(pair)
        out |= nxt
        frontier = nxt
    return out
