# Internals: Features and the linear representation hypothesis

<sub>[Back to Artificial Intelligence](../Readme.md#content)</sub>

**The linear representation hypothesis is the idea that a model stores many of the things it tracks, such as “this text is in French” or “this verb is in the past tense,” as directions in its internal vectors.** If it holds, you can read such a property by measuring how far a vector points that way. It is a hypothesis, supported in many tests but not always true.

## Where this fits

The earlier articles explained what a model computes. This article and [Superposition and mechanistic interpretability](../Superposition%20and%20mechanistic%20interpretability/Readme.md) ask what those numbers mean:

Read the model's route from left to right. The purple branch shows researchers inspecting its internal vectors.

![where-this-fits.svg](images/where-this-fits.svg)

This is **interpretability** research. It studies the vectors in [the residual stream](../The%20residual%20stream%20and%20normalization/Readme.md) that carry each token's information between blocks. None of their numbers has a label: when the model reads “She walked home,” no slot is marked “past tense.”

## Features and neurons

A **feature** is a property of the input that the model represents, such as past tense, French text, or a plural noun. It need not have a human name.

As in the MLP article, a **neuron** is one slot in the expanded middle of an MLP. One neuron per feature, such as a “French neuron,” would be easy to read, and some neurons come close. But many respond to several unrelated things, and one feature is often spread across many neurons. So researchers look for directions instead of single slots.

## The hypothesis: features are directions

Think of a vector as an arrow. A **direction** is where the arrow points, and it can be diagonal, using many slots at once. The hypothesis makes three claims:

1. Each feature has its own direction.
2. A stronger feature means a longer step along that direction.
3. When several features are present, their steps simply add up.

“Linear” describes only this way of storing features. The model still needs nonlinear steps such as ReLU to work out whether a feature is present at all.

## Reading a feature: measure along its direction

![direction-and-projection.svg](images/direction-and-projection.svg)

To read a feature, measure how far a vector reaches along its direction, like the shadow a stick casts on a line. In the diagram, the arrow to `x = [2, 1]` is a token's vector and the “line along u” is a feature's direction. The dashed line drops from `x` at a right angle to the point labeled “projection”: the part of `x` that lies along `u`. The “Measure along u” box turns it into one number with a **dot product**, the multiply-and-add comparison that [attention](../Attention/Readme.md) also uses.

The bottom box adds two cautions: “unit direction” means length 1, not one slot, and the result is a position along a line, not a probability.

If two features' directions overlap, measuring one also picks up some of the other. Researchers suspect that real models track more features than they have slots, which forces overlaps, as the next article explains.

## Finding directions: linear probes

Nobody knows a real feature's direction in advance. A **linear probe** finds one from examples. Researchers run the model on sentences labeled, say, past or present tense, save the vectors at one layer, and train a tiny separate model to split the two groups with a direction and a cutoff. The language model itself does not change.

A probe needs checks: test it on new sentences, see how well it learns random labels (pure memorizing), and compare it with a probe on an untrained copy of the model, which should do clearly worse.

Passing these checks shows that the property is **recoverable** at that spot. It does not show that the model **uses** it, just as a spreadsheet can hold a column that no formula reads. In one study, how well a probe read a property did not predict how much the model suffered when that property was erased.

## Testing use: interventions

![probe-and-intervention.svg](images/probe-and-intervention.svg)

The diagram contrasts two experiments; the model's weights stay fixed in both. In “Read a copy,” a probe reads the vector and the model continues with the original, so the answer cannot change. In “Change the activation,” an **intervention** edits the vector during the run, and the output is compared with an unedited run. A change of the predicted kind is evidence of **causal influence**.

A common edit, **steering**, adds some of a feature's direction. In one study, Llama 2 completed “Long live the” with “king.” Adding its male-to-female direction made “queen” the top word, while the choice between “King” and “king” stayed the same. The diagram's last line warns that a good reading direction is not automatically a good steering direction: where features overlap, a probe can tilt its direction to avoid the overlap.

## Evidence and limits

- **Support:** in Llama 2, nearly all of 27 tested concepts, such as plural nouns and English-to-French, behaved approximately like directions.
- **Not every feature is one direction:** days of the week and months of the year sit on circles in some models, which use them for prompts like “Two days from Monday is.”
- **A readable direction is a finding, not a full explanation** of how the model computes or uses the feature.

# Sources

- [Toy Models of Superposition: features, neurons, and directions](https://transformer-circuits.pub/2022/toy_model/index.html)
- [Designing and Interpreting Probes with Control Tasks](https://arxiv.org/abs/1909.03368)
- [Probing Classifiers: baselines and limitations](https://aclanthology.org/2022.cl-1.7/)
- [Amnesic Probing: decoding versus causal use](https://arxiv.org/abs/2006.00995)
- [The Linear Representation Hypothesis: Llama 2 concepts and steering](https://arxiv.org/html/2311.03658v2)
- [The Geometry of Truth: probe directions and causal effects](https://arxiv.org/abs/2310.06824)
- [Not All Language Model Features Are One-Dimensionally Linear](https://arxiv.org/abs/2405.14860)
