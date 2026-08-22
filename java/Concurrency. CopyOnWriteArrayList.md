# CopyOnWriteArrayList

## Front

How does `CopyOnWriteArrayList` work, what guarantees does it provide, and when should it be used instead of another concurrent collection?

## Back

`CopyOnWriteArrayList<E>` is a thread-safe `List` optimized for workloads where **reads and traversals vastly outnumber mutations**.

Every successful mutation creates and publishes a new backing array:

```text
Readers ───────────────▶ current array A

Writer:
array A → copy to array B → modify B → publish B

New readers ───────────▶ array B
Existing iterators ────▶ array A
```

Reads are cheap and do not take the mutation lock. Writes are expensive because they copy the array.

### Basic example

```java
CopyOnWriteArrayList<String> names =
        new CopyOnWriteArrayList<>();

names.add("Alice");
names.add("Bob");

String first = names.getFirst();

for (String name : names) {
    System.out.println(name);
}
```

It preserves list encounter order, implements `RandomAccess`, permits duplicate elements, and permits `null`.

### Simplified internal design

The current OpenJDK implementation is conceptually similar to:

```java
final class SimplifiedCopyOnWriteList<E> {
    private final Object lock = new Object();
    private volatile Object[] array = new Object[0];

    E get(int index) {
        Object[] snapshot = array;
        return (E) snapshot[index];
    }

    void add(E element) {
        synchronized (lock) {
            Object[] oldArray = array;
            Object[] newArray = Arrays.copyOf(
                    oldArray,
                    oldArray.length + 1
            );

            newArray[oldArray.length] = element;
            array = newArray; // volatile publication
        }
    }
}
```

This is an explanatory model, not public API. Important ideas are:

1. The backing-array reference is published with volatile semantics.
2. Readers obtain a stable array reference.
3. Mutations are serialized by an internal lock.
4. Writers never modify the array currently used by readers.
5. A completed mutation atomically replaces the visible array reference.

### Snapshot iterators

An iterator captures the backing array that existed when the iterator was created:

```java
CopyOnWriteArrayList<String> list =
        new CopyOnWriteArrayList<>(List.of("A", "B"));

Iterator<String> iterator = list.iterator();

list.add("C");
list.remove("A");

iterator.forEachRemaining(System.out::println);
```

Output:

```text
A
B
```

The iterator does not see `C`, and it still sees `A`. It traverses the old immutable snapshot even though the current list is now `[B, C]`.

Snapshot iterators:

- Never throw `ConcurrentModificationException` because of later list changes.
- Need no external synchronization during traversal.
- Do not reflect additions, removals, or replacements made after creation.
- Do not support `remove()`, `set()`, or `add()`; those operations throw `UnsupportedOperationException`.

The spliterator is also snapshot-based and reports `IMMUTABLE`, `ORDERED`, `SIZED`, and `SUBSIZED`.

### Reads versus writes

| Operation | Typical cost | Important detail |
|---|---:|---|
| `get(index)` | O(1) | Reads the current array snapshot |
| `size()` | O(1) | Reads the current array length |
| `contains(value)` | O(n) | Linear scan |
| Iteration | O(n) | No mutation lock; stable snapshot |
| `add(value)` | O(n) | Allocates and copies an array |
| `set(index, value)` | O(n) | Normally copies before publication |
| `remove(...)` | O(n) | Searches when needed, then copies |
| `addIfAbsent(value)` | O(n) | Atomic presence check; copies only when added |

A write also temporarily requires memory for both the old and new arrays. Old arrays remain reachable while iterators or spliterators still reference them.

### Excellent use case: listener registry

```java
final class EventBus {
    private final CopyOnWriteArrayList<EventListener> listeners =
            new CopyOnWriteArrayList<>();

    void register(EventListener listener) {
        listeners.addIfAbsent(listener);
    }

    void unregister(EventListener listener) {
        listeners.remove(listener);
    }

    void publish(Event event) {
        for (EventListener listener : listeners) {
            listener.onEvent(event);
        }
    }
}
```

This design works well when events are published frequently but listeners are registered or removed rarely.

If a listener is added during `publish()`, it will participate in a later traversal, not the current snapshot. A listener removed during the traversal may still receive the current event if it exists in that snapshot.

### `addIfAbsent()` versus check-then-add

Broken compound operation:

```java
if (!listeners.contains(listener)) {
    listeners.add(listener);
}
```

Two threads can both observe that the element is absent and both add it.

Use the atomic method:

```java
listeners.addIfAbsent(listener);
```

For multiple elements:

```java
int added = listeners.addAllAbsent(newListeners);
```

Thread safety of individual methods does not automatically make an arbitrary sequence of methods atomic.

### Memory-consistency guarantee

Actions performed by one thread before placing an object into the list happen-before another thread subsequently accesses or removes that element through the list.

```java
message.prepare();
messages.add(message); // safely publishes preceding state
```

```java
Message message = messages.get(0);
message.consume();     // sees state published before add()
```

This safely publishes the element reference and its preceding state. It does **not** make later unsynchronized mutations inside the element thread-safe.

```java
CopyOnWriteArrayList<MutableCounter> counters = ...;

counters.get(0).increment();
// The counter still needs its own thread-safety policy.
```

The list copies references, not the referenced objects.

### Best use cases

- Event-listener and observer registries.
- Routing or handler lists that change rarely.
- Small configuration snapshots read frequently.
- Allow-lists or rule lists with rare administrative updates.
- Traversals that must not be blocked by concurrent registration changes.

It is most suitable when all of these are true:

```text
reads ≫ writes
list is relatively small
snapshot iteration is acceptable
write latency and allocation are acceptable
```

### Poor use cases

- Large lists with frequent additions, removals, or replacements.
- Producer-consumer queues.
- High-frequency counters or mutable shared state.
- Workloads requiring an iterator to observe the newest change immediately.
- Algorithms performing repeated indexed mutations.
- Situations where old snapshots retaining elements would be costly.

Bad pattern:

```java
CopyOnWriteArrayList<Integer> list =
        new CopyOnWriteArrayList<>();

for (int i = 0; i < 100_000; i++) {
    list.add(i); // repeatedly copies a growing array
}
```

Build the data before constructing the copy-on-write list:

```java
List<Integer> initial = new ArrayList<>();

for (int i = 0; i < 100_000; i++) {
    initial.add(i);
}

CopyOnWriteArrayList<Integer> list =
        new CopyOnWriteArrayList<>(initial);
```

Prefer bulk methods such as `addAll()` or `removeIf()` over many separate mutations when they express the required operation.

### Compound indexed traversal can still be inconsistent

Each call is thread-safe, but separate calls may observe different snapshots:

```java
for (int i = 0; i < list.size(); i++) {
    use(list.get(i));
}
```

A concurrent removal can occur between `size()` and `get()`, potentially invalidating the index. Prefer snapshot iteration:

```java
for (Element element : list) {
    use(element);
}
```

### Be careful with `subList()`

`subList()` returns a view backed by the original list. Its semantics become undefined if the backing list is modified by any route other than the returned view.

Do not retain a sublist while unrelated threads directly modify the parent list. If a stable range snapshot is needed, first copy the whole list and then select the range:

```java
List<Element> fullSnapshot = List.copyOf(list);
List<Element> rangeSnapshot = List.copyOf(
        fullSnapshot.subList(from, to)
);
```

### Comparison with alternatives

| Collection | Reads | Writes | Iteration behavior | Good for |
|---|---|---|---|---|
| `CopyOnWriteArrayList` | Very cheap | O(n) copy | Stable snapshot | Read-mostly lists |
| `Collections.synchronizedList(...)` | Locked | Locked | Caller must synchronize traversal | Mixed operations with one lock |
| `ConcurrentLinkedQueue` | Concurrent | Concurrent | Weakly consistent | Frequent queue insertion/removal |
| `ConcurrentHashMap` | Concurrent key lookup | Concurrent updates | Weakly consistent | Keyed shared state |
| Immutable `List` | Very cheap | No mutation | Stable | State replaced as a whole elsewhere |

If element uniqueness is the main requirement and ordering rules fit, consider `CopyOnWriteArraySet`, which is backed by copy-on-write storage.

### Advantages

- Simple, thread-safe traversal without explicit locking.
- Readers do not block writers through the mutation lock.
- Stable and deterministic snapshot for each iterator.
- No iterator interference or fail-fast exception from later mutations.
- Safe publication through the concurrent collection.

### Disadvantages

- O(n) copying and allocation on mutation.
- Mutations are serialized.
- Temporary memory pressure from multiple arrays.
- Iterators intentionally return stale snapshots.
- Long-lived iterators can retain removed elements through an old array.
- Does not protect the mutable state of contained objects.

### Key idea

> `CopyOnWriteArrayList` makes reads and snapshot traversal cheap by making every mutation expensive. Use it when the collection is small, reads vastly outnumber writes, and observing a stable but potentially stale snapshot is exactly the desired behavior.

### Official references

- [`CopyOnWriteArrayList` API](https://docs.oracle.com/en/java/javase/26/docs/api/java.base/java/util/concurrent/CopyOnWriteArrayList.html)
- [OpenJDK `CopyOnWriteArrayList` implementation](https://github.com/openjdk/jdk/blob/master/src/java.base/share/classes/java/util/concurrent/CopyOnWriteArrayList.java)
