#!/usr/bin/env python

import argparse
import json
import os

import requests


ap = argparse.ArgumentParser()
ap.add_argument("baseurl")
ap.add_argument("token")
args = ap.parse_args()


r = requests.post(
    f"{args.baseurl}/api/v1/auth/data-service",
    headers={"Authorization": f"Bearer {args.token}"}
)
r.raise_for_status()

response = r.json()["data"]["response"]
if isinstance(response, str):
    response = json.loads(response)

jwt = response["access_token"]