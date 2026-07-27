from __future__ import annotations

import struct
from pathlib import Path


def extract_idat_measurements(file_path: str) -> dict[int, dict]:
    """
    Extract all measurements required for genotype inference from a
    single Illumina IDAT file.

    Since an IDAT contains only one fluorescence channel, the missing
    channel values are initialized as None. After loading both the
    Green and Red IDATs, merge the dictionaries by Address ID.

    Returns
    -------
    dict[int, dict]

        {
            31730401: {
                "green_intensity": ...,
                "red_intensity": ...,
                "green_stddev": ...,
                "red_stddev": ...,
                "green_bead_count": ...,
                "red_bead_count": ...,
            },
            ...
        }
    """

    channel = Path(file_path).stem.upper()

    if "GRN" in channel:
        is_green = True
    elif "RED" in channel:
        is_green = False
    else:
        raise ValueError(
            "Cannot determine channel from filename "
            "(expected *_Grn.idat or *_Red.idat)."
        )

    with open(file_path, "rb") as f:

        if f.read(4) != b"IDAT":
            raise ValueError("Not a valid IDAT file.")

        # Version
        f.read(8)

        num_fields = struct.unpack("<I", f.read(4))[0]

        fields = {}

        for _ in range(num_fields):
            field_id = struct.unpack("<H", f.read(2))[0]
            field_offset = struct.unpack("<Q", f.read(8))[0]
            fields[field_id] = field_offset

        ############################################################
        # Number of loci
        ############################################################

        f.seek(fields[102])
        num_loci = struct.unpack("<I", f.read(4))[0]

        ############################################################
        # Address IDs
        ############################################################

        f.seek(fields[104])
        address_ids = [
            struct.unpack("<I", f.read(4))[0]
            for _ in range(num_loci)
        ]

        ############################################################
        # Mean intensity
        ############################################################

        if 107 in fields:
            f.seek(fields[107])
            intensities = [
                struct.unpack("<H", f.read(2))[0]
                for _ in range(num_loci)
            ]
        else:
            intensities = [0] * num_loci

        ############################################################
        # StdDev
        ############################################################

        if 108 in fields:
            f.seek(fields[108])
            stddevs = [
                struct.unpack("<H", f.read(2))[0]
                for _ in range(num_loci)
            ]
        else:
            stddevs = [0] * num_loci

        ############################################################
        # Bead Count
        ############################################################

        if 109 in fields:
            f.seek(fields[109])
            bead_counts = [
                struct.unpack("<B", f.read(1))[0]
                for _ in range(num_loci)
            ]
        else:
            bead_counts = [0] * num_loci

    ############################################################
    # Build output
    ############################################################

    result: dict[int, dict] = {}

    for address_id, intensity, stddev, bead_count in zip(
        address_ids,
        intensities,
        stddevs,
        bead_counts,
    ):

        if is_green:
            result[address_id] = {
                "green_intensity": intensity,

                "green_stddev": stddev,

                "green_bead_count": bead_count,

            }
        else:
            result[address_id] = {

                "red_intensity": intensity,

                "red_stddev": stddev,
                "red_bead_count": bead_count,
            }

    return result