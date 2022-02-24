import os
import git
import sys
import pydriller as pyd
import pickle
from halo import Halo # Super duper important spinner animation :)


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

    def clone(self):
        """
        Clones the repository, if it doesn't exist already.
        """
        if os.path.isdir(self.path):
            return
        spinner = Halo(text='Cloning repo...', spinner='dots')
        spinner.start()
        git.repo.clone_from(self.link, self.path)
        spinner.succeed()
        return self

    def _optimize_changed_files(self, changed_files):
        efficient_file_sets = []
        file_names = {}
        file_counter = 0
        for file_set in changed_files:
            temp = []
            for file in file_set:
                if '.java' in file:
                    if file not in file_names:
                        file_names[file] = file_counter
                        file_counter += 1
                    temp.append(sys.intern(file))
            if len(temp) > 0:
                efficient_file_sets.append(temp)
        return efficient_file_sets, file_names

    def get_changed_files(self, starting_commit = None, end_commit = None):
        """
        Returns a list containing a list for each commit with the modified files, as well
        as the unique files.

        :param starting_commit: SHA of the earliest commit to consider
        :param end_commit: SHA of the latest commit to consider
        :return: the list of lists with the modified files, and the unique files
        """

        try:
            with open(f"files-changed/{self.name}-files.pkl", "rb") as p:
                file_sets = pickle.load(p)
                return self._optimize_changed_files(file_sets)
                
        except FileNotFoundError:
            print("No previous file sets saved, creating them.")

        if not os.path.isdir("files-changed"):
            os.mkdir("files-changed")
        
        file_sets = []
        pydriller_repo = pyd.Repository(self.path, num_workers=8)
        spinner = Halo(text='Extracting files changed...', spinner='dots')
        spinner.start()
        for commit in pydriller_repo.traverse_commits():
             # 1h:30 para o Fénix
            #file_sets.append([sys.intern(c.filename) for c in commit.modified_files])

             # 5m para o Fénix
            file_sets.append(os.popen(f"cd {self.path} && git diff-tree --no-commit-id --name-only -r {commit.hash}").read().split())

            # 2m:38 para o Fénix se for pure bash

        with open(f"files-changed/{self.name}-files.pkl", "wb") as p:
            pickle.dump(file_sets, p)
        
        spinner.succeed()
        
        return self._optimize_changed_files(file_sets)
