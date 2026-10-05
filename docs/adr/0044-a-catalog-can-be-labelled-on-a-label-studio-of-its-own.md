# 44. A catalog can be labelled on a Label Studio of its own

**Status:** accepted; follows record 0029

## The decision

`[label_studio.<catalog>]` tables name the instance a catalog is labelled
on, layered on the flat `[label_studio]` keys, which stay the machine's own
instance for every catalog without one. A project is labelled on its
catalog's instance. An instance's API key comes from
`$LABEL_STUDIO_API_KEY_<CATALOG>` or its own table, never from the machine's
`$LABEL_STUDIO_API_KEY`. A table naming a catalog the machine does not
describe is refused.

## Why per catalog

Label Studio is a view of the catalog (record 0029), so which instance
shows a catalog is a fact about the catalog. A shared catalog is best
labelled on one instance next to it, whichever machine the labelling is
done from: the queue is then the same queue from the desktop and the
laptop, and its images come from the blob server beside it through signed
URLs (record 0013). A local catalog is labelled on a local instance,
which works with no network. One machine labels both, so one URL for the
whole machine cannot say this.

A project already keeps its Label Studio project id per instance URL, so a
job moved between instances needs `init` on the new one and loses nothing:
answers live in the catalog, and the queue rebuilds from it.

## Why the machine's key is not a fallback

Each instance issues its own keys. The machine's key sent to a catalog's
instance is refused as an invalid token by a server that is not the one it
belongs to, which reads as a broken deployment rather than as a missing
variable. Missing, the error names the variable to set.
