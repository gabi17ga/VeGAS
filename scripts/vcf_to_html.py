#!/usr/bin/env python3
"""
Convert VCF to interactive HTML table
Usage: vcf_to_html.py <vcf_file> <output.html>
"""

import sys
import re
from pathlib import Path

def parse_vcf(vcf_file):
    """Parse VCF file and extract variants"""
    variants = []
    with open(vcf_file) as f:
        for line in f:
            if line.startswith('#'):
                continue
            fields = line.strip().split('\t')
            if len(fields) < 5:
                continue
            
            variant = {
                'CHROM': fields[0],
                'POS': fields[1],
                'ID': fields[2],
                'REF': fields[3],
                'ALT': fields[4],
                'QUAL': fields[5],
                'FILTER': fields[6],
                'INFO': fields[7],
                'FORMAT': fields[8] if len(fields) > 8 else '',
                'SAMPLES': fields[9:] if len(fields) > 9 else []
            }
            variants.append(variant)
    return variants

def vcf_to_html(vcf_file, output_file):
    """Generate HTML report from VCF"""
    variants = parse_vcf(vcf_file)
    
    html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>VCF Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
        h1 {{ color: #333; }}
        .stats {{ background: white; padding: 15px; margin: 10px 0; border-radius: 5px; }}
        table {{ 
            border-collapse: collapse; 
            width: 100%; 
            background: white;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-top: 10px;
        }}
        th {{ 
            background: #4CAF50; 
            color: white; 
            padding: 12px; 
            text-align: left;
            font-weight: bold;
        }}
        td {{ 
            border: 1px solid #ddd; 
            padding: 10px;
        }}
        tr:nth-child(even) {{ background: #f9f9f9; }}
        tr:hover {{ background: #f0f0f0; }}
        .ref {{ background: #e3f2fd; }}
        .alt {{ background: #fff3e0; }}
        .info {{ font-size: 0.9em; color: #666; }}
    </style>
</head>
<body>
    <h1>📊 VCF Variants Report</h1>
    <div class="stats">
        <strong>Total variants:</strong> {total}
    </div>
    
    <table>
        <thead>
            <tr>
                <th>CHROM</th>
                <th>POS</th>
                <th>REF</th>
                <th>ALT</th>
                <th>QUAL</th>
                <th>TYPE</th>
                <th>INFO</th>
            </tr>
        </thead>
        <tbody>
""".format(total=len(variants))
    
    for v in variants:
        # Determine variant type from INFO
        var_type = 'SNV'
        if 'TYPE=' in v['INFO']:
            match = re.search(r'TYPE=(\w+)', v['INFO'])
            if match:
                var_type = match.group(1)
        
        # Extract key INFO fields
        info_short = v['INFO'][:100] + '...' if len(v['INFO']) > 100 else v['INFO']
        
        html += f"""            <tr>
                <td>{v['CHROM']}</td>
                <td>{v['POS']}</td>
                <td class="ref"><strong>{v['REF']}</strong></td>
                <td class="alt"><strong>{v['ALT']}</strong></td>
                <td>{v['QUAL']}</td>
                <td>{var_type}</td>
                <td class="info" title="{v['INFO']}">{info_short}</td>
            </tr>
"""
    
    html += """        </tbody>
    </table>
</body>
</html>
"""
    
    with open(output_file, 'w') as f:
        f.write(html)
    
    print(f"✅ HTML report generated: {output_file}")
    print(f"   Variants: {len(variants)}")

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: vcf_to_html.py <vcf_file> <output.html>")
        sys.exit(1)
    
    vcf_to_html(sys.argv[1], sys.argv[2])
