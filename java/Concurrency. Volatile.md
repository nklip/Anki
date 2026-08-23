# Concurrency. Volatile

## Front

What does `volatile` guarantee in Java, how can it safely publish state, and why does it not make `count++` thread-safe?

## Back

**A `volatile` field modifier provides visibility and ordering through a happens-before relationship, but it provides neither mutual exclusion nor atomic compound operations.**

The three diagrams build the idea in order: the memory-model rule, safe publication through a volatile reference, and the lost-update problem.

### Guarantees at a glance

| Property | Does `volatile` provide it? |
|---|---|
| A read sees a value allowed by the Java Memory Model | Yes |
| Visibility of earlier writes through the same volatile field | Yes |
| Ordering through a release/acquire edge | Yes |
| Atomic read or write of the volatile field itself | Yes, including `long` and `double` |
| Atomicity of `++`, check-then-act, or read-modify-write logic | **No** |
| Mutual exclusion: only one thread inside a critical section | **No** |
| Blocking, notification, fairness, or eventual thread scheduling | **No** |

`volatile` can modify an instance or static field. A local variable or method parameter cannot be volatile.

### The happens-before rule

![A writer publishes ordinary state through a volatile flag, and a reader acquires that state by reading the same flag](svg/concurrency-volatile-happens-before.svg)

A write to a volatile field **happens-before every subsequent read of that same field**. The write acts as a **release**; the matching read acts as an **acquire**.

Program order and happens-before are transitive. Therefore, when the reader observes the published volatile value, it also sees the ordinary writes that the writer completed before the volatile write.

```java
final class MessageBox {
    private int data;
    private String message;
    private volatile boolean ready;

    void publish() {
        data = 42;              // ordinary write
        message = "ready";      // ordinary write
        ready = true;           // volatile release write
    }

    String consume() {
        if (!ready) {           // volatile acquire read
            return "not ready";
        }
        return data + ": " + message;
    }
}
```

If `consume()` reads `ready == true` from the publication, it is guaranteed to see `data == 42` and `message.equals("ready")` from before that publication.

The edge must go through the **same volatile field**. Writing one volatile field and reading an unrelated volatile field does not establish this direct publication relationship.

> Think in terms of Java Memory Model guarantees, not “always reading RAM.” The JVM and CPU may still use registers, caches, and optimizations as long as observable behavior obeys the model.

### Safely publishing an immutable snapshot

![A fully constructed immutable object is published through a volatile reference and then read with its initialized state visible](svg/concurrency-volatile-reference-publication.svg)

The volatile field may be a reference. Construct a complete object first, then place its reference in the volatile field. A thread that later reads that reference acquires the state written before publication.

```java
record Config(String host, int timeoutSeconds) {}

final class ConfigService {
    private volatile Config current =
            new Config("api.example.com", 30);

    Config current() {
        return current;          // volatile acquire read
    }

    void reload(String host, int timeoutSeconds) {
        Config next = new Config(host, timeoutSeconds);
        current = next;          // volatile release write
    }
}
```

This pattern is especially clear with an immutable object: readers receive either the old complete snapshot or the new complete snapshot, never a partially updated combination of its fields.

However, a volatile reference does **not** make the referenced object deeply volatile:

```java
volatile int[] values = new int[10];
```

Here, reads and writes of `values` are volatile, but `values[0]` is still an ordinary array-element access. Likewise, mutating fields inside an already published mutable object does not automatically publish each later mutation. Prefer replacing an immutable snapshot, or protect internal mutations with a lock, atomics, or another appropriate synchronization mechanism.

### Why `count++` still loses updates

![Two threads read the same volatile counter value, both calculate the same next value, and one increment is lost](svg/concurrency-volatile-lost-update.svg)

```java
final class VolatileCounter {
    private volatile int count;

    void increment() {
        count++;                 // not one atomic action
    }

    int get() {
        return count;
    }
}
```

`count++` means:

1. read `count`;
2. calculate `count + 1`;
3. write the result.

Each individual volatile read and write is atomic, but the three-action sequence is not. Two threads can both read `0`, both calculate `1`, and both write `1`. The final value is `1`, although two increments occurred.

For a single atomic counter, use an atomic read-modify-write operation:

```java
import java.util.concurrent.atomic.AtomicInteger;

final class AtomicCounter {
    private final AtomicInteger count = new AtomicInteger();

    void increment() {
        count.incrementAndGet();
    }

    int get() {
        return count.get();
    }
}
```

Use `synchronized` or a `Lock` when several actions or fields must change together as one critical section.

### When `volatile` is a good fit

Use it when all of these are true:

- one field or immutable snapshot represents the published state;
- threads perform independent reads and simple replacement writes;
- an update does not depend on the field's current value;
- no multi-field invariant or critical section must be protected;
- no blocking or wake-up mechanism is required.

Typical examples are a stop/ready flag, a status field, or an immutable configuration snapshot. A volatile stop flag only makes the flag visible: it does not wake a thread blocked in I/O, waiting on a monitor, or otherwise unable to check the flag.

### Choosing the mechanism

| Need | Prefer | Why |
|---|---|---|
| Publish a flag or independently replaced value | `volatile` | Visibility and ordering with simple field access |
| Atomically update one value from its current value | `AtomicInteger`, `AtomicReference`, etc. | Atomic compare-and-set/read-modify-write operations |
| Protect several operations or related fields | `synchronized` or `Lock` | Mutual exclusion around a critical section |
| Publish related values mainly for reading | Immutable object + volatile reference | Readers see a complete old or new snapshot |
| Pass every event to a consumer | Queue, channel, latch, semaphore, etc. | A volatile field stores only its current value; intermediate values may be missed |

### Common traps

- `volatile` is not a lightweight replacement for every lock; it solves a narrower visibility-and-ordering problem.
- `volatile int[]` makes the array **reference** volatile, not its elements. Use synchronization, immutable replacement, or a class such as `AtomicIntegerArray` when element updates need stronger guarantees.
- A reader can miss intermediate values if a volatile field changes several times before it reads again. Volatile fields are state, not event queues.
- `volatile` does not make `if (!initialized) { initialize(); }` atomic; that is a check-then-act sequence.
- A field cannot be both `final` and `volatile`: `final` prevents reassignment, while volatile publication requires field writes after initialization.
- Visibility cannot guarantee liveness. The scheduler may delay a thread, and blocking operations may prevent it from observing a new value.

### Memory aid

**`volatile` = visible, ordered publication of one field.**

**Atomic class = one value updated atomically.**

**Lock = a protected multi-action or multi-field invariant.**

## Sources

- [Java Language Specification, §8.3.1.4 — `volatile` Fields](https://docs.oracle.com/javase/specs/jls/se26/html/jls-8.html#jls-8.3.1.4)
- [Java Language Specification, §17.4.5 — Happens-before Order](https://docs.oracle.com/javase/specs/jls/se26/html/jls-17.html#jls-17.4.5)
- [Java Language Specification, §17.7 — Non-Atomic Treatment of `double` and `long`](https://docs.oracle.com/javase/specs/jls/se26/html/jls-17.html#jls-17.7)
- [Java SE 26 API — `AtomicInteger`](https://docs.oracle.com/en/java/javase/26/docs/api/java.base/java/util/concurrent/atomic/AtomicInteger.html)
- [Java SE 26 API — `AtomicIntegerArray`](https://docs.oracle.com/en/java/javase/26/docs/api/java.base/java/util/concurrent/atomic/AtomicIntegerArray.html)
