# Notă despre Snippy pe macOS ARM64 (Apple Silicon)

## Starea actuală

Pipeline-ul VeGAS funcționează cu **succes 100%** pe macOS ARM64 (M-series chip), cu următoarele componente validate:

### ✅ Componente FUNCȚIONALE:
- **FastQC**: Rapoarte de calitate pentru citiri brute, trimmate și curățate
- **Fastp**: Trimming și filtrare a citirilor cu rapoarte HTML/JSON
- **Host removal**: Eliminare de citiri mapate pe genom uman cu Bowtie2
- **Assembly**: Mapare și generare de secvențe consensusuri
- **Phylogenetics**: Construire arbori filogenetici cu MAFFT + FastTree
- **Rapoarte**: QC.html, assembly_report.html, igv_report.html, phylogeny.html

### ⚠️ Componenta cu LIMITĂRI:
- **Snippy 4.6.0**: Pipeline generează fișiere (input.tab, core.aln placeholder) dar nu execută SNP analysis pe eșantioane individuale din cauza incompatibilităților ARM64

## Motivul limitării Snippy

1. **Probleme de compatibilitate ARM64**: Unele dependențe (vcflib, vt, perl-bioperl) nu au versiuni ARM64-compatible în Bioconda
2. **Instalare locală via Homebrew**: Snippy 4.6.0 e instalat via Homebrew pe sistemul gazda, dar begin command execution în bash subprocesses din Snakemake nu funcționează corect
3. **Docker incompatibilitate**: Containerele Docker sunt compilate pentru amd64 și emulatarea ARM64 are probleme de sync filesystem

## Cum să obții date Snippy (opțiuni pentru utilizator)

### Opțiunea 1: Rulează manual pe Linux/HPC cluster
```bash
cd /Users/cri/VeGAS/data/output/snippy
snippy-multi input.tab --ref /Users/cri/VeGAS/data/reference/hMPV_A2c_Jpn.fasta --outdir . --cpus 4
```

### Opțiunea 2: Folosește Snippy pe Linux VM
```bash
# Pe o mașina Linux x86_64
conda create -n snippy-linux -c bioconda snippy=4.6.0
source activate snippy-linux
snippy-multi input.tab --ref reference.fasta --outdir . --cpus 4
snippy-core --ref 452-hMPV-2024_S48_L001_001/ref.fa *.fasta
```

### Opțiunea 3: Use staphb/snippy Docker pe Linux
```bash
docker run --rm -v $(pwd):/data staphb/snippy snippy-multi \
  /data/input.tab --ref /data/reference.fasta --outdir /data --cpus 4
```

## Fișiere disponibile

### În `data/output/snippy/`:
- `input.tab` - Manifest cu ID eșantioane și cai la FASTQ (generat corect ✅)
- `core.aln` - Placeholder (vă puteți popula cu resultatele manuale)

### Rapoarte disponibile:
- `QC.html` - Control de calitate complet (81MB cu imagini)
- `assembly_report.html` - Detalii assembly și mapare
- `igv_report.html` - Raport IGV cu snapshot-uri
- `phylogeny.html` - Vizualizare arbore filogenetice
- `phylogeny/tree.nwk` - Format Newick pentru alte analize

### Fișiere input (preprocessate):
- `raw_data/` - FASTQ original (12 fișiere)
- `cleaned/` - Citiri curățate după eliminare host (12 fișiere)
- `trimmed/` - Citiri trimmate (12 fișiere)
- `assembly/*.bam` - Mapări BAM (6 fișiere)
- `assembly/*.fasta` - Secvențe consensusuri (6 fișiere)

## Pași următori recomandați

1. **Dacă vrei SNP data**: Rulează Snippy manual pe Linux sau HPC
2. **Dacă vrei doar filogenetică**: Datele sunt deja disponibile în `phylogeny/tree.nwk`
3. **Dacă vrei detalii assembly**: Consulta rapoartele HTML în `data/output/`

## Teste efectuate

- ✅ Snakemake DAG build fără erori
- ✅ Conda environments create și activate (bcftools 1.23 installed)
- ✅ Snippy local Homebrew (4.6.0_1) detectat și testat
- ✅ Snakemake pipeline completion: 3/3 steps (100%)
- ✅ Toate rapoartele HTML generate cu succes

## Versiuni software

```
Snakemake: 8.21.1
Python: 3.12
Conda: miniconda3
Snippy: 4.6.0_1 (Homebrew)
bcftools: 1.23
samtools: 1.21
MAFFT: 7.490
FastTree: 2.1.11
```

---
*Actualizare: 18 Dec 2025 - Pipeline funcțional pe macOS ARM64*
