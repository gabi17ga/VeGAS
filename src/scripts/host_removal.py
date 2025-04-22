#!/usr/bin/env python3

import argparse, glob, os, shutil, subprocess

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--r1", required=True, help="Input R1 FASTQ(.gz)")
    parser.add_argument("--r2", required=True, help="Input R2 FASTQ(.gz)")
    parser.add_argument("--out_r1", required=True, help="Output R1 file path")
    parser.add_argument("--out_r2", required=True, help="Output R2 file path")
    parser.add_argument("--host", required=True, help="Folder with Bowtie2 indexes (*.1.bt2, etc.)")
    parser.add_argument("--folder", required=True, help="Working directory")
    parser.add_argument("--threads", default="1", help="Threads for Bowtie2")
    args = parser.parse_args()

    sample_name = os.path.basename(args.r1).replace("_R1.fastq.gz", "")

    os.makedirs(args.folder, exist_ok=True)
    curr_r1 = os.path.join(args.folder, f"{sample_name}_1.fastq")
    curr_r2 = os.path.join(args.folder, f"{sample_name}_2.fastq")

    # Copy the input reads to our working directory
    shutil.copyfile(args.r1, curr_r1)
    shutil.copyfile(args.r2, curr_r2)

    # Create a summary file
    summary_file = os.path.join(args.folder, "removal_summary.txt")
    with open(summary_file, "w") as s:
        s.write("Removal Summary (paired-end)\n")

    # Loop over each Bowtie2 index in --host_genome folder
    # (We look for "*.1.bt2" to get the prefix.)
    for f in sorted(glob.glob(os.path.join(args.host, "*.1.bt2"))):
        base = os.path.basename(f).replace(".1.bt2", "")
        index_path = f.replace(".1.bt2", "")

        unmapped_prefix = os.path.join(args.folder, f"{base}_unmapped")
        mapped_prefix   = os.path.join(args.folder, f"{base}_mapped")
        stats_file      = os.path.join(args.folder, f"{base}_stats.txt")

        cmd = [
            "bowtie2",
            "-x", index_path,
            "-1", curr_r1,
            "-2", curr_r2,
            "-p", args.threads,
            "--un-conc", f"{unmapped_prefix}.fastq",
            "--al-conc", f"{mapped_prefix}.fastq"
        ]
        # Run Bowtie2 and capture its stderr to parse stats
        result = subprocess.run(cmd, capture_output=True, text=True)
        with open(stats_file, "w") as sf:
            sf.write(result.stderr)

        # Parse out the count of reads aligned exactly once or more than once
        exact, multi = 0, 0
        with open(stats_file) as st:
            for line in st:
                if "aligned exactly 1 time" in line:
                    exact = int(line.split()[0])
                elif "aligned >1 times" in line:
                    multi = int(line.split()[0])
        removed = exact + multi

        with open(summary_file, "a") as s:
            s.write(f"{base} removed {removed} read pairs\n")

        # Move the unmapped read pairs so next loop iteration only cleans further
        shutil.move(f"{unmapped_prefix}.1.fastq", curr_r1)
        shutil.move(f"{unmapped_prefix}.2.fastq", curr_r2)

    # Move the final unmapped reads to the desired output locations
    shutil.move(curr_r1, args.out_r1)
    shutil.move(curr_r2, args.out_r2)

    print("Host removal complete.")
    print(f"Final unaligned read 1: {args.out_r1}")
    print(f"Final unaligned read 2: {args.out_r2}")
    print(f"See {summary_file} for the removal summary.")

if __name__ == "__main__":
    main()
