# HashMap in Modern Java — Java 25

## Front

How does `HashMap` work internally in modern Java?

Explain:

- Table allocation, capacity, load factor, and threshold.
- Hash spreading and bucket selection.
- Collision handling, linked lists, and tree bins.
- Resizing and the one-bit bucket split.
- Operation complexity and iteration cost.
- Correct key design, `null` handling, and concurrency limitations.
- Important modern methods and common traps.

## Back

`HashMap<K,V>` is a mutable, hash-table implementation of `Map<K,V>`.

Its main properties are:

| Property | Behavior |
|---|---|
| Ordering | No guaranteed iteration order |
| `null` keys | One `null` key is allowed |
| `null` values | Allowed, including for many keys |
| Duplicate keys | No; a new value replaces the old value for an equal key |
| Thread safety | Not thread-safe |
| Basic-operation cost | Expected O(1) with well-distributed hashes |
| Iterator behavior | Fail-fast on a best-effort basis |

```java
Map<String, Integer> scores = new HashMap<>();

scores.put("Alice", 10);
scores.put("Bob", 20);
scores.put("Alice", 30); // replaces Alice's old value
scores.put(null, 40);    // allowed
scores.put("Carol", null); // allowed
```

The exact fields, thresholds, tree shape, and resize algorithm below describe the current OpenJDK implementation. They explain behavior and performance, but they are not all Java API guarantees.

## Internal organization

![HashMap internal organization](svg/hashmap-internal-organization.svg)

Conceptually, a current OpenJDK `HashMap` contains fields similar to:

```java
Node<K,V>[] table;
Set<Map.Entry<K,V>> entrySet;
int size;
int modCount;
int threshold;
final float loadFactor;
```

The table is an array of **buckets**, also called bins. A bucket can be:

- Empty.
- A single node.
- A linked list of nodes that collided.
- A red-black tree bin after sufficiently many collisions.

A normal entry node is conceptually:

```java
static class Node<K,V> implements Map.Entry<K,V> {
    final int hash;   // cached spread hash
    final K key;
    V value;
    Node<K,V> next;
}
```

The array stores references to nodes. Keys and values are also stored as references; `HashMap` does not copy the key or value objects.

## Lazy table allocation

```java
Map<String, Integer> map = new HashMap<>();
```

The default constructor does not immediately allocate the ordinary 16-bucket table. The current implementation allocates the table lazily on the first insertion.

After allocation, the capacity is a power of two:

```text
16, 32, 64, 128, 256, ...
```

Power-of-two capacity makes bucket selection and resizing efficient.

## Capacity, size, load factor, and threshold

These terms are different:

```text
size        = number of key-value mappings
capacity    = table.length, after the table is allocated
load factor = how full the table may become before resize
threshold   = size limit that triggers the next resize
```

With the default load factor:

```text
loadFactor = 0.75
threshold  = capacity × 0.75
```

For a capacity of 16:

```text
threshold = 16 × 0.75 = 12
```

Resize happens when insertion makes:

```text
size > threshold
```

Therefore, with distinct keys and default sizing, the **13th mapping** triggers the first resize from 16 to 32. The 12th mapping still fits without resize.

### Current OpenJDK constants

| Constant | Current value | Meaning |
|---|---:|---|
| `DEFAULT_INITIAL_CAPACITY` | 16 | Default capacity after first allocation |
| `MAXIMUM_CAPACITY` | `1 << 30` | Largest normal power-of-two table capacity |
| `DEFAULT_LOAD_FACTOR` | `0.75f` | Default load factor |
| `TREEIFY_THRESHOLD` | 8 | Treeification considered around 8 nodes in one bin |
| `UNTREEIFY_THRESHOLD` | 6 | Used when deciding whether a tree split should become a list |
| `MIN_TREEIFY_CAPACITY` | 64 | Minimum table capacity before treeification |

These are implementation details, not values promised by the `HashMap` API.

## From key to bucket

![HashMap bucket selection and lookup](svg/hashmap-bucket-lookup.svg)

For a non-null key, the current implementation spreads the key's hash:

```java
static final int hash(Object key) {
    int h;
    return key == null
            ? 0
            : (h = key.hashCode()) ^ (h >>> 16);
}
```

It then selects a bucket using the table length `n`:

```java
int index = (n - 1) & hash;
```

This bit mask is valid because `n` is a power of two.

### Why spread the high bits?

When the table is small, `(n - 1) & hash` uses only the low bits of the hash. The XOR operation mixes some high bits into the low bits so that imperfect user hash functions are less likely to create avoidable collisions.

Hash spreading cannot rescue a key class whose `hashCode()` is fundamentally poor—for example, one that returns the same value for every instance.

### Which hash is cached?

Each operation computes `hashCode()` for the **incoming operation key**:

```java
map.get(searchKey);
map.put(searchKey, value);
```

However, each stored node caches the spread hash calculated when its key was inserted:

```java
final int hash;
```

Consequences:

- Lookup does not recompute `hashCode()` for every stored key in a bucket.
- Resize uses stored node hashes and does not call `hashCode()` again on stored keys.
- Mutating a stored key's hash-relevant state does not update the node's cached hash or move the node.

## How `get(key)` works

Conceptually:

```text
Compute the incoming key's spread hash
        ↓
Select table[(n - 1) & hash]
        ↓
Compare the first node's cached hash and key
        ↓
Traverse the linked list or tree bin
        ↓
Return its value, or null when no matching key exists
```

The current implementation first checks the cached hash. When hashes match, it checks whether the keys are:

1. The same object reference, or
2. Equal according to `equals()`.

Different hash codes mean unequal keys as far as hash lookup is concerned. Equal keys must therefore always return equal hash codes.

## `null` key and values

The `null` key is assigned spread hash 0 and is therefore stored in bucket 0.

```java
Map<String, Integer> map = new HashMap<>();

map.put(null, 10);
map.put(null, 20);

System.out.println(map.size());    // 1
System.out.println(map.get(null)); // 20
```

Bucket 0 is not reserved exclusively for `null`. A non-null key whose spread hash is 0 can collide with it, and normal equality checks distinguish them.

Because `null` values are allowed, this is ambiguous:

```java
V value = map.get(key);
```

A `null` result can mean either:

- The key is absent, or
- The key is present and maps to `null`.

Use `containsKey()` when the distinction matters:

```java
if (map.containsKey(key)) {
    V value = map.get(key); // may legitimately be null
}
```

`getOrDefault()` does not eliminate this ambiguity for an existing null mapping:

```java
map.put("x", null);

map.getOrDefault("x", "fallback"); // null, not "fallback"
```

## Collisions

A collision occurs when different keys select the same bucket.

The map still distinguishes them by cached hash and key equality:

```text
table[index] → Node A → Node B → Node C
```

Good hash distribution matters because a long list makes lookup scan many nodes.

### Treeification

In the current implementation, a list bin is considered for conversion to a red-black tree when insertion grows it to around 8 nodes.

Treeification occurs only when the table capacity is at least 64:

```text
bin reaches about 8 nodes
        ↓
capacity < 64  → resize the table instead
capacity ≥ 64  → convert the bin to a tree
```

Why resize first? At a small capacity, collisions may simply mean the table is too small. Increasing capacity often distributes those nodes across different buckets.

### Untreeification nuance

`UNTREEIFY_THRESHOLD` is 6 in current OpenJDK, but it should not be read as a public rule that every removal immediately converts a tree at exactly six nodes.

The threshold is notably used during a resize split. Removal can also untreeify based on the remaining tree shape. Application logic must not depend on the exact transition point.

### Are tree-bin operations always O(log n)?

Not unconditionally.

Tree bins usually improve a collision-heavy bucket substantially, especially when:

- Stored hashes differ, or
- Keys are mutually comparable and can provide a stable ordering.

For arbitrary non-`Comparable` keys that all have the same hash, current lookup may need to search both subtrees. Such adversarial cases do not have a universal strict O(log n) guarantee.

The safe statement is:

- `HashMap` provides expected O(1) basic operations with properly dispersed hashes.
- A plain collision list costs O(m) for a bin containing `m` nodes.
- A tree bin often provides O(log m)-like behavior when the keys can be ordered effectively.
- Correct, well-distributed `hashCode()` implementations remain essential.

## Resizing

![HashMap resize split](svg/hashmap-resize-split.svg)

When insertion makes `size > threshold`, the map normally doubles capacity:

```text
16 → 32 → 64 → 128 → ...
```

The threshold is recalculated for the new capacity.

### Why nodes do not need a full rehash

Suppose old capacity is 8 and new capacity is 16. A node from old bucket `j` can only:

- Stay at `j`, or
- Move to `j + oldCapacity`.

The implementation checks one newly relevant bit:

```java
if ((node.hash & oldCapacity) == 0) {
    // remains at index j
} else {
    // moves to index j + oldCapacity
}
```

The current resize algorithm:

- Reuses the cached spread hash.
- Does not call stored keys' `hashCode()` methods.
- Splits each old list into low and high lists.
- Preserves the original relative order inside each resulting list.
- Generally reuses existing nodes rather than recreating every ordinary node.

## Choosing an initial capacity

### Constructor capacity is not mapping capacity

```java
Map<Integer, String> map = new HashMap<>(100);
```

The argument is an initial table-capacity request, not a promise that 100 mappings will fit without resize.

In current OpenJDK with default load factor:

```text
requested initial capacity = 100
first allocated power-of-two table = 128
resize threshold = 128 × 0.75 = 96
97th distinct mapping triggers resize to 256
```

Before first allocation, the internal `threshold` field temporarily acts as an allocation-size placeholder. After allocation it becomes the actual resize threshold.

### `HashMap.newHashMap(expectedMappings)` — Java 19+

When the expected number of mappings is known, modern Java offers:

```java
HashMap<Integer, String> map = HashMap.newHashMap(100);
```

This factory sizes the map so that the expected number of mappings can be inserted without resize under the default load factor.

For 100 expected mappings in current OpenJDK, it leads to a capacity of 256 and threshold of 192.

### Do not grossly oversize

Iteration cost is proportional to:

```text
capacity + size
```

An enormous mostly empty table wastes memory and makes iteration slower because the iterator must examine empty buckets as well as mappings.

## Core methods and null semantics

### Read

```java
V value = map.get(key);
V valueOrDefault = map.getOrDefault(key, defaultValue);
boolean exists = map.containsKey(key);
```

### Write conditionally

```java
map.put(key, value);
map.putIfAbsent(key, value);
map.replace(key, newValue);
map.replace(key, expectedOldValue, newValue);
```

For `HashMap`, `putIfAbsent()` also installs the new value when the key currently maps to `null`.

### Remove conditionally

```java
map.remove(key);
map.remove(key, expectedValue);
```

### `computeIfAbsent`

```java
List<String> values = map.computeIfAbsent(
        key,
        ignored -> new ArrayList<>()
);
```

The function runs when the key is absent **or currently maps to `null`**. If the function returns `null`, no mapping is recorded.

### `computeIfPresent`

```java
map.computeIfPresent(key, (k, oldValue) -> transform(oldValue));
```

It runs only when the key is present with a non-null value. Returning `null` removes the mapping.

### `compute`

```java
map.compute(key, (k, oldValue) -> newValue);
```

The remapping function runs whether the mapping is present or absent. `oldValue` can be `null`. Returning `null` removes any existing mapping and leaves an absent key absent.

### `merge`

```java
counts.merge(word, 1, Integer::sum);
```

If the key is absent or maps to `null`, `merge()` installs the provided non-null value. Otherwise, it combines the old and provided values. If the remapping function returns `null`, the mapping is removed.

### Do not structurally mutate the same map from a remapping function

```java
map.computeIfAbsent(key, k -> {
    map.put(otherKey, value); // unsafe recursive structural modification
    return result;
});
```

Modern implementations can detect some recursive structural modifications and throw `ConcurrentModificationException`. Remapping functions should be short and should not structurally modify the same map.

## Live collection views

These methods return views backed by the map, not independent copies:

```java
Set<K> keys = map.keySet();
Collection<V> values = map.values();
Set<Map.Entry<K,V>> entries = map.entrySet();
```

Changes are reflected in both directions where the view operation is supported:

```java
keys.remove(key); // removes the mapping from map
map.clear();      // empties all three views
```

Use an explicit copy when a snapshot is required:

```java
Set<K> keySnapshot = new HashSet<>(map.keySet());
List<V> valueSnapshot = new ArrayList<>(map.values());
```

## Iteration and fail-fast behavior

```java
for (Map.Entry<K,V> entry : map.entrySet()) {
    // visit entry
}
```

Iteration order is unspecified and can change after resize or other modifications.

Iterators are fail-fast on a **best-effort basis**. A structural modification outside the iterator can cause `ConcurrentModificationException`:

```java
for (K key : map.keySet()) {
    map.remove(key); // may throw ConcurrentModificationException
}
```

Safe removal through that iterator:

```java
Iterator<K> iterator = map.keySet().iterator();

while (iterator.hasNext()) {
    K key = iterator.next();
    if (shouldRemove(key)) {
        iterator.remove();
    }
}
```

Fail-fast detection is for bug discovery. It is not a synchronization mechanism and must not be relied upon for program correctness.

## Concurrency

`HashMap` is not thread-safe.

Without external synchronization, concurrent reads and writes can produce:

- Lost updates.
- Stale observations.
- Inconsistent traversal.
- Internal state corruption.
- Data races even when a write only replaces an existing value.

The Java 7-era concurrent-resize linked-list cycle bug was removed by the Java 8 resize rewrite. That historical fix does **not** make current `HashMap` safe for unsynchronized concurrent access.

### External synchronization

```java
Map<K,V> map = Collections.synchronizedMap(new HashMap<>());
```

Individual wrapper operations synchronize on the wrapper. Iteration must be manually synchronized on the returned map:

```java
synchronized (map) {
    for (Map.Entry<K,V> entry : map.entrySet()) {
        // iterate safely relative to users of the same wrapper lock
    }
}
```

### Concurrent alternative

For a map shared by many threads, normally consider:

```java
ConcurrentHashMap<K,V> map = new ConcurrentHashMap<>();
```

Important differences:

- No `null` keys or values.
- Atomic per-key compound methods such as `putIfAbsent`, `compute`, and `merge`.
- Weakly consistent iterators that can overlap updates.
- Modern implementation uses CAS and fine-grained bin coordination, not the old fixed `Segment[]` design.

## Correct key design

### `equals()` and `hashCode()` contract

For any non-null objects `a` and `b`:

```text
a.equals(b) == true  ⇒  a.hashCode() == b.hashCode()
```

The reverse is not required. Equal hash codes can belong to unequal objects; that is a collision.

### Keys should be stable while stored

Fields used by `equals()` or `hashCode()` should not change while the object is a map key.

Broken example:

```java
final class MutableKey {
    String id;

    @Override
    public boolean equals(Object other) {
        return other instanceof MutableKey key
                && Objects.equals(id, key.id);
    }

    @Override
    public int hashCode() {
        return Objects.hash(id);
    }
}

MutableKey key = new MutableKey();
key.id = "A";

Map<MutableKey, String> map = new HashMap<>();
map.put(key, "value");

key.id = "B";

map.get(key); // commonly null: lookup now selects a different bucket
```

The entry can still appear during iteration because the node remains physically stored in its original bucket.

Prefer immutable keys:

```java
record UserId(long value) {}
```

Records work well when all components themselves have suitable stable value semantics.

### Arrays are identity keys by default

```java
byte[] a = {1, 2};
byte[] b = {1, 2};

System.out.println(a.equals(b)); // false
```

Arrays inherit identity-based `equals()` and `hashCode()` from `Object`. A record does not automatically fix this for an array component; its generated equality delegates to the component's normal equality behavior.

For binary content keys, use an immutable wrapper that copies the bytes and implements content equality:

```java
final class ByteKey {
    private final byte[] bytes;

    ByteKey(byte[] bytes) {
        this.bytes = bytes.clone();
    }

    @Override
    public boolean equals(Object other) {
        return other instanceof ByteKey key
                && Arrays.equals(bytes, key.bytes);
    }

    @Override
    public int hashCode() {
        return Arrays.hashCode(bytes);
    }
}
```

A `ByteBuffer` uses remaining-byte content, but its position, limit, and mutable backing bytes affect equality and hash codes. It is safe as a key only when that state and content are effectively frozen.

## Complexity summary

Let:

```text
n = number of mappings in the map
m = number of nodes in one selected bucket
c = table capacity
```

| Operation | Expected / typical cost | Important qualification |
|---|---:|---|
| `get`, `put`, `remove` | O(1) | Assumes properly dispersed hashes |
| Search in list bin | O(m) | Scans collided nodes |
| Search in orderable tree bin | Often O(log m) | Not an unconditional guarantee for adversarial non-comparable equal-hash keys |
| `containsKey` | Expected O(1) | Uses hash lookup |
| `containsValue` | O(n) | Must scan mappings |
| Iteration | O(c + n) | Empty buckets are examined |
| Resize | O(n) | Redistributes nodes; occasional operation |
| `size`, `isEmpty` | O(1) | Reads maintained state |

The expected O(1) claim is not a promise that every call takes constant time. Resizing, collisions, expensive user `hashCode()`/`equals()`, and tree-bin corner cases can cost more.

## Ordering and alternative map types

`HashMap` provides no encounter-order guarantee and is not a `SequencedMap`.

Choose another implementation when ordering is required:

| Requirement | Typical implementation |
|---|---|
| Fast unordered mutable map | `HashMap` |
| Insertion order or access order | `LinkedHashMap` |
| Sorted keys / navigation | `TreeMap` |
| Concurrent shared map | `ConcurrentHashMap` |
| Small immutable map | `Map.of(...)` / `Map.copyOf(...)` |

## Modern Java timeline

| Java version | Relevant change |
|---|---|
| Java 8 | Tree bins, new resize algorithm, `compute*`, and `merge` |
| Java 9 | `Map.of(...)` factories; stronger detection of some recursive remapping modifications |
| Java 10 | `Map.copyOf(...)` |
| Java 19 | `HashMap.newHashMap(expectedMappings)` |
| Java 21 | Sequenced collections introduced; `HashMap` intentionally remains unordered and is not a `SequencedMap` |
| Java 25 | Compact object headers became a product feature, but this does not change the `HashMap` algorithm and was not made the default by JEP 519 |

Compact object headers can reduce per-object overhead when enabled, including the overhead of node objects, but object layout is a JVM/runtime concern rather than a `HashMap` API property.

## Common misconceptions

### “The 12th insertion resizes the default map.”

No. Capacity 16 has threshold 12. Resize occurs after insertion makes `size > 12`, so the 13th distinct mapping triggers it.

### “`new HashMap<>(100)` fits 100 mappings without resize.”

Not with current OpenJDK defaults. Its first table is 128 buckets with threshold 96. Use `HashMap.newHashMap(100)` on Java 19+ when 100 is the expected mapping count.

### “Every lookup recomputes every stored key's hash.”

No. It hashes the incoming key. Stored nodes cache their spread hashes.

### “Tree bins make every collision attack strictly O(log n).”

No. Tree bins help greatly, but arbitrary non-comparable keys with identical hashes do not have a universal strict logarithmic lookup guarantee.

### “`getOrDefault()` distinguishes an absent key from a null mapping.”

No. An existing null mapping still returns `null`. Use `containsKey()` when the distinction matters.

### “Fail-fast iterators make `HashMap` thread-safe.”

No. Fail-fast behavior is best effort and is unrelated to safe publication, visibility, or atomicity.

### “Replacing an existing value concurrently is safe because it is not structural.”

No. It may not increment `modCount`, but it is still an unsynchronized data race.

## Interview summary

`HashMap` stores mappings in a lazily allocated, power-of-two `Node[]`. It spreads the incoming key's hash and selects a bucket with `(n - 1) & hash`. Nodes cache their spread hash. Collisions start as linked lists and may become red-black tree bins around eight nodes when capacity is at least 64. At the default load factor of 0.75, insertion beyond the threshold normally doubles capacity. During resize, each old bin splits between index `j` and `j + oldCapacity` by testing one hash bit, without recomputing stored keys' hash codes. Basic operations are expected O(1) with stable keys and well-distributed hashes, while iteration costs O(capacity + size). `HashMap` allows one null key and null values, has no order guarantee, is fail-fast only on a best-effort basis, and is not thread-safe.

## Official references

- [Java 25 `HashMap` API](https://docs.oracle.com/en/java/javase/25/docs/api/java.base/java/util/HashMap.html)
- [Java 25 `Map` API](https://docs.oracle.com/en/java/javase/25/docs/api/java.base/java/util/Map.html)
- [OpenJDK 25u `HashMap` source](https://github.com/openjdk/jdk25u/blob/master/src/java.base/share/classes/java/util/HashMap.java)
- [JEP 519: Compact Object Headers](https://openjdk.org/jeps/519)
