import json
import os
import pickle
import math
from collections import defaultdict

import git
from halo import Halo  # Super duper important spinner animation :)
from gitshellinterface import GitShellInterface
import matplotlib.pyplot as plt

plt.rcParams.update({'font.size': 3})


class Repository:
    """
    Abstracts different steps of the process of cloning the repo, obtaining changed files
    for all commits, etc.
    """

    def __init__(self, name, location, link, data_output_location):
        self.name = name
        self.location = location
        self.link = link
        self.path = f"{self.location}/{self.name}"
        self.shell_interface = GitShellInterface(self.path)
        self.rename_history = None
        self.data_output_location = data_output_location

    def clone(self, max_commit_hash: float = math.nan):
        """
        Clones the repository, if it doesn't exist already.
        """
        if os.path.isdir(self.path):
            return
        spinner = Halo(text='Cloning repo...', spinner='dots')
        spinner.start()
        if math.isnan(max_commit_hash):
            git.Repo.clone_from(self.link, self.path)
            spinner.succeed()
            return self
        repo = git.Repo.clone_from(self.link, self.path, no_checkout=True)
        repo.git.checkout(max_commit_hash)
        spinner.succeed()
        return self

    def get_current_files(self):
        """
        Returns: All the files found in the repository's directory, in an easy to test/parse format.
        """
        all_files = os.popen(f"cd {self.path} && find . -print").readlines()
        return [f[2:].replace("\n", "") for f in all_files]

    def get_changed_files(self, extensions, starting_commit=None, end_commit=None, entities_only=True):
        """Returns the files changed per commit with extension in "extensions".

        Args:
            entities_only ():
            extensions (: Extensions to be included in the files
            starting_commit (): The hash of the first commit to analyze. Defaults to None.
            end_commit (): The hash of the last commit to analyze. Defaults to None.

        Returns:
            All the files that changed in the repository's history, whose extension is in the "extensions" argument, as
            well as all the unique filenames found.
        """

        file_sets = []
        file_names = []
        authors = []
        if os.path.exists(f"files-changed/{self.name}.pkl"):
            with open(f"files-changed/{self.name}.pkl", "rb") as f:
                file_sets, file_names, authors, rename_history = pickle.load(f)
                self.rename_history = rename_history
                return file_sets, file_names, authors

        spinner = Halo(text='Extracting files changed...', spinner='dots')
        spinner.start()

        for commit_hash in self.shell_interface.traverse_commits(end_commit):
            changed_files, changed_files_names, author = self.shell_interface.get_files_in_commit_and_author(commit_hash, extensions)
            if len(changed_files) > 0:
                file_sets.append(changed_files)
                file_names += changed_files_names
                authors.append(author)
            if commit_hash == end_commit:
                print("Breaking traverse...")
                break

        self.rename_history = self.shell_interface.rename_history

        # An entity which is found in the latest repo version may have had other name in the past. As such, we can only
        # remove any non-entities after the whole history is obtained.
        if entities_only:
            file_sets, file_names, authors = self.remove_non_entities(file_sets, file_names, authors)

        with open(f"files-changed/{self.name}.pkl", "wb") as f:
            pickle.dump((file_sets, file_names, authors, self.rename_history), f)

        spinner.succeed()

        return file_sets, set(file_names), authors

    def get_latest_filename(self, filename):
        return self.rename_history.latest_filename(filename)

    def get_entity_filenames(self):
        """
        This method parses the filenames from the IDtoEntity file and returns them with a '.java' suffix.
        Returns:

        """
        files_in_output_folder = os.listdir(f"{self.data_output_location}{self.name}/")
        for file in files_in_output_folder:
            if "IDToEntity" in file:
                with open(f"{self.data_output_location}{self.name}/{file}", "r") as f:
                    id_to_entity = json.load(f)
                    return [f"{entity}.java" for entity in list(id_to_entity.values())]
        print(f"No IDToEntity file was found in {self.data_output_location}{self.name}/")
        return []

    def remove_non_entities(self, file_sets, file_names, authors):
        """
        This method removes any files that are not entities. If an entity information file could not
        be found, the user is notified, and no changes are made.
        Args:
            file_names ():
            result ():
            repo ():
        """

        spinner = Halo(text='Removing non-entities..', spinner='dots')
        spinner.start()

        entities_file_sets = []
        entities_file_names = []
        entities_authors = []
        entity_names = self.get_entity_filenames()
        if len(entity_names) == 0:
            return file_sets, file_names, authors

        for change_info, author in zip(file_sets, authors):
            new_change_info = []
            for file in change_info:
                if os.path.basename(self.get_latest_filename(file.filename())) in entity_names:
                    new_change_info.append(file)
            if len(new_change_info) > 0:
                entities_file_sets.append(new_change_info)
                entities_authors.append(author)
            #     print(f"+ {new_change_info}")
            # else:
            #     print("- ",end="")
            #     print(change_info)

        for entity_name in entity_names:
            entities_file_names.append(os.path.splitext(entity_name)[0])

        spinner.succeed()

        return entities_file_sets, entities_file_names, entities_authors
