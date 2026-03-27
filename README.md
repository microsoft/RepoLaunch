# `🚀 RepoLaunch Agent`

*Turning Any Codebase into Testable Sandbox Environment*

Paper: [RepoLaunch: Automating Build&Test Pipeline of Code Repositories on ANY Language and ANY Platform](https://arxiv.org/abs/2603.05026)

RepoLaunch now supports 
- All mainstram languages : C, C++, C#, Python, Java, Node.js (JS & TS), Go, Rust.
- Building on linux-arch & windows-arch docker images.


## Notifications

RepoLaunch now uses LiteLLM to:
  - ensure compatibility with all mainstream LLM providers
  - enable local LLM deployment for agentic training (RFT, RL) based on launch results

RepoLaunch now still uses traditional Thought-Action format for agent actions, because
  - We find that many smaller open-source LMs cannot handle tool call field well.
  - Thought Action in pure text content field ensures best compatibility and feasibility for smaller open-source LMs.

## Launch your Repository

To use RepoLaunch Agent to launch your repository, please refer to [Development.md](./docs/Development.md)

RepoLaunch can:
1) Install all dependencies and build the repository, delivered as a docker image;
2) Organize the command to rebuild the repository inside the container after modifications;
3) Organize command to test the repository, write a parser to parse test output into testcase-status mapping, and optionally find per-testcase running command.

The basic workflow of RepoLaunch agent is as follows:


![RepoLaunch Workflow](docs/assets/1.png)

## Contributing

### Contributing to RepoLaunch Source Codes

Please refer to [CONTRIBUTING.md](./CONTRIBUTING.md).

### Use RepoLaunch for New Applications

So far the major contribution of RepoLaunch is to create tasks for [SWE-bench-Live](https://github.com/microsoft/SWE-bench-Live), where the creation of SWE-tasks is based purely on scraping GitHub issues and PRs. Now SWE-bench-Live datasets have been used for benchmarking of LLMs and coding agents, and training (SFT/RL) of coding LLMs. 

We encourage new research projects to design new kinds of SWE-tasks, with task creation automated by RepoLaunch.


![RepoLaunch automated SWE dataset creation](docs/assets/2.png)

## Citations

```bibtex
@article{li2026repolaunch,
  title={RepoLaunch: Automating Build\&Test Pipeline of Code Repositories on ANY Language and ANY Platform},
  author={Li, Kenan and Li, Rongzhi and Zhang, Linghao and Jin, Qirui and Zhu, Liao and Huang, Xiaosong and Zhang, Geng and Zhang, Yikai and He, Shilin and Xie, Chengxing and others},
  journal={arXiv preprint arXiv:2603.05026},
  year={2026}
}
```

## Trademarks

This project may contain trademarks or logos for projects, products, or services. Authorized use of Microsoft
trademarks or logos is subject to and must follow
[Microsoft's Trademark & Brand Guidelines](https://www.microsoft.com/legal/intellectualproperty/trademarks/usage/general).
Use of Microsoft trademarks or logos in modified versions of this project must not cause confusion or imply Microsoft sponsorship.
Any use of third-party trademarks or logos are subject to those third-party's policies.

