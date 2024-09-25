import argparse
import logging
import os
import re
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Tuple, Type

import git
from fancy_log import FancyLogger
from msgspec.toml import decode as toml_decode
from msgspec.toml import encode as toml_encode

logger = FancyLogger.get_logger(__name__)
logger.setLevel(logging.DEBUG)

project_dir = __file__.split("scripts")[0]


class SemVerKind(Enum):
    MAJOR = "major"
    MINOR = "minor"
    PATCH = "patch"


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


class TomlDecoder:
    @staticmethod
    def decode(data: bytes, type: Type = object) -> Type:
        return toml_decode(buf=data, type=type)

    @staticmethod
    def encode(data: Iterable[object]) -> bytes:
        return toml_encode(data)

    @staticmethod
    def read_and_decode(file_path: str, type: Type = object) -> Type:
        with open(file_path, "rb") as file:
            data = file.read()
            return TomlDecoder.decode(data, type)

    @staticmethod
    def encode_and_write(file_path: str, data: Iterable[object]):
        binary_data = TomlDecoder.encode(data)
        with open(file_path, "wb") as file:
            file.write(binary_data)

    @staticmethod
    def pyproject(file_path: str = f"{project_dir}/pyproject.toml") -> Any:
        return TomlDecoder.read_and_decode(file_path, Dict)


def _remove_duplicates(package_list: List[str]) -> List[str]:
    seen = set()
    unique_packages = []
    for pkg in package_list:
        if pkg not in seen:
            unique_packages.append(pkg)
            seen.add(pkg)
    return unique_packages


def _dependency_check():
    pass


class Pyproject:
    _data: Any
    _file_path: str

    def __init__(self, file_path: Optional[str] = None):
        if file_path is None:
            self._file_path = f"{project_dir}/pyproject.toml"
        else:
            self._file_path = file_path
        self._data = TomlDecoder.read_and_decode(self._file_path, Dict)

    @property
    def version(self) -> str:
        return self._data["project"]["version"]

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
        TomlDecoder.encode_and_write(file_path=self._file_path, data=self._data)


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


def _pkgs_in_src() -> List[str]:
    src_dir = f"{project_dir}/src"
    pkgs = []
    _recurse_pkgs(pkgs, src_dir, parent_path="src")
    return pkgs


def _increment_version(tag):
    pattern = r"v(\d+)\.(\d+)\.(\d+)"
    match = re.match(pattern, tag)
    if not match:
        raise ValueError(f"Invalid tag format: {tag}")

    major, minor, patch = map(int, match.groups())
    patch += 1
    return f"v{major}.{minor}.{patch}"


class GitUtils:
    repo: git.Repo

    def __init__(self, repo_path: str = project_dir):
        self.repo = git.Repo(repo_path)

    def get_current_branch(self):
        return self.repo.active_branch.name

    def fetch_tags(self):
        self.repo.git.fetch("--tags")

    def get_latest_tag(self):
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

    def tag_and_push(self, new_tag):
        self.repo.create_tag(new_tag)
        origin = self.repo.remotes.origin
        origin.push(new_tag)


@action("update-pyproject")
def update_pyproject(parser_args: argparse.Namespace) -> None:
    pyproject = Pyproject()
    pkgs = _pkgs_in_src()
    pyproject.add_package(new_package=pkgs)
    pyproject.write()


@action("patch-version")
def update_version(parser_args: argparse.Namespace) -> None:
    py = Pyproject()
    logger.info(f"Current version: {py.version}")
    git = GitUtils()
    latest_tag = git.get_latest_tag()
    if latest_tag is None:
        new_tag = f"v{py.version}"
        git.tag_and_push(new_tag)
        return
    py.increment_version()
    new_tag = f"{py.version}"
    git.tag_and_push(new_tag)
    py.write()


@action("git-test")
def git_test(parser_args: argparse.Namespace) -> None:
    py = Pyproject()
    py.increment_version()
    git = GitUtils()
    git.fetch_tags()
    latest_tag = git.get_latest_tag()
    logger.info(f"Latest tag: {latest_tag}")
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
