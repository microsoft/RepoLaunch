# `🚀 RepoLaunch Agent`

*Turning Any Codebase into Testable Sandbox Environment*

RepoLaunch Agent now supports all mainstram languages, supports running on linux-arch & windows-arch docker images.


## Launch Environment
Before getting started, please set your `OPENAI_API_KEY` and `TAVILY_API_KEY` environment variable. We use [tavily](https://www.tavily.com/) for LLM search engine support.

We provide an example input file `test-dataset.jsonl` and a run config `test-config.json` to help you quickly go through the launch process.

```shell
pip install -e .

export TAVILY_API_KEY=...

python -m launch.run --config-path test-config.json
```

### Input

For the input data used to set up the environment, we require the following fields:

| Field        | Description                                                                 |
|--------------|-----------------------------------------------------------------------------|
| `repo`       | Full name of the repository like {user_name}/{project_name}                                                |
| `base_commit`| Commit to check out                                                         |
| `instance_id`| Unique identifier of the instance                                           |
| `language`   | Main language of the repo |
| `created_at` | (Optional) Creation time of the instance, used to support time-aware environment setup |
| `hints`   | Any hints for setting up the repo you want to give the agent, such as GitHub run checks info |

### Run Config

For the run configuration file, the following fields are supported:

| Field              | Type    |  Description                                                                 |
|--------------------|---------|-----------------------------------------------------------------------------|
| `llm_provider_name`| string  |  Name of the LLM provider (e.g., "OpenAI", "AOAI")                          |
| `print_to_console` | boolean |  Whether to print logs to console                                           |
| `model_config`     | dict  |  Configuration for the LLM model (contains `model_name` and `temperature`)  |
| `workspace_root`   | string  |  Workspace folder for one run                                      |
| `dataset`          | string  |  Path to the dataset file                                                    |
| `instance_id`      | string  |  Specific instance ID to run, null to run all instances in the dataset      |
| `first_N_repos`    | integer |  Limit processing to first N repos (-1 for all repos)                       |
| `max_workers`      | integer |  Number of parallel workers for processing                                   |
| `overwrite`        | boolean |  Whether to overwrite existing results (false will skip existing repos)     |
| `os`               | str     |  which docker image os architecture to build on (default on linux image, can choose windows image)   |
| `max_trials`               | integer     |   how many rounds of setup-verify loop agent can attempt, default 1   |
| `max_steps_setup`               | integer     |   how many steps agent can attemp to setup the environment, default 20   |
| `max_steps_verify`               | integer     |   how many steps agent can attemp to verify the setup, default 20   |
| `timeout`               | integer     |   time limit of each round of setup, default 30 min   |
| `image_prefix`   | prefix of the output_image in the format {namespace}/{dockerhub_repo}, defaults to repolaunch/dev |

### Output

The output will be saved in `{playground_folder}/{instance_id}/result.json` and follows the structure below:

| Field            | Description                                                                                      |
|------------------|--------------------------------------------------------------------------------------------------|
| `instance_id`    | Unique identifier of the instance                                                                |
| `base_image`     | Docker base image                            |
| `setup_commands` | List of shell commands used to set up the environment                                            |
| `test_commands`  | List of shell commands used to run the tests                                                     |
| `duration`       | Time taken to run the process (in minutes)         |
| `completed`      | Boolean indicating whether the execution completed successfully                                  |
| `exception`      | Error message or `null` if no exception occurred                                                 |


### Collect results

```bash
#collect build result
python -m launch.scripts.collect\
    --playground playground/java\
    --output_jsonl data/java.jsonl

# If share built images on docker hub
docker login
python -m launch.scripts.upload_docker\
    --dataset data/java.jsonl
```


## Contributing

This project welcomes contributions and suggestions.  Most contributions require you to agree to a
Contributor License Agreement (CLA) declaring that you have the right to, and actually do, grant us
the rights to use your contribution. For details, visit [Contributor License Agreements](https://cla.opensource.microsoft.com).

When you submit a pull request, a CLA bot will automatically determine whether you need to provide
a CLA and decorate the PR appropriately (e.g., status check, comment). Simply follow the instructions
provided by the bot. You will only need to do this once across all repos using our CLA.

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/).
For more information see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or
contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any additional questions or comments.

## Trademarks

This project may contain trademarks or logos for projects, products, or services. Authorized use of Microsoft
trademarks or logos is subject to and must follow
[Microsoft's Trademark & Brand Guidelines](https://www.microsoft.com/legal/intellectualproperty/trademarks/usage/general).
Use of Microsoft trademarks or logos in modified versions of this project must not cause confusion or imply Microsoft sponsorship.
Any use of third-party trademarks or logos are subject to those third-party's policies.

