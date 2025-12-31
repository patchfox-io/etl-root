import base64
import datetime
import logging
import os
import tempfile
from collections.abc import Generator
from typing import List
from zoneinfo import ZoneInfo

from dateutil import parser
from gitlab import Gitlab
from gitlab.v4.objects import Project

from patchfox_etl.buildfiles import BuildFile
from .base import AbstractRepo, Commit, GitBlameRecord, RepoBuildFile


LOG = logging.getLogger(__name__)


class GitlabRepo(AbstractRepo):
    _gitlab_api: Gitlab = None
    _repo: Project = None

    @property
    def gitlab_api(self):
        if self._gitlab_api is None:
            self._gitlab_api = Gitlab(url=self.gitlab_api_baseurl, private_token=self.gitlab_api_token)
        return self._gitlab_api

    @property
    def gitlab_api_baseurl(self):
        return self.kwargs["gitlab_api_baseurl"]
    
    @property
    def gitlab_api_token(self):
        return self.kwargs["gitlab_api_token"]
    
    @property
    def repo(self) -> Project:
        if self._repo is None:
            self._repo = self.gitlab_api.projects.get(self.datapath)
        return self._repo

    def branch(self):
        for branch in self.repo.branches.list():
            if branch.default:
                return branch.name

    def discover_build_files(self, recurse: bool):
        for project_file in self.repo.repository_tree(ref=self.branch(), recursive=recurse, iterator=True):
            cls = BuildFile.get_build_file(project_file["name"])
            if not cls:
                continue
            repo_build_file = RepoBuildFile(
                project_name=self.repo.name,
                branch=self.branch(),
                build_file_type=cls,
                build_file_path=project_file["path"],
                build_file_rel_path=project_file["path"]
            )
            LOG.info(f'adding record: {repo_build_file}')
            self.buildfiles.append(repo_build_file)

    def get_file_at(self, file_path: str, commit: Commit) -> str:
        f = self.repo.files.get(file_path=file_path, ref=commit.commit_hash)
        return f.decode()
    
    def iter_blame(self, repo_build_file: RepoBuildFile, commit: Commit) -> Generator[GitBlameRecord, None, None]:
        lineno = 1
        for blame in self.repo.files.blame(file_path=repo_build_file.build_file_path, ref=commit.commit_hash):
            for line in blame["lines"]:
                yield GitBlameRecord(
                    index=lineno,
                    commit=blame["commit"]["id"],
                    commit_author=blame["commit"]["committer_email"],
                    commit_timestamp=parser.parse(blame["commit"]["committed_date"]).astimezone(ZoneInfo("Zulu")),
                    buildFileLine=line
                )
                lineno += 1
    
    def get_blame(self, repo_build_file: RepoBuildFile, commit: Commit) -> List[dict]:
        blame_records = [b.to_dict() for b in self.iter_blame(repo_build_file, commit)]
        blame_records.sort(key=lambda b: b["index"])
        return blame_records
    
    def get_history(self, repo_build_file: RepoBuildFile, since: datetime.datetime | None) -> Generator[Commit, None, None]:
        # TODO: Use since param
        for commit in self.repo.commits.list(query_parameters={"path": repo_build_file.build_file_path}, iterator=True):
            commit = Commit(
                commit_hash=commit.id,
                commit_timestamp=parser.parse(commit.created_at).astimezone(ZoneInfo("Zulu"))
            )
            try:
                self.get_file_at(repo_build_file.build_file_rel_path, commit)
            except:
                continue
            yield commit
    
    def get_metadata(self, repo_build_file: RepoBuildFile, commit: Commit) -> dict:
        return {
            "datasource": repo_build_file.project_name,
            "dataType": repo_build_file.build_file_type.PURL,
            "commitHash": commit.commit_hash,
            "commitDatetime": commit.commit_timestamp.isoformat(),
            "commitBranch": repo_build_file.branch,
            "eventDatetime": datetime.datetime.now(ZoneInfo("Zulu")).replace(microsecond=0).isoformat()
        }
    
    def get_sbom(self, repo_build_file: RepoBuildFile, commit: Commit) -> dict:
        build_file_name = os.path.basename(repo_build_file.build_file_path)
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpfile = os.path.join(tmpdir, build_file_name)
            file_content = self.get_file_at(repo_build_file.build_file_path, commit)
            with open(tmpfile, "wb") as f:
                f.write(file_content)
            return super().get_sbom(tmpfile)