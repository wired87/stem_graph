"""Input collection, parsing, validation and IDAT pairing."""

from __future__ import annotations

import gzip
import io
import shutil
import tempfile
from pathlib import Path

from BeadArrayFiles.module import BeadPoolManifest, ClusterFile

from file.write_files_tmp_store import save_files
from product.genome_from_array import ARRAY_GENOME_MAPPING
from product.stem_file.arr_name import get_all_bpm_metadata
from product.stem_file.csv_meta import (
    extract_manifest_assay_data,
    extract_manifest_metadata,
)
from product.stem_file.meta_egt import get_all_egt_metadata
from product.stem_file.read_idat import read_idat_metadata


SUPPORTED_SUFFIXES = {
    ".idat", ".bpm", ".egt", ".csv", ".yaml", ".tsv", ".txt"
}


def collect_files(files=None, directory=None):
    if files is not None:
        return list(files)
    if directory is None:
        raise ValueError("Either files or directory must be provided")

    result = []
    for source in sorted(Path(directory).rglob("*")):
        if not source.is_file():
            continue
        target = source
        if source.suffix.lower() == ".gz":
            target = Path(tempfile.gettempdir()) / source.stem
            with gzip.open(source, "rb") as src, open(target, "wb") as dst:
                shutil.copyfileobj(src, dst)
        if target.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        uploaded = io.BytesIO(target.read_bytes())
        uploaded.name = target.name
        result.append(uploaded)
    return result


def single_file(graph, suffix):
    suffix = suffix.lstrip(".").lower()
    matches = [
        (nid, attrs)
        for nid, attrs in graph.G.nodes(data=True)
        if attrs.get("type") == "FILE" and attrs.get("sub_type") == suffix
    ]
    if len(matches) != 1:
        raise ValueError(
            f"Expected exactly one .{suffix} file, found {len(matches)}"
        )
    return matches[0]


def _persist_file(graph, uploaded_file):
    suffix = Path(uploaded_file.name).suffix.lower()
    target_dir = (
        graph.dirs["raw_input"] if suffix == ".idat" else graph.dirs["input"]
    )
    return str(save_files([uploaded_file], target_dir)[0])


def _metadata(path):
    suffix = Path(path).suffix.lower()
    readers = {
        ".bpm": get_all_bpm_metadata,
        ".egt": get_all_egt_metadata,
        ".idat": read_idat_metadata,
        ".csv": extract_manifest_metadata,
    }
    reader = readers.get(suffix)
    return reader(path) if reader else {"file_name": Path(path).name}


def _content(path):
    suffix = Path(path).suffix.lower()
    if suffix == ".bpm":
        return BeadPoolManifest(filename=path)
    if suffix == ".egt":
        with open(path, "rb") as handle:
            return ClusterFile.read_cluster_file(handle)
    if suffix == ".csv":
        return extract_manifest_assay_data(path)
    raise ValueError(f"Unsupported reference file: {path}")


def _pair_idats(graph, idat_nodes):
    grouped = {}
    for file_id, meta in idat_nodes:
        grouped.setdefault(
            (meta.get("chip_name"), meta.get("chip_pos")), []
        ).append((file_id, meta))

    pairs = []
    for sample_key, files in grouped.items():
        channels = {
            str(meta.get("color_channel", "")).lower(): file_id
            for file_id, meta in files
        }
        green = channels.get("green") or channels.get("grn")
        red = channels.get("red")
        if len(files) != 2 or not green or not red:
            raise ValueError(f"Invalid IDAT pair {sample_key}: {channels}")
        graph.add_edge(
            green,
            red,
            attrs={
                "rel": "partner_file",
                "src_layer": "FILE",
                "trgt_layer": "FILE",
            },
        )
        pairs.append((green, red))
    return pairs


def prepare_inputs(graph, files):
    """Register input nodes, load references and return paired IDAT ids."""
    idat_nodes = []
    for uploaded_file in files:
        path = _persist_file(graph, uploaded_file)
        suffix = Path(path).suffix.lower()
        meta = _metadata(path)
        if meta is None:
            raise ValueError(f"Could not parse metadata from {path}")
        if suffix == ".idat":
            meta["genome_version"] = ARRAY_GENOME_MAPPING.get(
                meta.get("array_name"), meta.get("genome_version", "Unknown")
            )
        graph.add_node(
            {
                "id": path,
                "type": "FILE",
                "sub_type": suffix.lstrip("."),
                "meta": meta,
            }
        )
        if suffix == ".idat":
            idat_nodes.append((path, meta))

    if not idat_nodes or len(idat_nodes) % 2:
        raise ValueError(
            f"IDAT files must form Green/Red pairs; found {len(idat_nodes)}"
        )
    for suffix in ("bpm", "egt", "csv"):
        file_id, _ = single_file(graph, suffix)
        graph.update_node({"id": file_id, "content": _content(file_id)})
    return _pair_idats(graph, idat_nodes)
