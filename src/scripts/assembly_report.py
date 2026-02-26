#!/usr/bin/env python3
import argparse, pathlib, numpy as np, pysam, jinja2, sys
from pyfaidx import Fasta
from plotly.subplots import make_subplots
import plotly.graph_objects as go
try:
    from utils import get_sample_names
except Exception:
    # If running as a script from another cwd, add scripts dir to path and retry
    import sys, os
    scripts_dir = os.path.dirname(__file__)
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    from utils import get_sample_names

def contig_lengths(fa):
    obj = Fasta(fa, as_raw=True, strict_bounds=False)
    d = {k: len(v) for k, v in obj.items()}
    obj.close()
    return d

def build_cov(bam, lens, bin_size):
    cov = {c: np.zeros((l // bin_size) + 1, dtype=np.uint32) for c, l in lens.items()}
    with pysam.AlignmentFile(bam) as fh:
        for r in fh.fetch(until_eof=True):
            if r.is_unmapped: continue
            c = fh.get_reference_name(r.reference_id)
            s, e = r.reference_start, (r.reference_end or r.reference_start + r.query_length)
            cov[c][s // bin_size:(e - 1) // bin_size + 1] += 1
    return cov

def cov_points(cov, lens, bin_size):
    off, x, y, cum = {}, [], [], 0
    for c in lens: off[c], cum = cum, cum + lens[c]
    for c, a in cov.items():
        idx = np.arange(a.size)
        x.extend(off[c] + idx * bin_size + bin_size // 2)
        y.extend(a.tolist())
    return x, y

def _pick_bam(folder: pathlib.Path, sample: str) -> pathlib.Path | None:
    """Return Path to BAM for *sample* or None if nothing found."""
    # priority: *.sorted.bam  >  *.bam
    cand = [folder / f"{sample}.sorted.bam",
            folder / f"{sample}.bam"]
    return next((p for p in cand if p.exists()), None)

def _ensure_index(bam: pathlib.Path):
    """Ensure <bam>.bai exists. Create one on the fly if missing."""
    idx = bam.with_suffix(bam.suffix + ".bai")
    if idx.exists():
        return
    print(f"  ↪ indexing {bam.name} …", file=sys.stderr)
    pysam.index(str(bam))           # creates bam.bai in‑place

def make_plot(sample, folder, bin_size):
    print(f"Processing {sample}…")
    folder = pathlib.Path(folder)
    asm = folder / f"{sample}.fasta"
    bam = _pick_bam(folder, sample)

    if not asm.exists():
        print(f"[warn] {sample}: missing fasta – skipped", file=sys.stderr)
        return ''
    if bam is None:
        print(f"[warn] {sample}: no BAM found – skipped", file=sys.stderr)
        return ''

    _ensure_index(bam)

    lens = contig_lengths(asm)
    cov  = build_cov(bam, lens, bin_size)
    x, y = cov_points(cov, lens, bin_size)

    pastel = '#A8D5E2'                       # base line colour

    fig = make_subplots(rows=1, cols=1)
    fig.add_trace(
        go.Scatter(
            x=x, y=y,
            mode='lines',
            line=dict(shape='spline', width=2, color=pastel),
            fill='tozeroy',                              # area under curve
            fillcolor='rgba(168,213,226,0.3)'            # same tone, 30 % opacity
        ),
        row=1, col=1
    )

    fig.update_xaxes(title_text='Consensus coordinate (bp)', showgrid=False)
    fig.update_yaxes(title_text='Read count / bin',        showgrid=False)
    fig.update_layout(
        height=400,
        showlegend=False,
        title=f'{sample}: reads vs consensus',
        plot_bgcolor='white',
        paper_bgcolor='white'
    )

    plot_div = fig.to_html(full_html=False, include_plotlyjs=False)
    return f'''
    <div class="row justify-content-center">
      <div class="col-md-10" style="width:60%;">
        {plot_div}
      </div>
    </div>'''


def main():
    ap = argparse.ArgumentParser(
        description='Generate an Assembly Report with coverage for each sample')
    ap.add_argument('--folder', required=True,
                    help='working directory containing sample files')
    ap.add_argument('--install_path', required=True,
                    help='path where assembly_report.html template lives')
    ap.add_argument('--bin_size', type=int, default=500)
    args = ap.parse_args()

    rows = []
    for s in get_sample_names(f"{args.folder}/raw_data"):
        r = make_plot(s, f"{args.folder}/assembly", args.bin_size)
        if r: rows.append(r)
    
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(f"{args.install_path}/html_templates"),
                             autoescape=False)
    tmpl = env.get_template('assembly.html')
    rendered = tmpl.render(rows=rows)

    out = pathlib.Path(args.folder, 'assembly_report.html')
    out.write_text(rendered)
    print(f'✔ Report written to {out}')

if __name__ == '__main__':
    main()
