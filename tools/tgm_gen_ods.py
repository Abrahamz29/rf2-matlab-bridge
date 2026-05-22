"""Inspect and reconstruct exports from the official Studio-397 TGM Gen ODS.

This is the first part of the MATLAB TGM Generator port: it treats the ODS as
the golden reference and extracts the generated text outputs without modifying
the workbook.
"""

from __future__ import annotations

import argparse
import math
import json
import re
import sys
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Callable, Iterable
from xml.etree import ElementTree as ET
from zipfile import ZipFile


DEFAULT_ODS = Path("tools/downloads/studio397/TGM Gen V0.33 - GY F1 1975 Front.ods")
DEFAULT_INPUT_SHEETS = [
    "General",
    "Geometry",
    "Construction",
    "Compound",
    "Realtime",
    "WLF",
    "ContactProps",
    "LoadSens",
    "Materials",
    "TBC",
]

NS = {
    "office": "urn:oasis:names:tc:opendocument:xmlns:office:1.0",
    "table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
    "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
    "chart": "urn:oasis:names:tc:opendocument:xmlns:chart:1.0",
    "svg": "urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0",
    "xlink": "http://www.w3.org/1999/xlink",
}

Q = {prefix: f"{{{uri}}}" for prefix, uri in NS.items()}


@dataclass
class Cell:
    text: str = ""
    value: str = ""
    formula: str = ""
    repeat: int = 1
    value_type: str = ""
    style_name: str = ""

    @property
    def display(self) -> str:
        return self.text if self.text != "" else self.value


@dataclass
class FormulaCell:
    sheet: str
    row: int
    col: int
    address: str
    display: str
    value: str
    formula: str
    value_type: str = ""
    style_name: str = ""


class FormulaEvaluationError(Exception):
    """Raised when a formula cannot yet be evaluated by the partial engine."""


class ExcelError:
    def __init__(self, code: str):
        self.code = code

    def __str__(self) -> str:
        return self.code

    def __repr__(self) -> str:
        return self.code

    def __bool__(self) -> bool:
        return False

    def __neg__(self) -> "ExcelError":
        return self

    def __add__(self, other: Any) -> "ExcelError":
        return self

    __radd__ = __add__
    __sub__ = __add__
    __rsub__ = __add__
    __mul__ = __add__
    __rmul__ = __add__
    __truediv__ = __add__
    __rtruediv__ = __add__
    __pow__ = __add__
    __rpow__ = __add__


class ExcelArray(list):
    def _binary(self, other: Any, op: Callable[[Any, Any], Any]) -> "ExcelArray":
        if isinstance(other, list):
            right = flatten(other)
            left = flatten(self)
            count = min(len(left), len(right))
            return ExcelArray([op(ExcelScalar(left[index]), ExcelScalar(right[index])) for index in range(count)])
        return ExcelArray([op(ExcelScalar(value), other) for value in flatten(self)])

    def __add__(self, other: Any) -> "ExcelArray":
        return self._binary(other, lambda a, b: a + b)

    def __radd__(self, other: Any) -> "ExcelArray":
        return ExcelArray([ExcelScalar(other) + ExcelScalar(value) for value in flatten(self)])

    def __sub__(self, other: Any) -> "ExcelArray":
        return self._binary(other, lambda a, b: a - b)

    def __rsub__(self, other: Any) -> "ExcelArray":
        return ExcelArray([ExcelScalar(other) - ExcelScalar(value) for value in flatten(self)])

    def __mul__(self, other: Any) -> "ExcelArray":
        return self._binary(other, lambda a, b: a * b)

    def __rmul__(self, other: Any) -> "ExcelArray":
        return ExcelArray([ExcelScalar(other) * ExcelScalar(value) for value in flatten(self)])

    def __truediv__(self, other: Any) -> "ExcelArray":
        return self._binary(other, lambda a, b: a / b)

    def __rtruediv__(self, other: Any) -> "ExcelArray":
        return ExcelArray([ExcelScalar(other) / ExcelScalar(value) for value in flatten(self)])

    def _compare(self, other: Any, op: Callable[[ExcelScalar, Any], bool]) -> "ExcelArray":
        if isinstance(other, list):
            right = flatten(other)
            left = flatten(self)
            count = min(len(left), len(right))
            return ExcelArray([op(ExcelScalar(left[index]), right[index]) for index in range(count)])
        return ExcelArray([op(ExcelScalar(value), other) for value in flatten(self)])

    def __lt__(self, other: Any) -> "ExcelArray":
        return self._compare(other, lambda a, b: a < b)

    def __le__(self, other: Any) -> "ExcelArray":
        return self._compare(other, lambda a, b: a <= b)

    def __gt__(self, other: Any) -> "ExcelArray":
        return self._compare(other, lambda a, b: a > b)

    def __ge__(self, other: Any) -> "ExcelArray":
        return self._compare(other, lambda a, b: a >= b)

    def __eq__(self, other: Any) -> "ExcelArray":  # type: ignore[override]
        return self._compare(other, lambda a, b: a == b)

    def __ne__(self, other: Any) -> "ExcelArray":  # type: ignore[override]
        return self._compare(other, lambda a, b: a != b)


class ExcelScalar:
    """Scalar wrapper with spreadsheet-like arithmetic and comparisons."""

    def __init__(
        self,
        value: Any,
        sheet: str | None = None,
        row: int | None = None,
        col: int | None = None,
        display: str | None = None,
    ):
        if isinstance(value, ExcelScalar):
            self.value = value.value
            self.sheet = value.sheet
            self.row = value.row
            self.col = value.col
            self.display = value.display
        else:
            self.value = value
            self.sheet = sheet
            self.row = row
            self.col = col
            self.display = display

    def __str__(self) -> str:
        return self.display if self.display not in (None, "") else format_excel_scalar(self.value)

    def __repr__(self) -> str:
        return repr(self.value)

    def __bool__(self) -> bool:
        return bool(self.value)

    def _num(self) -> float:
        if isinstance(self.value, ExcelError):
            raise FormulaEvaluationError(self.value.code)
        return to_number(self.value)

    def _other_num(self, other: Any) -> float:
        return to_number(unwrap_scalar(other))

    def _error_operand(self, other: Any = None) -> ExcelError | None:
        if isinstance(self.value, ExcelError):
            return self.value
        other = unwrap_scalar(other)
        if isinstance(other, ExcelError):
            return other
        return None

    def __neg__(self) -> float:
        error = self._error_operand()
        return error if error else ExcelScalar(-self._num())

    def __add__(self, other: Any) -> float:
        error = self._error_operand(other)
        if error:
            return error
        left = unwrap_scalar(self)
        if isinstance(left, str) and is_number_like(other):
            match = re.match(r"^(>=|<=|<>|>|<|=)([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)$", left)
            if match:
                return ExcelScalar(f"{match.group(1)}{to_number(match.group(2)) + self._other_num(other):g}")
            match = re.match(r"^(.*?)([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)$", left)
            if match:
                return ExcelScalar(f"{match.group(1)}{to_number(match.group(2)) + self._other_num(other):g}")
        if isinstance(unwrap_scalar(self), str) or isinstance(unwrap_scalar(other), str):
            return ExcelScalar(str(self) + format_excel_scalar(other))
        return ExcelScalar(self._num() + self._other_num(other))

    def __radd__(self, other: Any) -> float:
        error = self._error_operand(other)
        if error:
            return error
        if isinstance(unwrap_scalar(self), str) or isinstance(unwrap_scalar(other), str):
            return ExcelScalar(format_excel_scalar(other) + str(self))
        return ExcelScalar(self._other_num(other) + self._num())

    def __sub__(self, other: Any) -> float:
        error = self._error_operand(other)
        if error:
            return error
        left = unwrap_scalar(self)
        if isinstance(left, str) and left[:1] in (">", "<", "="):
            match = re.match(r"^(>=|<=|<>|>|<|=)([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)$", left)
            if match:
                return ExcelScalar(f"{match.group(1)}{to_number(match.group(2)) - self._other_num(other):g}")
        if isinstance(left, str):
            match = re.match(r"^(.*?)([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)$", left)
            if match:
                return ExcelScalar(f"{match.group(1)}{to_number(match.group(2)) - self._other_num(other):g}")
        return ExcelScalar(self._num() - self._other_num(other))

    def __rsub__(self, other: Any) -> float:
        error = self._error_operand(other)
        return error if error else ExcelScalar(self._other_num(other) - self._num())

    def __mul__(self, other: Any) -> float:
        error = self._error_operand(other)
        return error if error else ExcelScalar(self._num() * self._other_num(other))

    def __rmul__(self, other: Any) -> float:
        error = self._error_operand(other)
        return error if error else ExcelScalar(self._other_num(other) * self._num())

    def __truediv__(self, other: Any) -> float:
        error = self._error_operand(other)
        if error:
            return error
        denominator = self._other_num(other)
        if denominator == 0:
            return ExcelError("#DIV/0!")
        return ExcelScalar(self._num() / denominator)

    def __rtruediv__(self, other: Any) -> float:
        error = self._error_operand(other)
        if error:
            return error
        denominator = self._num()
        if denominator == 0:
            return ExcelError("#DIV/0!")
        return ExcelScalar(self._other_num(other) / denominator)

    def __pow__(self, other: Any) -> float:
        error = self._error_operand(other)
        return error if error else ExcelScalar(self._num() ** self._other_num(other))

    def __rpow__(self, other: Any) -> float:
        error = self._error_operand(other)
        return error if error else ExcelScalar(self._other_num(other) ** self._num())

    def __eq__(self, other: Any) -> bool:
        return unwrap_scalar(self) == unwrap_scalar(other)

    def _compare(self, other: Any, op: Callable[[float, float], bool], string_op: Callable[[str, str], bool]) -> bool:
        left = unwrap_scalar(self)
        right = unwrap_scalar(other)
        try:
            return op(to_number(left), to_number(right))
        except FormulaEvaluationError:
            if isinstance(left, str) and isinstance(right, str):
                return string_op(left, right)
            return False

    def __lt__(self, other: Any) -> bool:
        return self._compare(other, lambda a, b: a < b, lambda a, b: a < b)

    def __le__(self, other: Any) -> bool:
        return self._compare(other, lambda a, b: a <= b, lambda a, b: a <= b)

    def __gt__(self, other: Any) -> bool:
        return self._compare(other, lambda a, b: a > b, lambda a, b: a > b)

    def __ge__(self, other: Any) -> bool:
        return self._compare(other, lambda a, b: a >= b, lambda a, b: a >= b)


def unwrap_scalar(value: Any) -> Any:
    return value.value if isinstance(value, ExcelScalar) else value


def attr(element: ET.Element, namespace: str, name: str, default: str = "") -> str:
    return element.attrib.get(f"{Q[namespace]}{name}", default)


def read_xml(ods: Path, member: str) -> ET.Element:
    with ZipFile(ods) as zf:
        return ET.fromstring(zf.read(member))


def iter_tables(root: ET.Element) -> Iterable[ET.Element]:
    spreadsheet = root.find(".//office:spreadsheet", NS)
    if spreadsheet is None:
        return []
    return spreadsheet.findall("table:table", NS)


def table_name(table: ET.Element) -> str:
    return attr(table, "table", "name")


def cell_text(cell: ET.Element) -> str:
    parts: list[str] = []
    for paragraph in cell.findall(".//text:p", NS):
        parts.append("".join(paragraph.itertext()))
    return "\n".join(parts)


def cell_value(cell: ET.Element) -> str:
    for value_attr in ("string-value", "value", "date-value", "time-value", "boolean-value"):
        value = attr(cell, "office", value_attr)
        if value != "":
            return value
    return ""


def iter_row_cells(row: ET.Element) -> Iterable[tuple[int, Cell]]:
    col = 1
    covered_to_skip = 0
    for cell in list(row):
        if cell.tag == f"{Q['table']}covered-table-cell":
            if covered_to_skip > 0:
                covered_to_skip -= 1
                continue
            col += int(attr(cell, "table", "number-columns-repeated", "1"))
            continue
        if cell.tag != f"{Q['table']}table-cell":
            continue
        repeat = int(attr(cell, "table", "number-columns-repeated", "1"))
        span = int(attr(cell, "table", "number-columns-spanned", "1"))
        current = Cell(
            text=cell_text(cell),
            value=cell_value(cell),
            formula=attr(cell, "table", "formula"),
            repeat=1,
            value_type=attr(cell, "office", "value-type"),
            style_name=attr(cell, "table", "style-name"),
        )
        for _ in range(repeat):
            yield col, current
            col += span
            covered_to_skip += max(0, span - 1)


def get_cell_display(table: ET.Element, row_index: int, col_index: int) -> str:
    rows = table.findall("table:table-row", NS)
    expanded_row = 1
    target_row: ET.Element | None = None
    for row in rows:
        repeat = int(attr(row, "table", "number-rows-repeated", "1"))
        if expanded_row <= row_index < expanded_row + repeat:
            target_row = row
            break
        expanded_row += repeat
    if target_row is None:
        return ""

    for col, cell in iter_row_cells(target_row):
        if col <= col_index < col + cell.repeat:
            return cell.display
    return ""


def get_table(root: ET.Element, name: str) -> ET.Element:
    for table in iter_tables(root):
        if table_name(table) == name:
            return table
    raise KeyError(f"Sheet not found in ODS: {name}")


def col_to_index(col: str) -> int:
    value = 0
    for char in col.upper():
        if not ("A" <= char <= "Z"):
            raise ValueError(f"Invalid column name: {col}")
        value = value * 26 + ord(char) - ord("A") + 1
    return value


def index_to_col(index: int) -> str:
    if index < 1:
        raise ValueError(f"Column index must be >= 1: {index}")
    chars: list[str] = []
    while index:
        index, remainder = divmod(index - 1, 26)
        chars.append(chr(ord("A") + remainder))
    return "".join(reversed(chars))


def a1_to_row_col(address: str) -> tuple[int, int]:
    match = re.fullmatch(r"\$?([A-Za-z]+)\$?(\d+)", address.strip())
    if not match:
        raise ValueError(f"Unsupported cell address: {address}")
    return int(match.group(2)), col_to_index(match.group(1))


def row_col_to_a1(row: int, col: int) -> str:
    return f"{index_to_col(col)}{row}"


def parse_ref_endpoint(token: str, default_sheet: str) -> tuple[str, str]:
    token = token.strip().replace("$", "")
    if token.startswith("."):
        return default_sheet, token[1:]
    if "." in token:
        sheet, address = token.rsplit(".", 1)
        return sheet, address
    return default_sheet, token


def parse_ref_token(token: str, default_sheet: str) -> dict:
    token = token.strip()
    if ":" in token:
        left, right = token.split(":", 1)
        sheet, start = parse_ref_endpoint(left, default_sheet)
        right_sheet, end = parse_ref_endpoint(right, sheet)
        if right_sheet != sheet:
            raise ValueError(f"Cross-sheet ranges are not supported: {token}")
        return {"type": "range", "sheet": sheet, "start": start, "end": end}
    sheet, address = parse_ref_endpoint(token, default_sheet)
    return {"type": "cell", "sheet": sheet, "address": address}


def parse_scalar(value: str) -> Any:
    value = value.strip()
    if value == "":
        return ""
    if value.startswith("#") or value.startswith("Err:"):
        return ExcelError(value)
    if value == "#N/A":
        raise FormulaEvaluationError("#N/A")
    if "\n" in value:
        nonempty_lines = [line.strip() for line in value.splitlines() if line.strip()]
        if nonempty_lines:
            value = nonempty_lines[-1]
    fraction_prefix = re.match(r"^([-+]?\d+(?:\.\d+)?)/(\d+(?:\.\d+)?)\s*(?:[A-Za-z/%\"'°]+)?$", value)
    if fraction_prefix:
        return float(fraction_prefix.group(1)) / float(fraction_prefix.group(2))
    numeric_prefix = re.match(r"^([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)\s*(?:[A-Za-z/%\"'°]+)?$", value)
    if numeric_prefix:
        number_text = numeric_prefix.group(1)
        try:
            if re.fullmatch(r"[-+]?\d+", number_text):
                return int(number_text)
            return float(number_text)
        except ValueError:
            pass
    try:
        if re.fullmatch(r"[-+]?\d+", value):
            return int(value)
        return float(value)
    except ValueError:
        return value


def formula_display_for_cell(cell: FormulaCell) -> str:
    if cell.formula:
        return cell.display
    if cell.display.lstrip().startswith("+") and cell.value != "":
        try:
            if is_number_like(cell.display) and is_number_like(cell.value):
                if abs(to_number(cell.display) - to_number(cell.value)) <= 1e-12 * max(1.0, abs(to_number(cell.value))):
                    return cell.display
        except FormulaEvaluationError:
            pass
    if cell.value != "":
        return cell.value
    return format_excel_scalar(parse_scalar(cell.display)) if "\n" in cell.display else cell.display


def recursive_display_for_cell(cell: FormulaCell, value: Any) -> str:
    """Text form for references to recursively evaluated formula cells.

    Calc concatenation uses the stored numeric cell value more often than the
    shortened visible display. If our recomputed numeric value is only different
    by floating point noise, keep the ODS value text so strict exports do not
    drift by a final digit.
    """
    if cell.value != "":
        if str(cell.value).lstrip().startswith("+") and format_excel_scalar(value).lstrip("+") == str(cell.value).lstrip("+"):
            return cell.value
        try:
            stored = parse_scalar(cell.value)
            if is_number_like(stored) and is_number_like(value):
                expected = to_number(stored)
                actual = to_number(value)
                scale = max(1.0, abs(expected))
                if abs(expected - actual) <= 1e-12 * scale:
                    return format_excel_scalar(stored)
        except FormulaEvaluationError:
            pass
    return format_excel_scalar(value)


def flatten(values: Iterable[Any]) -> list[Any]:
    flattened: list[Any] = []
    for value in values:
        if isinstance(value, list):
            flattened.extend(flatten(value))
        else:
            flattened.append(value)
    return flattened


def to_number(value: Any) -> float:
    value = unwrap_scalar(value)
    if isinstance(value, ExcelError):
        raise FormulaEvaluationError(value.code)
    if value == "":
        return 0.0
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    parsed = parse_scalar(str(value))
    if isinstance(parsed, (int, float)):
        return float(parsed)
    try:
        return float(str(value))
    except ValueError as exc:
        raise FormulaEvaluationError(f"Expected numeric value, got {value!r}") from exc


def format_excel_scalar(value: Any) -> str:
    if isinstance(value, ExcelScalar):
        if value.display not in (None, ""):
            return value.display
        value = value.value
    value = unwrap_scalar(value)
    if isinstance(value, ExcelError):
        return value.code
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if math.isnan(value):
            return "#N/A"
        if math.isinf(value):
            return "#DIV/0!"
        return f"{value:.15g}"
    return str(value)


def format_excel_sci(value: Any, format_code: str = "#.##e#") -> str:
    numeric = to_number(value)
    if numeric == 0:
        return "0e0"
    mantissa_pattern = format_code.lower().split("e", 1)[0]
    decimals = len(mantissa_pattern.split(".", 1)[1]) if "." in mantissa_pattern else 0
    mantissa, exponent = f"{numeric:.{decimals}e}".split("e")
    mantissa = mantissa.rstrip("0").rstrip(".")
    exponent_int = int(exponent)
    return f"{mantissa}e{exponent_int}"


def replace_semicolons_outside_strings(text: str) -> str:
    out: list[str] = []
    in_string = False
    index = 0
    while index < len(text):
        char = text[index]
        if char == '"':
            out.append(char)
            if index + 1 < len(text) and text[index + 1] == '"':
                out.append(text[index + 1])
                previous_significant = '"'
                index += 2
                continue
            in_string = not in_string
        elif char == ";" and not in_string:
            out.append(",")
        else:
            out.append(char)
        index += 1
    return "".join(out)


def escape_newlines_in_strings(text: str) -> str:
    out: list[str] = []
    in_string = False
    index = 0
    while index < len(text):
        char = text[index]
        if char == '"':
            out.append(char)
            if index + 1 < len(text) and text[index + 1] == '"':
                out.append(text[index + 1])
                index += 2
                continue
            in_string = not in_string
        elif in_string and char in "\r\n":
            if char == "\r" and index + 1 < len(text) and text[index + 1] == "\n":
                index += 1
            out.append("\\n")
        else:
            out.append(char)
        index += 1
    return "".join(out)


def replace_ampersands_outside_strings(text: str) -> str:
    out: list[str] = []
    in_string = False
    index = 0
    while index < len(text):
        char = text[index]
        if char == '"':
            out.append(char)
            if index + 1 < len(text) and text[index + 1] == '"':
                out.append(text[index + 1])
                previous_significant = char
                index += 2
                continue
            in_string = not in_string
        elif char == "&" and not in_string:
            out.append("+")
        else:
            out.append(char)
        index += 1
    return "".join(out)


def fill_empty_arguments(text: str) -> str:
    out: list[str] = []
    in_string = False
    previous_significant = ""
    index = 0
    while index < len(text):
        char = text[index]
        if char == '"':
            out.append(char)
            if index + 1 < len(text) and text[index + 1] == '"':
                out.append(text[index + 1])
                previous_significant = char
                index += 2
                continue
            in_string = not in_string
            previous_significant = char
            index += 1
            continue
        if not in_string and char == "," and previous_significant in ("(", ","):
            out.append('""')
        if not in_string and char == ")" and previous_significant == ",":
            out.append('""')
        out.append(char)
        if not char.isspace():
            previous_significant = char
        index += 1
    return "".join(out)


def replace_equals_outside_strings(text: str) -> str:
    out: list[str] = []
    in_string = False
    index = 0
    while index < len(text):
        char = text[index]
        if char == '"':
            out.append(char)
            if index + 1 < len(text) and text[index + 1] == '"':
                out.append(text[index + 1])
                index += 2
                continue
            in_string = not in_string
        elif char == "<" and not in_string and index + 1 < len(text) and text[index + 1] == ">":
            out.append("!=")
            index += 2
            continue
        elif char == "=" and not in_string:
            prev_char = text[index - 1] if index > 0 else ""
            next_char = text[index + 1] if index + 1 < len(text) else ""
            if prev_char in "<>!=" or next_char == "=":
                out.append(char)
            else:
                out.append("==")
        else:
            out.append(char)
        index += 1
    return "".join(out)


def find_matching_paren(text: str, open_index: int) -> int:
    depth = 0
    in_string = False
    index = open_index
    while index < len(text):
        char = text[index]
        if char == '"':
            if index + 1 < len(text) and text[index + 1] == '"':
                index += 2
                continue
            in_string = not in_string
        elif not in_string:
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    return index
        index += 1
    raise FormulaEvaluationError("Unbalanced parentheses")


def split_top_level_args(text: str) -> list[str]:
    args: list[str] = []
    start = 0
    depth = 0
    in_string = False
    index = 0
    while index < len(text):
        char = text[index]
        if char == '"':
            if index + 1 < len(text) and text[index + 1] == '"':
                index += 2
                continue
            in_string = not in_string
        elif not in_string:
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
            elif char == "," and depth == 0:
                args.append(text[start:index].strip())
                start = index + 1
        index += 1
    args.append(text[start:].strip())
    return args


def transform_lazy_functions(expr: str) -> str:
    index = 0
    out: list[str] = []
    while index < len(expr):
        matched = False
        for name in ("IFERROR", "IF"):
            prefix = f"{name}("
            if expr.startswith(prefix, index) and (index == 0 or not (expr[index - 1].isalnum() or expr[index - 1] == "_")):
                open_index = index + len(name)
                close_index = find_matching_paren(expr, open_index)
                inner = expr[open_index + 1 : close_index]
                args = [transform_lazy_functions(arg) for arg in split_top_level_args(inner)]
                if name == "IFERROR" and len(args) >= 2:
                    out.append(f"IFERROR(lambda: ({args[0]}), lambda: ({args[1]}))")
                elif name == "IF" and len(args) >= 2:
                    false_arg = args[2] if len(args) >= 3 else '""'
                    out.append(f"IF(lambda: ({args[0]}), lambda: ({args[1]}), lambda: ({false_arg}))")
                else:
                    out.append(expr[index : close_index + 1])
                index = close_index + 1
                matched = True
                break
        if not matched:
            out.append(expr[index])
            index += 1
    return "".join(out)


def replace_refs_outside_strings(expr: str, current_sheet: str) -> str:
    out: list[str] = []
    in_string = False
    index = 0
    while index < len(expr):
        char = expr[index]
        if char == '"':
            out.append(char)
            if index + 1 < len(expr) and expr[index + 1] == '"':
                out.append(expr[index + 1])
                index += 2
                continue
            in_string = not in_string
            index += 1
            continue
        if not in_string and char == "[":
            close_index = expr.find("]", index + 1)
            if close_index == -1:
                raise FormulaEvaluationError("Unbalanced reference token")
            ref = parse_ref_token(expr[index + 1 : close_index], current_sheet)
            if ref["type"] == "cell":
                out.append(f'REF("{ref["sheet"]}","{ref["address"]}")')
            else:
                out.append(f'RANGE("{ref["sheet"]}","{ref["start"]}","{ref["end"]}")')
            index = close_index + 1
            continue
        out.append(char)
        index += 1
    return "".join(out)


def load_formula_cells(ods: Path) -> dict[tuple[str, int, int], FormulaCell]:
    root = read_xml(ods, "content.xml")
    cells: dict[tuple[str, int, int], FormulaCell] = {}

    for table in iter_tables(root):
        sheet = table_name(table)
        row_index = 1
        for row in table.findall("table:table-row", NS):
            row_repeat = int(attr(row, "table", "number-rows-repeated", "1"))
            col_index = 1
            row_cells = list(iter_row_cells(row))
            for col, cell in row_cells:
                if cell.display == "" and not cell.formula:
                    continue
                for offset in range(cell.repeat):
                    target_col = col + offset
                    cells[(sheet, row_index, target_col)] = FormulaCell(
                        sheet=sheet,
                        row=row_index,
                        col=target_col,
                        address=row_col_to_a1(row_index, target_col),
                        display=cell.display,
                        value=cell.value,
                        formula=cell.formula,
                        value_type=cell.value_type,
                        style_name=cell.style_name,
                    )
                col_index = col + cell.repeat
            row_index += row_repeat
    return cells


def load_named_ranges(ods: Path) -> dict[str, dict[str, str]]:
    root = read_xml(ods, "content.xml")
    ranges: dict[str, dict[str, str]] = {}
    for named_range in root.findall(".//table:named-range", NS):
        name = attr(named_range, "table", "name")
        address = attr(named_range, "table", "cell-range-address").replace("$", "")
        if not name or not address or ":" not in address:
            continue
        start_token, end_token = address.split(":", 1)
        sheet, start = parse_ref_endpoint(start_token, "")
        end_sheet, end = parse_ref_endpoint(end_token, sheet)
        ranges[name] = {"sheet": sheet, "start": start, "end": end, "end_sheet": end_sheet}
    return ranges


def refs_in_formula(formula: str, current_sheet: str) -> list[dict]:
    refs = []
    for match in re.finditer(r"\[([^\]]+)\]", formula):
        try:
            refs.append(parse_ref_token(match.group(1), current_sheet))
        except ValueError:
            refs.append({"type": "unsupported", "token": match.group(1)})
    return refs


def functions_in_formula(formula: str) -> set[str]:
    return {
        match.group(1).replace("COM.MICROSOFT.", "")
        for match in re.finditer(r"(?<![A-Za-z0-9_\.])((?:COM\.MICROSOFT\.)?[A-Z][A-Z0-9_]*)\s*\(", formula)
    }


def implemented_formula_functions() -> set[str]:
    return {
        "ABS",
        "ACOS",
        "ADDRESS",
        "AND",
        "ASIN",
        "ATAN",
        "ATAN2",
        "AVERAGE",
        "AVERAGEIF",
        "CEILING",
        "CHAR",
        "CONCAT",
        "COS",
        "COUNT",
        "COUNTIF",
        "CUBSPLINE",
        "DEGREES",
        "ERF",
        "FLOOR",
        "HLOOKUP",
        "IF",
        "IFERROR",
        "INDIRECT",
        "INDEX",
        "ISBLANK",
        "ISNUMBER",
        "ISODD",
        "ISTEXT",
        "LINEST",
        "LOG",
        "LOOKUP",
        "MATCH",
        "MAX",
        "MEDIAN",
        "MIN",
        "MOD",
        "MROUND",
        "NOT",
        "OR",
        "PI",
        "POWER",
        "QUARTILE",
        "RADIANS",
        "ROUND",
        "ROUNDDOWN",
        "ROW",
        "SIN",
        "SLOPE",
        "SQRT",
        "SUM",
        "SUMIF",
        "SUMIFS",
        "SUMPRODUCT",
        "TAN",
        "TEXT",
        "TEXTJOIN",
        "TIME",
        "TRANSPOSE",
        "VLOOKUP",
    }


def normalize_formula(formula: str, current_sheet: str) -> str:
    expr = formula
    if expr.startswith("of:="):
        expr = expr[4:]
    expr = expr.replace("COM.MICROSOFT.", "")
    expr = escape_newlines_in_strings(expr)

    expr = replace_refs_outside_strings(expr, current_sheet)
    expr = replace_semicolons_outside_strings(expr)
    expr = fill_empty_arguments(expr)
    expr = replace_ampersands_outside_strings(expr)
    expr = replace_equals_outside_strings(expr)
    expr = expr.replace("^", "**")
    expr = transform_lazy_functions(expr)
    return expr


class CachedFormulaEvaluator:
    """Partial ODS formula evaluator using stored ODS values for dependencies."""

    def __init__(self, cells: dict[tuple[str, int, int], FormulaCell], named_ranges: dict[str, dict[str, str]] | None = None):
        self.cells = cells
        self.named_ranges = named_ranges or {}
        self.named_range_cache: dict[str, ExcelArray] = {}
        self.current_sheet = ""
        self.current_row = 1
        self.current_col = 1

    def ref(self, sheet: str, address: str) -> Any:
        row, col = a1_to_row_col(address)
        cell = self.cells.get((sheet, row, col))
        if sheet == "General" and address.upper().replace("$", "") == "I47" and cell and "Filename used by Macro" in cell.display:
            cell = self.cells.get((sheet, row, col - 1), cell)
        if sheet == "General" and address.upper().replace("$", "") == "I47" and cell and cell.display.startswith("←"):
            cell = self.cells.get((sheet, row, col - 1), cell)
        if cell is None:
            return ExcelScalar("", sheet=sheet, row=row, col=col, display="")
        display = formula_display_for_cell(cell)
        return ExcelScalar(parse_scalar(cell.value if cell.value != "" else cell.display), sheet=sheet, row=row, col=col, display=display)

    def range_values(self, sheet: str, start: str, end: str) -> list[Any]:
        start_row, start_col = a1_to_row_col(start)
        end_row, end_col = a1_to_row_col(end)
        rows: list[list[Any]] = []
        for row in range(min(start_row, end_row), max(start_row, end_row) + 1):
            row_values: list[Any] = []
            for col in range(min(start_col, end_col), max(start_col, end_col) + 1):
                cell = self.cells.get((sheet, row, col))
                display = formula_display_for_cell(cell) if cell else ""
                row_values.append(
                    ExcelScalar(
                        parse_scalar((cell.value if cell.value != "" else cell.display)) if cell else "",
                        sheet=sheet,
                        row=row,
                        col=col,
                        display=display,
                    )
                )
            rows.append(row_values)
        if len(rows) == 1:
            return ExcelArray(rows[0])
        if rows and len(rows[0]) == 1:
            return ExcelArray([row[0] for row in rows])
        return ExcelArray(rows)

    def evaluate(self, cell: FormulaCell) -> Any:
        if not cell.formula:
            return parse_scalar(cell.display)
        expr = normalize_formula(cell.formula, cell.sheet)
        env = self.env()
        self.current_sheet = cell.sheet
        self.current_row = cell.row
        self.current_col = cell.col
        try:
            globals_env = {"__builtins__": {}, **env}
            value = eval(expr, globals_env, {})  # noqa: S307 - restricted env for local ODS formulas.
            if isinstance(value, list):
                values = flatten(value)
                return values[0] if values else ""
            return value
        except Exception as exc:
            raise FormulaEvaluationError(str(exc)) from exc

    def env(self) -> dict[str, Callable | float]:
        env = {
            "REF": self.ref,
            "RANGE": self.range_values,
            "ABS": lambda x: abs(to_number(x)),
            "ACOS": lambda x: excel_unary(x, math.acos),
            "ADDRESS": excel_address,
            "AND": lambda *args: all(bool(arg) for arg in args),
            "ASIN": lambda x: excel_unary(x, math.asin),
            "ATAN": lambda x: excel_unary(x, math.atan),
            # ODS/Calc ATAN2 takes (x; y), while Python's atan2 takes (y, x).
            "ATAN2": lambda x, y: excel_binary(y, x, math.atan2),
            "AVERAGE": lambda *args: excel_average(*args),
            "AVERAGEIF": excel_averageif,
            "CEILING": lambda x, significance=1: math.ceil(to_number(x) / to_number(significance)) * to_number(significance),
            "CHAR": lambda x: chr(int(to_number(x))),
            "CONCAT": lambda *args: "".join(format_excel_scalar(arg) for arg in flatten(args)),
            "COS": lambda x: excel_unary(x, math.cos),
            "COUNT": lambda *args: sum(1 for value in flatten(args) if is_number_like(value)),
            "COUNTIF": excel_countif,
            "CUBSPLINE": excel_cubspline,
            "DEGREES": lambda x: excel_unary(x, math.degrees),
            "ERF": lambda x: excel_unary(x, math.erf),
            "FLOOR": lambda x, significance=1: math.floor(to_number(x) / to_number(significance)) * to_number(significance),
            "HLOOKUP": excel_hlookup,
            "IF": excel_if,
            "IFERROR": excel_iferror,
            "INDIRECT": self.indirect,
            "INDEX": excel_index,
            "ISBLANK": lambda x: x == "",
            "ISNUMBER": is_number_like,
            "ISODD": lambda x: int(to_number(x)) % 2 == 1,
            "ISTEXT": lambda x: isinstance(x, str) and x != "",
            "LINEST": excel_linest,
            "LOG": excel_log,
            "LOOKUP": excel_lookup,
            "MATCH": excel_match,
            "MAX": lambda *args: max(to_number(value) for value in flatten(args) if value != "" and is_number_like(value)),
            "MEDIAN": excel_median,
            "MIN": lambda *args: min(to_number(value) for value in flatten(args) if value != "" and is_number_like(value)),
            "MOD": lambda x, y: to_number(x) % to_number(y),
            "MROUND": lambda x, multiple: round(to_number(x) / to_number(multiple)) * to_number(multiple),
            "NOT": lambda x: not bool(x),
            "OR": lambda *args: any(bool(arg) for arg in args),
            "PI": lambda: math.pi,
            "POWER": lambda x, y: to_number(x) ** to_number(y),
            "QUARTILE": excel_quartile,
            "RADIANS": lambda x: excel_unary(x, math.radians),
            "ROUND": excel_round,
            "ROUNDDOWN": excel_rounddown,
            "ROW": lambda value=None: value.row if isinstance(value, ExcelScalar) and value.row is not None else self.current_row,
            "SIN": lambda x: excel_unary(x, math.sin),
            "SLOPE": excel_slope,
            "SQRT": lambda x: excel_unary(x, math.sqrt),
            "SUM": lambda *args: sum(to_number(value) for value in flatten(args) if value != "" and is_number_like(value)),
            "SUMIF": excel_sumif,
            "SUMIFS": excel_sumifs,
            "SUMPRODUCT": excel_sumproduct,
            "TAN": lambda x: excel_unary(x, math.tan),
            "TEXT": excel_text,
            "TEXTJOIN": excel_textjoin,
            "TIME": lambda hour, minute, second: (to_number(hour) * 3600 + to_number(minute) * 60 + to_number(second)) / 86400,
            "TRANSPOSE": excel_transpose,
            "VLOOKUP": excel_vlookup,
        }
        for name, named_range in self.named_ranges.items():
            if name not in self.named_range_cache:
                self.named_range_cache[name] = self.range_values(named_range["sheet"], named_range["start"], named_range["end"])
            env[name] = self.named_range_cache[name]
        return env

    def indirect(self, reference: Any, *args: Any) -> Any:
        ref_text = str(reference).strip().replace("$", "")
        if ref_text.startswith("[") and ref_text.endswith("]"):
            ref_text = ref_text[1:-1]
        if "!" in ref_text:
            sheet, address = ref_text.split("!", 1)
        elif "." in ref_text:
            sheet, address = ref_text.rsplit(".", 1)
        else:
            sheet, address = self.current_sheet, ref_text
        if ":" in address:
            start, end = address.split(":", 1)
            return self.range_values(sheet, start, end)
        return self.ref(sheet, address)


class RecursiveFormulaEvaluator(CachedFormulaEvaluator):
    """ODS evaluator that recursively recalculates referenced formula cells."""

    def __init__(
        self,
        cells: dict[tuple[str, int, int], FormulaCell],
        named_ranges: dict[str, dict[str, str]] | None = None,
        overrides: dict[tuple[str, int, int], Any] | None = None,
        fallback_on_error: bool = False,
    ):
        super().__init__(cells, named_ranges)
        self.cache: dict[tuple[str, int, int], Any] = {}
        self.stack: list[tuple[str, int, int]] = []
        self.overrides = overrides or {}
        self.fallback_on_error = fallback_on_error
        self.fallback_count = 0
        self.fallback_cells: list[str] = []

    def ref(self, sheet: str, address: str) -> Any:
        row, col = a1_to_row_col(address)
        key = (sheet, row, col)
        if key in self.overrides:
            return ExcelScalar(self.overrides[key], sheet=sheet, row=row, col=col, display=format_excel_scalar(self.overrides[key]))
        cell = self.cells.get(key)
        if sheet == "General" and address.upper().replace("$", "") == "I47" and cell and "Filename used by Macro" in cell.display:
            col -= 1
            key = (sheet, row, col)
            cell = self.cells.get(key, cell)
        if sheet == "General" and address.upper().replace("$", "") == "I47" and cell and cell.display.startswith("â†"):
            col -= 1
            key = (sheet, row, col)
            cell = self.cells.get(key, cell)
        if cell is None:
            return ExcelScalar("", sheet=sheet, row=row, col=col, display="")
        if key in self.stack:
            return ExcelScalar(parse_scalar(cell.value if cell.value != "" else cell.display), sheet=sheet, row=row, col=col, display=cell.display)
        if cell.formula:
            value = self.evaluate(cell)
            return ExcelScalar(value, sheet=sheet, row=row, col=col, display=recursive_display_for_cell(cell, value))
        display = formula_display_for_cell(cell)
        return ExcelScalar(parse_scalar(cell.value if cell.value != "" else cell.display), sheet=sheet, row=row, col=col, display=display)

    def range_values(self, sheet: str, start: str, end: str) -> list[Any]:
        start_row, start_col = a1_to_row_col(start)
        end_row, end_col = a1_to_row_col(end)
        rows: list[list[Any]] = []
        for row in range(min(start_row, end_row), max(start_row, end_row) + 1):
            row_values: list[Any] = []
            for col in range(min(start_col, end_col), max(start_col, end_col) + 1):
                row_values.append(self.ref(sheet, row_col_to_a1(row, col)))
            rows.append(row_values)
        if len(rows) == 1:
            return ExcelArray(rows[0])
        if rows and len(rows[0]) == 1:
            return ExcelArray([row[0] for row in rows])
        return ExcelArray(rows)

    def evaluate(self, cell: FormulaCell) -> Any:
        key = (cell.sheet, cell.row, cell.col)
        if key in self.overrides:
            return self.overrides[key]
        if not cell.formula:
            return parse_scalar(cell.value if cell.value != "" else cell.display)
        if key in self.cache:
            return self.cache[key]
        if key in self.stack:
            raise FormulaEvaluationError(f"Circular formula reference at {cell.sheet}!{cell.address}")
        previous_sheet = self.current_sheet
        previous_row = self.current_row
        previous_col = self.current_col
        self.stack.append(key)
        try:
            value = super().evaluate(cell)
            self.cache[key] = value
            return value
        except FormulaEvaluationError:
            if not self.fallback_on_error:
                raise
            value = parse_scalar(cell.value if cell.value != "" else cell.display)
            self.cache[key] = value
            self.fallback_count += 1
            if len(self.fallback_cells) < 100:
                self.fallback_cells.append(f"{cell.sheet}!{cell.address}")
            return value
        finally:
            self.stack.pop()
            self.current_sheet = previous_sheet
            self.current_row = previous_row
            self.current_col = previous_col


def make_evaluator(
    ods: Path,
    cells: dict[tuple[str, int, int], FormulaCell],
    mode: str = "cached",
    overrides: dict[tuple[str, int, int], Any] | None = None,
    fallback_on_error: bool = False,
) -> CachedFormulaEvaluator:
    named_ranges = load_named_ranges(ods)
    if mode == "cached":
        return CachedFormulaEvaluator(cells, named_ranges)
    if mode == "recursive":
        return RecursiveFormulaEvaluator(cells, named_ranges, overrides=overrides, fallback_on_error=fallback_on_error)
    raise ValueError(f"Unsupported evaluator mode: {mode}")


def is_number_like(value: Any) -> bool:
    try:
        to_number(value)
        return value != ""
    except FormulaEvaluationError:
        return False


def excel_error_from_exception(exc: Exception) -> ExcelError:
    text = str(exc)
    if text.startswith("#"):
        return ExcelError(text)
    return ExcelError("#VALUE!")


def excel_if(condition_func: Callable[[], Any], true_func: Callable[[], Any], false_func: Callable[[], Any] | None = None) -> Any:
    try:
        condition = condition_func()
        if isinstance(unwrap_scalar(condition), ExcelError):
            return condition
        if isinstance(condition, list):
            true_value = true_func()
            false_value = false_func() if false_func else ""
            true_values = flatten(true_value) if isinstance(true_value, list) else None
            false_values = flatten(false_value) if isinstance(false_value, list) else None
            result = []
            for index, item in enumerate(flatten(condition)):
                if bool(item):
                    result.append(true_values[index] if true_values is not None and index < len(true_values) else true_value)
                else:
                    result.append(false_values[index] if false_values is not None and index < len(false_values) else false_value)
            return ExcelArray(result)
        return true_func() if bool(condition) else (false_func() if false_func else "")
    except FormulaEvaluationError as exc:
        return excel_error_from_exception(exc)


def excel_iferror(value_func: Callable[[], Any], fallback_func: Callable[[], Any]) -> Any:
    try:
        value = value_func()
        if isinstance(unwrap_scalar(value), ExcelError):
            return fallback_func()
        return value
    except (FormulaEvaluationError, ZeroDivisionError, ValueError):
        return fallback_func()


def excel_unary(value: Any, func: Callable[[float], float]) -> float | ExcelError:
    try:
        return func(to_number(value))
    except (FormulaEvaluationError, ValueError, ZeroDivisionError) as exc:
        return excel_error_from_exception(exc)


def excel_binary(left: Any, right: Any, func: Callable[[float, float], float]) -> float | ExcelError:
    try:
        return func(to_number(left), to_number(right))
    except (FormulaEvaluationError, ValueError, ZeroDivisionError) as exc:
        return excel_error_from_exception(exc)


def excel_round(value: Any, digits: Any = 0) -> float | ExcelError:
    try:
        if isinstance(value, list):
            return ExcelArray([excel_round(item, digits) for item in flatten(value)])
        digit_count = int(to_number(digits))
        quantum = Decimal("1").scaleb(-digit_count)
        return float(Decimal(str(to_number(value))).quantize(quantum, rounding=ROUND_HALF_UP))
    except (FormulaEvaluationError, ValueError) as exc:
        return excel_error_from_exception(exc)


def excel_rounddown(value: Any, digits: Any = 0) -> float | ExcelError:
    try:
        if isinstance(value, list):
            return ExcelArray([excel_rounddown(item, digits) for item in flatten(value)])
        scale = 10 ** int(to_number(digits))
        return math.trunc(to_number(value) * scale) / scale
    except (FormulaEvaluationError, ValueError) as exc:
        return excel_error_from_exception(exc)


def excel_average(*args: Any) -> float:
    numbers = [to_number(value) for value in flatten(args) if value != "" and is_number_like(value)]
    if not numbers:
        return ExcelError("#DIV/0!")
    return sum(numbers) / len(numbers)


def excel_lookup(value: Any, lookup_vector: list[Any], result_vector: list[Any] | None = None) -> Any:
    value = unwrap_scalar(value)
    lookup_vector = flatten(lookup_vector)
    result_vector = lookup_vector if result_vector is None else flatten(result_vector)
    if isinstance(value, str):
        for lookup, result in zip(lookup_vector, result_vector):
            if lookup == value:
                return result
        raise FormulaEvaluationError(f"LOOKUP did not find {value!r}")
    numeric_value = to_number(value)
    best = None
    for lookup, result in zip(lookup_vector, result_vector):
        if lookup == "" or not is_number_like(lookup):
            continue
        if to_number(lookup) <= numeric_value:
            best = result
    if best is None:
        raise FormulaEvaluationError(f"LOOKUP did not find numeric value {value!r}")
    return best


def excel_address(row: Any, col: Any, abs_num: Any = 1, a1: Any = 1, sheet: Any = "") -> str:
    address = row_col_to_a1(int(to_number(row)), int(to_number(col)))
    sheet_name = str(unwrap_scalar(sheet)).strip()
    return f"{sheet_name}.{address}" if sheet_name else address


def comparable_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(unwrap_scalar(value)).replace("\u2013", "-").replace("\u2014", "-")).strip().lower()


def excel_match(value: Any, lookup_vector: list[Any], match_type: int = 1) -> int:
    raw_value = value
    value = unwrap_scalar(value)
    lookup_vector = flatten(lookup_vector)
    match_mode = int(to_number(match_type))
    if isinstance(raw_value, list):
        truth_values = [bool(unwrap_scalar(item)) for item in flatten(raw_value)]
        if match_mode == -1:
            for index, item in enumerate(truth_values, start=1):
                if item:
                    return max(1, index - 1)
        else:
            for index, item in enumerate(truth_values, start=1):
                if item:
                    return index
        raise FormulaEvaluationError("MATCH did not find TRUE in array expression")
    if match_mode == 0:
        for index, item in enumerate(lookup_vector, start=1):
            if item == value:
                return index
        if isinstance(value, str):
            needle = comparable_text(value)
            for index, item in enumerate(lookup_vector, start=1):
                haystack = comparable_text(item)
                if needle and (needle == haystack or needle in haystack or haystack in needle):
                    return index
        raise FormulaEvaluationError(f"MATCH did not find {value!r}")
    best_index = None
    if isinstance(value, str):
        for index, item in enumerate(lookup_vector, start=1):
            if item == value:
                return index
        needle = comparable_text(value)
        for index, item in enumerate(lookup_vector, start=1):
            haystack = comparable_text(item)
            if needle and (needle == haystack or needle in haystack or haystack in needle):
                return index
        raise FormulaEvaluationError(f"MATCH did not find {value!r}")
    numeric_value = to_number(value)
    for index, item in enumerate(lookup_vector, start=1):
        if item != "" and is_number_like(item) and to_number(item) <= numeric_value:
            best_index = index
    if best_index is None:
        raise FormulaEvaluationError(f"MATCH did not find {value!r}")
    return best_index


def excel_index(values: list[Any], row_num: int, col_num: int = 1) -> Any:
    row_index = int(to_number(row_num)) - 1
    col_index = int(to_number(col_num)) - 1
    if values and isinstance(values[0], list):
        return values[row_index][col_index]
    if col_index != 0:
        raise FormulaEvaluationError("INDEX on vector only supports col_num=1")
    return values[row_index]


def excel_hlookup(value: Any, table: list[Any], row_index: int, approximate: bool = True) -> Any:
    row_index = int(to_number(row_index))
    if not table or not isinstance(table[0], list):
        if row_index != 1:
            raise FormulaEvaluationError("HLOOKUP table shape support is not complete yet")
        return excel_lookup(value, table, table) if approximate else table[excel_match(value, table, 0) - 1]
    first_row = table[0]
    match_index = excel_match(value, first_row, 1 if bool(approximate) else 0) - 1
    return table[row_index - 1][match_index]


def excel_vlookup(value: Any, table: list[Any], col_index: int, approximate: bool = True) -> Any:
    col_index = int(to_number(col_index))
    if not table or not isinstance(table[0], list):
        if col_index != 1:
            raise FormulaEvaluationError("VLOOKUP table shape support is not complete yet")
        return excel_lookup(value, table, table) if approximate else table[excel_match(value, table, 0) - 1]
    first_col = [row[0] if row else "" for row in table]
    match_index = excel_match(value, first_col, 1 if bool(approximate) else 0) - 1
    return table[match_index][col_index - 1]


def excel_median(*args: Any) -> float:
    numbers = sorted(to_number(value) for value in flatten(args) if value != "" and is_number_like(value))
    if not numbers:
        raise FormulaEvaluationError("MEDIAN has no numeric values")
    middle = len(numbers) // 2
    if len(numbers) % 2:
        return numbers[middle]
    return (numbers[middle - 1] + numbers[middle]) / 2


def excel_log(x: Any, base: Any = math.e) -> float | ExcelError:
    try:
        x_num = to_number(x)
        base_num = to_number(base)
        if x_num <= 0 or base_num <= 0 or base_num == 1:
            return ExcelError("#VALUE!")
        return math.log(x_num, base_num)
    except FormulaEvaluationError:
        return ExcelError("#VALUE!")


def excel_text(value: Any, format_code: str) -> str:
    format_text = str(format_code)
    sci_match = re.fullmatch(r"([^0#]*)([0#]+(?:\.[0#]+)?[eE][+-]?[0#]+)(.*)", format_text)
    if sci_match:
        return sci_match.group(1) + format_excel_sci(value, sci_match.group(2)) + sci_match.group(3)

    fixed_match = re.fullmatch(r"([^0#]*)([0#]+(?:\.[0#]+)?)(.*)", format_text)
    if fixed_match:
        return fixed_match.group(1) + format_fixed_number(value, fixed_match.group(2)) + fixed_match.group(3)

    return format_excel_scalar(value)


def format_fixed_number(value: Any, pattern: str) -> str:
    numeric = to_number(value)
    if "." not in pattern:
        return str(int(Decimal(str(numeric)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)))

    integer_pattern, decimal_pattern = pattern.split(".", 1)
    max_decimals = len(decimal_pattern)
    required_decimals = decimal_pattern.count("0")
    quantum = Decimal("1").scaleb(-max_decimals)
    rounded = Decimal(str(numeric)).quantize(quantum, rounding=ROUND_HALF_UP)
    text = f"{rounded:.{max_decimals}f}"
    integer_text, fraction_text = text.split(".", 1)

    if max_decimals > required_decimals:
        while len(fraction_text) > required_decimals and fraction_text.endswith("0"):
            fraction_text = fraction_text[:-1]

    if not fraction_text:
        return integer_text
    if not integer_pattern.startswith("0") and integer_text == "0":
        integer_text = ""
    if not integer_pattern.startswith("0") and integer_text == "-0":
        integer_text = "-"
    return integer_text + "." + fraction_text


def criteria_match(value: Any, criteria: Any) -> bool:
    value = unwrap_scalar(value)
    criteria = unwrap_scalar(criteria)
    if not isinstance(criteria, str):
        return value == criteria
    criteria = criteria.strip()
    for operator in (">=", "<=", "<>", ">", "<", "="):
        if criteria.startswith(operator):
            right = criteria[len(operator) :]
            numeric = is_number_like(value) and is_number_like(right)
            if not numeric and operator in (">=", "<=", ">", "<"):
                return False
            left_value = to_number(value) if numeric else str(value)
            right_value = to_number(right) if numeric else right
            if operator == ">=":
                return left_value >= right_value
            if operator == "<=":
                return left_value <= right_value
            if operator == "<>":
                return left_value != right_value
            if operator == ">":
                return left_value > right_value
            if operator == "<":
                return left_value < right_value
            return left_value == right_value
    return str(value) == criteria


def excel_countif(criteria_range: list[Any], criteria: Any) -> int:
    return sum(1 for value in flatten(criteria_range) if criteria_match(value, criteria))


def excel_averageif(criteria_range: list[Any], criteria: Any, average_range: list[Any] | None = None) -> float:
    criteria_values = flatten(criteria_range)
    average_values = criteria_values if average_range is None else flatten(average_range)
    selected: list[float] = []
    for index, value in enumerate(criteria_values):
        if index < len(average_values) and criteria_match(value, criteria) and average_values[index] != "":
            selected.append(to_number(average_values[index]))
    if not selected:
        raise FormulaEvaluationError("AVERAGEIF has no matching numeric values")
    return sum(selected) / len(selected)


def excel_sumif(criteria_range: list[Any], criteria: Any, sum_range: list[Any] | None = None) -> float:
    criteria_values = flatten(criteria_range)
    sum_values = criteria_values if sum_range is None else flatten(sum_range)
    total = 0.0
    for index, value in enumerate(criteria_values):
        if index < len(sum_values) and criteria_match(value, criteria):
            total += to_number(sum_values[index])
    return total


def excel_sumifs(sum_range: list[Any], *args: Any) -> float:
    sum_values = flatten(sum_range)
    if len(args) % 2:
        raise FormulaEvaluationError("SUMIFS requires criteria_range/criteria pairs")
    criteria_pairs = [(flatten(args[index]), args[index + 1]) for index in range(0, len(args), 2)]
    total = 0.0
    for row_index, sum_value in enumerate(sum_values):
        if all(row_index < len(values) and criteria_match(values[row_index], criteria) for values, criteria in criteria_pairs):
            total += to_number(sum_value)
    return total


def excel_textjoin(delimiter: str, ignore_empty: Any, *args: Any) -> str:
    values = flatten(args)
    if bool(ignore_empty):
        values = [value for value in values if value != ""]
    return str(delimiter).join(format_excel_scalar(value) for value in values)


def excel_transpose(values: list[Any]) -> list[Any]:
    if not values or not isinstance(values[0], list):
        return [[value] for value in values]
    return [list(row) for row in zip(*values)]


def excel_quartile(values: list[Any], quart: Any) -> float:
    numbers = sorted(to_number(value) for value in flatten(values) if value != "" and is_number_like(value))
    if not numbers:
        raise FormulaEvaluationError("QUARTILE has no numeric values")
    q = int(to_number(quart))
    if q <= 0:
        return numbers[0]
    if q >= 4:
        return numbers[-1]
    position = (len(numbers) - 1) * q / 4
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return numbers[lower]
    fraction = position - lower
    return numbers[lower] * (1 - fraction) + numbers[upper] * fraction


def excel_slope(y_values: list[Any], x_values: list[Any]) -> float:
    return excel_linest(y_values, x_values)[0][0]


def excel_sumproduct(*arrays: list[Any]) -> float:
    vectors = [flatten(array) for array in arrays]
    if not vectors:
        return 0.0
    count = min(len(vector) for vector in vectors)
    total = 0.0
    for index in range(count):
        product = 1.0
        for vector in vectors:
            product *= to_number(vector[index])
        total += product
    return total


def excel_cubspline(*args: Any) -> float:
    """Port of the ODS Basic CUBSPLINE helper from Basic/Standard/CubSpline.xml."""
    if len(args) >= 4 and not isinstance(args[1], list) and isinstance(args[2], list) and isinstance(args[3], list):
        method = int(to_number(args[0]))
        x = args[1]
        x_values = args[2]
        y_values = args[3]
    elif len(args) >= 3:
        method = 3
        x = args[0]
        x_values = args[1]
        y_values = args[2]
    else:
        return ExcelError("#VALUE!")
    xs_raw = flatten(x_values)
    ys_raw = flatten(y_values)
    pairs: list[tuple[float, float]] = []
    for x_value, y_value in zip(xs_raw, ys_raw):
        if y_value == "" or not is_number_like(y_value) or not is_number_like(x_value):
            continue
        pairs.append((to_number(x_value), to_number(y_value)))
    if not pairs:
        return ExcelError("#VALUE!")
    pairs = sorted(pairs, key=lambda item: item[0])
    x_num = to_number(x)
    if len(pairs) == 1:
        return pairs[0][1]
    if method == 1:
        return natural_cubic_spline(x_num, pairs)
    if method == 3:
        return monotonic_spline_x3(x_num, pairs)
    return natural_cubic_spline(x_num, pairs)


def natural_cubic_spline(x_value: float, pairs: list[tuple[float, float]]) -> float:
    x = [item[0] for item in pairs]
    y = [item[1] for item in pairs]
    n = len(x)
    y2 = [0.0] * n
    u = [0.0] * n
    y2[0] = 0.0
    u[0] = 0.0
    for i in range(1, n - 1):
        sig = (x[i] - x[i - 1]) / dxx(x[i + 1], x[i - 1])
        p = sig * y2[i - 1] + 2.0
        y2[i] = (sig - 1.0) / p
        u[i] = (
            6.0
            * ((y[i + 1] - y[i]) / dxx(x[i + 1], x[i]) - (y[i] - y[i - 1]) / dxx(x[i], x[i - 1]))
            / dxx(x[i + 1], x[i - 1])
            - sig * u[i - 1]
        ) / p
    y2[-1] = 0.0
    for k in range(n - 2, -1, -1):
        y2[k] = y2[k] * y2[k + 1] + u[k]

    klo = 0
    khi = n - 1
    while khi - klo > 1:
        k = (khi + klo) // 2
        if x[k] > x_value:
            khi = k
        else:
            klo = k
    h = dxx(x[khi], x[klo])
    a = (x[khi] - x_value) / h
    b = (x_value - x[klo]) / h
    return a * y[klo] + b * y[khi] + ((a**3 - a) * y2[klo] + (b**3 - b) * y2[khi]) * (h**2) / 6.0


def monotonic_spline_x3(x_value: float, pairs: list[tuple[float, float]]) -> float:
    x = [item[0] for item in pairs]
    y = [item[1] for item in pairs]
    n_max = len(x) - 1
    if x_value < x[0] or x_value > x[n_max]:
        num = 1 if x_value < x[0] else n_max
        b = (y[num] - y[num - 1]) / dxx(x[num], x[num - 1])
        a = y[num] - b * x[num]
        return a + b * x_value

    num = 1
    for i in range(1, n_max + 1):
        if x_value <= x[i]:
            num = i
            break

    gxx = [0.0, 0.0]
    ggxx = [0.0, 0.0]
    for j in range(2):
        i = num - 1 + j
        if i == 0 or i == n_max:
            gxx[j] = 10.0**30
        elif (y[i + 1] - y[i] == 0) or (y[i] - y[i - 1] == 0):
            gxx[j] = 0.0
        elif (dxx(x[i + 1], x[i]) / (y[i + 1] - y[i]) + dxx(x[i], x[i - 1]) / (y[i] - y[i - 1])) == 0:
            gxx[j] = 0.0
        elif (y[i + 1] - y[i]) * (y[i] - y[i - 1]) < 0:
            gxx[j] = 0.0
        else:
            gxx[j] = 2.0 / (dxx(x[i + 1], x[i]) / (y[i + 1] - y[i]) + dxx(x[i], x[i - 1]) / (y[i] - y[i - 1]))

    if num == 1:
        gxx[0] = 1.5 * (y[num] - y[num - 1]) / dxx(x[num], x[num - 1]) - gxx[1] / 2.0
    if num == n_max:
        gxx[1] = 1.5 * (y[num] - y[num - 1]) / dxx(x[num], x[num - 1]) - gxx[0] / 2.0

    ggxx[0] = -2.0 * (gxx[1] + 2.0 * gxx[0]) / dxx(x[num], x[num - 1]) + 6.0 * (y[num] - y[num - 1]) / dxx(x[num], x[num - 1]) ** 2
    ggxx[1] = 2.0 * (2.0 * gxx[1] + gxx[0]) / dxx(x[num], x[num - 1]) - 6.0 * (y[num] - y[num - 1]) / dxx(x[num], x[num - 1]) ** 2
    d = (ggxx[1] - ggxx[0]) / dxx(x[num], x[num - 1]) / 6.0
    c = 0.5 * (x[num] * ggxx[0] - x[num - 1] * ggxx[1]) / dxx(x[num], x[num - 1])
    b = (y[num] - y[num - 1] - c * (x[num] ** 2 - x[num - 1] ** 2) - d * (x[num] ** 3 - x[num - 1] ** 3)) / dxx(x[num], x[num - 1])
    a = y[num - 1] - b * x[num - 1] - c * x[num - 1] ** 2 - d * x[num - 1] ** 3
    return a + b * x_value + c * x_value**2 + d * x_value**3


def dxx(x1: float, x0: float) -> float:
    delta = x1 - x0
    return 10.0**30 if delta == 0 else delta


def excel_linest(y_values: list[Any], x_values: list[Any] | None = None, const: Any = True, stats: Any = False) -> list[list[float]]:
    y = [to_number(value) for value in flatten(y_values) if value != ""]
    if x_values is None:
        x = list(range(1, len(y) + 1))
    else:
        x = [to_number(value) for value in flatten(x_values) if value != ""]
    count = min(len(x), len(y))
    if count < 2:
        raise FormulaEvaluationError("LINEST requires at least two points")
    x = x[:count]
    y = y[:count]
    mean_x = sum(x) / count
    mean_y = sum(y) / count
    denom = sum((value - mean_x) ** 2 for value in x)
    if denom == 0:
        raise FormulaEvaluationError("LINEST x values have zero variance")
    slope = sum((x[index] - mean_x) * (y[index] - mean_y) for index in range(count)) / denom
    intercept = mean_y - slope * mean_x if bool(const) else 0.0
    return [[slope, intercept]]


def first_column_lines(table: ET.Element, row_count: int) -> list[str]:
    rows = table.findall("table:table-row", NS)
    lines: list[str] = []
    expanded_row = 1
    for row in rows:
        repeat = int(attr(row, "table", "number-rows-repeated", "1"))
        value = ""
        for col, cell in iter_row_cells(row):
            if col == 1:
                value = cell.display
                break
            if col > 1:
                break
        for _ in range(repeat):
            if expanded_row > row_count:
                return lines
            lines.append(value)
            expanded_row += 1
    return lines


def column_lines(table: ET.Element, col_index: int, skip_header: str | None = None) -> list[str]:
    lines: list[str] = []
    expanded_row = 1
    for row in table.findall("table:table-row", NS):
        repeat = int(attr(row, "table", "number-rows-repeated", "1"))
        value = ""
        for col, cell in iter_row_cells(row):
            if col <= col_index < col + cell.repeat:
                value = cell.display
                break
            if col > col_index:
                break
        if value != "":
            for _ in range(repeat):
                lines.append(value)
        expanded_row += repeat
        if expanded_row > 10000 and value == "":
            break
    if skip_header is not None and lines and lines[0] == skip_header:
        return lines[1:]
    return lines


def save_lines(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def cell_output_text(cell: FormulaCell, evaluator: CachedFormulaEvaluator) -> str:
    if not cell.formula:
        return cell.display
    actual = evaluator.evaluate(cell)
    return format_excel_scalar(actual)


def evaluated_first_column_lines(
    cells: dict[tuple[str, int, int], FormulaCell],
    evaluator: CachedFormulaEvaluator,
    sheet: str,
    row_count: int,
) -> list[str]:
    lines: list[str] = []
    for row in range(1, row_count + 1):
        cell = cells.get((sheet, row, 1))
        lines.append(cell_output_text(cell, evaluator) if cell else "")
    return lines


def evaluated_column_lines(
    cells: dict[tuple[str, int, int], FormulaCell],
    evaluator: CachedFormulaEvaluator,
    sheet: str,
    col_index: int,
    skip_header: str | None = None,
) -> list[str]:
    max_row = max((row for sheet_name, row, col in cells if sheet_name == sheet and col == col_index), default=0)
    lines: list[str] = []
    for row in range(1, max_row + 1):
        cell = cells.get((sheet, row, col_index))
        if cell is None:
            continue
        value = cell_output_text(cell, evaluator)
        if value != "":
            lines.append(value)
    if skip_header is not None and lines and lines[0] == skip_header:
        return lines[1:]
    return lines


def export_reference(ods: Path, out_dir: Path) -> dict:
    root = read_xml(ods, "content.xml")
    first_sheet = next(iter(iter_tables(root)))
    export_sheet = get_table(root, "Export")
    tbc_sheet = get_table(root, "TBC")

    final_row_value = get_cell_display(first_sheet, 31, 4)
    if final_row_value == "":
        raise ValueError("Could not read About!D31 lookup final row from ODS")
    export_row_count = int(float(final_row_value)) + 1

    tgm_lines = first_column_lines(export_sheet, export_row_count)
    tbc_lines = column_lines(tbc_sheet, 15, skip_header="Output")

    tgm_path = out_dir / "reference_from_ods.tgm"
    tbc_path = out_dir / "reference_from_ods.tbc"
    save_lines(tgm_path, tgm_lines)
    save_lines(tbc_path, tbc_lines)

    report = inspect_ods(ods)
    report["exports"] = {
        "tgm": {
            "path": str(tgm_path),
            "line_count": len(tgm_lines),
            "source_sheet": "Export",
            "row_count_source": "About!D31 + 1",
        },
        "tbc": {
            "path": str(tbc_path),
            "line_count": len(tbc_lines),
            "source_sheet": "TBC",
            "source_column": "O",
        },
    }
    report_path = out_dir / "tgm_gen_ods_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    report["report_path"] = str(report_path)
    return report


def generate_exports(
    ods: Path,
    out_dir: Path,
    mode: str = "cached",
    fallback_on_error: bool = False,
    project_path: Path | None = None,
) -> dict:
    root = read_xml(ods, "content.xml")
    first_sheet = next(iter(iter_tables(root)))
    final_row_value = get_cell_display(first_sheet, 31, 4)
    if final_row_value == "":
        raise ValueError("Could not read About!D31 lookup final row from ODS")
    export_row_count = int(float(final_row_value)) + 1

    cells = load_formula_cells(ods)
    overrides = load_project_overrides(project_path)
    evaluator = make_evaluator(ods, cells, mode, overrides=overrides, fallback_on_error=fallback_on_error)

    tgm_lines = evaluated_first_column_lines(cells, evaluator, "Export", export_row_count)
    tbc_lines = evaluated_column_lines(cells, evaluator, "TBC", 15, skip_header="Output")

    tgm_path = out_dir / "generated.tgm"
    tbc_path = out_dir / "generated.tbc"
    save_lines(tgm_path, tgm_lines)
    save_lines(tbc_path, tbc_lines)

    return {
        "ods": str(ods),
        "evaluator_mode": mode,
        "fallback_on_error": fallback_on_error,
        "fallback_count": getattr(evaluator, "fallback_count", 0),
        "fallback_cells": getattr(evaluator, "fallback_cells", []),
        "project_path": str(project_path) if project_path else "",
        "override_count": len(overrides),
        "outputs": {
            "tgm": {"path": str(tgm_path), "line_count": len(tgm_lines), "source_sheet": "Export"},
            "tbc": {"path": str(tbc_path), "line_count": len(tbc_lines), "source_sheet": "TBC", "source_column": "O"},
        },
    }


def extract_input_model(ods: Path, sheets: list[str] | None = None, out_path: Path | None = None) -> dict:
    selected_sheets = sheets or DEFAULT_INPUT_SHEETS
    cells = load_formula_cells(ods)
    inputs: list[dict[str, Any]] = []
    by_sheet: dict[str, int] = {}
    for cell in sorted(cells.values(), key=lambda item: (item.sheet, item.row, item.col)):
        if cell.sheet not in selected_sheets or cell.formula:
            continue
        if cell.display == "" and cell.value == "":
            continue
        parsed = parse_scalar(cell.value if cell.value != "" else cell.display)
        record = {
            "sheet": cell.sheet,
            "address": cell.address,
            "row": cell.row,
            "col": cell.col,
            "value": cell.value,
            "display": cell.display,
            "formulaValue": formula_display_for_cell(cell),
            "parsed": format_excel_scalar(parsed),
            "valueType": cell.value_type,
            "styleName": cell.style_name,
        }
        inputs.append(record)
        by_sheet[cell.sheet] = by_sheet.get(cell.sheet, 0) + 1
    report = {
        "ods": str(ods),
        "sheets": selected_sheets,
        "input_count": len(inputs),
        "sheet_counts": dict(sorted(by_sheet.items())),
        "inputs": inputs,
        "note": "This is the current editable-project seed: non-formula populated cells from ODS input sheets. ODS color/style classification is preserved for later white-cell filtering.",
    }
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        report["path"] = str(out_path)
    return report


def address_report(address: str, default_sheet: str = "") -> dict[str, Any]:
    cleaned = address.replace("$", "").strip()
    if cleaned == "":
        return {"raw": address}
    try:
        parsed = parse_ref_token(cleaned, default_sheet)
        report: dict[str, Any] = {"raw": address, **parsed}
        if parsed["type"] == "cell":
            row, col = a1_to_row_col(parsed["address"])
            report["row"] = row
            report["col"] = col
        else:
            start_row, start_col = a1_to_row_col(parsed["start"])
            end_row, end_col = a1_to_row_col(parsed["end"])
            report["startRow"] = start_row
            report["startCol"] = start_col
            report["endRow"] = end_row
            report["endCol"] = end_col
            report["rowCount"] = abs(end_row - start_row) + 1
            report["colCount"] = abs(end_col - start_col) + 1
            report["cellCount"] = report["rowCount"] * report["colCount"]
        return report
    except ValueError:
        return {"raw": address, "parseError": True}


def chart_member_sort_key(member: str) -> tuple[int, str]:
    match = re.match(r"Object\s+(\d+)/", member)
    if match:
        return int(match.group(1)), member
    return sys.maxsize, member


def element_text(element: ET.Element | None) -> str:
    if element is None:
        return ""
    return " ".join(part.strip() for part in element.itertext() if part.strip())


def inspect_charts(ods: Path) -> dict:
    charts: list[dict[str, Any]] = []
    with ZipFile(ods) as zf:
        members = sorted(
            (name for name in zf.namelist() if name.startswith("Object ") and name.endswith("/content.xml")),
            key=chart_member_sort_key,
        )
        for member in members:
            root = ET.fromstring(zf.read(member))
            for chart_index, chart in enumerate(root.findall(".//chart:chart", NS), start=1):
                title = element_text(chart.find("chart:title", NS))
                plot_area = chart.find("chart:plot-area", NS)
                plot_range = attr(plot_area, "table", "cell-range-address") if plot_area is not None else ""
                series_reports: list[dict[str, Any]] = []
                sheet_counts: dict[str, int] = {}
                for series_index, series in enumerate(chart.findall(".//chart:series", NS), start=1):
                    values_range = attr(series, "chart", "values-cell-range-address")
                    label_address = attr(series, "chart", "label-cell-address")
                    attached_axis = attr(series, "chart", "attached-axis")
                    default_sheet = ""
                    if values_range:
                        values_meta = address_report(values_range)
                        default_sheet = str(values_meta.get("sheet", ""))
                    else:
                        values_meta = {"raw": values_range}
                    label_meta = address_report(label_address, default_sheet) if label_address else {"raw": label_address}
                    domain_reports = [
                        address_report(attr(domain, "table", "cell-range-address"), default_sheet)
                        for domain in series.findall("chart:domain", NS)
                        if attr(domain, "table", "cell-range-address") != ""
                    ]
                    sheet = str(values_meta.get("sheet", ""))
                    if sheet:
                        sheet_counts[sheet] = sheet_counts.get(sheet, 0) + 1
                    series_reports.append(
                        {
                            "index": series_index,
                            "class": attr(series, "chart", "class"),
                            "values": values_meta,
                            "label": label_meta,
                            "domains": domain_reports,
                            "attachedAxis": attached_axis,
                        }
                    )

                charts.append(
                    {
                        "object": member.split("/", 1)[0],
                        "member": member,
                        "index": chart_index,
                        "title": title,
                        "class": attr(chart, "chart", "class"),
                        "width": attr(chart, "svg", "width"),
                        "height": attr(chart, "svg", "height"),
                        "plotRange": address_report(plot_range) if plot_range else {"raw": plot_range},
                        "seriesCount": len(series_reports),
                        "sheets": dict(sorted(sheet_counts.items())),
                        "series": series_reports,
                    }
                )

    title_counts: dict[str, int] = {}
    class_counts: dict[str, int] = {}
    sheet_counts: dict[str, int] = {}
    for chart in charts:
        title = chart["title"] or "(untitled)"
        title_counts[title] = title_counts.get(title, 0) + 1
        chart_class = chart["class"] or "(unknown)"
        class_counts[chart_class] = class_counts.get(chart_class, 0) + 1
        for sheet, count in chart["sheets"].items():
            sheet_counts[sheet] = sheet_counts.get(sheet, 0) + count

    return {
        "ods": str(ods),
        "chart_count": len(charts),
        "series_count": sum(chart["seriesCount"] for chart in charts),
        "title_counts": dict(sorted(title_counts.items())),
        "class_counts": dict(sorted(class_counts.items())),
        "sheet_series_counts": dict(sorted(sheet_counts.items())),
        "charts": charts,
    }


def load_project_overrides(project_path: Path | None) -> dict[tuple[str, int, int], Any]:
    if project_path is None:
        return {}
    data = json.loads(project_path.read_text(encoding="utf-8-sig"))
    overrides: dict[tuple[str, int, int], Any] = {}
    for record in data.get("inputs", []):
        sheet = str(record.get("sheet", ""))
        address = str(record.get("address", ""))
        if not sheet or not address:
            continue
        row, col = a1_to_row_col(address)
        value = record.get("value", "")
        if value == "":
            value = record.get("parsed", record.get("formulaValue", record.get("display", "")))
        overrides[(sheet, row, col)] = parse_scalar(str(value))
    return overrides


def strip_generated_lookup_blocks(text: str) -> str:
    lines = text.splitlines()
    kept: list[str] = []
    skipping = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("["):
            section = stripped.split("]", 1)[0].strip("[")
            skipping = section in {"LookupV2", "PatchV1"}
        if not skipping:
            kept.append(line.rstrip())
    return "\n".join(kept).strip() + "\n"


def normalize_export_text(text: str, strip_lookup: bool = False) -> str:
    normalized = "\n".join(line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"))
    if strip_lookup:
        normalized = strip_generated_lookup_blocks(normalized)
    return normalized.strip() + "\n"


def compare_files(reference: Path, candidate: Path, strip_lookup: bool = False) -> dict:
    ref = normalize_export_text(reference.read_text(encoding="utf-8", errors="ignore"), strip_lookup=strip_lookup)
    cand = normalize_export_text(candidate.read_text(encoding="utf-8", errors="ignore"), strip_lookup=strip_lookup)
    ref_lines = ref.splitlines()
    cand_lines = cand.splitlines()
    first_diff = None
    for index, (left, right) in enumerate(zip(ref_lines, cand_lines), start=1):
        if left != right:
            first_diff = {"line": index, "reference": left, "candidate": right}
            break
    if first_diff is None and len(ref_lines) != len(cand_lines):
        first_diff = {
            "line": min(len(ref_lines), len(cand_lines)) + 1,
            "reference": "<EOF>" if len(ref_lines) < len(cand_lines) else ref_lines[min(len(ref_lines), len(cand_lines))],
            "candidate": "<EOF>" if len(cand_lines) < len(ref_lines) else cand_lines[min(len(ref_lines), len(cand_lines))],
        }
    return {
        "equal": ref == cand,
        "reference_lines": len(ref_lines),
        "candidate_lines": len(cand_lines),
        "first_diff": first_diff,
        "strip_lookup": strip_lookup,
    }


def inspect_ods(ods: Path) -> dict:
    root = read_xml(ods, "content.xml")
    sheet_reports: list[dict] = []
    function_counts: dict[str, int] = {}

    for table in iter_tables(root):
        name = table_name(table)
        row_count = 0
        formula_count = 0
        nonempty_count = 0
        for row in table.findall("table:table-row", NS):
            row_count += int(attr(row, "table", "number-rows-repeated", "1"))
            for _, cell in iter_row_cells(row):
                if cell.formula:
                    formula_count += cell.repeat
                    for match in re.finditer(r"(?<![A-Za-z0-9_\.])([A-Z][A-Z0-9_]*)\s*\(", cell.formula):
                        function_counts[match.group(1)] = function_counts.get(match.group(1), 0) + cell.repeat
                if cell.display != "" or cell.formula:
                    nonempty_count += cell.repeat
        sheet_reports.append(
            {
                "name": name,
                "rows": row_count,
                "formula_count": formula_count,
                "nonempty_or_formula_cells": nonempty_count,
            }
        )

    return {
        "ods": str(ods),
        "sheet_count": len(sheet_reports),
        "sheets": sheet_reports,
        "formula_count": sum(sheet["formula_count"] for sheet in sheet_reports),
        "formula_functions": dict(sorted(function_counts.items())),
        "formula_engine_status": "inventory_only",
        "excluded_generated_sections": ["LookupV2", "PatchV1"],
    }


def values_match(expected: str, actual: Any, tolerance: float) -> bool:
    if expected == "":
        return actual == ""
    if str(expected).startswith(("#", "Err:")):
        return format_excel_scalar(actual) == expected or format_excel_scalar(actual).startswith("#")
    try:
        expected_number = to_number(parse_scalar(expected))
        actual_number = to_number(actual)
        scale = max(1.0, abs(expected_number))
        return abs(expected_number - actual_number) <= tolerance * scale
    except (ValueError, FormulaEvaluationError):
        return str(expected) == format_excel_scalar(actual)


def formula_report(
    ods: Path,
    sheets: list[str],
    tolerance: float = 1e-9,
    sample_limit: int = 12,
    mode: str = "cached",
    fallback_on_error: bool = False,
    project_path: Path | None = None,
) -> dict:
    cells = load_formula_cells(ods)
    overrides = load_project_overrides(project_path)
    evaluator = make_evaluator(ods, cells, mode, overrides=overrides, fallback_on_error=fallback_on_error)
    implemented = implemented_formula_functions()
    selected = [
        cell
        for cell in cells.values()
        if cell.formula and (not sheets or cell.sheet in sheets)
    ]

    sheet_reports: dict[str, dict[str, Any]] = {}
    unsupported_functions: dict[str, int] = {}
    dependency_edges = 0
    evaluated_count = 0
    match_count = 0
    mismatch_count = 0
    error_count = 0
    mismatch_samples: list[dict] = []
    error_samples: list[dict] = []

    for cell in selected:
        refs = refs_in_formula(cell.formula, cell.sheet)
        dependency_edges += len(refs)
        functions = functions_in_formula(cell.formula)
        unsupported = sorted(functions - implemented)
        for name in unsupported:
            unsupported_functions[name] = unsupported_functions.get(name, 0) + 1

        sheet_report = sheet_reports.setdefault(
            cell.sheet,
            {
                "formula_count": 0,
                "supported_formula_count": 0,
                "evaluated_count": 0,
                "match_count": 0,
                "mismatch_count": 0,
                "error_count": 0,
                "dependency_edges": 0,
            },
        )
        sheet_report["formula_count"] += 1
        sheet_report["dependency_edges"] += len(refs)
        if not unsupported:
            sheet_report["supported_formula_count"] += 1
        else:
            continue

        try:
            actual = evaluator.evaluate(cell)
            evaluated_count += 1
            sheet_report["evaluated_count"] += 1
            if values_match(cell.display, actual, tolerance):
                match_count += 1
                sheet_report["match_count"] += 1
            else:
                mismatch_count += 1
                sheet_report["mismatch_count"] += 1
                if len(mismatch_samples) < sample_limit:
                    mismatch_samples.append(
                        {
                            "cell": f"{cell.sheet}!{cell.address}",
                            "formula": cell.formula,
                            "expected": cell.display,
                            "actual": format_excel_scalar(actual),
                        }
                    )
        except FormulaEvaluationError as exc:
            if str(cell.display).startswith(("#", "Err:")):
                evaluated_count += 1
                sheet_report["evaluated_count"] += 1
                match_count += 1
                sheet_report["match_count"] += 1
            else:
                error_count += 1
                sheet_report["error_count"] += 1
                if len(error_samples) < sample_limit:
                    error_samples.append(
                        {
                            "cell": f"{cell.sheet}!{cell.address}",
                            "formula": cell.formula,
                            "expected": cell.display,
                            "error": str(exc),
                        }
                    )

    return {
        "ods": str(ods),
        "formula_engine_status": "cached_dependency_evaluator" if mode == "cached" else "recursive_dependency_evaluator",
        "dependency_mode": "referenced cells use stored ODS values" if mode == "cached" else "referenced formulas are recursively evaluated",
        "evaluator_mode": mode,
        "fallback_on_error": fallback_on_error,
        "fallback_count": getattr(evaluator, "fallback_count", 0),
        "fallback_cells": getattr(evaluator, "fallback_cells", []),
        "project_path": str(project_path) if project_path else "",
        "override_count": len(overrides),
        "sheets": sheets,
        "formula_count": len(selected),
        "supported_formula_count": sum(report["supported_formula_count"] for report in sheet_reports.values()),
        "evaluated_count": evaluated_count,
        "match_count": match_count,
        "mismatch_count": mismatch_count,
        "error_count": error_count,
        "dependency_edges": dependency_edges,
        "implemented_functions": sorted(implemented),
        "unsupported_functions": dict(sorted(unsupported_functions.items())),
        "sheet_reports": sheet_reports,
        "mismatch_samples": mismatch_samples,
        "error_samples": error_samples,
        "tolerance": tolerance,
    }


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ods", type=Path, default=DEFAULT_ODS)
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect", help="Print ODS formula and sheet inventory")
    inspect_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    chart_parser = subparsers.add_parser("chart-report", help="Print embedded ODS chart inventory and source ranges")
    chart_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    export_parser = subparsers.add_parser("export-reference", help="Write reference .tgm/.tbc files reconstructed from ODS outputs")
    export_parser.add_argument("--out-dir", type=Path, default=Path("tmp/tgm_gen_port"))
    export_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    generate_parser = subparsers.add_parser("generate", help="Write generated .tgm/.tbc files from evaluated ODS formulas")
    generate_parser.add_argument("--out-dir", type=Path, default=Path("tmp/tgm_gen_port"))
    generate_parser.add_argument("--mode", choices=["cached", "recursive"], default="recursive", help="Formula evaluator mode")
    generate_parser.add_argument("--fallback-on-error", action="store_true", help="Recursive mode: use stored ODS value for unresolved dependency edges")
    generate_parser.add_argument("--project", type=Path, default=None, help="Input project JSON produced by extract-inputs")
    generate_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    formula_parser = subparsers.add_parser("formula-report", help="Evaluate supported formulas against stored ODS values")
    formula_parser.add_argument("--sheets", nargs="*", default=["General", "Realtime", "Materials"], help="Sheet names to include")
    formula_parser.add_argument("--mode", choices=["cached", "recursive"], default="recursive", help="Formula evaluator mode")
    formula_parser.add_argument("--fallback-on-error", action="store_true", help="Recursive mode: use stored ODS value for unresolved dependency edges")
    formula_parser.add_argument("--project", type=Path, default=None, help="Input project JSON produced by extract-inputs")
    formula_parser.add_argument("--tolerance", type=float, default=1e-9)
    formula_parser.add_argument("--sample-limit", type=int, default=12)
    formula_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    input_parser = subparsers.add_parser("extract-inputs", help="Extract non-formula ODS input cells as a project seed JSON")
    input_parser.add_argument("--sheets", nargs="*", default=DEFAULT_INPUT_SHEETS, help="Sheet names to include")
    input_parser.add_argument("--out", type=Path, default=Path("tmp/tgm_gen_port/inputs.json"))
    input_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    compare_parser = subparsers.add_parser("compare", help="Compare two generated export files")
    compare_parser.add_argument("reference", type=Path)
    compare_parser.add_argument("candidate", type=Path)
    compare_parser.add_argument("--strip-lookup", action="store_true")
    compare_parser.add_argument("--json", action="store_true")

    args = parser.parse_args()
    if args.command in {"inspect", "chart-report", "export-reference", "generate", "formula-report", "extract-inputs"} and not args.ods.exists():
        raise FileNotFoundError(f"ODS not found: {args.ods}")

    if args.command == "inspect":
        report = inspect_ods(args.ods)
    elif args.command == "chart-report":
        report = inspect_charts(args.ods)
    elif args.command == "export-reference":
        report = export_reference(args.ods, args.out_dir)
    elif args.command == "generate":
        report = generate_exports(args.ods, args.out_dir, mode=args.mode, fallback_on_error=args.fallback_on_error, project_path=args.project)
    elif args.command == "formula-report":
        report = formula_report(
            args.ods,
            args.sheets,
            tolerance=args.tolerance,
            sample_limit=args.sample_limit,
            mode=args.mode,
            fallback_on_error=args.fallback_on_error,
            project_path=args.project,
        )
    elif args.command == "extract-inputs":
        report = extract_input_model(args.ods, sheets=args.sheets, out_path=args.out)
    else:
        report = compare_files(args.reference, args.candidate, strip_lookup=args.strip_lookup)

    if getattr(args, "json", False):
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        for key, value in report.items():
            print(f"{key}: {value}")
    return 0 if report.get("equal", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
