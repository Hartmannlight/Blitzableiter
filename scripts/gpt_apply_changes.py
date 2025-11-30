from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    import pyperclip
except ImportError:
    print(
        'Missing dependency "pyperclip". ' 'Install it with: pip install pyperclip',
        file=sys.stderr,
    )
    sys.exit(1)


@dataclass
class Operation:
    kind: str  # 'write', 'delete', 'mkdir'
    path: Path
    content: str | None = None


def read_clipboard_text() -> str:
    text = pyperclip.paste()
    if not isinstance(text, str):
        raise ValueError('Clipboard does not contain text')
    if not text.strip():
        raise ValueError('Clipboard is empty or only whitespace')
    return text


def normalize_path_string(raw: str) -> str:
    path_str = raw.strip()

    if path_str.startswith('`') and path_str.endswith('`') and len(path_str) >= 2:
        path_str = path_str[1:-1].strip()

    path_str = path_str.replace('*', '_')

    return path_str


def parse_operations(text: str) -> list[Operation]:
    operations: list[Operation] = []

    lines = text.splitlines(keepends=True)
    current_file_path: Path | None = None
    collecting_code = False
    code_lines: list[str] = []

    for raw_line in lines:
        line = raw_line.rstrip('\n')

        if current_file_path is not None:
            if collecting_code:
                if line.startswith('```'):
                    content = ''.join(code_lines)
                    operations.append(
                        Operation(kind='write', path=current_file_path, content=content),
                    )
                    current_file_path = None
                    collecting_code = False
                    code_lines = []
                else:
                    code_lines.append(raw_line.rstrip('\r\n') + '\n')
            else:
                if line.startswith('```'):
                    collecting_code = True
            continue

        if line.startswith('### FILE:'):
            path_str_raw = line[len('### FILE:') :].strip()
            if not path_str_raw:
                raise ValueError('Empty path in FILE directive')
            path_str = normalize_path_string(path_str_raw)
            if not path_str:
                raise ValueError('Path in FILE directive becomes empty after normalization')
            current_file_path = Path(path_str)
            collecting_code = False
            code_lines = []
            continue

        if line.startswith('### DELETE:'):
            path_str_raw = line[len('### DELETE:') :].strip()
            if not path_str_raw:
                raise ValueError('Empty path in DELETE directive')
            path_str = normalize_path_string(path_str_raw)
            if not path_str:
                raise ValueError('Path in DELETE directive becomes empty after normalization')
            operations.append(Operation(kind='delete', path=Path(path_str)))
            continue

        if line.startswith('### MKDIR:'):
            path_str_raw = line[len('### MKDIR:') :].strip()
            if not path_str_raw:
                raise ValueError('Empty path in MKDIR directive')
            path_str = normalize_path_string(path_str_raw)
            if not path_str:
                raise ValueError('Path in MKDIR directive becomes empty after normalization')
            operations.append(Operation(kind='mkdir', path=Path(path_str)))
            continue

    if current_file_path is not None:
        raise ValueError(
            f'Unclosed FILE block for path "{current_file_path}". Missing closing ```.',
        )

    return operations


def validate_operations(operations: list[Operation]) -> None:
    if not operations:
        raise ValueError('No operations found in clipboard text')

    for op in operations:
        if not op.path.is_absolute():
            raise ValueError(
                f'Path "{op.path}" is not absolute. All paths must be absolute.',
            )


def apply_operations(
    operations: list[Operation],
    dry_run: bool,
    encoding: str,
) -> None:
    writes = [op for op in operations if op.kind == 'write']
    deletes = [op for op in operations if op.kind == 'delete']
    mkdirs = [op for op in operations if op.kind == 'mkdir']

    print(
        f'Operations: {len(writes)} writes, ' f'{len(deletes)} deletes, {len(mkdirs)} mkdirs',
    )

    written = 0
    removed = 0
    created_dirs = 0

    for op in operations:
        path = op.path

        if op.kind == 'mkdir':
            if dry_run:
                print(f'[DRY-RUN] MKDIR  {path}')
                created_dirs += 1
                continue
            if not path.exists():
                print(f'MKDIR  {path}')
                path.mkdir(parents=True, exist_ok=True)
                created_dirs += 1
            else:
                print(f'SKIP   {path} (directory already exists)')

        elif op.kind == 'delete':
            if dry_run:
                if path.is_file():
                    print(f'[DRY-RUN] DELETE {path}')
                else:
                    print(f'[DRY-RUN] SKIP   {path} (file does not exist)')
                continue
            if path.is_file():
                print(f'DELETE {path}')
                path.unlink()
                removed += 1
            else:
                print(f'SKIP   {path} (file does not exist)')

        elif op.kind == 'write':
            if op.content is None:
                raise ValueError(f'Write operation for "{path}" without content')

            if dry_run:
                print(f'[DRY-RUN] WRITE  {path} (len={len(op.content)})')
                written += 1
                continue

            if not path.parent.exists():
                print(f'MKDIR  {path.parent}')
                path.parent.mkdir(parents=True, exist_ok=True)

            print(f'WRITE  {path}')
            path.write_text(op.content, encoding=encoding)
            written += 1

        else:
            raise ValueError(f'Unknown operation kind: {op.kind}')

    print(
        f'Done. Written: {written}, deleted: {removed}, ' f'directories created: {created_dirs}',
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Apply ChatGPT file operations from clipboard (### FILE/DELETE/MKDIR markers).',
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Only show planned operations, do not modify files.',
    )
    parser.add_argument(
        '--encoding',
        default='utf-8',
        help='Encoding for writing files (default: utf-8).',
    )

    args = parser.parse_args()

    try:
        text = read_clipboard_text()
    except ValueError as exc:
        print(f'Clipboard error: {exc}', file=sys.stderr)
        sys.exit(1)

    try:
        operations = parse_operations(text)
        validate_operations(operations)
    except ValueError as exc:
        print(f'Parse/validation error: {exc}', file=sys.stderr)
        sys.exit(1)

    try:
        apply_operations(operations, args.dry_run, args.encoding)
    except Exception as exc:
        print(f'Error while applying operations: {exc}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
