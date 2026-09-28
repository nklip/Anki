# Ingress

<sub>[Back to Kubernetes](../Readme.md#content)</sub>

# Front

What does Ingress do, and why does an Ingress object need a controller?

# Back

**Ingress declares web routing rules from outside a cluster to Services, usually using hostnames and paths.** It handles Hypertext Transfer Protocol (**HTTP**) and its secure form (**HTTPS**). An **Ingress controller** implements the rules by configuring a proxy or load balancer. Creating the object alone does not create functioning routing.

## Rules versus the traffic path

Suppose `shop.example.com/catalog` should reach the `catalog` Service and `/checkout` should reach the `checkout` Service. Ingress expresses those rules; a compatible controller makes the routing happen.

The top row is configuration. The bottom row is the logical request path; the exact backend forwarding mechanism depends on the controller.

![ingress-routing.svg](images/ingress-routing.svg)

## How it differs from a Service

A Service provides backend discovery and network access. Ingress adds web routing above it, such as choosing a backend by host or path and terminating **Transport Layer Security (TLS)** for HTTPS. Ingress is not itself a Service type and does not expose arbitrary protocols through its standard API.

### Current guidance

**The Ingress API is frozen**, meaning new features are being developed elsewhere; Kubernetes does not plan to remove it. Current documentation recommends **Gateway API** for new capabilities. Gateway API separates infrastructure ownership from application routing through resources such as `Gateway` and `HTTPRoute`; it also requires a supporting implementation.

Do not confuse the Ingress API with any particular controller product. Controller capabilities and lifecycle must be checked separately.

# Sources

- [Kubernetes — Ingress, prerequisites, TLS, and API status](https://kubernetes.io/docs/concepts/services-networking/ingress/)
- [Kubernetes — Ingress controllers](https://kubernetes.io/docs/concepts/services-networking/ingress-controllers/)
- [Kubernetes — Gateway API](https://kubernetes.io/docs/concepts/services-networking/gateway/)
