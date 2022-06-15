"""
A mixed collection strategy, where the static analysis data influences the commits.

The algorithm is like so:
- Retrieve, parse, fix the history and store it in a dataframe.
- Convert the dataframe into Commit objects, but store only the entities.
- For each functionality:
    * For each commit:
        + Does it have at least two entities from the functionality trace? Then, create a new commit with those entities
- Convert the "new" commits back into a dataframe, with the same format as before
- Compute the couplings using this custom history as if it was the original history.
"""
import json

from rich import print

from collector.repository import Repository
from helpers.constants import Constants


class Functionality:
    def __init__(self, entities_ids_accessed, name):
        self.entities_ids_accessed = entities_ids_accessed
        self.name = name

    def __str__(self):
        return f"{self.name} - {len(self.entities_ids_accessed)} entities"

    def __repr__(self):
        return self.__str__()

    def get_entities_in_commit(self, commit):
        return []


class Commit:
    def __init__(self, commit_hash, commit_data):
        self.commit_hash = commit_hash
        self.commit_data = commit_data


def parse_functionalities(static_analysis_file_path):
    functionalities = []
    with open(static_analysis_file_path, "r") as f:
        data = json.load(f)
    for controller in data:
        accesses = data[controller]["t"][0]["a"]
        entities_ids = set()
        for access in accesses:
            entities_ids.add(access[1])
        if len(entities_ids) > 1:
            functionalities.append(Functionality(entities_ids, controller))
    return functionalities


def get_commits_from_history(history):
    commits = []
    for commit_hash, commit_data in history.commits():
        commits.append(Commit(commit_hash, commit_data))
    return commits


def increment_hash(commit_hash):
    # keep track of a hash hash table, where we increment a hash by 1 so we know which commit it sort of belongs to
    # but we still keep it unique hopefully. may not work.
    pass


def get_adapted_history(functionalities, commits):
    new_commit_list = []
    for functionality in functionalities:
        for commit in commits:
            entities_from_functionality_in_commit = functionality.get_entities_in_commit(commit)
            if len(entities_from_functionality_in_commit) > 1:
                new_commit_list.append(Commit(
                    increment_hash(commit.commit_hash),
                    entities_from_functionality_in_commit
                ))
    # Convert the commits to DF: basically rbind them all


def collect(codebases):
    for codebase in codebases:
        codebase_repo = Repository(codebase)
        cutoff_value = 100  # Commits with 5 or more files are ignored
        history = codebase_repo.cleanup_history(cutoff_value)

        functionalities = parse_functionalities(f"{Constants.codebases_data_output_directory}/{codebase}/{codebase}.json")
        commits = get_commits_from_history(history)

        adapted_history = get_adapted_history(functionalities, commits)

collect(["quizzes-tutor"])
