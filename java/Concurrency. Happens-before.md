# Happens-Before in Java

## Front

What does **happens-before** mean in the Java Memory Model, which operations create happens-before relationships, and why are they necessary for correct concurrent code?

## Back

The **happens-before** relation defines when the effects of one action are guaranteed to be visible to another action.

If action **A happens-before B**:

- Memory effects produced by A are visible to B.
- A is ordered before B from the program's observable perspective.
- The compiler, JVM, and CPU may still optimize or physically reorder instructions, but they must preserve behavior allowed by this relationship.

Happens-before is a **partial order**, not a global timeline. Two actions may be unrelated by happens-before and therefore be concurrent or involved in a data race.

### How a happens-before chain is formed

Happens-before is built from three rules:

1. **Program order** — actions earlier in one thread happen-before actions later in that same thread.
2. **Synchronizes-with edges** — certain synchronization actions connect different threads.
3. **Transitivity** — if A happens-before B and B happens-before C, then A happens-before C.

```text
A --program order--> B --synchronizes-with--> C --program order--> D

Therefore: A happens-before D
```

Transitivity is what allows a synchronization operation to publish ordinary, non-volatile data written before it.

### Broken publication: no happens-before edge

```java
final class Example {
    private int data;
    private boolean ready;

    void writer() {
        data = 42;
        ready = true;
    }

    void reader() {
        if (ready) {
            System.out.println(data);
        }
    }
}
```

If `writer()` and `reader()` run in different threads, there is no inter-thread happens-before edge.

The Java Memory Model does not guarantee that the reader will observe either write correctly. It may observe:

- `ready == false` after the writer assigned `true`.
- `ready == true` but still observe an old value of `data`.
- Other behavior allowed by compiler, JVM, or CPU reorderings.

Merely executing one thread first in wall-clock time does not establish happens-before.

### Volatile publication

```java
final class Example {
    private int data;
    private volatile boolean ready;

    void writer() {
        data = 42;       // 1
        ready = true;    // 2: volatile write
    }

    void reader() {
        while (!ready) { // 3: volatile read
            Thread.onSpinWait();
        }

        System.out.println(data); // 4: guaranteed to see 42
    }
}
```

The complete chain is:

```text
write data = 42
    happens-before        by program order
volatile write ready = true
    happens-before        volatile write → subsequent read
volatile read ready == true
    happens-before        by program order
read data
```

Therefore the ordinary write `data = 42` is visible to the reader after it observes `ready == true`.

`volatile` provides visibility and ordering, but it does not provide mutual exclusion or make compound operations atomic:

```java
volatile int count;

count++; // read + modify + write; not atomic
```

### Monitor locking with `synchronized`

An unlock of a monitor happens-before every subsequent lock of the **same monitor**.

```java
private final Object lock = new Object();
private int data;

void writer() {
    synchronized (lock) {
        data = 42;
    } // unlock: release
}

void reader() {
    synchronized (lock) { // lock: acquire
        System.out.println(data);
    }
}
```

Everything performed by the writer before releasing `lock` becomes visible to a reader after it acquires that same `lock`.

Synchronizing on different objects does not create this relationship. Synchronizing only the writer or only the reader is also insufficient.

### Core Java happens-before rules

| Action A | Happens-before action B |
|---|---|
| An action in a thread | Every later action in that thread's program order |
| Unlocking monitor `m` | A subsequent lock of the same monitor `m` |
| Writing volatile field `v` | A subsequent read of the same volatile field `v` |
| Calling `thread.start()` | Every action performed by the started thread |
| Every action in thread `T` | Another thread successfully returning from `T.join()` or otherwise detecting its termination |
| Calling `T.interrupt()` | Another thread detecting that `T` was interrupted |
| Default initialization to `0`, `false`, or `null` | The first actions of every thread |

The source of a synchronization edge is often called a **release**, and its destination is called an **acquire**.

### `Thread.start()` publication

Actions before `start()` are visible to the new thread:

```java
int[] holder = {0};
holder[0] = 42;

Thread thread = new Thread(() ->
        System.out.println(holder[0]));

thread.start(); // the new thread is guaranteed to see 42
```

The edge goes from the call to `start()` into the started thread. It does not provide a reverse edge from the worker back to the caller.

### `Thread.join()` publication

All actions performed by a thread happen-before another thread successfully returns from `join()` on it:

```java
int[] result = {0};

Thread worker = new Thread(() -> result[0] = 42);
worker.start();
worker.join();

System.out.println(result[0]); // guaranteed to see 42
```

Without `join()` or another synchronization mechanism, merely observing that enough time has passed provides no visibility guarantee.

### Higher-level `java.util.concurrent` rules

The concurrency library extends happens-before to higher-level operations:

| Before | After |
|---|---|
| Actions before submitting a `Runnable` or `Callable` | The task begins execution in an `Executor` |
| Actions in an asynchronous computation | Another thread successfully returns from `Future.get()` |
| Placing an element in a concurrent collection | Another thread accesses or removes that element |
| `Lock.unlock()` | A successful later `Lock.lock()` on the same lock |
| `Semaphore.release()` | A successful later `Semaphore.acquire()` on the same semaphore |
| `CountDownLatch.countDown()` | A successful return from `await()` on that latch |
| Actions before exchanging an object | Actions after the matching `Exchanger.exchange()` in the other thread |
| Actions before a barrier arrival | Actions after successful passage through the corresponding barrier phase |

### Executor and `Future` example

```java
int[] state = {0};
state[0] = 42;

Future<Integer> future = executor.submit(() -> state[0]);

int result = future.get(); // guaranteed to be 42
```

There are two useful edges:

1. Actions before `submit()` happen-before execution of the submitted task.
2. Actions in the task happen-before actions after a successful `Future.get()`.

### `CountDownLatch` example

```java
int[] result = {0};
CountDownLatch finished = new CountDownLatch(1);

executor.execute(() -> {
    result[0] = 42;
    finished.countDown();
});

finished.await();
System.out.println(result[0]); // guaranteed to see 42
```

The write to `result` occurs before `countDown()`. A successful return from `await()` acquires the effects released by `countDown()`.

### Operations that do not create happens-before

The following do not publish ordinary shared data by themselves:

- `Thread.sleep()`.
- `Thread.yield()`.
- Waiting for an arbitrary amount of wall-clock time.
- Logging or printing.
- Reading and writing an ordinary non-volatile flag.
- Locking a different monitor or `Lock` object.
- Calling `notify()` without accounting for the monitor unlock and reacquisition.

`Object.wait()` releases the object's monitor while waiting and reacquires it before returning. Visibility comes from the monitor unlock/lock relationship, not from elapsed time or notification alone. Conditions must still be tested in a loop because wakeups may be spurious.

### Happens-before and data races

Two accesses conflict when they access the same variable and at least one is a write.

```text
conflicting accesses + no happens-before ordering = data race
```

A program whose sequentially consistent executions contain no data races is **correctly synchronized**. The Java Memory Model guarantees that executions of correctly synchronized programs appear sequentially consistent.

This is often called the **data-race-free guarantee**:

```text
DRF → sequentially consistent behavior
```

This does not mean that every group of thread-safe operations is collectively atomic. Higher-level race conditions, such as check-then-act, can still exist.

### Happens-before is not the same as atomicity

```java
if (!map.containsKey(key)) {
    map.put(key, value);
}
```

Even with a thread-safe map, another thread can act between these two calls. Individual visibility guarantees do not make the compound operation atomic. Use an atomic operation such as `putIfAbsent()` or `computeIfAbsent()` when appropriate.

### Safe publication patterns

An object can be safely published through:

- A volatile reference.
- A correctly locked field.
- Static initialization.
- A concurrent collection.
- An executor submission.
- A completed `Future` followed by `get()`.
- Another documented release/acquire mechanism.

The object's construction must finish before publication. Do not allow `this` to escape from its constructor. Java also gives `final` fields special initialization guarantees, but those rules are separate from the ordinary happens-before rules and do not make later mutation safe.

### Important nuances

- Happens-before is a guarantee about **observable behavior**, not a demand that hardware execute instructions literally in that order.
- It provides visibility only along a complete chain reaching the reading thread.
- A volatile edge requires the same volatile variable.
- A monitor edge requires the same monitor.
- A lock or synchronizer edge requires the corresponding successful acquire operation.
- If later writes intervene, happens-before does not mean a read must return one particular historical value.
- Synchronization must protect or publish all state that participates in the invariant.

### Key idea

> To make a write in Thread A reliably visible to Thread B, construct a complete happens-before path from the write to the read using program order, a release/acquire synchronization edge, and transitivity.

### Official references

- [Java Language Specification §17.4.5: Happens-before Order](https://docs.oracle.com/javase/specs/jls/se26/html/jls-17.html#jls-17.4.5)
- [`java.util.concurrent`: Memory Consistency Properties](https://docs.oracle.com/en/java/javase/26/docs/api/java.base/java/util/concurrent/package-summary.html#MemoryVisibility)
