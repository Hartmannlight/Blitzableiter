from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str]) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return result.stdout.strip()


def is_ci() -> bool:
    return (
        os.environ.get('CI') == 'true'
        or 'GITHUB_ACTIONS' in os.environ
        or 'GITLAB_CI' in os.environ
    )


def repo_root() -> Path:
    out = run(['git', 'rev-parse', '--show-toplevel'])
    return Path(out) if out else Path('.')


def get_branch() -> str:
    return run(['git', 'rev-parse', '--abbrev-ref', 'HEAD'])


def get_email() -> str:
    return run(['git', 'config', 'user.email'])


def get_version(repo: Path) -> str | None:
    py = repo / 'pyproject.toml'
    if not py.exists():
        return None
    for line in py.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if line.startswith('version') and '=' in line:
            _, val = line.split('=', 1)
            return val.strip().strip('"').strip("'")
    return None


def show_dialog(branch: str, email: str, version: str | None) -> bool:
    import tkinter as tk  # local import to avoid issues in headless/CI

    root = tk.Tk()
    root.title('Commit check')
    root.geometry('460x240')
    root.resizable(False, False)

    tk.Label(
        root,
        text='Commit confirmation',
        font=('Segoe UI', 12),
    ).pack(pady=(10, 6))

    tk.Label(root, text='Branch', font=('Segoe UI', 10)).pack(anchor='w', padx=20)
    tk.Label(
        root,
        text=branch,
        font=('Segoe UI', 11, 'bold'),
        fg='#004a9f',
    ).pack(anchor='w', padx=40, pady=(0, 6))

    tk.Label(root, text='Email', font=('Segoe UI', 10)).pack(anchor='w', padx=20)
    tk.Label(
        root,
        text=email or 'N/A',
        font=('Segoe UI', 11, 'bold'),
        fg='#006400',
    ).pack(anchor='w', padx=40, pady=(0, 6))

    tk.Label(
        root,
        text='Version (pyproject.toml)',
        font=('Segoe UI', 10),
    ).pack(anchor='w', padx=20)
    ver_text = version if version else 'not found'
    tk.Label(
        root,
        text=ver_text,
        font=('Segoe UI', 11, 'bold'),
        fg='#8b0000' if version is None else '#000000',
    ).pack(anchor='w', padx=40, pady=(0, 10))

    result: dict[str, bool] = {'ok': False}

    def on_ok(_event: object | None = None) -> None:
        result['ok'] = True
        root.destroy()

    def on_cancel(_event: object | None = None) -> None:
        root.destroy()

    btn_frame = tk.Frame(root)
    btn_frame.pack(pady=5)
    tk.Button(
        btn_frame,
        text='Continue (Enter)',
        width=16,
        command=on_ok,
    ).pack(side='left', padx=6)
    tk.Button(
        btn_frame,
        text='Abort (Esc)',
        width=16,
        command=on_cancel,
    ).pack(side='left', padx=6)

    root.bind('<Return>', on_ok)
    root.bind('<Escape>', on_cancel)

    root.mainloop()
    return result['ok']


def main() -> int:
    if is_ci():
        return 0

    root_path = repo_root()
    branch = get_branch()
    email = get_email()
    version = get_version(root_path)

    ok = show_dialog(branch, email, version)
    if not ok:
        print('Commit aborted by user.')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
