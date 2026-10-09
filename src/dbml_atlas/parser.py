from __future__ import annotations

import re
import textwrap

from .model import Column, Ref, Schema, Table
from .style import CATEGORY_ALIASES

IDENT = r'(?:"[^"]+"|`[^`]+`|[\w$]+)'
TYPE = r'(?:"[^"]+"|[\w.$]+(?:\s*\([^)]*\))?(?:\[\])?)'


def strip_quotes(s: str) -> str:
    s = s.strip()
    if s.startswith("'''") and s.endswith("'''") and len(s) >= 6:
        return s[3:-3]
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'`":
        return s[1:-1]
    return s


def clean_note(s: str) -> str:
    s = s.strip()
    if s.startswith("'''"):
        s = s[3:]
    if s.endswith("'''"):
        s = s[:-3]
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "'\"":
        s = s[1:-1]
    return textwrap.dedent(s.replace("\\'", "'")).strip()


def split_top(s: str, sep: str = ",") -> list[str]:
    out = []
    buf = []
    depth = 0
    quote = None
    i = 0
    while i < len(s):
        ch = s[i]
        if quote:
            buf.append(ch)
            if ch == "\\" and i + 1 < len(s):
                buf.append(s[i + 1]); i += 2; continue
            if s.startswith(quote, i):
                if len(quote) == 3:
                    buf.append(s[i + 1:i + 3]); i += 2
                quote = None
        elif s.startswith("'''", i):
            quote = "'''"; buf.append("'''"); i += 2
        elif ch in "\"'`":
            quote = ch; buf.append(ch)
        elif ch in "([":
            depth += 1; buf.append(ch)
        elif ch in ")]":
            depth -= 1; buf.append(ch)
        elif ch == sep and depth == 0:
            out.append("".join(buf).strip()); buf = []
        else:
            buf.append(ch)
        i += 1
    if "".join(buf).strip():
        out.append("".join(buf).strip())
    return out


def normalize(text: str) -> str:
    """Put every { and } (outside strings, [settings] and comments) on its own line."""
    out, i, n = [], 0, len(text)
    quote, depth, comment = None, 0, False
    while i < n:
        ch = text[i]
        if comment:
            out.append(ch)
            if ch == "\n":
                comment = False
        elif quote:
            out.append(ch)
            if ch == "\\" and i + 1 < n:
                out.append(text[i + 1]); i += 2; continue
            if text.startswith(quote, i):
                if len(quote) == 3:
                    out.append(text[i + 1:i + 3]); i += 2
                quote = None
        elif text.startswith("//", i):
            comment = True; out.append(ch)
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2)
            i = n if j < 0 else j + 2
            continue
        elif text.startswith("'''", i):
            quote = "'''"; out.append("'''"); i += 3; continue
        elif ch in "\"'`":
            quote = ch; out.append(ch)
        elif ch == "[":
            depth += 1; out.append(ch)
        elif ch == "]":
            depth = max(0, depth - 1); out.append(ch)
        elif ch == "{" and depth == 0:
            out.append("{\n")
        elif ch == "}" and depth == 0:
            out.append("\n}\n")
        else:
            out.append(ch)
        i += 1
    return "".join(out)


def strip_comment(line: str) -> str:
    quote = None
    for i, ch in enumerate(line):
        if quote:
            if ch == quote:
                quote = None
        elif ch in "\"'`":
            quote = ch
        elif line.startswith("//", i):
            return line[:i].rstrip()
    return line


def parse_endpoint(text: str) -> tuple[str, str] | None:
    parts = re.findall(r'"[^"]+"|`[^`]+`|\([^)]*\)|[\w$]+', text.strip())
    if len(parts) < 2:
        return None
    col = parts[-1]
    if col.startswith("("):
        col = col[1:-1].split(",")[0]
    return strip_quotes(parts[-2]), strip_quotes(col.strip())


def parse_settings(text: str) -> dict:
    out: dict = {}
    for item in split_top(text):
        if ":" in item:
            k, v = item.split(":", 1)
            k = k.strip().lower()
            if k == "ref":
                out.setdefault("ref", []).append(v.strip())
            else:
                out[k] = strip_quotes(v.strip())
        elif item.strip():
            out[item.strip().lower()] = True
    return out


def _add_ref(schema: Schema, aliases: dict, left: str, op: str, right: str, settings: dict) -> None:
    left_ep, right_ep = parse_endpoint(left), parse_endpoint(right)
    if not left_ep or not right_ep:
        return
    left_ep = (aliases.get(left_ep[0], left_ep[0]), left_ep[1])
    right_ep = (aliases.get(right_ep[0], right_ep[0]), right_ep[1])
    if op == "<":
        left_ep, right_ep, op = right_ep, left_ep, ">"
    schema.refs.append(Ref(left_ep[0], left_ep[1], right_ep[0], right_ep[1], op, settings.get("color")))


def parse_dbml(text: str) -> Schema:
    schema = Schema()
    aliases: dict[str, str] = {}
    inline_refs: list[tuple[str, str, str]] = []
    pending_category: str | None = None
    pending_new: bool = False
    ctx: str | None = None
    cur_table: Table | None = None
    cur_group: tuple | None = None
    cur_enum: str | None = None
    skip_depth = 0
    note_sink = None  # (note_setter, note_buffer, terminator)

    def start_note(note_setter, first_line_rest, block=False):
        nonlocal note_sink
        line_rest = first_line_rest.strip()
        if not block and (line_rest.count("'''") != 1):
            note_setter(clean_note(line_rest))
            return True
        note_sink = (note_setter, [line_rest], "}" if block else "'''")
        return False

    for raw in normalize(text).splitlines():
        # collecting a multi-line note
        if note_sink:
            note_setter, note_buffer, terminator = note_sink
            stripped_line = raw.strip()
            if terminator == "'''" and "'''" in stripped_line:
                note_buffer.append(raw[:raw.find("'''") + 3])
                note_setter(clean_note("\n".join(note_buffer)))
                note_sink = None
            elif terminator == "}" and stripped_line == "}":
                note_setter(clean_note("\n".join(note_buffer)))
                note_sink = None
            else:
                note_buffer.append(raw)
            continue

        line = raw.strip()

        # //@ directives
        if line.startswith("//@"):
            parts = line[3:].split()
            if not parts:
                continue
            directive, rest = parts[0].lower(), line[3 + len(parts[0]):].strip()
            if directive == "title":
                schema.title = rest
            elif directive == "area":
                m = re.match(r"(.+?)\s+(#[0-9a-fA-F]{3,8})$", rest)
                if m:
                    schema.area_colors[m.group(1).strip().replace("_", " ")] = m.group(2)
            elif directive == "hub" and len(parts) >= 2:
                schema.hubs[parts[1]] = parts[2] if len(parts) > 2 else None
            elif directive == "category" and len(parts) >= 2:
                pending_category = parts[1].lower()
            elif directive == "new":
                pending_new = True
            continue

        line = strip_comment(line)
        if not line:
            continue

        # blocks we don't draw
        if ctx == "skip":
            if line.count("'''") == 1:
                note_sink = (lambda _v: None, [], "'''")
                continue
            skip_depth += line.count("{") - line.count("}")
            if skip_depth <= 0:
                ctx = "table" if cur_table else None
            continue

        # top level
        if ctx is None:
            m = re.match(rf"Project\s+({IDENT})", line, re.I)
            if m and not schema.title:
                schema.title = strip_quotes(m.group(1))
            if re.match(r"(Project|Note|TablePartial|Records|DiagramView)\b", line, re.I):
                if line.endswith("{"):
                    ctx, skip_depth = "skip", 1
                continue
            m = re.match(rf"Enum\s+((?:{IDENT}\.)?{IDENT})\s*\{{", line, re.I)
            if m:
                cur_enum = strip_quotes(m.group(1).split(".")[-1])
                schema.enums[cur_enum] = []
                ctx = "enum"
                continue
            m = re.match(
                rf"Table\s+((?:{IDENT}\.)?{IDENT})(?:\s+as\s+({IDENT}))?\s*(?:\[(.*?)\])?\s*\{{",
                line, re.I
            )
            if m:
                name = strip_quotes(re.split(r'\.(?=(?:[^"]*"[^"]*")*[^"]*$)', m.group(1))[-1])
                settings = parse_settings(m.group(3) or "")
                cur_table = Table(
                    name=name,
                    headercolor=settings.get("headercolor"),
                    is_new=pending_new,
                    note=clean_note(settings["note"]) if isinstance(settings.get("note"), str) else "",
                )
                if pending_category:
                    cur_table.category = CATEGORY_ALIASES.get(pending_category, pending_category)
                pending_category, pending_new = None, False
                if m.group(2):
                    aliases[strip_quotes(m.group(2))] = name
                schema.tables[name] = cur_table
                ctx = "table"
                continue
            m = re.match(rf"TableGroup\s+({IDENT})\s*(?:\[(.*?)\])?\s*\{{", line, re.I)
            if m:
                group_name = strip_quotes(m.group(1))
                cur_group = tuple(
                    p.replace("_", " ").strip()
                    for p in re.split(r"__|\s*/\s*", group_name)
                    if p.strip()
                )
                schema.groups.setdefault(cur_group, [])
                settings = parse_settings(m.group(2) or "")
                if settings.get("color"):
                    schema.group_colors.setdefault(cur_group[0], settings["color"])
                if isinstance(settings.get("note"), str):
                    schema.group_notes[cur_group] = clean_note(settings["note"])
                ctx = "group"
                continue
            m = re.match(r"Ref\b[^:{]*:\s*(.+?)\s*(<>|[<>-])\s*(.+?)\s*(?:\[(.*)\])?$", line, re.I)
            if m:
                _add_ref(schema, aliases, m.group(1), m.group(2), m.group(3), parse_settings(m.group(4) or ""))
                continue
            if re.match(r"Ref\b.*\{$", line, re.I):
                ctx = "ref"
            continue

        if ctx == "enum":
            if line == "}":
                ctx = None; continue
            m = re.match(rf"({IDENT})\s*(?:\[(.*)\])?$", line)
            if m:
                settings = parse_settings(m.group(2) or "")
                schema.enums[cur_enum].append(  # type: ignore[index]
                    (strip_quotes(m.group(1)), settings.get("note", "") if isinstance(settings.get("note"), str) else "")
                )
            continue

        if ctx == "ref":
            if line == "}":
                ctx = None; continue
            m = re.match(r"(.+?)\s*(<>|[<>-])\s*(.+?)\s*(?:\[(.*)\])?$", line)
            if m:
                _add_ref(schema, aliases, m.group(1), m.group(2), m.group(3), parse_settings(m.group(4) or ""))
            continue

        if ctx == "group":
            if line == "}":
                ctx, cur_group = None, None; continue
            m = re.match(r"note\s*:(.*)$", line, re.I)
            if m:
                g = cur_group
                start_note(lambda v, g=g: schema.group_notes.__setitem__(g, v), m.group(1))
                continue
            if re.match(r"note\s*\{$", line, re.I):
                g = cur_group
                start_note(lambda v, g=g: schema.group_notes.__setitem__(g, v), "", block=True)
                continue
            for tok in re.findall(r'"[^"]+"|`[^`]+`|[\w$.]+', line):
                schema.groups[cur_group].append(strip_quotes(tok.split(".")[-1]))  # type: ignore[index]
            continue

        if ctx == "indexes":
            if line == "}":
                ctx = "table"; continue
            m = re.match(r"\(?(.*?)\)?\s*\[(.*)\]\s*$", line)
            if m and re.search(r"\bpk\b|primary key", m.group(2), re.I):
                for cname in split_top(m.group(1)):
                    c = cur_table.col(strip_quotes(cname))  # type: ignore[union-attr]
                    if c:
                        c.pk = True
            continue

        if ctx == "table":
            if line == "}":
                ctx, cur_table = None, None; continue
            if re.match(r"indexes\s*\{$", line, re.I):
                ctx = "indexes"; continue
            if re.match(r"checks\s*\{$", line, re.I):
                ctx, skip_depth = "skip", 1; continue
            t = cur_table
            m = re.match(r"note\s*:(.*)$", line, re.I)
            if m:
                start_note(lambda v, t=t: setattr(t, "note", v), m.group(1)); continue
            if re.match(r"note\s*\{$", line, re.I):
                start_note(lambda v, t=t: setattr(t, "note", v), "", block=True); continue
            if line.startswith("~"):
                continue
            m = re.match(rf"({IDENT})\s+({TYPE})\s*(?:\[(.*)\])?\s*$", line)
            if m:
                settings = parse_settings(m.group(3) or "")
                c = Column(
                    name=strip_quotes(m.group(1)),
                    type=strip_quotes(m.group(2)),
                    pk=bool(settings.get("pk") or settings.get("primary key")),
                    not_null=bool(settings.get("not null")),
                    unique=bool(settings.get("unique")),
                    increment=bool(settings.get("increment")),
                    default=settings.get("default") if isinstance(settings.get("default"), str) else None,
                    note=clean_note(settings["note"]) if isinstance(settings.get("note"), str) else "",
                )
                t.columns.append(c)  # type: ignore[union-attr]
                for r in settings.get("ref", []):
                    inline_refs.append((t.name, c.name, r))  # type: ignore[union-attr]
            continue

    for tname, cname, rtext in inline_refs:
        m = re.match(r"(<>|[<>-])\s*(.+)$", rtext.strip())
        if m:
            _add_ref(schema, aliases, f"{tname}.{cname}", m.group(1), m.group(2), {})
    for r in schema.refs:
        t = schema.tables.get(r.child)
        if t and t.col(r.child_col):
            t.col(r.child_col).fk = True  # type: ignore[union-attr]
    return schema
