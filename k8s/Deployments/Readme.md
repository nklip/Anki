# Deployments and ReplicaSets

<sub>[Back to Kubernetes](../Readme.md#content)</sub>

# Front

How does a Deployment manage Pods through ReplicaSets, including during an update?

# Back

**A Deployment manages ReplicaSets to maintain and update a set of usually interchangeable Pods.** A ReplicaSet maintains a requested replica count; the Deployment adds controlled replacement of one Pod template with another.

## Count versus version

A **Pod template** describes the containers and configuration used when creating a Pod. Changing the Deployment's template, such as its container image, triggers a rollout. Simply changing its replica count scales the workload without triggering a new template rollout.

With the default `RollingUpdate` strategy, the Deployment scales up a ReplicaSet for the new template and scales down the old one. Read the diagram from the declared template to the two replica groups.

![deployment-rollout.svg](images/deployment-rollout.svg)

## Control the rollout

- `maxSurge` bounds how many extra replicas may be created during the rollout.
- `maxUnavailable` bounds how many desired replicas may be unavailable during it.
- A **readiness probe** tests whether a container is ready to serve. Correct readiness checks help keep unready Pods out of normal Service traffic.

For an existing Deployment named `web` in the current namespace:

```bash
kubectl rollout status deployment/web
kubectl rollout history deployment/web
# Explicitly restore the preceding retained Pod-template revision:
kubectl rollout undo deployment/web
```

### Important limit

**A failed rollout does not automatically roll back.** A progress deadline can mark it `ProgressDeadlineExceeded`; a person or additional automation must decide what to do. Rollback restores a retained Pod template, not database changes or every external configuration value. A Deployment also does not provide a stable network endpoint; that is a Service's role.

# Sources

- [Kubernetes — Deployments, rollout strategy, history, and failure conditions](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/)
- [Kubernetes — ReplicaSet](https://kubernetes.io/docs/concepts/workloads/controllers/replicaset/)
- [Kubernetes — Readiness probes](https://kubernetes.io/docs/concepts/workloads/pods/probes/)
