import datetime
import io
import json
import logging
import os
import zipfile
from typing import List

from packageurl import PackageURL

from .api import ETLBundle
from .repo import GitRepo


LOG = logging.getLogger(__name__)


def purl_to_cache_key(package_url: PackageURL) -> str:
    purl = PackageURL(
        type=package_url.type,
        namespace=package_url.namespace,
        name=package_url.name,
        version=package_url.version,
    )
    return str(purl)


def process_repo(repo: GitRepo, purl_namespace: str, recurse: bool, since: datetime.datetime | None = None):
    # Discover build files in the target repository
    repo.discover_build_files(recurse)

    # Process all of the build files
    for repo_build_file in repo.buildfiles:
        for commit in repo.get_history(repo_build_file, since):
            project_file_path = os.path.join(repo_build_file.project_name, repo_build_file.build_file_rel_path)
            datasource_name = os.path.dirname(project_file_path).replace("/", "__")

            package_url = PackageURL(
                type="generic",
                namespace=purl_namespace,
                name=f"{datasource_name}::{repo_build_file.branch}",
                version=repo_build_file.build_file_type.PURL,
                qualifiers={
                    "commitHash": commit.commit_hash,
                    "commitDatetime": commit.commit_timestamp.isoformat()
                }
            )

            with io.BytesIO() as tf:
                # Create a zip file (in memory) with a directory for each commit. That directory
                # contains metadata.json, syft_sbom.json, and git_blame.json
                with zipfile.ZipFile(tf, mode="w") as zf:        
                    try:
                        metadata = repo.get_metadata(repo_build_file, commit)
                        zf.writestr(f"{commit.commit_hash}/metadata.json", json.dumps(metadata))
                    except:
                        LOG.error("error getting repo metadata for purl %s", package_url)
                        raise

                    try:
                        sbom = repo.get_sbom(repo_build_file, commit)
                        if not sbom:
                            LOG.error("error generating an sbom for purl %s", package_url)
                            continue
                        if not sbom["artifacts"]:
                            LOG.warning("no artifacts found in sbom for purl %s", package_url)
                            continue

                        zf.writestr(f"{commit.commit_hash}/syft_sbom.json", json.dumps(sbom))
                    except:
                        LOG.error("error getting sbom for purl %s", package_url)
                        raise

                    try:
                        git_blame = repo.get_blame(repo_build_file, commit)
                        zf.writestr(f"{commit.commit_hash}/git_blame.json", json.dumps(git_blame))
                    except:
                        LOG.error("error getting blame for purl %s", package_url)
                        raise
            
                # Reset pointer to start of in-memory file
                tf.seek(0)

                yield (
                    # Calculate the datasource PURL
                    package_url,

                    # Generate a filename for the archive
                    ETLBundle(
                        name=f"patchfox_data_{purl_namespace}_{metadata['eventDatetime']}.zip",
                        commitDatetime=commit.commit_timestamp,
                        file_object=tf
                    )
                )