"""Input readers for FASTA and FASTQ samples."""

from gmlst.readers.fasta import FastaReader
from gmlst.readers.fastq import FastqReader
from gmlst.readers.sample import SampleInput, detect_sample

__all__ = ["FastaReader", "FastqReader", "SampleInput", "detect_sample"]
