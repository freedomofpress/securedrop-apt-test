#!/usr/bin/env python3

import glob
import shutil
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


def parse_apt_repo(repo_path):
    """Parse APT repository structure and extract package information"""
    result = {}
    repo_base_path = Path(repo_path)

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
    return template.render(repo_data=repo_data, title="SecureDrop APT Testing Repository")


def main():
    repo_path = Path(__file__).parent.parent.parent / "repo/public"
    repo_data = parse_apt_repo(repo_path)
    html_output = generate_html(repo_data)
    (repo_path / "index.html").write_text(html_output)
    shutil.copyfile(Path(__file__).parent / "styles.css", repo_path / "styles.css")


if __name__ == "__main__":
    main()
