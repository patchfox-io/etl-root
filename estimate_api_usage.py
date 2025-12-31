#!/usr/bin/env python

import argparse
import os

from github import Auth, Github
from patchfox_etl.buildfiles import BuildFile


GITHUB_API_TOKEN = os.environ["GITHUB_API_TOKEN"]
GH = Github(auth=Auth.Token(GITHUB_API_TOKEN))


ap = argparse.ArgumentParser()
ap.add_argument("org")
args = ap.parse_args()


org = GH.get_organization(args.org)
all_repos = org.get_repos(type="public")
count = int(all_repos.totalCount / 30) + 1
print(f"{count} requests to enumerate repos")
for repo in all_repos:
    try:
        contents = repo.get_contents("")
    except:
        count += 1
        print(f"1 requests to enumerate files in {repo.name} ({count} total)")
        continue
    pages = int(len(contents) / 30) + 1
    count += pages
    print(f"{pages} requests to enumerate files in {repo.name} ({count} total)")
    for file_content in contents:
        cls = BuildFile.get_build_file(file_content.name)
        if not cls:
            continue
        commits = repo.get_commits(path=file_content.path)
        pages = int(commits.totalCount / 30) + 1
        count += pages
        print(f"{pages} requests to get commits for {file_content.name} ({count} total)")

print(f"{count} total requests")