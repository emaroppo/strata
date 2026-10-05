# 43. A machine reaches several modelling hosts, and a project names its own

**Status:** accepted; extends records 0007 and 0020

## The decision

`config.toml` may describe several modelling hosts as `[modelling.<name>]`
tables layered on the flat `[modelling]` keys, one of them the default, the
same shape as `[catalog]` (record 0020). A flat `[modelling]` alone is one
unnamed host, as before. A project may name the host that trains it in
`[model] host`; a command's `--host` overrides that, and with neither the
machine's default is used. An unknown name is refused with the list of the
ones that exist, and several hosts with no default is refused at the point
of use rather than resolved.

Each named host's token comes from `$STRATA_MODELLING_TOKEN_<NAME>`, then
`$STRATA_MODELLING_TOKEN` for all of them. `$STRATA_MODELLING_URL` stands in
for the flat url only, and is refused when several hosts are named, since
it could replace any of them.

## Why the project names it

A run and its checkpoint live on the host that trained it (record 0007),
and the next round's parent is chosen there. Asking another host for the
project's latest run is not an error: it answers about a different chain,
or an older one, and a push then ranks the review queue with a model that
is not the one just trained. Nothing raises. So which host holds a job's
runs is part of the job, as which catalog it draws from is, and it travels
in `project.toml`. Where each host *is* stays in `config.toml`.

## Why --host as well

A second host is also for trying a model somewhere else, or for training
while the usual one is busy (one job at a time per host, record 0007). That
is a decision about one command, not the job. The override says so out
loud, and the project's runs on the other host stay where they are.

## Consequences

- `catalog-check` asks every modelling host described, since each is one
  more machine that can be left on the old catalog.
- A round watched from one host is reattached with the same `--host`; the
  hint printed on interrupt includes it.
- A host whose url is empty is this machine, so a project can name local
  training explicitly on a machine where the default is remote.
