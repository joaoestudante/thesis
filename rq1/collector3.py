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
        self.current_change_event_counter = None
        self.name = name
        self.url = url
        self.cloning_location = cloning_location
        self.path = f"{self.cloning_location}/{self.name}"
        self.pydriller_repo = None
        self.shell_commands = ShellCommands(self.path)
        self.authorized_extensions = [".java", ".py", ".rb"]

    def clone(self):
        if os.path.isdir(self.path):
            self.pydriller_repo = Git(self.path)
            return self
        os.mkdir(self.path)
        git.Repo.clone_from(self.url, self.path)
        self.pydriller_repo = Git(self.path)
        return self

    def get_full_history(self, n_commits=None):
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
            if n_commits is not None and i == n_commits:
                break
        return history

    def clear_deleted_files(self, full_history):
        print("Detecting deleted filenames")
        deleted_filenames = set()
        for event in full_history:
            for file in event.changed_diffs:
                if file.change_type == "D":
                    deleted_filenames.add(file.old_path)

        for file in deleted_filenames:
            for event in full_history:
                for entry in event.changed_diffs:
                    if entry.old_path == file or entry.new_path == file or entry.future_path == file:
                        event.delete_file(entry)

        return full_history

    def correct_renamed_files(self, history):
        print("Correcting renames")
        counter = 0
        cache = {}

        for event in history:
            for entry in event.changed_diffs:
                last_name = self.find_last_name(entry.future_path, counter, history, cache)
                if last_name != entry.future_path:
                    entry.future_path = last_name
            counter += 1
        return history

    def find_last_name(self, name, counter, history, cache):
        new_name = name
        in_cache = cache.get(name, "")
        if in_cache != "":
            return in_cache
        for i in range(counter, len(history)):
            event = history[i]
            for entry in event.changed_diffs:
                if entry.old_path == new_name and entry.old_path != entry.new_path:
                    new_name = entry.new_path
        cache[name] = new_name
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


    def get_logical_coupling(self, history_with_renames_fixed):
        result = defaultdict(list)

        start = history_with_renames_fixed[0].timestamp.replace(tzinfo=None)
        end = history_with_renames_fixed[-1].timestamp.replace(tzinfo=None)

        timestamps = pd.date_range(start, end, freq="H")
        events_grouped = []
        print("Grouping commits")
        start_counter = 0

        for i in range(1, len(timestamps)):
            events_to_consider = []
            start_date = timestamps[i-1]
            end_date = timestamps[i]
            for event in history_with_renames_fixed[start_counter:]:
                if start_date <= event.timestamp.replace(tzinfo=None) < end_date:
                    events_to_consider.append(event)
                    start_counter += 1

                if event.timestamp.replace(tzinfo=None) > end_date:  # any event after this will always be ignored
                    break
            if len(events_to_consider) > 0:
                events_grouped.append(events_to_consider)

        print("Constructing dict")
        for event_group in events_grouped:
            diffs = []
            for event in event_group:
                diffs += event.changed_diffs
            if len(diffs) >= 2:
                for entry in diffs:
                    new_change = diffs[:]
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

    repo_data = pd.read_csv("joao-codebases.csv")
    for repo_name, repo_link in zip(repo_data["codebase"], repo_data["repository_link"]):
        print("\nCHECKING " + repo_name)
        repository = Repository(repo_name, repo_link, cloning_location).clone()
        if os.path.isfile(f"files-changed/{repo_name}v3.pkl"):
            with open(f"files-changed/{repo_name}v3.pkl", "rb") as f:
                full_history = pickle.load(f)
        else:
            full_history = repository.get_full_history()
            with open(f"files-changed/{repo_name}v3.pkl", "wb") as h:
                pickle.dump(full_history, h)

        if os.path.isfile(f"files-changed/{repo_name}-clean-history.pkl"):
            with open(f"files-changed/{repo_name}-clean-history.pkl", "rb") as f:
                cleaned_history = pickle.load(f)
        else:
            history_with_renames_fixed = repository.correct_renamed_files(full_history)
            cleaned_history = repository.clear_deleted_files(history_with_renames_fixed)
            with open(f"files-changed/{repo_name}-clean-history.pkl", "wb") as f:
                pickle.dump(cleaned_history, f)

        logical_coupling_result = repository.get_logical_coupling(cleaned_history)
        authors_result = get_authors_result(cleaned_history)
        # repository.check_files(logical_coupling_result)

        if not os.path.isdir(f"codebases-data/{repo_name}/"):
            os.mkdir(f"codebases-data/{repo_name}/")

        with open(f"codebases-data/{repo_name}/{repo_name}-commit-v3.json", "w") as outfile:
            json.dump(logical_coupling_result, sort_keys=True, indent=2, separators=(',', ': '), fp=outfile)
        with open(f"codebases-data/{repo_name}/{repo_name}-author-v3.json", "w") as outfile:
            json.dump(authors_result, sort_keys=True, indent=2, separators=(',', ': '), fp=outfile)

        print("Saved.")


if __name__ == "__main__":
    main()
