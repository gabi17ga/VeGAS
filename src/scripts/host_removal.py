#!/usr/bin/env python3
import argparse, glob, gzip, os, shutil, subprocess, tempfile

def gzip_out(src: str, dst: str) -> None:
    """Gzip‑compress src to dst."""
    with open(src, "rb") as fi, gzip.open(dst, "wb") as fo:
        shutil.copyfileobj(fi, fo)

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--r1", required=True)
    p.add_argument("--r2", required=True)
    p.add_argument("--out_r1", required=True)
    p.add_argument("--out_r2", required=True)
    p.add_argument("--folder", required=True)
    p.add_argument("--threads", default="1")
    a = p.parse_args()

    os.makedirs(a.folder, exist_ok=True)
    sample = os.path.basename(a.r1).replace("_R1.fastq.gz", "")

    summary_path = os.path.join(a.folder, "removal_summary.txt")
    with open(summary_path, "w") as s:
        s.write("Removal Summary (paired-end)\n")

    total_removed = 0
    host_indexes = sorted(glob.glob(os.path.join("host_indexes", "*.1.bt2")))
    host_indexes = [f.replace(".1.bt2", "").replace(".rev", "") for f in host_indexes]
    host_indexes = list(set(host_indexes))

    with tempfile.TemporaryDirectory(dir=a.folder) as work:
        curr_r1 = os.path.join(work, f"{sample}_1.fastq")
        curr_r2 = os.path.join(work, f"{sample}_2.fastq")
        shutil.copyfile(a.r1, curr_r1)
        shutil.copyfile(a.r2, curr_r2)

        for f in host_indexes:
            base = os.path.basename(f).replace(".1.bt2", "")
            idx = os.path.join("host_indexes", base)

            unmapped = os.path.join(work, f"{base}_unmapped")
            mapped = os.path.join(work, f"{base}_mapped")
            stats = os.path.join(work, f"{base}_stats.txt")

            cmd = [
                "bowtie2", "-x", idx,
                "-1", curr_r1, "-2", curr_r2,
                "-p", a.threads,
                "--very-sensitive",
                "--end-to-end",
                "--un-conc", f"{unmapped}.fastq",
                "--al-conc", f"{mapped}.fastq"
            ]
            print("Running:", " ".join(cmd))
            res = subprocess.run(cmd, capture_output=True, text=True)
            with open(stats, "w") as sf:
                sf.write(res.stderr)

            exact = multi = unaligned = total = 0
            for line in res.stderr.splitlines():
                if "aligned exactly 1 time" in line:
                    exact = int(line.split()[0])
                elif "aligned >1 times" in line:
                    multi = int(line.split()[0])
                elif "paired; of these:" in line:
                    total = int(line.split()[0])
                elif "aligned concordantly 0 times" in line:
                    unaligned = int(line.split()[0])

            removed = exact + multi
            total_removed += removed
            print(f"[{base}] {removed:,}/{total:,} mapped; {unaligned:,} left")

            with open(summary_path, "a") as s:
                s.write(f"{base}\t{removed}\n")

            u1 = f"{unmapped}.1.fastq"
            u2 = f"{unmapped}.2.fastq"
            if os.path.exists(u1) and os.path.exists(u2):
                shutil.move(u1, curr_r1)
                shutil.move(u2, curr_r2)
            else:
                open(curr_r1, "a").close()
                open(curr_r2, "a").close()
                break

        gzip_out(curr_r1, a.out_r1 if a.out_r1.endswith(".gz") else f"{a.out_r1}.gz")
        gzip_out(curr_r2, a.out_r2 if a.out_r2.endswith(".gz") else f"{a.out_r2}.gz")

    print(f"\nTotal removed: {total_removed:,} pairs")
    print(f"Final unaligned files:\n  R1 → {a.out_r1}\n  R2 → {a.out_r2}")
    print("Detailed log:", summary_path)

if __name__ == "__main__":
    main()
