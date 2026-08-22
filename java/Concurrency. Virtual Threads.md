# Concurrency. Virtual Threads

## Front

What are virtual threads in modern Java, how do they work, and when should they be used?

## Back

**Virtual threads became a final feature in JDK 21** with JEP 444. They were previews in JDK 19 and JDK 20.

A virtual thread is a lightweight `java.lang.Thread` managed primarily by the JVM instead of being permanently mapped to one operating-system thread.

Virtual threads make the familiar **thread-per-task** programming style scalable for applications with many blocking tasks.

## Platform thread vs. Virtual thread

### Platform thread

```text
Java platform thread ─── OS thread
```

A platform thread normally occupies its OS thread for its entire lifetime. OS threads are relatively expensive, so applications usually keep a limited number in pools.

### Virtual thread

```text
Virtual thread A ─┐
Virtual thread B ─┼── JVM scheduler ── small set of carrier platform threads
Virtual thread C ─┘
```

Many virtual threads share a smaller number of platform threads. A platform thread currently executing a virtual thread is called its **carrier thread**.

## What exactly is a carrier thread?

A carrier thread is an ordinary JVM platform thread, backed by an operating-system thread, that temporarily provides CPU execution for a virtual thread.

```text
Virtual thread = task, stack, local variables, and Thread identity
Carrier thread = temporary platform thread on which that task executes
```

The carrier does not own the virtual thread and is not its parent. It is only the temporary execution vehicle selected by the JVM scheduler.

```text
Time 1: carrier-1 executes virtual-thread-A
Time 2: virtual-thread-A blocks and unmounts
Time 3: carrier-1 executes virtual-thread-B
Time 4: virtual-thread-A resumes on carrier-2
```

There is **no permanent one-to-one relationship** between them:

- One carrier executes only one virtual thread at a particular instant.
- The same carrier executes many virtual threads over time.
- A virtual thread can use different carriers during its lifetime.
- Far fewer carrier threads than virtual threads are normally required.

The carrier is intentionally hidden from application code:

```java
Thread thread = Thread.currentThread();

// This is the virtual thread, not its current carrier.
System.out.println(thread.isVirtual()); // true
```

The two threads also keep separate identities and state:

- Their stack traces are separate.
- Their `ThreadLocal` values are separate.
- An exception in a virtual thread does not include the carrier's stack frames.
- Moving to another carrier does not change the virtual thread's identity or local state.

Carrier threads are implementation resources managed by the JVM. Application code should create and manage **virtual threads as tasks**, rather than trying to select or interact with their carriers directly.

## Mounting and unmounting

To run code, the JVM **mounts** a virtual thread on a carrier:

```text
virtual thread → mounted on carrier → executes Java code
```

When the virtual thread performs a supported blocking operation, such as socket I/O or `BlockingQueue.take()`, the JVM can:

1. Suspend the virtual thread.
2. Save its execution state.
3. Unmount it from the carrier.
4. Use the free carrier to run another virtual thread.
5. Remount the original virtual thread when its operation can continue.

```text
VT-A runs → VT-A blocks → carrier runs VT-B → VT-A becomes ready → VT-A resumes
```

The virtual thread may resume on a different carrier. Application code still sees the same virtual `Thread`:

```java
Thread current = Thread.currentThread();
System.out.println(current.isVirtual()); // true
```

The virtual thread's stack is stored in resizable chunks in the Java heap, so it does not reserve a large fixed native stack like a platform thread normally does.

## Creating virtual threads

Start one virtual thread directly:

```java
Thread thread = Thread.startVirtualThread(() -> {
    System.out.println("Running in " + Thread.currentThread());
});

thread.join();
```

Use a builder when configuration such as naming is needed:

```java
Thread thread = Thread.ofVirtual()
        .name("order-processor")
        .start(this::processOrder);
```

## One virtual thread per task

For multiple independent tasks, use a virtual-thread-per-task executor:

```java
try (var executor = Executors.newVirtualThreadPerTaskExecutor()) {
    Future<String> user = executor.submit(this::loadUser);
    Future<String> orders = executor.submit(this::loadOrders);

    System.out.println(user.get());
    System.out.println(orders.get());
}
```

This executor creates a new virtual thread for every submitted task. It does **not** reuse a fixed pool of virtual threads.

## Best use cases

Virtual threads work best when an application has many tasks that spend substantial time waiting:

- HTTP request handling.
- Database calls.
- Network services.
- File or socket I/O.
- Blocking queues and other blocking concurrency utilities.

They improve **throughput and scalability**, not the speed of an individual task.

## CPU-bound work

Virtual threads do not create more CPU cores:

```java
// A million CPU-intensive virtual threads do not make the CPU faster
Thread.startVirtualThread(this::calculateForSeveralMinutes);
```

For long-running CPU-bound work, use a bounded executor sized according to available processors. Virtual threads are most valuable when tasks frequently block.

## Do not pool virtual threads

Virtual threads are cheap and should represent tasks directly:

```text
one task = one virtual thread
```

Do not create a small pool of reusable virtual threads. If access to a limited resource must be controlled, use a resource pool or a `Semaphore`:

```java
private final Semaphore databaseLimit = new Semaphore(20);

String queryDatabase() throws InterruptedException {
    databaseLimit.acquire();
    try {
        return runQuery();
    } finally {
        databaseLimit.release();
    }
}
```

This limits database concurrency without limiting the total number of virtual threads.

## Pinning

A virtual thread is **pinned** when it cannot unmount from its carrier during a blocking operation. The carrier is then blocked as well, which can reduce scalability.

Originally, blocking inside a `synchronized` block could cause pinning. **JDK 24 delivered JEP 491**, which removed nearly all pinning caused by `synchronized` methods, monitor acquisition, and `Object.wait()`.

Interactions with native or foreign code can still cause pinning. Short or infrequent pinning is normally harmless; frequent long blocking while pinned is the concern.

## Thread-local variables

Virtual threads support `ThreadLocal`, but creating a large cached object for every virtual thread can consume significant memory when there are thousands or millions of threads.

Use thread-local variables for genuine per-task context, not as a cache of expensive reusable objects. Consider `ScopedValue` for immutable context that follows a task.

## Important properties

- A virtual thread is still a real `Thread` from the application's perspective.
- Existing blocking code can often use virtual threads without being rewritten as callbacks.
- Virtual threads support interruption, stack traces, exceptions, and thread-local variables.
- Virtual threads are daemon threads and do not keep the JVM alive by themselves.
- Their priority is fixed and should not be used for scheduling decisions.
- Shared mutable state still requires synchronization; virtual threads do not remove data races.

## Summary

Virtual threads let Java applications create one lightweight thread per blocking task. The JVM mounts runnable virtual threads on carrier platform threads and normally unmounts them while they wait, allowing a small number of OS threads to support very high concurrency. Use them for blocking, I/O-heavy workloads; do not pool them or expect them to accelerate CPU-bound computation.

## Official references

- [JEP 444: Virtual Threads — JDK 21](https://openjdk.org/jeps/444)
- [JEP 491: Synchronize Virtual Threads without Pinning — JDK 24](https://openjdk.org/jeps/491)
- [Oracle Java 25 Guide: Virtual Threads](https://docs.oracle.com/en/java/javase/25/core/virtual-threads.html)
