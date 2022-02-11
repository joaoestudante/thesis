import numpy as np
from scipy.cluster import hierarchy
import sys
import json
from os import path

codebasesPath = str(sys.argv[1])
codebaseName = str(sys.argv[2])
totalNumberOfEntities = int(sys.argv[3])

interval = 10
multiplier = 10
minClusters = 3
clusterStep = 1
maxClusters = -1

if 3 < totalNumberOfEntities < 10:
    maxClusters = 3
elif 10 <= totalNumberOfEntities < 20:
    maxClusters = 5
elif 20 <= totalNumberOfEntities:
    maxClusters = 10
else:
    raise Exception("Number of entities is too small (less than 4)")

with open(codebasesPath + codebaseName + "/analyser/similarityMatrix.json") as f:
    similarityMatrix = json.load(f)

entities = similarityMatrix["entities"]
linkageType = similarityMatrix["linkageType"]


def createCut(a, w, r, s, n):
    name = ','.join(map(str, [a, w, r, s, n]))

    filePath = codebasesPath + codebaseName + "/analyser/cuts/" + name + ".json"

    if (path.exists(filePath)):
        return

    with open(codebasesPath + codebaseName + "/analyser/similarityMatrix.json") as f:
        similarityMatrix = json.load(f)

    matrix = similarityMatrix["matrix"]
    for i in range(len(matrix)):
        for j in range(len(matrix)):
            matrix[i][j] = matrix[i][j][0] * a / 100 + \
                           matrix[i][j][1] * w / 100 + \
                           matrix[i][j][2] * r / 100 + \
                           matrix[i][j][3] * s / 100

    matrix = np.array(matrix)

    hierarc = hierarchy.linkage(y=matrix, method=linkageType)

    cut = hierarchy.cut_tree(hierarc, n_clusters=n)

    clusters = {}
    for i in range(len(cut)):
        if str(cut[i][0]) in clusters.keys():
            clusters[str(cut[i][0])] += [entities[i]]
        else:
            clusters[str(cut[i][0])] = [entities[i]]

    clustersJSON = {}
    clustersJSON["clusters"] = clusters

    with open(filePath, 'w') as outfile:
        outfile.write(json.dumps(clustersJSON, indent=4))


def sendRequest(a, w, r, s, maxClusterCut):
    a *= multiplier
    w *= multiplier
    r *= multiplier
    s *= multiplier

    if maxClusterCut:
        createCut(a, w, r, s, totalNumberOfEntities)
    else:
        for n in range(minClusters, maxClusters + 1, clusterStep):
            createCut(a, w, r, s, n)


try:
    for a in range(interval, -1, -1):
        remainder = interval - a
        if remainder == 0:
            sendRequest(a, 0, 0, 0, False)
        else:
            for w in range(remainder, -1, -1):
                remainder2 = remainder - w
                if remainder2 == 0:
                    sendRequest(a, w, 0, 0, False)
                else:
                    for r in range(remainder2, -1, -1):
                        remainder3 = remainder2 - r
                        if remainder3 == 0:
                            sendRequest(a, w, r, 0, False)
                        else:
                            sendRequest(a, w, r, remainder3, False)

    sendRequest(10, 0, 0, 0, True)  # last request to discover max Complexity possible (each cluster is singleton)
except Exception as e:
    print(e)
