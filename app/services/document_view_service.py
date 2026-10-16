"""Parse editable RPD text into safe paragraphs and tables for browser and DOCX."""
import re


def document_blocks(text):
    lines = text.splitlines()
    blocks = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if "\t" in line:
            rows = []
            columns = len(line.split("\t"))
            while index < len(lines) and "\t" in lines[index] and len(lines[index].split("\t")) == columns:
                rows.append(lines[index].split("\t"))
                index += 1
            blocks.append({"kind": "table", "headers": rows[0], "rows": rows[1:]})
            continue
        value = line.strip()
        if value:
            if value == "РАБОЧАЯ ПРОГРАММА ДИСЦИПЛИНЫ":
                kind = "title"
            elif re.match(r"^\d{1,2}\.(?:\d+\s|\s)", value) or value.startswith(("Аннотация к", "Лист актуализации")):
                kind = "heading"
            elif value.startswith("Задание "):
                kind = "subheading"
            elif value.startswith(("• ", "· ")):
                kind = "bullet"
                value = value[2:]
            else:
                kind = "paragraph"
            blocks.append({"kind": kind, "text": value})
        index += 1
    return blocks
