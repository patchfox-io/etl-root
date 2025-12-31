import json
import logging
import os
import subprocess
import tempfile


LOG = logging.getLogger(__name__)


class Syft:
    PATH_TO_SYFT = "/usr/local/bin/syft"

    @classmethod
    def get_sbom(cls, source):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = os.path.join(tmpdir, "syft_sbom.json")

            args = [
                cls.PATH_TO_SYFT,
                "-o",
                f"json={output_file}",
                source,
            ]

            try:
                subprocess.run(
                    args,
                    check=True,
                    timeout=10,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except subprocess.TimeoutExpired:
                return {}

            with open(output_file, "r") as f:
                return json.load(f)