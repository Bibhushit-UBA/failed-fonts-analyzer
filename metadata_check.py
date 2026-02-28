from config import SESSION, DOWNLOAD_HEADERS, METADATA_API, METADATA_BATCH_SIZE


def check_metadata_availability(md5_to_fontnames: dict[str, list[str]]) -> set[str]:
    """
    Checks metadata availability for all unique MD5s in batches.

    Args:
        md5_to_fontnames: Mapping of MD5 -> list of font file names sharing that MD5.

    Returns:
        Set of font file names that have metadata available.
    """
    unique_md5s = list(md5_to_fontnames.keys())
    found_font_names: set[str] = set()
    batches = [
        unique_md5s[i:i + METADATA_BATCH_SIZE]
        for i in range(0, len(unique_md5s), METADATA_BATCH_SIZE)
    ]

    for batch in batches:
        url = METADATA_API.format(md5s=",".join(batch))
        try:
            response = SESSION.get(url, timeout=15, headers=DOWNLOAD_HEADERS, verify=False)
            data = response.json()
            if isinstance(data, list):
                for item in data:
                    md5 = item.get("md5") or item.get("file", {}).get("md5")
                    if md5 and md5 in md5_to_fontnames:
                        found_font_names.update(md5_to_fontnames[md5])
        except Exception as e:
            print(f"  Warning: Metadata API failed for batch: {e}")

    return found_font_names
