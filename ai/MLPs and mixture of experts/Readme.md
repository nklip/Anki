# MLPs, nonlinearities, and mixture of experts

<sub>[Back to Artificial Intelligence](../Readme.md#content)</sub>

**An MLP (multilayer perceptron) is the part of each transformer block that processes one token's vector on its own, after attention has gathered information from other tokens. A mixture of experts keeps several MLPs and lets each token use only a few of them.**

## Where this fits

Every transformer block does two jobs in order: attention, then the MLP ([The transformer forward pass](../The%20transformer%20forward%20pass/Readme.md)):

![where-this-fits.svg](images/where-this-fits.svg)

Read left to right; the enlarged block highlights the MLP as its second job.

A useful division of labor: attention *moves* information between positions ([Attention: queries, keys, values, and heads](../Attention/Readme.md)), and the MLP *works on* the information that each position now holds. Like attention, the MLP adds its result to [the residual stream](../The%20residual%20stream%20and%20normalization/Readme.md). In a standard, **dense** model, every position uses the same MLP weights within a block, and each block has its own MLP.

## What an MLP does

![dense-mlp-example.svg](images/dense-mlp-example.svg)

An MLP has three stages, which the diagram follows from left to right:

1. **Expand:** learned weights turn the vector into a longer one, giving more room to work. Expansion means more slots per token, not more tokens.
2. **Apply a nonlinear rule** to each slot separately. The diagram uses **ReLU (rectified linear unit)**: keep positive numbers, and replace negative ones with zero.
3. **Project back:** learned weights shrink the result to the original size. That result is the MLP's update.

In the diagram, a two-slot vector is expanded to three slots, ReLU zeroes the negative slot, and the result is projected back to two slots. The recipes are invented and only show the shape. Here a **projection** simply means a learned multiply-and-add recipe that produces new numbers. Each slot of the expanded middle is called a **neuron**; real MLPs have several times more neurons than the vector has slots.

## Why the nonlinear rule matters

Multiply-and-add steps stacked on top of each other collapse into a single multiply-and-add: doubling and then tripling is just multiplying by six. Without something else, a deeper network would add nothing new. A nonlinear rule such as ReLU breaks this collapse, because it treats negative and positive numbers differently. That lets stacked layers build behavior that no single multiply-and-add recipe can express.

## Gated MLPs

![gated-mlp.svg](images/gated-mlp.svg)

Llama-style models use a **gated** MLP called **SwiGLU**. Two learned branches read the same input: one produces content, and the other produces **gate values** that control how much of each content number passes through. In the diagram, the gate halves the first number and doubles the second, so a gate can weaken or strengthen a value, not only switch it on or off. The gate branch uses **SiLU** (also called Swish), a smooth rule without ReLU's sharp corner at zero. The product is then projected back, as before.

## Mixture of experts: choose which MLPs run

A **sparse mixture of experts (MoE)** replaces the single MLP with several MLPs, called **experts**, plus a small learned **router**. For each token, the router picks a few experts, runs only those, and blends their outputs.

![sparse-expert-routing.svg](images/sparse-expert-routing.svg)

In the diagram, the router picks experts 1 and 3 of four for this token and weights them 75% and 25%; experts 2 and 4 do not run. Another token may pick different experts. Experts are ordinary neural networks inside the model, not separate chatbots with assigned specialties.

The point is to give a model many parameters while each token uses only some of them. Mixtral 8x7B, for example, picks two of eight experts in each layer, so each token has access to 47 billion parameters but uses only about 13 billion. All experts must still be stored, and routing adds overhead, so using fewer parameters per token does not cut memory or time in the same proportion.

# Sources

- [Transformer: position-wise MLPs](https://arxiv.org/html/1706.03762v7)
- [PyTorch: ReLU](https://docs.pytorch.org/docs/2.15/generated/torch.nn.ReLU.html) and [SiLU](https://docs.pytorch.org/docs/2.15/generated/torch.nn.SiLU.html)
- [LLaMA: pre-norm and SwiGLU](https://arxiv.org/html/2302.13971v1)
- [GLU variants: gated MLP equations](https://arxiv.org/html/2002.05202v1)
- [Transformer Circuits: neurons and the residual stream](https://transformer-circuits.pub/2021/framework/index.html)
- [Mixtral: routing, active parameters, and memory](https://arxiv.org/html/2401.04088v1)
- [Switch Transformers: sparse computation and communication costs](https://arxiv.org/abs/2101.03961)
