# 54. A model makes labels or media, and a run keeps every checkpoint it saved

**Status:** proposed; amends records 0005, 0006 and 0041; builds on
records 0052 and 0053

## The decision

`Model` becomes the parent of two siblings. Each declares what it learns
from and what it makes:

```python
class Model(ABC):                  # what every trainable model shares
    version, requires_features
    save(path), load(path)

class LabelModel(Model):           # learns a label set, makes predictions
    label_type, requires_classes, requires_schema
    finetune(train, classes, val, on_epoch, save_checkpoint)
    predict(paths, on_batch, *, features) -> predictions

class MediaModel(Model):           # learns from samples, makes new media
    trains_on                      # a sample type, such as SFTTextExample
    finetune(train, val, on_epoch, save_checkpoint)
    generate(inputs, settings, seeds, on_batch) -> outputs
```

A `LabelModel` is today's `Model`, unchanged but for its base class and
the new optional hook. A `MediaModel` trains on samples of the type it
names. Its output becomes `GeneratedMedia` samples (record 0053), never
predictions.

A run keeps every checkpoint its model saved, not only the last. Each
is evaluated. Anything that uses a model names the checkpoint, or gets
the run's last.

strata-modelling gains a `text-sft` baseline: a LoRA fine-tune of a
causal language model on `SFTTextExample` samples. A project supplies
its prompt template, its system prompt and any metrics of its own.

## What this amends, and why

- **Record 0041 made a model's `label_type` the shape it learns from
  and emits. That now holds for a `LabelModel` only.** A model that
  writes text learns from samples, not from a label set. The label set
  on an SFT dataset is the verdicts, which chose the samples and are
  not what the model learns. So a `MediaModel` names a sample type
  instead, and training checks every manifest sample's type against it
  (record 0052 puts the type in the manifest).
- **Record 0005 gave a run one checkpoint. A run now has a checkpoint
  per save.** A LoRA's best epoch is found by evaluating each one, and
  doing that as one run per epoch count trains the same first epochs
  over and over. The run's chain, its id and its record are unchanged.
- **Record 0006 keyed a prediction on the run, the checksum and the
  feature digest. The key gains the checkpoint.** The property 0006
  argued for is that a prediction is a function of fixed weights and
  fixed bytes, so it is never stale. With several checkpoints a run no
  longer fixes the weights. Adding the checkpoint to the key keeps the
  property literally true.

## Why two siblings, and not one class with optional parts

Training fits both. An `Example` is a path, a target and features, and
for an SFT sample the path is the target output and the features are
the input. What differs is everything around training:

- **What is checked before the round.** A label type against the label
  set, or a sample type against the samples.
- **What it makes.** A prediction is about a sample that exists, and it
  stays in the run store (record 0048). A generated text is a new
  sample, and starts from an input alone, with no path to predict on.
- **What a class list means.** A `LabelModel` is trained on classes. A
  `MediaModel` has none, so `classes` is not in its `finetune`.

One class with `predict` or `generate`, and `label_type` or
`trains_on`, would be a class in which every reader asks which one it
is. Two siblings answer that by type, and the handler checks what each
declares.

`finetune` is declared on each sibling, not the parent, so a
`LabelModel`'s signature does not change. Moving a model costs one line.

## Why a model subclassing `Model` directly is refused

As record 0041 refused the old `task`: accepting both would keep a
fallback alive for as long as any old plugin exists, and a direct
subclass would quietly mean "a label model". The handler refuses one,
and the message names the fix, `class X(LabelModel)`. Every model today
moves: the GLiNER tagger, the transformer text base and the image
classifier in strata-modelling, the plant demo's classifier, and the
test models.

## What a media model is told, and what it records

**The input is features.** A feature is "something already known that
it may be told" (record 0011), which is what an SFT input is. The SFT
type names its input fields, and a freeze over it writes them as
features. A project does not declare them again. Each sample carries
exactly one input, since a freeze leaves out a sample whose origins
disagree (record 0053).

**The prompt template and the system prompt are run parameters.** The
template is a format string over the input fields. The run records the
values actually used, the plugin's defaults included, so a changed
default can never change what a recorded run means. A template naming
a field the input does not carry is refused before the round, as
`requires_features` refuses today. The base model's own chat template
comes with the base model, which the run also records.

**Generating returns outputs and writes nothing.** A generate request
names the run and the checkpoint, and gives the inputs, the settings
and the seeds. An input is values, and may also name samples by role,
passed as paths, as predict is given them: the text to summarise, the
images to combine. It returns each output, whether it ended on its own
or at the token limit, the digest of the settings that made it, and its
seed. Modelling never sees the catalog (record 0004). The caller knows
which samples it passed, so it commits the outputs as a generate run
(record 0053), with an origin row per input sample and its role, taking
the template and system prompt from the training run.

## Why a run keeps every checkpoint

`finetune` is handed `save_checkpoint(name)`, optional like `on_epoch`.
The handler passes it only to a `finetune` that accepts it, so no
existing model has to change for it.
A model that calls it after each epoch gets a checkpoint per epoch. One
that never calls it gets one at the end, as now, so a GLiNER run does
not start writing half a gigabyte per epoch unless it asks to. A LoRA
adapter is small enough to keep every epoch.

The run store gains a `checkpoint` table: run, name (`epoch-2`), path,
digest and when it was saved. The migration gives every existing run
one row, from its current column.

**Every checkpoint is evaluated.** The evaluate stage scores each of a
run's checkpoints. A metric row records its checkpoint, and the report
shows them side by side.

**Using a model names a checkpoint.** A predict request, a generate
request and a warm start from a parent run each name one, or get the
run's last. A generation record names it by name as well as by digest
(record 0053).

## How a generator is evaluated

A generated body is not wrong for differing from the real one. Many
bodies fit one subject. So a generator is scored on what its outputs
are, not on matching an answer. The evaluate stage generates one output
for each validation sample's input, and scores the outputs.

A **`generation` task** in strata-evaluation holds what any text
generator is scored on:

- **ended:** the share that stopped on their own rather than at the
  token limit;
- **distinct 1-, 2- and 3-grams** across outputs;
- **the longest run of words** shared with any training body, as a
  median, a 90th percentile and a maximum (memorisation).

A project's own checks are a metrics plugin (record 0042). Phishnet's
know its placeholder format, so they live in strata-phishnet: flags
honoured, placeholders valid, and attachment prose without an
`[ATTACHMENT_n]`.

The outputs made for scoring stay in the evaluation result. Judging
some of them means a generate run, which puts them in the catalog as
any other output.

## What the `text-sft` baseline does with long and near-identical bodies

- **A body over the token budget is dropped, never cut.** A cut example
  has no end token, and teaches the model not to stop. The budget is
  counted in the base model's tokens, which only the plugin has, so the
  plugin drops it and counts it (record 0036).
- **Near-identical bodies are collapsed within each side, and a
  validation body that nearly copies a training one is dropped.** Two
  bodies are near copies if, with whitespace and case folded, they are
  identical or their sets of five-word runs overlap by a Jaccard of at
  least 0.8, a parameter. Matches chain: A like B and B like C make one
  group. Each group keeps the member with the smallest checksum. All of
  it is counted.

Collapsing after the split is a stopgap. The old pipeline collapsed
before splitting, so near copies never straddled the two sides. A
freeze draws first, so this guards against the leak rather than
preventing it. A freeze-time grouping that keeps near copies on one
side is later work.

## Why the baseline is generic

Nothing in the training loop is phishnet's: a 4-bit LoRA on every
linear layer, a loss on the completion only, and a base or instruct
wrapping. What is phishnet's is the template, the system prompt and the
checks, and those are parameters and a metrics plugin. Keeping the loop
in strata-modelling means the next project that fine-tunes a text
generator starts from it.

It sits behind an `sft` extra, since unsloth and peft are heavy and
only a GPU host needs them.

## Consequences

- **strata-modelling:** `Model`, `LabelModel` and `MediaModel`; the
  handler checks a `MediaModel`'s `trains_on` and routes `generate`; a
  `GenerateRequest` and its result; the `checkpoint` table and the
  checkpoint in the prediction key, in one migration; the `text-sft`
  baseline under the `sft` extra.
- **Every existing model's base class becomes `LabelModel`.**
- **strata-evaluation:** the `generation` task. The task contract
  accepts a task that reads generated outputs rather than a label type.
- **strata-experiment:** the evaluate stage scores every checkpoint of
  a run.
- **strata-catalog:** a freeze over an SFT type writes its input fields
  as features.
- **strata-phishnet:** its template and system prompt as `text-sft`
  parameters in `project.toml`, and its checks as a metrics plugin.
  `phishnet_lab`'s `templates_*` scripts are replaced once these exist.
- **Records 0005, 0006 and 0041 are marked amended,** each with its
  part of the reasoning above.
