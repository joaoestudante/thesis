"""
This file contains code useful for a preliminary evaluation of repositories, with the goal
to answer RQ1 of my thesis:

        "Can we use commits to suggest a monolith decomposition that takes into account
                            the transactional context?"
"""

"""
Notes:
- xs2a tem commits estranhos... não dá resultados nenhuns, e a maior parte dos commits
é de poms ou jsons... O repo faz muitos merges e eu acho que os merges não aparecem com
modified files :(
"""
from email.policy import default
import pandas as pd
import os
import git
import sys
import pydriller as pyd
import pickle
from itertools import combinations
from efficient_apriori import apriori
from halo import Halo # Super duper important spinner animation :)
from collections import defaultdict
from tqdm import tqdm
import numpy as np
import matplotlib.pyplot as plt
from collections import Counter
from .repository import Repository


class CommitSimilarity:
    def __init__(self, file_changes, files, repo_name):
        self.file_changes = file_changes
        self.files = files
        self.repo_name = repo_name


    def compute_fpm_similarity(self, support_commits = None, support_value = None):
        """
        Computes and returns the commit similarity for pairs of classes.
        """
        
        associations = defaultdict(lambda: 0)
        if support_commits is not None:
            min_support = support_commits/len(self.file_changes)
        else:
            min_support = support_value
        desired_confidence = 0.1

        print("")
        print(f"----- Running similarity algorithm for {self.repo_name} -----")
        print(f"* Total commits: {len(self.file_changes)}")
        print(f"* Minimum support: {round(min_support*100,4)}% = {support_commits or min_support*len(self.file_changes)} commits")
        print(f"* Minimum confidence: {desired_confidence*100}%")
        print(f"----- Results --------------------------------------")

        spinner = Halo(text='Computing...', spinner='dots')
        spinner.start()
        _, rules = apriori(self.file_changes, min_support=min_support, min_confidence=desired_confidence)
        for rule in rules:
            java_files_in_rule = []
            for file in rule.lhs:
                if ".java" in file:
                    java_files_in_rule.append(file)
            for file in rule.rhs:
                if ".java" in file:
                    java_files_in_rule.append(file)
            
            for pair in list(combinations(java_files_in_rule, 2)):
                associations[pair] = rule.support # Or should we use confidence?
        
        spinner.stop()

        covered_pairs = sum(x != 0 for x in associations.values())
        print(f"Covered pairs: {covered_pairs} = {round(covered_pairs*100/(len(self.files)*(len(self.files)-1)/2),5)}% out of all pairs")
        covered_files = set()
        for key,value in associations.items():
            if value != 0:
                covered_files.add(key[0])
                covered_files.add(key[1])
        print(f"Covered files: {len(covered_files)} = {round(len(covered_files)*100/len(self.files), 3)}%")

        # print("Some rules with values:")
        # i = 0
        # for key,value in associations.items():
        #     if value != 0:
        #         print(key, value)
        #         i += 1
        #     if i == 5:
        #         break
        print("")

        return associations


    def filename_to_hash(self, filename):
        return self.files[filename]


    def compute_simple_similarity(self):
        associations = defaultdict(int)
        number_of_large_change_sets = 0
        for change_set in self.file_changes:
            if len(change_set) < 100:
                combs = list(combinations(change_set, 2))
                for pair in combs:
                    associations[pair] += 1
            else:
                number_of_large_change_sets += 1

        total_pairs = len(self.files)*(len(self.files)-1)/2 # n(n-1)/2
        pairs_covered = round(len(associations.values())*100/(total_pairs), 3) # percentage
        occurring_once = sum(x == 1 for x in associations.values())
        occurring_more_than_once = sum(x > 1 for x in associations.values())

        print(f"Pairs covered: {pairs_covered}%")
        print(f"Change sets ignored: {number_of_large_change_sets} = {round(number_of_large_change_sets/len(self.file_changes),3)}%")
        print(f"Number of 1s: {occurring_once}")
        print(f"Number of > 1: {occurring_more_than_once}")
        print()

        self.associations = associations

        return self.repo_name, total_pairs, len(associations.values()), occurring_once, occurring_more_than_once, len(self.file_changes), len(self.files)

    
    def get_associations_frequency(self):
        hist = defaultdict(int)
        for value in self.associations.values():
            hist[value] += 1
        hist_formatted = []
        for key, value in sorted(hist.items()):
            hist_formatted.append([self.repo_name, key, round(value/len(self.associations.values()), 4)])
        return hist_formatted

    
    def save_associations(self):
        with open(f"pairs-associations/{self.repo_name}-associations.pkl", "wb") as f:
            pickle.dump(self.associations, f)

def flatten(t):
    return [item for sublist in t for item in sublist]

def main():
    """
    Executes the steps required for analysis. Should be working without any changes out of
    the box, and provide the same results as the ones presented on the thesis.

    It also creates a codebases folder on one level above the folder the script
    is running, which is where repositories will be cloned to.
    This can be configured by changing `cloning_location` below.
    """

    cloning_location = "../codebases"
    if not os.path.isdir(cloning_location):
        os.mkdir(cloning_location)

    results = []
    histogram_results = []
    repos = pd.read_csv("joao-codebases.csv")
    for repo_name, repo_link in zip(repos["codebase"], repos["repository_link"]):
        repo = Repository(repo_name, cloning_location, repo_link)
        repo.clone()
        changed_files_in_all_commits, file_names = repo.get_changed_files()

        print(f"Evaluating {repo_name}")
        sim = CommitSimilarity(changed_files_in_all_commits, file_names, repo_name)
        #sim.compute_fpm_similarity(support_value = 0.0005)
        results.append(sim.compute_simple_similarity())
        sim.save_associations()
        histogram_results.append(sim.get_associations_frequency())
    #pd.DataFrame(flatten(histogram_results), columns=["name","frequency","count"]).to_csv("data/pairs-frequencies.csv", index=False)
    #pd.DataFrame(results, columns=["name", "total_pairs", "pairs_covered","pairs_occurring_once", "pairs_occurring_more_than_once", "ncommits", "nfiles"]).to_csv("data/logical-coupling-comparison-data.csv", index=False)
        
if __name__ == "__main__":
    main()