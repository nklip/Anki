# Features and the linear representation hypothesis

<sub>[Back to Artificial Intelligence](../Readme.md#content)</sub>

**The linear representation hypothesis proposes that many meaningful properties are encoded approximately as directions in a model's working vectors.** We will distinguish features from neurons, measure a direction, and explain what a linear probe can establish.

## Features, neurons, and activations

An **activation** is a working number calculated while the model processes an input. A **vector** is an ordered list of numbers; a **coordinate** is one slot. Activations change with the input, even when learned weights stay fixed.

Here, a **feature** means a property represented by the model, such as past tense. It need not have a neat human-readable name. A **neuron** is a computational unit that produces one activation value. In a **multilayer perceptron (MLP)**, the intermediate vector contains many such values.

A feature is not necessarily one neuron. It can involve many coordinates, and a neuron can respond to several features. A coordinate in the residual stream—the running vector between components—is not automatically a named concept or a neuron.

## What “linear representation” proposes

A **direction** describes how coordinates increase or decrease together. It can point diagonally instead of following one coordinate axis.

In the linear picture, a feature's strength scales its direction, and several features contribute by adding their scaled directions. Doubling a contribution means doubling each of its numbers.

This concerns representation. Nonlinear computation can still detect features and use them; the whole model need not be linear.

## A projection: measure along an arrow

Use invented two-number vectors to measure along a direction. This is geometry, not a discovered language feature.

![direction-and-projection.svg](images/direction-and-projection.svg)

Let the activation vector be `x = [2, 1]` and the direction be `u = [0.6, 0.8]`. This is a **unit direction**, meaning its arrow has length 1, not that it has one slot. Its squared length is `0.6 × 0.6 + 0.8 × 0.8 = 1`; its length is 1 because `1 × 1 = 1`.

The **dot product** multiplies matching coordinates, then adds:

`x · u = 2 × 0.6 + 1 × 0.8 = 1.2 + 0.8 = 2`.

Because `u` has length 1, this is the **signed projection length**: 2 units along that direction. Negative would mean the opposite direction. The projected vector is `2 × [0.6, 0.8] = [1.2, 1.6]`, like a shadow dropped onto the direction's line.

The score 2 is not a probability, and geometry alone does not tell us its meaning. We use ordinary flat-page geometry; real model spaces may require a different geometry for measuring concepts.

## Linear probes: can we read out a property?

A **linear probe** is a small predictor trained on saved activations and known labels, such as “past tense” or “present tense.” It learns a multiply-and-add score: multiply each coordinate by a learned weight, add the results, and optionally add an offset. A threshold can turn that score into a label.

Choose a layer and token position to read. Only the probe learns; the model stays fixed. Test on examples excluded from probe training. Use baselines and controls for memorization or data shortcuts.

![probe-and-intervention.svg](images/probe-and-intervention.svg)

Good test performance shows that the property is **recoverable by that probe on those examples**. It does not establish that the model uses that property to produce its answer.

An **intervention** changes an activation and checks the effect on the model's output. Controlled interventions provide evidence of causal influence. Check for side effects on other properties; a useful probe's weights are not automatically a good direction for editing the model.

## Evidence and limits

Experiments with Llama 2 found approximate directions for many tested concepts, including language distinctions, with related results for reading and changing outputs. This supports studied cases, not every concept or model.

Some representations need more than one direction: researchers found circular representations of weekdays and months in studied models. Directions can also overlap, so one projection may mix several signals. “A direction predicts a label” is a useful finding, not a complete explanation of the model's computation.

# Sources

- [Toy Models of Superposition: features and directions](https://transformer-circuits.pub/2022/toy_model/index.html)
- [The Linear Representation Hypothesis: theory and experiments](https://arxiv.org/html/2311.03658v2)
- [Designing and Interpreting Probes with Control Tasks](https://arxiv.org/abs/1909.03368)
- [Amnesic Probing: decoding versus causal use](https://arxiv.org/abs/2006.00995)
- [Probing Classifiers: methods and limitations](https://aclanthology.org/2022.cl-1.7/)
- [Not All Language Model Features Are One-Dimensionally Linear](https://arxiv.org/abs/2405.14860)
