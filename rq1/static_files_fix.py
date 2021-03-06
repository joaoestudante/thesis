"""
There are plenty of static data collection files, but they have two problems:
- None is in the most up-to-date format
- Some don't have an id to entity file.
This script fixes the problem for the desired codebases.
"""
import json
import os
import difflib


def get_codebases_of_interest(codebases_root):
    results = []
    for folder in os.listdir(codebases_root):
        if ".git" in os.listdir(codebases_root + folder):
            commit_count = get_commit_count(folder, codebases_root)
            if commit_count < 100:
                print(f"{folder} has {commit_count} commits.")
            else:
                results.append(folder)

    return results


def update_collection_file(codebase, data_collection_root):
    entity_to_id = {}
    data_collection = {}
    original_data = None
    next_entity_id = 1

    all_jsons = os.listdir(data_collection_root)
    matches = difflib.get_close_matches(codebase + ".json", all_jsons)

    with open(f"{data_collection_root}{matches[0]}", "r") as f:
        original_data = json.load(f)

    if original_data is not None:
        for controller_method in original_data.keys():
            accesses = []
            for access in original_data[controller_method]:
                entity_name = access[0]
                access_type = access[1]
                if entity_name in entity_to_id:
                    accesses.append([access_type, entity_to_id[entity_name]])
                else:
                    entity_to_id[entity_name] = next_entity_id
                    accesses.append([access_type, next_entity_id])
                    next_entity_id += 1
            new_trace = {
                "t": [{
                    "id": 0,
                    "a": accesses
                }]
            }
            data_collection[controller_method] = new_trace

    return entity_to_id, data_collection


def reverse_dict(_dict):
    return {v: k for k, v in _dict.items()}


def write_files(entity_to_id, data_collection, output_directory, codebase):
    output_folder = f"{output_directory}/{codebase}"
    if not os.path.isdir(output_folder):
        os.makedirs(output_folder)

    data_collection_location = f"{output_folder}/{codebase}.json"
    entity_to_id_location = f"{output_folder}/{codebase}_entityToID.json"
    id_to_entity_location = f"{output_folder}/{codebase}_IDToEntity.json"

    with open(data_collection_location, "w") as f:
        json.dump(data_collection, f)

    with open(entity_to_id_location, "w") as f:
        json.dump(entity_to_id, f)

    with open(id_to_entity_location, "w") as f:
        json.dump(reverse_dict(entity_to_id), f)

    return True


def get_commit_count(codebase, codebases_root):
    return int(os.popen(f"cd {codebases_root}{codebase} && git rev-list --count HEAD").read())


def main():
    codebases_root = "../codebases/"
    output_directory = "all-codebases-data"
    data_collection_root = "../mono2micro-mine/data/static/CodebasesDetails/CodebasesStaticCollectionDatafiles" \
                           "/staticCollectionDatafiles/staticCollectionDatafiles/"
    codebases = get_codebases_of_interest(codebases_root)
    for codebase in codebases:
        entity_to_id, data_collection = update_collection_file(codebase, data_collection_root)
        if write_files(entity_to_id, data_collection, output_directory, codebase):
            print(f"Successfully wrote files to {output_directory}/{codebase}")
        else:
            print(f"Error writing files to {output_directory}/{codebase}")

if __name__ == "__main__":
    main()
