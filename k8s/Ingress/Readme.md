# Ingress

<sub>[Back to Kubernetes](../Readme.md#content)</sub>

# Front

What does Ingress do, and why does an Ingress object need a controller?

# Back

**Ingress declares web routing rules from outside a cluster to Services, usually using hostnames and paths.** It handles Hypertext Transfer Protocol (**HTTP**) and its secure form (**HTTPS**). An **Ingress controller** implements the rules by configuring a proxy or load balancer. Creating the object alone does not create functioning routing.

## Rules versus the traffic path

Suppose `example.com/users` should reach `users-service` and `/orders` should reach `orders-service`. Ingress expresses those rules; a compatible controller makes the routing happen.

Read top to bottom: the controller's proxy or load balancer applies the Ingress rules to choose a Service, whose backend Pods run the application. This is a logical routing flow; the exact network hops depend on the controller.

Solid arrows show request routing; dashed arrows show configuration or Pod management. In this example, each application has a **Deployment**, which controls replicas and updates through **ReplicaSets** that maintain its Pods. Requests do not pass through Deployments.

![ingress-routing.svg](images/ingress-routing.svg)

## How it differs from a Service

A Service provides backend discovery and network access. Ingress adds web routing above it, such as choosing a backend by host or path and terminating **Transport Layer Security (TLS)** for HTTPS. Ingress is not itself a Service type and does not expose arbitrary protocols through its standard API.

## Gateway API version

**The Ingress API is frozen**, meaning new features are being developed elsewhere; Kubernetes does not plan to remove it. Current documentation recommends **Gateway API** for new capabilities. Gateway API separates infrastructure ownership from application routing through resources such as `Gateway` and `HTTPRoute`; it also requires a supporting implementation.

`GatewayClass` selects the controller implementation. `Gateway` defines a listener, and an attached `HTTPRoute` maps hosts and paths to Services. Here the listener accepts HTTPS on port 443; the Services and Deployments keep their roles. Gateway API requires its **Custom Resource Definitions (CRDs)** and a compatible controller.

![gateway-routing.svg](images/gateway-routing.svg)

Do not confuse the Ingress API with any particular controller product. Controller capabilities and lifecycle must be checked separately.

# Sources

- [Kubernetes — Ingress, prerequisites, TLS, and API status](https://kubernetes.io/docs/concepts/services-networking/ingress/)
- [Kubernetes — Ingress controllers](https://kubernetes.io/docs/concepts/services-networking/ingress-controllers/)
- [Kubernetes — Gateway API](https://kubernetes.io/docs/concepts/services-networking/gateway/)
- [Kubernetes — Deployments and their ReplicaSets](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/)
