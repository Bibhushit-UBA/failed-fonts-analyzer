import json
import shlex
import subprocess

from config import STATUS_API, STATUS_SOURCE, STATUS_CONSUMER_ID, STATUS_COOKIE


def check_asset_status(md5_list: list[str]) -> dict[str, tuple[str, str, str]]:
    """
    Runs an asset status check for all MD5s via curl and returns results.

    Args:
        md5_list: List of MD5 strings (duplicates are handled internally).

    Returns:
        Dict mapping md5 -> (status_code, av_check_status, font_read_error).
        font_read_error is "Unable to read font" when the AV status contains
        that phrase, otherwise empty.
        Rows with no result (e.g. 404) will not appear in the dict.
    """
    unique_md5s = list(dict.fromkeys(md5_list))
    md5_to_status: dict[str, tuple[str, str, str]] = {}

    body = json.dumps({"mdFives": unique_md5s})
    curl_cmd = [
        "curl", "--silent", "--location", STATUS_API,
        "--header", "accept: application/json",
        "--header", f"source: {STATUS_SOURCE}",
        "--header", f"consumer-id: {STATUS_CONSUMER_ID}",
        "--header", "Content-Type: application/json",
        "--header", f"Cookie: {STATUS_COOKIE}",
        "--data", body,
    ]

    try:
        result = subprocess.run(curl_cmd, capture_output=True, text=True, timeout=60)
        raw = result.stdout.strip()
        print(f"  Status API response: {raw[:300]}")

        data = json.loads(raw)
        for item in data.get("result", []):
            key = item.get("key") or item.get("md5")
            if not key:
                continue
            status_code = str(item.get("statusCode", ""))
            av_check = item.get("avCheckResult")
            av_status = str(av_check.get("status", "")) if isinstance(av_check, dict) else ""
            charset = item.get("characterset")
            charset_error = str(charset.get("error", "")) if isinstance(charset, dict) else ""
            font_read_error = (
                charset_error
                if "unable to read font" in charset_error.lower()
                else ""
            )
            md5_to_status[key] = (status_code, av_status, font_read_error)

    except Exception as e:
        print(f"  Warning: Asset status check failed: {e}")

    return md5_to_status
