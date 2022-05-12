import json
import os
import pickle
import time
import shutil

import pandas as pd
import subprocess
from io import StringIO

import itertools
from collections import defaultdict
from static_files_fix import get_codebases_of_interest, reverse_dict


class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def findsubsets(S, m):
    return set(itertools.combinations(S, m))


def get_history(repo_name) -> pd.DataFrame:
    command = f"./commit_log_script.sh ../codebases/{repo_name}/ | grep '\.java'"
    try:
        output = subprocess.check_output(command, stderr=subprocess.STDOUT, shell=True, universal_newlines=True)
    except subprocess.CalledProcessError as e:
        print("Error retrieving history.")
        print(e)
    else:
        return pd.read_csv(StringIO(output), sep=";",
                           names=['commit_hash', 'change_type', 'previous_filename', 'filename', 'timestamp', 'author'])


def fix_renames(history: pd.DataFrame):
    rename_info = history.loc[history['change_type'] == "RENAMED"]
    for before, after in zip(rename_info['previous_filename'], rename_info['filename']):
        history.loc[history['filename'] == before, 'filename'] = after
    return history


def fix_deletes(history: pd.DataFrame):
    delete_info = history.loc[history['change_type'] == "DELETED"]['filename']

    # We can only delete files that were not added/modified after appearing as deleted. This means that their latest
    # change type in the history must be a delete. Otherwise, we don't do anything with it here.
    actual_files_to_delete = history.loc[history['filename'].isin(delete_info)].groupby('filename').filter(
        lambda x: x.tail(1)['change_type'] == 'DELETED'
    )
    history = history.loc[~history['filename'].isin(actual_files_to_delete['filename'])]
    history = history.loc[~history['previous_filename'].isin(actual_files_to_delete['filename'])]
    return history


def compute_logical_coupling(fixed_history):
    earliest_timestamp = fixed_history['timestamp'].min()
    last_timestamp = fixed_history['timestamp'].max()
    couplings = []
    for ts in range(earliest_timestamp, last_timestamp, 3600):
        bottom_range = ts
        top_range = bottom_range + 3600
        commits_of_interest = fixed_history.loc[(fixed_history['timestamp'] < top_range) &
                                                (fixed_history['timestamp'] >= bottom_range)]
        filenames = set(commits_of_interest['filename'])
        couplings += findsubsets(filenames, 2)

    return pd.DataFrame(couplings, columns=['first_file', 'second_file'])


def extract_entity_files(repo_name, fixed_history):
    results = []
    id_to_entity = None
    with open(f"all-codebases-data/{repo_name}/{repo_name}_IDToEntity.json", "r") as f:
        id_to_entity = json.load(f)
        files_plain = list(id_to_entity.values())
        for filename in files_plain:
            filename_long = list(
                fixed_history.loc[fixed_history['filename'].str.contains("/" + filename + ".java")]['filename'].head(1))
            if len(filename_long) > 0:
                results.append(filename_long[0])
    return results, id_to_entity


def read_codebases(codebases_folder):
    results = []
    for folder in os.listdir(codebases_folder):
        if ".git" in os.listdir(codebases_folder + folder):
            results.append(folder)
    return results


def get_filename_id(full_filename, entity_to_id):
    return entity_to_id[os.path.splitext(os.path.basename(full_filename))[0]]


def convert_logical_coupling_authors_to_json(logical_coupling, history, id_to_entity):
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
            logical_coupling_data[get_filename_id(file, entity_to_id)].append(int(get_filename_id(file2, entity_to_id)))

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


def write_files(logical_coupling_data, author_data, repo_name, filename):
    with open(f"all-codebases-data/{repo_name}/{filename}-commit.json", "w") as f:
        json.dump(logical_coupling_data, f)
    with open(f"all-codebases-data/{repo_name}/{filename}-authors.json", "w") as f:
        json.dump(author_data, f)

    # Also copy to the mono2micro folder - only uncomment if you created the codebase, ran the analyzer,
    # but then found out that there was something wrong when creating decompositions with commit data as base...
    # shutil.copyfile(f"all-codebases-data/{repo_name}/{repo_name}-commit.json", f"../mono2micro/codebases/{
    # repo_name}__latest/commitChanges.json")
    # shutil.copyfile(f"all-codebases-data/{repo_name}/{repo_name}-authors.json",
    #                f"../mono2micro/codebases/{repo_name}__latest/filesAuthors.json")


def get_couplings(repo_name, ignore_refactors):
    if os.path.isfile(f"all-codebases-data/{repo_name}/{repo_name}-coupling.pkl"):
        with open(f"all-codebases-data/{repo_name}/{repo_name}-coupling.pkl", "rb") as f:
            entities_logical_coupling, all_logical_coupling, entities_only_history, fixed_history = pickle.load(f)
            entity_files, id_to_entity = extract_entity_files(repo_name, fixed_history)
    else:
        print("* Preparing history...")
        history = get_history(repo_name)
        renamed_history = fix_renames(history)
        fixed_history = fix_deletes(renamed_history)

        print("* Computing logical coupling...")
        if ignore_refactors:  # Ignore commits with more than 100 files
            fixed_history = fixed_history.groupby('commit_hash').filter(lambda x: len(x) < 100)

        entity_files, id_to_entity = extract_entity_files(repo_name, fixed_history)
        entities_only_history = fixed_history.loc[fixed_history['filename'].isin(entity_files)]
        entities_logical_coupling = compute_logical_coupling(entities_only_history)
        all_logical_coupling = compute_logical_coupling(fixed_history)
        with open(f"all-codebases-data/{repo_name}/{repo_name}-coupling.pkl", "wb") as f:
            pickle.dump((entities_logical_coupling, all_logical_coupling, entities_only_history, fixed_history), f)

    return entities_logical_coupling, all_logical_coupling, entities_only_history, fixed_history, entity_files, id_to_entity


def main():
    codebases_folder = "../codebases/"
    valid_codebases = get_codebases_of_interest(codebases_folder)
    ignore_refactors = True
    total_codebases = len(valid_codebases)
    current_codebase_id = 1
    for repo_name in valid_codebases:
        if repo_name != 'APMHome':
            continue
        print(
            f"===================== {bcolors.UNDERLINE} {repo_name} {current_codebase_id}/{total_codebases} {bcolors.ENDC} ===================== ")
        t0 = time.time()
        current_codebase_id += 1

        entities_logical_coupling, all_logical_coupling, \
            entities_only_history, fixed_history, entity_files, id_to_entity = get_couplings(repo_name, ignore_refactors)

        print("* Converting and writing logical coupling...")
        print("  - Entities")
        entities_logical_coupling_json, authors_entities_json = convert_logical_coupling_authors_to_json(
            entities_logical_coupling, entities_only_history, id_to_entity)

        print("  - All files")
        filename_ids = {}
        last_id = int(list(id_to_entity.keys())[-1])
        entity_to_id = reverse_dict(id_to_entity)
        for file in list(fixed_history['filename'].unique()):
            short_name = os.path.splitext(os.path.basename(file))[0]
            if short_name in list(id_to_entity.values()):
                filename_ids[entity_to_id[short_name]] = short_name
            else:
                last_id += 1
                filename_ids[str(last_id)] = short_name

        logical_coupling_json, authors_json = convert_logical_coupling_authors_to_json(
            all_logical_coupling, fixed_history, filename_ids)

        print(logical_coupling_json)
        # write_files(entities_logical_coupling_json, authors_entities_json, repo_name, f"{repo_name}-entities")
        # write_files(logical_coupling_json, authors_json, repo_name, f"{repo_name}-all-files")


if __name__ == '__main__':
    main()
