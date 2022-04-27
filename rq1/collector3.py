"""
Alternative way of performing the collection and filtering of commit data, as short as possible.
Old saying to keep in mind: the best code is the unwritten code.
"""
import pickle
import subprocess
from collections import defaultdict

import pandas as pd
import os
import git
from pydriller.git import Git
from tqdm import tqdm
import json


def get_extension_of_file(file):
    return os.path.splitext(os.path.basename(file))[1]


class ChangeEvent:
    def __init__(self, diffs, timestamp, author, commit_hash):
        self.changed_diffs = diffs
        self.timestamp = timestamp
        self.author = author
        self.commit_hash = commit_hash

    def delete_file(self, diff):
        self.changed_diffs.remove(diff)


    def __repr__(self):
        return f"[{self.commit_hash[:7]}]: {len(self.changed_diffs)} files, committed at {self.timestamp} by {self.author}"


class ChangedFile:
    def __init__(self, old_path, new_path, change_type):
        self.old_path = old_path
        self.new_path = new_path
        self.change_type = change_type
        self.future_path = self.new_path

    def __repr__(self):
        if self.new_path != "":
            return f"[{self.change_type}] {self.old_path} => {self.new_path}"
        return f"[{self.change_type}] {self.old_path}"


class ShellCommands:
    def __init__(self, working_directory: str):
        self.working_directory = working_directory

    def get_files_changed(self, commit_hash):
        command = f"cd {self.working_directory} && git diff --name-status {commit_hash}^ {commit_hash} --root " \
                  f"--find-renames=30% "
        try:
            output = subprocess.check_output(
                command, stderr=subprocess.STDOUT, shell=True, timeout=3,
                universal_newlines=True)
        except subprocess.CalledProcessError:
            # This exception occurs when the given commit hash corresponds to a commit with no parents.
            # Such a situation is normal for the first commit, but can also rarely happen in the middle of the history.
            # When it does happen, we use a similar command that compares the commit with a special Git hash that is
            # meant to indicate an empty tree.
            lines = os.popen(f"cd {self.working_directory} && git diff --name-status "
                             f"4b825dc642cb6eb9a060e54bf8d69288fbee4904 {commit_hash}").readlines()
        else:
            lines = output.split("\n")[:-1]
            if "rename detection" in output:
                # FIXME: We should probably do something smarter here. Refer to issue #1 on GitHub.
                print("Skipped! Too many files in commit...")
                print("Actual output is: ")
                print(output)
                return []
        return lines


class Repository:
    def __init__(self, name: str, url: str, cloning_location: str):
        self.name = name
        self.url = url
        self.cloning_location = cloning_location
        self.path = f"{self.cloning_location}/{self.name}"
        self.pydriller_repo = Git(self.path)
        self.shell_commands = ShellCommands(self.path)
        self.authorized_extensions = [".java", ".py", ".rb"]

    def clone(self):
        if os.path.isdir(self.path):
            return self
        git.Repo.clone_from(self.url, self.path)
        return self

    def get_full_history(self):
        all_commits = list(self.pydriller_repo.get_list_commits())
        history = []
        print("Parsing all commits")
        for i in tqdm(range(len(all_commits))):
            commit = all_commits[i]
            files = self.shell_commands.get_files_changed(commit.hash)
            parsed_files = []
            for file in files:
                if get_extension_of_file(file) in self.authorized_extensions:
                    split_file = file.split()
                    if len(split_file) == 3:  # happens only on renames
                        change_type = split_file[0]
                        old_path = split_file[1]
                        new_path = split_file[2]
                    else:
                        change_type = split_file[0]
                        old_path = split_file[1]
                        new_path = old_path
                    parsed_files.append(ChangedFile(old_path, new_path, change_type))
            if len(parsed_files) > 0:
                history.append(ChangeEvent(parsed_files, commit.committer_date, commit.author.email, commit.hash))
        return history

    def clear_deleted_files(self, full_history):
        print("Detecting deleted filenames")
        deleted_filenames = set()
        for event in tqdm(full_history):
            for file in event.changed_diffs:
                if file.change_type == "D":
                    deleted_filenames.add(file.old_path)
        print(f"{len(deleted_filenames)} were deleted in the history. Clearing them.")
        # If a file is renamed, this will only delete the latest rename. But the previous ones should also be deleted...
        # Or maybe not? If they should, we can basically reverse the find_last_name, by searching from the commit to 0,
        # gathering all files, and deleting at the end
        for file in deleted_filenames:
            for event in full_history:
                for entry in event.changed_diffs:
                    if entry.old_path == file or entry.new_path == file or entry.future_path == file:
                        event.delete_file(entry)
        print("Cleared.")
        return full_history

    def correct_renamed_files(self, history):
        print("Correcting renames")
        counter = 0

        for event in history:
            for entry in event.changed_diffs:
                last_name = self.find_last_name(entry.future_path, counter, history)
                if last_name != entry.future_path:
                    entry.future_path = last_name
            counter += 1
        return history

    def find_last_name(self, name, counter, history):
        new_name = name
        for i in range(counter, len(history)):
            event = history[i]
            for entry in event.changed_diffs:
                if entry.old_path == new_name and entry.old_path != entry.new_path:
                    new_name = entry.new_path
        # print(f"{name} has changed to {new_name}")
        return new_name

    def check_files(self, logical_coupling_result):
        java_files_list = [file for file in self.pydriller_repo.files() if get_extension_of_file(file) in self.authorized_extensions]
        files_gathered = list(logical_coupling_result.keys())
        for file in java_files_list:
            if file.replace(f"/home/joaolourenco/Thesis/development/codebases/{self.name}/", "") not in files_gathered:
                print(f"{file} is in repo, but not in dict")
        for file in files_gathered:
            if f"/home/joaolourenco/Thesis/development/codebases/{self.name}/{file}" not in java_files_list:
                print(f"{file} is in dict, but not in repo")


def get_logical_coupling(history_with_renames_fixed):
    result = defaultdict(list)

    for event in history_with_renames_fixed:
        if len(event.changed_diffs) >= 2:
            for entry in event.changed_diffs:
                new_change = event.changed_diffs[:]
                new_change.remove(entry)
                result[entry.future_path] += [e.future_path for e in new_change]
    return result


def get_authors_result(cleaned_history):
    result = defaultdict(list)
    for event in cleaned_history:
        for entry in event.changed_diffs:
            result[entry.future_path] += [event.author]
    return result


def main():
    cloning_location = "../codebases"
    if not os.path.isdir(cloning_location):
        os.mkdir(cloning_location)

    data_output_location = "codebases-data"
    if not os.path.isdir(data_output_location):
        os.mkdir(data_output_location)

    repo_data = pd.read_csv("mazlami-codebases.csv")
    for repo_name, repo_link in zip(repo_data["codebase"], repo_data["repository_link"]):
        print("CHECKING " + repo_name)
        repository = Repository(repo_name, repo_link, cloning_location).clone()
        # if os.path.isfile(f"files-changed/{repo_name}v3.pkl"):
        #     with open(f"files-changed/{repo_name}v3.pkl", "rb") as f:
        #         full_history = pickle.load(f)
        # else:
        full_history = repository.get_full_history()
        with open(f"files-changed/{repo_name}v3.pkl", "wb") as h:
            pickle.dump(full_history, h)
        history_with_renames_fixed = repository.correct_renamed_files(full_history)
        cleaned_history = repository.clear_deleted_files(history_with_renames_fixed)
        logical_coupling_result = get_logical_coupling(cleaned_history)
        authors_result = get_authors_result(cleaned_history)
        repository.check_files(logical_coupling_result)
        with open(f"codebases-data/{repo_name}/{repo_name}-commit-v3.json", "w") as outfile:
            json.dump(logical_coupling_result, sort_keys=True, indent=2, separators=(',', ': '), fp=outfile)
        with open(f"codebases-data/{repo_name}/{repo_name}-author-v3.json", "w") as outfile:
            json.dump(authors_result, sort_keys=True, indent=2, separators=(',', ': '), fp=outfile)


if __name__ == "__main__":
    main()