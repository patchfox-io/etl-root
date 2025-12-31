import base64
import datetime
import io
import json
import logging
import time
from typing import NamedTuple
from urllib.parse import urlparse, urljoin 

import requests
from packageurl import PackageURL


LOG = logging.getLogger(__name__)


class ETLBundle(NamedTuple):
    name: str
    commitDatetime: datetime.datetime
    file_object: io.BytesIO


import time

import requests


class AutoRetrySession(requests.Session):
    def get_sleep_time(self, response):
        # pylint: disable=unused-argument,no-self-use
        return 3

    def request(self, *args, **kwargs):
        # pylint: disable=signature-differs
        retries = 5
        r = None
        while retries > 0:
            retries -= 1
            try:
                r = super().request(*args, **kwargs)
                if r.status_code in (429, 500, 502, 504):
                    if retries == 0:
                        return r
                    time.sleep(self.get_sleep_time(r))
                    continue
            except (requests.exceptions.ConnectionError, ConnectionRefusedError):
                if retries == 0:
                    raise
                time.sleep(3)
                continue
            else:
                break
        return r


class PatchfoxApi(AutoRetrySession):
    jwt: str | None = None
    
    def __init__(self, patchfox_organization, patchfox_datasource, patchfox_api_token, patchfox_get_api_baseurl=None, patchfox_post_api_baseurl=None):
        super().__init__()
        self.organization = patchfox_organization
        self.datasource = patchfox_datasource
        self.api_token = patchfox_api_token
        self.get_api_baseurl = patchfox_get_api_baseurl or f"https://{patchfox_organization}.patchfox.io"
        self.post_api_baseurl = patchfox_post_api_baseurl or self.get_api_baseurl
    
    # Override upstream requests.Session methods
    def prepare_request(self, request):
        parsed = urlparse(request.url)

        if not parsed.scheme:
            if request.method == "POST":
                baseurl = self.post_api_baseurl
            else:
                baseurl = self.get_api_baseurl
            request.url = urljoin(baseurl, request.url)
            parsed = urlparse(request.url)

            if not (parsed.scheme == "http" and parsed.hostname.split(".")[-1] == "localhost"):
                request.headers.update({
                    "Authorization": f"Bearer {self.get_access_token()}"
                })

        LOG.debug(f'sending request to PatchFox at: {request.url}')
        return super().prepare_request(request)

    def _get_access_token(self):
        r = self.post(
            f"{self.get_api_baseurl}/api/v1/auth/data-service",
            headers={"Authorization": f"Bearer {self.api_token}"}
        )
        r.raise_for_status()
        auth_response = r.json()["data"]["response"]
        if isinstance(auth_response, str):
            auth_response = json.loads(auth_response)
        jwt = auth_response["access_token"]
        return jwt
    
    def get_jwt_expires(self) -> datetime.datetime:
        if self.jwt is None:
            return datetime.datetime.fromtimestamp(0)
        try:
            p = self.jwt.split(".")[1]
        except:
            return datetime.datetime.fromtimestamp(0)
        
        p += "=" * divmod(len(p), 4)[1]
        
        jwt_json = base64.b64decode(p.encode()).decode()
        jwt = json.loads(jwt_json)

        return datetime.datetime.fromtimestamp(jwt["exp"])
    
    def jwt_is_valid(self) -> bool:
        return self.get_jwt_expires() > datetime.datetime.now()
    
    def get_access_token(self):
        if not self.jwt_is_valid():
            LOG.info("Refreshing auth token")
            self.jwt = self._get_access_token()
            LOG.info(f"New auth token valid until {self.get_jwt_expires().isoformat()}")
        return self.jwt
    
    def get_latest_event(self, package_url: PackageURL):
        (datasource_name, _, datasource_branch) = package_url.name.partition("::")
        r = self.get(
            "/api/v1/datasourceEvents/latest",
            params={
                "domain": package_url.namespace,
                "name": datasource_name,
                "branch": datasource_branch,
                "type": package_url.version
            }
        )
        if r.status_code == 404:
            return None
        r.raise_for_status()
        r_json = r.json()
        LOG.debug(f'response from data service is: {r_json}')
        return r_json["data"]["datasourceEvent"]
    
    def send_event(self, archive: ETLBundle, datasource_purl: PackageURL) -> requests.Response | None:
        # print(datasource_purl.to_string())
        r = self.post(
            "/api/v1/input/git",
            files={
                "eventFileData": (archive.name, archive.file_object)
            },
            data={
                "datasourceEvent": datasource_purl.to_string()
            }
        )

        if not r.ok:
            LOG.warning(f'response code was not ok: {r.status_code}')
            LOG.warning(f'response json was: {r.json()}')

        return r