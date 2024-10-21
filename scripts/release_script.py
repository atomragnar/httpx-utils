import argparse
import logging
import os
import re
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import git
from msgspec.toml import decode as toml_decode
from msgspec.toml import encode as toml_encode

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


## argsparsing


class ActionRegistry:
    def __init__(self):
        self.actions = {}

    def register(self, name, func):
        self.actions[name] = func

    def run(self, parser_args, *args, **kwargs):
        if parser_args.action in self.actions:
            return self.actions[parser_args.action](parser_args, *args, **kwargs)
        else:
            raise ValueError(f"Action '{parser_args.action}' not found")


action_registry = ActionRegistry()


def action(name):
    def decorator(func):
        action_registry.register(name, func)
        return func

    return decorator


class ArgumentParser:
    def __init__(self):
        self.parser = argparse.ArgumentParser(description="Command line interface")
        self.parser.add_argument("action", type=str, help="The action to perform")
        self.parser.add_argument(
            "args", nargs=argparse.REMAINDER, help="Arguments for the action"
        )

    def parse_and_run(self):
        parser_args = self.parser.parse_args()
        try:
            action_registry.run(parser_args=parser_args)
        except ValueError as e:
            print(e)


## helper functions


def _remove_duplicates(package_list: List[str]) -> List[str]:
    seen: set[str] = set()
    unique_packages: List[str] = []
    for pkg in package_list:
        if pkg not in seen:
            unique_packages.append(pkg)
            seen.add(pkg)
    return unique_packages


def _recurse_pkgs(packages: List[str], src_dir: str, parent_path: str) -> None:
    for entry in os.scandir(src_dir):
        if entry.is_dir():
            for subentry in os.scandir(entry.path):
                if subentry.is_file():
                    if subentry.name == "__init__.py":
                        packages.append(f"{parent_path}/{entry.name}")
                else:
                    _recurse_pkgs(
                        packages,
                        src_dir=entry.path,
                        parent_path=f"{parent_path}/{entry.name}",
                    )


def _pkgs_in_src(project_path: str) -> List[str]:
    src_dir = f"{project_path}/src"
    pkgs: List[str] = []
    _recurse_pkgs(pkgs, src_dir, parent_path="src")
    return pkgs


class SemVerKind(Enum):
    MAJOR = "major"
    MINOR = "minor"
    PATCH = "patch"


class Pyproject:
    _data: Any
    _file_path: str

    def __init__(self, file_path: Optional[str] = None):
        if file_path is None:
            file_path = os.path.dirname(__file__)
            self._file_path = f"{file_path}/pyproject.toml"
        else:
            self._file_path = file_path
        with open(self._file_path, "rb") as file:
            data = file.read()
        self._data = toml_decode(buf=data, type=Dict)

    @property
    def version(self) -> str:
        return self._data["project"]["version"]

    @property
    def project_dir(self) -> str:
        return os.path.dirname(self._file_path)

    def git_tag_version(self) -> str:
        return f"v{self.version}"

    def set_version(self, version: str) -> None:
        self._data["project"]["version"] = version

    @property
    def dependencies(self) -> Tuple[Dict[str, str], Dict[str, str]]:
        deps = self._data["project"]["dependencies"]
        dev_deps = self._data["tool"]["rye"]["dev-dependencies"]
        return deps, dev_deps

    def log_dependencies(self):
        deps, dev_deps = self.dependencies
        dependencies = "\nDependencies:\n"
        for dep in deps:
            dep_split = dep.split(">=")
            dependencies = f"{dependencies}\n{dep_split[0]}=={dep_split[1]}"

        dependencies = f"{dependencies}\n\nDev Dependencies:\n"
        for dep in dev_deps:
            dep_split = dep.split(">=")
            dependencies = f"{dependencies}\n{dep_split[0]}=={dep_split[1]}"
        logger.info(dependencies)

    @property
    def packages(self) -> List[str]:
        return self._data["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"]

    def increment_version(self, ver_type: SemVerKind = SemVerKind.PATCH) -> None:
        version = self.version
        pattern = r"(\d+)\.(\d+)\.(\d+)"
        match = re.match(pattern, version)
        if not match:
            raise ValueError(f"Invalid tag format: {version}")

        major, minor, patch = map(int, match.groups())
        if ver_type == SemVerKind.MAJOR:
            major += 1
            minor = 0
            patch = 0
        elif ver_type == SemVerKind.MINOR:
            minor += 1
            patch = 0
        elif ver_type == SemVerKind.PATCH:
            patch += 1

        new_version = f"{major}.{minor}.{patch}"
        logger.info(f"Incrementing version from {version} to {new_version}")
        self.set_version(new_version)

    def add_package(self, new_package: str | List[str]) -> None:
        pkgs = self.packages
        if isinstance(new_package, str):
            pkgs.append(new_package)
        else:
            for p in new_package:
                pkgs.append(p)
        self._data["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"] = (
            _remove_duplicates(pkgs)
        )

    def write(self) -> None:
        binary_data = toml_encode(self._data)
        with open(self._file_path, "wb") as file:
            file.write(binary_data)


# git utils


class GitUtils:
    repo: git.Repo

    def __init__(self, repo_path: str):
        self.repo = git.Repo(repo_path)

    def get_current_branch(self) -> str:
        return self.repo.active_branch.name

    def fetch_tags(self) -> None:
        self.repo.git.fetch("--tags")

    def get_latest_tag(self) -> str | None:
        tags = sorted(self.repo.tags, key=lambda t: t.commit.committed_datetime)
        return tags[-1] if tags else None

    def increment_version(self):
        latest_tag = self.get_latest_tag()
        latest_tag_name = latest_tag.name if latest_tag else "v0.0.0"
        pattern = r"v(\d+)\.(\d+)\.(\d+)"
        match = re.match(pattern, latest_tag_name)
        if not match:
            raise ValueError(f"Invalid tag format: {latest_tag}")

        major, minor, patch = map(int, match.groups())
        patch += 1
        return f"v{major}.{minor}.{patch}"

    def tag_and_push(self, new_tag) -> None:
        self.repo.create_tag(new_tag)
        origin = self.repo.remotes.origin
        origin.push(new_tag)


# helpers for actions


def _get_pyproject() -> Pyproject:
    project_dir = __file__.split("scripts")[0]
    if not project_dir:
        raise ValueError("Project directory not found")
    pyproject = Pyproject(file_path=f"{project_dir}/pyproject.toml")
    return pyproject


# actions


@action("update-pyproject")
def update_pyproject(parser_args: argparse.Namespace) -> None:
    pyproject = _get_pyproject()
    pkgs = _pkgs_in_src(pyproject.project_dir)
    pyproject.add_package(new_package=pkgs)
    pyproject.write()


@action("update-pyproject-version")
def update_version(parser_args: argparse.Namespace) -> None:
    logger.info(f"args {parser_args}")
    py = _get_pyproject()
    logger.info(f"Current pyproject version: {py.version}")
    git = GitUtils(repo_path=py.project_dir)
    latest_tag = git.get_latest_tag()
    if latest_tag is None:
        return

    latest_tag = str(latest_tag)
    # todo make a semver kind comparison

    if latest_tag == py.git_tag_version():
        ver_type = SemVerKind.PATCH
        if len(parser_args.args) > 0:
            type_arg = parser_args.args[0]
            if type_arg == "--major":
                ver_type = SemVerKind.MAJOR
                logger.info("Major version update")
            elif type_arg == "--minor":
                ver_type = SemVerKind.MINOR
                logger.info("Minor version update")
        py = _get_pyproject()
        py.increment_version(ver_type)
        new_tag = py.version
        py.write()
        git.repo.git.add(py._file_path)
        git.repo.index.commit(f"chore: bump pyproject.toml version to {new_tag}")
        # token = os.getenv("GITHUB_SECRETS_TOKEN")
        # if not token:
        #     logger.error("Github secrets token not found")
        #     raise ValueError("Github secrets token not found")
        origin = git.repo.remotes.origin
        origin.push()
    else:
        logger.info("No new version to update")


@action("test-version")
def test_update_version(parser_args: argparse.Namespace) -> None:
    logger.info(f"args {parser_args}")
    ver_type = SemVerKind.PATCH
    if len(parser_args.args) > 0:
        type_arg = parser_args.args[0]
        if type_arg == "--major":
            ver_type = SemVerKind.MAJOR
            logger.info("Major version update")
        elif type_arg == "--minor":
            ver_type = SemVerKind.MINOR
            logger.info("Minor version update")
    py = _get_pyproject()
    py.increment_version(ver_type)
    py.write()


@action("release-tag")
def release_tag(parser_args: argparse.Namespace) -> None:
    py = _get_pyproject()
    print(py.git_tag_version())


@action("git-test")
def git_test(parser_args: argparse.Namespace) -> None:
    py = _get_pyproject()
    logger.info("running git-test")

    logger.info("running git-test")
    git = GitUtils(repo_path=py.project_dir)
    git.fetch_tags()
    latest_tag = git.get_latest_tag()
    py_git_tag = py.git_tag_version()
    latest_tag = str(latest_tag)
    bol = latest_tag == py_git_tag
    logger.info(f"Pyproject comparison: {bol}")
    logger.info(f"Pyproject version: {py_git_tag} - {len(py_git_tag)}")

    logger.info(f"Latest tag: {latest_tag} - {len(latest_tag)}")
    branch = git.get_current_branch()
    logger.info(f"Current branch: {branch}")


@action("deps")
def show_deps(parser_args: argparse.Namespace) -> None:
    py = Pyproject()
    py.log_dependencies()


def main() -> int:
    ArgumentParser().parse_and_run()
    return 0


if __name__ == "__main__":
    main()
