# The Memory-aware RepoLaunch for Build and Test 

This document introduces our memory-aware, self-evolving solution for RepoLaunch to learn from previous build and test results so that the subsequent build and test could be more cost-effective with higher success rate.

## Reuse RepoLaunch results for different commits of the same repo

If your dataset to be launched contains multiple commits from the same repo, we suggest you using the below script to launch your dataset instead of using the simple `launch data/examples/config.json`:

```bash
export OPENAI_API_KEY=... # for linux
$env:OPENAI_API_KEY=... # for windows
export TAVILY_API_KEY=... # for linux
$env:TAVILY_API_KEY=... # for windows

export GITHUB_TOKEN=... # for linux
$env:GITHUB_TOKEN=...   # for windows
python -m launch.scripts.adjacent_commit_run --config-path data/examples/config.json
```

The "organize" item in "mode" entry in `data/examples/config.json` must be set to `true` as this script must get the detailed test statuses of the current base commit to determine whether reusing existing RepoLaunch results for the current commit is safe. You can specify the "get_pertest_cmd" item in "mode" entry in `data/examples/config.json` as `false` if you don't need to get per-test execution command.

The differences between `launch data/examples/config.json` and `python -m launch.scripts.adjacent_commit_run --config-path data/examples/config.json` is that: `launch data/examples/config.json` invokes `launch/run.py` which launch each repo-commit pair separately from scratch. 

`launch/scripts/adjacent_commit_run.py` instead:
1. Select the base commit with commit time at the medium among all base commits of a repo in your dataset (the `medium commit`);
2. Launch the repo at the medium commit to get the required commands, parser and docker image at that commit. If launch is failed, will retry again next iteration;
3. Checkout to other commits of the repo specified in your dataset from the built image;
4. Run rebuild command, test command and test log parser at the checked-out commit. These commands and parser are from the result of the medium commit got by RepoLaunch. Decide whether direct git checkout is safe by comparing the number of tests passed at the medium commit result and the number of tests passed when using direct git checkout;
5. If num of tests passed does not meet the requirement, direct checkout is marked as failed, and the failed instances of the same repo is grouped again with medium commits re-selected. Then go back to Step 2.

Experiments on building executable envs for 856 GitHub issues from 93 repos show >= 98% success, with 82% savings on LM API cost and 78% savings on Docker image storage space, when using GPT-5.6-Sol-Medium. 

The even higher success rate compared to launching each repo-commit pair separately (~90% success rate) is because many build/test failures result from the generation randomness of LMs; re-running the instances that RepoLaunch didn't resolve at first trial and using rule-based git checkout reduces the LM randomness and thus increases overall success.

The saved disk space for docker images is because the images of different commits from the same repo only have different additional `git checkout <commit>` layers on top of the docker image of the medium commit. Only the image of medium commit is built from scratch by RepoLaunch. The images of different commits from the same repo share the same bottom layers with no duplicated storage. The `git checkout` layer is very light and almost take no additional space.
