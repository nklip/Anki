# ConcurrentLinkedQueue in Modern Java

## Front

How does `ConcurrentLinkedQueue` work, what guarantees does it provide, and when should it be used?

## Back

`ConcurrentLinkedQueue<E>` is a thread-safe, unbounded, non-blocking FIFO queue based on linked nodes.

```java
Queue<String> queue = new ConcurrentLinkedQueue<>();

queue.offer("A");
queue.offer("B");

String first = queue.poll(); // A
String next = queue.peek();  // B remains in the queue
```

It is designed for many producers and consumers that need to exchange elements without a global queue lock.

## Main properties

| Property | Behavior |
|---|---|
| Ordering | FIFO |
| Capacity | Unbounded |
| Thread safety | Concurrent producers and consumers are supported |
| Coordination | Lock-free algorithm using CAS |
| `null` elements | Not allowed |
| `offer(e)` | Appends and normally returns `true` |
| `poll()` | Removes the head, or returns `null` when empty |
| `peek()` | Reads the head without removing it |
| Blocking operations | None — no `put()` or `take()` |
| Iterator | Weakly consistent |
| `size()` | O(n), and may be inaccurate during concurrent changes |

Because `null` elements are forbidden, `poll()` can use `null` unambiguously to mean that no element was available.

## Internal organization

![ConcurrentLinkedQueue internal organization](svg/concurrentlinkedqueue-structure.svg)

Conceptually, the queue is a singly linked chain:

```text
head → Node → Node → Node → null
                          ↑
                         tail
```

In the current OpenJDK implementation, a node contains approximately:

```java
class Node<E> {
    volatile E item;
    volatile Node<E> next;
}
```

The queue also maintains volatile `head` and `tail` references.

These details explain the implementation; they are not public API contracts that application code should depend on.

## Why `head` and `tail` are only hints

`head` and `tail` do not always point to the first and last physical nodes at every instant.

- `head` may temporarily point to a node whose `item` is already `null`.
- `tail` may temporarily lag behind the actual last linked node.
- Operations follow `next` links to find the required live node.
- Threads may help advance stale `head` or `tail` references.

Correctness depends on the node and item CAS operations, not on immediately updating the hints.

Allowing these references to lag reduces contention: every operation does not need to win another CAS merely to update an optimization pointer.

## Compare-and-set

CAS means **compare-and-set**:

```text
if current value == expected value:
    replace it with the new value atomically
else:
    report failure
```

A failed CAS means that another thread changed the observed state first. The operation reads the new state and retries.

## How `offer()` works

![ConcurrentLinkedQueue offer and poll workflow](svg/concurrentlinkedqueue-offer-poll.svg)

Conceptually, `offer(element)`:

1. Rejects `null`.
2. Creates a new node containing the element.
3. Starts from the `tail` hint and follows `next` links to the actual last node.
4. Atomically changes that last node's `next` from `null` to the new node using CAS.
5. Tries to advance the `tail` hint.

```text
Before:
A → B → null       new C

CAS B.next: null → C

After:
A → B → C → null
```

The successful CAS of `last.next` is the **linearization point**: the precise logical instant when the offered element becomes part of the queue.

Moving `tail` afterward is best effort. If that CAS fails, the element is still correctly linked and another operation can help advance `tail`.

## How `poll()` works

Conceptually, `poll()`:

1. Starts from the `head` hint.
2. Skips nodes whose `item` is already `null`.
3. Finds the first live node.
4. Atomically changes its `item` from the element to `null` using CAS.
5. Returns the removed element.
6. May advance `head` and help unlink obsolete nodes.

```text
Before:
[item=A] → [item=B] → [item=C]

CAS first.item: A → null

After logical removal:
[item=null] → [item=B] → [item=C]
```

The successful CAS that changes `item` to `null` is the removal's **linearization point**.

Changing the item to `null` is logical removal. Physical cleanup can happen later, allowing other threads to continue without waiting for a global lock.

If no live element is found, `poll()` returns `null` immediately. It does not wait for a producer.

## Why the algorithm is lock-free

The queue does not use one lock around all operations. Competing threads use CAS and retry when their expected state has changed.

```text
Thread A and Thread B attempt the same CAS
                ↓
one succeeds; the other observes failure
                ↓
the losing thread rereads and retries
```

This provides **lock-free progress**: under contention, the system as a whole continues to make progress because a failed CAS normally means some competing operation succeeded.

Lock-free does **not** mean:

- Every individual operation completes in a fixed number of steps.
- A thread can never be delayed or starved.
- Operations cannot pause because of scheduling, allocation, or garbage collection.
- The queue provides blocking `take()` semantics.

`ConcurrentLinkedQueue` is lock-free, but not wait-free.

## FIFO under concurrency

Elements are removed in the FIFO order established by successful insertions.

When two producers call `offer()` concurrently, source-code timing alone does not determine which insertion wins. The order of their successful link CAS operations determines their FIFO order.

```text
Thread A starts offer(A)
Thread B starts offer(B)

If B links first: B is before A in the queue.
```

## Iteration

Its iterator is **weakly consistent**:

```java
for (String value : queue) {
    process(value);
}
```

The iterator:

- Does not throw `ConcurrentModificationException` merely because the queue changes.
- Can run while producers and consumers modify the queue.
- Preserves FIFO order among the elements it observes.
- Is not a frozen snapshot.
- May reflect some concurrent changes and not others.

Use an external snapshot or other coordination when an exact, stable view is required.

## `size()` is not a coordination mechanism

Calculating the size requires traversing the linked nodes:

```java
int count = queue.size(); // O(n)
```

Other threads may add or remove elements during traversal, so the returned number can already be stale or may not represent one atomic instant.

Do not write check-then-act logic like this:

```java
if (queue.size() < limit) {
    queue.offer(task); // another producer may have changed the queue
}
```

Use a bounded queue, semaphore, or another explicit capacity-control mechanism when a hard limit is required.

## Memory visibility

`ConcurrentLinkedQueue` provides the standard concurrent-collection happens-before guarantee:

```text
Producer initializes object
        ↓
Producer places object in queue
        ↓ happens-before
Consumer accesses or removes that object
        ↓
Consumer sees the initialization performed before publication
```

```java
Message message = new Message();
message.setText("ready");
queue.offer(message);

// Another thread
Message received = queue.poll();
if (received != null) {
    System.out.println(received.getText()); // safely published as "ready"
}
```

This does not make later unsynchronized mutations of the element automatically safe. The queue safely transfers the reference; the element's subsequent thread safety is a separate concern.

## Bulk operations are not one atomic transaction

Operations such as `addAll`, `removeIf`, `retainAll`, `clear`, and `forEach` may overlap concurrent modifications. Do not assume the whole bulk operation happens as one indivisible queue update.

## When to use it

Use `ConcurrentLinkedQueue` when:

- Many threads concurrently add and remove elements.
- FIFO ordering is required.
- Consumers should return immediately when the queue is empty.
- An unbounded, lock-free queue is appropriate.

Avoid it when:

- Consumers must wait for work — use a `BlockingQueue`.
- Capacity must be bounded for backpressure.
- Constant-time or exact `size()` is required.
- A stable snapshot iteration is required.
- Elements must be added or removed from both ends — consider `ConcurrentLinkedDeque`.

## Choosing a queue

| Requirement | Typical choice |
|---|---|
| Unbounded, non-blocking FIFO | `ConcurrentLinkedQueue` |
| Optionally bounded linked blocking queue | `LinkedBlockingQueue` |
| Bounded array-backed blocking queue | `ArrayBlockingQueue` |
| Non-blocking access at both ends | `ConcurrentLinkedDeque` |

An unbounded queue can grow until memory is exhausted if producers consistently outpace consumers. Thread safety does not provide backpressure.

## Summary

`ConcurrentLinkedQueue` is an unbounded FIFO queue that uses linked nodes, volatile state, and CAS instead of a global lock. `offer()` linearizes when it links a new node; `poll()` linearizes when it changes the first live node's item to `null`. Head and tail may lag because they are traversal hints. Iteration is weakly consistent, `size()` is O(n), and empty consumers return immediately rather than block.

## Official references

- [Java 25 API: ConcurrentLinkedQueue](https://docs.oracle.com/en/java/javase/25/docs/api/java.base/java/util/concurrent/ConcurrentLinkedQueue.html)
- [OpenJDK source: ConcurrentLinkedQueue.java](https://github.com/openjdk/jdk/blob/master/src/java.base/share/classes/java/util/concurrent/ConcurrentLinkedQueue.java)
