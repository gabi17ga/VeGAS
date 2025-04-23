import os
import glob

def get_sample_names(path):
    raw_fastq_zips_R1 = glob.glob(os.path.join(path, "*_R1.fastq.gz"))
    return [os.path.basename(f).replace("_R1.fastq.gz", "") for f in raw_fastq_zips_R1]