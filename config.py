import urllib3
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

SUPPORTED_EXTENSIONS = (".csv", ".xlsx", ".xls")

DOWNLOAD_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
}

METADATA_API = "https://fbms-itw.monotype.com/font/{md5s}/metadata"
METADATA_BATCH_SIZE = 20

STATUS_API = "https://asset-itw.monotype.com/asset/status"
STATUS_SOURCE = "5386d862-844b-4b01-9533-0613ee64e307"
STATUS_CONSUMER_ID = "ITW"

# Update all __cf_bm and _cfuvid values when Cloudflare tokens expire
STATUS_COOKIE = (
    "__cf_bm=ydfjakZqRKqv9SY0_NvReEC9NPwTwPi99SoVNPIB098-1726134827-1.0.1.1-VfZFw_bHXrLAtPza_SWJLJPAXxJwHqPZ4xWoJ2.JkYGU0uz2p4btNI6CpMiF7.TUbO4wHf8D5ub05qvatQhPag; "
    "__cf_bm=.RZq.FSS_A07QnPFDYk3D7zfkSC.qDc92T3EZgGWvo8-1771573425-1.0.1.1-Hh25p7RvIECT3UUqm4QfgMqjphRHoNpwEvU9Gaw1il2nrAI.poClUqn8d_xbRFiuHry7Qhhz91fResE9CQVS6PtdIYL5eYsXN5jr70dPqPc; "
    "_cfuvid=tn_0ehlhorKasT4XPCvoO.YZaCYOFFkOrxoOKGDpsFw-1771498554526-0.0.1.1-604800000; "
    "__cf_bm=2vPEF4Hl0ebS3_NJpDpYVKjtb0GrI27IV.Nl5BrlCII-1771574127-1.0.1.1-BR7gA3FkMUv4rGmAEXT7eoGb44FV9u4FIbHOpWeTktsrBJQHQk88sxWT78Fz7tZClMWDjfZdjrIuTHcORsrt.c2cuWlVqjrDOzf9EnAF1Sk"
)


def build_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=2, status_forcelist=[429, 500, 502, 503, 504])
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.mount("http://", HTTPAdapter(max_retries=retry))
    return session


SESSION = build_session()
