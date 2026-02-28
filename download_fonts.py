import base64
import os

from tqdm import tqdm

from config import SESSION, DOWNLOAD_HEADERS


def _format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 ** 2):.1f} MB"


def _download_single_font(web_path: str, font_file_name: str, output_dir: str) -> str:
    """
    Downloads a single font file from the given web path.

    Returns:
        Formatted file size string on success, or 'N/A (<reason>)' on failure.
    """
    if not web_path or not isinstance(web_path, str) or not web_path.strip():
        return "N/A"

    wp = web_path.strip()
    safe_name = (
        "".join(c if c.isalnum() or c in "._-" else "_" for c in font_file_name)
        or "unknown_font"
    )
    output_path = os.path.join(output_dir, safe_name)

    try:
        if wp.startswith("data:") and "base64" in wp:
            _, encoded = wp.split(",", 1)
            file_data = base64.b64decode(encoded)
            with open(output_path, "wb") as f:
                f.write(file_data)
            return _format_size(len(file_data))

        if "typekit.net" in wp or "fonts.googleapis.com" in wp:
            return "N/A (hosted service)"

        if wp.startswith("http://") or wp.startswith("https://"):
            response = SESSION.get(wp, timeout=60, headers=DOWNLOAD_HEADERS, verify=False, stream=True)
            if response.status_code == 200:
                with open(output_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                return _format_size(os.path.getsize(output_path))
            return f"N/A (HTTP {response.status_code})"

    except Exception as e:
        return f"N/A ({type(e).__name__})"

    return "N/A"


def download_all_fonts(unique_df, output_dir: str) -> list[str]:
    """
    Downloads font files for all rows in unique_df using their Web Path.

    Args:
        unique_df: DataFrame with 'Web Path' and 'Font File Name' columns.
        output_dir: Directory to save downloaded font files.

    Returns:
        List of file size strings (one per row), in the same row order.
    """
    total_with_webpath = (
        unique_df["Web Path"].dropna().astype(str).str.strip().ne("").sum()
    )
    downloaded_count = 0
    file_sizes = []

    with tqdm(
        unique_df.iterrows(),
        total=len(unique_df),
        desc=f"Downloading fonts [0/{total_with_webpath} files]",
        bar_format="{desc}  {elapsed}",
    ) as pbar:
        for _, row in pbar:
            web_path = str(row.get("Web Path", "") or "")
            font_file_name = str(row.get("Font File Name", "") or "unknown_font")

            size = _download_single_font(web_path, font_file_name, output_dir)
            file_sizes.append(size)

            if not size.startswith("N/A"):
                downloaded_count += 1

            pbar.set_description(
                f"Downloading fonts [{downloaded_count}/{total_with_webpath} files]"
                f" → {font_file_name[:35]}"
            )

    return file_sizes
