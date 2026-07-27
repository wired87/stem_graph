from __future__ import annotations

import struct
from pathlib import Path


def explore_egt_header(
    file_path: str,
    header_size: int = 4096,
) -> dict:
    """
    Explore the binary header of an Illumina .egt file.

    The function performs no assumptions about the EGT format.
    Instead it extracts every useful representation of the header
    for reverse engineering.

    Returns
    -------
    dict
    """

    path = Path(file_path)

    with path.open("rb") as f:
        header = f.read(header_size)

    result = {
        "file_size": path.stat().st_size,
        "header_size": len(header),

        "ascii_strings": [],

        "u8": [],
        "u16": [],
        "u32": [],
        "u64": [],

        "i16": [],
        "i32": [],
        "i64": [],

        "float32": [],
        "float64": [],

        "possible_offsets": [],
        "possible_counts": [],
    }

    ############################################################
    # raw bytes
    ############################################################

    result["u8"] = list(header)

    ############################################################
    # uint16 / int16
    ############################################################

    for off in range(0, len(header) - 1, 2):

        result["u16"].append(
            {
                "offset": off,
                "value": struct.unpack_from("<H", header, off)[0],
            }
        )

        result["i16"].append(
            {
                "offset": off,
                "value": struct.unpack_from("<h", header, off)[0],
            }
        )

    ############################################################
    # uint32 / int32 / float32
    ############################################################

    for off in range(0, len(header) - 3, 4):

        u32 = struct.unpack_from("<I", header, off)[0]
        i32 = struct.unpack_from("<i", header, off)[0]
        f32 = struct.unpack_from("<f", header, off)[0]

        result["u32"].append(
            {
                "offset": off,
                "value": u32,
            }
        )

        result["i32"].append(
            {
                "offset": off,
                "value": i32,
            }
        )

        result["float32"].append(
            {
                "offset": off,
                "value": f32,
            }
        )

        ########################################################
        # heuristics
        ########################################################

        if 0 < u32 < path.stat().st_size:
            result["possible_offsets"].append(
                {
                    "offset": off,
                    "value": u32,
                }
            )

        if 100 <= u32 <= 10000000:
            result["possible_counts"].append(
                {
                    "offset": off,
                    "value": u32,
                }
            )

    ############################################################
    # uint64 / int64 / float64
    ############################################################

    for off in range(0, len(header) - 7, 8):

        result["u64"].append(
            {
                "offset": off,
                "value": struct.unpack_from("<Q", header, off)[0],
            }
        )

        result["i64"].append(
            {
                "offset": off,
                "value": struct.unpack_from("<q", header, off)[0],
            }
        )

        result["float64"].append(
            {
                "offset": off,
                "value": struct.unpack_from("<d", header, off)[0],
            }
        )

    ############################################################
    # printable strings
    ############################################################

    start = None

    for i, b in enumerate(header):

        printable = 32 <= b <= 126

        if printable:

            if start is None:
                start = i

        else:

            if start is not None:

                if i - start >= 4:

                    result["ascii_strings"].append(
                        {
                            "offset": start,
                            "length": i - start,
                            "value": header[start:i].decode("ascii"),
                        }
                    )

                start = None

    ############################################################
    # hex dump
    ############################################################

    result["hex"] = header.hex()

    return result