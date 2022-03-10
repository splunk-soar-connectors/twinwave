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

# Phantom App imports
import time

import phantom.app as phantom
from phantom import vault
from phantom.action_result import ActionResult
from phantom.base_connector import BaseConnector
from phantom.vault import Vault

# Usage of the consts file is recommended
from phtwinwave import Twinwave

JOB_POLL_INTERVAL = 15


class RetVal(tuple):
    def __new__(cls, val1, val2=None):

        return tuple.__new__(RetVal, (val1, val2))


def _make_resource_tree(resources):
    root = [r for r in resources if not r["ParentID"]][0]

    def _get_children(r, resources):
        r["Children"] = [c for c in resources if c["ParentID"] == r["ID"]]
        for c in r["Children"]:
            _get_children(c, resources)

    _get_children(root, resources)

    return root


class TwinWaveConnector(BaseConnector):
    def __init__(self):

        # Call the BaseConnectors init first
        super(TwinWaveConnector, self).__init__()
        self._state = None
        self._base_url = None

    def initialize(self):

        # Load the state in initialize, use it to store data that needs to be accessed across actions
        self._state = self.load_state()

        # Get the asset config from Phantom
        config = self.get_config()

        # Use the config to initialize fortisiem object to handle connections to the fortisiem server
        self._twinwave = Twinwave(config)

        return phantom.APP_SUCCESS

    def _add_to_vault(self, data, filename):
        # this temp directory uses "V" since this function is from the CLASS instance not the same as the "v" vault instance
        container_id = self.get_container_id()
        Vault.create_attachment(data, container_id, file_name=filename)

    def _handle_test_connectivity(self, param):

        # Add an action result object to self (BaseConnector) to represent the action for this param
        action_result = self.add_action_result(ActionResult(dict(param)))

        self.save_progress("Connecting to endpoint")

        try:
            self._twinwave.get_engines()

        except Exception as e:
            # the call to the 3rd party device or service failed
            # action result should contain all the error details so just return from here
            self.save_progress(str(e))
            self.save_progress("Test Connectivity Failed.")
            return action_result.get_status()

        # Return success
        self.save_progress("Test Connectivity Passed.")
        return action_result.set_status(phantom.APP_SUCCESS)

    def _handle_get_job_normalized_forensics(self, params):

        action_result = self.add_action_result(ActionResult(dict(params)))

        self.save_progress("Connecting to endpoint")

        should_wait = params.get("wait")
        timeout_in_minutes = params.get("timeout")
        job_id = params.get("job_id")

        try:
            if should_wait:
                self._get_job_data(job_id, should_wait, timeout_in_minutes)

            job_fore = self._twinwave.get_job_normalized_forensics(job_id)

        except Exception as e:
            self.save_progress(str(e))
            self.save_progress("Unable to retrieve forensics")
            return action_result.get_status()

        action_result.add_data(job_fore)
        self.save_progress("Job Normal Forensics Retrieved")
        return action_result.set_status(phantom.APP_SUCCESS)

    def _handle_submit_file(self, params):

        action_result = self.add_action_result(ActionResult(dict(params)))

        self.save_progress("Connecting to endpoint")

        submit_data = {}

        try:
            file = params.get("file")
            success, message, info = vault.vault_info(vault_id=file)
            file_path = info[0]["path"]
            file_name = info[0]["name"]
            f = open(file_path, "rb")
            file_data = f.read()
            submit_data = self._twinwave.submit_file(file_name, file_data)
        except Exception as err:
            self.save_progress(str(err))
            self.save_progress("Unable to submit file")
            return action_result.set_status(phantom.APP_ERROR)

        submit_data["AppURL"] = "https://app.twinwave.io/job/{}".format(submit_data.get("JobID"))
        action_result.add_data(submit_data)
        self.debug_print("results", dump_object=submit_data)
        self.save_progress("Submitted File")
        return action_result.set_status(phantom.APP_SUCCESS)

    def _handle_submit_url(self, params):

        action_result = self.add_action_result(ActionResult(dict(params)))

        self.save_progress("Connecting to endpoint")

        submit_data = {}

        try:
            url = params.get("url")
            submit_data = self._twinwave.submit_url(url)
        except Exception as e:
            self.save_progress(str(e))
            self.save_progress("Unable to submit url")
            return action_result.set_status(phantom.APP_ERROR)

        submit_data["AppURL"] = "https://app.twinwave.io/job/{}".format(submit_data.get("JobID"))
        action_result.add_data(submit_data)
        self.debug_print("results", dump_object=submit_data)
        self.save_progress("Submitted URL")
        return action_result.set_status(phantom.APP_SUCCESS)

    def _handle_get_engines(self, params):

        action_result = self.add_action_result(ActionResult(dict(params)))

        self.save_progress("Connecting to endpoint")

        try:
            response = self._twinwave.get_engines()

        except Exception as e:
            self.save_progress(str(e))
            self.save_progress("Unable to get engines")
            return action_result.get_status()

        action_result.add_data(response)
        self.save_progress("Submitted URL")
        return action_result.set_status(phantom.APP_SUCCESS)

    def _handle_list_recent_jobs(self, params):

        action_result = self.add_action_result(ActionResult(dict(params)))

        self.save_progress("Connecting to endpoint")
        # save_state load_state to get last run job date to reference
        # after save the run now as last run
        # parameter uses an integer from how many days back you want
        # parameter count uses start at 100 if applicable if not start at 0
        # paremter pull for "DONE" jobs
        try:
            list = self._twinwave.get_recent_jobs(params)

        except Exception as e:
            self.save_progress(str(e))
            self.save_progress("Unable to get jobs")
            return action_result.get_status()

        action_result.add_data(list)
        self.save_progress("Gathered Recent Jobs")
        return action_result.set_status(phantom.APP_SUCCESS)

    def _handle_poll_recent_jobs(self, params):
        action_result = self.add_action_result(ActionResult(dict(params)))
        state_dict = self.load_state()
        next_token = state_dict.get("token", None)
        try:
            payload = self._twinwave.poll_for_done_jobs(next_token)
        except Exception as e:
            self.save_progress(str(e))
            self.save_progress("Unable to get jobs")
            return action_result.get_status()
        jobs = payload.get("Jobs")
        if jobs:
            for job in jobs:
                container = {}
                job_id = job["ID"]
                submission_name = job["Submission"]["Name"]
                container["name"] = submission_name
                container["source_data_identifier"] = job_id
                container["run_automation"] = True
                container["data"] = job
                container["artifacts"] = []

                for resource in job["Resources"]:
                    severity = "low"
                    if resource["DisplayScore"] >= 70:
                        severity = "high"
                    elif resource["DisplayScore"] >= 30:
                        severity = "medium"

                    if resource["Type"] == "URL":
                        container["artifacts"].append(
                            {
                                "data": resource,
                                "cef": {"requestURL": resource["Name"]},
                                "label": "url",
                                "name": resource["Name"],
                                "severity": severity,
                                "type": "url",
                            }
                        )
                    elif resource["Type"] == "file":
                        container["artifacts"].append(
                            {
                                "data": resource,
                                "cef": {
                                    "fileName": resource["Name"],
                                    "fileHash": resource["FileMetadata"]["SHA256"],
                                    "fileSize": resource["FileMetadata"]["Size"],
                                    "fileType": resource["FileMetadata"]["MimeType"],
                                },
                                "label": "file",
                                "name": resource["Name"],
                                "severity": severity,
                                "type": "file",
                            }
                        )

                ret_val, msg, cid = self.save_container(container)
                if phantom.is_fail(ret_val):
                    self.save_progress("Error saving container: {}".format(msg))
                    self.debug_print("Error saving container: {} -- CID: {}".format(msg, cid))
        else:
            self.debug_print("payload_empty")
        state_dict["token"] = payload.get("NextToken")
        self.save_state(state_dict)
        return action_result.set_status(phantom.APP_SUCCESS)

    def _get_job_data(self, job_id, should_wait, timeout_in_minutes):
        start_time = time.time()
        while True:
            try:
                job_summary = self._twinwave.get_job(job_id)

                if job_summary.get("State") not in ("done", "error") and should_wait:
                    self.debug_print("Job is in state '{}', waiting and retrying..".format(job_summary.get("State")))
                    time.sleep(JOB_POLL_INTERVAL)
                    continue
                elif time.time() > start_time + timeout_in_minutes * 60:
                    self.debug_print("Giving up polling for job status")
                    self.save_progress("Timed out waiting for job to be complete")
                    return None
                else:
                    return job_summary
            except Exception as e:
                self.save_progress(str(e))
                self.save_progress("Unable to get job")
                return None

    def _handle_get_job_summary(self, params):

        action_result = self.add_action_result(ActionResult(dict(params)))

        self.save_progress("Connecting to endpoint")

        should_wait = params.get("wait")
        timeout_in_minutes = params.get("timeout")
        job_id = params.get("job_id")

        self.debug_print(
            "Getting summary for job ID: {}, wait: {}, timeout: {}".format(params.get("job_id"), params.get("wait"), params.get("timeout"))
        )

        job_summary = self._get_job_data(job_id, should_wait, timeout_in_minutes)
        if not job_summary:
            return action_result.set_status(phantom.APP_ERROR)

        job_summary["ResourceTree"] = _make_resource_tree(job_summary["Resources"])

        action_result.add_data(job_summary)
        action_result.update_summary({"JobID": job_id, "Score": job_summary.get("DisplayScore"), "Verdict": job_summary.get("Verdict")})

        self.save_progress("Job Summary Retrieved")

        return action_result.set_status(phantom.APP_SUCCESS)

    def _handle_get_job_pdf_report(self, params):
        action_result = self.add_action_result(ActionResult(dict(params)))

        self.save_progress("Connecting to endpoint")

        should_wait = params.get("wait")
        timeout_in_minutes = params.get("timeout")
        job_id = params.get("job_id")

        if should_wait:
            # do this just to make sure the job is completed
            job_summary = self._get_job_data(job_id, should_wait, timeout_in_minutes)
            if not job_summary:
                return action_result.set_status(phantom.APP_ERROR)

        try:
            pdf_data = self._twinwave.download_job_pdf(job_id)

            self._add_to_vault(data=pdf_data, filename=f"TwinWave job report {job_id}.pdf")
        except Exception as e:
            self.save_progress(str(e))
            self.save_progress("Unable to get PDF report")
            return action_result.set_status(phantom.APP_ERROR)

        return action_result.set_status(phantom.APP_SUCCESS)

    def _handle_get_job_screenshots(self, params):
        action_result = self.add_action_result(ActionResult(dict(params)))

        self.save_progress("Connecting to endpoint")

        should_wait = params.get("wait")
        timeout_in_minutes = params.get("timeout")
        job_id = params.get("job_id")

        if should_wait:
            # do this just to make sure the job is completed
            job_summary = self._get_job_data(job_id, should_wait, timeout_in_minutes)
            if not job_summary:
                return action_result.set_status(phantom.APP_ERROR)

        try:
            forensics = self._twinwave.get_job_normalized_forensics(job_id)

            for i, ss in enumerate(forensics.get("Screenshots", [])):
                self.save_progress(f"Downloading screenshot #{i}")

                shot_data = self._twinwave.download_artifact(ss["ArtifactPath"])
                self._add_to_vault(shot_data, f"TwinWave screenshot #{i}.png")

            screenshot_count = len(forensics.get("Screenshots", []))

            action_result.append_to_message(f"Attached {screenshot_count} screenshots")
            action_result.update_summary({"screenshot count": screenshot_count})
            action_result.add_data({"screenshot_count": screenshot_count})
        except Exception as e:
            self.save_progress(str(e))
            self.save_progress("Unable to download screenshots")
            return action_result.set_status(phantom.APP_ERROR)

        return action_result.set_status(phantom.APP_SUCCESS)

    def handle_action(self, param):

        ret_val = phantom.APP_SUCCESS

        # Get the action that we are supposed to execute for this App Run
        action_id = self.get_action_identifier()

        self.debug_print("action_id", self.get_action_identifier())

        self.save_progress("action_id={}".format(action_id))

        if action_id == "test_connectivity":
            ret_val = self._handle_test_connectivity(param)
        elif action_id == "twinwave_get_job_normalized_forensics":
            ret_val = self._handle_get_job_normalized_forensics(param)
        elif action_id == "twinwave_get_job_summary":
            ret_val = self._handle_get_job_summary(param)
        elif action_id == "twinwave_list_recent_jobs":
            ret_val = self._handle_list_recent_jobs(param)
        elif action_id == "twinwave_submit_file":
            ret_val = self._handle_submit_file(param)
        elif action_id == "twinwave_submit_url":
            ret_val = self._handle_submit_url(param)
        elif action_id == "twinwave_get_job_pdf":
            ret_val = self._handle_get_job_pdf_report(param)
        elif action_id == "twinwave_get_job_screenshots":
            ret_val = self._handle_get_job_screenshots(param)
        elif action_id == "on_poll":
            ret_val = self._handle_poll_recent_jobs(param)
        return ret_val

    def finalize(self):
        # Save the state, this data is saved accross actions and app upgrades
        self.save_state(self._state)
        return phantom.APP_SUCCESS
