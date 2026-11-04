# Superposition and mechanistic interpretability

<sub>[Back to Artificial Intelligence](../Readme.md#content)</sub>

**Superposition represents more features than a vector has dimensions, using overlapping directions. Mechanistic interpretability investigates how internal computations produce behavior.** We will examine the overlap, a tool for finding candidate features, and tests of causal explanations.

A **feature** is a represented property, such as past tense. An **activation vector** is a list of working numbers inside the model. Its **dimensions** are its number slots. In the linear picture from article 13, features contribute by adding their directions, scaled by how strongly they are active.

## Three features in two slots

Use invented features A, B, and C, each either off or on. When on, a feature adds its assigned vector.

![overlapping-feature-directions.svg](images/overlapping-feature-directions.svg)

A adds `[1, 0]`, B adds `[0, 1]`, and C adds `[1, 1]`. The two slots are shared: C uses both. If only one feature is on, its vector tells us which one it is.

But A and B together give `[1, 0] + [0, 1] = [1, 1]`: add matching slots, so `1 + 0 = 1` and `0 + 1 = 1`. That is identical to C alone. **No method can distinguish these two cases from this vector alone.** This exact collision is specific to our toy example.

## Interference and sparsity

**Interference** means one feature affects a measurement intended for another. Suppose a simple C detector adds both slots and divides by 2. On C alone it gives `(1 + 1) ÷ 2 = 1`. On A alone it gives `(1 + 0) ÷ 2 = 0.5`, even though C is off.

The 0.5 is a leaked signal, not necessarily a wrong final decision. A cutoff can reject small signals. It cannot fix the identical-vector collision above.

**Sparse activity** means few features are active at once. This can make interference manageable: the model rarely needs to separate many overlapping signals simultaneously. Toy networks demonstrate this trade-off; it is not unlimited, lossless storage.

A **polysemantic neuron** responds to several different features. Superposition can cause this, but is not the only possible explanation. A feature spanning several coordinates also does not, by itself, prove that there are more features than dimensions.

## Sparse autoencoders: look for a useful decomposition

A **sparse autoencoder (SAE)** is a separate network trained on a model's activations while the original model's weights stay fixed.

![sparse-autoencoder.svg](images/sparse-autoencoder.svg)

Its **encoder** maps the activation into many candidate feature slots, with only a few active. Its **decoder** reconstructs the input by adding scaled vectors from a learned collection called a **dictionary**. The SAE learns to reconstruct accurately while keeping activity sparse. It learns the dictionary too; researchers need not supply concept names.

With our toy dictionary, `[1, 1]` can be reconstructed using C alone. That uses fewer active slots than A plus B, but does not prove that C was the original cause. Good reconstruction is not the same as a correct explanation.

Real SAEs can leave **reconstruction error**: the difference between the original and rebuilt vectors. Their candidate features can miss or mix important structure. A readable label is a hypothesis to test.

## From features to mechanisms

A **circuit** is a set of internal components and connections that jointly implement a computation. Finding a “name” feature is only a starting point; explaining how a model selects the correct name requires tracing interactions.

![testing-a-circuit.svg](images/testing-a-circuit.svg)

Researchers test proposed mechanisms using **ablation**, which suppresses a contribution, and **activation patching**, which replaces an activation with one from another run. They compare the resulting behavior with an unchanged run and check other inputs and possible side effects.

These interventions test causal influence, beyond merely observing that a feature activates near an answer. Backup pathways can hide an ablation's effect, and a damaging edit can affect unrelated computations.

Researchers have identified and tested circuits for selecting a recipient's name in GPT-2 small. That is progress on a specific behavior, not a complete account of the model. Current circuit maps and feature dictionaries remain partial explanations.

# Sources

- [Toy Models of Superposition](https://transformer-circuits.pub/2022/toy_model/index.html)
- [Sparse Autoencoders Find Highly Interpretable Features](https://arxiv.org/abs/2309.08600)
- [Scaling and Evaluating Sparse Autoencoders](https://arxiv.org/html/2406.04093v1)
- [Interpretability in the Wild: circuits and causal tests](https://arxiv.org/html/2211.00593v1)
- [Circuit Tracing: methods and limitations](https://transformer-circuits.pub/2025/attribution-graphs/methods.html)
