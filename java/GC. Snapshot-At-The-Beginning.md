# GC. Snapshot-At-The-Beginning (SATB)

## Front

What is **Snapshot-At-The-Beginning (SATB)** marking, and how does a pre-write barrier keep concurrent garbage collection correct while application threads modify the object graph?

## Back

**Snapshot-At-The-Beginning (SATB)** is a concurrent garbage-collection marking strategy.

Its central rule is:

> Every object reachable from the GC roots at the logical beginning of marking must be treated as live for that marking cycle.

The collector does **not** copy the entire heap. It creates a **logical snapshot of reachability** and preserves that view while application threads continue changing references.

G1 uses SATB for concurrent old-generation marking. Generational ZGC also uses SATB marking with store barriers.

![SATB pre-write barrier preserves an overwritten reference](svg/gc-satb-pre-write-barrier.svg)

## Why concurrent marking needs a barrier

Suppose the object graph initially contains:

```text
GC root → A → B → C
```

The collector discovers `A` but has not yet scanned `A.next`.

At the same time, an application thread executes:

```java
A.next = D;
```

The old edge `A → B` disappears:

```text
Current graph:

GC root → A → D

B → C       // disconnected from the current graph
```

Without additional coordination, the collector could miss `B` and `C`, even though both were reachable at the beginning of marking.

Reclaiming them during this cycle would violate the SATB invariant and could be unsafe if the collector had not yet accounted for the application transition.

## The SATB pre-write barrier

Before a reference field is overwritten, the barrier observes its **old value**:

```text
old = A.next;              // B
satbPreWriteBarrier(old);  // record B when required
A.next = D;                // perform the application write
```

This is conceptual pseudocode. Application developers do not call the barrier themselves; HotSpot inserts the required barrier code into compiled application code.

The old reference is placed in a thread-local SATB buffer or marking queue:

```text
SATB queue: [B]
```

The collector later drains the queue and traces:

```text
B → C
```

Therefore, `B` and `C` remain marked for the current cycle even though the application removed their path from `A`.

### Why record the old value?

SATB preserves the graph as it existed at the beginning.

When a field is overwritten, the important information is the edge that is being **deleted**, so the barrier records the previous reference:

```text
before: owner.field → oldObject
after:  owner.field → newObject

SATB barrier records oldObject
```

This is why SATB is commonly described as using a **pre-write**, **deletion**, or **old-value** barrier.

## Marking cycle

![SATB concurrent marking timeline](svg/gc-satb-marking-timeline.svg)

A simplified cycle is:

### 1. Establish the starting point

During a brief stop-the-world coordination pause, the collector establishes the root snapshot and starts a new marking cycle.

For G1, this happens as part of the **Concurrent Start** pause.

### 2. Mark concurrently

GC threads trace the object graph while application threads continue running.

Application reference writes execute barriers. When a write might hide an object belonging to the logical starting snapshot, the old reference is buffered for later marking.

### 3. Remark

During the stop-the-world **Remark** pause, the collector completes marking and drains remaining SATB work that must be processed before the mark bitmap is finalized.

### 4. Use the liveness information

The collector uses the completed marking information to decide which regions or pages contain reclaimable space.

SATB marking itself identifies liveness. The collector's later evacuation or relocation phases perform the actual space reclamation.

## Tri-colour interpretation

Concurrent tracing is often explained with three conceptual colours:

| Colour | Meaning |
|---|---|
| White | Not yet discovered |
| Grey | Discovered, but its outgoing references have not all been scanned |
| Black | Discovered and scanned |

The dangerous transition is an application write that removes the last visible path to a white object before the collector reaches it.

```text
black/grey A ──old edge──▶ white B
```

The SATB barrier preserves the old reference to `B`, making it available to the marking process even after the edge is overwritten.

The colours are a reasoning model. HotSpot implements marking with bitmaps, queues, buffers, and collector-specific metadata rather than Java-level colour fields.

## Floating garbage

SATB deliberately favours safety over reclaiming every newly dead object immediately.

If an object was reachable at the beginning but becomes unreachable during marking, it can remain marked for this cycle:

```text
At marking start:       root → A → B
During marking:         root → A
Current SATB result:    A and B are treated as live
Next marking cycle:     B can be discovered as unreachable
```

`B` is called **floating garbage**: it is currently unreachable, but it survives because it belonged to the logical starting snapshot.

It is normally reclaimable in a later collection cycle.

### New allocations

Objects allocated after the snapshot also need safe treatment. Collectors use implementation-specific rules so that a newly allocated object cannot be incorrectly reclaimed while the application is using it.

For G1, objects allocated in the portion of a region after the marking snapshot are treated as live for that cycle rather than requiring the concurrent marker to rediscover them through the old snapshot.

## SATB barrier vs. remembered-set barrier

These barriers solve different problems.

| Barrier purpose | Value normally observed | Why it exists |
|---|---|---|
| SATB concurrent marking | Old reference before overwrite | Preserves objects reachable in the logical starting snapshot |
| Remembered set / card marking | Information about the new reference or written field | Tracks references across regions or generations |

G1 needs both concepts:

- its SATB pre-write barrier supports concurrent marking;
- its post-write/card barrier helps maintain remembered sets for regional collection.

Generational ZGC can combine several checks in its store-barrier machinery, but the logical responsibilities remain distinct.

## SATB vs. incremental-update marking

Both strategies make concurrent marking safe, but they preserve different invariants.

| SATB | Incremental update |
|---|---|
| Preserves reachability from the beginning of marking | Repairs the marker's view toward the changing current graph |
| Primarily reacts to deleted/overwritten old references | Primarily reacts to newly inserted references |
| Commonly uses a pre-write old-value barrier | Commonly uses a post-write new-value barrier |
| Can retain floating garbage until a later cycle | May require more rescanning of modified objects or regions |

The exact barrier protocol is collector-specific; the table describes the high-level marking models, not a universal implementation recipe.

## Performance characteristics

SATB allows most tracing to happen concurrently, which reduces long marking pauses, but it is not free:

- Reference writes execute a barrier fast path.
- Old references may be appended to per-thread SATB buffers.
- GC threads must drain and trace buffered references.
- A high mutation rate can create more concurrent marking work.
- Remaining buffered work contributes to the Remark phase.
- Floating garbage can temporarily increase retained heap occupancy.

Buffers and fast-path checks keep most writes inexpensive. Collector implementations heavily optimize these paths because they run in application code.

## What SATB does not mean

- It is **not** a physical copy of the Java heap.
- It is **not** an immutable application-visible snapshot.
- It does not stop application threads for the entire marking phase.
- It does not mean that objects that die during marking are reclaimed immediately.
- It is unrelated to snapshot iterators such as `CopyOnWriteArrayList.iterator()`.
- It is unrelated to database MVCC transaction snapshots.
- It is an internal GC mechanism; ordinary Java code does not invoke it directly.

## Practical mental model

```text
1. Remember which objects were reachable when marking began.
2. Trace concurrently while the application changes references.
3. Before an old reference disappears, preserve it in an SATB queue.
4. Finish queued work during marking/Remark.
5. Treat the completed logical snapshot as live for this cycle.
6. Collect newly floating garbage during a later cycle.
```

## Summary

> SATB is a concurrent marking model that preserves the object graph as it logically existed at the start of marking. A pre-write barrier captures an overwritten old reference before the application replaces it, allowing the collector to finish tracing objects that otherwise might disappear from the current graph. The result is safe concurrent marking with short coordination pauses, at the cost of write-barrier work and possible floating garbage that survives until a later collection.

## Official references

- [Oracle Java 26 GC Tuning Guide — G1 marking](https://docs.oracle.com/en/java/javase/26/gctuning/garbage-first-g1-garbage-collector1.html)
- [JEP 439: Generational ZGC — SATB marking barriers](https://openjdk.org/jeps/439)
- [OpenJDK G1 barrier implementation](https://github.com/openjdk/jdk/tree/master/src/hotspot/share/gc/g1)
