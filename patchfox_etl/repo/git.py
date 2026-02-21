import datetime
import io
import logging
import os
import tempfile
from collections.abc import Generator
from contextlib import contextmanager
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import git

from patchfox_etl.buildfiles import BuildFile
from .base import AbstractRepo, Commit, GitBlameRecord, RepoBuildFile

# from .syft import Syft


logging.getLogger("gql").setLevel(logging.ERROR)


LOG = logging.getLogger(__name__)


def commit_for_git_commit(commit: git.Commit):
    return Commit(
        commit_hash=commit.hexsha,
        commit_timestamp=commit.committed_datetime.astimezone(ZoneInfo("Zulu"))
    )


class GitRepo(AbstractRepo):
    EXCLUDED_DIRS = set([
        'node_modules', # otherwise it'll include all installed node packages
        'site-packages', # otherwise it'll include all installed virtual env python packages
        '.ve', 'venv', # since packages can exist (and be erroneously included) in other dirs
        'generated-sources', # nested generated java files can have their own pom.xml files
        '.angular', # angular likes to cache its own package with its own package.json 
        '.git', # skip the .git directory, there's nothing useful there
    ])

    _old_head: git.Commit = None

    def __init__(self, datapath, **kwargs):
        super().__init__(datapath, **kwargs)
        self._repo = git.Repo(self.datapath, odbt=git.GitCmdObjectDB)
        self._branch = None
        self.branch()

    def __enter__(self):
        self.tmpdir = None
        if self._repo.is_dirty(untracked_files=True):
            LOG.warning(f"Entering dirty git working dir '{self.datapath}', creating a temporary clone")
            self.tmpdir = tempfile.TemporaryDirectory()
            name = os.path.basename(self.datapath)
            with self.clone_from(self.datapath, os.path.join(self.tmpdir.name, name), cleanup=False) as repo:
                return repo

        return super().__enter__()
    
    def __exit__(self, exc_type, exc_value, traceback):
        if hasattr(self, '_repo') and self._repo:
            self._repo.close()
        if self.tmpdir:
            self.tmpdir.cleanup()
            self.tmpdir = None
        return super().__exit__(exc_type, exc_value, traceback)

    @property
    def HEAD(self) -> git.Commit:
        return self._repo.head.commit

    @classmethod
    @contextmanager
    def clone_from(cls, url, clone_into=None, head=None, cleanup=True):
        tmpdir = None

        parsed = urlparse(url)
        name = parsed.path.strip("/").split("/")[-1]
        if name.endswith(".git"):
            name = name[:-4]

        if clone_into is None:
            tmpdir = tempfile.TemporaryDirectory()
            target_dir = os.path.join(tmpdir.name, name)
        else:
            target_dir = os.path.join(clone_into, name)

        _old_head: git.Commit = None

        if os.path.exists(target_dir):
            repo = git.Repo(target_dir)

            # Store a reference to the old head so we can compare
            _old_head = repo.head.commit

            if head:
                LOG.info(f"Checking out {head} in {target_dir}")
                repo.head.reset(index=True, working_tree=True)
                repo.git.checkout(head)
                repo.remote("origin").pull(force=True)
        else:
            repo = git.Repo.clone_from(url, target_dir)

        o = cls(target_dir)
        if _old_head:
            o._old_head = _old_head

        yield o

        if tmpdir and cleanup:
            tmpdir.cleanup()
    
    def branch(self):
        if self._branch is None:
            self._branch = self._repo.active_branch.name
        return self._branch
    
    def get_relevant_commits(self, file_path: str):
        return [commit_for_git_commit(commit) for commit in self._repo.iter_commits(all=True, paths=file_path)]

    def discover_build_files(self, recurse: bool):
        project_name = os.path.basename(self.datapath.rstrip("/"))
        
        relevant_commits = []

        for root, dirs, files, in os.walk(self.datapath, topdown=True):
            if recurse:
                dirs[:] = [d for d in dirs if d not in self.EXCLUDED_DIRS]
            else:
                dirs[:] = []
            for filename in files:
                LOG.debug(f'looking at {filename}')
                cls = BuildFile.get_build_file(filename)
                if not cls:
                    continue

                norm_root = os.path.normpath(os.path.abspath(root))
                build_file_path = os.path.join(norm_root, filename)
                # record = (project_name, cls, build_file_path)
                repo_build_file = RepoBuildFile(
                    project_name=project_name,
                    branch=self.branch(),
                    build_file_type=cls,
                    build_file_path=build_file_path,
                    build_file_rel_path=os.path.relpath(build_file_path, self.datapath)
                )
                
                try:
                    with open(build_file_path) as f: ...
                except UnicodeDecodeError:
                    LOG.error(f'{filename} appears to be binary')
                    continue
                
                LOG.info(f'adding record: {repo_build_file}')
                self.buildfiles.append(repo_build_file)
                relevant_commits.extend(self.get_relevant_commits(repo_build_file.build_file_rel_path))
                
        if not self.buildfiles:
            LOG.info(f"No buildfiles found")
            return
                
        LOG.debug(f"Need to analyze {len(relevant_commits)} commits")
        with self.repo_at_commit():
            for commit in relevant_commits:
                with self.repo_at_commit(commit, reset_when_done=False) as repo:
                    for repo_build_file in self.buildfiles:
                        full_path = os.path.join(repo.working_tree_dir, repo_build_file.build_file_rel_path)
                        if os.path.exists(full_path):
                            with open(full_path) as f:
                                self._file_history_cache[(repo_build_file.build_file_rel_path, commit.commit_hash)] = f.read()
                        else:
                            self._file_history_cache[(repo_build_file.build_file_rel_path, commit.commit_hash)] = None

    def get_file_at(self, file_path: str, commit: Commit) -> str:
        if (file_path, commit.commit_hash) not in self._file_history_cache:
            with self.repo_with_commit(commit) as repo:
                full_path = os.path.join(repo.working_tree_dir, file_path)
                if not os.path.exists(full_path):
                    self._file_history_cache[(file_path, commit.commit_hash)] = None
                else:
                    with open(full_path) as f:
                        self._file_history_cache[(file_path, commit.commit_hash)] = f.read()
        return self._file_history_cache[(file_path, commit.commit_hash)]

    def iter_blame(self, repo_build_file: RepoBuildFile, commit: Commit) -> Generator[GitBlameRecord, None, None]:
        # build_file_rel_path = os.path.relpath(repo_build_file.build_file_path, self.datapath)
        build_file_contents = self.get_file_at(repo_build_file.build_file_rel_path, commit)
        if build_file_contents is None:
            return

        build_file_contents = io.StringIO(build_file_contents).readlines()
        build_file_contents = [line.rstrip("\r\n") for line in build_file_contents]

        repo = self._repo
        for blame in repo.blame_incremental(commit.commit_hash, file=repo_build_file.build_file_rel_path):
            blame_commit = repo.commit(blame.commit)

            for lineno in blame.linenos:
                yield GitBlameRecord(
                    index=lineno,
                    commit=blame_commit.hexsha,
                    commit_author=blame_commit.committer.email,
                    commit_timestamp=blame_commit.committed_datetime.astimezone(ZoneInfo("Zulu")),
                    buildFileLine=build_file_contents[lineno - 1]
                )

    def get_history(self, repo_build_file: RepoBuildFile, since: datetime.datetime | None) -> Generator[Commit, None, None]:
        # TODO: Use since param
        for commit in self._repo.iter_commits(all=True, paths=repo_build_file.build_file_rel_path):
            commit = Commit(
                commit_hash=commit.hexsha,
                commit_timestamp=commit.committed_datetime.astimezone(ZoneInfo("Zulu"))
            )

            if self.get_file_at(repo_build_file.build_file_rel_path, commit) is None:
                continue
            yield commit

    def get_sbom(self, repo_build_file: RepoBuildFile, commit: Commit) -> dict:
        with tempfile.TemporaryDirectory() as tmpdir:
            name = os.path.basename(self.datapath)
            repo_dir = os.path.join(tmpdir, name)
            full_path = os.path.join(repo_dir, repo_build_file.build_file_rel_path)

            os.makedirs(os.path.dirname(full_path), exist_ok=True)

            with open(full_path, "w") as f:
                f.write(self.get_file_at(repo_build_file.build_file_rel_path, commit))

            return super().get_sbom(full_path, source_name=repo_build_file.project_name)
        
    def checkout(self, head):
        self._repo.head.reference = head
        self._repo.head.reset(index=True, working_tree=True)
        
    @contextmanager
    def repo_at_commit(self, commit: Commit | str | None = None, reset_when_done=True):
        if reset_when_done:
            previous_head = self._repo.head.reference
            previous_branch = None if self._repo.head.is_detached else self._repo.active_branch
        else:
            previous_head = previous_branch = None

        # Checkout commit
        if isinstance(commit, Commit):
            self._repo.head.reference = self._repo.commit(commit.commit_hash)
        elif commit:
            self._repo.head.reference = commit
        self._repo.head.reset(index=True, working_tree=True)

        yield self._repo

        # Reset to whatever head was before
        if reset_when_done:
            self._repo.head.reference = previous_head
            self._repo.head.reset(index=True, working_tree=True)
            if previous_branch:
                self._repo.git.checkout(previous_branch)