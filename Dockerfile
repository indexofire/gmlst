FROM mambaorg/micromamba:1.5-jammy

USER root

RUN micromamba install -y -n base -c bioconda -c conda-forge \
      python=3.12 \
      blast \
      minimap2 \
      mummer4 \
      kma \
      mmseqs2 \
      prodigal \
      samtools \
      pip \
    && micromamba clean --all --yes

RUN micromamba run -n base pip install --no-cache-dir gmlst \
    && ln -s /opt/conda/bin/gmlst /usr/local/bin/gmlst

RUN mkdir -p /data && chown -R $MAMBA_USER:$MAMBA_USER /data
WORKDIR /data

USER $MAMBA_USER

ENTRYPOINT ["gmlst"]
CMD ["--help"]
