import json
import os
from functools import cached_property

from collector.history import History
from helpers.constants import Constants


class Repository:
    """
    Represents a repository. Allows for access to history and information of files, as well as clone.
    """

    def __init__(self, codebase_name):
        self.name = codebase_name
        self.history = History(codebase_name)
        self.no_refactors_history = None

    def clone(self):
        raise NotImplemented

    def cleanup_history(self, cutoff_value) -> History:
        self.history = self.history.fix_renames().fix_deletes()
        self.no_refactors_history = self.history.get_no_refactors_copy(cutoff_value)
        self.history = self.no_refactors_history
        return self.no_refactors_history

    @property
    def unique_filenames(self):
        # Abstraction could be better here
        return list(self.history.history_df['filename'].unique())

    @property
    def entity_short_names(self):
        return self.id_to_entity.values()

    @property
    def entity_full_names(self):
        long_entities = []
        short_entities = list(self.id_to_entity.values())
        for filename in short_entities:
            filename_long = self.history.convert_short_to_long_filename(filename)
            if filename_long is not None:
                long_entities.append(filename_long)
        return long_entities

    def get_file_id(self, full_filename):
        return self.file_to_id[os.path.splitext(os.path.basename(full_filename))[0]]

    @cached_property
    def id_to_file(self):
        id_to_entity = self.id_to_entity
        entity_to_id = self.entity_to_id
        last_id = int(list(id_to_entity.keys())[-1])
        ids_filename = {}

        for file in self.unique_filenames:
            short_name = os.path.splitext(os.path.basename(file))[0]
            if short_name in list(id_to_entity.values()):
                ids_filename[str(entity_to_id[short_name])] = short_name
            else:
                last_id += 1
                ids_filename[str(last_id)] = short_name
        return ids_filename

    @cached_property
    def file_to_id(self):
        return {v: k for k, v in self.id_to_file.items()}

    @property
    def id_to_entity(self):
        try:
            with open(f"{Constants.codebases_data_output_directory}/{self.name}/{self.name}_IDToEntity"
                      f".json", "r") as f:
                return json.load(f)
        except FileNotFoundError as e:
            print(f"[red]The [b]IDToEntity.json[/b] file could not be found at "
                  f"{Constants.codebases_data_output_directory}/{self.name}/{self.name}_IDToEntity.json.[/red]")
            raise e

    @property
    def entity_to_id(self):
        try:
            with open(f"{Constants.codebases_data_output_directory}/{self.name}/{self.name}_entityToID"
                      f".json", "r") as f:
                return json.load(f)
        except FileNotFoundError as e:
            print(f"[red]The [b]entityToID.json[/b] file could not be found at "
                  f"{Constants.codebases_data_output_directory}/{self.name}/{self.name}_IDToEntity.json.[/red]")
            raise e
