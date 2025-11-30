# scripts/gpt_copy.py
from __future__ import annotations

import argparse
import sys
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

import pyperclip  # type: ignore[import]
import yaml  # type: ignore[import]


@dataclass
class TreeConfig:
    ignored_dirs: set[str] = field(default_factory=set)
    ignored_files: set[str] = field(default_factory=set)
    ignored_extensions: set[str] = field(default_factory=set)


def load_config(path: Path | None) -> TreeConfig:
    if path is None or not path.is_file():
        return TreeConfig()

    with path.open('r', encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}

    ignored_dirs = set(data.get('ignored_dirs', []) or [])
    ignored_files = set(data.get('ignored_files', []) or [])
    ignored_extensions = set(data.get('ignored_extensions', []) or [])

    return TreeConfig(
        ignored_dirs=ignored_dirs,
        ignored_files=ignored_files,
        ignored_extensions=ignored_extensions,
    )


def should_skip(path: Path, config: TreeConfig) -> bool:
    name = path.name

    if path.is_dir():
        return name in config.ignored_dirs

    if name in config.ignored_files:
        return True

    for ext in config.ignored_extensions:
        if name.endswith(ext):
            return True

    return False


def filtered_entries(directory: Path, config: TreeConfig) -> list[Path]:
    entries: list[Path] = []
    for entry in directory.iterdir():
        if should_skip(entry, config):
            continue
        entries.append(entry)

    entries.sort(key=lambda p: (not p.is_dir(), p.name.lower()))
    return entries


def build_tree_and_file_list(root: Path, config: TreeConfig) -> tuple[list[str], list[Path]]:
    lines: list[str] = [root.name or str(root)]
    files: list[Path] = []

    def walk(directory: Path, prefix: str) -> None:
        entries = filtered_entries(directory, config)
        last_index = len(entries) - 1

        for index, entry in enumerate(entries):
            is_last = index == last_index
            connector = '└── ' if is_last else '├── '

            lines.append(f'{prefix}{connector}{entry.name}')

            if entry.is_dir():
                extension = '    ' if is_last else '│   '
                walk(entry, prefix + extension)
            else:
                files.append(entry)

    if root.is_dir():
        walk(root, '')
    else:
        files.append(root)

    return lines, files


def read_file_safely(path: Path) -> str:
    try:
        with path.open('r', encoding='utf-8', errors='replace') as f:
            return f.read()
    except OSError:
        return ''


def build_clipboard_text(root: Path, config: TreeConfig) -> str:
    tree_lines, files = build_tree_and_file_list(root, config)

    parts: list[str] = []
    parts.append('\n'.join(tree_lines))
    parts.append('')

    for idx, file_path in enumerate(files):
        abs_path = str(file_path.resolve())
        parts.append(f'# {abs_path}')

        content = read_file_safely(file_path)
        parts.append(content)
        parts.append('')

        if idx != len(files) - 1:
            parts.append('# ----- FILE SEPARATOR -----')
            parts.append('')
            parts.append('')

    return '\n'.join(parts).rstrip() + '\n'


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            'Print directory tree and copy tree + file contents to clipboard, '
            'using a YAML-based blacklist.'
        ),
    )
    parser.add_argument(
        'path',
        nargs='?',
        default='.',
        help='Directory to scan (default: current directory).',
    )
    parser.add_argument(
        '-c',
        '--config',
        default=None,
        help=(
            'Path to YAML config file. If omitted, the script searches in '
            '<root>/gpt_copy.yml and <script_dir>/gpt_copy.yml.'
        ),
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def resolve_config_path(arg_value: str | None, root: Path) -> Path | None:
    if arg_value:
        return Path(arg_value).expanduser().resolve()

    script_dir = Path(__file__).resolve().parent

    candidates = [
        root / 'gpt_copy.yml',
        script_dir / 'gpt_copy.yml',
    ]

    for candidate in candidates:
        if candidate.is_file():
            return candidate

    return None


def console_supports_box_chars() -> bool:
    encoding = sys.stdout.encoding or 'utf-8'
    sample = '├── │   └──'
    try:
        sample.encode(encoding)
        return True
    except UnicodeEncodeError:
        return False


def normalize_tree_line_for_console(line: str, use_box_chars: bool) -> str:
    if use_box_chars:
        return line
    result = line
    result = result.replace('│   ', '|   ')
    result = result.replace('├──', '|--')
    result = result.replace('└──', '`--')
    return result


def main(argv: Iterable[str] | None = None) -> None:
    args = parse_args(argv)

    root = Path(args.path).expanduser().resolve()
    config_path = resolve_config_path(args.config, root)
    config = load_config(config_path)

    text = build_clipboard_text(root, config)
    try:
        pyperclip.copy(text)
    except pyperclip.PyperclipException:
        print(
            'Warning: could not copy result to clipboard. Printing tree only.',
            file=sys.stderr,
        )

    tree_lines, _ = build_tree_and_file_list(root, config)
    use_box_chars = console_supports_box_chars()

    for line in tree_lines:
        print(normalize_tree_line_for_console(line, use_box_chars))


if __name__ == '__main__':
    main()
