"""Render the public board and Forecast Lab concurrently; publish neither here.

The existing CLIs validate their own inputs and atomically replace distinct
outputs (docs/index.html and docs/forecast-lab.html). Run after weekly reviews
and while holding the existing publishing lock. Both children must succeed.
"""
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
RENDERERS = (
    ('board', 'pgo_comparison.py', ('--refresh-mccabe',)),
    ('forecast_lab', 'pgo_forecast_lab.py', ()),
)


def _stop_children(children):
    """Stop/reap only processes launched by this invocation after interruption."""
    for _, child in children:
        if child.poll() is None:
            child.terminate()
    for _, child in children:
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()


def render_pages(root=ROOT):
    root = Path(root).resolve()
    children = []
    try:
        for name, script, arguments in RENDERERS:
            print(f'Starting {name} renderer', flush=True)
            children.append((name, subprocess.Popen(
                [sys.executable, str(root / script), *arguments], cwd=root,
                shell=False)))
        outcomes = {}
        for name, child in children:
            outcomes[name] = child.wait()
            print(f'{name} renderer exited {outcomes[name]}', flush=True)
        return outcomes
    except BaseException:
        _stop_children(children)
        raise


def main():
    try:
        outcomes = render_pages()
    except KeyboardInterrupt:
        print('Rendering interrupted; owned renderer processes stopped.', file=sys.stderr)
        return 130
    except OSError as error:
        print(f'Cannot run page renderers: {error}', file=sys.stderr)
        return 1
    failed = [name for name, code in outcomes.items() if code != 0]
    if failed:
        print('Rendering failed: ' + ', '.join(failed) + '; publication must stop.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
