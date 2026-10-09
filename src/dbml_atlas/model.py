from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field


@dataclass
class Column:
    name: str
    type: str
    pk: bool = False
    not_null: bool = False
    unique: bool = False
    increment: bool = False
    fk: bool = False
    default: str | None = None
    note: str = ""


@dataclass
class Table:
    name: str
    columns: list = field(default_factory=list)
    headercolor: str | None = None
    category: str | None = None
    is_new: bool = False
    note: str = ""
    path: tuple = ()

    def col(self, name: str) -> Column | None:
        return next((c for c in self.columns if c.name == name), None)

    def col_index(self, name: str) -> int | None:
        return next((i for i, c in enumerate(self.columns) if c.name == name), None)


@dataclass
class Ref:
    child: str
    child_col: str
    parent: str
    parent_col: str
    kind: str = ">"
    color: str | None = None


@dataclass
class Schema:
    title: str = ""
    tables: OrderedDict = field(default_factory=OrderedDict)
    refs: list = field(default_factory=list)
    groups: OrderedDict = field(default_factory=OrderedDict)
    group_notes: dict = field(default_factory=dict)
    group_colors: dict = field(default_factory=dict)
    area_colors: dict = field(default_factory=dict)
    hubs: OrderedDict = field(default_factory=OrderedDict)
    enums: OrderedDict = field(default_factory=OrderedDict)
