#!/usr/bin/env python3

import glob
import os
import shutil
import subprocess
from datetime import datetime, UTC
from pathlib import Path

from debian import deb822
from jinja2 import Environment, FileSystemLoader, select_autoescape


def format_size(size_bytes):
    """Convert size in bytes to human-readable format"""
    if size_bytes < 1024:
        return f"{size_bytes}B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f}KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f}MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f}GB"


def commit_info(git_root: Path, codename: str, component: str, pkginfo) -> (str, str):
    # Calculate the original filename in the core or workstation folders
    if codename in ["noble", "focal"]:
        group = "core"
    else:
        group = "workstation"
    if component == "main":
        folder = codename
    else:
        folder = f"{codename}-{component}"
    deb_path = git_root / group / folder / Path(pkginfo["Filename"]).name
    # Find the commit in which the file was added
    output = subprocess.check_output(
        [
            "git",
            "log",
            "--diff-filter=A",
            "--follow",
            "--format=%H|%ai",
            "--",
            str(deb_path),
        ],
        text=True,
    ).strip()
    if not output:
        raise RuntimeError(f"Error: No commit found for {deb_path}")
    commit, date = output.split("|")
    # Git timestamps are in commiter time, convert to UTC and remove the now useless +00:00 offset
    date = str(datetime.fromisoformat(date).astimezone(UTC)).split("+")[0]
    return commit, date


def parse_apt_repo(git_root: Path, repo_base_path: Path):
    """Parse APT repository structure and extract package information"""
    result = {}

    # Find all dists directories
    dists_path = repo_base_path / "dists"
    if not dists_path.exists():
        raise RuntimeError(f"Error: {dists_path} does not exist")

    # Iterate through each codename (e.g., bullseye, bookworm)
    for codename_dir in sorted(dists_path.iterdir()):
        if not codename_dir.is_dir():
            continue

        # Parse Release file to get distribution information
        release_file = codename_dir / "Release"
        if not release_file.exists():
            raise RuntimeError(f"Error: No Release file found for {codename_dir.name}")

        result[codename_dir.name] = {"components": {}}

        # Find all components (e.g., main, contrib, non-free)
        for component_dir in sorted(codename_dir.iterdir()):
            if not component_dir.is_dir():
                continue

            result[codename_dir.name]["components"][component_dir.name] = []

            # Find all binary package indexes
            # Note: Using glob.glob here since Path.glob doesn't support **/ in all versions
            binary_paths = glob.glob(str(component_dir / "binary-*" / "Packages"))
            for packages_file in sorted(binary_paths):
                packages_path = Path(packages_file)

                with packages_path.open("rb") as f:
                    for pkg in deb822.Packages.iter_paragraphs(f):
                        commit, date = commit_info(
                            git_root, codename_dir.name, component_dir.name, pkg
                        )
                        # Extract filename for download link
                        filename = pkg["Filename"]
                        # Construct the download link relative to the repo base
                        download_link = str(Path("/") / filename)

                        package_info = {
                            "name": pkg["Package"],
                            "version": pkg["Version"],
                            "size": format_size(int(pkg["Size"])),
                            "description": pkg["Description"].split("\n")[0],
                            "architecture": pkg["Architecture"],
                            "download_link": download_link,
                            "filename": Path(filename).name,
                            "commit": commit,
                            "date": date,
                        }
                        result[codename_dir.name]["components"][
                            component_dir.name
                        ].append(package_info)

    if not result:
        raise RuntimeError("Error: No packages found in the repository")
    return result


def generate_html(repo_data):
    """Generate HTML output using Jinja2 templating with autoescaping enabled"""

    # Create template with autoescaping enabled
    env = Environment(
        loader=FileSystemLoader(Path(__file__).parent),
        autoescape=select_autoescape(["html", "xml"]),
    )

    # Load the template from file
    template = env.get_template("index.html.j2")
    return template.render(
        repo_data=repo_data,
        title="SecureDrop APT Testing Repository",
        # Set by GitHub Actions
        repo_name=os.environ["GITHUB_REPOSITORY"],
    )


def main():
    git_root = Path(__file__).parent.parent.parent
    repo_path = git_root / "repo/public"
    repo_data = parse_apt_repo(git_root, repo_path)
    html_output = generate_html(repo_data)
    (repo_path / "index.html").write_text(html_output)
    shutil.copyfile(Path(__file__).parent / "styles.css", repo_path / "styles.css")


if __name__ == "__main__":
    main()
