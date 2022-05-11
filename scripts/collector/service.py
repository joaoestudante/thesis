from __future__ import annotations

from functools import lru_cache

from rich.progress import track, Progress

import json
import os
import pickle
import time
import shutil

import pandas as pd
import subprocess
from io import StringIO
from rich import print

import itertools
from collections import defaultdict

from helpers.constants import Constants


class HistoryService:
    def __init__(self, codebase_name: str):
        self.codebase_name = codebase_name
        self.history: pd.DataFrame | None = None
        self.history_renames_fixed: pd.DataFrame | None = None
        self.history_deletes_fixed: pd.DataFrame | None = None

    def get_original_history(self) -> pd.DataFrame | None:
        command = f"{Constants.project_root}/collector/commit_log_script.sh {Constants.codebases_root_directory}/{self.codebase_name}/ | grep '\\.java'"
        try:
            output = subprocess.check_output(command, stderr=subprocess.STDOUT, shell=True, universal_newlines=True)
        except subprocess.CalledProcessError as e:
            print("Error retrieving history.")
            print(e.output)
        else:
            self.history = pd.read_csv(StringIO(output), sep=";", names=[
                'commit_hash', 'change_type', 'previous_filename', 'filename', 'timestamp', 'author'])
            return self.history

    def fix_renames(self, history: pd.DataFrame) -> pd.DataFrame:
        history_copy = history.copy()
        rename_info = history_copy.loc[history_copy['change_type'] == "RENAMED"]
        for before, after in zip(rename_info['previous_filename'], rename_info['filename']):
            history_copy.loc[history_copy['filename'] == before, 'filename'] = after
        self.history_renames_fixed = history_copy
        return history_copy

    def fix_deletes(self, history: pd.DataFrame):
        history_copy = history.copy()
        delete_info = history_copy.loc[history_copy['change_type'] == "DELETED"]['filename']

        # Sometimes, files are deleted at timestamp X, but then appear as added or modified in timestamp X + Y.
        # The cause is unknown, but if this happens, we don't want to delete those files: there is relevant
        # information after their supposed "deletion", and they still exist in the current snapshot of the repo.
        actual_files_to_delete = history_copy.loc[history_copy['filename'].isin(delete_info)].groupby(
            'filename').filter(
            lambda x: x.tail(1)['change_type'] == 'DELETED'
        )
        history_copy = history_copy.loc[~history_copy['filename'].isin(actual_files_to_delete['filename'])]
        history_copy = history_copy.loc[~history_copy['previous_filename'].isin(actual_files_to_delete['filename'])]
        self.history_deletes_fixed = history_copy
        return history_copy

    def get_clean_history(self):
        return self.fix_deletes(self.fix_renames(self.get_original_history()))


def findsubsets(s: set, m: int):
    return set(itertools.combinations(s, m))


class CommitCollectorService:
    def __init__(self, codebases):
        self.codebases_names = codebases
        self.codebases_names.sort()
        self.couplings_df: pd.DataFrame | None = None

    def get_id_to_filename(self, codebase):
        try:
            with open(f"{Constants.codebases_data_output_directory}/{codebase}/{codebase}_IDToEntity.json", "r") as f:
                return json.load(f)
        except FileNotFoundError as e:
            print(f"[red]The [b]IDToEntity.json[/b] file could not be found at "
                  f"{Constants.codebases_data_output_directory}/{codebase}/{codebase}_IDToEntity.json.[/red]")
            raise e

    def get_logical_couplings(self, history):
        earliest_timestamp = history['timestamp'].min()
        last_timestamp = history['timestamp'].max()
        couplings = []
        for bottom_range in range(earliest_timestamp, last_timestamp, Constants.group_commits_interval):
            top_range = bottom_range + Constants.group_commits_interval
            commits_of_interest = history.loc[(history['timestamp'] < top_range) &
                                              (history['timestamp'] >= bottom_range)]
            filenames = set(commits_of_interest['filename'])
            couplings += findsubsets(filenames, 2)

        self.couplings_df = pd.DataFrame(couplings, columns=['first_file', 'second_file'])
        return self.couplings_df

    def convert_logical_couplings(self, history: pd.DataFrame):
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
        Note that 'A' could be the filename itself, or the id (as a string in the case of keys, and an int in the case
        of values). The id is preferred as it saves memory.
        """
        author_data = {}
        logical_coupling_data = defaultdict(list)
        entity_to_id = reverse_dict(id_to_entity)
        filenames = list(history['filename'].unique())
        history_copy = history.copy()
        f = list(entity_to_id.keys())
        f.sort()
        history_copy['filename_id'] = history_copy['filename'].apply(lambda x: get_filename_id(x, entity_to_id))

        for file in filenames:
            file_authors = list(history_copy[history_copy['filename'] == file]['author'])
            author_data[get_filename_id(file, entity_to_id)] = list(set(file_authors))
            changed_with_this_file = logical_coupling.loc[logical_coupling['first_file'] == file]['second_file']
            for file2 in list(changed_with_this_file):
                logical_coupling_data[get_filename_id(file, entity_to_id)].append(
                    int(get_filename_id(file2, entity_to_id)))

        # Any file not in the logical coupling data? Add it... with 0 couplings to others
        # This can happen if a file changed alone, or only with non .java files, or in refactors, or all of them. Either
        # way, for our purposes, it has not changed with other files.
        for file in entity_to_id:
            file_id = get_filename_id(file, entity_to_id)
            if file_id not in logical_coupling_data:
                logical_coupling_data[file_id] = []
                file_authors = list(history_copy[history_copy['filename_id'] == file_id]['author'])
                author_data[file_id] = list(set(file_authors))

        return logical_coupling_data, author_data

    def generate_id_to_filename(self, codebase, history):
        with open(f"{Constants.codebases_data_output_directory}/{codebase}/{codebase}_IDToEntity.json", "r") as f:
            id_to_entity = json.load(f)
        filename_ids = {}
        last_id = int(list(id_to_entity.keys())[-1])
        entity_to_id = {value: key for key, value in id_to_entity.items()}

        for file in list(history['filename'].unique()):
            short_name = os.path.splitext(os.path.basename(file))[0]
            if short_name in list(id_to_entity.values()):
                filename_ids[entity_to_id[short_name]] = short_name
            else:
                last_id += 1
                filename_ids[str(last_id)] = short_name
        return filename_ids

    def get_filename_id(self, full_filename, entity_to_id):
        return entity_to_id[os.path.splitext(os.path.basename(full_filename))[0]]

    def remove_non_entities(self, all_files_logical_couplings, codebase, history):
        with open(f"{Constants.codebases_data_output_directory}/{codebase}/{codebase}_IDToEntity.json", "r") as f:
            id_to_entity = json.load(f)
            entity_ids = list(id_to_entity.keys())

        id_to_filename = self.generate_id_to_filename(codebase, history)
        entities_logical_couplings = all_files_logical_couplings.copy()
        entities_logical_couplings['first_file_id'] = entities_logical_couplings['first_file'].apply(
            lambda x: self.get_filename_id(x, id_to_filename))
        entities_logical_couplings['second_file_id'] = entities_logical_couplings['second_file'].apply(
            lambda x: self.get_filename_id(x, id_to_filename))

        return entities_logical_couplings.loc[
            (entities_logical_couplings['first_file_id'].isin(entity_ids)) &
            (entities_logical_couplings['second_file_id'].isin(entity_ids))
        ]

    def collect_data(self):
        for i, codebase in enumerate(self.codebases_names):
            print("")
            print(f"[underline]{codebase}[/underline] [{i + 1}/{len(self.codebases_names)}]")

            print(":white_circle: Parsing history")
            history_service = HistoryService(codebase)
            clean_history = history_service.get_clean_history()
            no_refactors_history = clean_history.groupby('commit_hash').filter(lambda x: len(x) < 100)

            print(":white_circle: Getting couplings for all files")
            all_files_logical_couplings = self.get_logical_couplings(no_refactors_history)

            print(":white_circle: Getting coupling only for entities")
            entities_only_logical_couplings = self.remove_non_entities(
                all_files_logical_couplings, codebase, no_refactors_history)
