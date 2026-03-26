#!/usr/bin/env python3
import argparse
import os
from itertools import combinations

import numpy as np
import plotly.graph_objects as go
from plotly.offline import plot
from jinja2 import Environment, FileSystemLoader


def parse_vcf_variant_count(vcf_path):
    count = 0
    with open(vcf_path, "rt") as handle:
        for line in handle:
            if line.startswith("#"):
                continue
            if line.strip():
                count += 1
    return count


def parse_fasta_records(fasta_path):
    records = {}
    current_name = None
    current_seq = []

    with open(fasta_path, "rt") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith(">"):
                if current_name is not None:
                    records[current_name] = "".join(current_seq)
                current_name = line[1:].split()[0]
                current_seq = []
            else:
                current_seq.append(line.upper())

    if current_name is not None:
        records[current_name] = "".join(current_seq)

    return records


def snp_distance(seq_a, seq_b):
    valid = {"A", "C", "G", "T"}
    dist = 0
    for base_a, base_b in zip(seq_a, seq_b):
        if base_a in valid and base_b in valid and base_a != base_b:
            dist += 1
    return dist


def compute_distance_matrix(records):
    sample_names = list(records.keys())
    n = len(sample_names)
    matrix = np.zeros((n, n), dtype=int)

    for i, j in combinations(range(n), 2):
        d = snp_distance(records[sample_names[i]], records[sample_names[j]])
        matrix[i, j] = d
        matrix[j, i] = d

    return sample_names, matrix


def build_barplot(sample_counts):
    samples = [sample for sample, _ in sample_counts]
    counts = [count for _, count in sample_counts]

    fig = go.Figure(
        data=[go.Bar(x=samples, y=counts, marker_color="#8FB9E3")]
    )
    fig.update_layout(
        title="SNP count per sample",
        xaxis_title="Sample",
        yaxis_title="SNP count",
        plot_bgcolor="white",
        paper_bgcolor="white",
    )
    return plot(fig, output_type="div", include_plotlyjs=False)


def build_heatmap(sample_names, matrix):
    fig = go.Figure(
        data=[
            go.Heatmap(
                z=matrix,
                x=sample_names,
                y=sample_names,
                colorscale="Blues",
                colorbar=dict(title="SNP distance"),
            )
        ]
    )
    fig.update_layout(
        title="Pairwise SNP distance matrix (from core.aln)",
        xaxis_title="Sample",
        yaxis_title="Sample",
        plot_bgcolor="white",
        paper_bgcolor="white",
    )
    return plot(fig, output_type="div", include_plotlyjs=False)


def main():
    parser = argparse.ArgumentParser(description="Generate Snippy summary report")
    parser.add_argument("--folder", required=True, help="Working directory")
    parser.add_argument("--install_path", required=True, help="Install/src path")
    args = parser.parse_args()

    snippy_dir = os.path.join(args.folder, "snippy")
    core_aln = os.path.join(snippy_dir, "core.aln")

    sample_counts = []
    if os.path.isdir(snippy_dir):
        for name in sorted(os.listdir(snippy_dir)):
            sample_dir = os.path.join(snippy_dir, name)
            if not os.path.isdir(sample_dir):
                continue
            vcf_path = os.path.join(sample_dir, "snps.vcf")
            if os.path.exists(vcf_path):
                sample_counts.append((name, parse_vcf_variant_count(vcf_path)))

    sample_names = []
    matrix = np.zeros((0, 0), dtype=int)
    if os.path.exists(core_aln):
        records = parse_fasta_records(core_aln)
        if records:
            sample_names, matrix = compute_distance_matrix(records)

    barplot_div = build_barplot(sample_counts) if sample_counts else "<p>No per-sample snps.vcf files found.</p>"
    heatmap_div = (
        build_heatmap(sample_names, matrix)
        if len(sample_names) > 0
        else "<p>No core.aln found or alignment is empty.</p>"
    )

    env = Environment(loader=FileSystemLoader(os.path.join(args.install_path, "html_templates")), autoescape=False)
    template = env.get_template("snippy.html")

    rendered = template.render(
        sample_counts=sample_counts,
        barplot_div=barplot_div,
        heatmap_div=heatmap_div,
    )

    out_path = os.path.join(args.folder, "snippy_report.html")
    with open(out_path, "wt") as handle:
        handle.write(rendered)

    print(f"Wrote Snippy report to {out_path}")


if __name__ == "__main__":
    main()
