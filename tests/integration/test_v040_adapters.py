from __future__ import annotations

import gzip
import io
import tarfile
import zipfile
from pathlib import Path

import pandas as pd

from artifactor.datasets.adapters import prepare_cptac_ccrcc, prepare_seqc2


def _add_tar_bytes(bundle: tarfile.TarFile, name: str, payload: bytes) -> None:
    info = tarfile.TarInfo(name)
    info.size = len(payload)
    info.mtime = 0
    bundle.addfile(info, io.BytesIO(payload))


def test_seqc_adapter_never_turns_absence_into_negative(tmp_path: Path) -> None:
    source, output = tmp_path / "source", tmp_path / "output"
    source.mkdir()
    output.mkdir()
    vcf = b"##fileformat=VCFv4.2\n#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tS\nchr1\t10\t.\tA\tT\t.\tPASS\t.\tGT:DP:RD:AD\t0/1:20:15:5\n"
    with tarfile.open(source / "IGT1.tar.gz", "w:gz") as bundle:
        _add_tar_bytes(bundle, "IGT1/SampleA_IGT1_ST01_100ng_LIB1.vcf.gz", gzip.compress(vcf, mtime=0))
    with gzip.open(source / "KnownPositives_hg19.vcf.gz", "wt") as stream:
        stream.write("#header\nchr1\t10\t.\tA\tT\t.\tPASS\tVAF=0.25;TYPE=SNV;CAT=truth\n")
    with gzip.open(source / "KnownNegatives_hg19.bed.gz", "wt") as stream:
        stream.write("chr1\t19\t20\n")
    with zipfile.ZipFile(source / "BED.zip", "w") as bundle:
        bundle.writestr("IGT_hg19.bed", "chr1\t0\t100\n")
    _, warnings = prepare_seqc2(source, output)
    calls = pd.read_parquet(output / "variant_calls.parquet")
    counts = pd.read_parquet(output / "variant_counts.parquet")
    assert set(calls.call_state) == {"called_positive"}
    assert counts.iloc[0].alternate_count == 5
    assert any("unknown" in item for item in warnings)


def test_cptac_adapter_preserves_upstream_correction_warning(tmp_path: Path) -> None:
    source, output = tmp_path / "source", tmp_path / "output"
    source.mkdir()
    output.mkdir()
    protein = b'"Index"\t"NumberPSM"\t"Proteins"\t"ReferenceIntensity"\t"CPT0010000001"\n"g"\t2\t"P1"\t1\t2\n'
    with tarfile.open(source / "Supplementary_Data_Proteome_TMT.tar.gz", "w:gz") as bundle:
        _add_tar_bytes(bundle, "Supplementary_Data_Proteome_TMT/m.tsv", protein)
    with tarfile.open(source / "CPTAC_CCRCC_Transcriptome_rpkm.tar.gz", "w:gz") as bundle:
        _add_tar_bytes(bundle, "CPTAC_CCRCC_Transcriptome_rpkm/RNA_rpkm_tumor_normal.tsv", b"geneID\trna1\nENSG1.1\t3\n")
        _add_tar_bytes(bundle, "CPTAC_CCRCC_Transcriptome_rpkm/RNA_clinical.csv", b"C3L-1,Primary Tumor,rna1\n")
    mapping = pd.DataFrame({"PCC": ["JHU"], "Folder Name": ["01_Proteome_X"], "TMT10-127N Participant ID": ["C3L-1"], "TMT10-127N Specimen Label": ["CPT0010000001"], "Instrument": ["MS"], "Operator": ["op"]})
    with pd.ExcelWriter(source / "S044_TMT10_Label_to_Sample_Mapping_File_CCRCC_r2_Jan2019.xlsx") as writer:
        mapping.to_excel(writer, sheet_name="TMT10_mapping_File", index=False)
    clinical = pd.DataFrame({"case_id": ["C3L-1"], "specimen_id": ["C3L-1-01"], "tissue_type": ["tumor"]})
    with pd.ExcelWriter(source / "S050_S044_CPTAC_ccRCC_Discovery_Cohort_Clinical_Data_r4_Sept2019.xlsx") as writer:
        clinical.to_excel(writer, sheet_name="Specimen_Attributes", index=False)
    _, warnings = prepare_cptac_ccrcc(source, output)
    assert (output / "rna_expression.parquet").exists()
    assert (output / "technical_metadata.parquet").exists()
    assert any("ComBat" in item for item in warnings)
