# ConcurrentHashMap

## Front

How does `ConcurrentHashMap` work in modern Java, which operations are atomic, what visibility and iteration guarantees does it provide, and when should it be used?

## Back

**ConcurrentHashMap** was introduced in **Java 5 (JDK 1.5)** as a thread-safe hash table for concurrent retrievals and updates.

`ConcurrentHashMap<K,V>` is usually the right general-purpose map when many threads share key-value state. Retrievals such as `get()` generally do not block; updates combine atomic compare-and-set (CAS) operations with fine-grained coordination. Atomic methods such as `putIfAbsent`, `compute`, and `merge` protect one mapping operation, but they do not create a transaction across the whole map.

The first diagram explains bins and update coordination. The second contrasts a broken compound update with an atomic per-key update. The third shows how threads cooperate during resizing.

It supports:

- Full concurrency for retrievals such as `get()`.
- High expected concurrency for updates.
- Atomic conditional and per-key compound operations.
- Traversal while other threads update the map.

It provides no sorted order and no atomic whole-map snapshot.

```java
import java.util.concurrent.ConcurrentHashMap;

public final class ConcurrentHashMapBasics {
    public static void main(String[] args) {
        ConcurrentHashMap<String, Integer> counts =
                new ConcurrentHashMap<>();

        counts.put("apple", 1);
        counts.merge("apple", 1, Integer::sum);

        System.out.println(counts.get("apple")); // 2
        System.out.println(counts.get("pear"));  // null
    }
}
```

Important properties:

| Property | Guarantee |
|---|---|
| Thread-safe methods | Yes |
| `null` keys | Not allowed |
| `null` values | Not allowed |
| Ordering | No guaranteed encounter order |
| Retrieval locking | `get()` generally does not lock |
| Iterators | Weakly consistent; no `ConcurrentModificationException` |
| Atomic compound methods | `putIfAbsent`, conditional `remove`/`replace`, `compute*`, `merge` |
| Whole-map snapshot | Not provided |

## Internal organization

![ConcurrentHashMap internal structure](svg/concurrenthashmap-internal-structure.svg)

The JDK 7 implementation used a fixed `Segment[]` array. Since Java 8, OpenJDK uses one table of bins instead; the old segment-shaped serialized fields remain only for compatibility.

Conceptually, it contains a power-of-two array of bins:

```text
table[0] → empty
table[1] → Node → Node → Node
table[2] → Node
table[3] → TreeBin containing tree nodes
...
```

A mapping is stored in a node containing approximately:

```java
// Conceptual fragment based on the current OpenJDK Node class.
final int hash;
final K key;
volatile V value;
volatile Node<K,V> next;
```

This is an explanatory representation of the current OpenJDK implementation, not public API.

### Finding a bin

The map spreads the key's hash and uses the table length to select a bin:

```text
spread(key.hashCode())
        ↓
index = (table.length - 1) & hash
```

The table length is a power of two, allowing the index calculation to use a bit mask rather than division.

Keys used in any hash map should have stable `equals()` and `hashCode()` behavior while stored in the map. Mutating fields involved in either method can make an entry effectively unreachable.

## How `get()` works

Retrieval operations generally do not acquire a bin lock:

```text
Read current table
        ↓
Read bin head
        ↓
Compare hash and key
        ↓
Traverse list or tree
        ↓
Return current value or null
```

The implementation uses volatile/acquire reads and safely published nodes. A reader can overlap writers and resizing activity.

`get(key)` must reflect an update for that key that completed before the retrieval began. When a retrieval overlaps an update, it may legally observe the mapping before or after that update, according to their concurrent timing.

`get()` is therefore **non-blocking in the ordinary map-locking sense**, but that statement does not make it formally lock-free under every JVM or application condition. For example, user-defined `hashCode()` or `equals()` can execute arbitrary code.

## How updates work

The modern implementation combines CAS and fine-grained bin coordination.

### Empty bin

When the target bin is empty, insertion normally uses CAS:

```text
table[index] == null
        ↓
CAS(null, newNode)
        ↓
success or retry
```

No bin monitor is needed for the successful empty-bin insertion.

### Occupied bin

When the bin already contains nodes, updates coordinate on that bin—normally by synchronizing on its current first node and validating that it is still the bin head.

```text
bin 3 update ──coordinates with── other bin 3 updates

bin 3 update ──can proceed with── bin 9 update
```

This is often called **per-bin locking**. It is not:

- One global map lock.
- One permanent lock object per key.
- The old `Segment[]` architecture.

Different keys can still contend when their hashes place them in the same bin. A slow `equals()`, `hashCode()`, or remapping function can therefore delay other updates associated with that bin.

### What `concurrencyLevel` means now

This constructor still exists for compatibility:

```java
// Constructor shape; concurrencyLevel is not a segment count.
new ConcurrentHashMap<>(
        initialCapacity,
        loadFactor,
        concurrencyLevel
);
```

In modern Java, `concurrencyLevel` is only an **initial sizing hint**. It does not create that number of segments or locks.

## Collision handling and tree bins

A bin normally starts as a linked list. With many collisions, it may become a balanced tree:

```text
short bin:
Node → Node → Node

collision-heavy bin:
          TreeNode
         /        \
    TreeNode    TreeNode
```

Current OpenJDK implementation thresholds are:

- Treeify around 8 nodes in one bin.
- Treeification requires a table capacity of at least 64.
- Otherwise, the map prefers resizing the table.
- A tree may become a list again around 6 nodes during a resize split.

These are implementation details, not API promises. They should explain performance, not become application logic.

Tree bins reduce the damage caused by severe hash collisions. Good `hashCode()` distribution is still important.

## Atomic operations

![ConcurrentHashMap atomic operations](svg/concurrenthashmap-atomic-operations.svg)

Thread safety of individual methods does not make an arbitrary sequence of calls atomic.

### Broken check-then-act

```java
// Conceptual fragment: Value and createValue() are application code.
if (!map.containsKey(key)) {
    map.put(key, createValue());
}
```

Two threads can both observe that the key is absent, create two values, and overwrite one another.

Use:

```java
// Conceptual fragment.
Value existing = map.putIfAbsent(key, candidate);
```

If value creation should happen only when the key is absent:

```java
// Conceptual fragment.
Value value = map.computeIfAbsent(
        key,
        ignored -> createValue()
);
```

### Lost update with `get()` followed by `put()`

Broken counter:

```java
// Conceptual fragment.
Integer current = counts.get(word);
counts.put(word, current + 1);
```

Two threads can read the same value and both publish the same incremented value.

Atomic alternative:

```java
// Conceptual fragment.
counts.merge(word, 1, Integer::sum);
```

or:

```java
// Conceptual fragment.
counts.compute(word, (key, current) ->
        current == null ? 1 : current + 1
);
```

### Atomic method summary

| Method | Atomic behavior for the relevant key |
|---|---|
| `putIfAbsent(k, v)` | Insert only when absent |
| `remove(k, v)` | Remove only when currently mapped to `v` |
| `replace(k, old, next)` | Replace only when currently mapped to `old` |
| `computeIfAbsent(k, f)` | Compute and install only when absent |
| `computeIfPresent(k, f)` | Recompute only when present |
| `compute(k, f)` | Recompute from the current value or absence |
| `merge(k, v, f)` | Insert `v` when absent; otherwise combine atomically |

Returning `null` from `compute`, `computeIfPresent`, or the `merge` remapping function removes the mapping. Returning `null` from `computeIfAbsent` leaves the key absent.

### Atomic per key does not mean one transaction across keys

```java
// Conceptual fragment: each call is atomic only for its own mapping.
map.compute("debit",  (k, v) -> v - 100);
map.compute("credit", (k, v) -> v + 100);
```

Each call is atomic for its relevant mapping, but another thread can observe the state between them.

Use a lock, immutable aggregate state, database transaction, or another coordination mechanism when an invariant spans several mappings.

## Remapping functions must be short and simple

Methods such as `computeIfAbsent`, `compute`, and `merge` may prevent some competing updates from completing while the function runs.

Good:

```java
// Conceptual fragment.
cache.computeIfAbsent(key, this::loadQuickly);
```

Potentially dangerous:

```java
// Conceptual fragment: do not block or update other mappings here.
cache.computeIfAbsent(key, ignored -> {
    callSlowRemoteService();
    waitForAnotherThread();
    updateSeveralOtherMappings();
    return value;
});
```

The remapping-function contracts require the computation to be short and simple. `compute` forbids modifying this map from its remapping function; the other remapping methods likewise forbid attempts to update other mappings from inside the function. A detectable recursive update that would never complete can throw `IllegalStateException`.

A function passed to `computeIfAbsent` is invoked at most once **for that method invocation** when the key is absent. If it throws or returns `null`, a later invocation may execute it again.

Do not place non-idempotent external side effects inside a remapping function unless the surrounding design tolerates exceptions, later calls, and contention.

## Scalable frequency map

For a highly contended histogram, store `LongAdder` values. This complete example follows the pattern recommended by the API:

```java
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.LongAdder;

public final class FrequencyCounter {
    private final ConcurrentHashMap<String, LongAdder> frequencies =
            new ConcurrentHashMap<>();

    public void record(String word) {
        frequencies
                .computeIfAbsent(word, ignored -> new LongAdder())
                .increment();
    }

    public long count(String word) {
        LongAdder counter = frequencies.get(word);
        return counter == null ? 0L : counter.sum();
    }

    public static void main(String[] args) {
        FrequencyCounter counter = new FrequencyCounter();
        counter.record("java");
        counter.record("java");
        System.out.println(counter.count("java")); // 2
    }
}
```

Why not repeatedly replace an `Integer`?

```text
ConcurrentHashMap<String, Integer>
        ↓
all updates for one key replace the same mapping

ConcurrentHashMap<String, LongAdder>
        ↓
map installs one counter atomically
        ↓
LongAdder spreads contended increments internally
```

The value object still has its own concurrency semantics. `ConcurrentHashMap` makes access to the mapping thread-safe; it does not automatically make arbitrary mutable values thread-safe.

## Memory consistency and safe publication

For a particular key, an update happens-before a subsequent non-null retrieval that reports the updated value.

```java
// Conceptual producer fragment.
Payload payload = new Payload();
payload.initialize();

map.put("job", payload);
```

Another thread:

```java
// Conceptual consumer fragment.
Payload payload = map.get("job");

if (payload != null) {
    payload.consumeInitializedState();
}
```

If `get("job")` returns the published payload, the reader sees the actions that preceded its publication through the map.

Conceptually:

```text
initialize payload
        happens-before
put(key, payload)
        happens-before
successful get(key) returning payload
        happens-before
consume initialized state
```

This safely publishes the state that existed before insertion. It does not make later unsynchronized mutations of `Payload` safe:

```java
// Conceptual fragment: the value object needs its own safety policy.
map.get("job").mutableField++;
```

The mutable object needs its own synchronization, immutability, atomic fields, or confinement policy.

## Iteration is weakly consistent

```java
// Conceptual fragment: concurrent updates may overlap this loop.
for (Map.Entry<String, User> entry : users.entrySet()) {
    process(entry);
}
```

An iterator may run while other threads insert, update, or remove entries.

It:

- Does not throw `ConcurrentModificationException` because of concurrent updates.
- Never requires a single global map lock.
- May observe some updates and miss others.
- Does not provide a point-in-time snapshot.
- Is intended to be used by one thread at a time.

Example:

```text
Iterator created when map contains A and B

Concurrent thread removes A and adds C

Iterator may observe:
A, B
B, C
A, B, C
or another state permitted by concurrent timing
```

The precise result should not be used as a transactional view of the map.

If a stable snapshot is required, copy the map using an application-level synchronization protocol that prevents relevant updates during the copy. Calling `new HashMap<>(concurrentMap)` alone does not stop concurrent changes.

## `size()` and aggregate state

During concurrent updates, methods such as:

```java
// Conceptual examples of transient aggregate observations.
map.size();
map.isEmpty();
map.containsValue(value);
map.mappingCount();
```

may reflect transient state. They are useful for monitoring and estimation but should not normally control a correctness-critical decision.

Broken assumption:

```java
// Conceptual fragment: another thread can insert after size().
if (map.size() < limit) {
    map.put(key, value);
}
```

Another thread can insert between the check and update. The map does not make the capacity rule atomic.

`mappingCount()` returns a `long` and is preferable when the map might theoretically contain more than `Integer.MAX_VALUE` mappings, but its value is still an estimate during concurrent mutation.

## Parallel bulk operations

`ConcurrentHashMap` supplies concurrent-friendly bulk operations:

- `forEach`
- `search`
- `reduce`

Example:

```java
// Conceptual fragment: counts contains LongAdder values.
long total = counts.reduceValuesToLong(
        10_000,
        LongAdder::sum,
        0L,
        Long::sum
);
```

The first argument is `parallelismThreshold`:

- `Long.MAX_VALUE` forces sequential execution.
- `1` requests maximum partitioning.
- Parallel tasks use `ForkJoinPool.commonPool()`.

Bulk operations are safe during concurrent updates, but the result is not necessarily an atomic whole-map snapshot. Reduction functions should be associative and commutative, and should not depend on encounter order.

For small maps or cheap functions, parallel overhead may be greater than the saved work. Measure before choosing a threshold.

## Cooperative resizing

![ConcurrentHashMap cooperative resize](svg/concurrenthashmap-cooperative-resize.svg)

The table is normally resized when its occupancy crosses an internal threshold corresponding roughly to a 0.75 load factor.

Modern resizing is cooperative. A replacement table, normally twice as large, is allocated. Threads claim disjoint ranges of old bins, split and transfer them, and replace transferred old slots with `ForwardingNode` markers. An operation that encounters one continues in the new table, and additional updater threads can help finish the transfer.

```text
old table bin i
        ↓ split using one additional hash bit
new table bin i
or
new table bin i + oldCapacity
```

Resizing does not require freezing all retrievals behind one global table lock. It is nevertheless real work and may affect latency and throughput.

When a reliable size estimate is available, provide `initialCapacity`:

```java
// Conceptual sizing example.
ConcurrentHashMap<String, User> users =
        new ConcurrentHashMap<>(expectedUsers);
```

The constructor interprets this as the expected number of mappings to accommodate, not necessarily the exact backing-array length.

## Why `null` is forbidden

```java
// Conceptual examples; both calls throw NullPointerException.
map.put(null, value); // NullPointerException
map.put(key, null);   // NullPointerException
```

With concurrent access, `get(key) == null` must unambiguously mean that no mapping was observed:

```java
// Conceptual fragment.
Value value = map.get(key);

if (value == null) {
    // no mapping observed
}
```

Allowing stored null values would make absence indistinguishable from a present mapping to null. The API also uses null as a control result in search, reduce, and remapping operations.

Use `Optional`, a sentinel object, or a domain-specific representation when “present but empty” is meaningful.

## Key-set views

Create a concurrent set backed by a `ConcurrentHashMap`:

```java
// Conceptual key-set example.
Set<String> onlineUsers =
        ConcurrentHashMap.newKeySet();

onlineUsers.add("alice");
onlineUsers.remove("bob");
```

You can also obtain a key-set view whose additions map every key to a common value:

```java
// Conceptual key-set view example.
ConcurrentHashMap<String, Boolean> map =
        new ConcurrentHashMap<>();

Set<String> keys = map.keySet(Boolean.TRUE);
keys.add("alice");
```

## When to use it

- Shared caches and registries.
- Concurrent lookup tables.
- Per-key state machines.
- Frequency maps with `LongAdder` values.
- Deduplication or membership sets through `newKeySet()`.
- Workloads with frequent reads and concurrent updates.
- Situations where weakly consistent traversal is acceptable.

## When another structure may be better

- Use an immutable map or ordinary `HashMap` for thread-confined state.
- Use `Collections.synchronizedMap(...)` when one coarse lock and externally synchronized compound traversal are intentional.
- Use `ConcurrentSkipListMap` when sorted keys, range queries, or navigation are required.
- Use a bounded cache library when eviction, expiration, loading, statistics, or size limits are required.
- Use an explicit lock or transactional design when invariants span several keys.

## Comparison

| Map | Shared mutation | Nulls | Ordering | Traversal during updates |
|---|---|---|---|---|
| `HashMap` | Requires external coordination | Yes | None | Do not traverse while unsafely mutating |
| `Collections.synchronizedMap` | Yes, using the wrapper's protocol | Depends on delegate | Depends on delegate | Manually synchronize on the wrapper while traversing |
| `ConcurrentHashMap` | Yes | No | None | Weakly consistent |
| `ConcurrentSkipListMap` | Yes | No | Sorted | Weakly consistent |

## Common misconceptions

### “Every operation is lock-free”

False. Retrievals generally avoid locking, but contended updates can coordinate through a bin monitor or tree-bin mechanism.

### “It has one lock per key”

False. Update coordination is based on bins. Different keys in one bin can contend.

### “It still uses segments”

False for modern Java. The old segment design was replaced in Java 8. The `concurrencyLevel` constructor parameter remains only as a sizing hint.

### “Thread-safe methods make this sequence atomic”

False:

```java
// Conceptual broken check-then-act sequence.
if (map.get(key) == null) {
    map.put(key, value);
}
```

Use the appropriate atomic map operation.

### “Its iterator is a snapshot”

False. It is weakly consistent and may incorporate concurrent changes.

### “Values stored in it become thread-safe”

False. The map safely coordinates and publishes mappings; mutable values require their own safety strategy.

## Interview summary

> Modern `ConcurrentHashMap` is a power-of-two table of bins, not a segmented map. Reads generally use volatile/acquire access and do not lock. An insertion into an empty bin usually uses CAS; updates to an occupied bin coordinate at bin granularity, allowing unrelated bins to update concurrently. Collision-heavy bins can become balanced trees. Atomic methods such as `putIfAbsent`, `compute`, and `merge` prevent per-key check-then-act races, but they do not create transactions across keys. Iterators are weakly consistent, aggregate counts may be transient during mutation, and successful per-key publication establishes the required visibility for a retrieval that observes the value. Resizing is cooperative: threads transfer bin ranges and leave forwarding nodes that redirect operations to the new table.

## Sources

- [Java SE 26 `ConcurrentHashMap` API](https://docs.oracle.com/en/java/javase/26/docs/api/java.base/java/util/concurrent/ConcurrentHashMap.html)
- [Java SE 26 `ConcurrentMap` API](https://docs.oracle.com/en/java/javase/26/docs/api/java.base/java/util/concurrent/ConcurrentMap.html)
- [Java SE 26 `java.util.concurrent` package summary — memory consistency](https://docs.oracle.com/en/java/javase/26/docs/api/java.base/java/util/concurrent/package-summary.html#MemoryVisibility)
- [Current OpenJDK `ConcurrentHashMap.java` source](https://github.com/openjdk/jdk/blob/master/src/java.base/share/classes/java/util/concurrent/ConcurrentHashMap.java)
- [OpenJDK 7 `ConcurrentHashMap.java` — legacy segmented implementation](https://github.com/openjdk/jdk7u/blob/master/jdk/src/share/classes/java/util/concurrent/ConcurrentHashMap.java)
- [OpenJDK 8 `ConcurrentHashMap.java` — bin-based redesign](https://github.com/openjdk/jdk8u/blob/master/jdk/src/share/classes/java/util/concurrent/ConcurrentHashMap.java)
