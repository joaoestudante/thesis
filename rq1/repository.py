import json
import os
import pickle

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
        self.extensions = []

    def clone(self):
        """
        Clones the repository, if it doesn't exist already.
        """
        if os.path.isdir(self.path):
            return
        spinner = Halo(text='Cloning repo...', spinner='dots')
        spinner.start()
        git.Repo.clone_from(self.link, self.path)
        spinner.succeed()
        return self

    def get_current_files(self):
        """
        Returns: All the files found in the repository's directory, in an easy to test/parse format.
        """
        all_files = os.popen(f"cd {self.path} && find . -print").readlines()
        current_files_extension = []
        for file in all_files:
            if os.path.splitext(file)[1].replace("\n", "") in self.extensions:
                current_files_extension.append(file[2:].replace("\n", ""))
        return current_files_extension

    def get_changed_files(self, extensions, starting_commit=None, end_commit=None):
        """Returns the files changed per commit with extension in "extensions".

        Args:
            extensions (: Extensions to be included in the files
            starting_commit (): The hash of the first commit to analyze. Defaults to None.
            end_commit (): The hash of the last commit to analyze. Defaults to None.

        Returns:
            All the files that changed in the repository's history, whose extension is in the "extensions" argument, as
            well as all the unique filenames found.
        """
        self.extensions = extensions
        file_sets = []
        file_names = []
        if os.path.exists(f"files-changed/{self.name}.pkl"):
            with open(f"files-changed/{self.name}.pkl", "rb") as f:
                file_sets, file_names, rename_history = pickle.load(f)
                self.rename_history = rename_history
                return file_sets, file_names

        spinner = Halo(text='Extracting files changed...', spinner='dots')
        spinner.start()

        for commit_hash in self.shell_interface.traverse_commits(end_commit):
            changed_files, changed_files_names = self.shell_interface.get_files_in_commit(commit_hash, extensions)
            if len(changed_files) > 0:
                file_sets.append(changed_files)
                file_names += changed_files_names
            if commit_hash == end_commit:
                print("Breaking traverse...")
                break
        self.rename_history = self.shell_interface.rename_history

        with open(f"files-changed/{self.name}.pkl", "wb") as f:
            pickle.dump((file_sets, file_names, self.rename_history), f)

        spinner.succeed()

        return file_sets, set(file_names)

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

    def previous_filenames(self, filename: str) -> list[str]:
        previous_names = self.shell_interface.get_previous_filenames(filename)
        return previous_names.split("\n")[1:-1]
