"""
Alternative way of performing the collection and filtering of commit data, as short as possible.
Old saying to keep in mind: the best code is the unwritten code.
"""
import subprocess

import pandas as pd
import os
import git
from pydriller.git import Git
from tqdm import tqdm
import json


def get_extension_of_file(file):
    return os.path.splitext(os.path.basename(file))[1]


class ShellCommands:
    def __init__(self, working_directory: str):
        self.working_directory = working_directory

    def commits_modifying_file(self, filename):
        command = f"cd {self.working_directory} && git log --follow --format=%H {filename}"
        try:
            output = subprocess.check_output(
                command, stderr=subprocess.STDOUT, shell=True, timeout=3,
                universal_newlines=True)
        except subprocess.CalledProcessError:
            return None
        return output.split()

    def files_in_commit(self, commit):
        command = f"cd {self.working_directory} && git diff-tree --no-commit-id --name-only -r {commit}"
        try:
            output = subprocess.check_output(
                command, stderr=subprocess.STDOUT, shell=True, timeout=3,
                universal_newlines=True)
        except subprocess.CalledProcessError:
            return None
        return [x for x in output.split() if get_extension_of_file(x) in [".java"]]


class Repository:
    def __init__(self, name: str, url: str, cloning_location: str):
        self.name = name
        self.url = url
        self.cloning_location = cloning_location
        self.path = f"{self.cloning_location}/{self.name}"
        self.pydriller_repo = Git(self.path)
        self.shell_commands = ShellCommands(self.path)

    def clone(self):
        if os.path.isdir(self.path):
            return self
        git.Repo.clone_from(self.url, self.path)
        return self

    def files(self, allowed_extensions):
        all_files = self.pydriller_repo.files()
        return [file for file in all_files if get_extension_of_file(file) in allowed_extensions]

    def get_files_changed_with(self, file, allowed_extensions):
        files_changed_with_file = []
        # commits_touching_file = self.pydriller_repo.get_commits_modified_file(file)
        commits_touching_file = self.shell_commands.commits_modifying_file(file)
        for commit in commits_touching_file:
            files_in_commit =[f for f in self.shell_commands.files_in_commit(commit) if f != file]
            if 100 > len(files_in_commit) > 2:
                files_changed_with_file += files_in_commit
            # if commit != "":  # commit could be empty if the file only appeared once, in a merge commit
                # commit_object = self.pydriller_repo.get_commit(commit)
                # if 100 > len(commit_object.modified_files) > 2:
                #     for modified_file in commit_object.modified_files:
                #         # if get_extension_of_file(modified_file.filename) in allowed_extensions:
                #         #     files_changed_with_file.append(modified_file.filename)
                #         pass
                # pass
        return files_changed_with_file


def main():
    cloning_location = "../codebases"
    if not os.path.isdir(cloning_location):
        os.mkdir(cloning_location)

    data_output_location = "codebases-data"
    if not os.path.isdir(data_output_location):
        os.mkdir(data_output_location)

    repo_data = pd.read_csv("mazlami-codebases.csv")
    for repo_name, repo_link in zip(repo_data["codebase"], repo_data["repository_link"]):
        repository = Repository(repo_name, repo_link, cloning_location).clone()
        repository_files = repository.files([".java"])
        result = {}
        for file in tqdm(repository_files):
            shorter_filename = file.replace(f"/home/joaolourenco/Thesis/development/codebases/{repo_name}/", "")
            result[shorter_filename] = repository.get_files_changed_with(shorter_filename, [".java"])
        with open(f"codebases-data/{repo_name}/{repo_name}-commit-test.json", "w") as outfile:
            json.dump(result, sort_keys=True, indent=2, separators=(',', ': '), fp=outfile)
        exit()


if __name__ == "__main__":
    main()