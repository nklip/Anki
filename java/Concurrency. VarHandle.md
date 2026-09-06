# Concurrency. VarHandle

<!-- Card mode: complex. Validate with --mode complex. -->

## Front

What is a `VarHandle`, how do its ordering and atomic-update modes work, and which production libraries use it?

## Back

**Variable Handles (`VarHandle`) were introduced in JDK 9 with JEP 193.**

A `VarHandle` is an immutable, strongly typed handle to a variable—or a family of variables such as array elements. The handle identifies **what can be accessed**; each operation selects **how it is accessed**: plain, opaque, acquire/release, volatile, or atomic read-modify-write.

Use it for **fine-grained ordering or atomic access to existing fields and array elements**, especially inside concurrent data structures and runtime libraries. It is not automatically faster than `AtomicInteger` or `synchronized`; choose it for the required semantics and measure performance in the actual workload.

The core concepts are locating the target variable, choosing memory ordering, and performing atomic updates such as compare-and-set (CAS).

### Variable type and coordinates

Every handle has:

- one **variable type**: the type stored at the target; and
- zero or more **coordinate types**: the values needed to locate one target variable.

| Target | Variable type | Coordinates |
|---|---|---|
| Instance field `Counter.value` | `int` | `Counter` receiver |
| Static field | field type | none |
| `String[]` element | `String` | `String[]` and `int` index |

For an instance field, create the handle with an appropriately privileged `MethodHandles.Lookup`:

```java
import java.lang.invoke.MethodHandles;
import java.lang.invoke.VarHandle;

final class Counter {
    private int value;

    private static final VarHandle VALUE;

    static {
        try {
            VALUE = MethodHandles.lookup().findVarHandle(
                    Counter.class, "value", int.class);
        } catch (ReflectiveOperationException exception) {
            throw new ExceptionInInitializerError(exception);
        }
    }

    int getVolatile() {
        return (int) VALUE.getVolatile(this);
    }

    void setRelease(int next) {
        VALUE.setRelease(this, next);
    }

    boolean compareAndSet(int expected, int update) {
        return VALUE.compareAndSet(this, expected, update);
    }
}
```

`VALUE` has variable type `int` and coordinate type `Counter`. Thus `this` is the first argument to each access operation. Access checking happens when `findVarHandle()` creates the handle, so keep a handle private unless callers should receive that access capability.

An array-element handle uses the array and index as coordinates. These statements belong inside a method, with the imports above:

```java
VarHandle element =
        MethodHandles.arrayElementVarHandle(String[].class);

String[] values = new String[10];
element.setRelease(values, 3, "ready");
String value = (String) element.getAcquire(values, 3);
```

Array type, null, and bounds checks still apply. Access methods are **signature-polymorphic**: one method name accepts different call signatures, checked against the handle at invocation time. Incompatible coordinate, value, or return types can cause `WrongMethodTypeException` or `ClassCastException`.

### Access modes choose the memory semantics

Read the top row from weaker to stronger ordering, then use the lower flow to see release/acquire publication.

![concurrency-varhandle-access-modes.svg](svg/concurrency-varhandle-access-modes.svg)

| Mode | Main guarantee | Typical use |
|---|---|---|
| `get` / `set` | Ordinary non-volatile field semantics; no cross-thread ordering | Thread confinement or synchronization supplied elsewhere |
| `getOpaque` / `setOpaque` | Atomic access and a consistent order for the same variable; no ordering guarantee for other variables | Specialized polling or progress state |
| `getAcquire` / `setRelease` | Earlier producer accesses stay before the release; later consumer accesses stay after a matching acquire | One-way publication |
| `getVolatile` / `setVolatile` | Volatile semantics plus a total order among volatile operations | Strong, straightforward visibility and ordering |

Plain `get()` and `set()` are guaranteed bitwise atomic for references and primitive values up to 32 bits. Unless a handle's factory documents otherwise, they are also atomic for `long` and `double` on 64-bit platforms; the VarHandle API allows non-atomic plain access to those types on 32-bit platforms. Other supported read/write modes provide atomic access for references and all primitive types.

Opaque access alone does **not** publish changes to other variables. For that, use a suitable release/acquire or stronger protocol.

#### Release/acquire publication

This is a one-shot example: one producer calls `publish()` once, and consumers use the same safely shared `Publication` instance. Here the flag is never reset, and the payload is not changed again.

```java
import java.lang.invoke.MethodHandles;
import java.lang.invoke.VarHandle;

final class Publication {
    private int payload;
    private int ready;

    private static final VarHandle READY;

    static {
        try {
            READY = MethodHandles.lookup().findVarHandle(
                    Publication.class, "ready", int.class);
        } catch (ReflectiveOperationException exception) {
            throw new ExceptionInInitializerError(exception);
        }
    }

    void publish() {
        payload = 42;
        READY.setRelease(this, 1);
    }

    int consume() {
        if ((int) READY.getAcquire(this) != 1) {
            return -1;
        }
        return payload;
    }
}
```

If `getAcquire()` observes the `1` published by `setRelease()`, the producer's earlier `payload = 42` is ordered before the consumer's later read of `payload`.

The operation overrides the field declaration's ordering. `HANDLE.get(receiver)` is a plain access even if the field is declared `volatile`; `HANDLE.getVolatile(receiver)` has volatile semantics even when the field is not declared `volatile`. Mixing modes is valid only when the whole protocol remains correct.

### Compare-and-set is one atomic conditional update

The diagram first shows success versus failure, then the retry loop used when the new value depends on the current value.

![concurrency-varhandle-cas-workflow.svg](svg/concurrency-varhandle-cas-workflow.svg)

For the `int` field in `Counter`, `compareAndSet(target, expected, update)` compares the current value with `expected` using `==` and writes `update` only if they match. The comparison and conditional write form **one indivisible operation**. It returns `true` on success or `false` on failure.

For references, comparison uses identity, not `equals()`. For `float` and `double` fields or array elements, it compares **raw bits**: `+0.0` and `-0.0` differ, and NaN (not-a-number) values must have matching bit patterns. Thus the comparison is not ordinary floating-point `==`.

`compareAndSet()` reads with volatile semantics and writes with volatile semantics on success. A failed CAS performs no write.

Use a retry loop when another thread may change the value between the read and the attempted update. Add this method inside `Counter`:

```java
int incrementAndGet() {
    int current;
    int next;

    do {
        current = (int) VALUE.getVolatile(this);
        next = current + 1;
    } while (!VALUE.compareAndSet(this, current, next));

    return next;
}
```

If the CAS fails, the loop rereads and recalculates instead of overwriting the winning thread's update.

For supported numeric types, the built-in atomic operation is shorter. An alternative body for `Counter.incrementAndGet()` is:

```java
int previous = (int) VALUE.getAndAdd(this, 1);
return previous + 1;
```

`compareAndExchange()` performs the same conditional exchange but returns the value it actually witnessed, which can avoid a separate reread. Weak compare-and-set variants may fail spuriously even when the value appears to match, so they normally belong in retry loops with a deliberately selected ordering variant.

### Supported operations and fences

Not every handle supports every mode:

- a handle to a `final` field is read-only;
- numeric updates such as `getAndAdd()` require a supported numeric variable type;
- bitwise updates require a supported integral or boolean type;
- unsupported operations throw `UnsupportedOperationException`.

Check a mode when building generic low-level code. For example, inside a `Counter` method:

```java
boolean supported = VALUE.isAccessModeSupported(
        VarHandle.AccessMode.GET_AND_ADD);
```

Static methods such as `VarHandle.acquireFence()`, `releaseFence()`, and `fullFence()` constrain reordering without accessing a variable. They are advanced primitives; a correctly paired access mode is usually clearer because the synchronization point remains visible in the code.

### Choosing the right abstraction

| Need | Prefer |
|---|---|
| Simple visibility for one declared field | `volatile` |
| Convenient atomic counter or reference | `AtomicInteger`, `AtomicReference`, etc. |
| Ordered or atomic access to an existing field or array element | `VarHandle` |
| Several operations or fields protected as one invariant | `synchronized` or `Lock` |

`VarHandle` is useful in concurrent collections, queues, state machines, runtime libraries, and atomic array algorithms. It is a safe standard replacement for many on-heap `sun.misc.Unsafe` memory-access operations, but it is **not** a transaction over multiple variables. Prefer higher-level concurrency utilities in ordinary application code when they express the intent directly.

### Where VarHandle is used in production software

These are concrete implementations in released software. The OpenJDK 25 and Elasticsearch 9 examples use the latest released updates checked on **2026-09-06**. Implementation choices can change between releases.

| System or library | Component and actual use | Why it matters |
|---|---|---|
| **OpenJDK 25.0.4.1** | `ConcurrentLinkedQueue.offer()` uses `NEXT.compareAndSet(...)` to attach a new linked-list node. | Concurrent producers can append without overwriting another producer's link. |
| **OpenJDK 25.0.4.1** | `CompletableFuture.completeValue()` uses `RESULT.compareAndSet(this, null, ...)` to record completion. | Only one competing attempt can change the result from incomplete to completed. |
| **LMAX Disruptor 4.0.0** — event-processing library | `MultiProducerSequencer` uses an `int[]` element handle: `setRelease` publishes a slot's availability; `getAcquire` checks it. | Consumers can observe that a producer has finished writing an event into the ring buffer, an array reused in a cycle. |
| **Elasticsearch 9.5.3** — search and analytics system | `AbstractRefCounted.tryIncRef()` retries `weakCompareAndSet` to increment a positive reference count; `decRef()` uses `getAndAdd(this, -1)` to decrement it. | The count tracks outstanding resource references. Releasing the last reference changes the count from 1 to 0 and triggers `closeInternal()` for cleanup. |

These examples connect directly to the CAS, publication, and atomic-add operations above. They are implementation details inside these systems and libraries; application code can use their public APIs without constructing a handle itself.

### Memory aid

**Handle = target type + coordinates.**

**Access mode = ordering and atomicity for this operation.**

**CAS = compare and conditionally replace one variable atomically.**

## Sources

- [JEP 193 — Variable Handles](https://openjdk.org/jeps/193)
- [Oracle JDK 9 release notes — JEP 193](https://docs.oracle.com/javase/9/whatsnew/)
- [Java SE 25 API — `VarHandle`](https://docs.oracle.com/en/java/javase/25/docs/api/java.base/java/lang/invoke/VarHandle.html)
- [Java SE 25 API — `MethodHandles.Lookup.findVarHandle()`](https://docs.oracle.com/en/java/javase/25/docs/api/java.base/java/lang/invoke/MethodHandles.Lookup.html#findVarHandle(java.lang.Class,java.lang.String,java.lang.Class))
- [Java SE 25 API — `MethodHandles.arrayElementVarHandle()`](https://docs.oracle.com/en/java/javase/25/docs/api/java.base/java/lang/invoke/MethodHandles.html#arrayElementVarHandle(java.lang.Class))
- [JEP 471 — Deprecate the Memory-Access Methods in `sun.misc.Unsafe` for Removal](https://openjdk.org/jeps/471)
- [Doug Lea — Using JDK 9 Memory Order Modes](https://gee.cs.oswego.edu/dl/html/j9mm.html)
- [OpenJDK 25.0.4.1 (`jdk-25.0.4.1-ga`) — `ConcurrentLinkedQueue` source](https://github.com/openjdk/jdk25u/blob/jdk-25.0.4.1-ga/src/java.base/share/classes/java/util/concurrent/ConcurrentLinkedQueue.java#L354)
- [OpenJDK 25.0.4.1 (`jdk-25.0.4.1-ga`) — `CompletableFuture` source](https://github.com/openjdk/jdk25u/blob/jdk-25.0.4.1-ga/src/java.base/share/classes/java/util/concurrent/CompletableFuture.java#L305)
- [Oracle — JDK 25 release history](https://www.oracle.com/java/technologies/javase/25all-relnotes.html)
- [LMAX Disruptor 4.0.0 — `MultiProducerSequencer` source](https://github.com/LMAX-Exchange/disruptor/blob/4.0.0/src/main/java/com/lmax/disruptor/MultiProducerSequencer.java)
- [Elasticsearch 9.5.3 — `AbstractRefCounted` source](https://github.com/elastic/elasticsearch/blob/v9.5.3/libs/core/src/main/java/org/elasticsearch/core/AbstractRefCounted.java#L25)
- [Elastic — Elasticsearch release notes](https://www.elastic.co/docs/release-notes/elasticsearch)
