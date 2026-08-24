# Concurrency. Obstruction-Free vs. Lock-Free vs. Wait-Free

## Front

How do **obstruction-free**, **lock-free**, and **wait-free** algorithms differ, and what do these progress guarantees mean for Java code?

## Back

**Obstruction-free, lock-free, and wait-free are progress guarantees: they state whose operation must finish when concurrent threads interfere.**

**Strength order—read from left to right:**

```text
weakest                                      strongest
obstruction-free  →  lock-free  →  wait-free
```

**Logical implication—stronger guarantees include the weaker ones:**

```text
wait-free ⇒ lock-free ⇒ obstruction-free
```

Here, `A ⇒ B` means every algorithm satisfying guarantee A also satisfies guarantee B. Thus every wait-free algorithm is lock-free, but a lock-free algorithm is not necessarily wait-free. The first diagram shows why the guarantees are nested; the rest of the card explains how to recognize each one.

![Nested hierarchy of obstruction-free, lock-free, and wait-free progress guarantees](svg/concurrency-progress-guarantees-hierarchy.svg)

### The comparison in one table

| Guarantee | Who must complete? | Required condition | Can one active thread starve? |
|---|---|---|---:|
| **Obstruction-free** | The operation that gets enough time without interference | It eventually runs in isolation long enough | Yes |
| **Lock-free** | Some operation in the system | Threads keep taking steps | Yes |
| **Wait-free** | Every active operation | The operation keeps taking its own steps | No, within the algorithm's model |

The essential question is not “does the code use a lock?” It is **what completion does the complete algorithm guarantee?**

### Vocabulary first

- An **operation** is one call such as `increment()`, `offer()`, or `poll()`.
- An **active operation** has started but has not yet returned.
- A thread takes an **own step** when it executes one step of that operation. Progress bounds concern these steps, not wall-clock time.
- **Interference** means another thread changes shared state in a way that invalidates the current attempt.
- **Starvation** means one operation can be postponed forever even while other operations finish.

## Obstruction-free: “I finish if interference stops”

An operation is **obstruction-free** if it completes after running alone for sufficiently many of its own steps.

“Alone” does not mean every other thread has terminated. It means other threads stop taking conflicting steps long enough for this operation to finish.

```text
T1 tries → T2 interferes → T1 restarts
T2 tries → T1 interferes → T2 restarts

No isolation window → no completion is required
T2 stops interfering → T1 runs alone → T1 must complete
```

Under continuous contention, all operations may repeatedly restart. A contention manager, randomized delay, or backoff may make this unlikely in practice, but it does **not** strengthen the underlying guarantee unless the complete mechanism proves stronger progress.

Conceptual shape—not a complete implementation:

```java
for (;;) {
    Snapshot before = readConsistentState();
    Update after = calculateUpdate(before);

    if (validateAndCommit(before, after)) {
        return;
    }

    // Interference invalidated this attempt.
}
```

The loop's shape alone proves nothing. The guarantees of `readConsistentState()`, `validateAndCommit()`, conflict handling, and memory reclamation all matter.

## Lock-free: “the system keeps finishing operations”

An algorithm is **lock-free** when continued execution guarantees that **some** operation completes in a finite number of system-wide steps.

It promises **global progress**, not fairness:

```text
T1 loses → T2 succeeds
T1 loses → T3 succeeds
T1 loses → T2 succeeds

The system progresses, but T1 may starve.
```

A paused thread cannot indefinitely prevent every other thread from completing merely because it paused during its operation. That is the important difference from a thread that pauses while holding an exclusive lock needed by everybody else.

### Typical compare-and-set retry loop

`compareAndSet(expected, update)`—usually abbreviated **CAS**—atomically changes a value only if it still equals the expected value.

```java
import java.util.concurrent.atomic.AtomicInteger;

final class LockFreeCounter {
    private final AtomicInteger value = new AtomicInteger();

    int increment() {
        for (;;) {
            int current = value.get();
            int next = current + 1;

            if (value.compareAndSet(current, next)) {
                return next;
            }

            Thread.onSpinWait();
        }
    }
}
```

For this counter:

- a successful CAS completes the current operation;
- a failed strong CAS means the expected value no longer matched, so another update changed the counter;
- repeated failures can therefore accompany system-wide progress;
- one unlucky caller can still lose every race, so the loop is **not wait-free**.

`Thread.onSpinWait()` is only a runtime hint for a busy-wait loop. Removing it does not change correctness, and adding it does not strengthen the progress guarantee.

## Wait-free: “every active operation has its own bound”

An algorithm is **wait-free** when every active operation completes after a finite, bounded number of its own steps, regardless of other threads' relative speeds or failures.

This is **per-operation progress**. An aggressive competitor cannot force one active operation to retry forever.

The bound may depend on a stated property, such as the number of participants, the structure's capacity, or the chosen operation. It must not depend on another thread eventually being scheduled and voluntarily completing some future action.

Many wait-free designs use **helping**:

```text
1. A thread publishes a description of its pending operation.
2. Threads find pending descriptions in a controlled order.
3. A thread may finish another thread's operation before its own.
4. A bounded helping rule prevents an active request from being ignored forever.
```

Helping can turn system-wide progress into per-operation progress, but it adds state, work, and a substantially harder correctness proof.

### Compare the executions

Read each row from left to right. Red blocks are failed attempts; green blocks are completed operations.

![Execution timelines showing who completes under each progress guarantee](svg/concurrency-progress-guarantees-timeline.svg)

- **Obstruction-free:** completion appears only after T1 gets an isolation window.
- **Lock-free:** T2 and T3 complete while T1 may retry forever.
- **Wait-free:** every active operation finishes within its own algorithmic bound.

## Why the hierarchy holds

### Wait-free implies lock-free

If every active operation completes, then at least one operation completes. Per-operation progress necessarily gives system-wide progress.

### Lock-free implies obstruction-free

If only one active operation keeps taking steps, any lock-free system progress must come from that operation. It therefore completes while running without interference.

### The reverse directions fail

- **Obstruction-free does not imply lock-free:** two threads can continually invalidate each other, so neither finishes.
- **Lock-free does not imply wait-free:** the system can complete infinitely many operations while one caller loses every race.

## Progress is not correctness

The three terms describe **liveness**: whether operations finish. They do not by themselves prove **safety**: whether the results are correct.

A usable concurrent algorithm may also need:

- atomic updates and correct memory ordering;
- **linearizability**, so each completed operation appears to take effect at one instant between its call and return;
- preservation of data-structure invariants;
- protection from the ABA problem where relevant;
- safe reclamation of removed nodes.

An algorithm may be linearizable and still be blocking, obstruction-free, lock-free, or wait-free.

## Blocking contrast

```java
final class LockedCounter {
    private int value;

    synchronized int increment() {
        return ++value;
    }
}
```

This code can be perfectly correct, but it is blocking. If a thread is suspended while owning the monitor, another caller needing that monitor cannot finish until the owner runs again and releases it.

That does not make locks bad. Locks are often simpler to design and verify, and they may perform better for a real workload. A progress guarantee is not a speed ranking.

## How to interpret Java APIs

The `java.util.concurrent.atomic` package supplies atomic operations intended to support lock-free programming on single variables. `ConcurrentLinkedQueue` is documented as using a non-blocking algorithm based on the Michael–Scott queue.

Still, do not label arbitrary Java code lock-free merely because it contains `AtomicInteger`, `VarHandle`, or CAS. The claim belongs to a **specific operation of a complete algorithm under stated assumptions**. An unrelated blocking call, an unsafe reclamation scheme, or a retry condition that does not imply competing progress can invalidate the claim.

Likewise, do not call an operation wait-free solely because one atomic instruction appears to be constant-time. The Java API may not promise a formal per-operation progress bound for the entire path.

## Common traps

| Claim | Correct interpretation |
|---|---|
| “Lock-free means every thread progresses.” | No. Some operation progresses; one caller may starve. |
| “Wait-free means a wall-clock deadline.” | No. It bounds algorithmic steps, not scheduling pauses, JVM safepoints, page faults, or hardware delays. |
| “Every CAS loop is lock-free.” | No. Failures must imply system progress, and the entire operation must preserve the guarantee. |
| “No `synchronized` means non-blocking.” | No. A spin loop can avoid locks and still have no progress guarantee. |
| “A fixed retry limit makes the update wait-free.” | Only if returning failure is part of the operation's contract; otherwise the requested update did not complete. |
| “Wait-free is always fastest.” | No. Helping and bookkeeping can cost more than retries or locking. |

## Memory aid

```text
Obstruction-free:  I finish after interference stops.
Lock-free:         The system keeps finishing operations.
Wait-free:         Every active operation finishes within its bound.

Strength order (weakest to strongest):
obstruction-free → lock-free → wait-free

Logical implication (strongest includes weaker guarantees):
wait-free ⇒ lock-free ⇒ obstruction-free
```

## Sources

- [Maurice Herlihy, Victor Luchangco, and Mark Moir — “Obstruction-Free Synchronization: Double-Ended Queues as an Example”](https://cs.brown.edu/people/mph/HerlihyLM03/main.pdf)

  *Proceedings of the 23rd International Conference on Distributed Computing Systems (ICDCS)*, IEEE Computer Society, 2003, pp. 522–529. [DOI: 10.1109/ICDCS.2003.1203503](https://doi.org/10.1109/ICDCS.2003.1203503). Supports the obstruction-free definition, the progress hierarchy, contention management, and helping discussion.

- [Maurice Herlihy — “Wait-Free Synchronization”](https://cs.brown.edu/people/mph/Herlihy91/p124-herlihy.pdf)

  *ACM Transactions on Programming Languages and Systems*, vol. 13, no. 1, January 1991, pp. 124–149. [DOI: 10.1145/114005.102808](https://doi.org/10.1145/114005.102808). Supports the wait-free definition, own-step reasoning, and safety-versus-liveness distinction.

- [Maged M. Michael and Michael L. Scott — “Simple, Fast, and Practical Non-Blocking and Blocking Concurrent Queue Algorithms”](https://www.cs.rochester.edu/~scott/papers/1996_PODC_queues.pdf)

  *Proceedings of the 15th Annual ACM Symposium on Principles of Distributed Computing (PODC ’96)*, ACM, 1996, pp. 267–275. [DOI: 10.1145/248052.248106](https://doi.org/10.1145/248052.248106). Supports the lock-free global-progress definition, bounded wait-free progress, and the Michael–Scott queue reference.

- [Oracle — Java SE 26 `java.util.concurrent` package summary](https://docs.oracle.com/en/java/javase/26/docs/api/java.base/java/util/concurrent/package-summary.html)

  *Java Platform, Standard Edition and Java Development Kit, Version 26 API Specification*. Supports Java’s distinction between non-blocking queues, blocking queues, and atomic utilities.

- [Oracle — Java SE 26 `ConcurrentLinkedQueue`](https://docs.oracle.com/en/java/javase/26/docs/api/java.base/java/util/concurrent/ConcurrentLinkedQueue.html)

  *Java Platform, Standard Edition and Java Development Kit, Version 26 API Specification*. Supports the statement that this queue uses a non-blocking algorithm based on the Michael–Scott queue.

- [Oracle — Java SE 26 `Thread.onSpinWait()`](https://docs.oracle.com/en/java/javase/26/docs/api/java.base/java/lang/Thread.html#onSpinWait())

  *Java Platform, Standard Edition and Java Development Kit, Version 26 API Specification*. Supports the statement that `onSpinWait()` is an optional runtime hint and is not required for correctness.
