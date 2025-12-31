import datetime
import logging
from collections.abc import Generator
from typing import Dict, List, NamedTuple, Tuple, Type
from zoneinfo import ZoneInfo

from patchfox_etl.buildfiles import BuildFile
from patchfox_etl.syft import Syft


LOG = logging.getLogger(__name__)


class Commit(NamedTuple):
    commit_hash: str
    commit_timestamp: datetime.datetime


class GitBlameRecord(NamedTuple):
    index: int
    commit: str
    commit_author: Dict[str, str]
    commit_timestamp: datetime.datetime
    buildFileLine: str

    def to_dict(self):
        return {
            "index": self.index,
            "commit": self.commit,
            "author": self.commit_author,
            "commitDatetime": self.commit_timestamp.isoformat(),
            "buildFileLine": self.buildFileLine
        }


class RepoBuildFile(NamedTuple):
    project_name: str
    branch: str
    build_file_type: Type[BuildFile]
    build_file_path: str
    build_file_rel_path: str


class AbstractRepo:
    buildfiles: List[RepoBuildFile]
    datapath: str
    kwargs: dict
    _file_history_cache: Dict[Tuple[str, str], str]

    def __init__(self, datapath, **kwargs):
        self.datapath = datapath
        self.buildfiles = []
        self.kwargs = kwargs
        self._file_history_cache = {}

    def __repr__(self):
        return f"<{type(self).__name__}[{self.datapath}@{self.branch()}]>"

    def branch(self):
        raise NotImplementedError

    def discover_build_files(self, recurse: bool):
        raise NotImplementedError
    
    def iter_blame(self, repo_build_file: RepoBuildFile, commit: Commit) -> Generator[GitBlameRecord, None, None]:
        raise NotImplementedError
    
    def get_blame(self, repo_build_file: RepoBuildFile, commit: Commit) -> List[dict]:
        blame_records = [b.to_dict() for b in self.iter_blame(repo_build_file, commit)]
        blame_records.sort(key=lambda b: b["index"])
        return blame_records
    
    def get_history(self, repo_build_file: RepoBuildFile) -> Generator[Commit, None, None]:
        raise NotImplementedError
    
    def get_metadata(self, repo_build_file: RepoBuildFile, commit: Commit) -> dict:
        return {
            "datasource": repo_build_file.project_name,
            "dataType": repo_build_file.build_file_type.PURL,
            "commitHash": commit.commit_hash,
            "commitDatetime": commit.commit_timestamp.isoformat(),
            "commitBranch": repo_build_file.branch,
            "eventDatetime": datetime.datetime.now(ZoneInfo("Zulu")).replace(microsecond=0).isoformat()
        }
    
    def get_sbom(self, source_file_path: str) -> dict:
        return Syft.get_sbom(source_file_path)
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        pass