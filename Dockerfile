FROM mambaorg/micromamba:1.5-jammy

USER root

# Pinned by CI on release builds (see .github/workflows/docker.yml); empty = latest.
ARG GMLST_VERSION=""

ENV PATH="/opt/conda/bin:${PATH}"

RUN micromamba install -y -n base -c bioconda -c conda-forge \
      python=3.12 \
      blast \
      minimap2 \
      mummer4 \
      kma \
      kmc \
      mmseqs2 \
      prodigal \
      samtools \
      pip \
    && micromamba clean --all --yes

RUN if [ -n "$GMLST_VERSION" ]; then \
        micromamba run -n base pip install --no-cache-dir "gmlst==${GMLST_VERSION}"; \
    else \
        micromamba run -n base pip install --no-cache-dir gmlst; \
    fi \
    && ln -s /opt/conda/bin/gmlst /usr/local/bin/gmlst

RUN gmlst --version \
    && blastn -version \
    && minimap2 --version \
    && kma -v

RUN mkdir -p /data && chown -R $MAMBA_USER:$MAMBA_USER /data
WORKDIR /data

USER $MAMBA_USER

ENTRYPOINT ["gmlst"]
CMD ["--help"]
