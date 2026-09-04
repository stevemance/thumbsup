"""Minimal S-expression reader for KiCad files (netlists, schematics, libraries)."""

from __future__ import annotations


def parse(text: str):
    """Return nested Python lists; atoms are str (quotes stripped)."""
    tokens = _tokenize(text)
    pos = 0
    stack: list[list] = [[]]
    while pos < len(tokens):
        tok = tokens[pos]
        pos += 1
        if tok == "(":
            stack.append([])
        elif tok == ")":
            done = stack.pop()
            stack[-1].append(done)
        else:
            stack[-1].append(tok)
    if len(stack) != 1:
        raise ValueError("unbalanced s-expression")
    return stack[0]


def _tokenize(text: str) -> list[str]:
    out: list[str] = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c.isspace():
            i += 1
        elif c in "()":
            out.append(c)
            i += 1
        elif c == '"':
            j = i + 1
            buf = []
            while j < n:
                if text[j] == "\\" and j + 1 < n:
                    buf.append(text[j + 1])
                    j += 2
                    continue
                if text[j] == '"':
                    break
                buf.append(text[j])
                j += 1
            out.append("".join(buf))
            i = j + 1
        else:
            j = i
            while j < n and not text[j].isspace() and text[j] not in "()":
                j += 1
            out.append(text[i:j])
            i = j
    return out


def find_all(node, key: str):
    """Yield every child list whose head is `key` (recursive)."""
    if isinstance(node, list):
        if node and node[0] == key:
            yield node
        for child in node:
            if isinstance(child, list):
                yield from find_all(child, key)


def child(node, key: str, default=None):
    """First direct child list with head `key`."""
    for c in node:
        if isinstance(c, list) and c and c[0] == key:
            return c
    return default


def kicad_netlist_nets(text: str) -> dict[str, set[tuple[str, str]]]:
    """Net name -> {(ref, pin)} from a KiCad s-expression netlist."""
    tree = parse(text)
    nets: dict[str, set[tuple[str, str]]] = {}
    for net in find_all(tree, "net"):
        name = child(net, "name")[1]
        nodes = {(child(nd, "ref")[1], child(nd, "pin")[1]) for nd in net if isinstance(nd, list) and nd[0] == "node"}
        nets[name] = nodes
    return nets
