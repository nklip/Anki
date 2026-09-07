# Concurrency. Parallel Stream Internals

<!-- Card mode: complex. Validate with --mode complex. -->

## Front

You call `orders.parallelStream()`. Explain what the JDK actually does: how the source becomes chunks, what runs those chunks, how the pipeline stages execute inside one chunk, and how partial results become one answer. Which of those details does the Stream API guarantee, and which are only today's implementation?

## Back

**The Stream API, including parallel streams, was introduced in Java 8 under JSR 335.**

In one sentence: **a parallel stream cuts the source into chunks, runs the same pipeline over each chunk on a shared pool of threads, and merges the partial results.**

Three things follow from that sentence, and they are what interviews probe:

1. Nothing runs while you chain `filter()` and `map()`. The **last** call — `sum()`, `collect()`, `forEach()` — starts everything.
2. Elements do **not** get one thread each. Chunks get tasks, and a small pool of threads runs those tasks.
3. `parallel()` is **not** a promise of speed. Cutting, scheduling and merging all cost something.

![concurrency-parallel-stream-execution-pipeline.svg](images/concurrency-parallel-stream-execution-pipeline.svg)

### Vocabulary, before anything else

These six words carry the whole card. Each one is defined properly at the level named on its right; the table is only so that no term appears before you have met it.

| Term | What it means | Taught in |
|---|---|---|
| **Pipeline** | The chain of calls you write. A recipe, not a running computation | Level 2 |
| **Terminal operation** | The last call. It starts the work and decides what the result is | Level 2 |
| **Spliterator** | The object that walks a source and can cut it in two | Level 3 |
| **Chunk / leaf task** | One slice of the source, and the unit of work that processes it | Level 3 |
| **Sink** | One pipeline stage at run time, wired to the stage after it | Level 4 |
| **Fork/join** | The scheduler that runs leaf tasks on a shared pool of threads | Level 5 |

### How this card is organised

Each level answers one question and assumes only the levels above it.

| Level | The question it answers |
|---|---|
| 1 | What is the short answer? |
| 2 | What are the moving parts, and why does laziness matter? |
| 3 | How does one source become a tree of chunks? |
| 4 | What actually executes inside a single chunk? |
| 5 | Which threads run those chunks, and who schedules them? |
| 6 | Why does the parallel answer equal the sequential answer? |
| 7 | What happens to encounter order and short-circuiting? |
| 8 | When is parallel execution actually faster? |

Every number below was measured on one 12-core machine. The **counts** — 11 workers, 64 leaf tasks, `41` versus `76` — are deterministic and come out the same on JDK 25 and JDK 26. The **timings** are from JDK 25 and illustrate the mechanism; they are not constants.

## Level 1 — The short answer

Four sentences, in this order:

1. A stream pipeline is a **recipe**. Intermediate operations such as `filter()` and `map()` only record what to do.
2. The terminal operation starts the work, and the pipeline's **most recent** `parallel()` or `sequential()` call decides the mode for the whole pipeline.
3. In parallel mode a `Spliterator` cuts the source into chunks, and fork/join tasks apply the recorded stages to each chunk.
4. The terminal operation defines how the partial results are merged — or, if it only causes side effects, what ordering you get instead.

Three claims that sound right and are wrong:

- *"Each element gets its own thread."* No. Chunks get tasks; tasks share a small pool of threads.
- *"`parallel()` makes it faster."* It adds splitting, scheduling and merging. Whether that pays back depends on the source, the work per element, and the machine.
- *"The calling thread just waits."* It runs the first task itself and then helps finish the rest.

## Level 2 — The moving parts, and why laziness matters

Four parts, and one job each:

| Part | Job |
|---|---|
| **Source** | Supplies elements: an array, an `ArrayList`, a range, a generator |
| **Pipeline** | Records the intermediate operations. It is lazy and single-use |
| **Spliterator** | Walks the source and, when it can, cuts it in two |
| **Terminal operation** | Starts the work and defines the result: a reduction, a collection, a search, or a side effect |

```java
long total = orders.parallelStream()
        .filter(Order::isCompleted)
        .mapToLong(Order::amountInCents)
        .sum();
```

Before `sum()` runs, no element has been read and no thread has been touched. `sum()` triggers all of it.

### Laziness has two consequences interviews like

**A pipeline is consumed once.**

```java
Stream<Order> pipeline = orders.stream().filter(Order::isCompleted);
long a = pipeline.count();
long b = pipeline.count();
```

```text
java.lang.IllegalStateException: stream has already been operated upon or closed
```

**The mode belongs to the pipeline, not to the position where you set it.** The last of `parallel()` / `sequential()` wins, and it applies to every stage — including the ones written before it. Both directions are worth seeing:

```java
Set<String> threads = ConcurrentHashMap.newKeySet();

// map() is written before sequential(), yet it runs only on the calling thread:
numbers.stream().parallel()
        .map(v -> { threads.add(Thread.currentThread().getName()); return v; })
        .sequential()
        .forEach(v -> { });
// threads = [main]

// map() is written before parallel(), yet it runs on many threads:
numbers.stream().sequential()
        .map(v -> { threads.add(Thread.currentThread().getName()); return v; })
        .parallel()
        .forEach(v -> { });
// threads = 10 distinct names on one run of 1000 elements
```

That is why `parallel()` is often called a *flag on the pipeline* rather than an operation in it.

## Level 3 — From one source to a tree of chunks

A `Spliterator` is a "splittable iterator": it walks a source **and** can hand away part of it. That second ability is the whole basis of parallel streams.

It has four jobs:

- `trySplit()` — hand back a new spliterator covering part of the remaining elements, or `null` if it cannot or should not split;
- `estimateSize()` — say how many elements are left;
- `tryAdvance()` and `forEachRemaining()` — walk elements;
- **characteristics** — declare facts the implementation is allowed to exploit.

| Characteristic | Why parallel evaluation cares |
|---|---|
| `ORDERED` | Elements have an encounter order that some operations must preserve |
| `SIZED` | The size is exact before traversal, so the split plan can be computed up front |
| `SUBSIZED` | Every child of a split is also `SIZED` and `SUBSIZED` |
| `DISTINCT` / `SORTED` | The source already guarantees uniqueness or order, so a stage can be skipped |
| `IMMUTABLE` / `CONCURRENT` | Says how structural changes during traversal are handled |

### How many chunks does it make?

The implementation picks a **target chunk size**, then keeps splitting while a chunk is bigger than that target.

```text
leafTarget = 4 x parallelism           // deliberately more tasks than threads
targetSize = estimateSize / leafTarget // at least 1
while (chunkSize > targetSize && trySplit() != null) { split again }
```

![concurrency-parallel-stream-leaf-sizing.svg](images/concurrency-parallel-stream-leaf-sizing.svg)

Read the diagram left to right. Parallelism here means the size of the shared fork/join thread pool that will run the tasks — the *common pool*, covered at Level 5. It defaults to `availableProcessors() - 1`, so 12 cores give 11 worker threads — plus the calling thread, which also runs work. The target is four leaves per worker: 44 leaves for 100 000 elements means about 2272 elements each. An `ArrayList` halves cleanly, so splitting continues to the next power of two at or above that target — **64 leaf tasks**.

You can count them. A non-concurrent collector creates one container per leaf, so counting containers counts leaves:

```java
AtomicInteger containers = new AtomicInteger();
Set<String> threads = ConcurrentHashMap.newKeySet();

data.parallelStream().collect(Collector.of(
        () -> { containers.incrementAndGet();
                threads.add(Thread.currentThread().getName());
                return new ArrayList<Integer>(); },
        ArrayList::add,
        (a, b) -> { a.addAll(b); return a; }));
```

```text
availableProcessors    = 12
commonPool parallelism = 11
containers created     = 64      // leaf tasks, every run
distinct threads       = 12      // 11 workers + main, on this run
```

The leaf count is deterministic; the thread count is not. Twelve is the **ceiling** — 11 workers plus the caller — and most runs use fewer, because a worker that never receives a task never creates a container. Over 300 runs on this machine the count ranged from 6 to 12. That is the point of the section: leaves are planned up front, but which threads run them is decided at run time.

**Over-partitioning is deliberate.** One chunk per worker would mean a worker that finishes early has nothing to do, while a worker with a slow chunk holds up the answer. The surplus tasks are what makes rebalancing possible.

### Watch a source split

Splitting quality is not a claim you have to take on trust — call `trySplit()` yourself:

```java
Spliterator<Integer> rest = collection.spliterator();
System.out.println("SIZED=" + rest.hasCharacteristics(Spliterator.SIZED)
                 + " SUBSIZED=" + rest.hasCharacteristics(Spliterator.SUBSIZED));
for (int i = 1; i <= 4; i++) {
    Spliterator<Integer> part = rest.trySplit();
    System.out.println("  first part=" + part.estimateSize()
                     + ", remainder=" + rest.estimateSize());
}
```

For 10 000 elements the two answers could not be more different:

```text
ArrayList  SIZED=true SUBSIZED=true   LinkedList  SIZED=true SUBSIZED=true
  first part=5000, remainder=5000       first part=1024, remainder=8976
  first part=2500, remainder=2500       first part=2048, remainder=6928
  first part=1250, remainder=1250       first part=3072, remainder=3856
  first part= 625, remainder= 625       first part=3856, remainder=   0
```

The `ArrayList` halves: its split is index arithmetic, so it costs nothing and both sides are equal. The `LinkedList` cannot jump to the middle of a chain, so its `trySplit()` **walks the list and copies elements into a fresh array**, in batches that grow 1024, 2048, 3072 … The same batching applies to any iterator-backed spliterator.

Notice that `LinkedList` reports `SIZED` and `SUBSIZED` and still splits badly.

### Good splitting versus bad splitting

![concurrency-parallel-stream-splitting-quality.svg](images/concurrency-parallel-stream-splitting-quality.svg)

A source is a good parallel input when `trySplit()` is **cheap** and its children are **similarly sized**. Arrays, `ArrayList` and numeric ranges qualify.

`Stream.iterate(seed, f)` fails differently. Its spliterator extends `AbstractSpliterator`, which *does* split — `trySplit()` hands out arithmetically growing batches and, by its own comment, produces `O(sqrt(n))` splits allowing `O(sqrt(cores))` potential speedup. So it is **unsized and batch-splittable**, not unsplittable. The problem is that it estimates its size as `Long.MAX_VALUE` and is not `SIZED`, so the target-size plan above has nothing to work with, and the batches are uneven by construction.

**`SIZED` does not promise balanced splitting, and `SUBSIZED` does not promise a cheap one.** Splitting quality is a property of the source's implementation, not of its characteristic bits.

## Level 4 — What runs inside one chunk

A leaf task runs **every stage over its own chunk** — the same code path a sequential stream uses. At run time each stage is a `Sink`, and the sinks are chained.

![concurrency-parallel-stream-sink-chain.svg](images/concurrency-parallel-stream-sink-chain.svg)

Two directions matter, and they are opposite:

- **Construction runs backwards.** The terminal sink is built first, then each earlier stage wraps it. That is why every stage knows its `downstream`.
- **Data runs forwards.** The chunk's spliterator pushes one element into the first sink, and that element travels the whole chain before the next element is read.

Every sink follows one lifecycle: `begin(size)`, then `accept(element)` repeatedly, then `end()`. A short-circuiting pipeline also polls `cancellationRequested()` between elements, which is how a leaf stops early.

### Proof that it is one pass, element by element

Put a `peek()` before and after a stage and watch the order:

```java
List.of("ann", "bob", "cy").stream()
    .peek(n -> System.out.println("filter sees " + n))
    .filter(n -> n.length() == 3)
    .peek(n -> System.out.println("    map sees " + n))
    .map(String::toUpperCase)
    .forEach(n -> System.out.println("        forEach got " + n));
```

```text
filter sees ann
    map sees ann
        forEach got ANN
filter sees bob
    map sees bob
        forEach got BOB
filter sees cy
```

The output **interleaves**. Each element goes all the way through before the next one is read, and `cy` is dropped by `filter` so it is never mapped. This is **operation fusion**: no intermediate list exists between `filter` and `map`.

For the example pipeline, one chunk therefore behaves exactly like this loop:

```java
long localSum = 0;
for (Order order : chunk) {
    if (order.isCompleted()) {
        localSum += order.amountInCents();
    }
}
```

### The stateful operations that end a segment

The one-pass picture holds while every stage is **stateless** — able to judge an element on its own. Some operations cannot be: `sorted()` must see every element before it can emit the first one.

Such an operation ends a **segment**, and is therefore also called a **barrier**. A parallel pipeline is evaluated segment by segment, and each segment's result feeds the next one. Run the same `peek` trick to see the boundary appear:

```java
List.of(3, 1, 2).stream()
    .peek(v -> System.out.println("  A " + v))
    .sorted()
    .map(v -> v * 10)
    .forEach(v -> System.out.println("        B " + v));
```

```text
  A 3
  A 1
  A 2
        B 10
        B 20
        B 30
```

No interleaving any more. Every `A` finishes before the first `B` starts, because `sorted()` had to materialise the whole stream in between. So `filter().sorted().map().collect()` is **two segments**, not one fused pass.

Knowing *how* each barrier is implemented is what separates a vague answer from a good one:

| Operation | What parallel evaluation actually does |
|---|---|
| `sorted()` | Collects everything into an array, then calls `Arrays.parallelSort`. Two passes and full materialisation |
| `distinct()` on an **ordered** stream | Reduces into a `LinkedHashSet` and merges sets with `addAll` — preserving order forces the barrier |
| `distinct()` on an **unordered** stream | Feeds one shared `ConcurrentHashMap`, which parallelises far better |
| `limit()` / `skip()` while `SIZED` and `SUBSIZED` | Cheap: the slice comes straight from source indexes |
| `limit()` / `skip()` on an **ordered** stream that is no longer sized (say, after `filter()`) | Runs a slice task that **buffers leaf output** so the correct prefix can be chosen. This is where ordered `limit()` gets expensive |

That last row is the classic trap, measured at Level 8.

## Level 5 — Who runs the chunks

The public Stream API specifies results and behavioural rules. It never exposes an `Executor`. Underneath, the implementation builds a tree of `CountedCompleter` tasks and, when the terminal operation is called from an ordinary thread, runs that tree on `ForkJoinPool.commonPool()`.

![concurrency-parallel-stream-work-stealing.svg](images/concurrency-parallel-stream-work-stealing.svg)

The splitting loop is the part worth remembering:

```text
while (size > targetSize && trySplit() succeeds) {
    make a left child and a right child
    setPendingCount(1)          // wait for exactly one of them
    fork one child into the queue
    keep computing the other one on this thread
}
run the leaf, then tryComplete()
```

A parent forks only **one** child and keeps the other, so the tree avoids child-by-child joins: the pending count records the dependency, and when the forked side finishes, the parent's `onCompletion()` merges the two results and completes upward. Which side gets forked alternates, which spreads stealable work across the tree.

That reduces blocking but does not abolish it. `join()` on a `CountedCompleter` first tries `helpComplete` — running available tasks to push the computation forward — and parks the thread only when helping cannot finish the work. Helping is the fast path, not a guarantee.

Scheduling is **work stealing**:

- each thread owns a deque and takes its own **newest** task first (LIFO), because that task's data is most likely still in cache;
- a thread with nothing to do picks a random victim and steals from the **far** end of that queue (FIFO), where the oldest — and therefore largest, least-split — task sits;
- one steal moves a lot of work and needs little coordination.

### Three facts that come up in interviews

**1. The caller participates.** `invoke()` runs the root task on the calling thread and then helps complete the tree. Record thread names inside the pipeline and `main` is right there among the workers:

```java
Set<String> threads = ConcurrentHashMap.newKeySet();
data.parallelStream().forEach(v -> threads.add(Thread.currentThread().getName()));
```

```text
[ForkJoinPool.commonPool-worker-1 ... worker-11, main]   // 12 names on this run
```

How many worker names appear varies from run to run, and 12 is the ceiling rather than a constant. What does not vary is that `main` is one of them: across 300 runs on this machine the caller appeared every single time. The caller running work is the reliable fact; the exact head count is not.

**2. The common pool is JVM-wide, and it is a default rather than the only option.** A terminal operation called from an ordinary thread goes to `ForkJoinPool.commonPool()`, and every such pipeline in the process shares it — so one that blocks delays unrelated work. Its parallelism defaults to `availableProcessors() - 1` and can be set with the `java.util.concurrent.ForkJoinPool.common.parallelism` system property.

**3. Submitting inside another pool keeps the work there.** `fork()` pushes into the current thread's own queue when that thread is a `ForkJoinWorkerThread`, and only otherwise reaches for the common pool:

```java
ForkJoinPool pool = new ForkJoinPool(4);
Set<String> names = pool.submit(() ->
        data.parallelStream()
            .map(v -> Thread.currentThread().getName())
            .collect(Collectors.toCollection(TreeSet::new))).get();
```

```text
[ForkJoinPool-1-worker-1, ForkJoinPool-1-worker-2,
 ForkJoinPool-1-worker-3, ForkJoinPool-1-worker-4]
```

Only that pool's four threads appear — and `main` does not, because it is blocked in `get()`.

That third point is a consequence of fork/join mechanics, **not a contract of `Stream`**. If you need strict executor ownership, isolation, quotas or a cancellation policy, use an API that takes an executor explicitly.

## Level 6 — Why the parallel answer equals the sequential answer

Chunk boundaries are chosen at run time, so **the result must not depend on where they fall**.

![concurrency-parallel-stream-reduction-contracts.svg](images/concurrency-parallel-stream-reduction-contracts.svg)

A reduction has to obey its algebraic contract:

- the operation must be **associative**: `(a op b) op c == a op (b op c)`;
- the identity must be **neutral**: `identity op x == x`;
- in three-argument `reduce()`, the combiner must be compatible with the accumulator.

Break one of those rules and the two modes disagree. For the numbers 1 to 8:

| Reduction | Sequential | Parallel | Why |
|---|---|---|---|
| `reduce(0, Integer::sum)` | `36` | `36` | Correct: `+` is associative and `0` is neutral |
| `reduce(5, Integer::sum)` | `41` | `76` | `5` is not the identity. It is injected into every partition: `36 + 8 × 5` |
| `reduce(0, (a, b) -> a - b)` | `-36` | `0` | Subtraction is not associative, and `0 - x` is `-x`, not `x`, so `0` is not its identity either |

Floating-point addition is a subtler case. It is associative in mathematics but not under IEEE 754 rounding, so the two modes can differ in the low bits. Summing `1/1 + 1/2 + ... + 1/100000` with a plain reduction shows it:

```java
IntStream.rangeClosed(1, 100_000).mapToDouble(i -> 1.0 / i).reduce(0.0, Double::sum);
```

```text
sequential 12.090146129863335
parallel   12.090146129863427
```

Neither is "wrong" — but if you compare such a result with `==`, the mode becomes visible.

The reduction matters, though. Swap that `reduce` for `sum()` and **both modes print `12.090146129863427`**, so the difference disappears:

```java
IntStream.rangeClosed(1, 100_000).mapToDouble(i -> 1.0 / i).sum();
```

`DoubleStream.sum()` is not a plain left-to-right addition. Its javadoc says the method may use compensated summation and is therefore *not necessarily equivalent* to `reduce(0, Double::sum)`; `Collectors.summingDouble` compensates as well. That is a stronger warning than it first looks: the agreement is a property of one library method on one input, not a guarantee. The javadoc also states that the output of `sum()` may vary on the same input elements. Never treat a `double` reduction as mode-independent because one formulation happened to agree.

### Why ordinary `collect()` can use mutable containers safely

A non-concurrent collector gives **each leaf its own container**, keeps it confined while accumulating, and merges containers only after local accumulation ends. That is why `Collectors.toList()` needs no synchronisation: several workers never touch one `ArrayList`.

A collector marked `CONCURRENT` does the opposite: one shared container, no merge at all. Count the supplier calls and the difference is stark:

```text
non-concurrent collector : container created 64 times   // one per leaf, then merged
concurrent collector     : container created  1 time    // shared, never merged
```

The implementation takes the concurrent path only when **all three** conditions hold:

1. the stream is parallel;
2. the collector is `CONCURRENT`;
3. the stream is unordered **or** the collector is `UNORDERED`.

You can read those bits off any collector:

```text
Collectors.toList()             -> [IDENTITY_FINISH]
Collectors.toSet()              -> [UNORDERED, IDENTITY_FINISH]
Collectors.groupingBy(...)      -> [IDENTITY_FINISH]
Collectors.groupingByConcurrent -> [CONCURRENT, UNORDERED, IDENTITY_FINISH]
```

So `groupingByConcurrent` always takes the shared-container path in a parallel stream, while `groupingBy` always builds per-leaf maps and merges them. And `UNORDERED` alone is not enough: `toSet()` is `UNORDERED` but not `CONCURRENT`, so it still builds one `HashSet` per leaf.

The merge is not free — `Collectors.toList()` combines with `left.addAll(right)`, so elements are copied at every level of the task tree. Level 8 measures what that costs.

`CONCURRENT` describes how the collector accumulates. It does **not** make arbitrary state touched by your lambdas safe.

### Correctness rules for the lambdas themselves

Behavioural parameters must be **non-interfering** and, in most cases, **stateless**:

- do not modify a non-concurrent source while its pipeline is running;
- do not let the result depend on mutable state that changes during the run;
- do not mutate an unsynchronised shared result from `forEach()`;
- prefer a reduction or a collector that owns its partial results.

Here is what breaking the third rule looks like. Five runs of the same code, adding 100 000 elements to a plain `ArrayList`:

```java
List<Integer> output = new ArrayList<>();
IntStream.range(0, 100_000).boxed().parallel().forEach(output::add); // data race
```

```text
run 1: size = 16406      (expected 100000)
run 2: size = 12748
run 3: size = 12115
run 4: size = 12728
run 5: threw ArrayIndexOutOfBoundsException
```

Both failure modes in one demo: **silently lost elements**, and occasionally an exception. Nothing warns you.

The fix is to let the collector own the partial results:

```java
List<Integer> output = IntStream.range(0, 100_000).boxed().parallel()
        .collect(Collectors.toList()); // correct, every run
```

Wrapping the list in `Collections.synchronizedList` would stop the corruption, but it leaves the order nondeterministic and adds contention. **Thread-safe is not the same as correct, deterministic, or fast.**

## Level 7 — Encounter order and short-circuiting

An ordered source such as a `List` has an **encounter order** — the order its elements are defined to appear in. Parallel scheduling may process later elements first, and an order-sensitive terminal must still meet its contract anyway.

![concurrency-parallel-stream-ordering.svg](images/concurrency-parallel-stream-ordering.svg)

One run over `[1..12]`, all four terminals on the same parallel stream:

| Call | Result | What it costs |
|---|---|---|
| `forEach(print)` | `8 9 7 11 4 12 10 2 5 6 3 1` | Nothing. Action order is unspecified, so no coordination is needed |
| `forEachOrdered(print)` | `1 2 3 … 12` | Upstream stages still run in parallel; only the actions are replayed in encounter order |
| `filter(x % 3 == 0).findFirst()` | `3`, every run | Must respect encounter order, so it cancels tasks that come later |
| `filter(x % 3 == 0).findAny()` | `9` in the diagram's run; `3`, `6`, `9` and `12` all appeared across 200 runs | Nothing. Any match is a legal answer, so no task waits for an earlier chunk |

`forEachOrdered` is often assumed to disable parallelism. It does not. Leaves **may** buffer: a leaf whose left-hand predecessor has not completed yet collects its output into a `Node` first, while a leaf that is already free to complete runs straight into the action. The memory cost is real, but it is paid only where the ordering dependency is still outstanding.

### `unordered()` is a real optimisation

If you genuinely do not care about order, saying so lets `distinct()`, `limit()` and concurrent collectors take their cheaper path. One million values drawn from 50 000 distinct keys:

```text
distinct().count()
  sequential            11 967 us
  parallel, ordered     14 483 us   // slower than sequential
  parallel, unordered    3 818 us   // 3.1x faster than sequential
```

Ordered `distinct()` has to merge `LinkedHashSet`s to preserve order, which costs more than it gains. Adding `.unordered()` switches it to one shared `ConcurrentHashMap` — the same operation, a different contract, a 3.8x difference.

### One more trap: an intermediate side effect is not a per-element hook

```java
int[] seen = {0};                                            // 100 000 elements

big.stream().peek(v -> seen[0]++).count();                   // peek ran 0 times
big.stream().filter(v -> true).peek(v -> seen[0]++).count(); // peek ran 100 000 times
```

In the first line the size was already known, so `count()` returned it without traversing anything — and `peek` never ran. In the second, `filter()` destroyed the exact size, so the pipeline had to be traversed after all. The `count()` javadoc documents exactly this. Never rely on `peek()` for logic.

## Level 8 — When parallel execution actually pays

Parallelism has fixed costs: computing the split plan, allocating tasks, forking, stealing, buffering and merging. The question is whether the real work is big enough to amortise them.

The useful model is **total work ≈ N × Q** — element count times cost per element. Both factors count, and either one can carry the pipeline.

### Where the break-even actually is

Summing an `ArrayList<Integer>` is about the cheapest `Q` there is. Even so:

| Elements | Sequential | Parallel | Result |
|---|---|---|---|
| 100 | 0.8 µs | 2.5 µs | 3.3× **slower** |
| 1 000 | 2.9 µs | 3.5 µs | 1.2× **slower** |
| 10 000 | 29 µs | 9.0 µs | 3.2× faster |
| 100 000 | 293 µs | 61 µs | 4.8× faster |
| 1 000 000 | 2 940 µs | 434 µs | 6.8× faster |

Two lessons. First, the overhead is small and fixed — a few microseconds — so it is repaid somewhere in the low thousands of elements even for trivial work. Second, 12 cores never buy 12×; 7× on a perfect source is a realistic ceiling.

This lines up with the `ForkJoinTask` rule of thumb that a task should do **more than 100 and fewer than 10 000 basic computational steps**. With roughly 64 leaves, a pipeline whose total work is only a few thousand steps gives each leaf less than that useful minimum.

### The source decides how much of that speedup you get

Same cheap sum, same one million elements, different source:

```text
ArrayList    sequential 2 842 us   parallel   407 us   -> 7.0x
LinkedList   sequential 3 249 us   parallel 2 358 us   -> 1.4x
```

`LinkedList` is not "unparallelisable" — it is a source that spends most of the win on copying its elements into batch arrays before any of them can be split. You keep about a fifth of the available speedup.

### The merge decides how much survives

Grouping one million values into 100 000 keys:

```text
groupingBy            sequential 57 428 us
groupingBy            parallel   49 211 us   -> 1.2x, almost nothing
groupingByConcurrent  parallel   18 169 us   -> 3.2x
```

`groupingBy` builds 64 maps and merges them key by key, and with many keys the merge eats the win. `groupingByConcurrent` accumulates into one `ConcurrentHashMap` and skips the merge entirely. This is the concrete reason the concurrent variant exists.

### Ordering pressure can make parallel much slower

The trap from Level 4, measured. Find the first 1000 primes in `[0, 2 000 000)`:

```text
filter(isPrime).limit(1000).count()
  sequential              288 us
  parallel, ordered     2 566 us   // 9x slower
  parallel, unordered   1 071 us
```

The sequential stream stops as soon as it has 1000 matches, near the start of the range. The parallel one splits the *whole* range, does far more speculative work, and buffers leaf output so it can pick the correct ordered prefix. Short-circuiting plus encounter order is where `parallel()` most often backfires.

Note the contrast with `sorted()`, which is a barrier but **not** automatically a loss: parallel `sorted()` on one million elements ran 151 ms sequentially against 27 ms in parallel, because it delegates to `Arrays.parallelSort`. The cost of a barrier is the full materialisation and the extra pass, not the sorted operation itself.

### Putting the factors together

| Better candidate | Poor candidate |
|---|---|
| Large, finite source (roughly 10 000+ cheap elements, far fewer expensive ones) | Small source |
| Array, `ArrayList`, or a balanced range | `LinkedList`, iterator-backed, or unsized `Stream.iterate` |
| CPU-heavy independent work per element | One cheap field read on a short list |
| Stateless stages | Shared mutable state or a contended lock |
| Cheap combination (`sum`, `groupingByConcurrent`) | Expensive merge (`toList`, `groupingBy` on many keys) |
| Little ordering pressure, or `unordered()` | Ordered `limit()` after a `filter()`, ordered `distinct()` |
| Spare CPU capacity | Common pool already busy |

![concurrency-parallel-stream-decision-checklist.svg](images/concurrency-parallel-stream-decision-checklist.svg)

Three closing cautions:

- **Blocking calls are a poor fit.** Fork/join can compensate for *recognised* blocking through `ManagedBlocker`, but it does not guarantee enough workers for arbitrary blocked I/O or unmanaged synchronisation — and every blocked common-pool worker is one the rest of the JVM has lost. For blocking work use an explicit design with bounded resources, timeouts and cancellation, and consider virtual threads.
- **Nested parallel streams do not add processors.** They add tasks and coordination to the pool already in use, which usually increases contention rather than throughput.
- **Measure.** Compare `.stream()` and `.parallelStream()` on representative data and hardware, with warm-up and realistic surrounding load. Do not infer performance from core count.

## Putting it together

This Java 8-compatible example uses stateless functions and library reductions, and shows the two grouping paths side by side:

```java
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentMap;
import java.util.stream.Collectors;

public final class ParallelStreamExample {
    private ParallelStreamExample() {
    }

    /** Cheap combine: primitive partial sums are merged up the task tree. */
    static long completedTotal(List<Order> orders) {
        return orders.parallelStream()
                .filter(Order::isCompleted)
                .mapToLong(Order::amountInCents)
                .sum();
    }

    /** One map per leaf, then a merge. Fine for few keys. */
    static Map<String, Long> totalsByRegion(List<Order> orders) {
        return orders.parallelStream()
                .filter(Order::isCompleted)
                .collect(Collectors.groupingBy(
                        Order::region,
                        Collectors.summingLong(Order::amountInCents)));
    }

    /** One shared map, no merge. Worth it when there are many keys. */
    static ConcurrentMap<String, Long> totalsByRegionConcurrent(List<Order> orders) {
        return orders.parallelStream()
                .filter(Order::isCompleted)
                .collect(Collectors.groupingByConcurrent(
                        Order::region,
                        Collectors.summingLong(Order::amountInCents)));
    }

    static final class Order {
        private final String region;
        private final long amountInCents;
        private final boolean completed;

        Order(String region, long amountInCents, boolean completed) {
            this.region = region;
            this.amountInCents = amountInCents;
            this.completed = completed;
        }

        String region() {
            return region;
        }

        long amountInCents() {
            return amountInCents;
        }

        boolean isCompleted() {
            return completed;
        }
    }
}
```

Every lambda here is stateless, no shared mutable state is touched, and each combine is associative — which is exactly what makes swapping `stream()` for `parallelStream()` safe.

The two grouping methods are **not** drop-in replacements for each other, though. `groupingBy` fills one map per leaf and merges them, which happens to preserve encounter order inside every group; `groupingByConcurrent` shares one map, so it does not:

```java
IntStream.range(0, 40).boxed().parallel()
         .collect(Collectors.groupingBy(v -> v % 4)).get(0);
// [0, 4, 8, 12, 16, 20, 24, 28, 32, 36]  — same on every run

IntStream.range(0, 40).boxed().parallel()
         .collect(Collectors.groupingByConcurrent(v -> v % 4)).get(0);
// [12, 28, 20, 24, 0, 16, 8, 32, 36, 4]  — different on every run
```

Here the downstream is `summingLong`, which does not care about order, so the swap is safe. With an order-sensitive downstream such as `toList()` it is a behaviour change, not an optimisation.

## Interview drill

| Question | Short answer |
|---|---|
| How many threads does a parallel stream use? | Common pool parallelism, `availableProcessors() - 1` by default, plus the calling thread, which also runs work |
| How many tasks? | Roughly four leaves per worker; the tree splits while a chunk exceeds `estimateSize / (4 × parallelism)` |
| Where does `filter` run relative to `map`? | In the same pass over the same element, inside one leaf — stages in a segment are fused, not run as separate phases |
| Is the whole pipeline always one fused pass? | Only while every stage is stateless. Each stateful operation ends a segment, and a parallel pipeline with one is evaluated segment by segment |
| How do you *show* fusion in an interview? | Put a `peek()` before and after a stage: stateless output interleaves per element, `sorted()` batches it |
| Why is `Collectors.toList()` safe without synchronisation? | Each leaf accumulates into its own container; containers merge only after local accumulation ends |
| When does a collector write into one shared container? | Parallel stream **and** `CONCURRENT` collector **and** (unordered stream **or** `UNORDERED` collector) |
| `findFirst()` versus `findAny()`? | `findFirst()` must respect encounter order and cancels later tasks; `findAny()` may return any match and needs no ordering coordination |
| Does `forEachOrdered` disable parallelism? | No. Upstream stages still run in parallel; only the actions are replayed in encounter order, and a leaf buffers only while an earlier leaf is outstanding |
| Why is `LinkedList` a weak parallel source? | `trySplit()` copies elements into growing batch arrays (1024, 2048, 3072 …) instead of halving, so you keep only a fraction of the speedup |
| Does a big `N` alone justify `parallel()`? | It usually does once total work `N × Q` is large enough — measured break-even was a few thousand elements even for a trivial sum — but the source and the merge decide how much you keep |
| What is the worst realistic case? | Short-circuiting under encounter order: `filter().limit(n)` on an ordered stream was 9× slower in parallel |
| Can you choose the pool? | Calls from an ordinary thread use the common pool; inside a fork/join computation subtasks stay in the current pool, so `customPool.submit(...)` works in practice — but pool selection is not part of the `Stream` contract |
| Why did my `peek()` not run? | A terminal such as `count()` may compute the answer from the source size and skip traversal entirely |
| Is `groupingByConcurrent` a free swap for `groupingBy`? | Only when the downstream ignores order. `groupingBy` merges per-leaf maps and keeps encounter order inside each group; the concurrent one shares a map and does not |

## API guarantee versus implementation detail

| Safe to rely on | Do not treat as a permanent promise |
|---|---|
| Parallel or sequential mode, and terminal-operation semantics | Exact task classes or the split threshold |
| Non-interference and statelessness requirements | Four leaves per worker, or 64 leaves on 12 cores |
| Associativity and identity requirements | A fixed worker count |
| Encounter-order contracts | The caller always doing a particular amount of work |
| Collector characteristics and the concurrent-reduction conditions | Selecting a custom pool by invoking the stream inside it |
| That a stateful operation ends a segment | How any specific barrier is implemented today |

## One-sentence mental model

> A parallel stream is one lazy pipeline run over many `Spliterator` chunks, scheduled by fork/join, with the terminal operation deciding how the partial results become the single answer you see.

## Sources

- [Java SE 26 `java.util.stream` package specification](https://docs.oracle.com/en/java/javase/26/docs/api/java.base/java/util/stream/package-summary.html)

  Defines laziness, parallel mode, stateless and stateful operations, non-interference, reduction, side effects, and the ordering section quoted for `unordered()` and buffering.

- [Java SE 26 `Stream` API](https://docs.oracle.com/en/java/javase/26/docs/api/java.base/java/util/stream/Stream.html)

  Specifies reduction contracts, `forEach` and `forEachOrdered`, short-circuiting, and the `count()` note that a pipeline may not be traversed at all.

- [Java SE 26 `Spliterator` API](https://docs.oracle.com/en/java/javase/26/docs/api/java.base/java/util/Spliterator.html)

  Defines `trySplit()`, size estimates, characteristics, thread confinement, and the effect of balanced splitting.

- [Java SE 26 `Collector` API](https://docs.oracle.com/en/java/javase/26/docs/api/java.base/java/util/stream/Collector.html)

  Defines isolated partial containers, the associativity and identity constraints, and the `CONCURRENT`, `UNORDERED` and `IDENTITY_FINISH` characteristics.

- [Java SE 26 `Collectors` API](https://docs.oracle.com/en/java/javase/26/docs/api/java.base/java/util/stream/Collectors.html)

  Documents which factory methods produce concurrent collectors, including `groupingByConcurrent`.

- [Java SE 26 `ForkJoinPool` API](https://docs.oracle.com/en/java/javase/26/docs/api/java.base/java/util/concurrent/ForkJoinPool.html)

  Documents work stealing, the common pool, its parallelism system property, and the limits around blocked I/O and unmanaged synchronisation.

- [Java SE 26 `ForkJoinTask` API](https://docs.oracle.com/en/java/javase/26/docs/api/java.base/java/util/concurrent/ForkJoinTask.html)

  Gives the task-granularity rule of thumb of more than 100 and fewer than 10 000 basic computational steps.

- [OpenJDK `AbstractTask` source (jdk-26-ga)](https://github.com/openjdk/jdk/blob/jdk-26-ga/src/java.base/share/classes/java/util/stream/AbstractTask.java)

  Shows `LEAF_TARGET`, `suggestTargetSize`, the `compute()` splitting loop, the alternating fork, and `setPendingCount(1)`.

- [OpenJDK `Sink` source (jdk-26-ga)](https://github.com/openjdk/jdk/blob/jdk-26-ga/src/java.base/share/classes/java/util/stream/Sink.java)

  Documents the `begin`, `accept`, `end` and `cancellationRequested` protocol and the chained downstream design.

- [OpenJDK `AbstractPipeline` source (jdk-26-ga)](https://github.com/openjdk/jdk/blob/jdk-26-ga/src/java.base/share/classes/java/util/stream/AbstractPipeline.java)

  Shows `wrapSink()` building the chain backwards, `copyInto` versus `copyIntoWithCancel`, the sequential or parallel terminal dispatch, and the implementation note that a parallel pipeline with stateful operations is evaluated in segments rather than one jammed pass.

- [OpenJDK `ReduceOps` source (jdk-26-ga)](https://github.com/openjdk/jdk/blob/jdk-26-ga/src/java.base/share/classes/java/util/stream/ReduceOps.java)

  Shows leaf accumulation and the `onCompletion()` combination for parallel reductions.

- [OpenJDK `ForEachOps` source (jdk-26-ga)](https://github.com/openjdk/jdk/blob/jdk-26-ga/src/java.base/share/classes/java/util/stream/ForEachOps.java)

  Shows `ForEachOrderedTask` and its `if (task.getPendingCount() > 0)` guard: a leaf buffers into a `Node` only when an ordering dependency is still outstanding, and otherwise copies straight into the action.

- [OpenJDK `SortedOps` source (jdk-26-ga)](https://github.com/openjdk/jdk/blob/jdk-26-ga/src/java.base/share/classes/java/util/stream/SortedOps.java)

  Shows that parallel `sorted()` flattens the stream into an array and then calls `Arrays.parallelSort`.

- [OpenJDK `DistinctOps` source (jdk-26-ga)](https://github.com/openjdk/jdk/blob/jdk-26-ga/src/java.base/share/classes/java/util/stream/DistinctOps.java)

  Shows the ordered `LinkedHashSet` reduction and the unordered `ConcurrentHashMap` path.

- [OpenJDK `SliceOps` source (jdk-26-ga)](https://github.com/openjdk/jdk/blob/jdk-26-ga/src/java.base/share/classes/java/util/stream/SliceOps.java)

  Shows the cheap sized-and-subsized slice, the unordered slice, and the buffering `SliceTask` used for an ordered, no-longer-sized `limit()`.

- [OpenJDK `Spliterators` source (jdk-26-ga)](https://github.com/openjdk/jdk/blob/jdk-26-ga/src/java.base/share/classes/java/util/Spliterators.java)

  Shows `AbstractSpliterator.trySplit()` and `IteratorSpliterator.trySplit()`: arithmetically growing array batches, `O(sqrt(n))` splits, and the `BATCH_UNIT` of 1024.

- [OpenJDK `ForkJoinTask` source (jdk-26-ga)](https://github.com/openjdk/jdk/blob/jdk-26-ga/src/java.base/share/classes/java/util/concurrent/ForkJoinTask.java)

  Shows that `fork()` pushes to the current thread's own queue when it is a `ForkJoinWorkerThread` and only otherwise reaches for the common pool; that `invoke()` is `doExec()` followed by `join()`; and that `join()` on a `CountedCompleter` tries `helpComplete` first and falls through to a `LockSupport.park()` wait when helping does not finish the task.

- [OpenJDK `ForkJoinPool` source (jdk-26-ga)](https://github.com/openjdk/jdk/blob/jdk-26-ga/src/java.base/share/classes/java/util/concurrent/ForkJoinPool.java)

  Documents the LIFO own-queue and randomised FIFO steal preference, and the `availableProcessors() - 1` default for the common pool.

- [JSR 335 final specification page](https://www.jcp.org/en/jsr/detail?id=335)

  Records the Java 8-era language and library work that introduced lambdas and the Stream API.
