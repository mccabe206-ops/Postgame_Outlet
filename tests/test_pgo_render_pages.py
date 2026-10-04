"""Small child processes exercise concurrent rendering without real app renders."""
from contextlib import redirect_stderr, redirect_stdout
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, call, patch

import pgo_render_pages as render


class RenderPagesTests(unittest.TestCase):
    def scripts(self, root, codes):
        for (name, filename, arguments), code in zip(render.RENDERERS, codes):
            # A sequential runner cannot pass this rendezvous. Each successful
            # child writes a separate output only after both have started.
            source = f'''from pathlib import Path
import sys
import time
root = Path.cwd()
assert sys.argv[1:] == {list(arguments)!r}
(root / {name + '.started'!r}).write_text('started')
deadline = time.monotonic() + 5
while not all((root / (name + '.started')).exists() for name in ('board', 'forecast_lab')):
    if time.monotonic() >= deadline:
        raise SystemExit(99)
    time.sleep(0.01)
(root / {name + '.finished'!r}).write_text('finished')
raise SystemExit({code})
'''
            (root / filename).write_text(source, encoding='utf-8')

    def test_both_renderers_start_before_either_is_joined(self):
        with tempfile.TemporaryDirectory(prefix='pgo render ') as temp:
            root = Path(temp)
            self.scripts(root, (0, 0))
            with redirect_stdout(io.StringIO()):
                result = render.render_pages(root)
            self.assertEqual(result, {'board': 0, 'forecast_lab': 0})
            self.assertTrue(all((root / (name + '.finished')).exists() for name in result))

    def test_either_or_both_failures_still_join_both_children(self):
        for codes in ((3, 0), (0, 4), (3, 4)):
            with self.subTest(codes=codes), tempfile.TemporaryDirectory(prefix='pgo render ') as temp:
                root = Path(temp)
                self.scripts(root, codes)
                with redirect_stdout(io.StringIO()):
                    result = render.render_pages(root)
                self.assertEqual(list(result.values()), list(codes))
                self.assertTrue(all((root / (name + '.finished')).exists() for name in result))

    def test_spawn_uses_current_interpreter_fixed_arguments_and_no_shell(self):
        children = [Mock(), Mock()]
        for child in children:
            child.wait.return_value = 0
        with patch.object(render.subprocess, 'Popen', side_effect=children) as spawn, redirect_stdout(io.StringIO()):
            result = render.render_pages(render.ROOT)
        self.assertEqual(spawn.call_args_list, [
            call([sys.executable, str(render.ROOT / 'pgo_comparison.py'), '--refresh-mccabe'],
                 cwd=render.ROOT, shell=False),
            call([sys.executable, str(render.ROOT / 'pgo_forecast_lab.py')],
                 cwd=render.ROOT, shell=False),
        ])
        self.assertEqual(result, {'board': 0, 'forecast_lab': 0})
        for child in children:
            child.wait.assert_called_once_with()
            child.terminate.assert_not_called()

    def test_second_spawn_failure_stops_and_reaps_first_owned_child(self):
        child = Mock()
        child.poll.return_value = None
        with patch.object(render.subprocess, 'Popen', side_effect=[child, OSError('spawn failed')]), \
             redirect_stdout(io.StringIO()), self.assertRaisesRegex(OSError, 'spawn failed'):
            render.render_pages()
        child.terminate.assert_called_once_with()
        child.wait.assert_called_once_with(timeout=5)

    def test_first_spawn_failure_does_not_attempt_another_process(self):
        with patch.object(render.subprocess, 'Popen', side_effect=OSError('spawn failed')) as spawn, \
             redirect_stdout(io.StringIO()), self.assertRaises(OSError):
            render.render_pages()
        spawn.assert_called_once()

    def test_interrupt_stops_only_owned_running_children_and_reaps_both(self):
        first, second = Mock(), Mock()
        first.poll.return_value = 0
        first.wait.side_effect = [KeyboardInterrupt, 0]
        second.poll.return_value = None
        second.wait.side_effect = [subprocess.TimeoutExpired('owned renderer', 5), -9]
        with patch.object(render.subprocess, 'Popen', side_effect=[first, second]), \
             redirect_stdout(io.StringIO()), self.assertRaises(KeyboardInterrupt):
            render.render_pages()
        first.terminate.assert_not_called()
        first.wait.assert_has_calls([call(), call(timeout=5)])
        second.terminate.assert_called_once_with()
        second.kill.assert_called_once_with()
        second.wait.assert_has_calls([call(timeout=5), call()])

    def test_cli_succeeds_only_after_both_successful_results(self):
        for outcomes, expected in (({'board': 0, 'forecast_lab': 0}, 0),
                                   ({'board': 1, 'forecast_lab': 0}, 1),
                                   ({'board': 0, 'forecast_lab': -9}, 1)):
            with self.subTest(outcomes=outcomes), patch.object(render, 'render_pages', return_value=outcomes), \
                 redirect_stderr(io.StringIO()):
                self.assertEqual(render.main(), expected)
        for error, expected in ((KeyboardInterrupt(), 130), (OSError('launch failed'), 1)):
            with self.subTest(error=type(error).__name__), patch.object(render, 'render_pages', side_effect=error), \
                 redirect_stderr(io.StringIO()):
                self.assertEqual(render.main(), expected)


if __name__ == '__main__':
    unittest.main()
