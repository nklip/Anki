# Kubernetes

<sub>[Back to Anki Flashcards](../README.md)</sub>

Ten focused interview cards selected from the local Anki deck **Kubernetes** (40 notes / 40 cards), with updated explanations and one editable SVG per card. Checked against current official documentation on **28 September 2026**; the release page identifies **Kubernetes 1.37** as the current minor release.

## Content

The order below is a learning sequence. This is an editorial shortlist of commonly covered interview topics, not a measured frequency ranking. Selection combines overlap with an interview-question guide, foundational value, and practical relevance. Every selected topic already exists in the source deck; broad prompts have been rewritten as focused questions.

| # | Card | Original deck front | Original Anki note ID |
| --- | --- | --- | --- |
| 1 | [What problem does Kubernetes solve?](Kubernetes/Readme.md) | Kubernetes | `1686533135092` |
| 2 | [How do the cluster components work together?](Cluster%20components/Readme.md) | Main components of Kubernetes | `1689115755684` |
| 3 | [What is a Pod?](Pods/Readme.md) | Pod | `1686534042384` |
| 4 | [What does a Deployment manage?](Deployments/Readme.md) | Deployment | `1689116001461` |
| 5 | [How does a Service reach changing Pods?](Services/Readme.md) | Service in K8s | `1690371932134` |
| 6 | [ConfigMap or Secret?](ConfigMaps%20and%20Secrets/Readme.md) | ConfigMaps and Secrets | `1690538840801` |
| 7 | [What does Ingress do?](Ingress/Readme.md) | Ingress | `1690681227254` |
| 8 | [When should you use a StatefulSet?](StatefulSets/Readme.md) | StatefulSets | `1690753402722` |
| 9 | [What does a Namespace isolate?](Namespaces/Readme.md) | Namespaces | `1692455356317` |
| 10 | [How does HPA decide to scale?](Horizontal%20Pod%20Autoscaling/Readme.md) | HPA | `1692455450596` |

To locate an original in Anki's browser, search `nid:1686533135092`, replacing the number with its note ID. These Markdown cards are repository study material; the original Anki collection was read without changing its notes or review history.

## Additional cards

- [What does CloudNativePG (CNPG) do in Kubernetes?](CloudNativePG/Readme.md)

## What was refreshed

- Cluster architecture separates the API server, scheduler, controllers, kubelet, and container runtime; kube-proxy is optional when another implementation provides Service forwarding.
- Deployment rollouts support explicit rollback; a failed rollout does not automatically restore an earlier revision.
- Service explanations include EndpointSlices and the headless-Service exception to a virtual IP address.
- The original ConfigMap example placed an API key in non-secret configuration. The new card separates sensitive data and explains why base64 is not encryption.
- Ingress needs a controller. Its API is frozen, and current Kubernetes documentation recommends Gateway API for new capabilities.
- StatefulSet identity does not imply automatic database replication or backups. Storage retention can be configured.
- Namespaces scope resources; network isolation and authorization require additional policy.
- HPA uses metrics APIs and resource requests for utilization targets, with explicit limits on the simplified scaling calculation.

# Sources

- Local Anki deck `Kubernetes`, deck ID `1686533053086`, read on 28 September 2026. Original note IDs are preserved above for traceability.
- [Kubernetes — Releases](https://kubernetes.io/releases/)
- [Dataquest — Kubernetes interview-question guide](https://www.dataquest.io/blog/kubernetes-interview-questions/) — topic-selection context only; technical answers use official sources listed on each card.
