"""Snapshots of one Java source tree, compiled and run.

A problem's code lives in <problem>/java/*.java, one type per file, written once. Lines that
exist only in some snapshots are wrapped in markers (flat, never nested):

    //@ from f3            visible from snapshot f3 on
    //@ until f3           visible before snapshot f3
    //@ from f1 until f4   visible from f1, before f4
    //@ end                closes the block
    //@ file from f2       first line only: the whole file exists from f2 on

Snapshots are ordered by the problem's SNAPS list, e.g. ['core', 'f1', ..., 'x'].
Runs of blank lines left behind by removed blocks are collapsed to one.
"""
import os
import re
import shutil
import subprocess
import tempfile

MARK = re.compile(r'^\s*//@\s*(.*?)\s*$')
JAVAC = shutil.which('javac') or 'javac'
JAVA = shutil.which('java') or 'java'


class Tree:
    def __init__(self, java_dir, snaps):
        self.dir = java_dir
        self.snaps = list(snaps)
        self.files = {}                      # name -> list of raw lines
        for f in sorted(os.listdir(java_dir)):
            if f.endswith('.java'):
                with open(os.path.join(java_dir, f), encoding='utf-8') as fh:
                    self.files[f] = fh.read().split('\n')

    def idx(self, snap):
        return self.snaps.index(snap)

    def _visible(self, cond, snap):
        """cond: dict with optional 'from'/'until'."""
        i = self.idx(snap)
        if 'from' in cond and i < self.idx(cond['from']):
            return False
        if 'until' in cond and i >= self.idx(cond['until']):
            return False
        return True

    @staticmethod
    def _parse(spec):
        words = spec.split()
        cond = {}
        k = 0
        while k < len(words):
            if words[k] in ('from', 'until') and k + 1 < len(words):
                cond[words[k]] = words[k + 1]
                k += 2
            else:
                raise ValueError('bad marker: //@ ' + spec)
        return cond

    def exists(self, name, snap):
        lines = self.files[name]
        m = MARK.match(lines[0]) if lines else None
        if m and m.group(1).startswith('file '):
            return self._visible(self._parse(m.group(1)[5:]), snap)
        return True

    def text(self, name, snap):
        """The file as it reads in `snap`, or None if it does not exist yet."""
        if not self.exists(name, snap):
            return None
        out, cond = [], None
        lines = self.files[name]
        for n, line in enumerate(lines):
            m = MARK.match(line)
            if m:
                spec = m.group(1)
                if n == 0 and spec.startswith('file '):
                    continue
                if spec == 'end':
                    if cond is None:
                        raise ValueError(f'{name}:{n + 1}: //@ end without a block')
                    cond = None
                else:
                    if cond is not None:
                        raise ValueError(f'{name}:{n + 1}: nested //@ block')
                    cond = self._parse(spec)
                continue
            if cond is None or self._visible(cond, snap):
                out.append(line)
        if cond is not None:
            raise ValueError(f'{name}: unclosed //@ block')
        # collapse blank runs, trim blank lines just inside braces
        clean = []
        for line in out:
            if line.strip() == '' and clean and clean[-1].strip() == '':
                continue
            clean.append(line)
        final = []
        for k, line in enumerate(clean):
            if line.strip() == '':
                prev = final[-1].rstrip() if final else ''
                nxt = clean[k + 1].strip() if k + 1 < len(clean) else ''
                if prev.endswith('{') or nxt.startswith('}'):
                    continue
            final.append(line)
        while final and final[-1].strip() == '':
            final.pop()
        return '\n'.join(final) + '\n'

    def names(self, snap):
        return [n for n in self.files if self.exists(n, snap)]


def compile_run(sources, mains=(), timeout=120, runs=1, java_args=(), strict=True):
    """sources: {name: text}. Compiles all; runs each class in `mains` `runs` times.
    Returns (ok, compile_output, {main: [(exit_code, output), ...]})."""
    d = tempfile.mkdtemp(prefix='wbsnap_')
    try:
        for name, text in sources.items():
            with open(os.path.join(d, name), 'w', encoding='utf-8') as fh:
                fh.write(text)
        flags = ['-Xlint:all', '-Werror'] if strict else ['-nowarn']
        cmd = [JAVAC, *flags, '-d', os.path.join(d, 'out')] + [os.path.join(d, n) for n in sources]
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        comp = (p.stdout + p.stderr).replace(d + os.sep, '')
        comp = '\n'.join(l for l in comp.split('\n') if 'JAVA_TOOL_OPTIONS' not in l).strip()
        if p.returncode != 0:
            return False, comp, {}
        results = {}
        for m in mains:
            results[m] = []
            for _ in range(runs):
                try:
                    r = subprocess.run([JAVA, *java_args, '-cp', os.path.join(d, 'out'), m],
                                       capture_output=True, text=True, timeout=timeout)
                    outp = '\n'.join(l for l in (r.stdout + r.stderr).split('\n')
                                     if 'JAVA_TOOL_OPTIONS' not in l).rstrip() + '\n'
                    results[m].append((r.returncode, outp))
                except subprocess.TimeoutExpired:
                    results[m].append((124, 'TIMEOUT\n'))
        return True, comp, results
    finally:
        shutil.rmtree(d, ignore_errors=True)
