# Rogue-Bench

This is a work in progress repository that forked my original project [here](https://github.com/iwhalen/rogomatic-llm).

It focuses more on portability and making the proof of concept into a real agent benchmark.

If you just want to play Rogue, see the [Rogue Collection](https://github.com/mikeyk730/Rogue-Collection).

My to do list is:
- [x] Dockerize Rogue Collection for portability
- [x] Implement headless version of Rogue for performance reasons
- [x] Determine how to and then implement run seeding / saving
- [x] Determine how to implement run saving in headless mode and when running in dockerized mode
- [ ] Determine how to output score as the "reward" signal (is it just total gold? Gold + amulet?)
- [ ] Implement Rogomatic as an agent
- [ ] Implement LLM agent with pydantic ai
- [ ] Make it easier to add custom agents / agent harnesses
- [ ] Implement rogue-bench as a `verifiers` environment

## Quickstart

Rogue-Bench has been tested locally on (WSL2) Ubuntu 24.04 and also provides a Docker setup.

### Local

To run locally on Ubuntu 24.04, execute:

``` bash
git clone --recursive https://github.com/iwhalen/rogue-bench.git 
make install  # Install system level dependencies
make build  # Compile the custom headless Rogue executable
uv run rogue-bench --player human
```

This will start a "human" session where you can control Rogue with keyboard inputs.

For all command line options, see:

``` bash
uv run rogue-bench --help
```

### Docker

To run in Docker, execute:

``` bash
git clone --recursive https://github.com/iwhalen/rogue-bench.git
make build-docker
uv run rogue-bench --docker-image rogue-bench --player human
```

Again, this will start in "human" mode.

## License

Note that the code for running Rogue-Bench in this repository is offered under the GPL-3.0 license.

The modified Rogue executables are under the same license(s) as the [Rogue Collection](https://github.com/mikeyk730/Rogue-Collection). At the time of writing, this is a mix of GPL-3.0 and other licenses. 
