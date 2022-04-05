import os
import pathlib
import networkx as nx
import re
import subprocess


class ChangedFile:
    def __init__(self, status, commit_hash, src_path, dst_path=None):
        self.status = status
        self.commit_hash = commit_hash
        self.src_path = src_path
        self.dst_path = dst_path

    def filename(self):
        """
        Returns the filename of this file. If the file was modified, the filename of
        this file is assumed to be the most recent one.

        Returns:
            str: The most recent filename of the file.
        """

        if self.dst_path is not None:
            return self.dst_path

        return self.src_path

    def previous_filename(self):
        """The previous filename is always the src_path - in the case of renames, src_path
        represents the filename before getting renamed; in other cases, src_path is just
        the name of the file.
        Although this method might seem useless, it abstracts away internal naming of this
        class and interpretation of the results from `git log`.
        """
        return self.src_path

    def is_renamed(self):
        return "R" in self.status

    def is_deleted(self):
        return "D" in self.status

    def is_modified(self):
        return "M" in self.status

    def is_added(self):
        return "A" in self.status

    def __lt__(self, other):
        return self.filename() < other.filename()

    def __gt__(self, other):
        return self.filename() > other.filename()

    def __str__(self):
        if self.is_renamed():
            return f"{self.src_path} => {self.dst_path} ({self.commit_hash})"
        else:
            return self.filename()


class RenameHistory:
    def __init__(self):
        self.rename_graph = nx.DiGraph()

    def add_new_rename(self, previous_name, new_name, commit_hash):
        self.rename_graph.add_edge(previous_name, new_name)

    def latest_filename(self, filename):
        try:
            all_filenames = list(nx.nodes(nx.dfs_tree(self.rename_graph, filename)))
            return all_filenames[-1]
        except KeyError:
            # Was never renamed
            return filename


class GitShellInterface:
    def __init__(self, codebase_folder):
        self.codebase_folder = codebase_folder
        self.rename_history = RenameHistory()

    def traverse_commits(self, end_commit):
        all_commits = os.popen(f"cd {self.codebase_folder} && git log --pretty=format:'%H' --reverse").readlines()
        for commit_hash in all_commits:
            yield commit_hash.replace("\n", "")


    def execute_get_files_command(self, commit_hash: str) -> list[str] or []:
        """
        This method executes a shell command to retrieve the changed files for the given commit hash.
        Each line contains information about:
            * The filename
            * The new filename (in case of rename)
            * The status (Added: A, Deleted: D, Modified: M, or Renamed: RXX where XX is the similarity %)
        Args:
            commit_hash (): The commit that should be analyzed.

        Returns:
            A list of all lines extracted from the shell command. Each line corresponds to a file in the commit.

        """
        command = f"cd {self.codebase_folder} && git diff --name-status {commit_hash}^ {commit_hash} --root " \
                  f"--find-renames=30% "
        try:
            output = subprocess.check_output(
                command, stderr=subprocess.STDOUT, shell=True, timeout=3,
                universal_newlines=True)
        except subprocess.CalledProcessError:
            # This exception occurs when the given commit hash corresponds to a commit with no parents.
            # Such a situation is normal for the first commit, but can also rarely happen in the middle of the history.
            # When it does happen, we use a similar command that compares the commit with a special Git hash that is
            # meant to indicate an empty tree.
            lines = os.popen(f"cd {self.codebase_folder} && git diff --name-status "
                             f"4b825dc642cb6eb9a060e54bf8d69288fbee4904 {commit_hash}").readlines()
        else:
            lines = output.split("\n")[:-1]
            if "rename detection" in output:
                # FIXME: We should probably do something smarter here. Refer to issue #1 on GitHub.
                print("Skipped! Too many files in commit...")
                return []
        return lines

    def get_files_in_commit(self, commit_hash: str, extensions: list[str]):
        """
        Parses the lines from the shell command to create objects with the correct properties.
        Args:
            commit_hash (): The commit to analyze.
            extensions (): The extensions to consider. Files with an extension not in this list are ignored.

        Returns: A list with ChangedFile objects, and a list with filenames. Both lists can be empty if no file in
        the given commit has an extension found in the `extensions` argument.

        """
        lines = self.execute_get_files_command(commit_hash)
        if not lines:
            return [], []
        files = []
        names = []
        for line in lines:
            splitted = re.split(r'\t+', line.rstrip('\t').replace("\n", ""))
            status = splitted[0]
            name = splitted[1]
            if len(splitted) > 2:
                renamed_name = splitted[2]
            else:
                renamed_name = None
            if pathlib.Path(splitted[-1]).suffix in extensions:
                changed_file = ChangedFile(status, commit_hash, name, renamed_name)

                if changed_file.is_renamed():
                    self.rename_history.add_new_rename(name, renamed_name, commit_hash)

                files.append(changed_file)
                names.append(changed_file.filename())
        return files, names
