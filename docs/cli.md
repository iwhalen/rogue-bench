# CLI

This page explains the Rogue-Bench CLI in more depth.

Of course, you can run `rogue-bench --help` for the short version of this information.

## TL;DR

If you are experimenting with LLMs in Rogue, most of your commands will look like:

``` bash
rogue-bench --player agent \ 
  --agent-class naive.NaiveAgent \
  --agent-config config/naive.json \
  --output-path results/gpt-5-4-mini/ \ 
  --versioned \ 
  --seed 0
```

Read on for more specific documentation.

## Running Rogue

Rogue-Bench can be run in two modes: local and Docker. They differ only by where the Rogue executable is running. 

### Local mode

In local mode, the Rogue executable is running directly on your computer. 

You first have to have system-level dependencies installed and the Rogue executable compiles to run in local mode. To carry this out, run: 

``` bash
git clone --recursive https://github.com/iwhalen/rogue-bench.git 
cd rogue-bench
make install
make build
```

No extra options are needed to run in local mode.

### Docker mode

!!! example "Experimental"
    
    Note that more extensive testing has been done on local mode. Docker mode works in most cases but still may have some unexpected bugs.

    If you find any problems, please open an [issue](https://github.com/iwhalen/rogue-bench/issues). 

In docker mode, the Rogue executable is running in a Docker container. 

You'll first need Docker installed. See [here](https://www.docker.com/get-started/) for a guide on getting started with Docker.

Then, build the docker image with:

``` bash
make build-docker
```

This will create a new docker image named `rogue-bench` by default. Then, when running any command, specify the `--docker-image rogue-bench` option.

For example, running in human mode will look like:

``` bash
uv run rogue-bench --docker-image rogue-bench --player human
```

## Player types

There are currently three player types for executing Rogue runs: human, agent, and Rog-O-Matic.

### Human

As its name suggests, this puts you (the human) in control of Rogue.

``` bash
rogue-bench --player human 
```

Everything works the same here on gathering statistics and replay data. Read on for more information on this.

Of course, if you only want to play Rogue, head to the [Rogue Collection](https://github.com/mikeyk730/Rogue-Collection) instead. Other options for Rogue can be found hosted on various retro gaming sites or on [Steam](https://store.steampowered.com/app/1443430/Rogue/). 

### Agent

This type of player outputs actions through a programmatic interface.

The only agent player currently implemented is `NaiveAgent`.

#### `NaiveAgent`

`NaiveAgent` uses an LLM with a fixed history length and simple system prompt to output commands.

To run `NaiveAgent`, execute:

``` bash
rogue-bench --player agent \
  --agent-class naive.NaiveAgent \
  --agent-config config/naive.json
```

The `--agent-class` option is an import path to a `RogueAgent` subclass. Short paths are resolved under `rogue_bench.agent`, so `naive.NaiveAgent` loads `rogue_bench.agent.naive.NaiveAgent`.

The `--agent-config` option should point to a JSON file. For `NaiveAgent`, the config fields are:

- `model`: Pydantic AI model string.
- `max_history`: number of prior request/response pairs to keep.
- `retries`: number of attempts for a model call before failing.

You can also set `--action-delay` to slow down the keystrokes sent back to Rogue.

To extend `NaiveAgent` or add your own `Agent`, see [here](add-an-agent.md).

!!! info 

    Any LLM API keys are expected to be provided through a `.env` file (or already in the environment). `python-dotenv` is used under the hood to read `.env` files.

    Under the hood, Pydantic AI is used to define agents. For more on Pydantic AI supported providers, see [here](https://pydantic.dev/docs/ai/models/overview/). 

### Rog-O-Matic

Rog-O-Matic runs the classic Rogue bot instead of an LLM agent.

``` bash
rogue-bench --player rogomatic
```

Rog-O-Matic can also be run in Docker mode:

``` bash
uv run rogue-bench --docker-image rogue-bench --player rogomatic
```

Use `--seed` to replay a specific Rogue seed:

``` bash
rogue-bench --player rogomatic --seed 1234
```

The `--rogomatic-config` option should point to a JSON file. For Rog-O-Matic, the config fields are:

- `fresh_run`: delete Rog-O-Matic's local `rlog/` directory before starting.
- `use_ltm`: allow long-term-memory files across runs.
- `genes`: 8 fixed Rog-O-Matic knobs instead of the gene pool.
- `random_gene_seed`: seed used for gene generation/selection. If this is omitted, `--seed` is used.

For example:

``` bash
rogue-bench --player rogomatic \
  --seed 1755847237 \
  --rogomatic-config config/rogomatic.json
```

When `--output-path` is set, Rogue-Bench saves the normal run files and also copies Rog-O-Matic's debug files when they are available:

- `rogomatic.log`
- `rogomatic.frogue`

For more on Rog-O-Matic, see [here](https://www.cs.princeton.edu/~appel/papers/rogomatic.html).

Rog-O-Matic is specified as its own player as it requires quite a few hacks to get working. Check out the source for more.

## Run options

These options can be combined with the player types above.

### `--rogue-path`

Path to the local `rogue-collection-headless` executable. This is used for local runs and replays, but not Docker mode.

``` bash
rogue-bench --rogue-path ./rogue-collection/build/release/rogue-collection-headless
```

### `--action-delay`

Seconds to wait between actions in agent mode. This makes watching an LLM-based agent a little more readable. 

``` bash
rogue-bench --player agent \
  --agent-class naive.NaiveAgent \
  --action-delay 0.1
```

### `--seed`

RNG seed for the Rogue game. If this is omitted, the current time will be used.

``` bash
rogue-bench --player human --seed 1234
```

### `--output-path`

Directory for recording a run. Rogue-Bench creates it if needed.

``` bash
rogue-bench --player rogomatic --output-path runs/rogomatic-1234
```

### `--versioned`

Append a timestamped subdirectory under `--output-path`.

``` bash
rogue-bench --player rogomatic \
  --output-path runs/rogomatic \
  --versioned
```

### `--timeout`

Maximum wall-clock seconds for one game run. The default is 1200 seconds.

``` bash
rogue-bench --player agent \
  --agent-class naive.NaiveAgent \
  --timeout 300
```

## Replay options

When `--output-path` is provided, Rogue-Bench writes a `game.sav` file. That file stores the game name, seed, and keylog needed to reconstruct the run.

### `--input-path`

Directory containing a `game.sav` file. This starts replay mode.

``` bash
rogue-bench --input-path runs/rogomatic-1234
```

`--input-path` cannot be used with `--output-path`.

If the directory also contains `playback.json` from an agent run, replay shows the "actions" and "reasoning" panels from the original run.

Docker mode works for replay too:

``` bash
uv run rogue-bench \
  --docker-image rogue-bench \
  --input-path runs/rogomatic-1234
```

### `--replay-speed`

Seconds to wait between recorded keystrokes during visual replay.

``` bash
rogue-bench --input-path runs/rogomatic-1234 --replay-speed 0.02
```

### `--no-display`

Skip visual replay and print final statistics as JSON.

``` bash
rogue-bench --input-path runs/rogomatic-1234 --no-display
```
