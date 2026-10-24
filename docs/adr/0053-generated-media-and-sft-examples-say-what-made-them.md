# 53. Generated media and SFT examples are types, and each says what made it

**Status:** proposed; builds on records 0045, 0048, 0049 and 0052

## The decision

Two mixins describe what a sample is *for*, beside the media it is
made of. A type combines one with a media's type:

| Class | Lives in | Stored as | What it is |
|---|---|---|---|
| `GeneratedMedia` | strata-contracts | (a mixin) | A model's output |
| `GeneratedText(Text, GeneratedMedia)` | strata-contracts | `text/generated` | Text a model wrote |
| `SFTExample` | strata-contracts | (a mixin) | A supervised fine-tuning example |
| `SFTTextExample(Text, SFTExample)` | strata-contracts | `text/sft` | One with a text target |
| `PhishNetEmail(GeneratedText)` | strata-phishnet | `text/generated/phishnet-email` | The LoRA's output |
| `PhishNetSFT(SFTTextExample)` | strata-phishnet | `text/sft/phishnet` | A masked message, as a LoRA target |

The media is `text` throughout, so every text label type, the labeller's
text templates and every text model work on these samples unchanged. A
`GeneratedImage(Image, GeneratedMedia)` or `SFTImageExample(Image,
SFTExample)` later is the same pattern.

**A generated sample** arrives only through a **generate** run. It has
an origin row for each sample whose bytes the model was given, such as
the text a summary was made from, or the content and style images of a
style transfer. Each row says the **role** the sample filled (`text`,
`content`, `style`). A LoRA writing from a subject alone has none. Every
generated sample has a **generation record**, one per generate run that
produced it:

- the generate run;
- the model run that generated it, by its host and run id, and the
  checkpoint, by name and digest (record 0054);
- the prompt template's, system prompt's and generation settings'
  digests;
- the values filled into the template;
- the seed.

The generate run's spec holds the template, the system prompt and every
settings variant in full, as canonical JSON. So any generated sample
leads back to the exact text and settings that made it.

**An SFT example's bytes are its target, and its input is its
metadata.** The type's `Metadata` declares the input fields. Each
origin's facts are checked against it (record 0049).

**Samples made from samples outside the catalog arrive through a
derive run.** Each has an origin row per input sample, named by
checksum and type (record 0052). The run's spec names everything it
read: prediction runs, any model and prompt digest, and label sets as
they stood when it started.

## Why mixins, and why the media stays the target's

A subtype cannot change its media (record 0010), so "generated" or
"SFT" as a media of its own would be a sibling of `text`. Nothing
text-shaped would accept it. A span label set, the tagger and the
labeller's text templates would each have to be taught a new media,
for samples that are text.

Where a sample was put already keeps it out of the wrong dataset.
Every query and every freeze names its collections (record 0022), so a
generated sample enters a dataset only through a collection that holds
it.

A mixin is a plain class, not a `SampleType`. A sample type with no
media could be registered and picked on its own, and would mean
nothing. The mixin holds what the catalog checks:

- **`GeneratedMedia`:** a sample of the type arrives only through a
  generate run, and has a generation record, with an origin row per
  input sample. A generate run writes only such types. Any other run
  that offers one is refused.
- **`SFTExample`:** the bytes are the target, and the type's
  `Metadata` names the input fields, required on every origin.

## What a generated sample's origins are, and what anchors the rest

An origin row names an input the sample was made from: a raw file or a
sample (record 0045). A generated sample can be made from samples, and
then that is lineage like any other. A summary was made from its text,
and a style transfer from two images. So each sample the model was
given is an origin row, and the generate run is the run that made it.
A query for what was made from a text then finds its summaries, the
same way it finds anything derived from it.

One model can take several samples in different parts, so an origin
row gains a `role`: the input it filled, named as the model names its
inputs. It is null for origins written by ingest, prepare and derive
runs, whose inputs have no parts. The role is part of the row's
uniqueness, since one sample can fill two roles in one run.

The rest of what made a generated sample is not data. The checkpoint,
the template, the settings and the values in the prompt are not
samples, and forcing them into origin rows would make every reader of
origins handle inputs that are not data. So the generation record is a
table of its own, keyed by sample and run like an origin.

The template, the system prompt and the settings are named per sample,
not only per run. One run can sweep a setting, such as temperature, and
each sample still says which variant made it.

A prompt value copied out of a stored sample's metadata, such as a real
message's subject, is different. The model was given the value, not the
sample. It is recorded with the values as a reference to that sample,
by checksum and type, and is not an origin.

The model was trained with a template and a system prompt, which the
training run records as its parameters. A generate run takes them from
there. The digests let anyone check that an output was prompted the way
its model learned. A run that prompts differently is not refused, since
trying a new prompt on an old model is legitimate, but the difference
shows.

## Why generated output is a sample, not a prediction

A prediction says something about a sample that already exists, and it
stays in the run store (record 0048). A generated text is a new thing:
it gets labelled, judged and frozen into datasets like any other text.
That needs a sample. A run store holds nothing a label set can hang
off, and nothing a freeze can select.

When an output's bytes match a sample of another type, such as a
training target the model reproduced, record 0052 keeps them apart: it
is a `PhishNetEmail` of its own, and the training sample is unchanged.
So exact memorisation is a query: generated samples whose checksum also
exists as an SFT example. Near copies need a similarity check at
evaluation, which is later work.

## Why the input is metadata, and what that costs

An SFT example's input could have gone in the bytes, beside the target,
as JSON. Then the checksum would cover both. Two examples with one body
and two subjects would be two samples. But every span would need to say
which part of the JSON it points into, since an offset into escaped
JSON means nothing. And the sample would no longer be a text document
that every text tool reads.

With the input as metadata, the bytes are the target, a plain document.
Two examples with one body and two subjects are one sample with two
origins. Each origin keeps its own subject, and the sample's combined
metadata shows the first (record 0049). Nothing is lost in storage.

A materialised sample carries one input, never several. A freeze over
an SFT type compares each sample's input fields across its origins. A
sample whose origins disagree is left out, and counted under a reason
(record 0036), so a version records what it dropped. The type decides
what disagreeing means: `PhishNetSFT` compares subjects with whitespace
folded, so a re-wrapped subject is not a dispute. This is what
phishnet's SFT export does today.

## Why a derive run, and not a prepare run

A prepare run is a chain of stages that the catalog runs over raw files
(records 0046 and 0047). Running a chain on the same input gives the
same output, so a run's counts are enough to explain any input it
dropped. Masking a message fits none of that. It runs where the models
are, on a GPU host. It reads GLiNER's and the tagger's predictions,
and asks an LLM how to group entities, so running it again can give
different text.

So a derive run is made outside the catalog and committed to it with
its lineage declared, as an import is. The catalog checks what arrives:

- every input sample exists, with the type named;
- the output type's `Metadata` holds for each origin's facts;
- the spec names the runs and label-set states it read.

The origin table could already name a sample as an input (record 0045).
A derive run is the first writer to do so.

## The phishnet case

**SFT examples.** The anonymise script becomes a derive run. It reads
`text/email` samples from `phishnet/enron/single` and
`phishnet/podesta/single`. For each one it writes a `PhishNetSFT` whose
bytes are the masked body, into collections of its own (for example
`phishnet/sft/enron`). The origin row points to the source message. The
origin's facts are the input: the subject, from the source message's
metadata, and the corpus. The URL and attachment flags are facts about
the bytes, which `PhishNetSFT` computes from the placeholders.

The spec names:

- the GLiNER and tagger runs;
- the Gemma model and the grouping prompt's digest;
- the `boilerplate` label set as it stood, for the cuts.

**Verdicts** are a classification label set over the `PhishNetSFT`
samples: `keep`, `drop-grouping`, `drop-report`, `drop-leak`, `drop-id`,
`drop-overmask` and `drop-text`. The verdicts carried from the emails
project arrive in an import run, as `import`, with a batch naming them
as carried. Judging one again in the labeller makes a `human` answer,
which wins (record 0048). The carried files also say `skipped` and
`failed`, which are not verdicts: grouping never produced a text, either
because the message was over the decision cap or because the LLM gave
no usable answer twice. Those messages have no `PhishNetSFT` sample. A
derive run counts them under its reasons, and a later run can try them
again. The SFT dataset is an ordinary freeze over
the `phishnet/sft/*` collections, with a selection spec that keeps
`keep` (record 0050).

**Generated output** is `PhishNetEmail`, written by a generate run into
a collection per run. It is judged with a label set of its own, never
with the SFT verdicts, so judging a training example and judging the
model's output stay separate questions.

## Consequences

- **strata-contracts gains `GeneratedMedia`, `GeneratedText`,
  `SFTExample` and `SFTTextExample`.** The catalog's intake checks the
  mixins' rules.
- **The catalog gains run kinds `generate` and `derive`, and a
  `generation` table:** sample, run, model host and run id, checkpoint
  digest, template, system prompt and settings digests, values, seed.
- **An origin row gains a nullable `role`,** part of its uniqueness.
- **A command commits each kind of run:** a directory of outputs, with
  their origins, generation records and the run's spec, checked and
  committed in one transaction.
- **strata-phishnet registers `PhishNetEmail` and `PhishNetSFT` as
  sample types.** Any host that writes them to `main` has it installed.
- **phishnet's `carry_judged.py` and `export_sft.py` are replaced** by
  the derive run, the verdict import and the freeze. They stay until
  those exist.
- **Not decided here: the modelling side.** A generative model trains on
  samples and their metadata, not on labels. Its template and system
  prompt are its parameters, and it produces samples through a generate
  run, not predictions. That changes modelling's contract and is record
  0054's to decide.
