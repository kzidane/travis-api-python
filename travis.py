import json
import os
import requests
from time import sleep

headers = { \
    "Content-Type": "application/json", \
    "Accept": "application/json",
    "Travis-API-Version": "3",
    "Authorization": "token {}".format(os.environ["TRAVIS_TOKEN"])
}

_BASE_URL = "https://api.travis-ci.com/"
def _request(method="get", endpoint="", headers=headers, **kwargs):
    """ Wrapper around requests.get and requests.post """

    methods = {
        "get": requests.get,
        "patch": requests.patch,
        "post": requests.post
    }

    if method in methods:
        request = methods[method]
    else:
        request = methods["get"]

    return request(_BASE_URL + endpoint, headers=headers, **kwargs)

def _toggle_setting(setting_name, value, owner, repo):
    response = _request("patch", "repo/{}%2F{}/setting/{}".format(owner, repo, setting_name), data='{{ "setting.value": {} }}'.format(value))
    return response.status_code == 200

def activate(owner, repo):
    """ Enables a repository on Travis CI """

    response = _request(method="post", endpoint="repo/{}%2F{}/activate".format(owner, repo))
    if response.status_code != 200:
        return

    # block 'til repo is active or timeout
    for i in range(10):
        repo = get_repo(owner, repo)
        if repo["active"]:
            return True
        sleep(1)

def auto_cancel(owner, repo):
    """ Enables auto-cancellation of Travis CI builds """
    return _toggle_setting("auto_cancel_pushes", "true", owner, repo)

def disable_build_pushes(owner, repo):
    return _toggle_setting("build_pushes", "false", owner, repo)

def disable_build_pull_requests(owner, repo):
    return _toggle_setting("build_pull_requests", "false", owner, repo)

def configure(owner, repo):
    _repo = get_repo(owner, repo)
    if not _repo:
        sync()
        _repo = get_repo(owner, repo)

        if not _repo:
            return

    if (not _repo["active"] and not activate(owner, repo)) or \
        not disable_build_pushes(owner, repo) or \
        not disable_build_pull_requests(owner, repo) or \
        not auto_cancel(owner, repo):
            return

    return True

def build(owner, repo, branch):
    """ Triggers a build for owner/repo:branch, syncing and activating repo as necessary """

    # trigger build
    # TODO add webhook URL
    payload = {
        "request": {
            "branch": branch,
            "config": {
                "language": "python",
                "python": "3.5",
                "merge_mode": "replace",
                "script": "python3 check50.py --full --local {} ../*".format(branch),
                "notifications": { "webhooks": "https://cs50.me/hooks/travis" }
            }
        }
    }

    response = _request(method="post", endpoint="repo/{}%2F{}/requests".format(owner, repo), data=json.dumps(payload))
    if response.status_code == 404:
        if not sync() or not activate(owner, repo) or not auto_cancel(owner, repo):
            return

        response = _request(method="post", endpoint="repo/{}%2F{}/requests".format(owner, repo), data=json.dumps(payload))

    elif response.status_code != 202:
        return

    return True

def get_jobs(build_id):
    """ Returns jobs associated with build whose id is build_id """

    response = _request(endpoint="build/{}".format(build_id))
    if response.status_code == 200:
        return response.json()["jobs"]

def get_log_parts(job_id):
    """ Returns log parts for the job whose id is job_id """

    response = _request(endpoint="job/{}/log".format(job_id))
    if response.status_code == 200:
        return response.json()["log_parts"]

def get_repo(owner, repo):
    """ Returns information about a repository """

    response = _request(endpoint="repo/{}%2F{}".format(owner, repo))
    if response.status_code == 200:
        return response.json()

def get_user():
    """ Returns information about the current user """

    response = _request(endpoint="user")
    if response.status_code == 200:
        return response.json()

def sync():
    """ Syncs user's GitHub repositories so they are seen by Travis CI """

    user = get_user()
    if not user:
        return

    response = _request(method="post", endpoint="user/{}/sync".format(user["id"]))
    if response.status_code != 200:
        return

    # block 'til syncing is done or timeout
    for i in range(10):
        user = get_user()
        if not user["is_syncing"]:
            return True
        sleep(1)
