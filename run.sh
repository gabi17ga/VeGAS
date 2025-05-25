#! /bin/bash

docker run \
  --platform linux/amd64 \
  --volume .:/vegas \
  --workdir /vegas \
  host_genome=/vegas/data/host/ \
  reference_genome=/vegas/data/reference/ \
  snakemake/snakemake python src/main.py \
    -d /vegas/data/input/ \
    -o /vegas/data/output/ \
    -r /vegas/data/reference/ \
    -t /vegas/data/host/ \
    -c 1 -cc 1 --overwrite
