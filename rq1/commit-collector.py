from collections import defaultdict
from repository import Repository
import pandas as pd
import os
from tqdm import tqdm
import json
import redis
import re


def build_simple_json(file_changes):
    result = defaultdict(list)
    for change in file_changes:
        if len(change) > 1 and len(change) < 100:
            for file1 in change:

                # This snippet copies the change list, and removes the current file
                # on the iteration. This way, we store the files that changed with this
                # file in the dictionary.
                new_change = change[:]
                new_change.remove(file1)

                result[file1] += [["C", x] for x in new_change]
        print(result[2])

    return result


def build_final_json(file_changes):
    basic = build_simple_json(file_changes)
    complex = {}
    for entry, commits in tqdm(basic.items()):
        complex[entry] = {
            "t":[{
                "id" : 0,
                "a": commits
            }]
        }
    return complex


def build_redis_data(file_changes, files, codebase_name, progress):
    r = redis.Redis()
    total_changes = len(file_changes)
    current_change = 0
    for change in file_changes:
        for file1 in change:
            r.lpush(f"{codebase_name}.{files[file1]}", files[file2])
            for file2 in change:
                if file2 != file1:
                    #print(f"Pushing {files[file2]} to {codebase_name}.{files[file1]}")
                    r.lpush(f"{codebase_name}.{files[file1]}", files[file2])
        current_change += 1
        print(f"Current: {current_change}", end="\r")


def convert_file_changes(file_changes, files):
    numbered_file_changes = []
    for change in file_changes:
        new_change = []
        for file in change:
            new_change.append(files[file])
        numbered_file_changes.append(new_change)
    return numbered_file_changes


def main():
    cloning_location = "../codebases"
    if not os.path.isdir(cloning_location):
        os.mkdir(cloning_location)
    
    repos = pd.read_csv("joao-codebases.csv")
    for repo_name, repo_link in zip(repos["codebase"], repos["repository_link"]):
        print(f"Evaluating {repo_name}")
        # if repo_name == "fenixedu-academic":
        #     continue
        repo = Repository(repo_name, cloning_location, repo_link)
        repo.clone()
        file_changes, file_names = repo.get_changed_files()

        new_changes = convert_file_changes(file_changes, file_names)
        #build_redis_data(file_changes, file_names, repo_name, redis_progress)
        #build_simple_json(new_changes)
        result = build_final_json(new_changes)
        return
        with open(f"codebases-commit-json/{repo_name}.json", "w") as outfile:
            json.dump(result, sort_keys=True, indent=2, separators=(',', ': '), fp=outfile)


if __name__ == "__main__":
    main()