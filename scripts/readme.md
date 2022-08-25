# About

This folder contains the main collection scripts and some experiments. Organization is as follows:

* `collector`

    Has experiments and scripts:

  * `history.py` - a class to interact with the history of a repository.
  * `repository.py` - a class to interact with a repository. It mostly abstracts away details about the id of classes/files,
  and the cloning of a repository.
  * `service.py` - the main collection methods. `collect_data()` is the entry method called by the main script.
  * `log.awk`, `commit_log_script.sh` - scripts to obtain the history of a repository. These are managed and called by the `__init__()` method of `history.py`.
  * `legacy/` - a folder with experiments for alternate data collection strategies.

* `helpers`
  * `constants.py` - a class with constants used across the other scripts.
  * `static_files_fix.py` - some methods used to select the codebases we are evaluating.

* `metrics`

  Various scripts to compute evaluation metrics with Python. Were mainly built to better understand the metrics and look for
possible optimizations (spoiler alert: no optimizations were achieved). `tsr.py` is the only relevant one that is used, and it
computes the Team Size Reduction ratio for the codebases.

* `mono2micro`

  An abstraction to interact with the Mono2Micro backend. It has methods to create a codebase, run the analyser on it, and 
create decompositions.

* `run_thesis_tasks.py`

  The main script. The `main()` method contains the various things that can be done: data collection, codebase creation in the Mono2Micro backend,
analyser running, and gathering the analyser results into a single csv. They can be executed separately, but this may throw errors (for example,
running the analyser without creating a codebase first, or creating a codebase without the data files).

* `resources/`

This is where the data collection files will be saved. 