#!/usr/bin/env python3
"""
Generate a simple alignment HTML that points to the phylogeny alignment FASTA.
Writes `data/output/alignment.html` by injecting the alignment path into
`src/html_templates/alignment.html`.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / 'src' / 'html_templates' / 'alignment.html'
DEFAULT_OUT_DIR = ROOT / 'data' / 'output'

def find_alignment(root):
    # search common locations
    candidates = [
        root / 'phylogeny' / 'alignment.fa',
        root / 'phylogeny' / 'alignment.fasta',
        root / 'phylogeny' / 'alignment.fa.gz'
    ]
    for c in candidates:
        if c.exists():
            return c
    # fallback: any .fa or .fasta under phylogeny
    p = root / 'phylogeny'
    if p.exists():
        for ext in ('*.fa','*.fasta'):
            for f in p.glob(ext):
                return f
    return None

def main():
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    aln = find_alignment(out_dir)
    if aln is None:
        print('No alignment found under', out_dir / 'phylogeny')
        sys.exit(2)
    # Use a web-relative path from out_dir (served root) to the alignment file
    # e.g., 'phylogeny/alignment.fa'
    try:
        rel = aln.relative_to(out_dir)
    except Exception:
        # alignment might already be under out_dir/phylogeny; fall back to absolute
        rel = aln

    tpl = TEMPLATE.read_text(encoding='utf8')
    html = tpl.replace('__ALIGNMENT_PATH__', str(rel).replace('\\','/'))
    out_path = out_dir / 'alignment.html'
    out_path.write_text(html, encoding='utf8')
    print('Wrote', out_path)

if __name__ == '__main__':
    main()
