from collections import defaultdict
from repository import Repository
import pandas as pd
import os
from tqdm import tqdm
import json

def convert_changes_to_json(file_changes, file_names):
    result = defaultdict(list)
    for change in file_changes:
        if len(change) > 1 and len(change) < 100:
            for file in change:
                new_change = change[:]
                new_change.remove(file)
                #result[file] += [file_names[x] for x in new_change]
                result[file] += [x for x in new_change]

    return result


def main():
    cloning_location = "../codebases"
    if not os.path.isdir(cloning_location):
        os.mkdir(cloning_location)
    
    repos = pd.read_csv("joao-codebases.csv")
    for repo_name, repo_link in zip(repos["codebase"], repos["repository_link"]):
        print(f"Evaluating {repo_name}")
        repo = Repository(repo_name, cloning_location, repo_link)
        repo.clone()
        file_changes, file_names = repo.get_changed_files()
        result = convert_changes_to_json(file_changes, file_names)

        if not os.path.isdir(f"codebases-data/{repo_name}"):
            os.mkdir(f"codebases-data/{repo_name}")

        with open(f"codebases-data/{repo_name}/{repo_name}-commit.json", "w") as outfile:
            json.dump(result, sort_keys=True, indent=2, separators=(',', ': '), fp=outfile)

        # with open(f"codebases-commit-json/{repo_name}-file-id.json", "w") as outfile:
        #     # file_names contains file -> id, but we want to save the reverse.
        #     json.dump(dict(zip(file_names.values(), file_names.keys())), sort_keys=True, indent=2, separators=(',', ': '), fp=outfile)


if __name__ == "__main__":
    main()