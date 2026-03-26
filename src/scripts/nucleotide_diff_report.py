#!/usr/bin/env python3
import argparse
import os

import pandas as pd
import plotly.graph_objects as go
from jinja2 import Environment, FileSystemLoader
from plotly.offline import plot


BASE_TO_VALUE = {
    "A": 0,
    "C": 1,
    "G": 2,
    "T": 3,
    "N": 4,
    "-": 5,
}


VALUE_TO_BASE = {v: k for k, v in BASE_TO_VALUE.items()}


def normalize_to_ref_length(ref_seq, seq):
    ref_len = len(ref_seq)
    seq = seq[:ref_len]
    if len(seq) < ref_len:
        seq = seq + ("-" * (ref_len - len(seq)))
    return seq


def read_first_fasta_record(path):
    header = None
    seq = []
    with open(path, "rt") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            if line.startswith(">"):
                if header is None:
                    header = line[1:].split()[0]
                else:
                    break
            else:
                seq.append(line.upper())
    return header, "".join(seq)


def load_sample_list(folder):
    assembly_dir = os.path.join(folder, "assembly")
    samples = []
    for fn in sorted(os.listdir(assembly_dir)):
        if fn.endswith(".best_ref.txt"):
            samples.append(fn.replace(".best_ref.txt", ""))
    return samples


def diff_rows(ref_seq, classic_seq, snippy_seq):
    n = len(ref_seq)
    rows_any = []
    rows_classic_ai = []
    classic_vs_snippy = 0
    classic_vs_ref = 0
    snippy_vs_ref = 0

    for i in range(n):
        pos = i + 1
        ref_b = ref_seq[i]
        classic_b = classic_seq[i]
        snippy_b = snippy_seq[i]

        if classic_b != snippy_b:
            classic_vs_snippy += 1
            rows_classic_ai.append((pos, ref_b, classic_b, snippy_b))
        if classic_b != ref_b:
            classic_vs_ref += 1
        if snippy_b != ref_b:
            snippy_vs_ref += 1

        if classic_b != snippy_b or classic_b != ref_b or snippy_b != ref_b:
            rows_any.append((pos, ref_b, classic_b, snippy_b))

    return rows_any, rows_classic_ai, {
        "positions_compared": n,
        "classic_vs_snippy": classic_vs_snippy,
        "classic_vs_ref": classic_vs_ref,
        "snippy_vs_ref": snippy_vs_ref,
        "any_difference": len(rows_any),
    }


def build_position_plot(sample, diff_data, right_label="snippy"):
    x = [r[0] for r in diff_data]
    y = [1 for _ in diff_data]
    text = [f"pos={r[0]} ref={r[1]} classic={r[2]} {right_label}={r[3]}" for r in diff_data]

    fig = go.Figure(
        data=[
            go.Scatter(
                x=x,
                y=y,
                mode="markers",
                marker=dict(color="#E67E22", size=7),
                text=text,
                hovertemplate="%{text}<extra></extra>",
            )
        ]
    )
    fig.update_layout(
        title=f"{sample} - nucleotide differences",
        xaxis_title="Reference position",
        yaxis=dict(showticklabels=False, title="Difference"),
        plot_bgcolor="white",
        paper_bgcolor="white",
        height=260,
    )
    return plot(fig, output_type="div", include_plotlyjs=False)


def build_basegrid_plot(sample, ref_seq, classic_seq, snippy_seq):
    n = len(ref_seq)
    ref_seq = ref_seq[:n]
    classic_seq = classic_seq[:n]
    snippy_seq = snippy_seq[:n]

    rows = [
        [BASE_TO_VALUE.get(base, BASE_TO_VALUE["N"]) for base in ref_seq],
        [BASE_TO_VALUE.get(base, BASE_TO_VALUE["N"]) for base in classic_seq],
        [BASE_TO_VALUE.get(base, BASE_TO_VALUE["N"]) for base in snippy_seq],
    ]

    x_positions = list(range(1, n + 1))
    y_labels = ["REF", "CLASSIC", "SNIPPY"]

    customdata = []
    seqs = [ref_seq, classic_seq, snippy_seq]
    for row_name, seq in zip(y_labels, seqs):
        row_data = []
        for pos, base in enumerate(seq, start=1):
            row_data.append([row_name, pos, base])
        customdata.append(row_data)

    colorscale = [
        [0.0, "#2ECC71"],
        [0.1666, "#2ECC71"],
        [0.1667, "#3498DB"],
        [0.3333, "#3498DB"],
        [0.3334, "#F1C40F"],
        [0.5, "#F1C40F"],
        [0.5001, "#E74C3C"],
        [0.6666, "#E74C3C"],
        [0.6667, "#95A5A6"],
        [0.8333, "#95A5A6"],
        [0.8334, "#8E44AD"],
        [1.0, "#8E44AD"],
    ]

    fig = go.Figure(
        data=[
            go.Heatmap(
                z=rows,
                x=x_positions,
                y=y_labels,
                colorscale=colorscale,
                zmin=0,
                zmax=5,
                customdata=customdata,
                hovertemplate="Row=%{customdata[0]}<br>Pos=%{customdata[1]}<br>Base=%{customdata[2]}<extra></extra>",
                colorbar=dict(
                    title="Base",
                    tickvals=list(VALUE_TO_BASE.keys()),
                    ticktext=[VALUE_TO_BASE[i] for i in range(6)],
                ),
            )
        ]
    )
    fig.update_layout(
        title=f"{sample} - base-by-base matrix (REF / CLASSIC / SNIPPY)",
        xaxis_title="Reference position",
        yaxis_title="Sequence row",
        plot_bgcolor="white",
        paper_bgcolor="white",
        height=340,
    )
    return plot(fig, output_type="div", include_plotlyjs=False)


def write_tsv(path, rows):
    with open(path, "wt") as out:
        out.write("position\tref\tclassic\tsnippy\n")
        for pos, ref_b, classic_b, snippy_b in rows:
            out.write(f"{pos}\t{ref_b}\t{classic_b}\t{snippy_b}\n")


def write_excel_three_rows(path, sample_sequences):
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        for sample_name, ref_seq, classic_seq, snippy_seq in sample_sequences:
            n = len(ref_seq)
            ref_seq = ref_seq[:n]
            classic_seq = classic_seq[:n]
            snippy_seq = snippy_seq[:n]

            columns = ["type"] + [str(i) for i in range(1, n + 1)]
            ref_row = ["REF"] + list(ref_seq)
            classic_row = ["CLASIC"] + list(classic_seq)
            snippy_row = ["SNIPPY"] + list(snippy_seq)
            diff_row = ["DIFF"] + ["1" if c != s else "0" for c, s in zip(classic_seq, snippy_seq)]

            df = pd.DataFrame([ref_row, classic_row, snippy_row, diff_row], columns=columns)

            safe_sheet = sample_name[:31]
            df.to_excel(writer, index=False, sheet_name=safe_sheet)


def write_excel_per_sample(folder_path, sample_sequences):
    os.makedirs(folder_path, exist_ok=True)

    for sample_name, ref_seq, classic_seq, snippy_seq in sample_sequences:
        n = len(ref_seq)
        ref_seq = ref_seq[:n]
        classic_seq = classic_seq[:n]
        snippy_seq = snippy_seq[:n]

        columns = ["type"] + [str(i) for i in range(1, n + 1)]
        ref_row = ["REF"] + list(ref_seq)
        classic_row = ["CLASIC"] + list(classic_seq)
        snippy_row = ["SNIPPY"] + list(snippy_seq)

        df_three_rows = pd.DataFrame([ref_row, classic_row, snippy_row], columns=columns)

        out_file = os.path.join(folder_path, f"{sample_name}.xlsx")
        safe_sheet = "THREE_ROWS"

        long_df = pd.DataFrame(
            {
                "position": list(range(1, n + 1)),
                "REF": list(ref_seq),
                "CLASIC": list(classic_seq),
                "SNIPPY": list(snippy_seq),
                "DIFF": [1 if c != s else 0 for c, s in zip(classic_seq, snippy_seq)],
            }
        )

        with pd.ExcelWriter(out_file, engine="openpyxl") as writer:
            df_three_rows.to_excel(writer, index=False, sheet_name=safe_sheet)
            long_df.to_excel(writer, index=False, sheet_name="LONG")


def main():
    parser = argparse.ArgumentParser(description="Nucleotide-level comparison report")
    parser.add_argument("--folder", required=True)
    parser.add_argument("--install_path", required=True)
    args = parser.parse_args()

    out_folder = args.folder
    diff_dir = os.path.join(out_folder, "nucleotide_diffs")
    os.makedirs(diff_dir, exist_ok=True)

    sample_blocks = []
    sample_sequences = []

    for sample in load_sample_list(out_folder):
        best_ref_file = os.path.join(out_folder, "assembly", f"{sample}.best_ref.txt")
        classic_fasta = os.path.join(out_folder, "assembly", f"{sample}.fasta")
        snippy_fasta = os.path.join(out_folder, "snippy", sample, "snps.consensus.fa")

        if not (os.path.exists(best_ref_file) and os.path.exists(classic_fasta) and os.path.exists(snippy_fasta)):
            continue

        with open(best_ref_file, "rt") as bf:
            ref_prefix = bf.read().strip()

        ref_prefix = os.path.basename(ref_prefix)
        ref_fasta = os.path.join(out_folder, "ref_indexes", f"{ref_prefix}.fasta")
        if not os.path.exists(ref_fasta):
            continue

        _, ref_seq = read_first_fasta_record(ref_fasta)
        _, classic_seq = read_first_fasta_record(classic_fasta)
        _, snippy_seq = read_first_fasta_record(snippy_fasta)

        classic_seq = normalize_to_ref_length(ref_seq, classic_seq)
        snippy_seq = normalize_to_ref_length(ref_seq, snippy_seq)

        rows_any, rows_classic_ai, summary = diff_rows(ref_seq, classic_seq, snippy_seq)
        sample_sequences.append((sample, ref_seq, classic_seq, snippy_seq))

        tsv_any_path = os.path.join(diff_dir, f"{sample}.all_diffs.tsv")
        tsv_classic_ai_path = os.path.join(diff_dir, f"{sample}.classic_vs_snippy.tsv")
        write_tsv(tsv_any_path, rows_any)
        write_tsv(tsv_classic_ai_path, rows_classic_ai)

        plot_div = build_position_plot(sample, rows_any)
        base_plot_div = build_basegrid_plot(sample, ref_seq, classic_seq, snippy_seq)
        sample_blocks.append(
            {
                "sample": sample,
                "summary": summary,
                "diff_count": len(rows_any),
                "classic_ai_count": len(rows_classic_ai),
                "plot_div": plot_div,
                "base_plot_div": base_plot_div,
                "tsv_any_rel": os.path.relpath(tsv_any_path, out_folder),
                "tsv_classic_ai_rel": os.path.relpath(tsv_classic_ai_path, out_folder),
            }
        )

    env = Environment(
        loader=FileSystemLoader(os.path.join(args.install_path, "html_templates")),
        autoescape=False,
    )
    template = env.get_template("nucleotide_diff.html")
    html = template.render(sample_blocks=sample_blocks)

    out_html = os.path.join(out_folder, "nucleotide_diff_report.html")
    with open(out_html, "wt") as out:
        out.write(html)

    out_xlsx = os.path.join(out_folder, "nucleotide_3rows.xlsx")
    write_excel_three_rows(out_xlsx, sample_sequences)

    out_per_sample_dir = os.path.join(out_folder, "nucleotide_3rows_per_sample")
    write_excel_per_sample(out_per_sample_dir, sample_sequences)

    print(f"Wrote nucleotide diff report to {out_html}")
    print(f"Wrote Excel 3-row matrix to {out_xlsx}")
    print(f"Wrote per-sample Excel files to {out_per_sample_dir}")


if __name__ == "__main__":
    main()
