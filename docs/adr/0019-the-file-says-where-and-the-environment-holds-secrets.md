# 19. The file says where, the environment holds secrets, and every process reads the same file

**Status:** accepted

## The decision

One module describes catalogs and opens them, and the CLI, the blob server and
the modelling host all read a catalog through it. `config.toml` says where
things are and nothing about a job; the machine's secrets come from the
environment. A service refuses to start rather than start degraded. The
modelling host reads the CLI's own `config.toml` and trains from its default
catalog; pointing it at another catalog is changing that default and
restarting.

## Why one module

Three processes reading a catalog three ways is how one of them drifts. The
blob server, the modelling host and every command open a catalog through the
same function from the same file format, so the two cannot read a catalog
differently, and a catalog is opened per request on the host because a
long-lived remote connection goes stale.

## Why the file holds no secret and no secret holds a location

The file is copied between machines, so a secret in it is a secret on every
machine. A location in the environment would silently override the file, and a
switch made in the file would be undone by a variable exported in some shell,
with the host quietly reading the old catalog; so locations are never read from
the environment. Credentials are out of `repr`, since a config printed while
troubleshooting gets pasted into chats. Flat `[catalog]` keys layer under the
named tables so an endpoint is stated once.

## Why a catalog reads its own credentials first

A named catalog takes `$STRATA_BLOB_SECRET_ALT` for `[catalog.alt]`
before `$STRATA_BLOB_SECRET`, and the same for the two S3 keys: the variable
suffixed with its name, the way a modelling host's token is, then the shared
one. With only the shared names, every catalog a shell describes signs and
reads with the same values, so two catalogs kept apart on purpose — their own
bucket, their own key, their own blob server — are one secret apart from each
other again, and labelling one means re-exporting the other's secret by hand.
A catalog with none of its own takes the shared one, which keeps a host with
one catalog as it was; a server it does not belong to then refuses its URLs,
and a key it does not hold is refused by the bucket. The flat `[catalog]` has
no name to suffix and reads only the shared ones.

## Why a service refuses to start

Without a signing secret the blob server would serve the corpus to anyone who
guesses a URL; without an index it would answer 404 to everything; and both
look healthy from outside. A missing config file is an error for a service
where it is a default for a command, because the service would serve an empty
catalog, which reads as "the catalog is empty". The bootstrap exits with a
distinct code so a supervisor reports rather than restarting forever, and
listens on every interface so another machine can reach it.

## Consequences

- The index URL in the file carries no password; `$PGPASSWORD` supplies it,
  which is easy to miss and is what the remote commands say when it is.
- The modelling host has no run store fallback to guess from; its
  `STRATA_RUNS_URL` is stated.
- Migrations read the same tables and the same environment as every reader.
- A command given no `--config` reads the file `$STRATA_CONFIG` names, then
  `./config.toml`: the same variable a service reads, so a host states its
  file once and a project directory carries no copy. A variable naming a
  missing file is refused rather than defaulted.
