import pandas as pd
import sys
import os
import shutil
import requests
import base64
import urllib3
import json
import subprocess
import shlex
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from tqdm import tqdm

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "*/*",
}

def build_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=2, status_forcelist=[429, 500, 502, 503, 504])
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.mount("http://", HTTPAdapter(max_retries=retry))
    return session

SESSION = build_session()

SUPPORTED_EXTENSIONS = (".csv", ".xlsx", ".xls")
METADATA_API = "https://fbms-itw.monotype.com/font/{md5s}/metadata"
BATCH_SIZE = 20

STATUS_API = "https://asset-itw.monotype.com/asset/status"
STATUS_SOURCE = "5386d862-844b-4b01-9533-0613ee64e307"
STATUS_CONSUMER_ID = "ITW"
# Update when Cloudflare tokens expire
STATUS_COOKIE = (
    "__cf_bm=ydfjakZqRKqv9SY0_NvReEC9NPwTwPi99SoVNPIB098-1726134827-1.0.1.1-VfZFw_bHXrLAtPza_SWJLJPAXxJwHqPZ4xWoJ2.JkYGU0uz2p4btNI6CpMiF7.TUbO4wHf8D5ub05qvatQhPag; "
    "__cf_bm=.RZq.FSS_A07QnPFDYk3D7zfkSC.qDc92T3EZgGWvo8-1771573425-1.0.1.1-Hh25p7RvIECT3UUqm4QfgMqjphRHoNpwEvU9Gaw1il2nrAI.poClUqn8d_xbRFiuHry7Qhhz91fResE9CQVS6PtdIYL5eYsXN5jr70dPqPc; "
    "_cfuvid=tn_0ehlhorKasT4XPCvoO.YZaCYOFFkOrxoOKGDpsFw-1771498554526-0.0.1.1-604800000; "
    "__cf_bm=2vPEF4Hl0ebS3_NJpDpYVKjtb0GrI27IV.Nl5BrlCII-1771574127-1.0.1.1-BR7gA3FkMUv4rGmAEXT7eoGb44FV9u4FIbHOpWeTktsrBJQHQk88sxWT78Fz7tZClMWDjfZdjrIuTHcORsrt.c2cuWlVqjrDOzf9EnAF1Sk"
)

def read_input_file(input_path: str) -> pd.DataFrame:
    ext = os.path.splitext(input_path)[1].lower()
    if ext == ".csv":
        return pd.read_csv(input_path)
    elif ext in (".xlsx", ".xls"):
        return pd.read_excel(input_path)
    else:
        print(f"Error: Unsupported file type '{ext}'. Use .csv, .xlsx, or .xls.")
        sys.exit(1)

def check_metadata_availability(md5_to_fontnames: dict[str, list[str]]) -> set[str]:
    """Returns a set of Font File Names that have metadata available."""
    unique_md5s = list(md5_to_fontnames.keys())
    found_font_names = set()

    batches = [unique_md5s[i:i + BATCH_SIZE] for i in range(0, len(unique_md5s), BATCH_SIZE)]
    for batch in batches:
        url = METADATA_API.format(md5s=",".join(batch))
        try:
            response = SESSION.get(url, timeout=15, headers=HEADERS, verify=False)
            data = response.json()
            if isinstance(data, list):
                for item in data:
                    md5 = item.get("md5") or item.get("file", {}).get("md5")
                    if md5 and md5 in md5_to_fontnames:
                        found_font_names.update(md5_to_fontnames[md5])
        except Exception as e:
            print(f"  Warning: Metadata API failed for batch: {e}")

    return found_font_names


def check_asset_status(md5_list: list[str]) -> dict[str, tuple[str, str]]:
    """Runs the status check via curl (subprocess) and returns md5 -> status dict."""
    unique_md5s = list(dict.fromkeys(md5_list))
    md5_to_status: dict[str, str] = {}

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

        data = json.loads(raw)
        # Response format: {"result": [{"key": "<md5>", "statusCode": 200, "avCheckResult": {"status": "success"}, ...}]}
        for item in data.get("result", []):
            key = item.get("key") or item.get("md5")
            if key:
                status_code = str(item.get("statusCode", ""))
                av_check = item.get("avCheckResult")
                av_status = str(av_check.get("status", "")) if isinstance(av_check, dict) else ""
                md5_to_status[key] = (status_code, av_status)
    except Exception as e:
        print(f"  Warning: Curl status check call failed: {e}")

    return md5_to_status


def format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 ** 2):.1f} MB"


def download_font(web_path: str, font_file_name: str, output_dir: str) -> str:
    """Downloads font from web_path into output_dir. Returns formatted file size or 'N/A'."""
    if not web_path or not isinstance(web_path, str) or not web_path.strip():
        return "N/A"

    wp = web_path.strip()
    safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in font_file_name) or "unknown_font"
    output_path = os.path.join(output_dir, safe_name)

    try:
        if wp.startswith("data:") and "base64" in wp:
            _, encoded = wp.split(",", 1)
            file_data = base64.b64decode(encoded)
            with open(output_path, "wb") as f:
                f.write(file_data)
            return format_size(len(file_data))

        if "typekit.net" in wp or "fonts.googleapis.com" in wp:
            return "N/A (hosted service)"

        if wp.startswith("http://") or wp.startswith("https://"):
            response = SESSION.get(wp, timeout=60, headers=HEADERS, verify=False, stream=True)
            if response.status_code == 200:
                with open(output_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                return format_size(os.path.getsize(output_path))
            return f"N/A (HTTP {response.status_code})"

    except Exception as e:
        return f"N/A ({type(e).__name__})"

    return "N/A"


def process_file(input_path: str):
    filename = os.path.basename(input_path)
    name_without_ext = os.path.splitext(filename)[0]

    df = read_input_file(input_path)

    required_columns = ["MD5", "Font File Name", "Web Path", "ITW Status"]
    missing = [col for col in required_columns if col not in df.columns]
    if missing:
        print(f"  Error: Missing columns in '{filename}': {missing}. Skipping.")
        return

    unique_df = df.drop_duplicates(subset=["Font File Name"])[required_columns].copy()

    md5_to_fontnames: dict[str, list[str]] = {}
    for _, row in unique_df[["MD5", "Font File Name"]].dropna().iterrows():
        md5 = str(row["MD5"])
        font_name = str(row["Font File Name"])
        md5_to_fontnames.setdefault(md5, []).append(font_name)

    print(f"  Metadata Availability Check for {len(md5_to_fontnames)} unique MD5(s) in batches of {BATCH_SIZE}...")
    found_font_names = check_metadata_availability(md5_to_fontnames)
    unique_df["Metadata Availability"] = unique_df["Font File Name"].apply(
        lambda x: "Yes" if str(x) in found_font_names else "No"
    )

    print(f"  Curl Status Check for {len(md5_to_fontnames)} unique MD5(s)...")
    md5_to_status = check_asset_status(unique_df["MD5"].astype(str).tolist())
    unique_df["Status Code"] = unique_df["MD5"].astype(str).map(
        lambda x: md5_to_status[x][0] if x in md5_to_status else ""
    )
    unique_df["Curl Status Check"] = unique_df["MD5"].astype(str).map(
        lambda x: md5_to_status[x][1] if x in md5_to_status else ""
    )

    base_dir = os.path.dirname(os.path.abspath(input_path))
    output_folder = os.path.join(base_dir, f"UNIQUE {name_without_ext}")
    downloads_folder = os.path.join(output_folder, f"Downloaded Files")
    os.makedirs(output_folder, exist_ok=True)
    os.makedirs(downloads_folder, exist_ok=True)

    file_sizes = []
    total_with_webpath = unique_df["Web Path"].dropna().astype(str).str.strip().ne("").sum()
    downloaded_count = 0
    with tqdm(
        unique_df.iterrows(),
        total=len(unique_df),
        desc=f"Downloading fonts [0/{total_with_webpath} files]",
        bar_format="{desc} {elapsed}",
    ) as pbar:
        for _, row in pbar:
            web_path = str(row.get("Web Path", "") or "")
            font_file_name = str(row.get("Font File Name", "") or "unknown_font")
            size = download_font(web_path, font_file_name, downloads_folder)
            file_sizes.append(size)
            if not size.startswith("N/A"):
                downloaded_count += 1
            pbar.set_description(f"Downloading fonts [{downloaded_count}/{total_with_webpath} files] → {font_file_name[:35]}")

    unique_df["FILE SIZE"] = file_sizes

    shutil.copy2(input_path, os.path.join(output_folder, filename))

    output_path = os.path.join(output_folder, f"Unique {name_without_ext}.csv")
    unique_df.to_csv(output_path, index=False)

    downloaded = sum(1 for s in file_sizes if not s.startswith("N/A"))
    print(f"  Done. {len(unique_df)} unique records written. {downloaded}/{len(unique_df)} fonts downloaded to '{name_without_ext} Downloads/'.")

def process_input(input_path: str):
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
            process_file(f)
    elif os.path.isfile(input_path):
        print(f"Processing: {os.path.basename(input_path)}")
        process_file(input_path)
    else:
        print(f"Error: '{input_path}' is not a valid file or folder.")
        sys.exit(1)

# User INPUT FOR FAILED FONTS
INPUT_FILE = "OneFailed.xlsx"  # Set to a file path or folder path

if __name__ == "__main__":
    if len(sys.argv) >= 2:
        process_input(sys.argv[1])
    elif INPUT_FILE:
        process_input(INPUT_FILE)
    else:
        print("Usage: python unique_font_file.py <file_or_folder_path>")
        sys.exit(1)
