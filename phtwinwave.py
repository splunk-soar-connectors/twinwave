# File: phtwinwave.py
#
# Copyright (c) TwinWave, 2022
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software distributed under
# the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
# either express or implied. See the License for the specific language governing permissions
# and limitations under the License.

import json
import time
from datetime import datetime, timedelta

import requests

""" CONSTANTS """
DATE_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
API_HOST = "https://api.twinwave.io"
API_VERSION = "v1"
REQUEST_TIMEOUT = 60


class AuthenticationException(Exception):
    pass


class Twinwave:
    def __init__(self, config):
        self._host = f"{API_HOST}/{API_VERSION}"
        self._base_url = "https://app.twinwave.io/"
        self._api_key = "{}".format(config.get("api_token"))
        self._proxy = None
        self._verify = True
        self._since = int(config.get("since"))

    def get_header(self):
        return {"X-API-KEY": self._api_key}

    def get_recent_jobs(self, num_jobs=10, username=None, source=None, state=None):
        url = f"{self._host}/jobs/recent"
        params = {}
        params["count"] = num_jobs
        if username:
            params["username"] = username
        if source:
            params["source"] = source
        if state:
            params["state"] = state
        resp = requests.get(url, params=params, headers=self.get_header(), verify=self._verify, proxies=self._proxy, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json()

    def poll_for_done_jobs(self, token):
        url = f"{self._host}/jobs/poll"
        time_now = datetime.now()
        if token:
            resp = requests.get(url, params={"token": token}, headers=self.get_header(), timeout=REQUEST_TIMEOUT)
        else:
            since = self._since
            if not since:
                since = 0
                epoch_convert_time = time_now.timestamp()
            else:
                prev_date = time_now - timedelta(hours=since)
                epoch_convert_time = prev_date.timestamp()
            try:
                resp = requests.get(url, params={"since": int(epoch_convert_time)}, headers=self.get_header(), timeout=REQUEST_TIMEOUT)
            except Exception:
                time.sleep(10)
            payload = resp.json()
        return payload

    def get_engines(self):
        url = f"{self._host}/engines"
        resp = requests.get(url, headers=self.get_header(), verify=self._verify, proxies=self._proxy, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json()

    def get_job(self, job_id):
        url = f"{self._host}/jobs/{job_id}"
        resp = requests.get(url, headers=self.get_header(), verify=self._verify, proxies=self._proxy, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json()

    def get_job_normalized_forensics(self, job_id):
        url = f"{self._host}/jobs/{job_id}/forensics"
        resp = requests.get(url, headers=self.get_header(), verify=self._verify, proxies=self._proxy, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json()

    def submit_url(self, scan_url, engine_list=[], parameters=None, priority=None, profile=None):
        url = f"{self._host}/jobs/urls"
        req = {"url": scan_url, "engines": engine_list, "parameters": parameters}
        if priority:
            req["priority"] = priority
        if profile:
            req["profile"] = profile

        resp = requests.post(url, json=req, headers=self.get_header(), verify=self._verify, proxies=self._proxy, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json()

    def submit_file(self, file_name, file_obj, engine_list=[], priority=None, profile=None):
        url = f"{self._host}/jobs/files"
        payload = {}
        file_dict = {"filedata": file_obj}
        payload["engines"] = (None, json.dumps(engine_list))
        payload["filename"] = (None, file_name)
        payload["priority"] = priority
        payload["profile"] = profile

        resp = requests.post(url, data=payload, files=file_dict, headers=self.get_header(), verify=self._verify, proxies=self._proxy,
            timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json()

    def download_job_pdf(self, job_id):
        url = f"{self._host}/jobs/{job_id}/pdfreport"
        resp = requests.get(url, headers=self.get_header(), verify=self._verify, proxies=self._proxy, stream=True, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.content

    def download_artifact(self, artifact_path):
        url = f"{self._host}/jobs/artifacts/{artifact_path}"
        resp = requests.get(url, headers=self.get_header(), verify=self._verify, proxies=self._proxy, stream=True, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.content
