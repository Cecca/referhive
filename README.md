# ReferHive

A referee for Hive tournaments

## Building the bundled containers

You need to have `docker` installed in order to build and run the containers. For convenience there are a couple of container definitions bundled in this repo that you can build using a single command based on [`just`](https://just.systems/)

```
just build-all
```

## Setting up a tournament

Create a file (for instance [`tournament.txt`](https://github.com/Cecca/referhive/blob/bddab62598ee1c8f356164d862ce7122769cfbdf/tournament.txt)) that contains games to be played, one per line. Each line should contain the names of two `docker` images implementing the battling bots.
Lines starting with a `#` are ignored.

The tournament is then played by running

```
python main.py tournament.txt
```

The execution updates (and creates if needed) a sqlite database `games.db` that records the outcome of each game, along with the game string to replay it.
