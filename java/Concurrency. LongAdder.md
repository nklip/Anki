# LongAdder in Modern Java

## Front

How does `LongAdder` work, why can it outperform `AtomicLong`, and when should it be used?

## Back

**`LongAdder` was added in JDK 8.**

`LongAdder` is a thread-safe counter optimized for frequent updates from many competing threads.

```java
import java.util.concurrent.atomic.LongAdder;

LongAdder requests = new LongAdder();

requests.increment();
requests.add(5);
requests.decrement();

long total = requests.sum();
```

Its key trade-off is:

```text
higher update throughput under contention
                in exchange for
more memory and a sum that is not an atomic snapshot
```

It is designed for statistics and measurements, not for sequence numbers or synchronization decisions.

## Main operations

| Method | Meaning |
|---|---|
| `increment()` | Equivalent to `add(1)` |
| `decrement()` | Equivalent to `add(-1)` |
| `add(long x)` | Adds an arbitrary value |
| `sum()` | Calculates `base + all cells` |
| `longValue()` | Equivalent to `sum()` |
| `reset()` | Resets maintained values to zero |
| `sumThenReset()` | Collects the maintained values and resets them |

`LongAdder` does not provide operations such as:

- `compareAndSet()`
- `getAndIncrement()`
- `incrementAndGet()`
- An atomic `set()` followed by exact concurrent reads

Those operations require one authoritative value, which would defeat the striped design.

## Internal organization

![LongAdder striped cells](svg/longadder-striped-cells.svg)

The current OpenJDK implementation inherits its mechanics from an internal class named `Striped64`.

Conceptually, a `LongAdder` contains:

```text
base
cells[0]
cells[1]
cells[2]
...
```

The visible total is calculated as:

```text
sum = base + cells[0] + cells[1] + ...
```

These fields and exact expansion rules are implementation details, not public API contracts.

## Low-contention path

The cells array is created lazily. When contention is low, an update first tries to change `base` with CAS:

```text
read base
    ↓
CAS(base, base + delta)
    ↓
success → update complete
```

This keeps the common uncontended case small and efficient.

## What happens under contention?

If several threads repeatedly fail to update the same `base`, the implementation creates a striped array of `Cell` objects.

Each updating thread uses a per-thread probe to select a cell:

```text
index = probe & (cells.length - 1)
```

The thread then updates that cell's value using CAS:

```text
Thread A → cell[0]
Thread B → cell[3]
Thread C → cell[1]
Thread D → cell[2]
```

Instead of every thread contending for one cache location, updates are distributed across multiple locations.

## Collision handling

Two threads can still select the same cell. If a cell CAS fails, the implementation may:

1. Retry with a changed probe.
2. Create a cell in an empty slot.
3. Expand the cells array when contention persists.
4. Temporarily fall back to updating `base`.

The current implementation starts the cells array lazily and expands it in powers of two, up to an implementation-defined CPU-based limit.

A small CAS-controlled internal guard is used only while creating or resizing the array and installing cells. Normal counter updates do not acquire one global counter lock.

## Avoiding false sharing

Cells in an array would normally be placed close together in memory. Independent threads updating adjacent cells could then invalidate the same CPU cache line, causing **false sharing**.

OpenJDK pads its internal cells so that frequently updated values are less likely to share a cache line:

```text
without padding:
[cell 0][cell 1][cell 2]  → may share one cache line

with padding:
[cell 0 + space] [cell 1 + space] [cell 2 + space]
```

This improves high-contention throughput but increases memory consumption.

## How `sum()` works

`sum()` reads `base` and then traverses the current cells:

```java
long result = adder.sum();
```

Conceptually:

```java
long result = base;

for (Cell cell : cells) {
    if (cell != null) {
        result += cell.value;
    }
}
```

The pseudocode explains the current implementation; `Cell` is not part of the public API.

When there are no concurrent updates, `sum()` returns the accurate total.

## `sum()` is not an atomic snapshot

While `sum()` traverses the stripes, other threads can continue updating them:

```text
read base
read cell[0]
Thread B updates cell[1]
read cell[1]
Thread C updates cell[0]
return combined result
```

The values can therefore be observed at different moments. A concurrent update may or may not be included.

This is correct for metrics such as request counts, where a temporarily approximate observation is acceptable. It is incorrect when the value controls a business invariant.

Do not write synchronization logic like this:

```java
if (inUse.sum() < limit) {
    inUse.increment(); // not an atomic check-and-increment
}
```

Use a `Semaphore`, lock, bounded queue, or another atomic coordination mechanism for a hard limit.

## AtomicLong compared with LongAdder

![AtomicLong compared with LongAdder](svg/longadder-vs-atomiclong.svg)

### `AtomicLong`

`AtomicLong` stores one authoritative value:

```java
AtomicLong sequence = new AtomicLong();
long id = sequence.incrementAndGet();
```

It supports linearizable reads, CAS, and atomic read-modify-write operations that return an exact previous or updated value.

Under heavy write contention, all threads repeatedly modify the same memory location.

### `LongAdder`

`LongAdder` spreads updates across several values:

```java
LongAdder completedRequests = new LongAdder();
completedRequests.increment();
```

It reduces contention, but `increment()` returns `void` and `sum()` is not a linearizable read of one variable.

## Practical choice

| Requirement | Prefer |
|---|---|
| Request, event, or error statistics | `LongAdder` |
| Many threads frequently update one metric | `LongAdder` |
| Occasional approximate observation is acceptable | `LongAdder` |
| Unique sequence numbers | `AtomicLong` |
| Exact `getAndIncrement()` result | `AtomicLong` |
| CAS or synchronization state | `AtomicLong` |
| Hard capacity or multi-step invariant | Semaphore, lock, or another higher-level mechanism |

Under low contention, `AtomicLong` and `LongAdder` often have similar characteristics. Under high contention, `LongAdder` generally provides higher expected update throughput at the cost of additional space and more expensive reads.

## Frequency map with ConcurrentHashMap

The Java API documentation recommends this pattern for a scalable histogram or frequency map:

```java
ConcurrentHashMap<String, LongAdder> frequencies =
        new ConcurrentHashMap<>();

frequencies
        .computeIfAbsent(word, ignored -> new LongAdder())
        .increment();
```

Each key has its own `LongAdder`, and each adder can stripe further when updates to that particular key become contended.

Read the current count with:

```java
LongAdder count = frequencies.get(word);
long value = count == null ? 0 : count.sum();
```

## `reset()` and `sumThenReset()`

`reset()` is intrinsically racy when updates occur concurrently:

```java
adder.reset();
```

Use it only when no threads are updating the adder.

`sumThenReset()` is approximately equivalent to reading the sum and resetting the maintained values:

```java
long intervalTotal = adder.sumThenReset();
```

It is useful at a **quiescent point** between computations. With concurrent updates, it is not guaranteed to return every update that occurred before the reset, and an update can fall into an unexpected measurement interval.

For reliable interval metrics with continuous writers, use a design that rotates counters safely or delegates interval handling to a metrics library.

## Additional details

- `LongAdder` extends `Number`; `intValue()`, `floatValue()`, and `doubleValue()` convert the calculated sum.
- It intentionally does not define value-based `equals()`, `hashCode()`, or `compareTo()`.
- It should not be used as a map key whose identity depends on the changing count.
- Like ordinary `long` arithmetic, the sum can overflow and wrap around.
- Serialization records a current calculated sum, not the internal stripe layout.

## Summary

`LongAdder` maintains a sum across a `base` value and dynamically created padded cells. Uncontended updates normally CAS the base; contended threads spread across cells to reduce cache and CAS contention. `sum()` combines all maintained values but is not an atomic snapshot. Use `LongAdder` for highly contended statistics, and use `AtomicLong` or a higher-level synchronization mechanism when an exact linearizable value is required.

## Official references

- [Java 25 API: LongAdder](https://docs.oracle.com/en/java/javase/25/docs/api/java.base/java/util/concurrent/atomic/LongAdder.html)
- [OpenJDK source: LongAdder.java](https://github.com/openjdk/jdk/blob/master/src/java.base/share/classes/java/util/concurrent/atomic/LongAdder.java)
- [OpenJDK source: Striped64.java](https://github.com/openjdk/jdk/blob/master/src/java.base/share/classes/java/util/concurrent/atomic/Striped64.java)
