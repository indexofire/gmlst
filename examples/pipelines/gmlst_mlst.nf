// Minimal Nextflow wrapper: batch MLST typing with gmlst.
//
// Usage:
//   nextflow run gmlst_mlst.nf --samples "assemblies/*.fna" --scheme saureus_1 \
//       [--container indexofire/gmlst:latest] [--args "--minscore 50"]
//
// Requires Nextflow >= 21.04. With a container engine configured
// (-profile docker / -profile singularity) the gmlst image ships all
// alignment backends, so no local conda setup is needed.

nextflow.enable.dsl = 2

params.samples = "assemblies/*.fna"
params.scheme = "saureus_1"
params.args = ""
params.container = "indexofire/gmlst:latest"
params.outdir = "results"

process gmlst_mlst {
    tag "${meta.id}"
    container "${params.container}"

    input:
    tuple val(meta), path(fasta)
    val scheme
    val cli_args

    output:
    tuple val(meta), path("${meta.id}.tsv"), emit: tsv
    tuple val(meta), path("${meta.id}.json"), emit: json
    path "versions.yml", emit: versions

    script:
    """
    gmlst typing mlst \
        -s ${scheme} \
        --format tsv \
        --output ${meta.id}.tsv \
        ${cli_args} \
        ${fasta}

    gmlst typing mlst \
        -s ${scheme} \
        --format json \
        --output ${meta.id}.json \
        ${cli_args} \
        ${fasta}

    cat <<-END_VERSIONS > versions.yml
    "\${task.process}":
        gmlst: \$(gmlst --version | awk '{print \$NF}')
    END_VERSIONS
    """
}

workflow {
    samples = channel
        .fromPath(params.samples, checkIfExists: true)
        .map { fasta -> tuple([id: fasta.simpleName], fasta) }

    gmlst_mlst(samples, params.scheme, params.args)

    gmlst_mlst.out.tsv.toList().view()
}
