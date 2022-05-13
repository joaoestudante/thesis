from __future__ import annotations

import json
import os
import time

import pandas as pd
from rich import print

import itertools
from collections import defaultdict

from collector.history import History
from collector.repository import Repository
from helpers.constants import Constants


def findsubsets(s: set, m: int):
    return set(itertools.permutations(s, m))


def get_logical_couplings(history: History):
    couplings = []
    for bottom_range in range(history.first_ts, history.last_ts, Constants.group_commits_interval):
        top_range = bottom_range + Constants.group_commits_interval
        filenames = set(history.get_filenames_in_range(bottom_range, top_range))
        couplings += findsubsets(filenames, 2)

    return pd.DataFrame(couplings, columns=['first_file', 'second_file'])


def coupling_to_json(logical_coupling, history: History, repo: Repository, entities_only: bool) -> dict:
    """
    Organizes pairs that appear together, and stores the information in a dictionary ready to be saved as a
    .json file.
    The dictionary has the following format:
    ```
    {
       'A' : [B, C, C],
       'B' : [A, C],
       'Z' : [F, G],
       ...
    }
    ```
    It can be read as: File 'A' has changed once with file B, and twice with file C.
    """

    logical_coupling_data = defaultdict(list)
    if entities_only:
        filenames = repo.entity_full_names
    else:
        filenames = repo.unique_filenames

    for file in filenames:
        changed_with_this_file = logical_coupling.loc[logical_coupling['first_file'] == file]['second_file']
        for file2 in list(changed_with_this_file):
            logical_coupling_data[repo.get_file_id(file)].append(int(repo.get_file_id(file2)))

    # Any file not in the logical coupling data? Add it... with 0 couplings to others
    # This can happen if a file changed alone, or only with non .java files, or in refactors, or all of them. Either
    # way, for our purposes, it has not changed with other files.
    for file in filenames:
        file_id = repo.get_file_id(file)
        if file_id not in logical_coupling_data:
            logical_coupling_data[file_id] = []

    return logical_coupling_data


def authors_to_json(history: History, repo: Repository):
    author_data = {}
    filenames = repo.unique_filenames
    for file in filenames:
        file_authors = history.get_file_authors(file)
        author_data[repo.get_file_id(file)] = list(set(file_authors))
    return author_data


def collect_data(codebases):
    for i, codebase in enumerate(codebases):
        t0 = time.time()
        print("")
        print(f"[underline]{codebase}[/underline] [{i + 1}/{len(codebases)}]")

        print(":white_circle: Parsing history")
        codebase_repo = Repository(codebase)
        history = codebase_repo.cleanup_history()
        entities_history = history.get_entities_only_copy(codebase_repo.entity_full_names)

        print(":white_circle: Getting couplings")
        print("  :white_circle: All files")
        all_logical_coupling = get_logical_couplings(history)

        print("  :white_circle: Entities")
        entities_logical_couplings = get_logical_couplings(entities_history)

        print(":white_circle: Converting to JSON")
        print("  :white_circle: All files")
        all_files_logical_coupling_json = coupling_to_json(all_logical_coupling, history, codebase_repo, False)
        all_files_authors_json = authors_to_json(history, codebase_repo)

        print("  :white_circle: Entities")
        entities_logical_coupling_json = coupling_to_json(entities_logical_couplings, entities_history, codebase_repo, True)
        entities_authors_json = authors_to_json(entities_history, codebase_repo)

        print(":white_circle: Writing")
        write_jsons(all_files_logical_coupling_json, entities_logical_coupling_json,
                    all_files_authors_json, entities_authors_json, codebase)

        t1 = time.time()
        print(f"[underline]Done in {round(t1-t0, 2)} seconds.[/underline]")


def write_jsons(all_files_logical_coupling_json, entities_logical_coupling_json, all_files_authors_json,
                entities_authors_json, codebase):
    with open(f"{Constants.codebases_data_output_directory}/{codebase}/{codebase}_commit_all.json", "w") as f:
        json.dump(all_files_logical_coupling_json, f)
    with open(f"{Constants.codebases_data_output_directory}/{codebase}/{codebase}_commit_entities.json", "w") as f:
        json.dump(entities_logical_coupling_json, f)
    with open(f"{Constants.codebases_data_output_directory}/{codebase}/{codebase}_author_all.json", "w") as f:
        json.dump(all_files_authors_json, f)
    with open(f"{Constants.codebases_data_output_directory}/{codebase}/{codebase}_author_entities.json", "w") as f:
        json.dump(entities_authors_json, f)
