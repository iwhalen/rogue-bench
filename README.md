# Rogue-Bench

This is a work in progress repository that forked my original project [here](https://github.com/iwhalen/rogomatic-llm).

It focuses more on portability and making the proof of concept into a real agent benchmark.

If you just want to play Rogue, see the [Rogue Collection](https://github.com/mikeyk730/Rogue-Collection).

My to do list is:
- [x] Dockerize Rogue Collection for portability
- [x] Implement headless version of Rogue for performance reasons
- [ ] Determine how to and then implement run seeding / saving
- [ ] Determine how to implement run saving in headless mode and when running in dockerized mode
- [ ] Reimplement the Rogue environment as a `gymnasium` environment
- [ ] Determine how to output score as the "reward" signal (is it just total gold?)
- [ ] Make it easier to add custom agents / agent harnesses

## Quickstart

Rogue-bench has been tested locally on (WSL2) Ubuntu 24.04 and also provides a Docker setup.

Both are available through `make` commands.

### Local

To run locally on Ubuntu 24.04, execute:

``` bash
git clone --recursive https://github.com/iwhalen/rogue-bench.git 
make install  # Install system level dependencies
make build
uv run rogue-bench --player human
```

This will start a "human" session where you can control Rogue with keyboard inputs.

### Docker

To run in Docker, execute:

``` bash
git clone --recursive https://github.com/iwhalen/rogue-bench.git
make build-docker
make docker-run ARGS="--player human"
```

Again, this will start in "human" mode.
