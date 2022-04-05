import os
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

    def __init__(self, name, location, link):
        self.name = name
        self.location = location
        self.link = link
        self.path = f"{self.location}/{self.name}"
        self.shell_interface = GitShellInterface(self.path)
        self.rename_history = None

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
        return [f[2:].replace("\n", "") for f in all_files]

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

        file_sets = []
        file_names = []
        # spinner = Halo(text='Extracting files changed...', spinner='dots')
        # spinner.start()
        last_commit_hash = None
        for commit_hash in self.shell_interface.traverse_commits(end_commit):
            changed_files, changed_files_names = self.shell_interface.get_files_in_commit(commit_hash, extensions)
            if len(changed_files) > 0:
                file_sets.append(changed_files)
                file_names += changed_files_names
            if commit_hash == end_commit:
                print("Breaking traverse...")
                break
        self.rename_history = self.shell_interface.rename_history

        # spinner.succeed()
        return file_sets, set(file_names)

    def get_latest_filename(self, filename):
        return self.rename_history.latest_filename(filename)
