#!/usr/bin/env python3
import os
import glob
import zipfile
import argparse
import json
from collections import defaultdict

import plotly.express as px
import plotly.graph_objects as go
from plotly.offline import plot
import plotly.offline as pyo
from plotly.subplots import make_subplots

from jinja2 import Template
from jinja2 import Environment, FileSystemLoader

import math

colors = {
    "raw": "#A3C1DA",       # Pastel blue
    "trimmed": "#B3DE81",   # Pastel green
    "cleaned": "#F7A1A1"    # Pastel red
}

fill_colors = {
    "raw": "rgba(163, 193, 218, 0.3)",   # Partially transparent for area
    "trimmed": "rgba(179, 222, 129, 0.3)",
    "cleaned": "rgba(247, 161, 161, 0.3)"
}

def format_number(n):
    if n >= 1000:
        return f"{n/1000:.1f}k".rstrip('0').rstrip('.')  # Converts 1500 → 1.5k, 2000 → 2k
    return str(n)

###########################################################
# Parse data
###########################################################

def parse_fastqc_per_base_quality(fastqc_zip_path):
    """
    Returns a list of dicts, each of which has:
      {
        "base_label": str,       # e.g. "1", or "10-14"
        "mean": float,
        "median": float,
        "q1": float,             # lower quartile
        "q3": float,             # upper quartile
        "p10": float,            # 10th percentile
        "p90": float             # 90th percentile
      }
    """
    data = []
    with zipfile.ZipFile(fastqc_zip_path, 'r') as z:
        data_txt_path = None
        # Find fastqc_data.txt in the ZIP
        for name in z.namelist():
            if name.endswith("fastqc_data.txt"):
                data_txt_path = name
                break
        if not data_txt_path:
            return data  # empty if not found

        in_section = False
        with z.open(data_txt_path) as f:
            lines = [line.decode("utf-8") for line in f]
            for line in lines:
                line = line.strip()
                if line.startswith(">>Per base sequence quality"):
                    in_section = True
                    continue
                if in_section:
                    if line.startswith(">>END_MODULE"):
                        break
                    if not line or line.startswith("#"):
                        continue
                    # Typical columns:
                    # Base | Mean | Median | Lower Quartile | Upper Quartile | 10th Percentile | 90th Percentile
                    parts = line.split()
                    if len(parts) < 7:
                        # Some lines might not conform or might be comments
                        continue
                    base_label = parts[0]
                    mean_val    = float(parts[1])
                    median_val  = float(parts[2])
                    q1_val      = float(parts[3])
                    q3_val      = float(parts[4])
                    p10_val     = float(parts[5])
                    p90_val     = float(parts[6])
                    data.append({
                        "base_label": base_label,
                        "mean": mean_val,
                        "median": median_val,
                        "q1": q1_val,
                        "q3": q3_val,
                        "p10": p10_val,
                        "p90": p90_val
                    })
    return data

def parse_fastqc_length_distribution(fastqc_zip_path):
    length_counts = []
    with zipfile.ZipFile(fastqc_zip_path, 'r') as z:
        data_txt_path = None
        for name in z.namelist():
            if name.endswith("fastqc_data.txt"):
                data_txt_path = name
                break
        if not data_txt_path:
            return length_counts

        in_section = False
        with z.open(data_txt_path) as f:
            lines = [line.decode("utf-8") for line in f]
            for line in lines:
                if line.startswith(">>Sequence Length Distribution"):
                    in_section = True
                    continue
                if in_section:
                    if line.startswith(">>END_MODULE"):
                        break
                    if line.startswith("#"):
                        continue
                    parts = line.strip().split()
                    if len(parts) == 2:
                        length_str, count_str = parts
                        length = int(length_str.split("-")[0])  # just take lower bound if "50-75"
                        count = int(float(count_str))
                        length_counts.append((length, count))
    return length_counts

def parse_fastp_json(fastp_json_path):
    with open(fastp_json_path, 'r') as f:
        data = json.load(f)

    result = {
        "summary": data.get("summary"),
        "filtering_result": data.get("filtering_result"),
        "adapter_cutting": data.get("adapter_cutting"),
        "read1_before_filtering": data.get("read1_before_filtering"),
        "read1_after_filtering": data.get("read1_after_filtering"),
        "read2_before_filtering": data.get("read2_before_filtering"),
        "read2_after_filtering": data.get("read2_after_filtering")
    }

    return result

###########################################################
# Create plots
###########################################################

def build_html_row(line_plot, donut1, donut2, donut3, table):
    return f"""
    <div class="row w-100">
        <!-- first third -->
        <div class="col-md-6">
            {line_plot}
        </div>

        <!-- middle third: two stacked plots -->
        <div class="col-md-6 d-flex flex-column">
            <div class="flex-fill">{donut1}</div>
            <div class="flex-fill">{donut2}</div>
        </div>

    </div>
    """
    # <html lang="en">
    #     <head>
    #         <meta charset="UTF-8">
    #         <title>Bootstrap Grid Example</title>
    #         <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
    #     </head>
    #     <body>
    #         <div class="container my-4">
    #             <div class="row">
    #                 <div class="col-md-8 border p-3">1 (spans 2 rows of content)</div>
    #                 <div class="col-md-4 border p-3">2</div>
    #             </div>
    #             <div class="row">
    #                 <!-- Offset by 8 columns to start beneath the top-right column -->
    #                 <div class="col-md-4 offset-md-8 border p-3">3</div>
    #             </div>
    #         </div>
    #     </body>
    # </html>

def build_distribution_plot(data_R1, data_R2, data_json, max_reads, sample_name):
    fig = go.Figure()

    total_reads = {
        "raw": 0,
        "trimmed": 0,
        "cleaned": 0
    }

    # Existing code to add traces
    for stage in ["raw", "trimmed", "cleaned"]:
        if stage in data_R1:
            length_counts = data_R1[stage]
            total_reads[stage] += sum([lc[1] for lc in length_counts])
            if not length_counts:
                continue
            x_vals = [lc[0] for lc in length_counts]
            y_vals = [lc[1] for lc in length_counts]
            fig.add_trace(
                go.Scatter(
                    x=x_vals,
                    y=y_vals,
                    mode="lines",
                    fill="tozeroy",
                    line_shape="spline",
                    name=f"{stage} R1",
                    line=dict(color=colors[stage], width=2, dash="solid"),
                    fillcolor=fill_colors[stage]
                )
            )
        if stage in data_R2:
            length_counts = data_R2[stage]
            total_reads[stage] += sum([lc[1] for lc in length_counts])
            if not length_counts:
                continue
            x_vals = [lc[0] for lc in length_counts]
            y_vals = [lc[1] for lc in length_counts]
            fig.add_trace(
                go.Scatter(
                    x=x_vals,
                    y=y_vals,
                    mode="lines",
                    fill="tozeroy",
                    line_shape="spline",
                    name=f"{stage} R2",
                    line=dict(color=colors[stage], width=2, dash="dash"),
                    fillcolor=fill_colors[stage]
                )
            )

    # Calculate total reads (assuming data_json has 'total_reads')
    total_reads_raw = total_reads["raw"]
    after_filtering = total_reads["trimmed"]
    reads_filtered = total_reads["raw"] - total_reads["trimmed"]
    total_reads_cleaned = total_reads["cleaned"]
    removed = total_reads["trimmed"] - total_reads["cleaned"]

    # Define y-axis ranges
    y_log_min = 0  # Start from 0, but log scale will handle actual min
    y_log_max = math.log10(max_reads) if max_reads > 1 else 1

    # Calculate values for donut chart
    total_lost = reads_filtered + removed
    total_remaining = total_reads_cleaned
    # Calculate values for donut chart (now 3 categories)
    donut_values = [reads_filtered, removed, total_reads_cleaned]
    donut_labels = ['Bad quality/Filtered', 'Host removal', 'Clean reads']
    
    # Add donut chart trace centered in plot
    fig.add_trace(go.Pie(
        values=donut_values,
        labels=donut_labels,
        hole=0.95,
        marker_colors=['#FF9999', '#99CCFF', '#99FF99'],
        textinfo='label+percent',
        textposition='auto',
        insidetextorientation='radial',
        hoverinfo='label+value+percent',
        domain={'x': [0.65, 0.95], 'y': [0.45, 0.7]},  # Centered in main plot area
        showlegend=False,
        textfont=dict(
            family='Arial, sans-serif',
            size=12,
            color='#404040'
        )
    ))

    # Update layout with annotation and buttons
    fig.update_layout(
        height=920,
        xaxis_title="Read Length",
        yaxis_title="Count",
        paper_bgcolor="white",
        plot_bgcolor="white",
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=False, range=[0, max_reads]),
        hovermode="x unified",
        annotations=[
            # Title row
            dict(
                x=0.4,
                y=0.7,
                xref="paper",
                yref="paper",
                text=f"<b>{sample_name}</b>",
                showarrow=False,
                font=dict(color="rgb(130,130,130)", size=25, family="Arial, sans-serif"),
                xanchor="center",
                yanchor="middle"
            ),
            dict(
                x=0.396,
                y=0.65,
                xref="paper",
                yref="paper",
                text=f"<b>Total raw reads:</b>",
                showarrow=False,
                font=dict(color="rgb(130,130,130)", size=20, family="Arial, sans-serif"),
                xanchor="right",
                yanchor="middle",
            ),
            dict(
                x=0.405,
                y=0.65,
                xref="paper",
                yref="paper",
                text=f"{format_number(total_reads_raw)}",  # Apply formatting here
                showarrow=False,
                font=dict(color="rgb(150,150,150)", size=20, family="Arial, sans-serif"),
                xanchor="left",
                yanchor="middle",
            ),
            
            # Subsequent rows
            *[dict(
                x=0.395,
                y=0.65 - (i*0.04),
                xref="paper",
                yref="paper",
                text=text,
                showarrow=False,
                font=dict(color="rgb(130,130,130)", size=20, family="Arial, sans-serif"),
                xanchor="right",
                yanchor="middle",
            ) for i, text in enumerate([
                f"<b>After filtering:</b>",
                f"<b>After host removal:</b>",
                f"<b>Filtered reads:</b>",
                f"<b>Aligned to host:</b>"
            ], start=1)],
            
            *[dict(
                x=0.405,
                y=0.65 - (i*0.04),
                xref="paper",
                yref="paper",
                text=f"{format_number(value)}",  # Apply formatting to all values
                showarrow=False,
                font=dict(color="rgb(150,150,150)", size=20, family="Arial, sans-serif"),
                xanchor="left",
                yanchor="middle",
            ) for i, value in enumerate([
                after_filtering,
                total_reads_cleaned,
                reads_filtered,
                removed
            ], start=1)]
        ],
        updatemenus=[
            dict(
                type="buttons",
                buttons=[
                    dict(
                        label="Linear",
                        method="relayout",
                        args=[
                            {
                                "xaxis.type": "linear",
                                "yaxis.type": "linear",
                                "yaxis.range": [0, max_reads],
                                "annotations[0].visible": True,
                                "annotations[1].visible": True,
                                "annotations[2].visible": True,
                                "annotations[3].visible": True,
                                "annotations[4].visible": True,
                                "annotations[5].visible": True,
                                "annotations[6].visible": True,
                                "annotations[7].visible": True,
                                "annotations[8].visible": True,
                                "annotations[9].visible": True,
                                "annotations[10].visible": True,
                                "annotations[11].visible": True,
                                "annotations[12].visible": True,
                                "annotations[13].visible": True
                            }
                        ]
                    ),
                    dict(
                        label="Log",
                        method="relayout",
                        args=[
                            {
                                "xaxis.type": "log",
                                "yaxis.type": "log",
                                "yaxis.range": [y_log_min, y_log_max],
                                "annotations[0].visible": False,
                                "annotations[1].visible": False,
                                "annotations[2].visible": False,
                                "annotations[3].visible": False,
                                "annotations[4].visible": False,
                                "annotations[5].visible": False,
                                "annotations[6].visible": False,
                                "annotations[7].visible": False,
                                "annotations[8].visible": False,
                                "annotations[9].visible": False,
                                "annotations[10].visible": False,
                                "annotations[11].visible": False,
                                "annotations[12].visible": False,
                                "annotations[13].visible": False
                            }
                        ]
                    )
                ],
                direction="left",
                pad={"r": 10, "t": 10},
                showactive=True,
                x=0.0,
                y=1.15,
                xanchor="left",
                yanchor="top"
            )
        ]
    )


    return fig.to_html(full_html=False)

def build_donut_plot():
    fig = go.Figure()
    fig.add_trace(
        go.Pie(
            labels=["A", "C", "G", "T"],
            values=[10, 20, 30, 40],
            hole=0.5,
            marker=dict(colors=["#AEC6CF", "#FFD1DC", "#C5E3BF", "#FDFD96"]),
            textinfo="percent+label",
            textposition="outside"  # places labels outside, with lines
        )
    )
    fig.update_layout(
        showlegend=False  # hide legend box to rely on lines for labeling
    )
    return fig.to_html(full_html=False)
    
def build_table(data_json, data_R1, data_R2):
    
    # Return a dummy table for now
    table_data = []
    for sample in data_json:
        row = {
            "Sample": sample,
            "Raw R1": data_R1.get("raw", ""),
            "Trimmed R1": data_R1.get("trimmed", ""),
            "Cleaned R1": data_R1.get("cleaned", ""),
            "Raw R2": data_R2.get("raw", ""),
            "Trimmed R2": data_R2.get("trimmed", ""),
            "Cleaned R2": data_R2.get("cleaned", "")
        }
        table_data.append(row)
    
    fig = go.Figure(data=[go.Table(
        header=dict(values=list(table_data[0].keys()), fill_color='paleturquoise', align='left'),
        cells=dict(values=list(zip(*[list(row.values()) for row in table_data])), fill_color='lavender', align='left'))
    ])
    
    return fig.to_html(full_html=False)

def build_fastqc_like_plot(quality_rows):
    """
    quality_rows is a list of dicts, each containing:
      {
        'base_label': '1', 'mean': 33.27, 'median': 34.0, 'q1': 33.0, 'q3': 34.0,
        'p10': 32.0, 'p90': 35.0
      }
    """

    # Expand any multi-base row like "10-14"
    expanded = []
    for row in quality_rows:
        label = row["base_label"]
        try:
            if "-" in label:
                start_str, end_str = label.split("-")
                start, end = int(start_str), int(end_str)
            else:
                start = end = int(label)
        except ValueError:
            continue

        # Create an entry for each base in the range
        for base in range(start, end + 1):
            expanded.append({
                "base_position": base,
                "median": row["median"],
                "q1": row["q1"],
                "q3": row["q3"],
                "p10": row["p10"],
                "p90": row["p90"]
            })

    fig = go.Figure()

    # Create a Box trace for each base with pastel colors
    for row in expanded:
        fig.add_trace(
            go.Box(
                x=[row['base_position']],
                q1=[row['q1']],
                median=[row['median']],
                q3=[row['q3']],
                lowerfence=[row['p10']],
                upperfence=[row['p90']],
                boxpoints=False,
                fillcolor='#B3E5FC',  # Pastel blue
                line=dict(color='#4A90E2', width=1),  # Darker blue
                width=0.8,  # Narrower boxes
                showlegend=False
            )
        )

    # Add background quality zones with pastel colors
    fig.update_layout(
        shapes=[
            # Red zone
            dict(type="rect", yref='y', xref='paper',
                 y0=0, y1=20, x0=0, x1=1,
                 fillcolor='rgba(255,205,210,0.3)',  # Pastel red
                 line_width=0, layer='below'),
            # Orange zone
            dict(type="rect", yref='y', xref='paper',
                 y0=20, y1=28, x0=0, x1=1,
                 fillcolor='rgba(255,224,178,0.3)',  # Pastel orange
                 line_width=0, layer='below'),
            # Green zone
            dict(type="rect", yref='y', xref='paper',
                 y0=28, y1=40, x0=0, x1=1,
                 fillcolor='rgba(200,230,201,0.3)',  # Pastel green
                 line_width=0, layer='below')
        ],
        annotations=[
            dict(
                x=0.5, y=10,
                xref='paper', yref='y',
                text="Poor Quality (≤20)",
                showarrow=False,
                font=dict(color='#d32f2f', size=12),
                bgcolor='rgba(255,255,255,0.7)'
            ),
            dict(
                x=0.5, y=24,
                xref='paper', yref='y',
                text="Fair Quality (21-28)",
                showarrow=False,
                font=dict(color='#f57c00', size=12),
                bgcolor='rgba(255,255,255,0.7)'
            ),
            dict(
                x=0.5, y=34,
                xref='paper', yref='y',
                text="Good Quality (≥29)",
                showarrow=False,
                font=dict(color='#388e3c', size=12),
                bgcolor='rgba(255,255,255,0.7)'
            )
        ],
        xaxis=dict(
            title=dict(text="Position in Read (bp)", font=dict(size=14)),
            showgrid=True,
            gridcolor='#e0e0e0',
            tickfont=dict(color='#2c3e50')
        ),
        yaxis=dict(
            title=dict(text="Phred Quality Score", font=dict(size=14)),
            range=[0, 40],
            showgrid=True,
            gridcolor='#e0e0e0',
            tickfont=dict(color='#2c3e50')
        ),
        plot_bgcolor='white',
        paper_bgcolor='white',
        margin=dict(t=60, b=60, l=60, r=30),
        hovermode='x unified'
    )

    # Add watermark-style annotation
    fig.add_annotation(
        x=1, y=-0.15,
        xref='paper', yref='paper',
        text="FastQC-like Quality Plot",
        showarrow=False,
        font=dict(size=12, color='#95a5a6'),
        align='right'
    )

    return fig.to_html(full_html=False)

###########################################################
# Main
###########################################################

def main():
    parser = argparse.ArgumentParser(
        description="Create a single HTML Plotly report showing read length distribution for raw/trimmed/cleaned samples."
    )
    parser.add_argument("--folder", required=True, help="The working dir")
    parser.add_argument("--install_path", required=True, help="The install path")
    args = parser.parse_args()

    raw_fastqc_dir = os.path.join(args.folder, "fastqc_raw")
    trimmed_fastqc_dir = os.path.join(args.folder, "fastqc_trimmed")
    cleaned_fastqc_dir = os.path.join(args.folder, "fastqc_cleaned")
    fastp_dir = os.path.join(args.folder, "fastp")
    output = os.path.join(args.folder, "QC.html")
    install_path = args.install_path

    #######################################################
    # Extract data for R1
    #######################################################

    # We'll look for <sample>_R1_fastqc.zip in each directory
    # and parse each sample. Adjust if your naming is different.
    raw_fastqc_zips_R1 = glob.glob(os.path.join(raw_fastqc_dir, "*_R1_fastqc.zip"))
    samples = []
    for f in raw_fastqc_zips_R1:
        # e.g. "sample1_R1_fastqc.zip" -> "sample1"
        base = os.path.basename(f)
        sample = basefig
        samples.append(sample)

    # We'll store data in a structure:
    # data[sample][stage] = list of (length, count)
    # stage can be "raw", "trimmed", "cleaned"
    data_R1 = defaultdict(dict)
    full_data_R1 = defaultdict(dict)
    for sample in samples:
        # raw
        raw_zip = os.path.join(raw_fastqc_dir, f"{sample}_R1_fastqc.zip")
        if os.path.exists(raw_zip):
            data_R1[sample]["raw"] = parse_fastqc_length_distribution(raw_zip)
        # trimmed
        trimmed_zip = os.path.join(trimmed_fastqc_dir, f"{sample}_R1_fastqc.zip")
        if os.path.exists(trimmed_zip):
            data_R1[sample]["trimmed"] = parse_fastqc_length_distribution(trimmed_zip)
        # cleaned
        cleaned_zip = os.path.join(cleaned_fastqc_dir, f"{sample}_R1_fastqc.zip")
        if os.path.exists(cleaned_zip):
            data_R1[sample]["cleaned"] = parse_fastqc_length_distribution(cleaned_zip)
            full_data_R1[sample] = parse_fastqc_per_base_quality(cleaned_zip)

    ###########################################################
    # Extract data for R2
    ###########################################################

    # We'll look for <sample>_R2_fastqc.zip in each directory
    # and parse each sample. Adjust if your naming is different.
    data_R2 = defaultdict(dict)
    full_data_R2 = defaultdict(dict)
    raw_fastqc_zips_R2 = glob.glob(os.path.join(raw_fastqc_dir, "*_R2_fastqc.zip"))
    for f in raw_fastqc_zips_R2:
        # e.g. "sample1_R2_fastqc.zip" -> "sample1"
        base = os.path.basename(f)
        sample = base.replace("_R2_fastqc.zip", "")
        if sample not in samples:
            continue

        # raw
        raw_zip = os.path.join(raw_fastqc_dir, f"{sample}_R2_fastqc.zip")
        if os.path.exists(raw_zip):
            data_R2[sample]["raw"] = parse_fastqc_length_distribution(raw_zip)
        # trimmed
        trimmed_zip = os.path.join(trimmed_fastqc_dir, f"{sample}_R2_fastqc.zip")
        if os.path.exists(trimmed_zip):
            data_R2[sample]["trimmed"] = parse_fastqc_length_distribution(trimmed_zip)
        # cleaned
        cleaned_zip = os.path.join(cleaned_fastqc_dir, f"{sample}_R2_fastqc.zip")
        if os.path.exists(cleaned_zip):
            data_R2[sample]["cleaned"] = parse_fastqc_length_distribution(cleaned_zip)
            full_data_R2[sample] = parse_fastqc_per_base_quality(cleaned_zip)

    ###########################################################
    # Extract data from fastp JSON files
    ###########################################################

    jsons = glob.glob(os.path.join(fastp_dir, "*.json"))
    # samples = [f.replace(".json", "") for f in jsons]
    data_json = defaultdict(dict)
    for f,sample in zip(jsons, samples):
        if os.path.exists(f):
            data_json[sample] = parse_fastp_json(f)
        else:
            raise FileNotFoundError(f"File {f} not found.")
    
    # Get the max length count from all samples
    max_R1 = max([max([lc[1] for lc in data_R1[sample]["raw"]]) for sample in samples])
    max_R2 = max([max([lc[1] for lc in data_R2[sample]["raw"]]) for sample in samples])
    maximum = max(max_R1, max_R2)
    
    rows = []
    for sample in samples:
        line_plot = build_distribution_plot(data_R1[sample], data_R2[sample], data_json[sample], maximum, sample)
        fastqc_plot_R1 = build_fastqc_like_plot(full_data_R1[sample])
        fastqc_plot_R2 = build_fastqc_like_plot(full_data_R2[sample])
        # donut12 = build_donut_plot()
        donut1 = build_donut_plot()
        donut2 = build_donut_plot()
        table = build_table(data_json[sample], data_R1[sample], data_R2[sample])
    
        row = build_html_row(line_plot, fastqc_plot_R1, fastqc_plot_R2, donut1, table)
        rows.append(row)
    
    # Load html template
    env = Environment(loader=FileSystemLoader(install_path))
    env.globals.update(zip=zip)
    template = env.get_template("html_templates/QC.html")

    # # Render the template
    # template = Template(html_content)
    rendered_html = template.render(rows=rows)

    # Write rendered HTML
    with open(output, 'w') as f:
        f.write(rendered_html)
if __name__ == "__main__":
    main()
