#!/usr/bin/env python3

import subprocess
from collections import defaultdict
from pathlib import Path


def main():
    root = Path(__file__).parent.parent.parent
    reprepro_base_dir = root / "repo"
    packages = defaultdict(lambda: defaultdict(list))
    for group in ["core", "workstation"]:
        for deb in root.glob(f"{group}/*/*.deb"):
            distro = deb.parent.name
            if "-" in distro:
                distro, component = distro.split("-", 1)
            else:
                component = "main"
            packages[distro][component].append(deb)

    for distro in packages:
        for component, debs in packages[distro].items():
            subprocess.check_call(
                [
                    "reprepro",
                    "--basedir",
                    reprepro_base_dir,
                    "--outdir",
                    reprepro_base_dir / "public",
                    "--export=never",
                    "-C",
                    component,
                    "includedeb",
                    distro,
                    *debs,
                ],
                cwd=root,
            )


if __name__ == "__main__":
    main()
