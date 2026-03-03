import os
import shutil
import sys

import pandas as pd

from config import SUPPORTED_EXTENSIONS
from count_by_type import get_file_type_summary
from download_fonts import download_all_fonts
from metadata_check import check_metadata_availability
from status_check import check_asset_status



def read_input_file(input_path: str) -> pd.DataFrame:
    ext = os.path.splitext(input_path)[1].lower()
    if ext == ".csv":
        return pd.read_csv(input_path)
    elif ext in (".xlsx", ".xls"):
        return pd.read_excel(input_path, engine="openpyxl")
    else:
        print(f"Error: Unsupported file type '{ext}'. Use .csv, .xlsx, or .xls.")
        sys.exit(1)


def process_file(input_path: str, download_fonts: bool = True) -> None:
    filename = os.path.basename(input_path)
    name_without_ext = os.path.splitext(filename)[0]

    df = read_input_file(input_path)

    required_columns = ["MD5", "Font File Name", "Web Path", "ITW Status"]
    missing = [col for col in required_columns if col not in df.columns]
    if missing:
        print(f"  Error: Missing columns in '{filename}': {missing}. Skipping.")
        return

    unique_df = df.drop_duplicates(subset=["Font File Name"])[required_columns].copy()

    # ── Build md5 → font name mapping ─────────────────────────────────────────
    md5_to_fontnames: dict[str, list[str]] = {}
    for _, row in unique_df[["MD5", "Font File Name"]].dropna().iterrows():
        md5_to_fontnames.setdefault(str(row["MD5"]), []).append(str(row["Font File Name"]))

    # ── Metadata availability ──────────────────────────────────────────────────
    print(f"  Metadata Availability Check for {len(md5_to_fontnames)} unique MD5(s)...")
    found_font_names = check_metadata_availability(md5_to_fontnames)
    unique_df["Metadata Availability"] = unique_df["Font File Name"].apply(
        lambda x: "Yes" if str(x) in found_font_names else "No"
    )

    # ── Asset status check ─────────────────────────────────────────────────────
    print(f"  Curl Status Check for {len(md5_to_fontnames)} unique MD5(s)...")
    md5_to_status = check_asset_status(unique_df["MD5"].astype(str).tolist())
    unique_df["Status Code"] = unique_df["MD5"].astype(str).map(
        lambda x: md5_to_status[x][0] if x in md5_to_status else ""
    )
    unique_df["Curl Status Check"] = unique_df["MD5"].astype(str).map(
        lambda x: md5_to_status[x][1] if x in md5_to_status else ""
    )

    # ── Output folders ─────────────────────────────────────────────────────────
    base_dir = os.path.dirname(os.path.abspath(input_path))
    output_folder = os.path.join(base_dir, f"UNIQUE {name_without_ext}")
    os.makedirs(output_folder, exist_ok=True)

    # ── Font downloads ─────────────────────────────────────────────────────────
    if download_fonts:
        downloads_folder = os.path.join(output_folder, "Downloaded Files")
        os.makedirs(downloads_folder, exist_ok=True)
        file_sizes = download_all_fonts(unique_df, downloads_folder)
        unique_df["FILE SIZE"] = file_sizes
        downloaded = sum(1 for s in file_sizes if not s.startswith("N/A"))
        download_summary = f"{downloaded}/{len(unique_df)} fonts downloaded."
    else:
        download_summary = "Font download skipped."

    # ── Save output ────────────────────────────────────────────────────────────
    summary_df = get_file_type_summary(unique_df)

    shutil.copy2(input_path, os.path.join(output_folder, filename))
    output_xlsx = os.path.join(output_folder, f"Unique {name_without_ext}.xlsx")

    with pd.ExcelWriter(output_xlsx, engine="openpyxl") as writer:
        unique_df.to_excel(writer, sheet_name="Unique Fonts", index=False)
        summary_df.to_excel(writer, sheet_name="File Type Summary", index=False)

    print(f"  Done. {len(unique_df)} unique records written. {download_summary}")


def process_input(input_path: str, download_fonts: bool = True) -> None:
    if os.path.isdir(input_path):
        files = [
            os.path.join(input_path, f)
            for f in os.listdir(input_path)
            if os.path.splitext(f)[1].lower() in SUPPORTED_EXTENSIONS
        ]
        if not files:
            print(f"No supported files (.csv, .xlsx, .xls) found in '{input_path}'.")
            sys.exit(1)
        print(f"Found {len(files)} file(s) in '{input_path}':")
        for f in sorted(files):
            print(f"  Processing: {os.path.basename(f)}")
            process_file(f, download_fonts)

    elif os.path.isfile(input_path):
        print(f"Processing: {os.path.basename(input_path)}")
        process_file(input_path, download_fonts)

    else:
        print(f"Error: '{input_path}' is not a valid file or folder.")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) >= 2:
        target = sys.argv[1]
    else:
        target = input("Enter file or folder path: ").strip()

    if not target:
        print("Error: No path provided.")
        sys.exit(1)

    should_download = input("Download font files? (y/n): ").strip().lower() == "y"

    process_input(target, download_fonts=should_download)
