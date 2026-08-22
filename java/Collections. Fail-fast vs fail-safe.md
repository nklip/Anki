# Collections. Fail-Fast vs. Fail-Safe Iteration

## Front

What is the difference between fail-fast and “fail-safe” iterators in Java, and how should collections be modified during iteration?

## Back

In Java collection discussions:

- A **fail-fast iterator** detects an unexpected structural modification and normally throws `ConcurrentModificationException`.
- **Fail-safe iterator** is common informal terminology, but it is **not an official Java iterator category**.
- Java documentation uses more precise terms such as **snapshot iterator** and **weakly consistent iterator**.

```text
fail-fast
    → detect unexpected interference on a best-effort basis

snapshot
    → traverse a stable copy or immutable version

weakly consistent
    → safely traverse a live concurrent structure
```

## Comparison

| Behavior | Typical examples | Concurrent changes |
|---|---|---|
| Fail-fast | `ArrayList`, `HashMap`, `HashSet` | Normally throws `ConcurrentModificationException` when detected |
| Snapshot | `CopyOnWriteArrayList`, `CopyOnWriteArraySet` | Iterator sees the state captured at creation |
| Weakly consistent | `ConcurrentHashMap`, `ConcurrentLinkedQueue` | Traversal continues and may reflect some changes |

## How fail-fast iteration works

![Fail-fast compared with weakly consistent iteration](svg/iteration-fail-fast-vs-weakly-consistent.svg)

Many ordinary collection implementations maintain a structural modification counter, commonly called `modCount`.

When an iterator is created, it remembers the current value:

```text
collection.modCount = 3
iterator.expectedModCount = 3
```

A structural modification made directly through the collection changes `modCount`:

```text
collection.add(element)
collection.modCount = 4
```

On a later iterator operation, the implementation compares the values:

```text
expectedModCount != modCount
        ↓
throw ConcurrentModificationException
```

`modCount` and the exact checking locations are implementation details, but they explain the common behavior of general-purpose collections.

## Broken modification during enhanced `for`

An enhanced `for` loop normally uses an iterator internally:

```java
List<String> names = new ArrayList<>(
        List.of("Alice", "Bob", "Carol")
);

for (String name : names) {
    if (name.startsWith("B")) {
        names.remove(name); // invalid interference with the iterator
    }
}
```

The direct `names.remove()` structurally modifies the list without informing the active iterator. A fail-fast iterator will normally detect this and throw `ConcurrentModificationException`.

The bug can occur in a **single thread**. Despite its name, `ConcurrentModificationException` does not prove that multiple threads were involved.

## Safe removal with the iterator

Use the iterator's own supported mutation operation:

```java
Iterator<String> iterator = names.iterator();

while (iterator.hasNext()) {
    String name = iterator.next();

    if (name.startsWith("B")) {
        iterator.remove();
    }
}
```

The iterator updates its expected structural version together with the collection.

A `ListIterator` may additionally support `add()` and `set()` according to its contract.

## Prefer collection operations when possible

For simple filtering, `removeIf()` is clearer:

```java
names.removeIf(name -> name.startsWith("B"));
```

Another option is to collect changes and apply them after traversal:

```java
List<String> toRemove = new ArrayList<>();

for (String name : names) {
    if (name.startsWith("B")) {
        toRemove.add(name);
    }
}

names.removeAll(toRemove);
```

These techniques solve same-thread iteration logic. They do not by themselves make a non-concurrent collection safe for access from several threads.

## What is a structural modification?

A structural modification changes the collection's size or internal traversal structure.

For `ArrayList`:

- `add()` is structural.
- `remove()` is structural.
- Explicitly resizing the backing structure is structural.
- Replacing an element with `set(index, value)` is not normally structural.

```java
ListIterator<String> iterator = names.listIterator();

while (iterator.hasNext()) {
    if (iterator.next().equals("Alice")) {
        iterator.set("Alicia"); // supported replacement
    }
}
```

The precise meaning depends on the collection. For example, access-ordered `LinkedHashMap` can structurally change its encounter order when `get()` is called.

## Fail-fast is best-effort only

Fail-fast detection is not guaranteed in the presence of unsynchronized concurrent modification.

```text
ConcurrentModificationException = useful bug signal
ConcurrentModificationException ≠ synchronization mechanism
```

Never write correctness logic that depends on the exception being thrown:

```java
try {
    iterate(sharedList);
} catch (ConcurrentModificationException ignored) {
    // Incorrect: the exception is not guaranteed
}
```

If several threads use an `ArrayList` and at least one modifies it structurally, coordinate access with synchronization or choose an appropriate concurrent collection.

## Snapshot iterators

![Snapshot compared with weakly consistent iteration](svg/iteration-snapshot-vs-weakly-consistent.svg)

`CopyOnWriteArrayList` creates a fresh array for every mutation. Its iterator retains a reference to the array that existed when the iterator was created:

```java
CopyOnWriteArrayList<String> names =
        new CopyOnWriteArrayList<>(List.of("A", "B", "C"));

Iterator<String> iterator = names.iterator();

names.add("D");

iterator.forEachRemaining(System.out::println);
// A, B, C — never D
```

The iterator's array never changes, so:

- It cannot observe later additions, removals, or replacements.
- It does not throw `ConcurrentModificationException` because of later writes.
- Traversal needs no external synchronization.
- Iterator mutation methods such as `remove()`, `set()`, and `add()` are unsupported.

Snapshot iteration is excellent when reads and traversals greatly outnumber writes. Copying the entire array for every mutation is expensive for write-heavy workloads.

## Weakly consistent iterators

Concurrent collections such as `ConcurrentHashMap` and `ConcurrentLinkedQueue` provide weakly consistent traversal:

```java
ConcurrentHashMap<String, Integer> scores =
        new ConcurrentHashMap<>();

scores.put("Alice", 10);
scores.put("Bob", 20);

for (var entry : scores.entrySet()) {
    // Other threads may update scores concurrently.
}
```

A weakly consistent iterator:

- Does not throw `ConcurrentModificationException` merely because concurrent updates occur.
- Can proceed while the collection is modified.
- Does not normally copy the whole collection.
- Is not a frozen snapshot.
- May reflect some concurrent additions, removals, or replacements and not others.

Exact visibility and duplication guarantees depend on the specific collection. Read that class's API contract rather than relying only on the phrase “weakly consistent.”

An iterator object is also normally intended to be used by one thread at a time, even when it comes from a concurrent collection.

## Snapshot vs. weakly consistent

| Question | Snapshot iterator | Weakly consistent iterator |
|---|---|---|
| Stable view? | Yes | No |
| Sees later writes? | No | Possibly |
| Copies data for mutation? | Typically yes | Typically no full copy |
| Throws CME for concurrent writes? | No | No |
| Best workload | Many traversals, few writes | Frequent concurrent reads and writes |

Both behaviors are often called “fail-safe,” but that label hides an important difference.

## Synchronized wrappers still require care

Wrapping an `ArrayList` does not turn its iterator into a weakly consistent or snapshot iterator:

```java
List<String> names = Collections.synchronizedList(
        new ArrayList<>()
);
```

The collection must be manually synchronized during the entire traversal:

```java
synchronized (names) {
    for (String name : names) {
        process(name);
    }
}
```

All access to the backing collection must go through the synchronized wrapper for the guarantee to hold.

For a synchronized map, synchronize on the map wrapper itself while iterating over its key, value, or entry views.

## Choosing the right behavior

| Requirement | Typical choice |
|---|---|
| Detect accidental same-thread structural modification | Ordinary fail-fast collection |
| Stable iteration while writes continue | `CopyOnWriteArrayList` |
| Frequent concurrent map updates and traversal | `ConcurrentHashMap` |
| Frequent concurrent FIFO updates and traversal | `ConcurrentLinkedQueue` |
| One exact snapshot of a concurrent structure | Copy under coordination or use an application-specific snapshot |
| Compound invariant across traversal and updates | Lock or another explicit coordination mechanism |

## Common interview traps

### Does `ConcurrentModificationException` require multiple threads?

No. Directly modifying a collection during its own iteration can trigger it in one thread.

### Does fail-fast mean thread-safe?

No. It means unexpected modification may be detected quickly on a best-effort basis.

### Does “fail-safe” mean the iterator sees all new elements?

No. A snapshot iterator sees none of the later changes; a weakly consistent iterator may see some.

### Can application correctness depend on CME?

No. The exception is a bug detector, not a guaranteed concurrency signal.

### Can `iterator.remove()` always be used?

No. It is optional. Snapshot iterators from `CopyOnWriteArrayList` do not support it.

## Summary

Fail-fast iterators from ordinary collections detect unexpected structural interference and throw `ConcurrentModificationException` on a best-effort basis. “Fail-safe” is an informal umbrella term that should be replaced with the precise behavior: snapshot iterators traverse a fixed old view, while weakly consistent iterators traverse a changing concurrent structure. Choose the collection based on the consistency, write cost, and coordination guarantees the application actually needs.

## Official references

- [Java 25 API: ConcurrentModificationException](https://docs.oracle.com/en/java/javase/25/docs/api/java.base/java/util/ConcurrentModificationException.html)
- [Java 25 API: ArrayList](https://docs.oracle.com/en/java/javase/25/docs/api/java.base/java/util/ArrayList.html)
- [Java 25 API: CopyOnWriteArrayList](https://docs.oracle.com/en/java/javase/25/docs/api/java.base/java/util/concurrent/CopyOnWriteArrayList.html)
- [Java 25 API: ConcurrentHashMap](https://docs.oracle.com/en/java/javase/25/docs/api/java.base/java/util/concurrent/ConcurrentHashMap.html)
- [Java 25 API: Collections synchronized wrappers](https://docs.oracle.com/en/java/javase/25/docs/api/java.base/java/util/Collections.html)
