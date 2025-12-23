# Contributing

## Microsoft Policy

This project welcomes contributions and suggestions. Most contributions require you to
agree to a Contributor License Agreement (CLA) declaring that you have the right to,
and actually do, grant us the rights to use your contribution. For details, visit
https://cla.microsoft.com.

When you submit a pull request, a CLA-bot will automatically determine whether you need
to provide a CLA and decorate the PR appropriately (e.g., label, comment). Simply follow the
instructions provided by the bot. You will only need to do this once across all repositories using our CLA.

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/).
For more information see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/)
or contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any additional questions or comments.

## Contributing Suggestions

1. Welcome issues and PRs related to the bugs and inefficiencies of out agent.

2. We found that many threads created from launch/run.py would have "Result Empty Error", which means the last agent state is not saved to disk and not passed back to the main function in launch/run.py. We think it's mostly because docker commit in save.py takes too long time (usually 10min - 120 min) -- it will return read timeout and so often make the thread DEAD... Future works would make docker commit detached in a separate thread/process to solve the problem. Maybe there's also problem in docker concurrency and old Langchain agent apis... Please help us find that problem and fix it!

3. In [launch/utilities/language_handlers.py](launch/utilities/language_handlers.py), you can see language-specific and operating-system-specific prompts and base images. 
Please help us improve these prompts and add new base images. 
Base images need update when the latest version of a language updates. 
Please add official new images if official sources provide them; 
otherwise you could help us build customized ones and upload to dockerhub public repos, there are example dockerfiles in [launch/utilities/dockerfiles](launch/utilities/dockerfiles).

4. To improve the success rate / lower down early submit hallucination (unsuccessful build but submit) in the setup stage; 
and increase the extraction coverage of per-testcase status and per-testcase command from test log in the organize stage -- any suggestions and improvements to the agent workflow is welcome.

