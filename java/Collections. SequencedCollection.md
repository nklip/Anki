# Collections. SequencedCollection

## Front

What is `SequencedCollection` in modern Java, which operations does it provide, and how does `reversed()` work?

## Back

`SequencedCollection<E>` is an interface added in **JDK 21** by **JEP 431: Sequenced Collections**.

It represents a collection with a defined **encounter order** from the first element to the last element:

```java
public interface SequencedCollection<E> extends Collection<E> {
    void addFirst(E e);
    void addLast(E e);

    E getFirst();
    E getLast();

    E removeFirst();
    E removeLast();

    SequencedCollection<E> reversed();
}
```

### Why was it added?

Before JDK 21, ordered collections exposed their ends through inconsistent APIs:

```java
list.get(0);
list.get(list.size() - 1);

deque.getFirst();
deque.getLast();

sortedSet.first();
sortedSet.last();
```

Some ordered collections, such as `LinkedHashSet`, did not have a convenient uniform API for accessing both ends.

`SequencedCollection` gives these types one common vocabulary:

- first and last element;
- insertion and removal at either end, when supported;
- traversal in reverse encounter order.

### Encounter order

Encounter order is the order in which iteration, streams, and array conversion observe the elements.

For this collection:

```text
[A, B, C]
```

- first element: `A`
- last element: `C`
- normal encounter order: `A, B, C`
- reversed encounter order: `C, B, A`

Encounter order is not necessarily insertion order:

- `ArrayList` normally uses index order;
- `LinkedHashSet` normally uses insertion order;
- `TreeSet` uses its sorted order.

### Main operations

| Method | Meaning |
|---|---|
| `getFirst()` | Returns the first element |
| `getLast()` | Returns the last element |
| `addFirst(e)` | Adds an element at the beginning, if supported |
| `addLast(e)` | Adds an element at the end, if supported |
| `removeFirst()` | Removes and returns the first element, if supported |
| `removeLast()` | Removes and returns the last element, if supported |
| `reversed()` | Returns a reverse-ordered view |

### Basic example

```java
SequencedCollection<String> tasks = new ArrayList<>();

tasks.addLast("compile");
tasks.addLast("test");
tasks.addFirst("clean");

System.out.println(tasks);            // [clean, compile, test]
System.out.println(tasks.getFirst()); // clean
System.out.println(tasks.getLast());  // test
```

Removing elements from both ends:

```java
String first = tasks.removeFirst(); // clean
String last = tasks.removeLast();   // test

System.out.println(tasks);          // [compile]
```

`getFirst()`, `getLast()`, `removeFirst()`, and `removeLast()` throw `NoSuchElementException` when the collection is empty.

```java
SequencedCollection<String> empty = new ArrayList<>();
empty.getFirst(); // NoSuchElementException
```

### `reversed()` returns a view, not a copy

```java
SequencedCollection<String> original =
        new ArrayList<>(List.of("A", "B", "C"));

SequencedCollection<String> reversed = original.reversed();

System.out.println(original); // [A, B, C]
System.out.println(reversed); // [C, B, A]
```

The first element of the original is the last element of the reversed view, and vice versa.

When a modification is supported by the view, it writes through to the underlying collection:

```java
reversed.removeFirst();

System.out.println(original); // [A, B]
System.out.println(reversed); // [B, A]
```

Adding to one end of the reversed view targets the opposite end of the original:

```java
reversed.addFirst("D");

System.out.println(original); // [A, B, D]
System.out.println(reversed); // [D, B, A]
```

The general interface contract says that visibility of changes made directly to the backing collection can depend on the implementation. Do not assume that every custom implementation has identical view behavior.

Applying `reversed()` twice restores the original logical encounter order:

```java
original.reversed().reversed(); // A, B, D
```

This does not promise that the returned object has the same identity as `original`.

### Which collections are sequenced?

Important subinterfaces include:

- `List`
- `Deque`
- `SequencedSet`
- `SortedSet`
- `NavigableSet`

Common implementations include:

- `ArrayList`
- `LinkedList`
- `ArrayDeque`
- `CopyOnWriteArrayList`
- `LinkedHashSet`
- `TreeSet`
- `ConcurrentLinkedDeque`

`HashSet` is not sequenced because it does not define a stable encounter order.

`HashMap` is also not sequenced. Ordered maps use the separate `SequencedMap` interface.

### Related interfaces

```text
Collection
    |
    +-- SequencedCollection
            |
            +-- List
            +-- Deque
            +-- SequencedSet
                    |
                    +-- SortedSet
                            |
                            +-- NavigableSet
```

- `SequencedCollection` provides ordered access to both ends.
- `SequencedSet` combines encounter order with unique elements.
- `SequencedMap` provides first, last, and reversed operations for key-value mappings; it is not a subtype of `SequencedCollection`.

### Operations may be unsupported

The interface defines semantics, but it does not require every collection to support every modification.

An unmodifiable list rejects changes:

```java
SequencedCollection<String> fixed = List.of("A", "B", "C");

fixed.addFirst("X");    // UnsupportedOperationException
fixed.removeLast();     // UnsupportedOperationException
```

`TreeSet` is ordered by its comparator or natural ordering, so the caller cannot choose an arbitrary first or last position:

```java
SequencedCollection<Integer> numbers = new TreeSet<>();

numbers.addFirst(10); // UnsupportedOperationException
numbers.addLast(20);  // UnsupportedOperationException
```

Normal `TreeSet.add(...)` remains supported because the set determines the element's sorted position.

### Performance depends on the implementation

`SequencedCollection` does not guarantee a particular time complexity.

| Implementation | First-end operations | Last-end operations |
|---|---:|---:|
| `ArrayList` | `getFirst()` is O(1); insertion/removal is O(n) | access/removal is O(1); addition is amortized O(1) |
| `LinkedList` | O(1) | O(1) |
| `ArrayDeque` | amortized O(1) | amortized O(1) |
| `TreeSet` | end lookup is O(log n); explicit end insertion is unsupported | end lookup is O(log n); explicit end insertion is unsupported |

Choose the concrete collection according to the required access pattern, not only according to the interface name.

### Generic API example

An API can now accept many kinds of ordered collections without depending on `List`, indexes, or `Deque`:

```java
static void printEnds(SequencedCollection<?> values) {
    if (values.isEmpty()) {
        System.out.println("empty");
        return;
    }

    System.out.println("first = " + values.getFirst());
    System.out.println("last  = " + values.getLast());
}
```

Reverse traversal is similarly generic:

```java
static void printInReverse(SequencedCollection<?> values) {
    values.reversed().forEach(System.out::println);
}
```

Streams also follow the reversed encounter order:

```java
List<String> result = tasks.reversed()
        .stream()
        .map(String::toUpperCase)
        .toList();
```

### `reversed()` vs `Collections.reverse(...)`

```java
List<String> values = new ArrayList<>(List.of("A", "B", "C"));

Collections.reverse(values); // mutates values in place
List<String> view = values.reversed(); // creates a reverse-ordered view
```

`Collections.reverse(list)` rearranges the list itself.

`list.reversed()` leaves the original encounter order intact and exposes that list through the opposite order.

### Common mistakes

- `reversed()` does not sort elements in descending order; it reverses the existing encounter order.
- A sequenced collection is not automatically a set: duplicates may still be allowed.
- A sequenced collection does not necessarily support random access.
- `addFirst()` and `addLast()` are optional operations.
- End operations are not guaranteed to be O(1).
- `SequencedCollection` does not make a collection thread-safe.
- Null-element policy still depends on the concrete implementation.

## Summary

```text
SequencedCollection = Collection + defined first-to-last encounter order

JDK introduced: 21

Read ends:       getFirst(), getLast()
Add ends:        addFirst(), addLast()       optional
Remove ends:     removeFirst(), removeLast() optional
Reverse order:   reversed()                 view, not copy

Semantics are common.
Mutability, null policy, thread safety, and performance depend on the implementation.
```

## Official references

- [SequencedCollection API — Java 25](https://docs.oracle.com/en/java/javase/25/docs/api/java.base/java/util/SequencedCollection.html)
- [JEP 431: Sequenced Collections](https://openjdk.org/jeps/431)
- [Creating Sequenced Collections, Sets, and Maps](https://docs.oracle.com/en/java/javase/24/core/creating-sequenced-collections-sets-and-maps.html)
