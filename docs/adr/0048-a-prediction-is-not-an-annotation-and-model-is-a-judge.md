# 48. A prediction is not an annotation, and the `model` source is a judge

**Status:** proposed; amends records 0009 and 0027

## The decision

A prediction stays in the run store. It never becomes an annotation by
being made. An annotation is an answer from something that dealt with
the sample: a person (`human`), an import (`import`), or a model
judging what was predicted (`model`). An annotation written by a run
carries that run's id.

## What this amends, and why

- **Record 0009 ranked `model` lowest and never said what it was.**
  Nothing in strata writes it. The obvious reading, a model's
  predictions written as answers, would break the rest of 0009: the
  queue is the samples with no current row (records 0009, 0012). Writing
  predictions as answers would empty that queue of every sample a model
  had seen, and would store each prediction twice. So `model` is defined
  as a judgement, which is the reading that fits 0009's own idea of an
  answer.
- **Record 0027 gave an annotation a `batch` and nothing naming the
  process that wrote it.** A judge's verdict, or an imported answer, is
  only as good as the process behind it. That process needs to be
  recorded where the answer is. So an annotation gains a `run_id`.
  `batch` keeps the meaning 0027 gave it: the import an answer first
  arrived in, carried onto the row that confirms or corrects it.

## Why a prediction stays a prediction

A prediction lives in the run store. It is a function of the sample's
checksum, the run, and the feature digest, and it is never invalidated
(record 0006). The run fixes the checkpoint behind it, so a prediction
already says exactly what made it. Whatever reads predictions names the
run, as a run names the runs it read (record 0045).

## What each source is

| Source | What it is |
|---|---|
| `human` | A person's answer |
| `import` | An answer the corpus arrived with, one brought from another catalog, or one a stopgap rule produced (see below) |
| `model` | A **judgement**: a model reading what was predicted, or the sample itself, and giving a verdict. An LLM judging a span model's output is the case that argued it. |

A judge is a reviewer that happens to be a model. Its answer outranks
nothing and is outranked by everything. Like an import, it is trusted
until a person looks. A person's spot check is what measures it (record
0028). The emails demo already works this way: an LLM reads every
grouped message and gives a verdict, and the verdicts are reported as
the judge's until a person checks them. What it keeps in ignored files
belongs here.

## What a run that writes answers records

An import run and a judge run each carry their id onto every row they
write. A judge run's spec records:

- the model, by name and digest;
- the prompt, by digest;
- the host;
- the prediction runs it judged.

A person's answer has no run. It keeps its source and its batch.

## Consequences

- **`annotation` gains a nullable `run_id`,** in record 0045's
  migration.
- **No code path writes a prediction as an annotation.** Pre-labelling
  in Label Studio still shows predictions, and an answer exists only
  once a person gives it.
- **A judged sample leaves the review queue as an imported one does,**
  and a spot check measures the judge (record 0028).

## Why a rule's answer has no source of its own

Marking disclaimers and footers by pattern produces answers that
neither arrived with a corpus nor came from another catalog. They are
written as `import`, because a rule is trusted until a person looks, as
an import is.

A `rule` source was considered and turned down. The patterns are a
stopgap until a model is trained to mark boilerplate. That model's
output follows the standard path: predictions in the run store, made
answers by a person or a judge. A source made for the stopgap would
outlive it. The run that writes rule answers still carries its id, and
its spec names the rule file by digest, so the answers say exactly what
made them.
