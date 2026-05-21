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
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable
from xml.etree import ElementTree as ET
from zipfile import ZipFile


DEFAULT_ODS = Path("tools/downloads/studio397/TGM Gen V0.33 - GY F1 1975 Front.ods")

NS = {
    "office": "urn:oasis:names:tc:opendocument:xmlns:office:1.0",
    "table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
    "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
    "chart": "urn:oasis:names:tc:opendocument:xmlns:chart:1.0",
}

Q = {prefix: f"{{{uri}}}" for prefix, uri in NS.items()}


@dataclass
class Cell:
    text: str = ""
    value: str = ""
    formula: str = ""
    repeat: int = 1

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
    formula: str


class FormulaEvaluationError(Exception):
    """Raised when a formula cannot yet be evaluated by the partial engine."""


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
    for cell in row.findall("table:table-cell", NS):
        repeat = int(attr(cell, "table", "number-columns-repeated", "1"))
        yield col, Cell(
            text=cell_text(cell),
            value=cell_value(cell),
            formula=attr(cell, "table", "formula"),
            repeat=repeat,
        )
        col += repeat


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


def flatten(values: Iterable[Any]) -> list[Any]:
    flattened: list[Any] = []
    for value in values:
        if isinstance(value, list):
            flattened.extend(flatten(value))
        else:
            flattened.append(value)
    return flattened


def to_number(value: Any) -> float:
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


def format_excel_sci(value: Any) -> str:
    numeric = to_number(value)
    if numeric == 0:
        return "0e0"
    mantissa, exponent = f"{numeric:.2e}".split("e")
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
                index += 2
                continue
            in_string = not in_string
        elif char == ";" and not in_string:
            out.append(",")
        else:
            out.append(char)
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
        elif char == "<" and index + 1 < len(text) and text[index + 1] == ">":
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
                        formula=cell.formula,
                    )
                col_index = col + cell.repeat
            row_index += row_repeat
    return cells


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
        "CEILING",
        "CHAR",
        "CONCAT",
        "COS",
        "COUNT",
        "DEGREES",
        "ERF",
        "FLOOR",
        "HLOOKUP",
        "IF",
        "IFERROR",
        "INDEX",
        "ISBLANK",
        "ISNUMBER",
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
        "RADIANS",
        "ROUND",
        "ROUNDDOWN",
        "ROW",
        "SIN",
        "SQRT",
        "SUM",
        "SUMIF",
        "SUMIFS",
        "TAN",
        "TEXT",
        "TEXTJOIN",
        "TRANSPOSE",
        "VLOOKUP",
    }


def normalize_formula(formula: str, current_sheet: str) -> str:
    expr = formula
    if expr.startswith("of:="):
        expr = expr[4:]
    expr = expr.replace("COM.MICROSOFT.CONCAT", "CONCAT")

    def ref_repl(match: re.Match) -> str:
        ref = parse_ref_token(match.group(1), current_sheet)
        if ref["type"] == "cell":
            return f'REF("{ref["sheet"]}","{ref["address"]}")'
        return f'RANGE("{ref["sheet"]}","{ref["start"]}","{ref["end"]}")'

    expr = re.sub(r"\[([^\]]+)\]", ref_repl, expr)
    expr = replace_semicolons_outside_strings(expr)
    expr = replace_equals_outside_strings(expr)
    expr = expr.replace("^", "**")
    return expr


class CachedFormulaEvaluator:
    """Partial ODS formula evaluator using stored ODS values for dependencies."""

    def __init__(self, cells: dict[tuple[str, int, int], FormulaCell]):
        self.cells = cells

    def ref(self, sheet: str, address: str) -> Any:
        row, col = a1_to_row_col(address)
        cell = self.cells.get((sheet, row, col))
        if cell is None:
            return ""
        return parse_scalar(cell.display)

    def range_values(self, sheet: str, start: str, end: str) -> list[Any]:
        start_row, start_col = a1_to_row_col(start)
        end_row, end_col = a1_to_row_col(end)
        rows: list[list[Any]] = []
        for row in range(min(start_row, end_row), max(start_row, end_row) + 1):
            row_values: list[Any] = []
            for col in range(min(start_col, end_col), max(start_col, end_col) + 1):
                cell = self.cells.get((sheet, row, col))
                row_values.append(parse_scalar(cell.display) if cell else "")
            rows.append(row_values)
        if len(rows) == 1:
            return rows[0]
        if rows and len(rows[0]) == 1:
            return [row[0] for row in rows]
        return rows

    def evaluate(self, cell: FormulaCell) -> Any:
        if not cell.formula:
            return parse_scalar(cell.display)
        expr = normalize_formula(cell.formula, cell.sheet)
        env = self.env()
        try:
            return eval(expr, {"__builtins__": {}}, env)  # noqa: S307 - restricted env for local ODS formulas.
        except Exception as exc:
            raise FormulaEvaluationError(str(exc)) from exc

    def env(self) -> dict[str, Callable | float]:
        return {
            "REF": self.ref,
            "RANGE": self.range_values,
            "ABS": lambda x: abs(to_number(x)),
            "ACOS": lambda x: math.acos(to_number(x)),
            "ADDRESS": lambda row, col: row_col_to_a1(int(to_number(row)), int(to_number(col))),
            "AND": lambda *args: all(bool(arg) for arg in args),
            "ASIN": lambda x: math.asin(to_number(x)),
            "ATAN": lambda x: math.atan(to_number(x)),
            "ATAN2": lambda y, x: math.atan2(to_number(y), to_number(x)),
            "AVERAGE": lambda *args: excel_average(*args),
            "CEILING": lambda x, significance=1: math.ceil(to_number(x) / to_number(significance)) * to_number(significance),
            "CHAR": lambda x: chr(int(to_number(x))),
            "CONCAT": lambda *args: "".join(format_excel_scalar(arg) for arg in args),
            "COS": lambda x: math.cos(to_number(x)),
            "COUNT": lambda *args: sum(1 for value in flatten(args) if is_number_like(value)),
            "DEGREES": lambda x: math.degrees(to_number(x)),
            "ERF": lambda x: math.erf(to_number(x)),
            "FLOOR": lambda x, significance=1: math.floor(to_number(x) / to_number(significance)) * to_number(significance),
            "HLOOKUP": excel_hlookup,
            "IF": lambda condition, true_value, false_value="": true_value if bool(condition) else false_value,
            "IFERROR": lambda value, fallback: fallback if isinstance(value, FormulaEvaluationError) else value,
            "INDEX": excel_index,
            "ISBLANK": lambda x: x == "",
            "ISNUMBER": is_number_like,
            "ISTEXT": lambda x: isinstance(x, str) and x != "",
            "LINEST": excel_linest,
            "LOG": lambda x, base=math.e: math.log(to_number(x), to_number(base)),
            "LOOKUP": excel_lookup,
            "MATCH": excel_match,
            "MAX": lambda *args: max(to_number(value) for value in flatten(args) if value != ""),
            "MEDIAN": excel_median,
            "MIN": lambda *args: min(to_number(value) for value in flatten(args) if value != ""),
            "MOD": lambda x, y: to_number(x) % to_number(y),
            "MROUND": lambda x, multiple: round(to_number(x) / to_number(multiple)) * to_number(multiple),
            "NOT": lambda x: not bool(x),
            "OR": lambda *args: any(bool(arg) for arg in args),
            "PI": lambda: math.pi,
            "POWER": lambda x, y: to_number(x) ** to_number(y),
            "RADIANS": lambda x: math.radians(to_number(x)),
            "ROUND": lambda x, digits=0: round(to_number(x), int(to_number(digits))),
            "ROUNDDOWN": lambda x, digits=0: math.trunc(to_number(x) * (10 ** int(to_number(digits)))) / (10 ** int(to_number(digits))),
            "ROW": lambda value=None: 1 if value is None else 1,
            "SIN": lambda x: math.sin(to_number(x)),
            "SQRT": lambda x: math.sqrt(to_number(x)),
            "SUM": lambda *args: sum(to_number(value) for value in flatten(args) if value != ""),
            "SUMIF": excel_sumif,
            "SUMIFS": excel_sumifs,
            "TAN": lambda x: math.tan(to_number(x)),
            "TEXT": excel_text,
            "TEXTJOIN": excel_textjoin,
            "TRANSPOSE": excel_transpose,
            "VLOOKUP": excel_vlookup,
        }


def is_number_like(value: Any) -> bool:
    try:
        to_number(value)
        return value != ""
    except FormulaEvaluationError:
        return False


def excel_average(*args: Any) -> float:
    numbers = [to_number(value) for value in flatten(args) if value != "" and is_number_like(value)]
    if not numbers:
        raise FormulaEvaluationError("AVERAGE has no numeric values")
    return sum(numbers) / len(numbers)


def excel_lookup(value: Any, lookup_vector: list[Any], result_vector: list[Any] | None = None) -> Any:
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


def excel_match(value: Any, lookup_vector: list[Any], match_type: int = 1) -> int:
    lookup_vector = flatten(lookup_vector)
    if int(to_number(match_type)) == 0:
        for index, item in enumerate(lookup_vector, start=1):
            if item == value:
                return index
        raise FormulaEvaluationError(f"MATCH did not find {value!r}")
    best_index = None
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


def excel_text(value: Any, format_code: str) -> str:
    if "e" in str(format_code).lower():
        return format_excel_sci(value)
    if "." in str(format_code):
        decimals = len(str(format_code).split(".", 1)[1].replace("#", "0"))
        return f"{to_number(value):.{decimals}f}".rstrip("0").rstrip(".")
    return format_excel_scalar(value)


def criteria_match(value: Any, criteria: Any) -> bool:
    if not isinstance(criteria, str):
        return value == criteria
    criteria = criteria.strip()
    for operator in (">=", "<=", "<>", ">", "<", "="):
        if criteria.startswith(operator):
            right = criteria[len(operator) :]
            numeric = is_number_like(value) and is_number_like(right)
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
    try:
        expected_number = to_number(parse_scalar(expected))
        actual_number = to_number(actual)
        scale = max(1.0, abs(expected_number))
        return abs(expected_number - actual_number) <= tolerance * scale
    except (ValueError, FormulaEvaluationError):
        return str(expected) == format_excel_scalar(actual)


def formula_report(ods: Path, sheets: list[str], tolerance: float = 1e-9, sample_limit: int = 12) -> dict:
    cells = load_formula_cells(ods)
    evaluator = CachedFormulaEvaluator(cells)
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
        "formula_engine_status": "partial_cached_dependency_evaluator",
        "dependency_mode": "referenced cells use stored ODS values",
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ods", type=Path, default=DEFAULT_ODS)
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect", help="Print ODS formula and sheet inventory")
    inspect_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    export_parser = subparsers.add_parser("export-reference", help="Write reference .tgm/.tbc files reconstructed from ODS outputs")
    export_parser.add_argument("--out-dir", type=Path, default=Path("tmp/tgm_gen_port"))
    export_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    formula_parser = subparsers.add_parser("formula-report", help="Evaluate supported formulas against stored ODS values")
    formula_parser.add_argument("--sheets", nargs="*", default=["General", "Realtime", "Materials"], help="Sheet names to include")
    formula_parser.add_argument("--tolerance", type=float, default=1e-9)
    formula_parser.add_argument("--sample-limit", type=int, default=12)
    formula_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    compare_parser = subparsers.add_parser("compare", help="Compare two generated export files")
    compare_parser.add_argument("reference", type=Path)
    compare_parser.add_argument("candidate", type=Path)
    compare_parser.add_argument("--strip-lookup", action="store_true")
    compare_parser.add_argument("--json", action="store_true")

    args = parser.parse_args()
    if args.command in {"inspect", "export-reference", "formula-report"} and not args.ods.exists():
        raise FileNotFoundError(f"ODS not found: {args.ods}")

    if args.command == "inspect":
        report = inspect_ods(args.ods)
    elif args.command == "export-reference":
        report = export_reference(args.ods, args.out_dir)
    elif args.command == "formula-report":
        report = formula_report(args.ods, args.sheets, tolerance=args.tolerance, sample_limit=args.sample_limit)
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
