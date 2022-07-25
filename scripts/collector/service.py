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


def update_coupling(file, file_coupled, couplings):
    if file in couplings:
        if file_coupled in couplings[file]:
            couplings[file][file_coupled] += 1
        else:
            couplings[file][file_coupled] = 1
        couplings[file]["total_commits"] += 1
    else:
        couplings[file] = {
            file_coupled: 1,
            "total_commits": 1
        }


def get_logical_couplings(history: History, repo: Repository):
    couplings = []
    logical_coupling = {}
    for bottom_range in range(history.first_ts, history.last_ts, Constants.group_commits_interval):
        top_range = bottom_range + Constants.group_commits_interval
        filenames = set(history.get_filenames_in_range(bottom_range, top_range))
        if len(filenames) > 1:
            for pair in findsubsets(filenames, 2):
                update_coupling(str(repo.get_file_id(pair[0])), str(repo.get_file_id(pair[1])), logical_coupling)
            couplings.append(filenames)
    return couplings


def coupling_to_json(logical_coupling, repo: Repository) -> dict:
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

    for file in repo.unique_filenames:
        changed_with_this_file = logical_coupling.loc[logical_coupling['first_file'] == file]['second_file']
        if len(list(changed_with_this_file)) == 0:
            logical_coupling_data[str(repo.get_file_id(file))] = []
        else:
            for file2 in list(changed_with_this_file):
                logical_coupling_data[str(repo.get_file_id(file))].append(int(repo.get_file_id(file2)))

    # Any entity that we missed for some reason? Also add it here. Otherwise, many tears will be shed 😭
    for entity_id in list(repo.id_to_entity.keys()):
        if entity_id not in logical_coupling_data:
            logical_coupling_data[entity_id] = []

    return logical_coupling_data


def authors_to_json(history: History, repo: Repository):
    author_data = {}
    for file in repo.unique_filenames:
        file_authors = history.get_file_authors(file)
        author_data[repo.get_file_id(file)] = list(set(file_authors))
    return author_data


def remove_non_entities_files(all_files_logical_coupling_json, codebase_repo):
    non_entities_coupling = {}
    entities_ids = list(codebase_repo.id_to_entity.keys())
    for entity_id in entities_ids:
        non_entities_coupling[entity_id] = all_files_logical_coupling_json[entity_id]

    for entity_id in non_entities_coupling:
        non_entities_coupling[entity_id] = [f for f in non_entities_coupling[entity_id] if str(f) in entities_ids]

    return non_entities_coupling


def collect_data(codebases):
    for i, codebase in enumerate(codebases):
        t0 = time.time()
        print("")
        print(f"[underline]{codebase}[/underline] [{i + 1}/{len(codebases)}]")

        print(":white_circle: Parsing history")
        codebase_repo = Repository(codebase)
        cutoff_value = 100  # Commits with 5 or more files are ignored
        history = codebase_repo.cleanup_history(cutoff_value)

        print(":white_circle: Getting couplings")
        all_logical_coupling = get_logical_couplings(history, codebase_repo)

        print(":white_circle: Converting to JSON")
        # all_files_logical_coupling_json = coupling_to_json(all_logical_coupling, codebase_repo)
        # all_files_authors_json = authors_to_json(history, codebase_repo)
        #
        # entities_logical_coupling_json = remove_non_entities_files(all_files_logical_coupling_json, codebase_repo)
        # entities_authors_json = {k: v for k, v in all_files_authors_json.items() if k in list(codebase_repo.id_to_entity.keys())}
        #
        #
        # print(":white_circle: Writing")
        # write_jsons(all_files_logical_coupling_json, entities_logical_coupling_json,
        #             all_files_authors_json, entities_authors_json, codebase)
        #
        # t1 = time.time()
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
