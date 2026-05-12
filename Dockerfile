FROM mambaorg/micromamba:1.5-jammy

ARG GMLST_VERSION=0.1.0

USER root

RUN micromamba install -y -n base -c bioconda -c conda-forge \
      python=3.12 \
      gmlst=${GMLST_VERSION} \
      blast \
      minimap2 \
      mummer4 \
      kma \
      mmseqs2 \
      prodigal \
      samtools \
    && micromamba clean --all --yes

# Cache directory lives inside the conda prefix by default
# ($CONDA_PREFIX/share/gmlst), so it stays isolated per container.
# Mount a volume at /data for input/output.
RUN mkdir -p /data
WORKDIR /data

ENTRYPOINT ["gmlst"]
CMD ["--help"]
