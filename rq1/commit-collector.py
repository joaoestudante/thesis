from collections import defaultdict
from repository import Repository
import pandas as pd
import os
import json
from gitshellinterface import ChangedFile
from halo import Halo  # Super duper important spinner animation :)
import time


def process_delete(file: str, result: dict) -> None:
    """
    This method deletes the given filename data from the result dict. This includes the filename and its changed
    files information (if they exist), as well as any appearances of the filename in other filenames changed files
    information.
    Args:
        file (): The filename to purge from the result dictionary.
        result (): Dictionary containing the non-deleted filenames as keys, and the filenames they changed with
        as values.
    """
    try:
        result.pop(file)
    except KeyError:
        # The file doesn't exist as a key - this is cheaper (maybe?) than testing for existence.
        # Ask for forgiveness rather than permission and all that :)
        pass
    for k, v in result.items():
        if file in v:
            result[k] = [x for x in v if x != file]  # Remove all occurrences of this filename in the list


def process_unresolved_renames(result: dict, repo: Repository) -> None:
    """
    This method analyzes and edits the result dictionary to ensure that all keys and values are the most up-to-date
    filenames. It exists because sometimes renames occur in commits that are ignored.
    Args:
        result (): Dictionary containing the non-deleted filenames as keys, and the filenames they changed with
        as values.
        repo (): Repository object representing the codebase.
    """
    keys_to_remove = []
    keys_to_add = []
    elements_to_add = []
    for k, v in result.items():
        k_latest_filename = repo.get_latest_filename(k)
        if k_latest_filename != k:
            # We can't change the dict size during iteration, so we store the info we want to add and delete after
            # this loop
            keys_to_add.append(k_latest_filename)
            elements_to_add.append([repo.get_latest_filename(x) for x in v])
            keys_to_remove.append(k)
        else:
            result[k] = [repo.get_latest_filename(x) for x in v]

    for k in keys_to_remove:
        result.pop(k)
    for k, v in zip(keys_to_add, elements_to_add):
        result[k] = v


def remove_non_entities(result: dict, repo: Repository, file_names: list[str]):
    """
    This method removes from the result dict any files that are not entities. If an entity information file could not
    be found, the user is notified, and no changes are made.
    Args:
        file_names ():
        result ():
        repo ():
    """

    entity_names = repo.get_entity_filenames()
    print(f"entities: {entity_names}")
    if len(entity_names) == 0:
        return

    for file in file_names:
        if os.path.basename(file) not in entity_names:
            process_delete(file, result)



def delete_files_not_in_repo(result: dict, repo: Repository, file_names: list[str]) -> None:
    """
    This method deletes from the result dictionary all the files that are not currently in the cloned repository.
    It's an alternative approach to the pruning and renaming persistence that is done with the other methods.
    Args:
        result (): Dictionary containing the non-deleted filenames as keys, and the filenames they changed with
        as values.
        repo (): Repository object representing the codebase.
        file_names (): List containing all the *unique* file names observed in the codebase's history.
    """
    all_files = repo.get_current_files()
    for file_name in file_names:
        if file_name not in all_files:
            try:
                result.pop(file_name)
            except KeyError:
                pass
            for k, v in result.items():
                if file_name in v:
                    result[k] = [x for x in v if
                                 x != file_name]  # Remove all occurrences of this filename in the list
        if file_name in all_files and file_name not in result.keys():
            result[file_name] = []


def convert_changes_to_json(file_changes: list[list[ChangedFile]], file_names: list[str], repo: Repository) -> dict:
    """
    This method takes the file changes as observed in the repository's commits and converts them to something useful
    for monolith decompositions.

    Args:
        file_changes (): List containing all the changes observed in the codebase's history.
        file_names (): List containing all the *unique* file names observed in the codebase's history.
        repo (): Repository object representing the codebase.

    Returns:
        result (dict): A dictionary containing the non-deleted filenames as keys, and the filenames they changed with
        as values.

    """
    result = defaultdict(list)
    deleted_files: list[str] = []

    for changed_index, change in enumerate(file_changes):
        if 1 < len(change) < 100:
            for file in change:
                new_change = change[:]
                new_change.remove(file)
                # result[file] += [file_names[x] for x in new_change]
                result[repo.get_latest_filename(file.filename())] += [repo.get_latest_filename(x.filename()) for x in new_change]

        # Even if we don't want to consider this change for analysis purposes, it might contain information about
        # deletions and modifications that is necessary to keep.
        for file in change:
            if file.is_deleted():
                deleted_files.append(file.filename())
            if file.is_added() or file.is_modified():
                if file.filename() in set(deleted_files):
                    deleted_files.remove(file.filename())

    # Catch files that exist, but were added in commits with more than 100 changed files.
    # In these cases, we can assume that the file is not related to any others, but it should still exist
    # in the list so that the clustering works correctly.
    for file in file_names:
        if repo.get_latest_filename(file) not in list(result.keys()):
            result[file] = []

    # Any file that was deleted in the repository history, and was never added or modified after its deletion should be
    # deleted from the result.
    for file in deleted_files:
        process_delete(file, result)

    # We ensure that any renaming which might've occurred in commits with more than 100 changed files
    # is properly stored.
    process_unresolved_renames(result, repo)

    # Any non-entity files are removed from the result.
    remove_non_entities(result, repo, file_names)

    # The method below deletes any information about files not currently in the repo. It's an alternative approach to
    # the one employed above, which might warrant some experimentation to see if results differ too much.
    # delete_files_not_in_repo(result, repo, file_names)

    return result


def main():
    cloning_location = "../codebases"
    if not os.path.isdir(cloning_location):
        os.mkdir(cloning_location)

    data_output_location = "codebases-data/"
    if not os.path.isdir(data_output_location):
        os.mkdir(data_output_location)
    
    repos = pd.read_csv("joao-codebases.csv")
    for repo_name, repo_link, max_commit_hash in zip(repos["codebase"], repos["repository_link"], repos["max_commit_hash"]):
        print(f"Evaluating {repo_name}")
        t0 = time.time()
        repo = Repository(repo_name, cloning_location, repo_link, data_output_location)
        repo.clone()
        file_changes, file_names = repo.get_changed_files([".java"], end_commit=max_commit_hash)
        spinner = Halo(text='Converting changes...', spinner='dots')
        spinner.start()
        result = convert_changes_to_json(file_changes, file_names, repo)
        spinner.succeed()

        if not os.path.isdir(f"codebases-data/{repo_name}"):
            os.mkdir(f"codebases-data/{repo_name}")

        with open(f"codebases-data/{repo_name}/{repo_name}-commit.json", "w") as outfile:
            json.dump(result, sort_keys=True, indent=2, separators=(',', ': '), fp=outfile)

        t1 = time.time()
        print(f"Took {t1-t0} seconds to run.")

        # with open(f"codebases-commit-json/{repo_name}-file-id.json", "w") as outfile:
        #     # file_names contains file -> id, but we want to save the reverse.
        #     json.dump(dict(zip(file_names.values(), file_names.keys())), sort_keys=True, indent=2, separators=(',', ': '), fp=outfile)


if __name__ == "__main__":
    main()