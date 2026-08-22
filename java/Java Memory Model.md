# Java Memory Model

## Front

What is the **Java Memory Model (JMM)**?

Explain:

- Visibility, ordering, and atomicity.
- The happens-before relationship.
- The guarantees provided by `synchronized`, `volatile`, `final`, thread lifecycle methods, locks, and atomic classes.
- What constitutes a data race.
- Modern `VarHandle` memory-ordering modes.
- Whether virtual threads use a different memory model.

## Back

The **Java Memory Model (JMM)** defines the rules for how multiple threads see and modify shared memory.

It is important not to confuse it with:

- Heap
- Stack
- Metaspace
- Garbage collection

Those describe JVM memory organization. The JMM instead answers questions such as:

> “If Thread A changes a variable, when is Thread B guaranteed to see that change?”

The current Java specification defines the JMM primarily through **happens-before**, synchronization actions, visibility, ordering, and data races.

## The three ideas to remember

### 1. Visibility

Visibility means that a value written by one thread becomes observable by another thread.

> **Key idea:** Visibility determines whether one thread can observe another thread's latest writes.

Without synchronization, the Java Memory Model does not guarantee when—or whether—another thread will observe a write.

#### Visibility problem

```java
boolean ready = false;

// Thread A
ready = true;

// Thread B
while (!ready) {
}
```

Thread B is not guaranteed to observe `true`. The compiler, JVM, CPU, and CPU caches may reuse or reorder values when no happens-before relationship exists.

#### Visibility solution

```java
volatile boolean ready = false;
```

A write to a volatile variable happens-before every subsequent read of that same variable.

Visibility can also be established by:

- Releasing a `synchronized` monitor and later acquiring that same monitor.
- Unlocking a `Lock` and later locking that same `Lock`.
- Starting a thread with `Thread.start()`.
- Waiting for a thread with `Thread.join()`.
- Using concurrent classes such as `AtomicInteger`.

### 2. Ordering

Ordering describes the sequence in which memory operations are observed.

> **Key idea:** Ordering controls which sequence of memory operations another thread is allowed to observe.

The compiler, JIT compiler, and CPU may reorder operations when the reordering does not change the result of a single-threaded program. Another thread, however, may observe those operations in an unexpected order when no happens-before relationship exists.

#### Ordering problem

```java
int data = 0;
boolean ready = false;

// Thread A
data = 42;
ready = true;

// Thread B
if (ready) {
    System.out.println(data);
}
```

Without synchronization, Thread B is not guaranteed to observe the writes in the intended order. It may observe `ready == true` without reliably observing `data == 42`.

#### Ordering solution

```java
int data = 0;
volatile boolean ready = false;

// Thread A
data = 42;
ready = true;

// Thread B
if (ready) {
    System.out.println(data); // 42
}
```

When Thread B reads `ready == true`, the write to `data` that occurred before the volatile write is also visible.

The same ordering guarantee can be created with `synchronized`, locks, and other happens-before relationships.

### 3. Atomicity

An operation is atomic when it happens as one indivisible action.

> **Key idea:** Atomicity prevents other threads from observing or interfering with a partially completed operation.

Other threads cannot observe it halfway through: they see either the state before the operation or the state after it.

#### Non-atomic example

```java
count++;
```

Although this is one Java statement, it consists of several actions:

1. Read `count`.
2. Add 1.
3. Write the new value.

Two threads can read the same old value and overwrite each other's updates. This is a **lost update**.

#### Atomic solution

```java
AtomicInteger count = new AtomicInteger();

count.incrementAndGet();
```

Another solution is to protect the compound operation with the same lock:

```java
synchronized (lock) {
    count++;
}
```

> **Important:** `volatile` guarantees visibility and ordering, but it does not make compound operations such as `count++` atomic.

## The most important JMM concept: happens-before

For everyday Java programming, **happens-before** is the central concept.

If A happens-before B, the effects of A are guaranteed to be visible to B, and A is ordered before B from the JMM's perspective.

The current Java Language Specification explicitly defines this relationship.

```text
A
│
│ happens-before
↓
B
```

This means B can safely observe what A did.

Several common Java constructs create happens-before relationships:

| Operation A | Happens-before operation B |
|---|---|
| Earlier action in one thread | Later action in the same thread |
| `synchronized` unlock | Later lock of the same monitor |
| `volatile` write | Later read of the same volatile variable |
| `Thread.start()` | Actions performed by the started thread |
| All actions in a thread | Another thread successfully returns from `Thread.join()` |

These relationships are explicitly part of the JMM.

## `synchronized`

Consider:

```java
// Thread A
synchronized (lock) {
    value = 42;
}
```

and another thread:

```java
// Thread B
synchronized (lock) {
    System.out.println(value);
}
```

There is a relationship:

```text
Thread A

write value = 42
      ↓
unlock(lock)
      │
      │ happens-before
      ↓
lock(lock)
      ↓
read value

Thread B
```

The second thread is therefore guaranteed to see the writes that happened before the first thread released that **same monitor**.

## `volatile`

`volatile` is lighter-weight than locking and is mainly about **visibility + ordering**.

```java
volatile boolean running = true;

// Thread A
running = false;

// Thread B
while (running) {
    // work
}
```

Conceptually:

```text
volatile write
      │
      │ happens-before
      ↓
volatile read
```

But this does not make compound operations atomic.

This is still unsafe:

```java
volatile int count;

count++;
```

because `count++` contains several operations.

## `final` has special JMM semantics

`final` fields have stronger initialization guarantees.

```java
class User {
    final int age;

    User() {
        age = 30;
    }
}
```

If the object is constructed correctly and the reference does not improperly escape during construction, other threads get special guarantees for properly initialized final fields.

The JMM has an entire section specifically for final-field semantics.

This is one reason immutable objects work particularly well for concurrency:

```java
final class User {
    private final String name;
    private final int age;
}
```

## Data race

A **data race** occurs when two threads access the same shared variable:

- At least one access is a write, and
- The accesses are not ordered by happens-before.

The Java Language Specification defines a data race in essentially these terms.

Example:

```java
int x;

// Thread A
x = 10;

// Thread B
System.out.println(x);
```

with no synchronization between them:

```text
Thread A            Thread B

x = 10              read x
   \                 /
    no happens-before
          ↓
       DATA RACE
```

Once you have data races, reasoning about what another thread can observe becomes much harder.

## Modern Java adds finer-grained memory ordering

Since Java 9, `VarHandle` exposes several levels of memory semantics:

- Plain
- Opaque
- Acquire / Release
- Volatile

Rough mental model:

```text
weaker ordering                         stronger ordering

Plain → Opaque → Acquire/Release → Volatile
```

| Mode | Main guarantee |
|---|---|
| Plain | Ordinary non-volatile access; no cross-thread ordering constraints |
| Opaque | Coherent ordering for accesses to the same variable |
| Acquire read | Later loads and stores cannot move before the acquire |
| Release write | Earlier loads and stores cannot move after the release |
| Volatile | Acquire/release effects plus total ordering among volatile operations |

For example:

```java
handle.getAcquire(obj);
handle.setRelease(obj, value);
```

Acquire/release can provide exactly the ordering required by sophisticated concurrent algorithms without necessarily requesting full volatile semantics.

Modern `VarHandle` also provides atomic updates:

```java
handle.compareAndSet(obj, expected, update);
handle.getAndSet(obj, value);
handle.getAndAdd(obj, delta);
```

and explicit fences:

```java
VarHandle.acquireFence();
VarHandle.releaseFence();
VarHandle.fullFence();
```

The Java 25 API documentation specifies plain, opaque, acquire/release, volatile, atomic-update, and fence semantics.

You normally do not need `VarHandle` in ordinary application code. It is much more relevant when implementing:

- Concurrent collections
- Lock-free algorithms
- Runtimes
- High-performance libraries
- Low-level infrastructure

## What about `AtomicInteger`, locks, and concurrent collections?

They ultimately give you JMM guarantees without requiring you to manually reason about CPU memory ordering.

Modern application code generally uses higher-level constructs:

```text
Java Memory Model
        ↓
synchronization primitives
        ↓
┌─────────────────────────────┐
│ synchronized                │
│ volatile                    │
│ Lock / ReentrantLock        │
│ AtomicInteger               │
│ AtomicReference             │
│ ConcurrentHashMap           │
│ BlockingQueue               │
│ CompletableFuture           │
│ concurrent collections      │
└─────────────────────────────┘
```

For example, rather than building synchronization yourself:

```java
volatile int counter;
```

you might simply use:

```java
AtomicInteger counter = new AtomicInteger();
counter.incrementAndGet();
```

## What about virtual threads?

**Virtual threads do not introduce a different memory model.**

You may have:

```java
Thread.ofVirtual().start(...);
```

instead of a traditional platform thread, but the same fundamental JMM concepts still apply:

- Visibility
- Ordering
- Atomicity
- Happens-before
- Synchronization

Virtual threads change how Java schedules and scales threads, not the fundamental rules by which threads communicate through shared memory.

## A useful modern mental model

Do not imagine each thread simply reading and writing RAM directly:

```text
Thread A ─────────→ RAM ←───────── Thread B
```

A better conceptual model is:

```text
              Java Memory Model
                     │
           defines legal behavior
                     │
       ┌─────────────┴─────────────┐
       ↓                           ↓
   Thread A                    Thread B
       │                           │
 JVM/compiler optimizations    JVM/compiler
       │                           │
       └──── CPU / caches / memory ┘
```

The compiler and processor may optimize aggressively.

The JMM defines:

> Which results those optimizations are allowed to expose to your Java program.

## Interview summary

The Java Memory Model is not the heap layout. It is the set of rules governing communication through shared memory. **Visibility** determines whether one thread can observe another thread's writes. **Ordering** constrains the order in which those operations can be observed. **Atomicity** makes an operation indivisible. Happens-before connects these concepts: if A happens-before B, A's effects are visible to and ordered before B. Constructs such as `synchronized`, `volatile`, `Thread.start()`, `Thread.join()`, locks, atomic classes, and concurrent collections establish the required guarantees. Code with conflicting accesses that are not ordered by happens-before has a data race. Virtual threads obey exactly the same JMM as platform threads.

## Official references

- [Java Language Specification §17.4: Memory Model](https://docs.oracle.com/javase/specs/jls/se25/html/jls-17.html#jls-17.4)
- [Java Language Specification §17.4.5: Happens-before Order](https://docs.oracle.com/javase/specs/jls/se25/html/jls-17.html#jls-17.4.5)
- [Java Language Specification §17.5: `final` Field Semantics](https://docs.oracle.com/javase/specs/jls/se25/html/jls-17.html#jls-17.5)
- [Java SE 25 `VarHandle` API](https://docs.oracle.com/en/java/javase/25/docs/api/java.base/java/lang/invoke/VarHandle.html)
- [Java SE 25 Virtual Threads guide](https://docs.oracle.com/en/java/javase/25/core/virtual-threads.html)
