#!/usr/bin/env python3

import argparse, os, subprocess, shutil, tempfile

def run_cmd(cmd):
    r = subprocess.run(cmd, shell=True, text=True, capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(f"Command failed: {cmd}\n{r.stderr}")
    return r.stdout, r.stderr

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--references", nargs='+', required=True,
                        help="Bowtie 2 index *prefixes* (each must also have prefix.fasta for bcftools).")
    parser.add_argument("--r1", required=True, help="R1 FASTQ(.gz)")
    parser.add_argument("--r2", required=True, help="R2 FASTQ(.gz)")
    parser.add_argument("--threads", default="1", help="Threads for bcftools/bowtie2")
    parser.add_argument("--folder", required=True, help="Output folder")
    args = parser.parse_args()

    # We will store outputs in: {args.folder}/assembly/
    assembly_dir = os.path.join(args.folder, "assembly")
    os.makedirs(assembly_dir, exist_ok=True)

    # Derive sample name from R1 filename
    # Example:  sample_R1.fastq.gz -> sample
    sample_name = os.path.basename(args.r1).replace("_R1.fastq.gz", "")

    tmp_dir = tempfile.mkdtemp(prefix="best_ref_")
    try:
        best_ref = None
        best_rate = -1.0
        print("Checking alignment rate for each Bowtie 2 index prefix...")

        # 1) Align reads to each pre-built index & measure alignment rate
        for ref_prefix in args.references:
            ref_prefix = ref_prefix.replace(".1.bt2","")
            base = os.path.basename(ref_prefix)
            sam_out = os.path.join(tmp_dir, f"{base}.sam")
            log_file = os.path.join(tmp_dir, f"{base}.bowtie2.log")

            align_cmd = (
                f"bowtie2 -x {ref_prefix} "
                f"-p {args.threads} "
                f"-1 {args.r1} -2 {args.r2} "
                f"--very-sensitive "
                f"-S {sam_out} 2> {log_file}"
            )
            run_cmd(align_cmd)

            alignment_rate = 0.0
            with open(log_file) as lf:
                for line in lf:
                    if "overall alignment rate" in line:
                        rate_str = line.split("%")[0].strip()
                        alignment_rate = float(rate_str)
                        break

            print(f"Reference {ref_prefix}: {alignment_rate}% overall alignment")

            if alignment_rate > best_rate:
                best_rate = alignment_rate
                best_ref = ref_prefix

        print(f"\nBest reference prefix: {best_ref} with {best_rate}% alignment.\n")

        # We'll assume there's a FASTA named best_ref + ".fasta"
        best_fasta = best_ref + ".fasta"
        final_sam = os.path.join(tmp_dir, "best_alignment.sam")
        final_bam = os.path.join(tmp_dir, "best_alignment.bam")
        final_bam_sorted = os.path.join(tmp_dir, "best_alignment.sorted.bam")
        final_vcf = os.path.join(tmp_dir, "variants.vcf.gz")

        print("Performing reference-guided assembly with the best reference...")

        # Realign reads to the best reference prefix
        run_cmd(
            f"bowtie2 -x {best_ref} "
            f"-p {args.threads} "
            f"-1 {args.r1} -2 {args.r2} "
            f"--very-sensitive "
            f"-S {final_sam} 2>/dev/null"
        )

        # Convert SAM -> sorted BAM -> index
        run_cmd(f"samtools view -bS {final_sam} > {final_bam}")
        run_cmd(f"samtools sort {final_bam} -o {final_bam_sorted}")
        run_cmd(f"samtools index {final_bam_sorted}")
        print("Best fasta is : ", best_fasta)
        # mpileup + call -> compressed VCF
        mpileup_cmd = (
            f"bcftools mpileup --threads {args.threads} "
            f"-f {best_fasta} {final_bam_sorted}"
        )
        call_cmd = "bcftools call -mv -Oz -o {vcf}".format(vcf=final_vcf)
        run_cmd(f"{mpileup_cmd} | {call_cmd}")
        run_cmd(f"bcftools index {final_vcf}")

        # Make final consensus
        final_consensus_path = os.path.join(assembly_dir, f"{sample_name}.fasta")
        run_cmd(f"bcftools consensus -f {best_fasta} {final_vcf} > {final_consensus_path}")

        # Copy final BAM and BAI
        final_bam_path = os.path.join(assembly_dir, f"{sample_name}.bam")
        final_bai_path = final_bam_path + ".bai"
        shutil.copyfile(final_bam_sorted, final_bam_path)
        shutil.copyfile(final_bam_sorted + ".bai", final_bai_path)

        print("Done.")
        print(f"Consensus FASTA: {final_consensus_path}")
        print(f"BAM: {final_bam_path}")
        print(f"BAI: {final_bai_path}")

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

if __name__ == "__main__":
    main()
