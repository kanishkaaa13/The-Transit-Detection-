# conftest.py
# -----------
# Tell pytest to only collect tests from files named test_*.py,
# and NOT from the pipeline source modules (stage4_heuristics.py etc.)
# which happen to contain public test_* functions.

collect_ignore_glob = ["stage4_*.py", "parameter_estimation.py"]
