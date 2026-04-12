#!/usr/bin/env python3
"""
Fix missing typing imports in app/ files.
Adds 'from typing import ...' for any typing constructs used but not imported.
"""
import re
from pathlib import Path
from typing import Set

APP_DIR = Path("app")

# Files and their needed typing imports
# Format: {file_path: set_of_needed_types}
needed: dict[str, Set[str]] = {}

for py_file in sorted(APP_DIR.rglob("*.py")):
    content = py_file.read_text(encoding="utf-8")

    # Find all used typing constructs: Optional[, List[, Set[, Dict[, Tuple[
    used_types: Set[str] = set()
    for match in re.finditer(r'\b(Optional|List|Set|Dict|Tuple|Callable|Iterator|Iterable|Union)\[', content):
        used_types.add(match.group(1))

    if not used_types:
        continue

    # Check what's already imported from typing
    typing_import_match = re.search(r'^from typing import (.+)$', content, re.MULTILINE)
    imported_types: Set[str] = set()
    if typing_import_match:
        for item in typing_import_match.group(1).split(","):
            imported_types.add(item.strip())

    missing = used_types - imported_types
    if missing:
        needed[str(py_file)] = missing
        print(f"  {py_file}: needs {sorted(missing)}")

        # Add the import
        if typing_import_match:
            # Append to existing import
            new_import_line = f"from typing import {', '.join(sorted(imported_types | missing))}"
            content = content.replace(typing_import_match.group(0), new_import_line)
        else:
            # Add new import after first line (docstring) or first import
            lines = content.split('\n')
            insert_idx = 0
            for i, line in enumerate(lines):
                if line.startswith('"""') and i + 1 < len(lines) and lines[i+1].strip() and not lines[i+1].startswith('#'):
                    insert_idx = i + 1
                    break
                if line.startswith('from ') or line.startswith('import '):
                    insert_idx = i
                    break

            new_import = f"from typing import {', '.join(sorted(missing))}"
            lines.insert(insert_idx + 1, new_import)
            content = '\n'.join(lines)

        py_file.write_text(content, encoding="utf-8")
        print(f"    Fixed: {py_file}")

print(f"\nTotal files fixed: {len(needed)}")
