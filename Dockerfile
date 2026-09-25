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

# The retry loop tolerates the PyPI index propagation lag when the image
# build races the release's publish job; "${GMLST_VERSION#v}" strips the
# tag prefix so pip sees a bare version.
RUN set -eux; \
    for i in 1 2 3 4 5 6 7 8 9 10; do \
        if [ -n "$GMLST_VERSION" ]; then \
            micromamba run -n base pip install --no-cache-dir "gmlst==${GMLST_VERSION#v}" && break; \
        else \
            micromamba run -n base pip install --no-cache-dir gmlst && break; \
        fi; \
        sleep 30; \
    done \
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
