# StatefulSets

<sub>[Back to Kubernetes](../Readme.md#content)</sub>

# Front

When should you choose a StatefulSet instead of a Deployment?

# Back

**Choose a StatefulSet when individual application instances need stable identities or stable per-instance storage.** A Deployment is usually simpler when replicas are interchangeable.

## Identity survives replacement

StatefulSet Pods have an ordinal identity, such as `db-0` and `db-1`. With a governing headless Service, they have stable network names. Their Internet Protocol (**IP**) addresses can still change.

For storage, a `volumeClaimTemplates` entry creates a **PersistentVolumeClaim (PVC)** for each Pod. A PVC requests storage backed by a **PersistentVolume (PV)**. A replacement for `db-0` can use `db-0`'s existing claim and data instead of becoming an unrelated database instance.

Read across the top: the Pod is replaced, while the identity and storage claim stay associated.

![statefulset-identity.svg](images/statefulset-identity.svg)

## Ordering and responsibility

By default, StatefulSets create and scale Pods in ordinal order and wait for predecessors to be ready. `podManagementPolicy: Parallel` changes scaling behavior; it does not change rolling-update behavior.

### Important limits

- Stable identity does **not** configure database replication, leader election, or backups. The application or an operator must handle those.
- Claims are retained by default when the StatefulSet is deleted or scaled down. A configured PVC retention policy can change that behavior. The PV's reclaim policy also affects what happens to the underlying storage after a claim is deleted.
- A stable network name is not a promise of uninterrupted availability.

# Sources

- [Kubernetes — StatefulSets, identity, ordering, and PVC retention](https://kubernetes.io/docs/concepts/workloads/controllers/statefulset/)
- [Kubernetes — PersistentVolumes, claims, and reclaim policies](https://kubernetes.io/docs/concepts/storage/persistent-volumes/)
