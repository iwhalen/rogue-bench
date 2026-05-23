# Leaderboard

!!! Example "Experimental"

    This page is very much a work in progress!

    Only small models have been tested and the experimental methodology is not exactly set in stone.

    If you'd like to donate some credits or suggest an improvement, please [get in touch](https://github.com/iwhalen/rogue-bench/issues). 


Below, score refers to how much gold an agent picked up.

## 10 minute bracket

Each result here had a 10 minute time limit to accumulate as high a score as possible.

Note that Rog-O-Matic is slightly better than human expert performance. 

All runs were tested on seed 0 with 5 replicates.

| Model | Harness | Max score (n=5) | Results folder |
| :--:  | :--:          | :---:              | :---:          |
| Rog-O-Matic[^rogomatic-note] | Rog-O-Matic | 923 | [Link](https://github.com/iwhalen/rogue-bench/tree/main/results/rogomatic) |
| Deepseek V4 Flash | `naive.NaiveAgent` | 23 | [Link](https://github.com/iwhalen/rogue-bench/tree/main/results/deepseek-v4-flash) |
| Claude Haiku 4.5 | `naive.NaiveAgent` | 5 | [Link](https://github.com/iwhalen/rogue-bench/tree/main/results/claude-haiku-4-5) | 
| Gemini 3 Flash | `naive.NaiveAgent` | 5 | [Link](https://github.com/iwhalen/rogue-bench/tree/main/results/gemini-3-flash) | 
| Kimi K2.6 | `naive.NaiveAgent` | 5 | [Link](https://github.com/iwhalen/rogue-bench/tree/main/results/kimi-k2-6) | 
| GPT-5-4-mini | `naive.NaiveAgent` | 0 | [Link](https://github.com/iwhalen/rogue-bench/tree/main/results/gpt-5-4-mini) |

??? Note "Click to reveal run details"

    **Rog-O-Matic**

    ```
    Runs: 5
    Max score over 5 runs: 923

    Metric             n  median  mean     min    max  
    -----------------  -  ------  -------  -----  -----
    Score              5     465      510    254    923
    Dungeon level      5       5      5.8      4      9
    Gold               5     517    567.2    283  1,026
    Experience level   5       5        5      4      6
    Experience points  5      89    139.4     40    295
    Keys pressed       5   3,422  4,783.4  2,127  9,239
    Total tokens       0       -        -      -      -
    Input tokens       0       -        -      -      -
    Output tokens      0       -        -      -      -
    Cache read tokens  0       -        -      -      -
    Agent turns        0       -        -      -      -

    Amulet found: 0/5
    Terminations: completed=5

    #  Run                       terminated  score  dlvl  gold   xp   keys   turns  tokens
    -  ------------------------  ----------  -----  ----  -----  ---  -----  -----  ------
    1  2026-05-22T22.02.09.111Z   completed    256     5    285   40  2,127      -       -
    2  2026-05-22T22.03.07.400Z   completed    923     9  1,026  295  9,239      -       -
    3  2026-05-22T22.05.07.137Z   completed    254     4    283   89  3,422      -       -
    4  2026-05-22T22.05.29.052Z   completed    652     7    725  206  6,549      -       -
    5  2026-05-22T22.06.22.650Z   completed    465     4    517   67  2,580      -       -
    ```

    **Deepseek V4 Flash**

    ```
    Runs: 5
    Max score over 5 runs: 23
    Model: openrouter:deepseek/deepseek-v4-flash

    Metric             n  median   mean       min     max    
    -----------------  -  -------  ---------  ------  -------
    Score              5        0        5.6       0       23
    Dungeon level      5        1        1.4       1        2
    Gold               5        0        6.4       0       26
    Experience level   5        1          1       1        1
    Experience points  5        2        3.6       2        9
    Keys pressed       5      172      212.8      42      397
    Total tokens       5  105,286  165,435.6  39,681  309,283
    Input tokens       5  102,248  161,247.2  38,282  302,121
    Output tokens      5    3,038    4,188.4   1,399    7,162
    Cache read tokens  5   68,096     66,560  25,856  103,936
    Agent turns        5       25       31.6      13       49

    Amulet found: 0/5
    Terminations: stalled_position=4, completed=1

    #  Run                       terminated        score  dlvl  gold  xp  keys  turns  tokens 
    -  ------------------------  ----------------  -----  ----  ----  --  ----  -----  -------
    1  2026-05-23T14.51.45.051Z  stalled_position     23     2    26   3   397     49  283,781
    2  2026-05-23T14.54.55.449Z         completed      0     1     0   2    42     13   39,681
    3  2026-05-23T14.55.35.720Z  stalled_position      0     2     0   2   172     25  105,286
    4  2026-05-23T14.57.19.297Z  stalled_position      5     1     6   9   348     49  309,283
    5  2026-05-23T15.02.31.620Z  stalled_position      0     1     0   2   105     22   89,147
    ```

    **Claude Haiku 4.5**

    Interestingly, Haiku was actually pretty good at Rogue. As you can see, it always timed out rather than getting stuck like GPT-5.4-mini.

    This was surprising, as I consider GPT-5.4-mini a stronger model. 

    ```
    Runs: 5
    Max score over 5 runs: 5
    Model: anthropic:claude-haiku-4-5

    Metric             n  median   mean       min      max    
    -----------------  -  -------  ---------  -------  -------
    Score              5        5          4        0        5
    Dungeon level      5        1        1.2        1        2
    Gold               5        6        4.8        0        6
    Experience level   5        1          1        1        1
    Experience points  5        6        6.2        5        9
    Keys pressed       5      129        143      106      230
    Total tokens       5  524,860  527,191.4  505,322  550,852
    Input tokens       5  517,319  520,915.8  500,104  544,691
    Output tokens      5    6,161    6,275.6    5,218    7,541
    Cache read tokens  5        0          0        0        0
    Agent turns        5       62         64       59       77

    Amulet found: 0/5
    Terminations: timeout=5

    #  Run                       terminated  score  dlvl  gold  xp  keys  turns  tokens 
    -  ------------------------  ----------  -----  ----  ----  --  ----  -----  -------
    1  2026-05-22T19.27.07.799Z     timeout      5     1     6   9   230     77  524,860
    2  2026-05-22T20.27.50.894Z     timeout      0     2     0   6   135     62  546,697
    3  2026-05-22T20.37.51.085Z     timeout      5     1     6   5   115     60  505,322
    4  2026-05-22T20.47.51.246Z     timeout      5     1     6   5   106     59  508,226
    5  2026-05-22T21.39.35.254Z     timeout      5     1     6   6   129     62  550,852
    ```

    **Gemini 3 Flash** 

    A few of these runs actually ended due to 

    ```
    Runs: 5
    Max score over 5 runs: 5
    Model: google-gla:gemini-3-flash-preview

    Metric             n  median   mean       min     max    
    -----------------  -  -------  ---------  ------  -------
    Score              5        5          3       0        5
    Dungeon level      5        1        1.2       1        2
    Gold               5        6        3.6       0        6
    Experience level   5        1          1       1        1
    Experience points  5        6        4.6       2        7
    Keys pressed       5       82       97.8      23      154
    Total tokens       5  171,291  175,169.8  27,182  292,104
    Input tokens       5  168,066  171,439.4  24,224  288,139
    Output tokens      5    3,225    3,730.4   2,958    5,544
    Cache read tokens  5   47,504   43,838.8       0   73,363
    Agent turns        5       35       34.2      10       53

    Amulet found: 0/5
    Terminations: completed=3, stalled_position=2

    #  Run                       terminated        score  dlvl  gold  xp  keys  turns  tokens 
    -  ------------------------  ----------------  -----  ----  ----  --  ----  -----  -------
    1  2026-05-22T23.01.41.597Z         completed      0     2     0   2    79     23   99,070
    2  2026-05-23T14.03.28.539Z         completed      5     1     6   6    82     35  171,291
    3  2026-05-23T14.04.14.966Z  stalled_position      5     1     6   6   154     53  292,104
    4  2026-05-23T14.05.24.190Z         completed      0     1     0   2    23     10   27,182
    5  2026-05-23T14.05.46.799Z  stalled_position      5     1     6   7   151     50  286,202
    ```

    **Kimi K2.6**

    ```
    Runs: 5
    Max score over 5 runs: 5
    Model: openrouter:moonshotai/kimi-k2.6

    Metric             n  median   mean       min     max    
    -----------------  -  -------  ---------  ------  -------
    Score              5        0          2       0        5
    Dungeon level      5        2        1.8       1        2
    Gold               5        0        2.4       0        6
    Experience level   5        1          1       1        1
    Experience points  5        3        3.8       2        7
    Keys pressed       5      233      240.2      44      433
    Total tokens       5  122,759  150,535.2  37,576  325,983
    Input tokens       5  116,862  141,163.2  33,599  304,910
    Output tokens      5    5,897      9,372   3,977   21,073
    Cache read tokens  5   75,168   73,998.4  22,816  127,571
    Agent turns        5       29       33.8      13       66

    Amulet found: 0/5
    Terminations: timeout=3, stalled_position=2

    #  Run                       terminated        score  dlvl  gold  xp  keys  turns  tokens 
    -  ------------------------  ----------------  -----  ----  ----  --  ----  -----  -------
    1  2026-05-23T15.22.37.786Z  stalled_position      0     2     0   2   159     13   37,576
    2  2026-05-23T15.24.36.665Z           timeout      0     2     0   3   332     42  202,598
    3  2026-05-23T15.34.36.823Z           timeout      5     2     6   7   433     66  325,983
    4  2026-05-23T15.44.37.008Z           timeout      0     2     0   2    44     19   63,760
    5  2026-05-23T15.54.37.162Z  stalled_position      5     1     6   5   233     29  122,759
    ```

    **GPT-5.4-mini**

    Note that "stalled_position" means the player's position didn't change for 50 turns.

    ```
    Runs: 5
    Max score over 5 runs: 0
    Model: openai:gpt-5.4-mini

    Metric             n  median     mean         min      max      
    -----------------  -  ---------  -----------  -------  ---------
    Score              5          0            0        0          0
    Dungeon level      5          1          1.4        1          2
    Gold               5          0            0        0          0
    Experience level   5          1            1        1          1
    Experience points  5          3            3        2          4
    Keys pressed       5        364        346.4      161        571
    Total tokens       5  1,247,165  1,153,628.6  610,545  1,640,721
    Input tokens       5  1,222,981  1,132,704.8  599,423  1,612,095
    Output tokens      5     24,184     20,923.8   11,122     28,626
    Cache read tokens  5     40,960       40,448   38,400     41,984
    Agent turns        5        349        303.6      156        423

    Amulet found: 0/5
    Terminations: stalled_position=4, timeout=1

    #  Run                       terminated        score  dlvl  gold  xp  keys  turns  tokens   
    -  ------------------------  ----------------  -----  ----  ----  --  ----  -----  ---------
    1  2026-05-22T01.07.24.283Z           timeout      0     2     0   4   571    423  1,640,721
    2  2026-05-22T01.17.24.485Z  stalled_position      0     1     0   2   221    195    763,528
    3  2026-05-22T01.21.55.822Z  stalled_position      0     1     0   2   161    156    610,545
    4  2026-05-22T01.25.30.304Z  stalled_position      0     1     0   3   415    395  1,506,184
    5  2026-05-22T01.34.12.628Z  stalled_position      0     2     0   4   364    349  1,247,165
    ```

## Reproduction

Of course, there's no _real_ way to reproduce these results. Due to the stochastic nature of LLMs, one would never get the same exact outcome at this leaderboard.

To provide as much of a paper trail as possible, result folders are provided in the Github repo.

If you would like to run any of these for yourself, you can use the `run-serial.py` to run back-to-back tests without having to sit at your computer.

``` bash 
uv run scripts/run-serial.py --n-replicas 5 \
    --player agent \
    --agent-class naive.NaiveAgent \
    --agent-config config/claude-haiku-4-5.json \
    --output-path results/claude-haiku-4-5 \ 
    --versioned \
    --timeout 600 \
    --action-delay 0 \
    --seed 0
```

Replace the config and output paths at your discretion. 

To analyze an output directory, us the `analyze-runs.py` script:

``` bash
uv run scripts/analyze-runs.py results/claude-haiku-4-5
```

See the [CLI docs](cli.md) for more on how to run replays.

[^rogomatic-note]: Each run has a randomly seeded initial genome and no shared memory between runs. For more on Rog-O-Matic, see [here](https://www.cs.princeton.edu/~appel/papers/rogomatic.html).
