#!/usr/bin/env python3
"""Build a simple phylogeny from per-sample assembly FASTA files.

This script collects one representative sequence per sample (the first sequence
found in the fasta), writes a temporary multi-FASTA, aligns with MAFFT and builds
a tree with FastTree. Outputs:
  - phylogeny/alignment.fa
  - phylogeny/tree.nwk

It expects assembly FASTAs to be in "assembly/" under the working directory.
"""
import os
import glob
import subprocess
import argparse


def read_first_record(fasta_path):
    """Return tuple (header, seq) of the first FASTA record in file, or None."""
    header = None
    parts = []
    with open(fasta_path, 'rt') as fh:
        for line in fh:
            line = line.rstrip('\n')
            if not line:
                continue
            if line.startswith('>'):
                header = line[1:].split()[0]
                break
        if header is None:
            return None
        # read rest of first seq
        for line in fh:
            if line.startswith('>'):
                break
            parts.append(line.strip())
    seq = ''.join(parts)
    return header, seq


def write_multi_fasta(records, out_path):
    with open(out_path, 'wt') as fh:
        for name, seq in records:
            fh.write(f'>{name}\n')
            # wrap at 80
            for i in range(0, len(seq), 80):
                fh.write(seq[i:i+80] + '\n')


def run_cmd(cmd, cwd=None):
    print('Running:', ' '.join(cmd))
    res = subprocess.run(cmd, cwd=cwd)
    if res.returncode != 0:
        raise RuntimeError(f'Command failed: {cmd}')


def main():
    p = argparse.ArgumentParser(description='Create alignment and phylogenetic tree from assembly FASTAs')
    p.add_argument('--assembly-dir', default='assembly', help='Directory with per-sample FASTA files')
    p.add_argument('--out-dir', default='phylogeny', help='Output directory for alignment and tree')
    p.add_argument('--mafft-opts', default='--auto', help='Options to pass to MAFFT')
    args = p.parse_args()

    fasta_files = sorted(glob.glob(os.path.join(args.assembly_dir, '*.fasta')))
    if not fasta_files:
        print('No assembly fasta files found in', args.assembly_dir)
        return

    records = []
    for f in fasta_files:
        sample = os.path.splitext(os.path.basename(f))[0]
        rec = read_first_record(f)
        if rec is None:
            print('Warning: no FASTA records in', f)
            continue
        header, seq = rec
        records.append((sample, seq))

    os.makedirs(args.out_dir, exist_ok=True)
    tmp_fasta = os.path.join(args.out_dir, 'inputs.fasta')
    aln_out = os.path.join(args.out_dir, 'alignment.fa')
    tree_out = os.path.join(args.out_dir, 'tree.nwk')

    write_multi_fasta(records, tmp_fasta)

    # Run MAFFT
    try:
        run_cmd(['mafft'] + args.mafft_opts.split() + [tmp_fasta], cwd=None)
    except Exception as e:
        print('MAFFT failed:', e)
        raise

    # MAFFT writes to stdout; capture it to file
    # we'll run mafft again with output redirection
    with open(aln_out, 'wt') as fh:
        res = subprocess.run(['mafft'] + args.mafft_opts.split() + [tmp_fasta], stdout=fh)
        if res.returncode != 0:
            raise RuntimeError('MAFFT failed with return code ' + str(res.returncode))

    # Run FastTree (nucleotide)
    res = subprocess.run(['FastTree', '-nt', aln_out], stdout=open(tree_out, 'wt'))
    if res.returncode != 0:
        # try lowercase fasttree
        res2 = subprocess.run(['fasttree', '-nt', aln_out], stdout=open(tree_out, 'wt'))
        if res2.returncode != 0:
            raise RuntimeError('FastTree failed')

    print('Wrote alignment to', aln_out)
    print('Wrote tree to', tree_out)


if __name__ == '__main__':
    main()
