# How Does a Parallel Stream Work Internally?

## Front

How does a Java parallel stream internally split work, execute a pipeline, and combine results? What determines its correctness and performance?

## Back

A parallel stream does **not** create one thread per element. It builds a lazy pipeline, partitions its source with a `Spliterator`, processes chunks using fork/join tasks, and combines partial results into the terminal result.

```text
source
  ↓
Spliterator
  ↓ trySplit()
tree of partitions
  ↓
fork/join leaf tasks
  ↓
fused pipeline execution on each chunk
  ↓
partial results
  ↓ tree-shaped combination
final result
```

### Example

```java
long total = orders.parallelStream()
        .filter(Order::isCompleted)
        .mapToLong(Order::amountInCents)
        .sum();
```

Conceptually, Java performs these steps:

1. Create a parallel pipeline around the source's `Spliterator`.
2. Record `filter` and `mapToLong` as lazy pipeline stages.
3. Start evaluation when `sum()` is invoked.
4. Recursively split the source into chunks.
5. Process chunks concurrently.
6. Compute a partial sum for each chunk.
7. Combine the partial sums into the final result.

### 1. Pipeline construction is lazy

`Collection.parallelStream()` is conceptually equivalent to:

```java
StreamSupport.stream(collection.spliterator(), true);
```

The `true` value marks the pipeline as parallel. Intermediate operations do not immediately traverse the data:

```java
Stream<Order> stream = orders.parallelStream()
        .filter(Order::isCompleted)
        .map(Order::validated);

// No orders have been processed yet.
```

Each intermediate operation adds a stage to an internal pipeline. The source is consumed only when a terminal operation such as `sum()`, `reduce()`, `collect()`, `toList()`, or `forEach()` begins.

The most recent call to `parallel()` or `sequential()` determines the mode of the **entire pipeline**, not only the operations after that call:

```java
stream.parallel().map(...).sequential().reduce(...);
// The complete pipeline is evaluated sequentially.
```

In OpenJDK, `AbstractPipeline.evaluate()` chooses between the terminal operation's sequential and parallel implementations.

### 2. The `Spliterator` partitions the source

A `Spliterator` combines traversal with optional partitioning:

- `tryAdvance()` processes one element.
- `forEachRemaining()` processes the remaining elements.
- `trySplit()` attempts to divide the remaining source into two parts.
- `estimateSize()` reports the approximate remaining size.
- `characteristics()` describes useful source properties.

The internal task repeatedly calls `trySplit()` while a partition is large enough and can still be divided.

Conceptually:

```java
Result compute(Spliterator<T> part) {
    if (partIsSmallEnough(part)) {
        return processLeaf(part);
    }

    Spliterator<T> left = part.trySplit();
    if (left == null) {
        return processLeaf(part);
    }

    fork(left);
    Result rightResult = compute(part);
    Result leftResult = join(left);
    return combine(leftResult, rightResult);
}
```

The exact splitting threshold is an implementation detail. Current OpenJDK deliberately creates more leaf tasks than worker threads—roughly four target leaf tasks per pool-parallelism unit—to improve load balancing.

### Spliterator quality matters

Good parallel sources provide:

- Cheap, balanced splitting.
- Accurate size estimates.
- The `SIZED` and preferably `SUBSIZED` characteristics.
- Efficient, low-overhead element traversal.

Typical source behavior:

| Source | Parallel splitting |
|---|---|
| Array | Excellent: indexed, sized, balanced |
| `ArrayList` | Excellent: indexed and cheaply split |
| `IntStream.range()` | Excellent: known range and balanced splits |
| `HashSet` / `HashMap` views | Usually reasonable, but distribution can vary |
| `LinkedList` | More expensive to partition and traverse |
| Iterator or unknown-size source | Often poor: little sizing information and weaker splitting |
| I/O-backed source | Usually a poor fit for CPU-oriented parallel streams |

Important characteristics include:

- `ORDERED` — the source has an encounter order.
- `SIZED` — the estimated size is exact before traversal.
- `SUBSIZED` — child spliterators are also sized.
- `SORTED` and `DISTINCT` — may let stages avoid redundant work.
- `IMMUTABLE` or `CONCURRENT` — describes how source interference can be handled.

### 3. Fork/join tasks execute the partitions

OpenJDK represents parallel stream work with `ForkJoinTask`-based internal tasks.

By default, a parallel stream started by an ordinary external thread uses `ForkJoinPool.commonPool()`. The calling thread can also participate while waiting for the root task to complete.

The pool uses **work stealing**:

1. A worker processes tasks from its local queue.
2. Splitting produces more tasks.
3. An idle worker steals available work from another worker.
4. Workers continue until the root computation completes.

```text
                     root partition
                    /              \
               partition A     partition B
               /        \       /        \
             A1          A2    B1          B2
              ↓           ↓     ↓           ↓
            worker      worker worker      caller/worker
```

The number of partitions is not the same as the number of threads. A worker normally processes many chunks over the lifetime of a computation.

Parallel streams use fork/join worker threads, not one new platform thread per element and not one virtual thread per element.

### Which pool is used?

The public Stream API does not accept an `Executor` or `ForkJoinPool` parameter.

In the current OpenJDK implementation, invoking a parallel stream from inside a custom `ForkJoinPool` task normally causes its forked stream tasks to use that current pool:

```java
try (ForkJoinPool pool = new ForkJoinPool(4)) {
    long total = pool.submit(() ->
            orders.parallelStream()
                    .mapToLong(Order::amountInCents)
                    .sum()
    ).join();
}
```

However, pool selection through this technique is an implementation behavior rather than a guarantee of the Stream API. If strict executor ownership or isolation is required, use an API that accepts an executor explicitly.

### 4. Stateless stages are fused inside each leaf

For stateless operations such as `map`, `filter`, and `peek`, OpenJDK builds a chain of internal `Sink` objects.

Instead of creating an intermediate collection after every operation, each leaf task pushes an element through the complete stage chain:

```text
element
  → filter predicate
  → mapping function
  → terminal accumulator
```

The earlier example behaves approximately like this inside each chunk:

```java
long localSum = 0;

for (Order order : chunk) {
    if (order.isCompleted()) {
        localSum += order.amountInCents();
    }
}
```

This fusion avoids materializing separate filtered and mapped collections.

### 5. Reductions combine partial results

For a reduction, each leaf task creates its own partial result. Parent tasks combine their children's results as the task tree completes.

```text
chunk A → 10 ─┐
              ├→ 25 ─┐
chunk B → 15 ─┘      │
                     ├→ 50
chunk C → 20 ─┐      │
              ├→ 25 ─┘
chunk D →  5 ─┘
```

OpenJDK's parallel reduction task computes a leaf accumulator and then combines the left and right child results during task completion.

This is why a reduction function must be **associative**:

```text
(a op b) op c == a op (b op c)
```

Correct:

```java
int sum = numbers.parallelStream()
        .reduce(0, Integer::sum);
```

Incorrect because subtraction is not associative:

```java
int value = numbers.parallelStream()
        .reduce(0, (left, right) -> left - right);
```

Different valid partition trees can produce different results for a non-associative operation. Floating-point arithmetic is also not exactly associative, so low-order rounding differences may occur between sequential and parallel reductions.

### How `collect()` remains safe

A normal parallel collector typically creates a separate mutable container for each partition:

```text
chunk A → List A ─┐
                  ├→ combined list
chunk B → List B ─┘
```

The containers are combined only after their leaf work completes. Therefore, a normal collector does not require every partial `ArrayList` to be concurrently mutated.

For a collector marked `CONCURRENT`, the implementation may accumulate into one shared concurrent result when:

- The stream is parallel.
- The collector has `Collector.Characteristics.CONCURRENT`.
- The stream is unordered, or the collector is also marked `UNORDERED`.

### 6. Stateful operations create coordination points

Stateless operations process each element independently. Stateful operations need information about other elements:

- `sorted()` must observe and arrange the input.
- `distinct()` must track previously encountered values.
- Ordered `limit()`, `skip()`, `takeWhile()`, and `dropWhile()` may need coordination or buffering.

In OpenJDK, a stateful operation can end one parallel pipeline segment. That segment is evaluated, and its result becomes the input to the next segment.

```text
source → parallel filter/map → [stateful sorted barrier]
       → parallel map/reduce → result
```

Stateful stages can require extra memory, multiple passes, merging, or global coordination. They often reduce the benefit of parallelism.

### 7. Short-circuiting uses cooperative cancellation

Operations such as these may stop before visiting the complete source:

- `anyMatch()`
- `allMatch()`
- `noneMatch()`
- `findAny()`
- `findFirst()`
- `limit()`

Tasks communicate that a result or cancellation has been found. However, other leaf tasks may already be running, so some additional elements can still be processed before cancellation propagates.

`findAny()` can return a result from whichever partition completes suitably. `findFirst()` must respect encounter order and therefore usually requires more coordination.

Do not rely on a mapping or `peek()` function being called for every element when the terminal result does not require it.

### 8. Encounter order constrains execution

An ordered source such as a `List` has an encounter order. Parallel processing may execute elements in any thread and in a different scheduling order, but an order-sensitive result must still match the required encounter order.

```java
list.parallelStream().forEach(System.out::println);
// Output order is not guaranteed.

list.parallelStream().forEachOrdered(System.out::println);
// Encounter order is preserved.
```

`forEachOrdered()` can reduce throughput because publication of effects must be ordered. It does not mean every upstream computation necessarily runs on one thread.

If order does not matter, `unordered()` can remove constraints and help operations such as `distinct()`, `limit()`, or concurrent collection:

```java
Set<String> values = stream.parallel()
        .unordered()
        .collect(Collectors.toSet());
```

### 9. Lambdas must be non-interfering and usually stateless

Broken shared mutation:

```java
List<Integer> output = new ArrayList<>();

numbers.parallelStream()
        .map(n -> n * 2)
        .forEach(output::add); // data race and possible corruption
```

Correct reduction:

```java
List<Integer> output = numbers.parallelStream()
        .map(n -> n * 2)
        .toList();
```

Synchronizing the shared list might prevent corruption, but contention can remove the performance benefit. An atomic counter may be thread-safe yet still become a hot shared bottleneck.

Do not modify a non-concurrent stream source while its pipeline is executing. Results may be incorrect, fail-fast, or otherwise nonconforming.

### 10. Parallel does not automatically mean faster

Parallel execution adds costs:

- Source partitioning.
- Task creation and scheduling.
- Work stealing and coordination.
- Partial-result allocation and combination.
- Ordered-result reconstruction.
- Stateful-operation buffering.
- Contention for the shared common pool.

Parallel streams are most promising when:

- The source is large and splits efficiently.
- Per-element work is CPU-intensive enough to amortize overhead.
- Operations are stateless and independent.
- Reduction is associative and cheap to combine.
- Encounter-order constraints are limited.
- Multiple CPU cores are available.

Sequential streams are often better when:

- The input is small.
- Each operation is very cheap.
- The source splits poorly.
- The pipeline contains expensive ordered or stateful stages.
- Work updates shared mutable state.
- The environment already has heavy common-pool usage.

Always benchmark realistic workloads; pipeline shape, source type, collector, machine, and surrounding load all matter.

### Blocking operations are a poor default fit

The fork/join pool is primarily designed for compute-oriented tasks. Blocking on network, file, database, or unmanaged synchronization can occupy workers and delay unrelated common-pool work. The pool does not guarantee compensation for arbitrary blocked I/O.

```java
urls.parallelStream()
        .map(httpClient::blockingRequest) // usually a poor design
        .toList();
```

For blocking I/O, prefer an explicit concurrency design with controlled resource limits, cancellation, timeouts, and—where appropriate—virtual threads. Parallel streams themselves do not execute one virtual thread per element.

### Common misconceptions

| Misconception | Reality |
|---|---|
| One element gets one thread | A task processes a chunk containing many elements |
| Parallel operations run in source order | Scheduling is free to differ; only required result order is preserved |
| `forEach()` preserves list order | Only `forEachOrdered()` promises encounter order |
| A thread-safe collection makes a stateful lambda a good idea | It may be safe but nondeterministic or contention-heavy |
| `parallelStream()` always uses all processors | Available parallelism, source splitting, workload, pool contention, and ordering all matter |
| Parallel streams use virtual threads | Current implementation uses fork/join tasks and pool workers |
| Parallel is always faster | Overhead can dominate small or cheap computations |

### Complete mental model

```text
1. Build a lazy pipeline and mark it parallel.
2. Invoke a terminal operation.
3. Obtain the source Spliterator.
4. Split it recursively into target-sized partitions.
5. Schedule internal fork/join tasks.
6. Let workers steal tasks for load balancing.
7. Run fused stateless stages inside each leaf task.
8. Coordinate or buffer at stateful stages when required.
9. Combine partial results up the task tree.
10. Return from the terminal operation after the root task completes.
```

### Key idea

> A parallel stream is a lazy data pipeline evaluated as a fork/join tree: the `Spliterator` determines how well the source divides, leaf tasks determine how efficiently elements are processed, and the terminal operation determines how results are combined.

### Official references

- [`java.util.stream` package documentation](https://docs.oracle.com/en/java/javase/26/docs/api/java.base/java/util/stream/package-summary.html)
- [`Spliterator` API](https://docs.oracle.com/en/java/javase/26/docs/api/java.base/java/util/Spliterator.html)
- [`ForkJoinPool` API](https://docs.oracle.com/en/java/javase/26/docs/api/java.base/java/util/concurrent/ForkJoinPool.html)
- [OpenJDK `AbstractPipeline`](https://github.com/openjdk/jdk/blob/master/src/java.base/share/classes/java/util/stream/AbstractPipeline.java)
- [OpenJDK `AbstractTask`](https://github.com/openjdk/jdk/blob/master/src/java.base/share/classes/java/util/stream/AbstractTask.java)
- [OpenJDK `ReduceOps`](https://github.com/openjdk/jdk/blob/master/src/java.base/share/classes/java/util/stream/ReduceOps.java)
