from __future__ import annotations

import csv
import gzip
import io
import re
import tarfile
import zipfile
from pathlib import Path

import pandas as pd

from .contracts import TransformationRecord

SEQC_NAME = re.compile(
    r"Sample(?P<sample>AIS|AC0?5|A|B|C)_(?P<panel>[^_]+)_(?P<lab>[^_]+)_"
    r"(?P<mass>[^_]+)_LIB(?P<replicate>\d+)\.vcf\.gz$"
)


def _vcf_rows(stream: io.TextIOBase) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    calls: list[dict[str, object]] = []
    counts: list[dict[str, object]] = []
    for line in stream:
        if line.startswith("#"):
            continue
        fields = line.rstrip().split("\t")
        if len(fields) < 8:
            continue
        row: dict[str, object] = {
            "chromosome": fields[0],
            "position": int(fields[1]),
            "reference": fields[3],
            "alternate": fields[4],
            "filter": fields[6],
            "call_state": "called_positive",
        }
        calls.append(row)
        if len(fields) >= 10:
            values = dict(zip(fields[8].split(":"), fields[9].split(":"), strict=False))
            try:
                depth = int(values["DP"])
                reference_count = int(values["RD"])
                alternate_count = int(values["AD"])
            except (KeyError, TypeError, ValueError):
                continue
            counts.append(
                {
                    **{key: row[key] for key in ("chromosome", "position", "reference", "alternate")},
                    "depth": depth,
                    "reference_count": reference_count,
                    "alternate_count": alternate_count,
                    "vaf": alternate_count / depth if depth else None,
                }
            )
    return calls, counts


def _read_bed(stream: io.TextIOBase, source: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for fields in csv.reader(stream, delimiter="\t"):
        if len(fields) < 3 or fields[0].startswith(("#", "track", "browser")):
            continue
        try:
            start, end = int(fields[1]), int(fields[2])
        except ValueError:
            continue
        rows.append(
            {
                "chromosome": fields[0],
                "start_zero_based": start,
                "end_zero_based_exclusive": end,
                "source": source,
            }
        )
    return rows


def prepare_seqc2(source: Path, destination: Path) -> tuple[list[TransformationRecord], list[str]]:
    manifests: list[dict[str, object]] = []
    calls: list[dict[str, object]] = []
    counts: list[dict[str, object]] = []
    regions: list[dict[str, object]] = []
    warnings = [
        "VCF absence is encoded as unknown; site-level callability cannot be established from submitted positive-only VCFs."
    ]
    archives = sorted(source.glob("*1.tar.gz"))
    for archive in archives:
        panel = archive.name.removesuffix("1.tar.gz")
        with tarfile.open(archive, "r:gz") as bundle:
            for member in sorted(bundle.getmembers(), key=lambda item: item.name):
                if not member.isfile() or not member.name.endswith(".vcf.gz"):
                    continue
                match = SEQC_NAME.search(Path(member.name).name)
                if not match:
                    warnings.append(f"Skipped unrecognized VCF name: {member.name}")
                    continue
                metadata = match.groupdict()
                reference_sample = "AC5" if metadata["sample"] == "AC05" else metadata["sample"]
                sample_id = Path(member.name).name.removesuffix(".vcf.gz")
                manifests.append(
                    {
                        "sample_id": sample_id,
                        "reference_sample": reference_sample,
                        "panel": metadata["panel"],
                        "laboratory": metadata["lab"],
                        "library_replicate": int(metadata["replicate"]),
                        "sequencing_platform": None,
                        "input_mass": metadata["mass"],
                        "umi_status": None,
                        "reference_build": "GRCh37",
                        "pipeline_identity": "submitted_callset",
                        "included_primary": reference_sample != "AIS",
                        "exclusion_reason": None if reference_sample != "AIS" else "AIS not in primary four-sample comparison",
                    }
                )
                raw = bundle.extractfile(member)
                if raw is None:
                    continue
                with gzip.open(raw, "rt", encoding="utf-8", errors="replace") as stream:
                    member_calls, member_counts = _vcf_rows(stream)
                for row in member_calls:
                    row.update(sample_id=sample_id, panel=panel)
                for row in member_counts:
                    row.update(sample_id=sample_id, panel=panel)
                calls.extend(member_calls)
                counts.extend(member_counts)

    bed_zip = source / "BED.zip"
    if bed_zip.exists():
        with zipfile.ZipFile(bed_zip) as bundle:
            for name in sorted(bundle.namelist()):
                if name.lower().endswith((".bed", ".txt")) and not name.endswith("/"):
                    text = io.TextIOWrapper(bundle.open(name), encoding="utf-8", errors="replace")
                    panel_rows = _read_bed(text, name)
                    for row in panel_rows:
                        row["panel"] = Path(name).stem.split("_")[0]
                        row["reference_build"] = "GRCh38" if "hg38" in name.lower() else "GRCh37"
                    regions.extend(panel_rows)

    truth: list[dict[str, object]] = []
    positive_path = source / "KnownPositives_hg19.vcf.gz"
    if positive_path.exists():
        with gzip.open(positive_path, "rt", encoding="utf-8", errors="replace") as stream:
            for line in stream:
                if line.startswith("#"):
                    continue
                fields = line.rstrip().split("\t")
                if len(fields) >= 8:
                    info = dict(
                        item.split("=", 1) for item in fields[7].split(";") if "=" in item
                    )
                    truth.append(
                        {
                            "chromosome": fields[0], "position": int(fields[1]),
                            "reference": fields[3], "alternate": fields[4],
                            "truth_class": "positive", "expected_vaf": info.get("VAF"),
                            "variant_type": info.get("TYPE"), "category": info.get("CAT"),
                            "reference_build": "GRCh37",
                        }
                    )
    negative_path = source / "KnownNegatives_hg19.bed.gz"
    if negative_path.exists():
        with gzip.open(negative_path, "rt", encoding="utf-8", errors="replace") as stream:
            for row in _read_bed(stream, negative_path.name):
                truth.append({**row, "truth_class": "negative", "reference_build": "GRCh37"})

    frames = {
        "manifest.parquet": pd.DataFrame(manifests),
        "variant_calls.parquet": pd.DataFrame(calls),
        "variant_counts.parquet": pd.DataFrame(counts),
        "reporting_regions.parquet": pd.DataFrame(regions),
        "variant_annotations.parquet": pd.DataFrame(columns=["variant_id", "annotation"]),
        "truth_positions.parquet": pd.DataFrame(truth),
        "panel_metadata.parquet": pd.DataFrame(
            [{"panel": name.removesuffix("1.tar.gz"), "callset_archive": name} for name in sorted(item.name for item in archives)]
        ),
        "laboratory_metadata.parquet": pd.DataFrame(manifests)[["laboratory", "panel"]].drop_duplicates() if manifests else pd.DataFrame(columns=["laboratory", "panel"]),
        "replicate_map.parquet": pd.DataFrame(manifests)[["sample_id", "reference_sample", "panel", "laboratory", "library_replicate"]] if manifests else pd.DataFrame(),
    }
    for name, frame in frames.items():
        frame.to_parquet(destination / name, index=False)
    ledger = [
        TransformationRecord(step_id="parse_submitted_calls", input_artifacts=[item.name for item in archives], operation="parse_vcf_without_call_state_inference", output_artifacts=["manifest.parquet", "variant_calls.parquet", "variant_counts.parquet"], rows_in=len(calls), rows_out=len(calls)),
        TransformationRecord(step_id="separate_truth_and_regions", input_artifacts=["KnownPositives_hg19.vcf.gz", "KnownNegatives_hg19.bed.gz", "BED.zip"], operation="parse_reference_truth_and_reporting_intervals", output_artifacts=["truth_positions.parquet", "reporting_regions.parquet"], rows_in=len(truth) + len(regions), rows_out=len(truth) + len(regions)),
    ]
    return ledger, warnings


def prepare_cptac_ccrcc(source: Path, destination: Path) -> tuple[list[TransformationRecord], list[str]]:
    protein_archive = source / "Supplementary_Data_Proteome_TMT.tar.gz"
    rna_archive = source / "CPTAC_CCRCC_Transcriptome_rpkm.tar.gz"
    mapping_path = source / "S044_TMT10_Label_to_Sample_Mapping_File_CCRCC_r2_Jan2019.xlsx"
    clinical_path = source / "S050_S044_CPTAC_ccRCC_Discovery_Cohort_Clinical_Data_r4_Sept2019.xlsx"

    with tarfile.open(protein_archive, "r:gz") as bundle:
        member = next(item for item in bundle.getmembers() if item.name.endswith(".tsv"))
        protein_stream = bundle.extractfile(member)
        if protein_stream is None:
            raise ValueError("protein matrix member could not be read")
        protein = pd.read_csv(protein_stream, sep="\t", quotechar='"')
    with tarfile.open(rna_archive, "r:gz") as bundle:
        matrix_member = next(item for item in bundle.getmembers() if item.name.endswith("RNA_rpkm_tumor_normal.tsv"))
        clinical_member = next(item for item in bundle.getmembers() if item.name.endswith("RNA_clinical.csv"))
        matrix_stream = bundle.extractfile(matrix_member)
        clinical_stream = bundle.extractfile(clinical_member)
        if matrix_stream is None or clinical_stream is None:
            raise ValueError("RNA archive members could not be read")
        rna = pd.read_csv(matrix_stream, sep="\t")
        rna_samples = pd.read_csv(clinical_stream, header=None, names=["subject_id", "tissue_type", "rna_sample_id"])

    mapping = pd.read_excel(mapping_path, sheet_name="TMT10_mapping_File")
    mapping = mapping[mapping["Folder Name"].astype(str).str.contains("_Proteome_")]
    protein_map: list[dict[str, object]] = []
    for _, row in mapping.iterrows():
        for column in mapping.columns:
            if not str(column).endswith(" Participant ID"):
                continue
            channel = str(column).removesuffix(" Participant ID")
            specimen_column = f"{channel} Specimen Label"
            participant, specimen = row.get(column), row.get(specimen_column)
            if pd.isna(participant) or pd.isna(specimen) or str(participant) == "pooled sample":
                continue
            tissue = "normal" if channel.endswith("N") else "tumor" if channel.endswith("C") else "unknown"
            protein_map.append({"protein_sample_id": str(specimen), "subject_id": str(participant), "tissue_type": tissue, "tmt_plex": row["Folder Name"], "tmt_channel": channel, "center": row["PCC"], "instrument": row["Instrument"], "operator": row["Operator"]})
    technical = pd.DataFrame(protein_map).drop_duplicates("protein_sample_id")
    manifest_rna = rna_samples.assign(modality="rna", sample_id=rna_samples["rna_sample_id"], aliquot_id=None, inclusion_reason="source publication matrix")
    manifest_protein = technical.assign(modality="protein", sample_id=technical["protein_sample_id"], aliquot_id=technical["protein_sample_id"], inclusion_reason="source publication matrix")
    manifest = pd.concat(
        [manifest_rna[["sample_id", "subject_id", "tissue_type", "modality", "aliquot_id", "inclusion_reason"]], manifest_protein[["sample_id", "subject_id", "tissue_type", "modality", "aliquot_id", "inclusion_reason"]]],
        ignore_index=True,
    ).sort_values(["subject_id", "modality", "sample_id"])

    clinical = pd.read_excel(clinical_path, sheet_name="Specimen_Attributes")
    feature_map = pd.DataFrame(
        {"original_identifier": rna["geneID"].astype(str), "mapped_identifier": rna["geneID"].astype(str).str.split(".", regex=False).str[0], "mapping_status": "rna_identifier_only", "mapping_source_version": "source Ensembl identifiers; no external mapping bundled", "aggregation_rule": "none"}
    ).drop_duplicates()
    protein_features = pd.DataFrame({"original_identifier": protein["Index"].astype(str), "mapped_identifier": protein["Proteins"].astype(str), "mapping_status": "source_protein_annotation", "mapping_source_version": "PDC000127 publication supplement", "aggregation_rule": "none"})
    feature_map = pd.concat([feature_map, protein_features], ignore_index=True)

    protein.to_parquet(destination / "protein_abundance.parquet", index=False)
    rna.to_parquet(destination / "rna_expression.parquet", index=False)
    manifest.to_parquet(destination / "manifest.parquet", index=False)
    feature_map.to_parquet(destination / "feature_map.parquet", index=False)
    pd.DataFrame(columns=["feature_id", "annotation", "source"]).to_parquet(destination / "feature_annotations.parquet", index=False)
    clinical.to_parquet(destination / "biospecimen_metadata.parquet", index=False)
    technical.sort_values("protein_sample_id").to_parquet(destination / "technical_metadata.parquet", index=False)
    ledger = [
        TransformationRecord(step_id="extract_publication_matrices", input_artifacts=[protein_archive.name, rna_archive.name], operation="lossless_archive_parse", output_artifacts=["protein_abundance.parquet", "rna_expression.parquet"], rows_in=len(protein) + len(rna), rows_out=len(protein) + len(rna)),
        TransformationRecord(step_id="map_public_identifiers", input_artifacts=[mapping_path.name, clinical_path.name], operation="documented_identifier_join_without_aggregation", output_artifacts=["manifest.parquet", "technical_metadata.parquet", "biospecimen_metadata.parquet", "feature_map.parquet"], rows_in=len(mapping) + len(clinical), rows_out=len(manifest) + len(technical) + len(clinical)),
    ]
    warnings = [
        "Protein values are publication-processed, imputed, and already ComBat-adjusted upstream; Artifactor correction is not eligible on this matrix.",
        "No frozen external one-to-one RNA-protein gene mapping is bundled; primary cross-modal feature concordance is not evaluable.",
        "TMT channel roles not explicitly marked N/C are retained with tissue_type=unknown.",
    ]
    return ledger, warnings
