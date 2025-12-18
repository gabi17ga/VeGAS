#!/bin/bash

# Run the pipeline inside the official Snakemake container.
# Use -v to mount current dir, -e to pass environment variables, and place the image
# name before the command to execute inside the container.
docker run --rm \
  --name vegas \
  --platform linux/amd64 \
  -v "$(pwd)":/vegas \
  -v /Volumes/vegas/output:/vegas/data/output \
  -w /vegas \
  -e HOST_GENOME=/vegas/data/host/ \
  -e REFERENCE_GENOME=/vegas/data/reference/ \
  snakemake/snakemake \
  python src/main.py \
    -d /vegas/data/input/ \
    -o /vegas/data/output/ \
    -r /vegas/data/reference/ \
    -t /vegas/data/host/ \
    -c 1 -cc 1 --overwrite
