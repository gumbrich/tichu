import gzip
import json
from pathlib import Path
import tempfile
import unittest

from tichu.improve import paired_change


class PairedComparisonTests(unittest.TestCase):
    def test_rejects_different_deals_and_incomplete_runs(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = [Path(directory)/name for name in ('a', 'b')]
            manifest = dict(seed=1, pairs=2, mode='rounds', opponent='search',
                            external_revision='fixed', status='complete')
            for path, margins in zip(paths, ((10, 20), (0, 10))):
                path.mkdir()
                (path/'manifest.json').write_text(json.dumps(manifest))
                with gzip.open(path/'pairs.jsonl.gz', 'wt') as handle:
                    for i, margin in enumerate(margins):
                        handle.write(json.dumps({'pair': i, 'games': [
                            {'our_margin': margin}, {'our_margin': margin}]})+'\n')
            self.assertEqual(paired_change(*paths)['mean'], 10)
            for key, value in (('seed', 2), ('status', 'running'), ('opponent', 'other')):
                (paths[1]/'manifest.json').write_text(json.dumps({**manifest, key: value}))
                with self.assertRaises(ValueError):
                    paired_change(*paths)


if __name__ == '__main__':
    unittest.main()
