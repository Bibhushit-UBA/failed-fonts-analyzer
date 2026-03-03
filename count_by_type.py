import os
from collections import Counter

import pandas as pd


def get_file_type_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    Counts font files by extension from the 'Font File Name' column.

    Returns a DataFrame with columns: File Extension, Count, File Names.
    Files with no extension are grouped under '(no extension)'.
    """
    counts: Counter = Counter()
    ext_to_names: dict[str, list[str]] = {}

    for font_name in df["Font File Name"].dropna().astype(str):
        file_ext = os.path.splitext(font_name)[1].lower() or "(no extension)"
        counts[file_ext] += 1
        ext_to_names.setdefault(file_ext, []).append(font_name)

    rows = [
        {
            "File Extension": ext,
            "Count": count,
            "File Names": ", ".join(ext_to_names[ext]),
        }
        for ext, count in sorted(counts.items(), key=lambda x: -x[1])
    ]

    return pd.DataFrame(rows)
