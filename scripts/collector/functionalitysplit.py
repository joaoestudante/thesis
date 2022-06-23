"""
A mixed collection strategy, where the commit data changes the static analysis data.

The algorithm is like so:
- Retrieve, parse, fix the history and store it in a dataframe.
- Compute the similarity of all entities
- For each functionality:
    * Create a similarity matrix with the entities in that functionality
    * Cluster those entities in the best way possible (according to scipy's fcluster method)
    * Create a new functionality for each of the generated clusters
"""
from collector.commitsplit import parse_functionalities
from collector.repository import Repository
from collector.service import get_logical_couplings
from helpers.constants import Constants
import json
from scipy.cluster import hierarchy
import numpy as np


class StaticFunctionality:
    def __init__(self, accesses, name):
        self.accesses = accesses
        self.name = name

    def __str__(self):
        return f"{self.name} - {len(self.accesses)} entities"

    def __repr__(self):
        return self.__str__()

    def split(self, couplings):
        new_functionalities = []
        entities_in_functionaliy = set()
        for a in self.accesses:
            entities_in_functionaliy.add(a[1])

        similarities = []
        for entity1 in entities_in_functionaliy:
            entity1_similarity = []
            for entity2 in entities_in_functionaliy:
                if entity1 == entity2:
                    entity1_similarity.append(1)
                else:
                    entity1_similarity.append(
                        len(couplings.loc[(couplings["first_file"] == entity1) & (couplings["second_file"] == entity2)])
                    )
            similarities.append(entity1_similarity)
        matrix = np.array(similarities)
        hierarc = hierarchy.linkage(y=matrix)
        clustering = hierarchy.fcluster(hierarc, 0.8, criterion='distance')
        print(clustering)

        print(similarities)



def convert_names_ids(element, repo):
    return [int(repo.get_file_id(element[0])), int(repo.get_file_id(element[1]))]


def parse_full_functionalities(static_analysis_file_path):
    functionalities = []
    with open(static_analysis_file_path, "r") as f:
        data = json.load(f)
    for controller in data:
        accesses = data[controller]["t"][0]["a"]
        if len(accesses) > 1:
            functionalities.append(StaticFunctionality(accesses, controller))
    return functionalities


def collect(codebases):
    for codebase in codebases:
        print("Initializing history")
        codebase_repo = Repository(codebase)

        cutoff_value = 100  # Commits with 5 or more files are ignored
        print("Processing history")
        history = codebase_repo.cleanup_history(cutoff_value)

        print("Parsing functionalities")
        functionalities = parse_full_functionalities(f"{Constants.codebases_data_output_directory}/{codebase}/{codebase}.json")

        print("Getting coupling data")
        couplings = get_logical_couplings(history)

        print("Converting to ids")
        couplings_ids = couplings.apply(convert_names_ids, args=[codebase_repo], axis=1, result_type='expand')
        couplings_ids.set_axis(["first_file", "second_file"], axis=1, inplace=True)

        final_functionalities = []
        for functionality in functionalities:
            new_functionalities = functionality.split(couplings_ids)


collect(["quizzes-tutor"])