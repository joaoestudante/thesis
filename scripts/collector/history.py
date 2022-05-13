from __future__ import annotations

import json
from functools import cached_property

import pandas as pd
import subprocess
from io import StringIO
from rich import print

from helpers.constants import Constants


class History:
    def __init__(self, codebase_name, df=None):
        if df is not None:
            self.history_df = df
            self.codebase_name = codebase_name
        else:
            command = f"{Constants.project_root}/collector/commit_log_script.sh {Constants.codebases_root_directory}/{codebase_name}/ | grep '\\.java'"
            try:
                output = subprocess.check_output(command, stderr=subprocess.STDOUT, shell=True, universal_newlines=True)
                self.history_df = pd.read_csv(StringIO(output), sep=";", names=[
                    'commit_hash', 'change_type', 'previous_filename', 'filename', 'timestamp', 'author'])
                self.codebase_name = codebase_name
            except subprocess.CalledProcessError as e:
                print("Error retrieving history.")
                print(e.output)

    def fix_renames(self) -> History:
        rename_info = self.history_df.loc[self.history_df['change_type'] == "RENAMED"]
        for before, after in zip(rename_info['previous_filename'], rename_info['filename']):
            self.history_df.loc[self.history_df['filename'] == before, 'filename'] = after
        return self

    def fix_deletes(self) -> History:
        delete_info = self.history_df.loc[self.history_df['change_type'] == "DELETED"]['filename']

        # Sometimes, files are deleted at timestamp X, but then appear as added or modified in timestamp X + Y.
        # The cause is unknown, but if this happens, we don't want to delete those files: there is relevant
        # information after their supposed "deletion", and they still exist in the current snapshot of the repo.
        actual_files_to_delete = self.history_df.loc[self.history_df['filename'].isin(delete_info)] \
            .groupby('filename') \
            .filter(lambda x: x.tail(1)['change_type'] == 'DELETED')

        self.history_df = self.history_df.loc[~self.history_df['filename'].isin(actual_files_to_delete['filename'])]
        self.history_df = self.history_df.loc[~self.history_df['previous_filename'].isin(actual_files_to_delete['filename'])]

        return self

    def remove_refactors(self):
        self.history_df = self.history_df.groupby('commit_hash').filter(lambda x: len(x) < 100)
        return self

    def get_entities_only_copy(self, entities_full_names):
        entities_only_df = self.history_df.loc[self.history_df['filename'].isin(entities_full_names)]
        return History(self.codebase_name, entities_only_df)

    def convert_short_to_long_filename(self, short):
        match = list(
            self.history_df.loc[self.history_df['filename'].str.contains("/" + short + ".java")]['filename'].head(1)
        )
        if len(match) == 0:
            return None
        else:
            return match[0]

    @property
    def first_ts(self):
        return self.history_df['timestamp'].min()

    @property
    def last_ts(self):
        return self.history_df['timestamp'].max()

    def get_filenames_in_range(self, bot, top):
        range_ = self.history_df.loc[(self.history_df['timestamp'] < top) & (self.history_df['timestamp'] >= bot)]
        return range_['filename']

    def get_file_authors(self, file):
        return list(self.history_df[self.history_df['filename'] == file]['author'])
