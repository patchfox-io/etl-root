import base64
import datetime
import logging
import os
import tempfile
from collections.abc import Generator
from zoneinfo import ZoneInfo

from dateutil import parser
from github import Auth, Github, GithubException
from github.Repository import Repository
from gql import Client, gql
from gql.transport.requests import RequestsHTTPTransport

from patchfox_etl.buildfiles import BuildFile
from .base import AbstractRepo, Commit, GitBlameRecord, RepoBuildFile


LOG = logging.getLogger(__name__)
logging.getLogger("gql").setLevel(logging.ERROR)

GITHUB_BLAME_GQL_QUERY = """
    {{
        repository(owner: "{repo_owner}", name: "{repo_name}") {{
            object(oid: "{commit_hash}") {{
                ... on Commit {{
                    blame(path: "{build_file_path}") {{
                        ranges {{
                            startingLine
                            endingLine
                            commit {{
                                oid
                                committedDate
                                author {{
                                    name
                                    email
                                }}
                            }}
                        }}
                    }}
                }}
            }}
        }}
    }}
"""


class GithubRepo(AbstractRepo):
    _github_api: Github = None
    _repo: Repository = None

    @property
    def github_api(self):
        if self._github_api is None:
            self._github_api = Github(auth=Auth.Token(self.github_api_token))
        return self._github_api
    
    @property
    def github_api_token(self):
        return self.kwargs["github_api_token"]

    @property
    def repo(self) -> Repository:
        if self._repo is None:
            self._repo = self.github_api.get_repo(self.datapath)
        return self._repo

    def branch(self):
        return self.repo.default_branch

    def discover_build_files(self, recurse: bool):
        contents = self.repo.get_contents("")
        while contents:
            file_content = contents.pop(0)
            if file_content.type == "dir" and recurse:
                contents.extend(self.repo.get_contents(file_content.path))
            else:
                cls = BuildFile.get_build_file(file_content.name)
                if not cls:
                    continue
                repo_build_file = RepoBuildFile(
                    project_name=self.repo.name,
                    branch=self.branch(),
                    build_file_type=cls,
                    build_file_path=file_content.path,
                    build_file_rel_path=file_content.path
                )
                LOG.info(f'adding record: {repo_build_file}')
                self.buildfiles.append(repo_build_file)

    def get_file_at(self, file_path: str, commit: Commit) -> str:
        if (file_path, commit.commit_hash) not in self._file_history_cache:
            LOG.info(f"Retrieving {file_path} @ {commit.commit_hash} from Github API")
            file_content = self.repo.get_contents(file_path, ref=commit.commit_hash)
            if file_content.encoding == "base64":
                self._file_history_cache[(file_path, commit.commit_hash)] = base64.b64decode(file_content.content.encode()).decode()
            else:
                self._file_history_cache[(file_path, commit.commit_hash)] = file_content.content
        return self._file_history_cache[(file_path, commit.commit_hash)]

    def iter_blame(self, repo_build_file: RepoBuildFile, commit: Commit) -> Generator[GitBlameRecord, None, None]:
        transport = RequestsHTTPTransport(
            url="https://api.github.com/graphql",
            verify=True,
            retries=3,
            headers={"Authorization": f"Bearer {self.github_api_token}"}
        )
        client = Client(transport=transport, fetch_schema_from_transport=True)
        query = GITHUB_BLAME_GQL_QUERY.format(
            repo_owner=self.repo.owner.login,
            repo_name=self.repo.name,
            commit_hash=commit.commit_hash,
            build_file_path=repo_build_file.build_file_path
        )
        query = gql(query)
        result = client.execute(query)

        build_file_contents = self.get_file_at(repo_build_file.build_file_path, commit).split("\n")
        for blame in result["repository"]["object"]["blame"]["ranges"]:
            blame_commit = Commit(
                commit_hash=blame["commit"]["oid"], 
                commit_timestamp=parser.parse(blame["commit"]["committedDate"]).astimezone(ZoneInfo("Zulu"))
            )
            for lineno in range(blame["startingLine"], blame["endingLine"] + 1):
                # try:
                #     build_file_contents[lineno - 1]
                # except:
                #     print((
                #         lineno,
                #         blame_commit.commit_hash,
                #         blame["commit"]["author"]["email"],
                #         blame_commit.commit_timestamp,
                #         # buildFileLine=build_file_contents[lineno - 1]
                #     ))
                #     print("\n".join(build_file_contents))
                #     raise
                yield GitBlameRecord(
                    index=lineno,
                    commit=blame_commit.commit_hash,
                    commit_author=blame["commit"]["author"]["email"],
                    commit_timestamp=blame_commit.commit_timestamp,
                    buildFileLine=build_file_contents[lineno - 1]
                )
    
    def get_history(self, repo_build_file: RepoBuildFile, since: datetime.datetime | None) -> Generator[Commit, None, None]:
        for commit in self.repo.get_commits(path=repo_build_file.build_file_path):
            commit = Commit(
                commit_hash=commit.sha,
                commit_timestamp=commit.commit.committer.date.astimezone(ZoneInfo("Zulu"))
            )
            try:
                self.get_file_at(repo_build_file.build_file_path, commit)
            except GithubException.UnknownObjectException:
                continue
            yield commit
    
    def get_sbom(self, repo_build_file: RepoBuildFile, commit: Commit) -> dict:
        build_file_name = os.path.basename(repo_build_file.build_file_path)
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpfile = os.path.join(tmpdir, build_file_name)
            file_content = self.get_file_at(repo_build_file.build_file_path, commit)
            with open(tmpfile, "w") as f:
                f.write(file_content)
            return super().get_sbom(tmpfile)