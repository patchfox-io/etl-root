import json
import logging
import os
import subprocess
import tempfile


LOG = logging.getLogger(__name__)


class Syft:
    PATH_TO_SYFT = "/usr/local/bin/syft"

    @classmethod
    def get_sbom(cls, source, source_name=None, source_version=None):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = os.path.join(tmpdir, "syft_sbom.json")

            args = [
                cls.PATH_TO_SYFT,
                "-o",
                f"json={output_file}",
            ]
            
            # Add source name/version if provided
            if source_name:
                args.extend(["--source-name", source_name])
            if source_version:
                args.extend(["--source-version", source_version])
            
            # Enable Java enrichment for better Maven resolution
            args.extend(["--enrich", "java"])
            
            args.append(source)

            env = os.environ.copy()
            # Use local Maven repo and network for parent POM resolution
            env["SYFT_JAVA_USE_MAVEN_LOCAL_REPOSITORY"] = "true"
            env["SYFT_JAVA_USE_NETWORK"] = "true"

            try:
                subprocess.run(
                    args,
                    check=True,
                    timeout=10,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    env=env,
                )
            except subprocess.TimeoutExpired:
                return {}

            with open(output_file, "r") as f:
                return json.load(f)