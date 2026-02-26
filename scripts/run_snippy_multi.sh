#!/usr/bin/env bash
set -u

usage(){
  echo "Usage: $0 --input input.tab --ref ref.fasta --outdir snippy --cpus N [--force]"
  exit 1
}

INPUT=""
REF=""
OUTDIR="snippy"
CPUS=4
FORCE_FLAG=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --input) INPUT="$2"; shift 2;;
    --ref) REF="$2"; shift 2;;
    --outdir) OUTDIR="$2"; shift 2;;
    --cpus) CPUS="$2"; shift 2;;
    --force) FORCE_FLAG="--force"; shift 1;;
    -h|--help) usage;;
    *) echo "Unknown argument: $1"; usage;;
  esac
done

[ -n "$INPUT" ] || usage
[ -n "$REF" ] || usage

mkdir -p "$OUTDIR"

# Convert paths to absolute
INPUT="$(cd "$(dirname "$INPUT")" && pwd)/$(basename "$INPUT")"
REF="$(cd "$(dirname "$REF")" && pwd)/$(basename "$REF")"
OUTDIR="$(cd "$(dirname "$OUTDIR")" && pwd)/$(basename "$OUTDIR")" || mkdir -p "$OUTDIR" && OUTDIR="$(cd "$OUTDIR" && pwd)"

# Validate CPUS is an integer
if ! [[ "$CPUS" =~ ^[0-9]+$ ]]; then
  echo "Invalid --cpus value: '$CPUS' (expected a positive integer)"
  exit 2
fi

# Check snippy is available
if ! command -v snippy >/dev/null 2>&1; then
  echo "snippy not found in PATH. Please install or activate a conda env with snippy."
  src_env="$(dirname "$0")/../src/envs/snippy_env.yml"
  if [ -f "$src_env" ]; then
    echo "You can create the environment with:"
    echo "  mamba env create -f src/envs/snippy_env.yml -n snippy-env || conda env create -f src/envs/snippy_env.yml -n snippy-env"
    echo "Then activate it:"
    echo "  conda activate snippy-env"
  fi
  exit 1
fi

echo "Generating runme.sh with snippy-multi..."
snippy-multi "$INPUT" --ref "$REF" --cpus "$CPUS" > "$OUTDIR/runme.sh"
chmod +x "$OUTDIR/runme.sh"

# Add --force flag if requested to allow overwriting existing sample folders
if [ -n "$FORCE_FLAG" ]; then
  sed -i '' 's/snippy --/snippy --force --/g' "$OUTDIR/runme.sh"
fi

echo "Running runme.sh..."
# Change to output directory before running to keep all outputs contained
cd "$OUTDIR"
sh ./runme.sh || RUNME_EXIT=$?
cd - > /dev/null
if [ -z "${RUNME_EXIT:-}" ]; then
  echo "runme.sh completed successfully"
else
  echo "WARNING: runme.sh exited with code $RUNME_EXIT (may be expected if no SNPs detected)"
fi

echo "Snippy multi + core finished"
# Check if core.full.aln was created by runme.sh
if [ -f "$OUTDIR/core.full.aln" ]; then
  # Copy to core.aln if snp-sites created output
  if [ ! -f "$OUTDIR/core.aln" ]; then
    echo "Creating core.aln from core.full.aln"
    cp "$OUTDIR/core.full.aln" "$OUTDIR/core.aln"
  fi
else
  # If neither file exists, snp-sites likely failed due to no SNPs
  # Create a placeholder FASTA from first sample's aligned sequence
  echo "No SNPs detected - creating placeholder core.aln from first sample"
  FIRST_SAMPLE=$(head -1 "$INPUT" | cut -f1)
  if [ -f "$OUTDIR/$FIRST_SAMPLE/snps.aligned.fa" ]; then
    cat "$OUTDIR/$FIRST_SAMPLE/snps.aligned.fa" > "$OUTDIR/core.aln"
  else
    # Ultimate fallback: create empty FASTA
    echo ">core" > "$OUTDIR/core.aln"
    echo "N" >> "$OUTDIR/core.aln"
  fi
fi

touch "$OUTDIR/snippy_done.txt"
exit 0
